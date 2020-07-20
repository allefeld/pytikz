"""
Extended-Wilkinson algorithm for ticks and tick labels

Following Talbot, J., Lin, S., & Hanrahan, P. (2010). An extension of
Wilkinson’s algorithm for positioning tick labels on axes. *IEEE Trans.
Vis. Comput. Graph.*, 16(6), 1036-1043.

Translated by Carsten Allefeld from the R code by Justin Talbot, see
https://rdrr.io/rforge/labeling/src/R/labeling.R
"""

from math import log10, ceil, floor
from itertools import count
from decimal import Decimal as D


class cfg:
    "tikz.extended_wilkinson configuration variables"

    Q = [D(1), D(5), D(2), D('2.5'), D(4), D(3)]
    """
    preference-ordered list of nice step sizes

    Values must be of type `decimal.Decimal`.
    """

    w = [0.25, 0.2, 0.5, 0.05]
    "weights for the subscores simplicity, coverage, density, and legibility"


class TicksGenerator:
    "choose ticks values and labels"

    def __init__(self, fs_t, fs_min, rt, only_loose=True, normalize=True):
        self.fs_t = fs_t
        self.fs_min = fs_min
        self.rt = rt
        self.only_loose = only_loose
        self.normalize = normalize

    # scoring functions, including the approximations for limiting the search

    def _simplicity(self, i, start, j, k):
        # v: is zero included in the ticks?
        # modifications
        # - (lmin % lstep < eps or lstep - (lmin % lstep) < eps),
        #   means lmin / lstep = start / j is an integer
        # - lmin <= 0 means start <=0
        # - lmax >= 0 means start + j * (k - 1) >= 0
        v = (start % j == 0 and start <= 0 and start + j * (k - 1) >= 0) * 1
        return 1 - (i - 1) / (len(cfg.Q) - 1) - j + v

    def _simplicity_max(self, i, j):
        # upper bound on _simplicity w.r.t. k, z, start
        # = w.r.t. v
        return 1 - (i - 1) / (len(cfg.Q) - 1) - j + 1

    def _coverage(self, dmin, dmax, lmin, lmax):
        return (1 - 0.5 * ((dmax - lmax)**2 + (dmin - lmin)**2)
                / (0.1 * (dmax - dmin))**2)

    def _coverage_max(self, dmin, dmax, span):
        # upper bound on _coverage w.r.t. start
        range = dmax - dmin
        # The original code has a branching which I don't think is necessary.
        # if span > range:
        #     half = (span - range) / 2
        #     return 1 - 0.5 * (2 * half ** 2) / (0.1 * range)**2
        # else:
        #     return 1
        half = (span - range) / 2
        return 1 - 0.5 * (2 * half ** 2) / (0.1 * range)**2

    def _density(self, k, m, dmin, dmax, lmin, lmax):
        r = (k - 1) / (lmax - lmin)
        rt = (m - 1) / (max(lmax, dmax) - min(dmin, lmin))
        return 2 - max((r / rt, rt / r))

    def _density_max(self, k, m):
        # From original code, which I don't understand.
        if k >= m:
            return 2 - (k - 1) / (m - 1)
        else:
            # Probably just the trivial upper bound.
            return 1

    def _legibility(self):
        return 1

    def _score(self, s, c, d, l):
        # combined score
        return cfg.w[0] * s + cfg.w[1] * c + cfg.w[2] * d + cfg.w[3] * l

    # optimization algorithm

    def ticks(self, dmin, dmax, length=None, m=None):
        if m is None:
            # The implementation here is based on the R code, which is defined
            # in terms of `m`, the target number of ticks. It optimizes w.r.t.
            # the ratio between the two quantities
            #   r = (k - 1) / (lmax - lmin)
            #   rt = (m - 1) / (max(lmax, dmax) - min(dmin, lmin))
            # We want to instead specify the physical density (e.g. in 1/cm),
            # stored as a class attribute `self.rt`, and the parameter `length`
            # (e.g. in cm). Assuming that the axis spans `min(dmin, lmin)` to
            # `max(lmax, dmax)`, while the ticks span lmin to lmax, the
            # optimization should use the ratio of
            #   r = (k - 1) / (length * (lmax - lmin))
            #       * (max(lmax, dmax) - min(dmin, lmin))
            # to `self.rt`.
            # It turns out that the two ratios are equivalent if one sets
            m = self.rt * length + 1

        # without 'legibility' quite fast, around 1 ms

        if dmin > dmax:
            dmin, dmax = dmax, dmin

        # threshold for optimization
        best_score = -2

        # We combine the j and q loops into one to enable breaking out of both
        # simultaneously, by iterating over a generator; and we create an
        # index i corresponding to q at the same time. i is `match(q, Q)[1]`
        # and replaces `q, Q` in function calls.
        JIQ = ((j, i, q)
               for j in count(start=1)
               for i, q in enumerate(cfg.Q, start=1))
        for j, i, q in JIQ:
            sm = self._simplicity_max(i, j)

            if self._score(sm, 1, 1, 1) < best_score:
                break

            for k in count(start=2):      # loop over tick counts
                dm = self._density_max(k, m)

                if self._score(sm, 1, dm, 1) < best_score:
                    break

                delta = (dmax - dmin) / (k + 1) / (j * float(q))

                for z in count(start=ceil(log10(delta))):
                    step = float(q) * j * 10**z

                    cm = self._coverage_max(dmin, dmax, step * (k - 1))

                    if self._score(sm, cm, dm, 1) < best_score:
                        break

                    min_start = floor(dmax / step) * j - (k - 1) * j
                    max_start = ceil(dmin / step) * j

                    if min_start > max_start:
                        continue

                    for start in range(min_start, max_start + 1):
                        lmin = start * step / j
                        lmax = lmin + step * (k - 1)
                        # lstep = step

                        # In terms of loop variables:
                        # lmin = q * start * 10**z
                        # lmax = q * (start + j * (k - 1)) * 10 ** z
                        # lstep = float(q) * j * 10**z

                        if self.only_loose:
                            if lmin > dmin or lmax < dmax:
                                continue

                        s = self._simplicity(i, start, j, k)
                        c = self._coverage(dmin, dmax, lmin, lmax)
                        d = self._density(k, m, dmin, dmax, lmin, lmax)

                        score = self._score(s, c, d, 1)

                        if score < best_score:
                            continue

                        best_score = score
                        ticklabels = Ticks(
                            q, start, j, z, k,
                            self.normalize)

        return ticklabels


