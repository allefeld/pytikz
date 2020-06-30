"tikz, a Python interface to TikZ"

import subprocess
import tempfile
import shutil
import atexit
import os.path
import os
import hashlib
import fitz
import IPython.display
import html
import base64


class cfg:
    "configuration variables"

    display_dpi = 96    # standard monitor dpi
    file_dpi = 300

    # executable name, possibly including path
    # pdflatex is fastest, lualatex + 50%, xelatex + 100%
    latex = 'pdflatex'

    # {0} is replaced by a Base64-encoded PNG image,
    # {1} by TikZ-LaTeX code
    demo_template = '\n'.join([
        '<div style="background-color:#e0e0e0;margin:0">',
        '  <div>',
        '    <img style="max-width:47%;padding:10px;float:left"',
        '      src="data:image/png;base64,{0}">',
        '    <pre',
        '        style="width:47%;margin:0;padding:10px;float:right;'
        + 'white-space:pre-wrap"',
        '        >{1}</pre>',
        '  </div>',
        '  <div style="clear:both"></div>',
        '</div>'])


# units in cm
inch = 2.54
pt = inch / 72.27
bp = inch / 72
mm = 0.1


def _option(key, val):
    "helper function for _options"
    key = str(key).replace('_', ' ')
    if val is True:
        return key
    else:
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


# coordinates

def _point(point):
    """
    helper function for _points and others
    (Cartesian) coordinates or freeform string, incl. node
    """
    if isinstance(point, str):
        return point
    else:
        return '(' + ','.join(map(str, point)) + ')'


def polar(angle, radius, y_radius=None):
    "polar coordinates"
    code = '(' + str(angle) + ':' + str(radius)
    if y_radius is not None:
        code += ' and ' + str(y_radius)
    code += ')'
    return code


def vertical(point1, point2):
    "perpendicular coordinates, vertical"
    coord = _point(point1)
    if coord.startswith('(') and coord.endswith(')'):
        coord = coord[1:-1]
    code = '(' + coord + ' |- '
    coord = _point(point2)
    if coord.startswith('(') and coord.endswith(')'):
        coord = coord[1:-1]
    code += coord + ')'
    return code


# sequences

# TODO: Change such that TikZ' logic is preserved:
# (Almost) all path operations take an "end coordinate" as an argument.
#
# → For operations where simple repetition makes sense, accept a sequence of
# coordinates.
#   pic.draw(line([(-1.5, 0), (1.5, 0)]))
# becomes
#   pic.draw((-1.5, 0), lineto((1.5, 0)))
# and
#   '-- cycle'
# becomes
#   lineto('cycle')
#
# Trickiness: distinguish between iterable argument which specifies a sequence
# of coordinate values, or a sequence of coordinates (points). Check whether
# first element is an iterable itself (other than a string).
#
# `point` can be a string or an iterable with at most 3 elements.
# `points` is an arbitrary-length sequence of points, i.e. also an iterable.


def _points(points):
    """
    helper function for draw and friends
    sequence of points with move-to operation between
    """
    return ' '.join([_point(p) for p in points])


def line(points, op='--'):
    """
    sequence of points with line-to operation between
    op can be '--' for straight lines (default)
    '-|' for first horizontal, then vertical
    '|-' for first vertical, then horizontal
    """
    return f' {op} '.join([_point(p) for p in points])


# path operations


def controls(point1, point2):
    "curve-to operation"
    return '.. controls ' + _point(point1) + ' and ' + _point(point2) + ' ..'


def rectangle(options=None, **kwoptions):
    "rectangle operation"
    code = 'rectangle' + _options(options=options, **kwoptions)
    return code


def circle(options=None, **kwoptions):
    "circle operation (also for ellipses)"
    code = 'circle' + _options(options=options, **kwoptions)
    return code


def arc(options=None, **kwoptions):
    "arc operation"
    code = 'arc' + _options(options=options, **kwoptions)
    return code


def grid(options=None, **kwoptions):
    "grid operation"
    code = 'grid' + _options(options=options, **kwoptions)
    return code


def parabola(bend=None, options=None, **kwoptions):
    "parabola operation"
    code = 'parabola' + _options(options=options, **kwoptions)
    if bend is not None:
        code += ' bend ' + _point(bend)
    return code


def sin(options=None, **kwoptions):
    "sine operation"
    code = 'sin' + _options(options=options, **kwoptions)
    return code


