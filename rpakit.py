#!/usr/bin/env python3

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


RPAKit is a small app for the work with Ren'Py Archives(RPA).
As input it takes single or multiple path or file objects, which will then be filtered for legal
Ren'Py archives. These will then decompressed and the content written in a custom-made subdirectory.
Just listing the archive files without writing or testing & identifying the archiv or
simulating the extraction process is also possible.
"""

# FIXME: Big projects may fail with "OSError: [Errno 28] No space left on device" Find a way to
# prevent this. (possible a big task)
# 1. Maybe rework tmpdir:unpack-move-delete process into smaller steps (10GiB each?)
# 2. Use more as one depot list with limited size (5GiB?)
# 3. Measure size of std temp and depotlist and if the size of the latter too big is then change
#    the tmpdir location(with the dir parameter of tempfile)
# 4. Add a warning if the archives size is higher as x % of the size limit of the OS tmpdir
# 5. Add a option to create the tempdir alongside the outdir
# options 1,2 are complicated, 4 seems short term usable, 5 seems a good long term option

# TODO: Overall tasks:
# - Kill simulation option! Nobody uses it.
# - Add option to move rpa after unpacking to a backup dir
# - Test atexit; remove remaining outcommented code
# - Add functionality to force rpa format version from user input
# - Rework the order of tasks into clearer steps e.g. prepare -> get depot list -> work depots
# - Fix the modules codetag tasks

__title__ = "RPA Kit"
__license__ = "Apache 2.0"
__author__ = "madeddy"
__status__ = "Development"
__version__ = "0.52.0-alpha"
__url__ = "https://github.com/madeddy/RpaKit"

import argparse
import atexit
import glob
import logging
import pickle
import re
import shutil
import sys
import tempfile
import traceback
import zlib
from copy import copy
from logging.handlers import TimedRotatingFileHandler
from os import urandom
from pathlib import Path


class RpaKitError(Exception):
    """Base class for exceptions in RpaKit."""

    def __init__(self, msg):
        self.msg = msg

    def __str__(self):
        return f"{RpaKitLog.cm('red')}{repr(self.msg)}{RpaKitLog.cm('reset')}"


class AmbiguousHeaderError(RpaKitError):
    """Exception raised if for a archiv more as one format dedected was.

    Parameter:
        vers -- version dict in which the error occurred
        message -- explanation of the error
    """

    def __init__(self, dep, ver):
        self.dep = dep
        self.ver = [v for k, v in ver.items() if "rpaid" in k]
        super().__init__(
            "Detection of the archive format failed, because multiple matches where found.\n"
            f"Archive: {self.dep} with Version > {self.ver}"
        )
        # NOTE: When the option to force the RPA version implemented is, we need to add another
        # line with info about this


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
            f"Archive: {self.dep} with header: > {self._header}"
        )


class BaseFormatter(logging.Formatter):
    """
    A very basic formatter for logfile output, which uses a different format for always emitted
    messages of the custom SESSION level. This class also removes also unwanted ANSI escape
    sequences from the log record, so it does not pollute the logfile with them.
    """

    ansi_remove = re.compile(r'\x1B(?:[@-Z\\-_]|\[[0-?]*[ -/]*[@-~])')

    def __init__(self, fmt, fmt_session, datefmt=None, style='{'):
        super().__init__(datefmt=datefmt, style=style)
        self.session_fmt = logging.Formatter(fmt_session, datefmt, style)
        self.default_fmt = logging.Formatter(fmt, datefmt, style)

    def format(self, record):
        # Removes ansi escape sequences from the logfile output from the percentmeter
        record.msg = self.ansi_remove.sub("", str(record.msg))

        if record.levelno == 60:
            return self.session_fmt.format(record)
        return self.default_fmt.format(record)


class ColorFormatter(logging.Formatter):
    """
    A formatter that colors some elements like the level names of log records. This class is the
    standard formatter for the console handler and falls back to the default formatter, if
    tty colors are not supported.

    Overrides the format method and uses a record copy to avoid altering the original, or
    other handlers emit ANSI escape sequences.
    """

    reset = "\x1b[0m"  # reset
    level_map = {
        "DEBUG": "\x1b[1;37m",  # bold, grey
        "INFO": "\x1b[32m",  # green
        "IMPORTANT": "\x1b[94m",  # light blue
        "WARNING": "\x1b[33m",  # yellow
        "ERROR": "\x1b[1;35m",  # bold, red
        "CRITICAL": "\x1b[30;41m",  # black, red bg
    }
    ansi_escape = re.compile(r'(\x9b|\x1b\[)[0-?]*[ -\/]*[@-~]')

    def format(self, record):
        record_copy = copy(record)

        if record.levelno == 60:
            # For session msg return immediately and bypass all other logic below.
            session_fmt = logging.Formatter("[{name}] {message}", style='{')
            return session_fmt.format(record)

        # Get the ANSI sequence and apply it to the levelname
        ansi_seq = self.level_map.get(record_copy.levelname, "\x1b[1;37m")
        new_levelname = f"[{ansi_seq}{record_copy.levelname}{self.reset}]"

        # Calc the length of the raw levelname and padding
        visible_len = len(self.ansi_escape.sub("", f"[{record_copy.levelname}]"))
        padding = len(new_levelname) + 11 - visible_len

        # Add the padding to the end of the colored, bracketed levelname
        record_copy.levelname = f"{new_levelname:<{padding}}"
        return super().format(record_copy)


class RpaKitLog(logging.Logger):
    """
    This class configures and initiates all logging functionality for the module.

    Contains a `colorname-to-ANSI` mapping dict which yields escape sequences for colored
    output.
    It adds a streamhandler for console output, including colored output, and a filehandler
    which writes to a logfile. The latter can be disabled by CLI.

      Parameters
      ----------
      name : `str`
          The name of the logger
      logfile : `bool`, optional
          If a logfile is created, by default True
      loglevel : `str`, optional
          The loglevel to use, by default "INFO"
    """

    ansi_colormap = {
        "reset": "\x1b[0m",
        "bold": "\x1b[1m",
        "uline": "\x1b[4m",  # underline
        "blink": "\x1b[5m",  # blinking
        "reverse": "\x1b[7m",  # fg <-> bg
        "black": "\x1b[30m",
        "red": "\x1b[31m",
        "green": "\x1b[32m",
        "yellow": "\x1b[33m",
        "blue": "\x1b[34m",
        "magenta": "\x1b[35m",
        "cyan": "\x1b[36m",
        "lyellow": "\x1b[93m",  # light yellow
        "lblue": "\x1b[94m",  # light blue
        "bg_b_yellow": "\x1b[103;30m",  # bg = background
        "bg_blue": "\x1b[44;30m",
        "bg_magenta": "\x1b[45;30m",
        "bg_white": "\x1b[47;30m",
        "erase": "\x1b[1A\x1b[2K\x1b[1A",  # erase last line; don't write after this log entry
        "return": "\x1b[10D\x1b[1A\x1b[K",  # write on same line: (xD=x rows left, xA=x lines up,
        # K=erase line)
    }

    def __init__(self, name, logfile=True, loglevel="IMPORTANT"):
        super().__init__(name)
        self.loglevel = loglevel
        self.tty_colors = True
        self.oldwin_tty_colors()
        logging.addLevelName(25, "IMPORTANT")
        logging.Logger.important = self.important
        logging.addLevelName(60, "SESSION")
        logging.Logger.important = self.session

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
        if sys.platform.startswith("win32") and sys.getwindowsversion()[2] < 16257:
            try:
                from ctypes import windll
                h = windll.kernel32
                h.SetConsoleMode(h.GetStdHandle(-11), 7)
            except Exception:
                print(
                    "Enabling TTY colors failed. This is not a critical error, but the "
                    "terminal output will be colorless."
                )
                self.tty_colors = False

            # NOTE: os.system("") allegedly could enable ANSI colors in Win cmd and py2.7. Not
            # useful this days for win7/8 etc.

            RpaKitLog.ansi_colormap.update(
                (k, "") for k in self.ansi_colormap if not self.tty_colors
            )

    def important(self, msg, *args, **kwargs):
        """
        Adds a custom logging level `IMPORTANT` with severity level 25, between
        info(20) and warning(30).
        """
        if self.isEnabledFor(25):
            self._log(25, msg, args, **kwargs)

    def session(self, msg, *args, **kwargs):
        """
        Adds a custom logging level `SESSION` with severity level 60, which is intended to
        write always.
        """
        if self.isEnabledFor(60):
            self._log(60, msg, args, **kwargs)

    def init_streamhandler(self):
        """
        Sets up the basic console handler configuration.
        Adds the console handler always and use custom formatter if tty-colors are available.
        """
        fmt_cls = ColorFormatter if self.tty_colors else BaseFormatter
        fmt_default = "[{name}]{levelname} >> {message}"
        fmt_session = "[{name}] {message}"

        ch = logging.StreamHandler()
        ch.setLevel(self.loglevel)
        ch.setFormatter(fmt_cls(fmt_default, fmt_session, style='{'))
        self.addHandler(ch)

    def init_filehandler(self):
        """
        Sets up the file logger configuration.
        If not disabled in CLI, a logfile in the script path and a file handler is added.
        """
        log_name = "rpakit.log"
        log_path = Path(__file__).parent.resolve().joinpath(log_name)
        fmt_default = "{asctime} {levelname:<9} - {filename}:{lineno:d} - {message}"
        fmt_session = "{asctime} {message}"

        fh = TimedRotatingFileHandler(log_path, when='midnight', backupCount=10)
        fh.suffix = '%d.%b%Y'
        fh.setLevel("DEBUG")
        fh.setFormatter(
            BaseFormatter(fmt_default, fmt_session, datefmt='%d.%b%Y %H:%M:%S', style='{')
        )
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
    count = {
        "dep_found": 0,
        "dep_done": 0,
        "files_total": 0,
        "dep_id_found": 0
        }  # fmt: skip

    def pm(self, fraction, total, object, bg_color=None):
        """Returns a fraction-meter like output for use in tty."""
        color = bg_color or "bg_blue"
        return (
            f"[{self.log.cm(color)}{fraction:{len(str(total))}>n}/{total:>n}"
            f"{self.log.cm('reset')}] {object!s:>4}"
        )

    @staticmethod
    def void_dir(dst):
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

    Parameters
    ----------
    raw_inp : `Path`
        The input path to work with.
    task : `str`
        The task to be performed.
    outdir : `Path`, optional
        The output directory, by default "rpakit_out"
    overwrite : `bool`, optional
        If True, overwrites already existing output files, by default False
    log_instance : `RpaKitLog`, optional
        The logger instance, by default None
    """

    log = None
    outdir = "rpakit_out"
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
        # FIXME: move() errors if a src dir exists in dst if --overwrite option is used

        # for entry in self.rk_tmp_dir.iterdir():
        #     shutil.move(entry, self.out_pt)

        #  as a workaround the manual way with copy-/removetree must be used
        shutil.copytree(self.rk_tmp_dir, self.out_pt, dirs_exist_ok=True)

    def exit_app(self, exitcode=0):
        """Exits the app with given exitcode."""
        if not exitcode:
            self.log.info("RpaKit exited successfully.")
        else:
            self.log.error("RpaKit terminated because of an error.")
        for i in range(3, -1, -1):
            print(f"{self.log.cm('bg_magenta')}{i}%{self.log.cm('reset')}", end='\r')
        sys.exit(exitcode)

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
                "and try again."
            )

            # self._dispose()
            # FIXME: In library usage this must be prevented to execute or it ends also the
            # parent app
            self.exit_app(17)

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
            if entry.suffix == ".rpi":
                twin = str(entry.with_suffix(".rpa"))
                if twin in self.dep_lst:
                    self.dep_lst.remove(twin)
                    # TODO: Check if this really a rpa v1 is and not some custom called rpi
                    # If positive we can count it as a v1 depot
                    # NOTE: Now counted in main

    def traverse(self, inpath):
        """
        Filters from input path for rpa and returns them. Recurses into all given directorys
        by calling itself.
        """
        if inpath.is_file() and inpath.suffix in [".rpa", ".rpi", ".rpc"]:
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
        """
        This prepairs the given path and output dir. It dicovers if the input is a file or
        directory and takes the according actions.
        """
        # FIXME: By mistake a restricted path was given and caused a PermissionError in
        # make_output. Needs to be handled or checked beforehand

        for globitem in self.filter_raw_input():
            for elem in self.traverse(globitem):
                self.dep_lst.append(elem)

            # TODO: Check if this needs to be here or maybe in init or ...?
            self.inp_pt = self.raw_inp.parent if self.raw_inp.is_file() else self.raw_inp

        self.ident_paired_depot()

        # TODO: This is a preparation step and should be moved to start tasksinit, or maybe
        # somewhere else?
        if self.task in ["extract", "simulate"]:
            self.rk_tmp_dir = Path(tempfile.mkdtemp(prefix="RpaKit.", suffix=".tmp"))
            self.make_output()

        return self.dep_lst, self.rk_tmp_dir, self.out_pt


