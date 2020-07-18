from math import inf, log10, ceil, floor
from itertools import count
from sys import float_info


class ExtendedWilkinson:
    """
    An Extension of Wilkinson's Algorithm for Position Tick Labels on Axes

    The "Extended-Wilkinson" algorithm described in the paper
    Talbot, J., Lin, S., & Hanrahan, P. (2010). An extension of Wilkinson’s
    algorithm for positioning tick labels on axes. IEEE VGTC, 16(6), 1036-1043.

    Parameters: target font size `fs_t`, minimum font size `fs_min`.

    Translated by Carsten Allefeld from the R code by Justin Talbot, see
    https://rdrr.io/rforge/labeling/src/R/labeling.R
    """

    Q = [1, 5, 2, 2.5, 4, 3]
    "preference-ordered list of nice step sizes"

    w = [0.25, 0.2, 0.5, 0.05]
    "weights for the subscores simplicity, coverage, density, and legibility"

    def __init__(self, fs_t, fs_min):
        self.fs_t = fs_t
        self.fs_min = fs_min

    # scoring functions, including the approximations for limiting the search

    def simplicity(self, i, j, lmin, lmax, lstep):
        eps = float_info.epsilon * 100
        v = ((lmin % lstep < eps or lstep - (lmin % lstep) < eps)
             and lmin <= 0 and lmax >= 0) * 1
        return 1 - (i - 1) / (len(self.Q) - 1) - j + v

    def simplicity_max(self, i, j):
        return 1 - (i - 1) / (len(self.Q) - 1) - j + 1

    def coverage(self, dmin, dmax, lmin, lmax):
        return (1 - 0.5 * ((dmax - lmax)**2 + (dmin - lmin)**2)
                / (0.1 * (dmax - dmin))**2)

    def coverage_max(self, dmin, dmax, span):
        range = dmax - dmin
        if span > range:
            half = (span - range) / 2
            return 1 - 0.5 * (2 * half ** 2) / (0.1 * range)**2
        else:
            return 1

    def density(self, k, m, dmin, dmax, lmin, lmax):
        r = (k - 1) / (lmax - lmin)
        rt = (m - 1) / (max(lmax, dmax) - min(dmin, lmin))
        return 2 - max((r / rt, rt / r))

    def density_max(self, k, m):
        return 2 - (k - 1) / (m - 1) if k >= m else 1

    def legibility(self, lmin, lmax, lstep):
        return 1

    # optimization algorithm

    def extended(self, dmin, dmax, m, only_loose=False):
        w = self.w
        eps = float_info.epsilon * 100

        if dmin > dmax:
            dmin, dmax = dmax, dmin

        if dmax - dmin < eps:
            # If the range is near the floating point limit,
            # let seq generate some equally spaced steps.
            return range(m) / (m - 1) * (dmax - dmin) + dmin

        best = dict(score=-2)

        for j in count(start=1):
            for i, q in enumerate(self.Q, start=1):
                # i is `match(q, Q)[1]` and replaces `q, Q` in function calls
                sm = self.simplicity_max(i, j)

                if w[0]*sm + w[1] + w[2] + w[3] < best['score']:
                    # to break out of i *and* j
                    j = inf
                    break

                for k in count(start=2):      # loop over tick counts
                    dm = self.density_max(k, m)

                    if w[0]*sm + w[1] + w[2]*dm + w[3] < best['score']:
                        break

                    delta = (dmax - dmin) / (k + 1) / (j * q)

                    for z in count(start=ceil(log10(delta))):
                        step = q * j * 10**z

                        cm = self.coverage_max(dmin, dmax, step * (k - 1))

                        if w[0]*sm + w[1]*cm + w[2]*dm + w[3] < best['score']:
                            break

                        min_start = floor(dmax / step) * j - (k - 1) * j
                        max_start = ceil(dmin / step) * j

                        if min_start > max_start:
                            continue

                        for start in range(min_start, max_start + 1):
                            lmin = start * step / j
                            lmax = lmin + step * (k - 1)
                            lstep = step

                            s = self.simplicity(i, j, lmin, lmax, lstep)
                            c = self.coverage(dmin, dmax, lmin, lmax)

                            g = self.density(k, m, dmin, dmax, lmin, lmax)
                            l = self.legibility(lmin, lmax, lstep)                  # noqa E741

                            score = w[0]*s + w[1]*c + w[2]*g + w[3]*l

                            if (score > best['score']
                                and (not only_loose
                                     or (lmin <= dmin and lmax >= dmax))):

                                best = dict(
                                    lmin=lmin,
                                    lmax=lmax,
                                    lstep=lstep,
                                    score=score,
                                    # j=j,
                                    # i=i,
                                    # q=q,
                                    # k=k,
                                    # z=z,
                                    # start=start,
                                    )
            if j == inf:
                # additionally break out of j
                break

        return best
        # return [
        #     index * best['lstep'] + best['lmin']
        #     for index in
        #     range(round((best['lmax'] - best['lmin']) / best['lstep']) + 1)]

# without 'legibility' quite fast, 1.33 ms on average
