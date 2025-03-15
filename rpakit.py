#!/usr/bin/python3

"""
Copyright 2025 madeddy

   Licensed under the Apache License, Version 2.0 (the "License");
   you may not use this file except in compliance with the License.
   You may obtain a copy of the License at

       http://www.apache.org/licenses/LICENSE-2.0

   Unless required by applicable law or agreed to in writing, software
   distributed under the License is distributed on an "AS IS" BASIS,
   WITHOUT WARRANTIES OR CONDITIONS OF ANY KIND, either express or implied.
   See the License for the specific language governing permissions and
   limitations under the License.



RPAKit is a small app which searches in a given path(if not file) RenPy archives and
decompresses the content in a custom-made subdirectory. Just listing without writing or
testing & identifying the archiv or simulating the extract process is also possible.
"""

# TODO: Overall tasks:
# 1. Test atexit; remove remaining outcommented code
# 2. Add functionality to force rpa format version from user input
# 3. Fix the modules codetag tasks

__title__ = 'RPA Kit'
__license__ = 'Apache 2.0'
__author__ = 'madeddy'
__status__ = 'Development'
__version__ = '0.49.0-alpha'
__url__ = "https://github.com/madeddy/RpaKit"

import argparse
import atexit
import glob
import logging
import pickle
import shutil
import sys
import tempfile
import traceback
import zlib
from copy import copy
from os import urandom
from pathlib import Path
from time import strftime

tty_colors = True
if sys.platform.startswith('win32'):
    try:
        from colorama import init
        init(autoreset=True)
    except ImportError:
        tty_colors = False


# NOTE: They use colors from RkCommon with self. Does this even work?
class RpaKitError(Exception):
    """Base class for exceptions in RpaKit."""

    def __init__(self, msg):
        self.msg = msg

    def __str__(self):
        return f"{self.red}{repr(self.msg)}{self.reset}"


class AmbiguousHeaderError(RpaKitError):
    """Exception raised if for a archiv more as one format dedected was.

    Parameter:
        vers -- version dict in which the error occurred
        message -- explanation of the error
    """

    def __init__(self, dep, ver):
        self.dep = dep
        self.ver = [v for k, v in ver.items() if 'rpaid' in k]
        super().__init__(
            "Detection of the archive format failed because multiple matches where found.\n"
            f"Archive: {self.dep} with Version > {self.ver}")


class NoRpaOrUnknownWarning(RpaKitError):
    """Warning raised if a archiv format could not identified.

    Parameter:
        dep -- depot with the problem
        message -- explanation of the problem
    """

    def __init__(self, dep, head):
        self.dep = dep
        self.head = head
        super().__init__(
            "Header not recognizable. The tested archive is not a RPA or a custom type.\n"
            f"Archive: {self.dep} with header: > {self._header}")


class ColorFormatter(logging.Formatter):
    """
    A subclass of Formatter that colors the level names of log records.

    Overrides the format method and uses a record copy to avoid altering the original, or
    other handlers emit ANSI escape sequences.
    """

    reset = '\x1b[0m'  # reset
    level_map = {
        'DEBUG': '\x1b[1;37m',  # bold, grey
        'INFO': '\x1b[32m',  # green
        'IMPORTANT': '\x1b[94m',  # light blue
        'WARNING': '\x1b[33m',  # yellow
        'ERROR': '\x1b[1;35m',  # bold, red
        'CRITICAL': '\x1b[30;41m'  # black, red bg
    }

    def format(self, record):
        color_record = copy(record)
        seq = self.level_map.get(record.levelname, '\x1b[1;37m')
        color_record.levelname = f"{seq}{record.levelname}{self.reset}"
        return super().format(color_record)


