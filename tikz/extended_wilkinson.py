"""
Extended-Wilkinson algorithm for ticks and tick labels

Following Talbot, J., Lin, S., & Hanrahan, P. (2010). An extension of
Wilkinson’s algorithm for positioning tick labels on axes. *IEEE Trans.
Vis. Comput. Graph.*, 16(6), 1036-1043.

Translated by Carsten Allefeld from the
[R code](https://rdrr.io/rforge/labeling/src/R/labeling.R)
and [additional information](https://github.com/jtalbot/Labeling/issues/1)
by Justin Talbot.
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

    font_metrics = {'offset': 0.1, '-': 0.678, '1': 0.5, '2': 0.5, '3': 0.5,
                    '4': 0.5, '5': 0.5, '6': 0.5, '7': 0.5, '8': 0.5, '9': 0.5,
                    '0': 0.5, '.': 0.278, 'height': 0.728}
    """
    default font metrics

    Font metrics are used to calculate the width and height of tick labels.
    They are specified as a `dict` that contains the width of each character
    that can occur in a tick label, where the character is the dictionary key,
    as well as an 'offset' to be added to the total width, and a 'height'.
    All numbers are in units of the font size.

    The default values are correct for TeX's 'Computer Modern Roman' in math
    mode.
    """


class TicksGenerator:
    """
    generator of tick values and labels

    - `font_sizes`: admissible font sizes, in TeX pt (2.54 cm / 72.27)
    - `density`: target density of ticks, in 1/cm
    - `font_metrics`: see `cfg.font_metrics`
    - `only_loose`: whether the range of tick values is forced to encompass the
      range of data values
    - `normalize`: whether trailing '0' decimals are stripped from tick labels
    """

    def __init__(self, font_sizes, density,
                 font_metrics=None, only_loose=True, normalize=True):
        if font_metrics is None:
            font_metrics = cfg.font_metrics
        self.font_sizes = sorted(font_sizes)
        self.rt = density
        self.font_metrics = font_metrics
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

    def _score(self, s, c, d, l):
        # combined score
        return cfg.w[0] * s + cfg.w[1] * c + cfg.w[2] * d + cfg.w[3] * l

    # optimization algorithm

    def ticks(self, dmin, dmax, length, horizontal):
        """
        generate tick values and labels for a given axis

        - `dmin`, `dmax`: range of data values
        - `length`: physical length of the axis, in cm
        - `horitontal`: whether the axis is oriented horizontally

        returns `Ticks` object
        """
        # without 'legibility' quite fast, around 1 ms

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
                        #   lmin = q * start * 10**z
                        #   lmax = q * (start + j * (k - 1)) * 10 ** z
                        #   lstep = float(q) * j * 10**z
                        # used in Ticks.values and ._decimal.

                        if self.only_loose:
                            if lmin > dmin or lmax < dmax:
                                continue

                        s = self._simplicity(i, start, j, k)
                        c = self._coverage(dmin, dmax, lmin, lmax)
                        d = self._density(k, m, dmin, dmax, lmin, lmax)

                        score = self._score(s, c, d, 1)

                        if score < best_score:
                            continue

                        ticks = Ticks(
                            q, start, j, z, k,
                            self.normalize,
                            self.font_sizes,
                            self.font_metrics,
                            length,
                            min(lmin, dmin), max(lmax, dmax),
                            horizontal)
                        l = ticks.opt_legibility                                    # noqa E741

                        score = self._score(s, c, d, l)

                        if score > best_score:
                            best_score = score

        return ticks


class Ticks:
    "represent tick values and labels"
    # TODO: privatize!
    def __init__(self, q, start, j, z, k,
                 normalize, font_sizes, font_metrics,
                 length, amin, amax, horizontal):
        self.q = q
        self.start = start
        self.j = j
        self.z = z
        self.k = k
        self.normalize = normalize
        self.amin = amin
        self.amax = amax

        self._optimize(font_sizes, font_metrics, length, horizontal)

    def _optimize(self, font_sizes, font_metrics, length, horizontal):
        "optimize legibility in terms of format, font size, and orientation"
        # factors:
        # - format: 'Decimal' or 'Factored Scientific'
        #   0-extended is not implemented because it's a user option
        # - font size: in the range fs_min to fs_t
        # - orientation: 'horizontal' or 'vertical'
        # parameters:
        # - tick values
        # - axis orientation
        # - axis length
        # subscores:
        # - Format: depends on format and tick values
        # - Font size: depends on font size
        # - Orientation: depends on orientation
        # - Overlap: depends on tick labels (and therefore format and tick
        #   values), font size, orientation, and axis orientation

        # tick values
        values = self.values()
        # minimum font size
        fs_min = font_sizes[0]
        # target font size
        fs_t = font_sizes[-1]

        # optimization
        self.opt_legibility = float('-inf')
        # format
        for f in range(2):
            # legibility score for format
            if f == 0:                      # format 'Decimal'
                vls = [(1e-4 < abs(v) < 1e6) * 1 for v in values]
                leg_f = sum(vls) / len(vls)
            else:                           # format 'Factored Scientific'
                leg_f = 0.3

            # tick labels
            labels, _ = self.labels(format=f)
            # widths and heights of tick labels, in units of font size
            widths = [self._label_width(l, font_metrics) for l in labels]
            heights = [self._label_height(l, font_metrics) for l in labels]

            # font size
            for fs in font_sizes:
                # legibility score for font size
                if fs == fs_t:
                    leg_fs = 1
                else:
                    leg_fs = 0.2 * (fs - fs_min + 1) / (fs_t - fs_min)
                
                # distance between ticks, in units of font size
                step = (
                    float(self.q) * self.j * 10 ** self.z   # numerical
                    / (self.amax - self.amin)               # relative to axis
                    * length                                # physical, in cm
                    /
                    (fs / 72.27 * 2.54)                     # font size, in cm
                    )

                # orientation
                for o in range(2):
                    # legibility score for orientation
                    if o == 0:              # horizontal orientation
                        leg_or = 1
                    else:                   # vertical orientation
                        leg_or = -0.5

                    # legibility score for overlap
                    # extents of labels along the axis, in units of font size
                    if (o == 0) == horizontal:
                        # label and axis have the same orientation
                        extents = widths
                    else:
                        # label and axis have different orientations
                        extents = heights
                    # minimum distance between neighboring labels
                    # We can apply the minimum here, since overlap legibility
                    # is an increasing function of distance.
                    dist = min(step - (extents[i] + extents[i + 1]) / 2
                               for i in range(len(extents) - 1))
                    # score; we interpret em as font size
                    if dist >= 1.5:
                        leg_ov = 1
                    elif dist > 0:
                        leg_ov = 2 - 1.5 / dist
                    else:
                        leg_ov = float('-inf')
                    
                    # total legibility score
                    leg = (leg_f + leg_fs + leg_or + leg_ov) / 4

                    # aggregate
                    if leg > self.opt_legibility:
                        self.opt_legibility = leg
                        self._format = f
                        self.font_size = fs
                        self.horizontal = (o == 0)

    def _label_width(self, label, font_metrics):
        w = sum(map(font_metrics.get, label)) + font_metrics['offset']
        return w

    def _label_height(self, label, font_metrics):
        h = font_metrics['height']
        return h

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

    def labels(self, format=None):
        "get tick labels"
        if format is None:
            format = self._format
        if format == 0:     # format 'Decimal'
            return self._labels_Decimal(), None
        elif format == 1:   # format 'Factored Scientific'
            return self._labels_Scientific()
        raise ValueError(f'unknown format {format}')

    def _labels_Decimal(self):
        "get tick labels in 'Decimal' format"
        # get values
        dvs = self._decimal()
        # create labels
        if self.normalize:
            labels = ['{:f}'.format(dv.normalize()) for dv in dvs]
        else:
            labels = ['{:f}'.format(dv) for dv in dvs]
        return labels

    def _labels_Scientific(self):
        "get tick labels in 'Scientific format'"
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
