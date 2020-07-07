"""
# pytikz

A Python interface to TikZ
"""

import atexit
import base64
import hashlib
import html
import numbers
import os
import os.path
import shutil
import subprocess
import tempfile

import fitz
import IPython.display
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


# helper functions and helper-helper functions


def _option_code(key, val):
    """
    transform single `key=value` pair into TikZ string

    A value of `True` is omitted, an underscore in a key is transformed into
    a space.

    helper function for `_options`
    """
    key = str(key).replace('_', ' ')
    if val is True:
        return key
    else:
        return f'{key}={str(val)}'


def _options_code(opt=None, **kwoptions):
    """
    transform options parameters into TikZ options string

    Transforms additional keyword parameters captured as a dictionary
    (`**kwoptions`) into string. Options with value `None` are omitted. A
    supplementary raw part of the options string can be provided
    via the keyword parameter `opt`. Example:
        (opt='red', thick=True, rounded_corners='4pt')
    returns
        '[thick,rounded corners=4pt,red]'

    helper function to format `opt=None, **kwoptions` in various functions
    """
    o = [_option_code(key, val) for key, val in kwoptions.items()
         if val is not None]
    if opt is not None:
        o.insert(0, opt)
    code = '[' + ','.join(o) + ']'
    if code == '[]':
        code = ''
    return code


def _str(obj): return isinstance(obj, str)


def _tuple(obj): return isinstance(obj, tuple)


def _numeric(obj): return isinstance(obj, numbers.Real)


def _str_or_numeric(obj): return _str(obj) or _numeric(obj)


def _ndarray(obj): return isinstance(obj, np.ndarray)


def _list(obj): return isinstance(obj, list)