class RpaKitLog(logging.Logger):
    """
    This configures and initiates all logging functionality for the module.

    Contains a `colorname-to-ANSI` mapping dict which yields escape sequences for colored
    output.
    It adds a streamhandler for console output, including colored output, and a filehandler
    which writes to a logfile. The latter can be disabled by CLI.

      Arguments:
        Positional: {name} takes `str` for the logger name
        Keyword: {logfile} takes `bool` to enable or disable the logfile
        Keyword: {loglevel} takes `str` from choices
    """

    ansi_colormap = {
        'reset': '\x1b[0m',
        'bold': '\x1b[1m',
        'uline': '\x1b[4m',  # underline
        'blink': '\x1b[5m',  # blinking
        'reverse': '\x1b[7m',  # fg <-> bg
        'black': '\x1b[30m',
        'orange': '\x1b[31m',
        'green': '\x1b[32m',
        'yellew': '\x1b[33m',
        'blue': '\x1b[34m',
        'red': '\x1b[35m',
        'cyan': '\x1b[36m',
        'lblue': '\x1b[94m',  # light blue
        'bg_yellow': '\x1b[43;30m',  # bg = background
        'bg_blue': '\x1b[44;30m',
        'bg_red': '\x1b[45;30m',
        'bg_white': '\x1b[47;30m',
        'ret': '\x1b[10D\x1b[1A\x1b[K'  # write on same line: (xD=x rows left, xA=x lines up,
        # K=erase line)
    }

    def __init__(self, name, logfile=True, loglevel='IMPORTANT'):
        super().__init__(name)
        self.loglevel = loglevel
        self.tty_colors = True
        self.oldwin_tty_colors()
        logging.addLevelName(25, 'IMPORTANT')
        logging.Logger.important = self.important

        self.init_streamhandler()
        if logfile:
            self.init_filehandler()

    # TODO: needs testing in windows
    def oldwin_tty_colors(self):
        """
        This attempts to enable ANSI colors for older Windows versions. Since W10 Preview
        build 16257 this is no longer necessary.
        Values for usage with ctypes lib:
        -11 is STD_OUTPUT_HANDLE; -12 is STD_ERROR_HANDLE
        7 is ENABLE_VIRTUAL_TERMINAL_PROCESSING
        """
        if sys.platform.startswith('win32') and sys.getwindowsversion()[2] < 16257:
            try:
                from ctypes import windll
                h = windll.kernel32
                h.SetConsoleMode(h.GetStdHandle(-11), 7)
            except Exception:
                print("The first try enabling TTY colors per ctypes failed.")
                self.tty_colors = False

            if not self.tty_colors:
                try:
                    # NOTE: allegedly enables also ANSI colors in Windows 10
                    from os import system
                    system('')
                except Exception:
                    print("Enabling TTY colors failed. This is not a critical error, but "
                          "the terminal output will be colorless.")
                else:
                    self.tty_colors = True

            RpaKitLog.ansi_colormap.update(
                (k, '') for k in self.ansi_colormap if not self.tty_colors)

    def important(self, msg, *args, **kwargs):
        """
        Adds a custom logging level 'IMPORTANT' with severity level 25, between
        info(20) and warning(30).
        """
        if self.isEnabledFor(25):
            self._log(25, msg, args, **kwargs)

    def init_streamhandler(self):
        """
        Sets up the basic console handler configuration.
        Adds the console handler always and use custom formatter if tty-colors are available.
        """
        fmt_cls = ColorFormatter if self.tty_colors else logging.Formatter()
        fmt = "[{name}][{levelname:>8s}] >> {message}"

        ch = logging.StreamHandler()
        ch.setLevel(self.loglevel)
        ch.setFormatter(fmt_cls(fmt, style='{'))
        self.addHandler(ch)

    def init_filehandler(self):
        """
        Sets up the file logger configuration.
        If not disabled in CLI, a logfile in the script path and a file handler is added.
        """
        # NOTE: filename:lineno should probably at linestart - needs testing
        fmt = "{asctime} - {name}:{levelname:8s} - {message} - {filename}:{lineno:d}"
        logfilename = f"unren2_{strftime('%d%m%Y')}.log"

        fh = logging.FileHandler(Path(__file__).parent.resolve().joinpath(logfilename))
        fh.setLevel('DEBUG')
        fh.setFormatter(logging.Formatter(fmt, datefmt='%d.%b%Y %H:%M:%S', style='{'))
        self.addHandler(fh)

    @classmethod
    def cm(cls, key):
        """Shorthand to the `ansi_colormap` dict for easier usage."""
        return cls.ansi_colormap[key]


