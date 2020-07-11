# To Do

- test Google docstrings

- split notebook into several, move to subdir

- release / PyPI upload?

- entry on homepage


# Idea for TikZ figure

- `Figure` is a subclass of `Picture` and replaces it in use

- `Figure` *has* a `Layout`.

-   The `Layout` starts with defaults for padding upon creation. Every time the figure is rendered, it extracts adjusted padding values and recomputes. If the layout changed, it renders again.


# Idea for a more complete solution to document a Python package:

- The distribution package name is determined as the name of the current directory.

- The package documentation is generated from `/<distribution>.md`, or if that does not exist, from `/README.md`.

- The import package name is assumed to be identical to the distribution package name; if no directory of that name exists, the import package name has to be specified.

- The directory `\<import>` and its subdirectories are searched for `.py` files; each is processed as a module by `pdoc3`. If parallel to the `.py` file an `.md` file exists with the same name, the module docstring is replaced by the contents of the file.

- The output is written to the directory `docs`.

Repurpose `pdoc3`s index page, which is only served but not written.