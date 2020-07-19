from math import log10, ceil, floor
from itertools import count
from sys import float_info
from decimal import Decimal as D


class ExtendedWilkinson:
    """
    Extended-Wilkinson algorithm for ticks and tick labels

    Following Talbot, J., Lin, S., & Hanrahan, P. (2010). An extension of
    Wilkinson’s algorithm for positioning tick labels on axes. *IEEE Trans.
    Vis. Comput. Graph.*, 16(6), 1036-1043.

    Parameters: target font size `fs_t`, minimum font size `fs_min`.

    Translated by Carsten Allefeld from the R code by Justin Talbot, see
    https://rdrr.io/rforge/labeling/src/R/labeling.R
    """

    Q = [D(1), D(5), D(2), D('2.5'), D(4), D(3)]
    """
    preference-ordered list of nice step sizes

    Values must be of type `decimal.Decimal`.
    """

    w = [0.25, 0.2, 0.5, 0.05]
    "weights for the subscores simplicity, coverage, density, and legibility"

    def __init__(self, fs_t, fs_min):
        self.fs_t = fs_t
        self.fs_min = fs_min

    # scoring functions, including the approximations for limiting the search

    def _simplicity(self, i, j, lmin, lmax, lstep):
        eps = float_info.epsilon * 100
        v = ((lmin % lstep < eps or lstep - (lmin % lstep) < eps)
             and lmin <= 0 and lmax >= 0) * 1
        return 1 - (i - 1) / (len(self.Q) - 1) - j + v

    def _simplicity_max(self, i, j):
        return 1 - (i - 1) / (len(self.Q) - 1) - j + 1

    def _coverage(self, dmin, dmax, lmin, lmax):
        return (1 - 0.5 * ((dmax - lmax)**2 + (dmin - lmin)**2)
                / (0.1 * (dmax - dmin))**2)

    def _coverage_max(self, dmin, dmax, span):
        range = dmax - dmin
        if span > range:
            half = (span - range) / 2
            return 1 - 0.5 * (2 * half ** 2) / (0.1 * range)**2
        else:
            return 1

    def _density(self, k, m, dmin, dmax, lmin, lmax):
        r = (k - 1) / (lmax - lmin)
        rt = (m - 1) / (max(lmax, dmax) - min(dmin, lmin))
        return 2 - max((r / rt, rt / r))

    def _density_max(self, k, m):
        return 2 - (k - 1) / (m - 1) if k >= m else 1

    def _legibility(self, lmin, lmax, lstep):
        return 1

    def _score(self, s, c, d, l):
        # combined score
        return self.w[0] * s + self.w[1] * c + self.w[2] * d + self.w[3] * l

    # optimization algorithm

    def _extended(self, dmin, dmax, m, only_loose):
        eps = float_info.epsilon * 100

        if dmin > dmax:
            dmin, dmax = dmax, dmin

        if dmax - dmin < eps:
            return None

        # threshold for optimization
        best = dict(score=-2)

        # We combine the j and q loops into one to enable breaking out of both
        # simultaneously, by iterating over a generator, and we create an
        # index i corresponding to q at the same time. i is `match(q, Q)[1]`
        # and replaces `q, Q` in function calls.
        JIQ = ((j, i, q)
               for j in count(start=1)
               for i, q in enumerate(self.Q, start=1))
        for j, i, q in JIQ:
            sm = self._simplicity_max(i, j)

            if self._score(sm, 1, 1, 1) < best['score']:
                break

            for k in count(start=2):      # loop over tick counts
                dm = self._density_max(k, m)

                if self._score(sm, 1, dm, 1) < best['score']:
                    break

                delta = (dmax - dmin) / (k + 1) / (j * float(q))

                for z in count(start=ceil(log10(delta))):
                    step = float(q) * j * 10**z

                    cm = self._coverage_max(dmin, dmax, step * (k - 1))

                    if self._score(sm, cm, dm, 1) < best['score']:
                        break

                    min_start = floor(dmax / step) * j - (k - 1) * j
                    max_start = ceil(dmin / step) * j

                    if min_start > max_start:
                        continue

                    for start in range(min_start, max_start + 1):
                        lmin = start * step / j
                        lmax = lmin + step * (k - 1)
                        lstep = step

                        if only_loose:
                            if lmin > dmin or lmax < dmax:
                                continue

                        s = self._simplicity(i, j, lmin, lmax, lstep)
                        c = self._coverage(dmin, dmax, lmin, lmax)
                        d = self._density(k, m, dmin, dmax, lmin, lmax)
                        l = self._legibility(lmin, lmax, lstep)                      # noqa E741

                        score = self._score(s, c, d, l)

                        if score > best['score']:
                            best = dict(
                                lmin=lmin,
                                lmax=lmax,
                                lstep=lstep,
                                score=score,
                                k=k,
                                q=q,
                                start=start,
                                j=j,
                                z=z
                            )

        return best
        # without 'legibility' quite fast, 1.33 ms on average

    def ticks(self, dmin, dmax, m, only_loose=False):
        # run optimization
        best = self._extended(dmin, dmax, m, only_loose)
        # store result for debugging
        self.last_best = best
        # create ticks
        param = [best[key] for key in ['q', 'start', 'j', 'z', 'k']]
        ticks = Ticks(*param)
        return ticks


class Ticks:
    "represents a set of tick values"
    def __init__(self, q, start, j, z, k):
        self.q = q
        self.start = start
        self.j = j
        self.z = z
        self.k = k

    def values(self):
        "get tick values as floats"
        return [float(self.q) * (self.start + self.j * ind) * 10 ** self.z
                for ind in range(self.k)]

    def _decimal(self, z0=0):
        "get tick values as `Decimal`s, relative to decadic power `z0`"
        return [self.q * (self.start + self.j * ind) * D(10) ** (self.z - z0)
                for ind in range(self.k)]

    # For the moment, we only implement the formats 'Decimal' and 'Factored
    # Scientific'.

    def labels_Decimal(self):
        "get labels in 'Decimal' format"
        # get values
        dvs = self._decimal()
        # create labels
        return ['{:f}'.format(dv.normalize()) for dv in dvs]

    def labels_Scientific(self):
        "get labels in 'Scientific format'"
        # get values
        dvs = self._decimal()
        # get largest power of 10 than can be factored out
        z0 = min([floor(log10(abs(dv))) for dv in dvs if dv != 0])
        # get values adjusted to that power
        dvs = self._decimal(z0=z0)
        # create labels
        return ['{:f}'.format(dv.normalize()) for dv in dvs], '{:d}'.format(z0)
