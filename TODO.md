# to do


## package

- split notebook into several, move to subdir

- release / PyPI upload?

- entry on homepage


## tikz

- it would be nice if a click on the SVG would open the PDF in an external application (`webbrowser`, or https://stackoverflow.com/a/17317468/2056067)


## tikz.figure

- Implement 'normalization'. Keep vertical alignment e.g. by `\phantom`izing the trailing decimal point and '0's.

- If x- and y-axis have the save `dmin, dmax, alen`, just use the horizontal labeling for the vertical, too, but without rotation.

- How to enforce isoscaling? Add `only_tight` or so to `extended_wilkinson`?

- Maybe: The `Layout` starts with defaults for padding upon creation. Every time the figure is rendered, it extracts adjusted padding values and recomputes. If the layout changed, it renders again. – Or maybe no automatic spacing, but interpretable information when scale decoration boxes get crowded ("overfull by ...").

- additional Layout subclasses:
  - simple GridLayout (like Matlab's subplot)
  - function to split existing View into grid (similar to Matlab's plotmatrix)  – is that compatible with automatic spacing? Yes, parameters just need to be interpreted consistently.

- Axes should provide a method to insert another axes (an inset), based on an independent View (not bound to a Figure / managed by a Layout). Boxes of such a view should either be specified in data coordinates or in local coordinates relative to the Axes' inner Box.

- An Axes is always based on a View, but a View can used for several Axes', for example for a second y-scale.



# Idea for a more complete solution to document a Python package:

- The distribution package name is determined as the name of the current directory.

- The package documentation is generated from `/<distribution>.md`, or if that does not exist, from `/README.md`.

- The import package name is assumed to be identical to the distribution package name; if no directory of that name exists, the import package name has to be specified.

- The directory `\<import>` and its subdirectories are searched for `.py` files; each is processed as a module by `pdoc3`. If parallel to the `.py` file an `.md` file exists with the same name, the module docstring is replaced by the contents of the file.

- The output is written to the directory `docs`.

Repurpose `pdoc3`s index page, which is only served but not written.