class RkCommon:
    """
    "Rpa Kit Common" acts as superclass for the classes RkPathWork and RkDepotWork and provides
    some shared methods and variables.
    """
    name = __title__
    count = {'dep_found': 0, 'dep_done': 0, 'files_total': 0, 'dep_id_found': 0}

    def pm(self, fraction, total, object, bg_color=None):
        """Returns a fraction-meter like output for use in tty."""
        color = bg_color or 'bg_blue'
        return (f"[{self.log.cm(color)}{fraction:{len(str(total))}>n}/{total:>n}"
                f"{self.log.cm('reset')}] {object!s:>4}")

    @classmethod
    def void_dir(cls, dst):
        """Checks if given directory has content."""
        return not any(dst.iterdir())

    def make_dirstruct(self, dst):
        """Constructs any needet output directorys if they not already exist."""
        if not dst.exists():
            self.log.info(f"Creating directory structure for: {dst}")
            dst.mkdir(parents=True, exist_ok=True)


class RkPathWork(RkCommon):
    """
    This is a support class for RPA Kit's path related tasks. Positional inputs are a ´file
    or directory paths` and ´task`. Optional inputs are "outdir" and "overwrite" and have
    default values.
    If input is a dir it searches there for archives, checks and filters them and stores them
    in a list. A archiv file as input skips the search part.
    """

    log = None
    outdir = 'rpakit_out'
    overwrite = False

    def __init__(self, raw_inp, task, outdir=None, overwrite=None, log_instance=None):
        super().__init__()
        self.raw_inp = raw_inp
        self.task = task
        if outdir:
            self.outdir = Path(outdir)
        if overwrite:
            self.overwrite = overwrite
        self.log = log_instance

        self.inp_pt = None
        # self.inp_pt = self.raw_inp.parent if self.raw_inp.is_file() else self.raw_inp
        self.out_pt = None
        self.rk_tmp_dir = None
        self.dep_lst = []

    def _dispose(self):
        """Removes temporary directory/-tree and the outdir if empty."""
        # a empty output can be removed
        if self.void_dir(self.out_pt):
            self.out_pt.rmdir()

        try:
            shutil.rmtree(self.rk_tmp_dir)
        except TypeError:
            self.log.warning(f"Tempdir '{self.rk_tmp_dir}' did not exist.")
        else:
            self.log.debug("Tempdir was successful removed.")

        if self.rk_tmp_dir is not None and self.rk_tmp_dir.exists():
            self.log.error(f"Tempdir '{self.rk_tmp_dir}' could not be removed!")

    def mv_tmp2outdir(self):
        """Copys all unpacked content from temporary dir to the output dir."""
        # FIXME: errors if a src dir exists in dst which happens with --overwrite option
        # for entry in self.rk_tmp_dir.iterdir():
        #     shutil.move(entry, self.out_pt)

        # move() errors on existing obj so the manual way with copy-/removetree is used
        shutil.copytree(self.rk_tmp_dir, self.out_pt, dirs_exist_ok=True)

    def exit_app(self):
        self.log.info("Exiting RpaKit.")
        for i in range(3, -1, -1):
            print(f"{self.log.cm('bg_red')}{i}%{self.log.cm('reset')}", end='\r')
        sys.exit(0)

    def make_output(self):
        """
        Constructs outdir if it not already exists and with content is. Errors otherwise and
        exits.
        """
        self.out_pt = self.inp_pt / self.outdir

        if not self.overwrite and self.out_pt.exists() and not self.void_dir(self.out_pt):
            self.log.important(
                f"The intended output directory {self.out_pt}\n"
                "exists already and is not empty. Use option `--overwrite` or remove it "
                "and try again.")

            # self._dispose()
            self.exit_app()

        self.make_dirstruct(self.out_pt)

    def ident_paired_depot(self):
        """
        Identifies the RPA-1 type paired archive, which consisting of a rpa and rpi suffixed
        files with the same name.
        rpi: Have the index position data for the rpa stored
        rpa: Have the the file data stored

        This function removes the rpa from our list because it would error later. The index
        is read from the rpi and in the extraction func switched to the rpa suffix.
        """

        lst_copy = self.dep_lst[:]
        for entry in lst_copy:
            if entry.suffix == '.rpi':
                twin = str(entry.with_suffix('.rpa'))
                if twin in self.dep_lst:
                    self.dep_lst.remove(twin)
                    # NOTE: Now counted in main
                    # RkCommon.count['dep_found'] -= 1

    def traverse(self, inpath):
        """
        Filters from input path for rpa and returns them. Recurses into all given directorys
        by calling itself.
        """
        if inpath.is_file() and inpath.suffix in ['.rpa', '.rpi', '.rpc']:
            yield inpath
        elif inpath.is_dir():
            for item in inpath.iterdir():
                yield from self.traverse(item)

    def filter_raw_input(self):
        """Checks input and casts output to pathlike state."""

        str_inp = str(self.raw_inp)
        retval = [Path(elem).resolve(strict=True) for elem in glob.glob(str_inp)]
        if not retval:
            print(f"Input path not found: {self.raw_inp}")
        return retval

    def pathworker(self):
        """This prepairs the given path and output dir. It dicovers if the input
        is a file or directory and takes the according actions.
        """
        # FIXME: By mistake a restricted path was given and caused a PermissionError in
        # make_output. Needs to be handled or checked beforehand

        for globitem in self.filter_raw_input():
            for elem in self.traverse(globitem):
                self.dep_lst.append(elem)
                # RkCommon.count['dep_found'] += 1

            # TODO: Check if this needs to be here or maybe in init or ...?
            self.inp_pt = self.raw_inp.parent if self.raw_inp.is_file() else self.raw_inp

        self.ident_paired_depot()

        if self.task in ['extract', 'simulate']:
            self.rk_tmp_dir = Path(tempfile.mkdtemp(prefix='RpaKit.', suffix='.tmp'))
            self.make_output()

        return self.dep_lst, self.rk_tmp_dir, self.out_pt


