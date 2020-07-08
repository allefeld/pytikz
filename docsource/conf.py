# Configuration file for the Sphinx documentation builder.
#
# This file only contains a selection of the most common options. For a full
# list see the documentation:
# https://www.sphinx-doc.org/en/master/usage/configuration.html

import os
import sys
import datetime

# -- Path setup --------------------------------------------------------------

# If extensions (or modules to document with autodoc) are in another directory,
# add these directories to sys.path here. If the directory is relative to the
# documentation root, use os.path.abspath to make it absolute, like shown here.
#
sys.path.insert(0, os.path.abspath('..'))


# -- Project information -----------------------------------------------------

# get information from `setup.py` or autogenerate
from setup import name, author, version, description, url          # noqa: E402

project = name
copyright = str(datetime.date.today().year) + ', ' + author

# The full version, including alpha/beta/rc tags
release = version


# -- General configuration ---------------------------------------------------

# Add any Sphinx extension module names here, as strings. They can be
# extensions coming with Sphinx (named 'sphinx.ext.*') or your custom
# ones.
extensions = [
    'sphinx.ext.napoleon',      # for Google-style docstrings
    'sphinx.ext.autodoc'        # to automatically create module documentation
]

# List of patterns, relative to source directory, that match files and
# directories to ignore when looking for source files.
# This pattern also affects html_static_path and html_extra_path.
exclude_patterns = ['_build', 'Thumbs.db', '.DS_Store']


# -- Options for HTML output -------------------------------------------------

# The theme to use for HTML and HTML Help pages.  See the documentation for
# a list of builtin themes.
#
html_theme = 'alabaster'
html_theme_options = {
    'logo': 'logo.png',
    'description': description,
    'fixed_sidebar': True,
    'github_button': True,
    'extra_nav_links': {
        'GitHub': url
    }
}
html_sidebars = {
    '**': [
        'about.html',
        'navigation.html',
        'searchbox.html'
        ]
}
html_static_path = ['_static']


# don't sort members
autodoc_member_order = 'bysource'
