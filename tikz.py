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
import numbers
import numpy as np


class cfg:
    "configuration variables"

    display_dpi = 192    # standard monitor dpi × zoom 2
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


def _option_code(key, val):
    """
    helper function for _options

    Transforms single `key=value` pair into string. A value of `True` is
    omitted, an underscore in a key is transformed into a space.
    """
    key = str(key).replace('_', ' ')
    if val is True:
        return key
    else:
        return f'{key}={str(val)}'


def _options_code(opt=None, **kwoptions):
    """
    helper function to format options in various functions

    Transforms dictionary from Python dictionary / **kwargs into TikZ string,
    e.g. `(opt='red', thick=True, rounded_corners='4pt')`
    returns `'[thick,rounded corners=4pt,red]'`. Options with value `None`
    are omitted.
    """
    o = [_option_code(key, val) for key, val in kwoptions.items()
         if val is not None]
    if opt is not None:
        o.insert(0, opt)
    code = '[' + ','.join(o) + ']'
    if code == '[]':
        code = ''
    return code


# coordinates

def _point(point):
    """
    helper function for _points and others
    Enables specification of a point as a tuple, list, or np.array of numbers,
    as well as a string like '(a)' or '(3mm,0mm)'.
    """
    # Haven't found a good solution for prefixes, '+', '++'.
    if isinstance(point, str):
        return point
    else:
        return '(' + ','.join(map(str, point)) + ')'


def _str(obj): return isinstance(obj, str)


def _tuple(obj): return isinstance(obj, tuple)


def _numeric(obj): return isinstance(obj, numbers.Real)


def _str_or_numeric(obj): return _str(obj) or _numeric(obj)


def _ndarray(obj): return isinstance(obj, np.ndarray)


def _list(obj): return isinstance(obj, list)


def _coordinate(coord):
    "check and normalize coordinate"
    # A coordinate can be a string containing enclosing parentheses or the
    # string 'cycle'.
    if _str(coord) and ((coord.startswith('(') and coord.endswith(')'))
                        or coord == 'cycle'):
        return coord
    # A coordinate can be a 2/3-element tuple containing strings or numbers:
    if (_tuple(coord) and len(coord) in [2, 3]
            and all(_str_or_numeric(x) for x in coord)):
        # If all strings, normalize to string.
        if all(_str(x) for x in coord):
            return '(' + ','.join(coord) + ')'
        # If all numbers, normalize to ndarray.
        if all(_numeric(x) for x in coord):
            return np.array(coord)
        # If mixed, keep.
        return coord
    # A coordinate can be a 2/3-element 1d-ndarray.
    if (_ndarray(coord) and coord.ndim == 1 and coord.size in [2, 3]
            and all(_numeric(x) for x in coord)):
        return coord
    # Otherwise, report error.
    raise TypeError(f'{coord} is not a coordinate')


def _sequence(seq, accept_coordinate=True):
    "check and normalize sequence of coordinates"
    # A sequence can be a list.
    if _list(seq):
        # Normalize contained coordinates.
        seq = [_coordinate(coord) for coord in seq]
        # If all coordinates are 1d-ndarrays, make the sequence a 2d-ndarray.
        if (all(_ndarray(coord) for coord in seq)
                and all(coord.size == seq[0].size for coord in seq)):
            return np.array(seq)
        return seq
    # A sequence can be a numeric 2d-ndarray with 2 or 3 columns.
    if (_ndarray(seq) and seq.ndim == 2 and seq.shape[1] in [2, 3]
            and all(_numeric(x) for x in seq.flat)):
        return seq
    # Optionally accept a coordinate and turn it into a 1-element sequence.
    if accept_coordinate:
        return _sequence([seq])
    # Otherwise, report error.
    raise TypeError(f'{seq} is not a sequence of coordinates')


def _str_or_numeric_code(x):
    """
    transform element of coordinate into TikZ representation

    Restricts numbers to 5-digit fixed-point representation (TikZ precision:
    ±16383.99999) without trailing '0' or '.'
    """
    if _str(x):
        return x
    else:
        return '{:.5f}'.format(x).rstrip('0').rstrip('.')


def _coordinate_code(coord):
    "transform coordinate into TikZ representation"
    # assumes the argument has already been normalized
    if _str(coord):
        return coord
    else:
        return '(' + ','.join(map(_str_or_numeric_code, coord)) + ')'


def cycle():
    "cycle 'coordinate'"
    return 'cycle'


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