class RkDepotWork(RkCommon):
    """
    The depot class for analyzing, testing and unpacking RPA files. Positional inputs are
    "depot", "task", "rk_tmp_dir" and "out_pt".

    """
    # IDEA: Alternate for rpaversion dicts; example:
    # rpaformats are simple functions of (archive) -> archivetype

    # rpaformats = []
    # def rpaformat(fnc):
    #     rpaformats.append(fnc)
    #     return fnc

    # @rpaformat
    # def rpa_v1(inp):
    #     """
    #     Format defintion for RPA1 format
    #     """

    # for extry in rpaformats:
    #     try:
    #         data = extry(inp)
    #     except ValueError:
    #         pass

    rpaformats = {
        'x': {
            'rpaid': 'rpa1',
            'desc': 'Legacy type RPA-1.0'
        },
        'RPA-2.0 ': {
            'rpaid': 'rpa2',
            'desc': 'Legacy type RPA-2.0'
        },
        'RPA-3.0 ': {
            'rpaid': 'rpa3',
            'desc': 'Standard type RPA-3.0'
        },
        # Header ID is the same as rpa3 but double keys are not allowed
        'RPA-3.0rk': {
            'rpaid': 'rpa3rk',
            'alias': 'RPA 3 rk',
            'desc': 'Custom type of RPA-3.0 with reversed key'
        },
        'RPI-3.0': {
            'rpaid': 'rpa32',
            'alias': 'rpi3',
            'desc': 'Custom type RPI-3.0'
        },
        'RPA-3.1': {
            'rpaid': 'rpa3',
            'alias': 'rpa31',
            'desc': 'Custom type RPA-3.1, a alias of RPA-3.0'
        },
        'RPA-3.2': {
            'rpaid': 'rpa32',
            'desc': 'Custom type RPA-3.2'
        },
        'RPA-4.0': {
            'rpaid': 'rpa3',
            'alias': 'rpa4',
            'desc': 'Custom type RPA-4.0, a alias of RPA-3.0'
        },
        'ALT-1.0': {
            'rpaid': 'alt1',
            'alias': 'ALT 1',
            'desc': 'Custom type ALT-1.0'
        },
        'ZiX-12A': {
            'rpaid': 'zix12a',
            'alias': 'ZIX 12a',
            'desc': 'Custom type ZiX-12A'
        },
        'ZiX-12B': {
            'rpaid': 'zix12b',
            'alias': 'ZIX 12b',
            'desc': 'Custom type ZiX-12B'
        }
    }

    rpaspecs = {
        'rpa1': {
            'offset': 0,
            'key': None
        },
        'rpa2': {
            'offset': slice(8, None),
            'key': None
        },
        'rpa3': {
            'offset': slice(8, 24),
            'key': slice(25, 33),
            'key_org': 1111638594,
            'key_rv': slice(None, None, -1)
        },
        'rpa32': {
            'offset': slice(8, 24),
            'key': slice(27, 35)
        },
        'alt1': {
            'offset': slice(17, 33),
            'key': slice(8, 16),
            'key2': 0xDABE8DF0
        }
    }

    log = None

    def __init__(self, task, depot, rk_tmp_dir, log_instance=None):
        super().__init__()
        self.task = task
        self.depot = depot
        self.rk_tmp_dir = rk_tmp_dir
        self.log = log_instance

        self.header = None
        self.version = {}
        self.reg = {}
        self.dep_initstate = None
        RkCommon.count['dep_id_found'] = 0  # IDEA: store instead of this ids?
        # RkCommon.count['dep_id_found'].clear()
        # self.dep_id_found = []

        self.init_depot()

    # FIXME: This method should be moot if instancing correctly works
    # def clear_rk_vars(self):
    #     """This clears some vars. In rare cases nothing is assigned and old values
    #     from previous depot run are caried over. Weird files will slip in and error.
    #     """
    #     self.header = None
    #     self.version.clear()
    #     self.reg.clear()
    #     self.dep_initstate = None
    #     RkCommon.count['dep_id_found'] = 0

    def extract_data(self, file_pt, pos_stats):
        """Extracts the archive data to a temporary file."""
        if self.depot.suffix == '.rpi':
            self.depot = self.depot.with_suffix('.rpa')

        with self.depot.open('rb') as of:
            if len(self.reg[file_pt]) == 1:
                offset, leg, prefix = pos_stats[0]
                of.seek(offset)
                tmp_file = prefix + of.read(leg - len(prefix))
            else:
                part = []
                for offset, leg, prefix in pos_stats:
                    of.seek(offset)
                    part.append(of.read(leg))
                    tmp_file = prefix.join(part)

        return tmp_file

    def unscrample_reg(self, key):
        """Unscrambles the archive register."""
        for kv in self.reg:
            self.reg[kv] = [(offset ^ key, leg ^ key, prefix)
                            for offset, leg, prefix in self.reg[kv]]

    def unify_reg(self):
        """
        Arranges the register data in common form so its easier to work with.
        There are two possible types in Ren'Py: Two value length for older and three for more
        recent engine versions. This method changes the two length variant to a length of three
        by adding a bytes prefix.
        """
        for val in self.reg.values():
            if len(val[0]) == 2:
                for num, _ in enumerate(val):
                    val[num] += (b'',)

    def get_cipher(self):
        """Fetches the cipher for the register from the header infos."""

        # NOTE: Slicing is error prone; perhaps use of "split parts" as a fallback
        # in the excepts is useful or even reverse the order of both
        offset, key = 0, None
        try:
            slos, slky = self.version['offset'], self.version['key']
            if self.version['rpaid'] != 'rpa1':
                offset = int(self.header[slos], 16)
            if self.version['rpaid'] != 'rpa2':
                key = int(self.header[slky], 16)

            if self.version['rpaid'] == 'rpa3' and key != self.version['key_org']:
                slky_b = self.version['key_rv']
                key = int(self.header[slky][slky_b], 16)
                self.version.update(self.rpaformats['RPA-3.0rk'])

        except (LookupError, ValueError) as err:
            print(sys.exc_info())
            raise (f"{err}: Problem with the format data encountered. Perhaps "
                   "the RPA is malformed.")
        except TypeError as err:
            raise (f"{err}: Somehow the wrong data types had a meeting in here. "
                   "They did'n like each other.")
        return offset, key

    def collect_register(self):
        """
        Collects the depot's register through use of unzip, followed by unpickling.
        Diverse extra steps for some depot formats are also managed from here.

        """

        # FIXME: make offset and key vars class wide; move this line somewhere else?
        offset, key = self.get_cipher()
        with self.depot.open('rb') as of:
            of.seek(offset)
            self.reg = pickle.loads(zlib.decompress(of.read()), encoding='bytes')

        self.unify_reg()
        if key is not None:
            if 'key2' in self.version.keys():
                key = key ^ self.version['key2']
            self.unscrample_reg(key)

    def get_version_specs(self):
        """Yields for the given archive version the cipher data."""
        try:
            for key, val in self.rpaspecs.items():
                if key == self.version['rpaid']:
                    self.version.update(val)
                    break
        except KeyError:
            raise f"Error while aquiring version specifications for {self.depot}."

    def get_header_start(self):
        """
        Reads the file header in and trys to produce a decoded string which we
        are able to match against the available format ID's.
        Catching the error as first indictor for RPA 1 is actually the easiest way
        because RPA 2/3 and the known custom formats passed this so far.
        """
        try:
            magic = self.header.decode()
        except UnicodeDecodeError:
            # Lets try this: rpa2/3 and custom headers are at 34/36 length
            # if len(self.header) not in (34, 36) and self.header.startswith(b"x"):
            #     magic = self.header[:1].decode()
            # alternate: Coding should be cp1252 and zlib compression default (\x9c)
            if len(self.header) not in (34, 36) and self.header.startswith(b"\x78\x9c"):
                magic = self.header[:2].decode('cp1252')
                self.log.warning("UnicodeDecodeError: Found possibly old RPA-1 format.")
            else:
                magic = str()
        return magic

    def guess_version(self):
        """
        Determines probable archive version from header/suffix and pairs fitting alias
        variants with a main format-ID.
        """
        magic = self.get_header_start()
        try:
            for key, val in self.rpaformats.items():
                if key in magic:
                    self.version.update(val)
                    RkCommon.count['dep_id_found'] += 1
                    # RkCommon.count['dep_id_found'].append(val)
                    # self.dep_id_found.append(val)

            # NOTE:If no version is found the dict is empty; searching with a key slice
            # for 'rpaid' excepts a KeyError (better init dict with key?)
            if 'rpa1' in self.version.values() and self.depot.suffix != '.rpi':
                self.version.clear()
            elif not self.version:
                raise NoRpaOrUnknownWarning(self.depot, self.header)
            # elif len(self.dep_id_found) > 1:
            elif RkCommon.count['dep_id_found'] > 1:
                raise AmbiguousHeaderError(self.version)
            elif 'zix12a' in self.version.values() or 'zix12b' in self.version.values():
                raise NotImplementedError(
                    self.log.warning(f"{self.depot!r} is a unsupported format.\nFound "
                                     f"archive header: > {self._header}"))

        except (NoRpaOrUnknownWarning, NotImplementedError):
            self.dep_initstate = False
        except LookupError as err:
            raise self.log.error(f"{err} A unknown problem with the archives format "
                                 "ID occured. Unable to continue.")
        else:
            self.dep_initstate = True
            self.log.info(f"Found archive format: {self.version['desc']}")

    def get_header(self):
        """Opens file and reads header line in."""
        with self.depot.open('rb') as of:
            of.seek(0)
            self.header = of.readline()

    def check_out_pt(self, f_pt):
        """
        Checks if output path legit is and if needed renames it. This can happen if objects
        in the archive are manipulated or broken. e.g. weird encoding, fradulent file type
        """
        tmp_pt = self.rk_tmp_dir / f_pt
        if tmp_pt.is_dir() or f_pt == "":
            rand_fn = '0_' + urandom(2).hex() + '.BAD'
            tmp_pt = self.rk_tmp_dir / rand_fn
            self.log.warning("Possible invalid archive! A filename was replaced with"
                             f"the new name '{rand_fn}'.")
        return tmp_pt

    def unpack_depot(self):
        """Manages the unpacking/simulation of the found depot files."""
        for file_num, (file_pt, pos_stats) in enumerate(self.reg.items()):
            try:
                tmp_path = self.check_out_pt(file_pt)
                self.make_dirstruct(tmp_path.parent)

                tmp_file_data = self.extract_data(file_pt, pos_stats)
                report = self.pm(file_num, RkCommon.count['files_total'], file_pt, 'bg_yellow')
                self.log.info(f"{report}")

                with tmp_path.open('wb') as of:
                    of.write(tmp_file_data)
            except TypeError as err:
                raise f"{err}: Unknown error while trying to extract a file."

        if self.void_dir(self.rk_tmp_dir):
            self.log.warning("No files from archive unpacked.")
        else:
            self.log.important(f"Unpacked {RkCommon.count['files_total']} files from archive: "
                               f"{self.depot!s}")

    def list_depot_content(self):
        """Lists the file content of a renpy archive without unpacking."""
        # IDEA: list to target of user choice
        # outp_dst = sys.stdout if "bla" else file
        print("Listing archive files:")
        print(f"Depot {RkCommon.count['dep_done'] + 1}: {self.depot.name}")
        for num, (fln, flidx) in enumerate(sorted(self.reg.items())):
            print(f"{' ' * 2}File {num}: {fln}\n{' ' * 4}Index data: {flidx}")

        self.log.important(f"Archive {self.depot.name!s} contains {len(self.reg.keys())} files.")

    def test_depot(self):
        """Tests archives for their format type and outputs this."""
        print(f"For archive > {self.depot.name} the identified version variant is: "
              f"{self.log.cm('bg_blue')}{self.version['desc']!r}{self.log.cm('reset')}")

    def work_depot(self):
        """Manages the different tasks for the given archives and their content."""
        if self.task in ['extract', 'simulate']:
            self.unpack_depot()
        elif self.task == 'list':
            self.list_depot_content()
        elif self.task == 'test':
            self.test_depot()
        else:
            raise ValueError(f"Unknown task request: {self.task!r}; Choose either: extract, list, "
                             "simulate, test")

    def init_depot(self):
        """Initializes and analyzes depot files to a ready state for further operations."""
        try:
            self.get_header()
            self.guess_version()

            if self.dep_initstate is False:
                self.log.warning(f"Skipping bogus archive: {self.depot!s}")
            elif self.dep_initstate is True:
                self.get_version_specs()
                self.collect_register()
                self.reg = {str(file_pt): pos_data for file_pt, pos_data in self.reg.items()}
                RkCommon.count['files_total'] = len(self.reg)

            if 'alias' in self.version.keys():
                self.log.important(
                    f"Unofficial RPA found. Variant name is '{self.version['alias']}'")
            else:
                self.log.info("Official RPA found.")

        except OSError as err:
            raise RpaKitError(f"{err}: Error while opening archive file "
                              f">{self.depot}< for initialization.")