def _coordinate(coord):
    """
    check and normalize coordinate

    A coordinate (in path specifications as well as as arguments elsewhere) is
    a string, or a `tuple` or 1d-`ndarray` with 2 or 3 elements.

    Strings can be used e.g. to provide coordinates in TikZ' `canvas`
    coordinate system. Coordinate-specifying strings are enclosed in
    parentheses, possibly prefixed by `+` or `++` (relative coordinates).

    Elements of `tuple`s can be numbers or strings. If all elements are
    numeric, it represents coordinates in TikZ' `xyz` coordinate system and is
    converted into a 1d-`ndarray`. If all are strings it represents
    coordinates in TikZ' `canvas` coordinate system, and is converted into a
    simple string including parentheses. Otherwise it represents a mixed
    `xyz`/`canvas` coordinate as described in §13.2.1 and is left as a tuple.

    `ndarray`s must be numeric.
    """
    # A coordinate can be a string with enclosing parentheses, possibly
    # prefixed by `+` or `++`, or the string 'cycle'.
    if _str(coord) and (
            (coord.startswith(('(', '+(', '++(')) and coord.endswith(')'))
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
    """
    check and normalize sequence of coordinates

    A sequence of coordinates is a `list` of coordinates as described under
    `_coordinate`, or a numeric 2d-`ndarray` with 2 or 3 columns,
    representing `xyz` coordinates. If a list contains only
    numeric 1d-`ndarray`s (after conversion) with the same number of elements,
    it is converted into a 2d-`ndarray` itself.
    """
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

    Leaves string  elements as is, and converts numeric elements to a
    fixed-point representation with 5 decimals precision (TikZ: ±16383.99999)
    without trailing '0's or '.'
    """
    if _str(x):
        return x
    else:
        return '{:.5f}'.format(x).rstrip('0').rstrip('.')


def _coordinate_code(coord):
    "create TikZ code for coordinate"
    # assumes the argument has already been normalized
    if _str(coord):
        return coord
    else:
        return '(' + ','.join(map(_str_or_numeric_code, coord)) + ')'


def _operation(op):
    """
    check and normalize path specification elements

    The elements of a path specification argument (`*spec`) can be `Operation`
    objects (left as is), (lists of) coordinates (converted to `moveto`
    objects), and strings (converted to `Raw` objects).
    """
    if isinstance(op, Operation):
        return op
    if _str(op):
        return Raw(op)
    return moveto(op)


# coordinates


def cycle():
    "cycle coordinate"
    return 'cycle'


# raw object

class Raw:
    """
    raw TikZ code object

    In order to support TikZ features that are not explicitly modelled, objects
    of this class encapsulate a string which is copied as-is into the TikZ
    code. `Raw` objects can be used in place of `Operation` and `Action`
    objects.
    """
    def __init__(self, string):
        self.string = string

    def code(self):
        return self.string


# path operations (§14)


class Operation:
    """
    path operation

    Path operations (§14) are modelled as `Operation` objects so that code
    generation can (in the future) depend on the context. All code
    generation beyond single coordinates is implemented by a method `code`
    (which will in the future accept an optional transformation argument).

    Names for `Operation` subclasses are lowercase, because from a user
    perspective they act like functions; no method call or field access should
    be performed on their instances.

    This is an abstract superclass that is not to be instantiated.
    """
    pass


class moveto(Operation):
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


class lineto(Operation):
    """
    one or several line-to operations of the same type

    `op` can be `'--'` for straight lines (default), `'-|'` for first
    horizontal, then vertical, or `'|-'` for first vertical, then horizontal.

    see §14.2
    """
    def __init__(self, coords, op='--'):
        self.coords = _sequence(coords, accept_coordinate=True)
        self.op = op

    def code(self):
        # put line-to operation before each coordinate
        return f'{self.op} ' + f' {self.op} '.join(
            _coordinate_code(coord) for coord in self.coords)


class line(Operation):
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


class curveto(Operation):
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


class rectangle(Operation):
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


class circle(Operation):
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


class arc(Operation):
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


class grid(Operation):
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


class parabola(Operation):
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


class sin(Operation):
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


class cos(Operation):
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


class topath(Operation):
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


class node(Operation):
    """
    node operation

    Animation is not supported because it does not make sense for static
    image generation. The foreach statement for nodes is not supported because
    it can be replaced by a Python loop.

    Provides 'headless' mode for node action.

    see §17
    """
    def __init__(self, contents, name=None, at=None, headless=False,
                 opt=None, **kwoptions):
        self.name = name
        self.contents = contents
        if at is not None:
            self.at = _coordinate(at)
        else:
            self.at = None
        self.headless = headless
        self.opt = opt
        self.kwoptions = kwoptions

    def code(self):
        if not self.headless:
            code = 'node'
        else:
            code = ''
        code += _options_code(opt=self.opt, **self.kwoptions)
        if self.name is not None:
            code += f' ({self.name})'
        if self.at is not None:
            code += ' at ' + _coordinate_code(self.at)
        code += ' {' + self.contents + '}'
        if self.headless:
            code = code.lstrip()
        return code


class coordinate(Operation):
    """
    coordinate operation

    Animation is not supported because it does not make sense for static
    image generation. The foreach statement for coordinates is not supported
    because it can be replaced by a Python loop.

    Provides 'headless' mode for coordinate action.

    see §17.2.1
    """
    def __init__(self, name, at=None, headless=False, opt=None, **kwoptions):
        self.name = name
        if at is not None:
            self.at = _coordinate(at)
        else:
            self.at = None
        self.headless = headless
        self.opt = opt
        self.kwoptions = kwoptions

    def code(self):
        if not self.headless:
            code = 'coordinate'
        else:
            code = ''
        code += _options_code(opt=self.opt, **self.kwoptions)
        code += f' ({self.name})'
        if self.at is not None:
            code += ' at ' + _coordinate_code(self.at)
        if self.headless:
            code = code.lstrip()
        return code


class plot(Operation):
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


def options(opt=None, **kwoptions):
    """
    in-path options

    This is not a path operation, but can be specified at an arbitrary position
    within a path specification. It sets options for the rest of the path.
    """
    # just a wrapper around _options_code
    return _options_code(opt=opt, **kwoptions)


# actions on paths

class Action:
    """
    action on path

    see §15
    """
    def __init__(self, action_name, *spec, opt=None, **kwoptions):
        self.action_name = action_name
        self.spec = [_operation(op) for op in spec]
        self.opt = opt
        self.kwoptions = kwoptions

    def code(self):
        return ('\\' + self.action_name
                + _options_code(opt=self.opt, **self.kwoptions)
                + ' ' + ' '.join(op.code() for op in self.spec) + ';')


# environments


class Scope:
    "scope environment"

    def __init__(self, opt=None, **kwoptions):
        self.elements = []
        self.opt = _options_code(opt=opt, **kwoptions)

    def _append(self, el):
        """
        append element

        Elements of an environment object can be `Action` objects (for path
        actions), `Raw` objects (for other commands), or other environment
        objects.
        """
        self.elements.append(el)

    def add_scope(self, opt=None, **kwoptions):
        "create and add scope environment"
        s = Scope(opt=opt, **kwoptions)
        self._append(s)
        return s

    def code(self):
        "create TikZ code"
        code = r'\begin{scope}' + self.opt + '\n'
        code += '\n'.join(el.code() for el in self.elements) + '\n'
        code += r'\end{scope}'
        return code

    # add actions on paths (§15)

    def path(self, *spec, opt=None, **kwoptions):
        "path action"
        self._append(Action('path', *spec, opt=opt, **kwoptions))

    def draw(self, *spec, opt=None, **kwoptions):
        "draw action"
        self._append(Action('draw', *spec, opt=opt, **kwoptions))

    def fill(self, *spec, opt=None, **kwoptions):
        "fill action"
        self._append(Action('fill', *spec, opt=opt, **kwoptions))

    def filldraw(self, *spec, opt=None, **kwoptions):
        "filldraw action"
        self._append(Action('filldraw', *spec, opt=opt, **kwoptions))

    def pattern(self, *spec, opt=None, **kwoptions):
        "pattern action"
        self._append(Action('pattern', *spec, opt=opt, **kwoptions))

    def shade(self, *spec, opt=None, **kwoptions):
        "shade action"
        self._append(Action('shade', *spec, opt=opt, **kwoptions))

    def shadedraw(self, *spec, opt=None, **kwoptions):
        "shadedraw action"
        self._append(Action('shadedraw', *spec, opt=opt, **kwoptions))

    def clip(self, *spec, opt=None, **kwoptions):
        "clip action"
        self._append(Action('clip', *spec, opt=opt, **kwoptions))

    def useasboundingbox(self, *spec, opt=None, **kwoptions):
        "useasboundingbox action"
        self._append(Action('useasboundingbox', *spec, opt=opt, **kwoptions))

    def node(self, contents, name=None, at=None, opt=None, **kwoptions):
        "node action"
        self._append(Action(
            'node', node(contents, name=name, at=at, headless=True),
            opt=opt, **kwoptions))

    def coordinate(self, name, at=None, opt=None, **kwoptions):
        "coordinate action"
        self._append(Action(
            'coordinate', coordinate(name=name, at=at, headless=True),
            opt=opt, **kwoptions))

    # other commands

    def definecolor(self, name, colormodel, colorspec):
        """
        definecolor command (xcolor)

        Define new color from color model and specification.

        - core models: rgb, cmy, cmyk, hsb, gray
        - integer models: RGB, HTML, HSB, Gray
        - decimal models: Hsb, tHsb, wave
        - pseudo models: names, ps
        """
        if not isinstance(colorspec, str):
            colorspec = ','.join(colorspec)
        self._append(Raw(r'\definecolor' + '{' + name + '}{'
                     + colormodel + '}{' + colorspec + '}'))

    def colorlet(self, name, colorexpr):
        """
        colorlet command (xcolor)

        Define new color from color expression, e.g. 'blue!20!white'.
        """
        self._append(Raw(r'\colorlet' + '{' + name + '}{' + colorexpr + '}'))

    def tikzset(self, opt=None, **kwoptions):
        """
        tikzset command

        Sets options.
        """
        # create options string without brackets
        opt = _options_code(opt=opt, **kwoptions)
        if opt.startswith('[') and opt.endswith(']'):
            opt = opt[1:-1]
        # because braces are needed
        self._append(Raw(r'\tikzset{' + opt + '}'))

    def tikzstyle(self, name, opt=None, **kwoptions):
        """
        define style

        Emulates deprecated tikzstyle command using tikzset.
        """
        # create options string without brackets
        opt = _options_code(opt=opt, **kwoptions)
        if opt.startswith('[') and opt.endswith(']'):
            opt = opt[1:-1]
        # because braces are needed
        self._append(Raw(r'\tikzset{' + name + '/.style={' + opt + '}}'))


class Picture(Scope):
    "tikzpicture environment"

    def __init__(self, opt=None, **kwoptions):
        super().__init__(opt=opt, **kwoptions)
        # additional preamble entries
        self.preamble = []
        # create temporary directory for pdflatex etc.
        self.tempdir = tempfile.mkdtemp(prefix='tikz-')
        # make sure it gets deleted
        atexit.register(shutil.rmtree, self.tempdir, ignore_errors=True)

    def usetikzlibrary(self, library):
        "usetikzlibrary command"
        self.preamble.append(r'\usetikzlibrary{' + library + '}')

    def code(self):
        "create TikZ code"
        # We use `str` to create the LaTeX code so that we can directly include
        # strings in `self.elements`, for which `str()` is idempotent.
        code = r'\begin{tikzpicture}' + self.opt + '\n'
        code += '\n'.join(el.code() for el in self.elements) + '\n'
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
            + self.code() + '\n'
            + r'\end{document}' + '\n')

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
        """
        write picture to image file

        The file type is determined from the file extension, and can be PDF,
        PNG, or SVG.
        """
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

    def _repr_png_(self, dpi=None):
        "represent of picture as PNG for notebook"
        self._create_pdf()
        if dpi is None:
            dpi = cfg.display_dpi
        zoom = dpi / 72
        doc = fitz.open(self.temp_pdf)
        page = doc.loadPage(0)
        pix = page.getPixmap(matrix=fitz.Matrix(zoom, zoom))
        return pix.getPNGdata()

    def demo(self, dpi=None):
        "convenience function to test & debug picture"
        png_base64 = ''
        try:
            png_base64 = base64.b64encode(
                self._repr_png_(dpi=dpi)).decode('ascii')
        except LatexException as le:
            message = le.args[0]
            tikz_error = message.find('! ')
            if tikz_error != -1:
                message = message[tikz_error:]
            print(message)
        code_escaped = html.escape(self.code())
        IPython.display.display(IPython.display.HTML(
            cfg.demo_template.format(png_base64, code_escaped)))


class LatexException(Exception):
    "problem with external LaTeX process"
    pass
