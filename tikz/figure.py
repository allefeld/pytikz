"""
specific parameters:
-   width
-   rows/columns for each view
-   aspect ratio for each view

implicit:
-   numbers of rows and columns
-   numbers of rows and columns

generic parameters:
-   horizontal margin, vertical margin
-   horizontal gap, vertical gap
-   left padding, right padding
-   below padding, above padding

results:
-   column widths
-   row heights
-   ...

all lengths in cm, or whatever the `xy` coordinate system has been set to
"""

# Copyright (C) 2020 Carsten Allefeld

import numpy as np
import collections
from tikz import Picture, rectangle, options


class cfg:
    "tikz.figure configuration variables"

    width = 16
    "width of figure, default 16"
    margin_horizontal = 0.5
    "horizontal margin of figure, default 0.5"
    margin_vertical = 0.5
    "vertical margin of figure, default 0.5"
    gap_horizontal = 0.5
    "horizontal gap between views, default 0.5"
    gap_vertical = 0.5
    "vertical gap between views, default 0.5"
    padding_left = 1
    "left view padding, default 1"
    padding_right = 0.5
    "right view padding, default 1"
    padding_bottom = 1
    "bottom view padding, default 1"
    padding_top = 0.5
    "top view padding, default 0.5"


class Box:
    def __init__(self, x, y, w, h):
        self.x = x
        self.y = y
        self.w = w
        self.h = h

    def _draw(self, env, label=None, opt=None, **kwoptions):
        "draw Box into environment"
        env.draw((self.x, self.y),
                 rectangle((self.x + self.w, self.y + self.h)),
                 opt=opt, **kwoptions)
        if label is not None:
            env.node(label, at=(self.x, self.y + self.h),
                     anchor='north west', font=r'\tiny')


class View:
    def __init__(self, outer=None, inner=None):
        self.outer = outer
        self.inner = inner

    def locate(self, outer, inner):
        self.outer = outer
        self.inner = inner

    def _draw(self, env, label=None):
        "draw View into environment"
        self.outer._draw(env, label, opacity=0.5)
        self.inner._draw(env)


class Layout:
    """
    superclass for layout classes

    Every subclass has to ensure that
    - there is a member `views` that contains a list of `View` objects,
    - there are members `width` and `height` which specify the dimensions,
    - if computations are necessary to ensure these members are up-to-date,
      they are implemented in a method overriding `_compute`.
    """
    def _compute(self):
        pass

    def get_views(self):
        self._compute()
        return self.views

    def get_dimensions(self):
        self._compute()
        return self.width, self.height

    def _draw(self, env):
        "draw Layout into environment"
        env.draw((0, 0), rectangle((self.width, self.height)))
        env.node('Layout', at=(0, self.height),
                 anchor='north west', font=r'\tiny')
        for i in range(len(self.views)):
            self.views[i]._draw(env, f'View {i}')

    def _repr_png_(self, dpi=None):
        "represent Layout as PNG for notebook"
        self._compute()
        pic = Picture()
        self._draw(pic)
        return pic.get_PNG(dpi=dpi)


class SimpleLayout(Layout):
    "layout with a single view"
    def __init__(self, **parameters):
        # process Layout parameters and get defaults
        self.width = parameters.get('width', cfg.width)
        mh = parameters.get('margin_horizontal', parameters.get(
            'margin', cfg.margin_horizontal))
        mv = parameters.get('margin_vertical', parameters.get(
            'margin', cfg.margin_vertical))
        pl = parameters.get('padding_left', cfg.padding_left)
        pr = parameters.get('padding_right', cfg.padding_right)
        pb = parameters.get('padding_bottom', cfg.padding_bottom)
        pt = parameters.get('padding_top', cfg.padding_top)
        ar = parameters.get('aspect_ratio', 4/3)
        # compute
        iw = self.width - 2 * mh - pl - pr
        ih = iw / ar
        ow = iw + pl + pr
        oh = ih + pb + pt
        ox = mh
        oy = mv
        ix = ox + pl
        iy = oy + pb
        self.height = oh + 2 * mv
        # create boxes and view
        outer = Box(ox, oy, ow, oh)
        inner = Box(ix, iy, iw, ih)
        self.views = [View(outer, inner)]