def horizontal(point1, point2):
    "perpendicular coordinates, horizontal"
    coord = _point(point1)
    if coord.startswith('(') and coord.endswith(')'):
        coord = coord[1:-1]
    code = '(' + coord + ' -| '
    coord = _point(point2)
    if coord.startswith('(') and coord.endswith(')'):
        coord = coord[1:-1]
    code += coord + ')'
    return code

# relative coordinates should be added


# path operations (§14)


class moveto:
    """
    one or several move-to operations

    see §14.1
    """
    def __init__(self, coords):
        self.coords = _sequence(coords, accept_coordinate=True)

    def code(self):
        # put move-to operation before each coordinate,
        # for the first one implicitly
        return ' '.join(_coordinate_code(coord) for coord in self.coords)


class lineto:
    """
    one or several line-to operations of the same type

    `op` can be
    -   '--' for straight lines (default),
    -   '-|' for first horizontal, then vertical, or
    -   '|-' for first vertical, then horizontal

    see §14.2
    """
    def __init__(self, coords, op='--'):
        self.coords = _sequence(coords, accept_coordinate=True)
        self.op = op

    def code(self):
        # put line-to operation before each coordinate
        return f'{self.op} ' + f' {self.op} '.join(
            _coordinate_code(coord) for coord in self.coords)


class line:
    """
    convenience version of `lineto`

    Starts with move-to instead of line-to operation.
    """
    def __init__(self, coords, op='--'):
        self.coords = _sequence(coords)
        self.op = op

    def code(self):
        # put line-to operation between coordinates
        # (implicit move-to before first)
        return f' {self.op} '.join(
            _coordinate_code(coord) for coord in self.coords)


class curveto:
    """
    curve-to operation
    
    see §14.3
    """
    def __init__(self, coord, control1, control2=None):
        self.coord = _coordinate(coord)
        self.control1 = _coordinate(control1)
        if control2 is not None:
            self.control2 = _coordinate(control2)
        else:
            self.control2 = None

    def code(self):
        code = '.. controls ' + _coordinate_code(self.control1)
        if self.control2 is not None:
            code += ' and ' + _coordinate_code(self.control2)
        code += ' ..' + ' ' + _coordinate_code(self.coord)
        return code


class rectangle:
    """
    rectangle operation

    see §14.4
    """
    def __init__(self, coord, opt=None, **kwoptions):
        self.coord = _coordinate(coord)
        self.opt = opt
        self.kwoptions = kwoptions

    def code(self):
        return ('rectangle' + _options_code(opt=self.opt, **self.kwoptions)
                + ' ' + _coordinate_code(self.coord))


class circle:
    """
    circle operation

    see §14.6
    """
    def __init__(self, radius=None, x_radius=None, y_radius=None, at=None,
                 opt=None, **kwoptions):
        if radius is not None:
            self.x_radius = radius
            self.y_radius = radius
        else:
            self.x_radius = x_radius
            self.y_radius = y_radius
        if at is not None:
            self.at = _coordinate(at)
        else:
            self.at = None
        self.opt = opt
        self.kwoptions = kwoptions

    def code(self):
        kwoptions = self.kwoptions
        if self.x_radius == self.y_radius:
            kwoptions['radius'] = self.x_radius
        else:
            kwoptions['x_radius'] = self.x_radius
            kwoptions['y_radius'] = self.y_radius
        if self.at is not None:
            kwoptions['at'] = _coordinate_code(self.at)
        return 'circle' + _options_code(opt=self.opt, **self.kwoptions)


class arc:
    """
    arc operation

    see §14.7
    """
    def __init__(self, radius=None, x_radius=None, y_radius=None,
                 opt=None, **kwoptions):
        if radius is not None:
            self.x_radius = radius
            self.y_radius = radius
        else:
            self.x_radius = x_radius
            self.y_radius = y_radius
        self.opt = opt
        self.kwoptions = kwoptions

    def code(self):
        kwoptions = self.kwoptions
        if self.x_radius == self.y_radius:
            kwoptions['radius'] = self.x_radius
        else:
            kwoptions['x_radius'] = self.x_radius
            kwoptions['y_radius'] = self.y_radius
        return 'arc' + _options_code(opt=self.opt, **kwoptions)