class Ticks:
    "represent tick values and labels"
    def __init__(self, q, start, j, z, k, normalize):
        self.q = q
        self.start = start
        self.j = j
        self.z = z
        self.k = k
        self.normalize = normalize

    def values(self):
        "get tick values as floats"
        return [float(self.q) * (self.start + self.j * ind) * 10 ** self.z
                for ind in range(self.k)]

    def _decimal(self, z0=0):
        "get tick values as `Decimal`s, relative to decadic power `z0`"
        # The D('1E1') notation is necessary to keep the number of significant
        # digits from q in the result.
        return [self.q * (self.start + self.j * ind)
                * D('1E1') ** (self.z - z0)
                for ind in range(self.k)]

    # For the moment, we only implement the formats 'Decimal' and 'Factored
    # Scientific'.

    def labels_Decimal(self):
        "get labels in 'Decimal' format"
        # get values
        dvs = self._decimal()
        # create labels
        if self.normalize:
            labels = ['{:f}'.format(dv.normalize()) for dv in dvs]
        else:
            labels = ['{:f}'.format(dv) for dv in dvs]
        return labels, None

    def labels_Scientific(self):
        "get labels in 'Scientific format'"
        # get values
        dvs = self._decimal()
        # get largest power of 10 than can be factored out
        z0 = min([floor(log10(abs(dv))) for dv in dvs if dv != 0])
        # get values adjusted to that power
        dvs = self._decimal(z0=z0)
        # create labels
        if self.normalize:
            labels = ['{:f}'.format(dv.normalize()) for dv in dvs]
        else:
            labels = ['{:f}'.format(dv) for dv in dvs]
        plabel = '{:d}'.format(z0)
        return labels, plabel