class FlexibleGridLayout(Layout):
    "layout where views encompass one or more of the cells of a flexible grid"
    def __init__(self, **parameters):
        # process Layout parameters and get defaults
        self.width = parameters.get('width', cfg.width)
        self.mh = parameters.get('margin_horizontal', parameters.get(
            'margin', cfg.margin_horizontal))
        self.mv = parameters.get('margin_vertical', parameters.get(
            'margin', cfg.margin_vertical))
        self.gh = parameters.get('gap_horizontal', parameters.get(
            'gap', cfg.gap_horizontal))
        self.gv = parameters.get('gap_vertical', parameters.get(
            'gap', cfg.gap_vertical))
        self.pl = parameters.get('padding_left', cfg.padding_left)
        self.pr = parameters.get('padding_right', cfg.padding_right)
        self.pb = parameters.get('padding_bottom', cfg.padding_bottom)
        self.pt = parameters.get('padding_top', cfg.padding_top)
        # initialize list of Views and view parameters
        self.views = []
        self.rf = []    # rows from
        self.rt = []    # rows to
        self.cf = []    # columns from
        self.ct = []    # columns to
        self.ar = []    # aspect ratio

    def add_view(self, rows, cols, aspect_ratio=None):
        # support specification of single row/col as scalar
        if not isinstance(rows, collections.abc.Iterable):
            rows = [rows]
        if not isinstance(cols, collections.abc.Iterable):
            cols = [cols]
        # store extent w.r.t. grid & aspect ratio
        self.rf.append(min(rows))
        self.rt.append(max(rows))
        self.cf.append(min(cols))
        self.ct.append(max(cols))
        self.ar.append(aspect_ratio)
        # create & store empty View object
        v = View()
        self.views.append(v)

    def _compute(self):
        # What we have to compute are the outer and inner box of each view. To
        # do so, we need to know the height of each row and the width of each
        # column. The constraints that allow to compute these unknowns u are
        # linear, which means they can be expressed by a matrix equation,
        # A u = b. The rows of u / columns of A correspond to first the the
        # row heights and then the column widths, and the rows of A / rows of
        # b correspond to the constraints.

        # compute number of rows/cols from maximal view row/col index
        nr = max(self.rt) + 1
        nc = max(self.ct) + 1

        # constraints: one global, and one per view
        n = 1 + len(self.views)
        A = np.zeros(shape=(n, nr + nc))
        b = np.zeros(shape=(n, 1))
        # global constraint
        # The column widths, margins and gaps have to add up to the width.
        A[0, :] = np.hstack((np.zeros(nr), np.ones(nc)))
        b[0] = self.width - 2 * self.mh - (nc - 1) * self.gh
        # per-view constraints
        for i in range(len(self.views)):
            # unpack for shorter code
            rf = self.rf[i]
            rt = self.rt[i]
            cf = self.cf[i]
            ct = self.ct[i]
            ar = self.ar[i]
            # ignore views with unspecified aspect ratio
            if ar is None:
                continue
            # row heights included in view
            h = np.zeros(nr)
            h[rf: rt + 1] = 1
            nvr = sum(h)
            # column widths included in view
            w = np.zeros(nc)
            w[cf: ct + 1] = 1
            nvc = sum(w)
            # constraint
            A[i + 1, :] = np.hstack((-ar * h, w))
            b[i + 1] = ((self.pl + self.pr - (nvc - 1) * self.gh)
                        - ar * (self.pt + self.pb - (nvr - 1) * self.gv))

        # check constraints
        rank = np.linalg.matrix_rank(A)
        if rank < nr + nc:
            print('Warning: The Layout is underdetermined.')

        # solve expression
        u = np.linalg.pinv(A) @ b

        # extract row heights and column widths
        rh = list(u[:nr].flat)
        cw = list(u[nr:].flat)

        # height of figure
        self.height = sum(rh) + 2 * self.mh + (nr - 1) * self.gv

        # check fulfillment of global constraint
        # Tolerance: We choose TeX's internal unit, the scaled point "sp", see
        # The TeXbook, p. 57.
        tol = 2.54 / 72.27 / 65536
        actual_width = sum(cw) + 2 * self.mh + (nc - 1) * self.gh
        if abs(actual_width - self.width) > tol:
            print(f'Warning: Layout width is {actual_width}.')

        # compute position of view boxes
        for i in range(len(self.views)):
            # unpack for shorter code
            rf = self.rf[i]
            rt = self.rt[i]
            cf = self.cf[i]
            ct = self.ct[i]
            ar = self.ar[i]
            # outer box
            ox = self.mh + sum(cw[:cf]) + cf * self.gh
            oy = self.mv + sum(rh[:rf]) + rf * self.gv
            ow = sum(cw[cf: ct + 1]) + (ct - cf) * self.gh
            oh = sum(rh[rf: rt + 1]) + (rt - rf) * self.gv
            oy = self.height - oy - oh
            outer = Box(ox, oy, ow, oh)
            # inner box
            ix = ox + self.pl
            iy = oy + self.pb
            iw = ow - self.pl - self.pr
            ih = oh - self.pt - self.pb
            inner = Box(ix, iy, iw, ih)
            # assign Boxes to View
            self.views[i].locate(outer, inner)

            # check fulfillment of per-view constraint
            if ar is None:
                continue
            if abs(iw - ar * ih) > tol:
                print(f'Warning: View {i} aspect ratio is {iw / ih}.')


class Figure(Picture):
    def __init__(self, layout=None, opt=None, **kwoptions):
        super().__init__(opt=opt, **kwoptions)
        if layout is None:
            layout = SimpleLayout()
        self.layout = layout
        # ensure minimum bounding box of figure
        self.width, self.height = layout.get_dimensions()
        self.path((0, 0), (self.width, self.height))
        # use font Fira
        self.fira()
        # TODO: create `TicksGenerator`, with Fira metrics

    def draw_layout(self):
        "draw layout"
        scope = self.add_scope(color='red')
        self.layout._draw(scope)

    def title(self, label, margin_vertical=None):
        # TODO: use another parameter name, and corresponding cfg?
        if margin_vertical is None:
            margin_vertical = cfg.margin_vertical
        scope = self.add_scope()
        # position title such that descenders touch Layout
        scope.node(label, at=(self.width / 2, self.height),
                   anchor='base', yshift='depth("gjpqy")', name='title',
                   outer_sep=0, inner_sep=0)
        # extend bounding box such that there is space above capital letters
        # and ascenders
        scope.path('(title.base)', options(yshift='height("HAbdfhk")'),
                   f'+(0,{margin_vertical})')
        # Alternatively, one could set the height and depth of the node,
        # see https://pgf-tikz.github.io/pgf/pgfmanual.pdf#subsubsection.17.4.4
        # Also, predefine this height and depth for ease of use? – No, because
        # it depends on the font size. But maybe define macros.