class RkDepotWork(RkCommon):
    """
    The depot class for analyzing, testing and unpacking RPA files.

    Parameters
    ----------
    task : str
        The task to be performed. Options: `extract`, `simulate`, `list`, `test`
    depot : Path
        The depot to be worked on
    rk_tmp_dir : Path
        The temporary directory for storing intermediate files
    log_instance : `RpaKitLog`, optional
        The logger instance, by default None
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
        "x": {
            "rpaid": "rpa1",
            "desc": "Legacy type RPA-1.0"
        },
        "RPA-2.0 ": {
            "rpaid": "rpa2",
            "desc": "Legacy type RPA-2.0"
        },
        "RPA-3.0 ": {
            "rpaid": "rpa3",
            "desc": "Standard type RPA-3.0"
        },
        # Header ID is the same as rpa3 but double keys are not allowed
        "RPA-3.0rk": {
            "rpaid": "rpa3rk",
            "alias": "RPA 3 rk",
            "desc": "Custom type of RPA-3.0 with reversed key"
        },
        "RPI-3.0": {
            "rpaid": "rpa32",
            "alias": "rpi3",
            "desc": "Custom type RPI-3.0"
        },
        "RPA-3.1": {
            "rpaid": "rpa3",
            "alias": "rpa31",
            "desc": "Custom type RPA-3.1, a alias of RPA-3.0"
        },
        "RPA-3.2": {
            "rpaid": "rpa32",
            "desc": "Custom type RPA-3.2"
        },
        "RPA-4.0": {
            "rpaid": "rpa3",
            "alias": "rpa4",
            "desc": "Custom type RPA-4.0, a alias of RPA-3.0"
        },
        "ALT-1.0": {
            "rpaid": "alt1",
            "alias": "ALT 1",
            "desc": "Custom type ALT-1.0"
        },
        "ZiX-12A": {
            "rpaid": "zix12a",
            "alias": "ZIX 12a",
            "desc": "Custom type ZiX-12A"
        },
        "ZiX-12B": {
            "rpaid": "zix12b",
            "alias": "ZIX 12b",
            "desc": "Custom type ZiX-12B"
        }
    }  # fmt: skip

    # TODO: Unify rpaformats and rpaspecs: WIP

    rpaspecs = {
        "rpa1": {
            "offset": 0,
            "key": None
        },
        "rpa2": {
            "offset": slice(8, None),
            "key": None
        },
        "rpa3": {
            "offset": slice(8, 24),
            "key": slice(25, 33),
            "key_org": 1111638594,
            "key_rv": slice(None, None, -1)
        },
        "rpa32": {
            "offset": slice(8, 24),
            "key": slice(27, 35)
        },
        "alt1": {
            "offset": slice(17, 33),
            "key": slice(8, 16),
            "key2": 0xDABE8DF0
        }
    }  # fmt: skip

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
        RkCommon.count["dep_id_found"] = 0  # IDEA: Should we store instead RPA IDs?
        self.init_depot()

    # TODO: Move this down above the calls to it
    def extract_data(self, file_pt, pos_stats):
        """Extracts the archive data to a temporary file."""
        if self.depot.suffix == ".rpi":
            self.depot = self.depot.with_suffix(".rpa")

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
            self.reg[kv] = [
                (offset ^ key, leg ^ key, prefix) for offset, leg, prefix in self.reg[kv]
            ]

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
        # IDEA: Maybe a better name e.g. get_rpa_specs
        """Fetches the cipher for the register from the header infos."""

        # NOTE: Slicing is error prone; perhaps use of "split parts" as a fallback
        # in the excepts is useful or even reverse the order of both
        offset, key = 0, None
        try:
            slos, slky = self.version["offset"], self.version["key"]
            if self.version["rpaid"] != "rpa1":
                offset = int(self.header[slos], 16)

            if self.version["rpaid"] != "rpa2":
                key = int(self.header[slky], 16)

            if self.version["rpaid"] == "rpa3" and key != self.version["key_org"]:
                slky_b = self.version["key_rv"]
                key = int(self.header[slky][slky_b], 16)
                self.version.update(self.rpaformats["RPA-3.0rk"])

        except (LookupError, ValueError) as err:
            print(sys.exc_info())
            raise (
                f"{err}: Problem with the format data encountered. Perhaps the RPA is malformed."
            )
        except TypeError as err:
            raise (
                f"{err}: A wrong data type was encountered in the RPA header. This is a rather "
                "peculiar case."
            )
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
            if "key2" in self.version.keys():
                key = key ^ self.version["key2"]
            self.unscrample_reg(key)

    def get_version_specs(self):
        """Yields for the given archive version the cipher data."""
        try:
            for key, val in self.rpaspecs.items():
                if key == self.version["rpaid"]:
                    self.version.update(val)
                    break
        except KeyError:
            raise f"Error while aquiring version specifications for {self.depot}."

    def get_header_start(self):
        # NOTE: Maybe a better name e.g. get_rpa_header
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
        # NOTE: Maybe a better name e.g. guess_rpa_version
        """
        Determines probable archive version from header/suffix and pairs fitting alias
        variants with a main format-ID.
        """
        magic = self.get_header_start()
        try:
            for key, val in self.rpaformats.items():
                if key in magic:
                    self.version.update(val)
                    RkCommon.count["dep_id_found"] += 1

            # NOTE:If no version is found the dict is empty; searching with a key slice
            # for "rpaid" excepts a KeyError (better init dict with key?)
            if "rpa1" in self.version.values() and self.depot.suffix != ".rpi":
                self.version.clear()
            elif not self.version:
                raise NoRpaOrUnknownWarning(self.depot, self.header)
            elif RkCommon.count["dep_id_found"] > 1:
                raise AmbiguousHeaderError(self.version)
            elif "zix12a" in self.version.values() or "zix12b" in self.version.values():
                raise NotImplementedError(
                    self.log.warning(
                        f"{self.depot!r} is a unsupported format.\nFound "
                        f"archive header: > {self._header}"
                    )
                )

        except (NoRpaOrUnknownWarning, NotImplementedError):
            self.dep_initstate = False
        except LookupError as err:
            raise self.log.error(
                f"{err} A unknown problem with the archives format ID occured. Unable to continue."
            )
        else:
            self.dep_initstate = True
            self.log.info(f"Found archive format: {self.version['desc']}")

    def get_header(self):
        # IDEA: Unify with get_header_start
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
            rand_fn = "0_" + urandom(2).hex() + ".BAD"
            tmp_pt = self.rk_tmp_dir / rand_fn
            self.log.warning(
                f"Possible invalid archive! A filename was replaced withthe new name '{rand_fn}'."
            )
        return tmp_pt

    def unpack_depot(self):
        """Manages the unpacking/simulation of the found depot files."""
        for file_num, (file_pt, pos_stats) in enumerate(self.reg.items()):
            try:
                tmp_path = self.check_out_pt(file_pt)
                self.make_dirstruct(tmp_path.parent)

                tmp_file_data = self.extract_data(file_pt, pos_stats)
                report = self.pm(file_num, RkCommon.count["files_total"], file_pt, "bg_b_yellow")
                self.log.info(f"{report}")

                with tmp_path.open('wb') as of:
                    of.write(tmp_file_data)
            except TypeError as err:
                raise f"{err}: Unknown error while trying to extract a file."

        if self.void_dir(self.rk_tmp_dir):
            self.log.warning("No files from archive unpacked.")
        else:
            self.log.important(
                f"Unpacked {RkCommon.count['files_total']} files from archive: {self.depot!s}"
            )

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
        print(
            f"For archive > {self.depot.name} the identified version variant is: "
            f"{self.log.cm('bg_blue')}{self.version['desc']!r}{self.log.cm('reset')}"
        )

    def work_depot(self):
        """
        Works on the depot files according to the task specified. The task parameter must
        be a allowed value or it raises a ValueError.
        """

        if self.task in ["extract", "simulate"]:
            self.unpack_depot()
        elif self.task == "list":
            self.list_depot_content()
        elif self.task == "test":
            self.test_depot()
        else:
            raise ValueError(
                f"Unknown task requested: {self.task!r}; Choose either: extract, list, "
                "simulate, test"
            )

    # TODO: Move this above check_out_pt
    def init_depot(self):
        """
        Initializes a depot to a ready state for further operations. This is done by analyzing
        the header, finding the version, collecting register information and updating the
        global counters.
        """
        try:
            self.get_header()
            self.guess_version()

            if self.dep_initstate is False:
                self.log.warning(f"Skipping bogus archive: {self.depot!s}")
            elif self.dep_initstate is True:
                self.get_version_specs()
                self.collect_register()
                self.reg = {str(file_pt): pos_data for file_pt, pos_data in self.reg.items()}
                RkCommon.count["files_total"] = len(self.reg)

            if "alias" in self.version.keys():
                self.log.important(
                    f"Unofficial RPA found. Variant name is '{self.version['alias']}'"
                )
            else:
                self.log.info("Official RPA found.")

        except OSError as err:
            raise RpaKitError(
                f"{err}: Error while working on archive file >{self.depot}< for initialization."
            )


def parse_args():
    """Argument parser to provide functionality for the command-line interface."""

    ap = argparse.ArgumentParser(
        description="A application for searching and unpacking RPA files.",
        epilog="Default output dir is set to `{Target}/rpakit_out/`. Change with option -o.",
        formatter_class=lambda prog: argparse.HelpFormatter(prog, max_help_position=30, width=100),
    )

    ap.add_argument(
        "inpath",
        metavar="Target",
        action="store",
        type=str,
        help="Directory path (to search) OR rpa file path to unpack.",
    )

    opts = ap.add_argument_group("Tasks")
    tasks = opts.add_mutually_exclusive_group(required=True)
    tasks.add_argument(
        "-e",
        "--extract",
        dest="task",
        action="store_const",
        const="extract",
        help="Extracts all stored files and dirs from the RPA.",
    )

    tasks.add_argument(
        "-l",
        "--list",
        dest="task",
        action="store_const",
        const="list",
        help="Prints a listing of all stored files.",
    )

    tasks.add_argument(
        "-t",
        "--test",
        dest="task",
        action="store_const",
        const="test",
        help="Verifies if archive(s) are a known RPA format.",
    )

    tasks.add_argument(
        "-s",
        "--simulate",
        dest="task",
        action="store_const",
        const="simulate",
        help="Unpacks all stored files just temporary.",
    )

    ap.add_argument(
        "-o",
        "--outdir",
        action="store",
        type=str,
        help="Extracts to the specified path instead of the default destination.",
    )

    ap.add_argument(
        "--overwrite",
        action="store_true",
        help="Overwrites outdir and any content if they already exist.",
    )

    ap.add_argument(
        "--no_log",
        action="store_false",
        help="Deactivates the use of a logfile written to the script path.",
    )

    ap.add_argument(
        "--loglevel",
        type=str.upper,
        default="IMPORTANT",
        choices=["DEBUG", "INFO", "IMPORTANT", "WARNING", "ERROR", "CRITICAL"],
        help="Set minimum log-level for the console. Default is `important`; Use `warning` "
             "or higher to reduce output",
    )

    ap.add_argument(
        "--version",
        action="version",
        version=f"{__title__} {__version__}"
    )

    return ap.parse_args()


def main(cfg=None):  # noqa: C901
    """
    This checks if the minimum required Python version runs, instantiates the classes,
    delivers the parameters to their init and executes the program flow.
    """
    if not sys.version_info[:2] >= (3, 9):
        raise RuntimeError(
            f"Must be executed in Python 3.9 or later.\nYou are running {sys.version}"
        )
    if not cfg:
        print("No configuration found, but is required. Termminating.")
        RkPathWork.exit_app(1)

    # Preperations #
    # TODO: Move Path casting and checks in classes
    pathlike_inp = Path(cfg.inpath)

    try:
        rklog = RpaKitLog("RK", logfile=cfg.no_log, loglevel=cfg.loglevel.upper())
    except Exception:
        raise RpaKitError(f"Logging initialization failed! {traceback.format_exc()}")

    # begin msg
    if pathlike_inp.is_file():
        rklog.info(f"Input is a file. Processing {cfg.inpath}.")
    elif pathlike_inp.is_dir():
        rklog.info(f"Input is a directory. Searching recursively for RPA in {cfg.inpath}.")
    else:
        rklog.error(f"Could not identify input: {cfg.inpath} Check and retry.")
        # FIXME: We need to exit here
        RkPathWork.exit_app(2)  # TODO: better(?) raise OSError(os.strerror(2))

    # Path stuff #
    rkp = RkPathWork(
        pathlike_inp, cfg.task, outdir=cfg.outdir, overwrite=cfg.overwrite, log_instance=rklog
    )
    if cfg.task in ["extract", "simulate"]:
        atexit.register(rkp._dispose)
    dep_lst, rk_tmp_dir, out_pt = rkp.pathworker()
    # FIXME: Should this be here? @end of pathworker
    RkCommon.count["dep_found"] = len(dep_lst)

    if RkCommon.count["dep_found"] > 0:
        rklog.important(
            f"Found {RkCommon.count['dep_found']} RPA files to process:\n"
            f"{chr(10).join([*map(str, dep_lst)])}"
        )
    else:
        rklog.warning("No RPA files found. Was the correct path given?")
        rkp.exit_app(2)  # TODO: raise ValueError or custom exception

    # Depot stuff #
    while dep_lst:

        # TODO: Add check for needed space of all depots and compare with free space of temp
        # dest_free = shutil.disk_usage(rk_tmp_dir).free / 1024 ** 3
        # list_size = sum(entry.stat().st_size for entry in dep_lst if entry.exists()) / 1024 ** 3
        # if dest_free < list_size * 1.1:
        #     raise OSError(os.strerror(28))
        # Maybe this should be in the RkDepotWork class or in a separate function

        depot = dep_lst.pop()

        rkd = RkDepotWork(cfg.task, depot, rk_tmp_dir, log_instance=rklog)

        # if something wrong with initializing dep
        if rkd.dep_initstate is False:
            rklog.warning(f"Archive could not be processed. Skipping: {depot!s}")
            continue

        rkd.work_depot()
        RkCommon.count["dep_done"] += 1

        # FIXME: Causes chaos in the logfile; ANSI codes are written raw
        report = rkd.pm(RkCommon.count["dep_done"], RkCommon.count["dep_found"], depot)
        rklog.important(f"{report}")

    # Finishing
    if cfg.task in ["extract", "simulate"]:
        if cfg.task == "extract":
            # FIXME: These both have perhaps no buissiness here. @class somewhere
            # Also related to the OSError from the FIXME at the top
            rkp.mv_tmp2outdir()
        # rkp._dispose()

        # done msg
        if RkCommon.count["dep_done"] > 0:
            if cfg.task == "extract":
                rklog.important(
                    f" Completed. {RkCommon.count['dep_done']} archive(s) where processed."
                )
            else:
                rklog.important(
                    f"The unpacking of {RkCommon.count['dep_done']} archive(s) was simulated."
                )
        else:
            rklog.warning("Oops! No archives where processed...")

    elif cfg.task in ["listing", "test"]:
        rklog.info("Task completed.")


if __name__ == '__main__':
    args = parse_args()
    main(args)
