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


This package provides a way to create, compile, view, and save graphics based on the LaTeX package `TikZ & PGF <https://ctan.org/pkg/pgf>`_. It makes
the creation of TikZ graphics easier when (part of) the underlying data is computed, and makes the preview and debugging of graphics within a Jupyter
notebook seamless.

This documentation explains only how to access TikZ' functionality from Python; to use it effectively, the `TikZ & PGF manual <https://pgf-tikz.github.io/pgf/pgfmanual.pdf>`_ needs to be consulted. A `notebook <https://nbviewer.jupyter.org/github/allefeld/pytikz/blob/master/pytikz.ipynb>`_ contains examples to get you started.

----

All functionality is contained in the module :py:mod:`tikz`. At its center is
the class :py:class:`tikz.Picture`.
