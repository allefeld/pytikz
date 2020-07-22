![](docs/logo.png)


# pytikz – A Python interface to Ti*k*Z

This package provides a way to create, compile, view, and save figures based on the LaTeX package [Ti*k*Z & PGF](https://ctan.org/pkg/pgf). It makes the creation of Ti*k*Z figures easier when (part of) the underlying data is computed, and makes the preview and debugging of figures within a Jupyter notebook seamless.


## Example

Python code adapted from the Ti*k*Z documentation:

```
coords = [(0, 0), (0, 2), (1, 3.25), (2, 2), (2, 0), (0, 2), (2, 2), (0, 0), (2, 0)]
pic = Picture()
pic.draw(line(coords), thick=True, rounded_corners='4pt')
pic.write_image('nikolaus.pdf')
```

## Installation

The distribution package is called `pytikz` and can be installed from this repository:

```
pip install git+https://github.com/allefeld/pytikz.git
```

Note that the import package is called `tikz`.


## Getting started

A tutorial illustrating the use of pytikz is provided in the form of a Jupyter notebook [`pytikz.ipynb`](pytikz.ipynb). It is best viewed through [nbviewer](https://nbviewer.jupyter.org/github/allefeld/pytikz/blob/master/pytikz.ipynb).


## Documentation

[Module `tikz`](https://allefeld.github.io/pytikz/tikz).


***


This software is copyrighted © 2020 by Carsten Allefeld and released under the terms of the GNU General Public License, version 3 or later.