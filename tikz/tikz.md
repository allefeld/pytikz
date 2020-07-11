# Module `tikz`

This module provides a way to create, compile, view, and save graphics based on the LaTeX package [TikZ & PGF](https://ctan.org/pkg/pgf). It makes the creation of TikZ graphics easier when (part of) the underlying data is computed, and makes the preview and debugging of graphics within a Jupyter notebook seamless.

This documentation explains only how to access TikZ' functionality from Python. To understand it, the [TikZ & PGF manual](https://pgf-tikz.github.io/pgf/pgfmanual.pdf) needs to be consulted in parallel. A [notebook](https://nbviewer.jupyter.org/github/allefeld/pytikz/blob/master/pytikz.ipynb) contains examples to get you started.


## Function

The module exposes the basic graphics functionality of TikZ, as described in [Part III](https://pgf-tikz.github.io/pgf/pgfmanual.pdf#part.3) of the manual, except for some specialized functions with complex syntax (pics, graphs, matrices, trees).

At its center is the class `Picture`. It primarily represents a [<code>tikzpicture</code> environment](https://pgf-tikz.github.io/pgf/pgfmanual.pdf#subsubsection.12.2.1), but also provides methods to create a complete LaTeX document and compile it in the background. Methods of the class serve mainly to insert TikZ commands into this environment, but also allow to load necessary TikZ libraries and LaTeX packages.

LaTeX documents created by this package always contain a single `tikzpicture` environment, and the document is compiled in such a way that a PDF containing only that picture's bounding box is created. The picture can be directly displayed in a notebook, saved as a PDF, converted to PNG or SVG, and the resulting image file used in another application or again in LaTeX. It is also possible to show the TikZ code corresponding to the picture and copy & paste it into a LaTeX document of your own.


## Design

TikZ' basic design comprises

-   (sequences of) coordinates,
-   path operations,
-   path specifications created from the combination of the first two, and
-   path actions.

Path actions and other commands are grouped in [<code>scope</code> environments](https://pgf-tikz.github.io/pgf/pgfmanual.pdf#subsubsection.12.3.1). In addition, there are options which can be attached to a path action, path operation, or environment but can also be embedded in a path specification. In the following it is explained how these TikZ stuctures are mapped to Python in this module.

![](design.svg){width=100%}

Coordinate

:   A [coordinate](https://pgf-tikz.github.io/pgf/pgfmanual.pdf#subsection.13.2) can be specified as a `tuple` or a NumPy 1d-`ndarray` with 2 or 3 elements, or as a string.

    Elements of `tuple`s can be numbers or strings. If all elements are numeric, it specifies coordinates in TikZ' `xyz` coordinate system. If all are strings (normally a number plus a unit like `'2pt'`) it specifies coordinates in TikZ' `canvas` coordinate system. Otherwise it specifies a [mixed](https://pgf-tikz.github.io/pgf/pgfmanual.pdf#subsubsection.13.2.1) `xyz`/`canvas` coordinate.

    `ndarray`s must be numeric and represent coordinates in TikZ' `xyz` coordinate system.
   
    Strings can be used to specify coordinates in TikZ' other coordinate systems, e.g. `polar`, `perpendicular`, and <code>node</code>. Coordinate-specifying strings are enclosed in parentheses `()`, possibly prefixed by `+` or `++` (relative / incremental coordinates). A special case is the coordinate `'cycle'`, which can be created by the function `cycle`.

    If an argument is intended to be a coordinate, it is normally named `coord`.

Sequence of coordinates

:   A sequence of coordinates is specified as a `list` of coordinates as described above, or as a numeric 2d-`ndarray` with 2 or 3 columns, representing `xyz` coordinates.

    If an argument is expected to be a sequence of coordinates, it is normally named `coords`. Often, a single coordinate can be given in place of a sequence.

Path operation

:   A path operation is specified as an object of a subclass of `Operation`. The subclass names are lowercase, because in practical use these classes act similar to functions, i.e. they are only instantiated, not manipulated.
   
    A path operation is normally not used as a single argument, but as part of a path specification. Some path operations accept options.

Path specification

:   A [path specification](https://pgf-tikz.github.io/pgf/pgfmanual.pdf#section.14) is specified as a sequence of path operations and  (sequences of) coordinates (shorthand for `moveto` operations). It can also include options and strings.

    A path specification is normally passed as a sequence of arguments named `**spec` to a path action method.

Path action

:   A [path action](https://pgf-tikz.github.io/pgf/pgfmanual.pdf#section.15) is specified as a method of `Picture` and other environments. Several method calls in sequence create a sequence of path actions.

    A path action method typically accepts a path specification as well as options as arguments.

Scope

:   A scope environment can be added to a `Picture` or another environment using the method [environment<code>.add_scope()</code>](#tikz.Scope.addscope). This creates a `Scope` object, adds it to the environment and returns it. To add path actions and other commands to the environment, call the methods on the returned object.


Option

:   An option is specified as a keyword argument (`**kwoptions`) and/or as a string (`opt`); the string is included as-is in the TikZ-formatted option string. TikZ keys that contain spaces are specified with an underscore `_` in their place. TikZ keys that do not take a value are specified with the value `True`. Keys with the value `None` are not passed to TikZ.

    For embedding options within a path specification, the function `options` can be used.

    Classes, methods or functions that accept options contain opt=None, **kwoptions in their signature.


## Color

TikZ automatically loads the [LaTeX package <code>xcolor</code>](https://mirrors.nxthost.com/ctan/macros/latex/contrib/xcolor/xcolor.pdf), which means that a large number of [named colors](https://mirrors.nxthost.com/ctan/macros/latex/contrib/xcolor/xcolor.pdf#section.4) can be used within pictures. The package also allows to define new colors based on a variety of color models as well as through mixture of known colors, exposed through the
[environment<code>.definecolor()</code>](#tikz.Scope.definecolor) and
[environment<code>.colorlet()</code>](#tikz.Scope.colorlet)
methods of `Picture` and other environments.


***