class grid:
    """
    grid operation

    Specifying `step` as a coordinate is not supported, use `xstep` and
    `ystep` instead.
    
    see §14.8
    """
    def __init__(self, coord, step=None, xstep=None, ystep=None,
                 opt=None, **kwoptions):
        self.coord = _coordinate(coord)
        if step is not None:
            self.xstep = step
            self.ystep = step
        else:
            self.xstep = xstep
            self.ystep = ystep
        self.opt = opt
        self.kwoptions = kwoptions

    def code(self):
        kwoptions = self.kwoptions
        if self.xstep == self.ystep:
            kwoptions['step'] = self.xstep
        else:
            kwoptions['xstep'] = self.xstep
            kwoptions['ystep'] = self.ystep
        return ('grid' + _options_code(opt=self.opt, **kwoptions)
                + ' ' + _coordinate_code(self.coord))


class parabola:
    """
    parabola operation

    see §14.9
    """
    def __init__(self, coord, bend=None, opt=None, **kwoptions):
        self.coord = _coordinate(coord)
        if bend is not None:
            self.bend = _coordinate(bend)
        else:
            self.bend = None
        self.opt = opt
        self.kwoptions = kwoptions

    def code(self):
        code = 'parabola' + _options_code(opt=self.opt, **self.kwoptions)
        if self.bend is not None:
            code += ' bend ' + _coordinate_code(self.bend)
        code += ' ' + _coordinate_code(self.coord)
        return code


class sin:
    """
    sine operation

    see §14.10
    """
    def __init__(self, coord, opt=None, **kwoptions):
        self.coord = _coordinate(coord)
        self.opt = opt
        self.kwoptions = kwoptions

    def code(self):
        return ('sin' + _options_code(opt=self.opt, **self.kwoptions)
                + ' ' + _coordinate_code(self.coord))


class cos:
    """
    cosine operation

    see §14.10
    """
    def __init__(self, coord, opt=None, **kwoptions):
        self.coord = _coordinate(coord)
        self.opt = opt
        self.kwoptions = kwoptions

    def code(self):
        return ('cos' + _options_code(opt=self.opt, **self.kwoptions)
                + ' ' + _coordinate_code(self.coord))


class topath:
    """
    to-path operation

    see §14.13
    """
    def __init__(self, coord, opt=None, **kwoptions):
        self.coord = _coordinate(coord)
        self.opt = opt
        self.kwoptions = kwoptions

    def code(self):
        return ('to' + _options_code(opt=self.opt, **self.kwoptions)
                + ' ' + _coordinate_code(self.coord))


class node:
    """
    node operation

    `name` can be specified through options.

    Animation is not supported because it does not make sense for static
    image generation. The foreach statement for nodes is not supported because
    it can be replaced by a Python loop.

    see §17
    """
    def __init__(self, contents, at=None, opt=None, **kwoptions):
        self.contents = contents
        if at is not None:
            self.at = _coordinate(at)
        else:
            self.at = None
        self.opt = opt
        self.kwoptions = kwoptions

    def code(self):
        code = 'node' + _options_code(opt=self.opt, **self.kwoptions)
        if self.at is not None:
            code += ' at ' + _coordinate_code(self.at)
        code += ' {' + self.contents + '}'
        return code


class coordinate:
    """
    coordinate operation

    `name` can be specified through options.

    Animation is not supported because it does not make sense for static
    image generation. The foreach statement for coordinates is not supported
    because it can be replaced by a Python loop.

    see §17.2.1
    """
    def __init__(self, at=None, opt=None, **kwoptions):
        if at is not None:
            self.at = _coordinate(at)
        else:
            self.at = None
        self.opt = opt
        self.kwoptions = kwoptions

    def code(self):
        code = 'coordinate' + _options_code(opt=self.opt, **self.kwoptions)
        if self.at is not None:
            code += ' at ' + _coordinate_code(self.at)
        return code


class plot:
    """
    plot operation

    The decision whether to directly specify coordinates or provide them
    through a file is made internally. Coordinate expressions and gnuplot
    formulas are not supported.

    see §22
    """
    def __init__(self, coords, to=False, opt=None, **kwoptions):
        self.coords = _sequence(coords, accept_coordinate=True)
        self.to = to
        self.opt = opt
        self.kwoptions = kwoptions

    def code(self):
        # The 'file' variant may be used in the future as an alternative to
        # coordinates when there are many points.
        if self.to:
            code = '--plot'
        else:
            code = 'plot'
        code += _options_code(opt=self.opt, **self.kwoptions)
        code += ' coordinates {' + ' '.join(
            _coordinate_code(coord) for coord in self.coords) + '}'
        return code


