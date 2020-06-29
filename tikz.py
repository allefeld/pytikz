"tikz, a Python interface to TikZ"

import subprocess
from inspect import cleandoc
from tempfile import mkdtemp
from shutil import copyfile, rmtree
from atexit import register
from os.path import sep, isfile, splitext
from os import rename
from hashlib import sha1
import fitz
from IPython.display import HTML
from html import escape
import base64


class cfg:
    "configuration variables"

    display_dpi = 96    # standard monitor dpi
    file_dpi = 300


# units in cm
inch = 2.54
pt = inch / 72.27
bp = inch / 72
mm = 0.1


def _point(point):
    "point (or something else)"
    if isinstance(point, str):
        return point
    else:
        return '(' + ','.join(map(str, point)) + ')'


def _points(points):
    "helper function for draw and friends"
    return ' '.join([_point(p) for p in points])


# path operations


def line(points, op='--'):
    "sequence of points with line operation"
    return f' {op} '.join([_point(p) for p in points])


def controls(point1, point2):
    "control points line operation"
    return '.. controls ' + _point(point1) + ' and ' + _point(point2) + ' ..'


def _option(key, val):
    if val is True:
        return str(key)
    else:
        key = str(key).replace('_', ' ')
        return f'{key}={str(val)}'


def _options(options=None, **kwoptions):
    "helper function to format options in various functions"
    o = [_option(key, val) for key, val in kwoptions.items()]
    if options is not None:
        o.insert(0, options)
    code = '[' + ','.join(o) + ']'
    if code == '[]':
        code = ''
    return code


def circle(options=None, **kwoptions):
    "circle"
    code = 'circle' + _options(options=options, **kwoptions)
    return code


def arc(options=None, **kwoptions):
    "arc"
    code = 'arc' + _options(options=options, **kwoptions)
    return code


def rectangle(options=None, **kwoptions):
    "rectangle"
    code = 'rectangle' + _options(options=options, **kwoptions)
    return code


def grid(options=None, **kwoptions):
    "grid"
    code = 'grid' + _options(options=options, **kwoptions)
    return code


def parabola(bend=None, options=None, **kwoptions):
    "parabola"
    code = 'parabola' + _options(options=options, **kwoptions)
    if bend is not None:
        code += ' bend ' + _point(bend)
    return code


def sin(options=None, **kwoptions):
    "sin"
    code = 'sin' + _options(options=options, **kwoptions)
    return code


def cos(options=None, **kwoptions):
    "cos"
    code = 'cos' + _options(options=options, **kwoptions)
    return code


# environments


class Scope:
    "representation of `scope` environment"

    def __init__(self, options=None, **kwoptions):
        self.elements = []
        self.options = _options(options=options, **kwoptions)

    def add(self, el):
        "add element (may be string)"
        self.elements.append(el)

    def scope(self):
        "scope environment"
        s = Scope()
        self.add(s)
        return s

    def __str__(self):
        "create LaTeX code"
        code = r'\begin{scope}' + self.options + '\n'
        code += '\n'.join(map(str, self.elements)) + '\n'
        code += r'\end{scope}'
        return code

    # commands

    def path(self, *spec, options=None, **kwoptions):
        "path command"
        self.add(r'\path'
                 + _options(options=options, **kwoptions) + ' '
                 + _points(spec) + ';')

    def draw(self, *spec, options=None, **kwoptions):
        "draw command"
        self.add(r'\draw'
                 + _options(options=options, **kwoptions) + ' '
                 + _points(spec) + ';')

    def fill(self, *spec, options=None, **kwoptions):
        "fill command"
        self.add(r'\fill'
                 + _options(options=options, **kwoptions) + ' '
                 + _points(spec) + ';')

    def filldraw(self, *spec, options=None, **kwoptions):
        "filldraw command"
        self.add(r'\filldraw'
                 + _options(options=options, **kwoptions) + ' '
                 + _points(spec) + ';')

    def clip(self, *spec, options=None, **kwoptions):
        "clip command"
        self.add(r'\clip'
                 + _options(options=options, **kwoptions) + ' '
                 + _points(spec) + ';')