def cos(options=None, **kwoptions):
    "cosine operation"
    code = 'cos' + _options(options=options, **kwoptions)
    return code

# more operations to follow


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

    def shade(self, *spec, options=None, **kwoptions):
        "shade command"
        self.add(r'\shade'
                 + _options(options=options, **kwoptions) + ' '
                 + _points(spec) + ';')

    def shadedraw(self, *spec, options=None, **kwoptions):
        "shadedraw command"
        self.add(r'\shadedraw'
                 + _options(options=options, **kwoptions) + ' '
                 + _points(spec) + ';')

    # more commands to follow


class Picture(Scope):
    "representation of `tikzpicture` environment"

    def __init__(self, options=None, **kwoptions):
        super().__init__(options=options, **kwoptions)
        # additional preamble entries
        self.preamble = []
        # create temporary directory for pdflatex etc.
        self.tempdir = tempfile.mkdtemp(prefix='tikz-')
        # make sure it gets deleted
        atexit.register(shutil.rmtree, self.tempdir, ignore_errors=True)

    def usetikzlibrary(self, library):
        "usetikzlibrary"
        self.preamble.append(r'\usetikzlibrary{' + library + '}')

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

        sep = os.path.sep

        # We don't want a PDF file of the whole LaTeX document, but only of the
        # contents of the `tikzpicture` environment. This is achieved using
        # TikZ' `external` library, which makes TikZ write out pictures as
        # individual PDF files. To do so, in a normal pdflatex run TikZ calls
        # pdflatex again with special arguments. We use these special
        # arguments directly. See section 53 of the PGF/TikZ manual.

        # create LaTeX code
        code = (
            '\n'.join([
                r'\documentclass{article}',
                r'\usepackage{tikz}',
                r'\usetikzlibrary{external}',
                r'\tikzexternalize'])
            + '\n'.join(self.preamble) + '\n'
            + r'\begin{document}' + '\n'
            + str(self) + '\n'
            + r'\end{document}' + '\n')
        # print(code)

        # does the PDF file have to be created?
        #  This check is implemented by using the SHA1 digest of the LaTeX code
        # in the PDF filename, and to skip creation if that file exists.
        hash = hashlib.sha1(code.encode()).hexdigest()
        self.temp_pdf = self.tempdir + sep + 'tikz-' + hash + '.pdf'
        if os.path.isfile(self.temp_pdf):
            return

        # create LaTeX file
        temp_tex = self.tempdir + sep + 'tikz.tex'
        with open(temp_tex, 'w') as f:
            f.write(code)

        # process LaTeX file into PDF
        completed = subprocess.run(
            [cfg.latex,
             '-jobname',
             'tikz-figure0',
             r'\def\tikzexternalrealjob{tikz}\input{tikz}'],
            cwd=self.tempdir,
            capture_output=True,
            text=True)
        if completed.returncode != 0:
            raise LatexException('pdflatex has failed\n' + completed.stdout)

        # rename created PDF file
        os.rename(self.tempdir + sep + 'tikz-figure0.pdf', self.temp_pdf)

    def write_image(self, filename, dpi=None):
        "write picture to image file (PDF, PNG, or SVG)"
        if dpi is None:
            dpi = cfg.file_dpi
        self._create_pdf()
        # determine extension
        _, ext = os.path.splitext(filename)
        # if a PDF is requested,
        if ext.lower() == '.pdf':
            # just copy the file
            shutil.copyfile(self.temp_pdf, filename)
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

    def demo(self):
        "convenience function to test & debug picture"
        png_base64 = ''
        try:
            png_base64 = base64.b64encode(self._repr_png_()).decode('ascii')
        except LatexException as le:
            message = le.args[0]
            tikz_error = message.find('! ')
            if tikz_error != -1:
                message = message[tikz_error:]
            print(message)
        code_escaped = html.escape(str(self))
        IPython.display.display(IPython.display.HTML(
            cfg.demo_template.format(png_base64, code_escaped)))


class LatexException(Exception):
    "problem with external LaTeX process"
    pass


# create pytikz logo
if __name__ == "__main__":
    pic = Picture()
    pic.add(r'\draw[darkgray] (0,0) node[scale=2] {\textsf{py}Ti\emph{k}Z};')
    pic.write_image('pytikz.png')