# more operations to follow


# environments


class Scope:
    "representation of `scope` environment"

    def __init__(self, opt=None, **kwoptions):
        self.elements = []
        self.opt = _options_code(opt=opt, **kwoptions)

    def add(self, el):
        "add element (may be string)"
        self.elements.append(el)

    def add_scope(self, opt=None, **kwoptions):
        "add scope environment"
        s = Scope(opt=opt, **kwoptions)
        self.add(s)
        return s

    def __str__(self):
        "create LaTeX code"
        code = r'\begin{scope}' + self.opt + '\n'
        code += '\n'.join(map(str, self.elements)) + '\n'
        code += r'\end{scope}'
        return code

    # actions on paths (§15)

    def _action(self, action_name, *spec, opt=None, **kwoptions):
        "helper function for actions"
        self.add('\\' + action_name
                 + _options_code(opt=opt, **kwoptions) + ' '
                 + moveto(spec) + ';')

    def path(self, *spec, opt=None, **kwoptions):
        "path action"
        self._action('path', *spec, opt=None, **kwoptions)

    def draw(self, *spec, opt=None, **kwoptions):
        "draw action"
        self._action('draw', *spec, opt=None, **kwoptions)

    def fill(self, *spec, opt=None, **kwoptions):
        "fill action"
        self._action('fill', *spec, opt=None, **kwoptions)

    def filldraw(self, *spec, opt=None, **kwoptions):
        "filldraw action"
        self._action('filldraw', *spec, opt=None, **kwoptions)

    def pattern(self, *spec, opt=None, **kwoptions):
        "pattern action"
        self._action('pattern', *spec, opt=None, **kwoptions)

    def shade(self, *spec, opt=None, **kwoptions):
        "shade action"
        self._action('shade', *spec, opt=None, **kwoptions)

    def shadedraw(self, *spec, opt=None, **kwoptions):
        "shadedraw action"
        self._action('shadedraw', *spec, opt=None, **kwoptions)

    def clip(self, *spec, opt=None, **kwoptions):
        "clip action"
        self._action('clip', *spec, opt=None, **kwoptions)

    def useasboundingbox(self, *spec, opt=None, **kwoptions):
        "useasboundingbox action"
        self._action('useasboundingbox', *spec, opt=None, **kwoptions)
        
    # \node → \path node
    # \coordinate → \path coordinate

    # more actions to follow

    # other commands

    def definecolor(self, name, colormodel, colorspec):
        """
        xcolor definecolor command

        Define new color from color model and specification.

        - core models: rgb, cmy, cmyk, hsb, gray
        - integer models: RGB, HTML, HSB, Gray
        - decimal models: Hsb, tHsb, wave
        - pseudo models: names, ps
        """
        if not isinstance(colorspec, str):
            colorspec = ','.join(colorspec)
        self.add(r'\definecolor' + '{' + name + '}{'
                 + colormodel + '}{' + colorspec + '}')

    def colorlet(self, name, colorexpr):
        """
        xcolor colorlet command

        Define new color from color expression, e.g. 'blue!20!white'.
        """
        self.add(r'\colorlet' + '{' + name + '}{' + colorexpr + '}')

    def tikzset(self, opt=None, **kwoptions):
        "tikzset command"
        # create options string without brackets
        opt = _options_code(opt=opt, **kwoptions)
        if opt.startswith('[') and opt.endswith(']'):
            opt = opt[1:-1]
        # because braces are needed
        self.add(r'\tikzset{' + opt + '}')

    def tikzstyle(self, name, opt=None, **kwoptions):
        "emulates deprecated tikzstyle command using tikzset"
        # create options string without brackets
        opt = _options_code(opt=opt, **kwoptions)
        if opt.startswith('[') and opt.endswith(']'):
            opt = opt[1:-1]
        # because braces are needed
        self.add(r'\tikzset{' + name + '/.style={' + opt + '}}')


class Picture(Scope):
    "representation of `tikzpicture` environment"

    def __init__(self, opt=None, **kwoptions):
        super().__init__(opt=opt, **kwoptions)
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
        code = r'\begin{tikzpicture}' + self.opt + '\n'
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
    pic.draw((0, 0), node(r'\textsf{py}Ti\emph{k}Z', scale=2), darkgray=True)
    pic.write_image('pytikz.png')