class Picture(Scope):
    "representation of `tikzpicture` environment"

    def __init__(self, options=None, **kwoptions):
        super().__init__(options=options, **kwoptions)
        # create temporary directory for pdflatex etc.
        self.tempdir = mkdtemp(prefix='tikz-')
        # make sure it gets deleted
        register(rmtree, self.tempdir, ignore_errors=True)

    def __str__(self):
        "create LaTeX code"
        # We use `str` to create the LaTeX code so that we can directly include
        # strings in `self.elements`, for which `str()` is idempotent.
        code = r'\begin{tikzpicture}' + self.options + '\n'
        code += '\n'.join(map(str, self.elements)) + '\n'
        code += r'\end{tikzpicture}'
        return code

    def _create_pdf(self):
        "ensure that an up-to-date PDF file exists"

        # We don't want a PDF file of the whole LaTeX document, but only of the
        # contents of the `tikzpicture` environment. This is achieved using
        # TikZ' `external` library, which makes TikZ write out pictures as
        # individual PDF files. To do so, in a normal pdflatex run TikZ calls
        # pdflatex again with special arguments. We use these special
        # arguments directly. See section 53 of the PGF/TikZ manual.

        # create LaTeX code
        code = (cleandoc(r"""
                    \documentclass{article}
                    \usepackage{tikz}
                    \usetikzlibrary{external}
                    \tikzexternalize
                    \begin{document}
                    """) + '\n'
                + str(self) + '\n'
                + r'\end{document}' + '\n')
        # print(code)

        # does the PDF file have to be created?
        #  This check is implemented by using the SHA1 digest of the LaTeX code
        # in the PDF filename, and to skip creation if that file exists.
        hash = sha1(code.encode()).hexdigest()
        self.temp_pdf = self.tempdir + sep + 'tikz-' + hash + '.pdf'
        if isfile(self.temp_pdf):
            return

        # create LaTeX file
        temp_tex = self.tempdir + sep + 'tikz.tex'
        with open(temp_tex, 'w') as f:
            f.write(code)

        # process LaTeX file into PDF
        completed = subprocess.run(
            ['pdflatex',
                '-jobname',
                'tikz-figure0',
                r'\def\tikzexternalrealjob{tikz}\input{tikz}'],
            cwd=self.tempdir,
            capture_output=True,
            text=True)
        if completed.returncode != 0:
            raise LatexException('pdflatex has failed\n' + completed.stdout)

        # rename created PDF file
        rename(self.tempdir + sep + 'tikz-figure0.pdf', self.temp_pdf)

    def write_image(self, filename, dpi=None):
        "write picture to image file (PDF, PNG, or SVG)"
        if dpi is None:
            dpi = cfg.file_dpi
        self._create_pdf()
        # determine extension
        _, ext = splitext(filename)
        # if a PDF is requested,
        if ext.lower() == '.pdf':
            # just copy the file
            copyfile(self.temp_pdf, filename)
        elif ext.lower() == '.png':
            # render PDF as PNG using PyMuPDF
            zoom = dpi / 72
            doc = fitz.open(self.temp_pdf)
            page = doc.loadPage(0)
            pix = page.getPixmap(matrix=fitz.Matrix(zoom, zoom), alpha=True)
            pix.writePNG(filename)
        elif ext.lower() == '.svg':
            # convert PDF to SVG using PyMuPDF
            doc = fitz.open(self.temp_pdf)
            page = doc.loadPage(0)
            svg = page.getSVGimage()
            with open(filename, 'w') as f:
                f.write(svg)
        else:
            print(f'format {ext[1:]} is not supported')

    def _repr_png_(self):
        "represent of picture as PNG for notebook"
        self._create_pdf()
        # render PDF as PNG using PyMuPDF
        zoom = cfg.display_dpi / 72
        doc = fitz.open(self.temp_pdf)
        page = doc.loadPage(0)
        pix = page.getPixmap(matrix=fitz.Matrix(zoom, zoom))
        return pix.getPNGdata()


class LatexException(Exception):
    pass


def demo(pic):
    "convenience function to test & debug picture"
    png_base64 = ''
    try:
        png_base64 = base64.b64encode(pic._repr_png_()).decode('ascii')
    except LatexException as le:
        message = le.args[0]
        tikz_error = message.find('! Package tikz Error:')
        if tikz_error != -1:
            message = message[tikz_error:]
        print(message)
    code_escaped = escape(str(pic))
    return HTML(demo_template.format(png_base64, code_escaped))


demo_template = '''
<div style="background-color:#e0e0e0;margin:0">
  <div>
    <img style="max-width:47%;padding:10px;float:left"
      src="data:image/png;base64,{}">
    <pre
        style="width:47%;margin:0;padding:10px;float:right;white-space:pre-wrap"
        >{}</pre>
  </div>
  <div style="clear:both"></div>
</div>
'''
