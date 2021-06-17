import setuptools

# constants for setup.py as well as docsource/conf.py
name = 'pytikz'
author = 'Carsten Allefeld'
version = '0.1.0'
description = 'A Python interface to TikZ'
url = 'https://github.com/allefeld/pytikz'
classifiers = [
    'Programming Language :: Python :: 3',
    'License :: OSI Approved :: '
    + 'GNU General Public License v3 or later (GPLv3+)',
    'Operating System :: OS Independent',
    ]
python_requires = '>=3.6'
install_requires = ['PyMuPDF','ipython','numpy']

if __name__ == '__main__':
    with open('README.md', 'r') as fh:
        long_description = fh.read()
    long_description_content_type = 'text/markdown'

    setuptools.setup(
        name=name,
        version=version,
        author=author,
        description=description,
        long_description=long_description,
        long_description_content_type=long_description_content_type,
        url=url,
        packages=setuptools.find_packages(),
        classifiers=classifiers,
        python_requires=python_requires,
        install_requires=install_requires,
    )