def parse_args():
    """Argument parser to provide functionality for the command-line interface."""

    epi = "Default output dir is set to `{Target}/rpakit_out/`. Change with option -o."
    ap = argparse.ArgumentParser(
        description="Program for searching and unpacking RPA files.",
        epilog=epi,
        formatter_class=lambda prog: argparse.HelpFormatter(prog, max_help_position=30, width=100))

    ap.add_argument(
        'inpath',
        metavar='Target',
        action='store',
        type=str,
        help='Directory path (to search) OR rpa file path to unpack.')

    opts = ap.add_argument_group("Tasks")
    tasks = opts.add_mutually_exclusive_group(required=True)
    tasks.add_argument(
        '-e',
        '--extract',
        dest='task',
        action='store_const',
        const='extract',
        help='Extracts all stored files and dirs.')

    tasks.add_argument(
        '-l',
        '--list',
        dest='task',
        action='store_const',
        const='list',
        help='Prints a listing of all stored files.')

    tasks.add_argument(
        '-t',
        '--test',
        dest='task',
        action='store_const',
        const='test',
        help='Tests if archive(s) are a known format.')

    tasks.add_argument(
        '-s',
        '--simulate',
        dest='task',
        action='store_const',
        const='simulate',
        help='Unpacks all stored files just temporary.')

    ap.add_argument(
        '-o',
        '--outdir',
        action='store',
        type=str,
        help='Extracts to the given path instead to the default destination.')

    ap.add_argument(
        '--overwrite',
        action='store_true',
        help='Overwrites outdir and any content if they already exist.')

    ap.add_argument(
        '--no_log',
        action='store_false',
        help='Deactivates the use of a logfile in the script path')

    ap.add_argument(
        '--loglevel',
        type=str,
        default='IMPORTANT',
        choices=['DEBUG', 'INFO', 'IMPORTANT', 'WARNING', 'ERROR', 'CRITICAL'],
        help='Set minimum log-level for the console; Default is "important"; Use "warning" '
        'or higher to reduce output')

    ap.add_argument(
        '--version',
        action='version',
        version=f"{__title__} {__version__}")

    args = ap.parse_args()
    return args


