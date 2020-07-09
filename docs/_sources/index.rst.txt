pytikz
======

.. Inform Sphinx about what is part of the documentation, without listing all
   the document's TOCs here. Some weird contortions are necessary to do a
   simple thing!
.. toctree::
   :maxdepth: 1
   :hidden:

   index
   tikz


This package provides a way to create, compile, view, and save graphics based on the LaTeX package `TikZ & PGF <https://ctan.org/pkg/pgf>`_. It makes the creation of TikZ graphics easier when (part of) the underlying data is computed, and makes the preview and debugging of graphics within a Jupyter
notebook seamless.

This documentation explains only how to access TikZ' functionality from Python; to understand it, the `TikZ & PGF manual <https://pgf-tikz.github.io/pgf/pgfmanual.pdf>`_ needs to be consulted in parallel. A `notebook <https://nbviewer.jupyter.org/github/allefeld/pytikz/blob/master/pytikz.ipynb>`_ contains examples to get you started.

Design of the package
---------------------

All functionality is contained in the module :py:mod:`tikz`, and at its center is the class :py:class:`tikz.Picture`. It represents a ``tikzpicture`` `environment <https://pgf-tikz.github.io/pgf/pgfmanual.pdf#subsubsection.12.2.1>`_, but also provides methods to create a complete LaTeX document and compile it in the background. Methods of the class serve mainly to insert TikZ commands into this environment, but also allow to load necessary TikZ libraries and LaTeX packages.

LaTeX documents created by this package always contain a single ``tikzpicture`` environment, and the document is compiled in such a way that a PDF containing only that picture's bounding box is created. This PDF can be displayed in a notebook, saved, converted to PNG or SVG, and the resulting image file used in another application or again in LaTeX. It is also possible to obtain the LaTeX code and copy & paste it into a LaTeX document of your own.

TikZ' basic design comprises (sequences of) coordinates, path operations, path specifications created from the combination of the first two, and path actions. Path actions and other commands are grouped in ``scope`` `environment <https://pgf-tikz.github.io/pgf/pgfmanual.pdf#subsubsection.12.3.1>`_. In addition, there are options which can be attached to a path action, path operation, or environment but can also be embedded in a path specification. In the following it is explained how these TikZ stuctures are mapped to Python in this package.

Coordinate
   A `coordinate <https://pgf-tikz.github.io/pgf/pgfmanual.pdf#subsection.13.2>`_ can be specified as a ``tuple`` or a NumPy 1d-``ndarray`` with 2 or 3 elements, or as a string.

   Elements of ``tuple``\ s can be numbers or strings. If all elements are    numeric, it represents coordinates in TikZ' ``xyz`` coordinate system. If all are strings (normally a number plus a unit like ``'2pt'``) it represents coordinates in TikZ' ``canvas`` coordinate system. Otherwise it represents a mixed ``xyz``/``canvas`` coordinate as described in §13.2.1.

   ``ndarray``\ s must be numeric and represent coordinates in TikZ' ``xyz`` coordinate system.
   
   Strings can be used to specify coordinates in TikZ' other coordinate systems, e.g. ``polar``, ``perpendicular`, and ``node``. Coordinate-specifying strings are enclosed in parentheses ``()``, possibly prefixed by ``+`` or ``++`` (relative / incremental coordinates). An special case is the coordinate ``'cycle'`` (see :py:func:`tikz.cycle`).

   If an argument is intended to be a coordinate, it is normally named ``coord``.

Sequence of coordinates
   A sequence of coordinates is specified as a ``list`` of coordinates as described above, or as a numeric 2d-``ndarray`` with 2 or 3 columns, representing ``xyz`` coordinates.

   If an argument is expected to be a sequence of coordinates, it is normally named ``coords``. Often, a single coordinate can be given in place of a sequence.

Path operation
   A path operation is specified as an object of a subclass of :py:class:`tikz.Operation`. The class names have been chosen as lowercase, because in practical use these classes act similar to functions, 
   
   It is normally not used as a single argument, but as part of a path specification. Some path operations accept options.

Path specification
   A `path specification <https://pgf-tikz.github.io/pgf/pgfmanual.pdf#section.14>`_ is specified as a sequence of path operations and  (sequences of) coordinates (shorthand for :py:class:`tikz.moveto` operations). It can also include options and :py:class:`tikz.Raw` objects.

   It is normally passed as a sequence of arguments named ``**spec`` to a path action method.

Path action
   A `path action <https://pgf-tikz.github.io/pgf/pgfmanual.pdf#section.15>`_ is specified as a method of :py:class:`tikz.Picture` and other environments.

   A path action method typically accepts a path specification as well as options as arguments.

Option
   An option is specified as a keyword argument (``**kwoptions``) or as a raw string (``opt``). TikZ keys that contain a space are specified with an underscore ``_`` instead, TikZ keys that do not take a value are specified with the value ``True``. Keys with the value ``None`` are not passed to TikZ.

   For embedding options within a path specification, the function :py:func:`tikz.options` can be used.

   Classes, methods or functions that accept options contain ``opt=None, **kwoptions`` in their signature.