def main():
    """
    This checks if the minimum required Python version runs, instantiates the class,
    delivers the parameters to its init and executes the program from CLI.
    """
    if not sys.version_info[:2] >= (3, 9):
        raise RuntimeError("Must be executed in Python 3.9 or later.\n"
                           f"You are running {sys.version}")
    cfg = parse_args()
    # TODO: Move Path casting and checks in classes
    pathlike_inp = Path(cfg.inpath)

    try:
        rkl = RpaKitLog('RK', logfile=cfg.no_log, loglevel=cfg.loglevel.upper())
    except Exception:
        raise RpaKitError("Logging initialization failed!", traceback.format_exc())

    # begin msg
    if pathlike_inp.is_file():
        rkl.info(f"Input is a file. Processing {cfg.inpath}.")
    elif pathlike_inp.is_dir():
        rkl.info(f"Input is a directory. Searching recursively for RPA in {cfg.inpath}.")
    else:
        rkl.error(f"Could not identify input: {cfg.inpath} Check and retry.")
        # FIXME: We need to exit here

    rkp = RkPathWork(pathlike_inp, cfg.task, outdir=cfg.outdir, overwrite=cfg.overwrite,
                     log_instance=rkl)
    if cfg.task in ['extract', 'simulate']:
        atexit.register(rkp._dispose)
    dep_lst, rk_tmp_dir, out_pt = rkp.pathworker()
    # FIXME: Should this be here? @end of pathworker
    RkCommon.count['dep_found'] = len(dep_lst)

    if RkCommon.count['dep_found'] > 0:
        rkl.important(f"Found {RkCommon.count['dep_found']} RPA files to process:\n"
                      f"{chr(10).join([*map(str, dep_lst)])}")
    else:
        rkl.warning("No RPA files found. Was the correct path given?")

    while dep_lst:
        depot = dep_lst.pop()

        rkd = RkDepotWork(cfg.task, depot, rk_tmp_dir, log_instance=rkl)

        # if something wrong with initializing dep
        if rkd.dep_initstate is False:
            continue
        # TODO: Tell about this

        rkd.work_depot()
        RkCommon.count['dep_done'] += 1

        report = rkd.pm(RkCommon.count['dep_done'], RkCommon.count['dep_found'], depot)
        rkl.important(f"{report}")

    if cfg.task in ['extract', 'simulate']:
        if cfg.task == 'extract':
            # FIXME: These both have perhaps no buissiness here. @class somewhere
            rkp.mv_tmp2outdir()
        # rkp._dispose()

        # done msg
        if RkCommon.count["dep_done"] > 0:
            if cfg.task == 'extract':
                rkl.important(f" Completed. We unpacked {RkCommon.count['dep_done']} archive(s).")
            else:
                rkl.important(
                    f"We simulated the unpacking of {RkCommon.count['dep_done']} "
                    "archive(s).")
        else:
            rkl.warning("Oops! No archives where processed...")

    elif cfg.task in ['listing', 'test']:
        rkl.info("Task completed.")

if __name__ == '__main__':
    main()
