#!/usr/bin/python3

"""
RPAKit is a small app which searches in a given path(if not file) RenPy archives
and decompresses the content in a custom-made subdirectory. Just listing without
writing or testing & identifying the archiv or simulating the expand process is
also possible.
"""

# TODO: shutil is a nightmare; perhaps code custom move functionality
# TODO: Add functionality to force rpa format version from user input

import os
import sys
import argparse
from pathlib import Path as pt
import tempfile
import shutil
import pickle
import zlib
import textwrap
from pathlib import Path

tty_colors = True
if sys.platform.startswith('win32'):
    try:
        from colorama import init
        init(autoreset=True)
    except ImportError:
        tty_colors = False


__title__ = 'RPA Kit'
__license__ = 'Apache 2.0'
__author__ = 'madeddy'
__status__ = 'Development'
__version__ = '0.44.0-alpha'


class RpaKitError(Exception):
    """Base class for exceptions in RpaKit."""
    def __init__(self, msg):
        self.msg = msg

    def __str__(self):
        return f"{self.red}{repr(self.msg)}{self.std}"


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
            "Detection of the archive format failed because multiple matches where "
            f"found.\nArchive: {self.dep} with Version > {self.ver}")


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
            "Header not recognizable. Tested archive is not a RPA or a unknown "
            f"custom type.\nArchive: {self.dep} with header: > {self._header}")


class RkCommon:
    """
    "Rpa Kit Common" provides some shared methods and variables for the other
    classes.
    """
    name = __title__
    verbosity = 1
    outdir = 'rpakit_out'
    count = {'dep_found': 0, 'dep_done': 0, 'fle_total': 0, 'fid_found': 0}
    rk_tmp_dir = None
    out_pt = None
    # tty color code shorthands
    std, ul, red, gre, ora, blu, ylw, bg_blu, bg_red = (
        '\x1b[0m', '\x1b[03m', '\x1b[31m', '\x1b[32m', '\x1b[33m', '\x1b[34m',
        '\x1b[93m', '\x1b[44;30m', '\x1b[45;30m' if tty_colors else '')

    def __str__(self):
        return f"{self.__class__.__name__}({self.name!r})"

    @classmethod
    def telltale(cls, fraction, total, obj):
        """Returns a percentage-meter like output for use in tty."""
        return f"[{cls.bg_blu}{fraction / float(total):05.1%}{cls.std}] {obj!s:>4}"

    @classmethod
    def inf(cls, inf_level, msg, m_sort=None):
        """Outputs by the current verboseness level allowed infos."""
        if cls.verbosity >= inf_level:  # TODO: use self.tty ?
            ind1 = f"{cls.name}:{cls.gre} >> {cls.std}"
            ind2 = " " * 12
            if m_sort == 'warn':
                ind1 = f"{cls.name}:{cls.ylw} WARNING {cls.std}> "
                ind2 = " " * 16
            elif m_sort == 'cau':
                ind1 = f"{cls.name}:{cls.red} CAUTION {cls.std}> "
                ind2 = " " * 20
            elif m_sort == 'raw':
                print(ind1, msg)
                return

            print(textwrap.fill(msg, width=90, initial_indent=ind1,
                  subsequent_indent=ind2))

    @classmethod
    def strpth(cls, data):
        return data if isinstance(data, str) else data.decode()

    @classmethod
    def void_dir(cls, dst):
        """Checks if given directory has content."""
        return not any(dst.iterdir())

    @classmethod
    def make_dirstruct(cls, dst):
        """Constructs any needet output directorys if they not already exist."""
        if not dst.exists():
            cls.inf(2, f"Creating directory structure for: {dst}")
            dst.mkdir(parents=True, exist_ok=True)


class RkPathWork(RkCommon):
    """
    Support class for RPA Kit's path related tasks. Needet inputs (file-/dir path)
    are internaly providet.
    If input is a dir it searches there for archives, checks and filters them and
    stores them in a list.
    A archiv as input skips the search part.
    """

    def __init__(self):
        super().__init__()
        self.dep_lst = []
        self.inp_pt = None
        self.raw_inp = None
        self.task = None

        """Removes temporary content and in simulate mode also the outdir."""

            # NOTE: Converting 'src' to str to avoid bugs.python.org/issue32689
            # fixed in py 3.9 - move accepts now pathlike
            # TODO: if its long standard we use pathlikes as source
            # means users need py3.9+
    def dispose(self):

        if self.task == 'extract':
            # FIXME: move does error if src exists in dst; how?
            for entry in self.rk_tmp_dir.iterdir():
                # src = (entry).relative_to(self.rk_tmp_dir)
                shutil.move(str(entry), self.out_pt)

            # TODO: write code to check output
            if self.void_dir(self.out_pt):
                self.out_pt.rmdir()
        else:
            self.out_pt.rmdir()

        if self.void_dir(self.rk_tmp_dir):
            self.rk_tmp_dir.rmdir()
        else:
            shutil.rmtree(self.rk_tmp_dir)

    def exit_app(self):
        self.inf(0, "Exiting RpaKit.")
        for i in range(3, -1, -1):
            print(f"{RkCommon.bg_red}{i}%{RkCommon.std}", end='\r')
        sys.exit(0)

    def make_output(self):
        """Constructs outdir and outpath."""

        self.out_pt = self.inp_pt / self.outdir
        if self.out_pt.exists() and not self.void_dir(self.out_pt):
            self.inf(0, f"The output directory > {self.out_pt} exists already and "
                     "is not empty. Rename or remove it.", m_sort='cau')
            self.dispose()
            self.exit_app()
        self.make_dirstruct(self.out_pt)

    def ident_paired_depot(self):
        """Identifys rpa1 type paired archives and removes one from the list."""
        lst_copy = self.dep_lst[:]
        for entry in lst_copy:
            if entry.suffix == '.rpi':
                twin = str(entry.with_suffix('.rpa'))
                if twin in self.dep_lst:
                    self.dep_lst.remove(twin)
                    RkCommon.count['dep_found'] -= 1

    @staticmethod
    def valid_archives(entry):
        """Checks path objects for identity by extension. RPA have no real magic num."""
        return bool(entry.is_file() and entry.suffix in ['.rpa', '.rpi', '.rpc'])

    def add_depot(self, depot):
        """Adds by extension as RPA identified files to the depot list."""
        if self.valid_archives(depot):
            self.dep_lst.append(depot)
            RkCommon.count['dep_found'] += 1

    def search_rpa(self):
        """Searches dir and calls another method which identifys RPA files."""
        for entry in os.scandir(self._inp_pt):
            entry_pth = pt(entry.path)
            self.add_depot(entry_pth)

    def check_inpath(self):
        """Helper to check if given path exist."""
        if not self.raw_inp.exists() or self.raw_inp.is_symlink():
            raise FileNotFoundError(f"Could the given path object ({self.raw_inp})"
                                    "not find! Check the given input.")
        self.raw_inp = self.raw_inp.resolve(strict=True)

    def pathworker(self):
        """This prepairs the given path and output dir. It dicovers if the input
        is a file or directory and takes the according actions.
        """
        try:
            self.check_inpath()

            if self.raw_inp.is_dir():
                self._inp_pt = self.raw_inp
                self.search_rpa()
            elif self.raw_inp.is_file():
                self.add_depot(self.raw_inp)
                self._inp_pt = self.raw_inp.parent
            else:
                raise FileNotFoundError("File not found!")

        except OSError as err:
            raise RpaKitError(
                f"{err}: Error while testing and prepairing input path "
                f">{self.raw_inp}< for the main job.")

        self.ident_paired_depot()

        if self.task in ['extract', 'simulate']:
            self.rk_tmp_dir = Path(tempfile.mkdtemp(prefix='RpaKit.', suffix='.tmp'))
            self.make_output()

        if RkCommon.count['dep_found'] > 0:
            self.inf(1, f"{RkCommon.count['dep_found']} RPA files to process:\n"
                     f"{chr(10).join([*map(str, self.dep_lst)])}", m_sort='raw')
        else:
            self.inf(1, "No RPA files found. Was the correct path given?")


class RkDepotWork(RkCommon):
    """
    The class for analyzing, testing and unpacking RPA files. All needet
    inputs (depot, output path) are internaly providet.
    """

    _rpaformats = {'x': {'rpaid': 'rpa1',
                         'desc': 'Legacy type RPA-1.0'},
                   'RPA-2.0 ': {'rpaid': 'rpa2',
                                'desc': 'Legacy type RPA-2.0'},
                   'RPA-3.0 ': {'rpaid': 'rpa3',
                                'desc': 'Standard type RPA-3.0'},
                   # Header ID is the same as rpa3 but double keys are not allowed
                   'RPA-3.0rk': {'rpaid': 'rpa3rk',
                                 'alias': 'RPA 3 rk',
                                 'desc': 'Custom type of RPA-3.0 with reversed key'},
                   'RPI-3.0': {'rpaid': 'rpa32',
                               'alias': 'rpi3',
                               'desc': 'Custom type RPI-3.0'},
                   'RPA-3.1': {'rpaid': 'rpa3',
                               'alias': 'rpa31',
                               'desc': 'Custom type RPA-3.1, a alias of RPA-3.0'},
                   'RPA-3.2': {'rpaid': 'rpa32',
                               'desc': 'Custom type RPA-3.2'},
                   'RPA-4.0': {'rpaid': 'rpa3',
                               'alias': 'rpa4',
                               'desc': 'Custom type RPA-4.0, a alias of RPA-3.0'},
                   'ALT-1.0': {'rpaid': 'alt1',
                               'alias': 'ALT 1',
                               'desc': 'Custom type ALT-1.0'},
                   'ZiX-12A': {'rpaid': 'zix12a',
                               'alias': 'ZIX 12a',
                               'desc': 'Custom type ZiX-12A'},
                   'ZiX-12B': {'rpaid': 'zix12b',
                               'alias': 'ZIX 12b',
                               'desc': 'Custom type ZiX-12B'}}

    _rpaspecs = {'rpa1': {'offset': 0,
                          'key': None},
                 'rpa2': {'offset': slice(8, None),
                          'key': None},
                 'rpa3': {'offset': slice(8, 24),
                          'key': slice(25, 33),
                          'key_org': 1111638594,
                          'key_rv': slice(None, None, -1)},
                 'rpa32': {'offset': slice(8, 24),
                           'key': slice(27, 35)},
                 'alt1': {'offset': slice(17, 33),
                          'key': slice(8, 16),
                          'key2': 0xDABE8DF0}}

    def __init__(self):
        super().__init__()
        self.depot = None
        self.header = None
        self.version = {}
        self.reg = {}
        self.dep_initstate = None

    def clear_rk_vars(self):
        """This clears some vars. In rare cases nothing is assigned and old values
        from previous depot run are caried over. Weird files will slip in and error.
        """
        self.header = None
        self.version.clear()
        self.reg.clear()
        self.dep_initstate = None
        self.count['fid_found'] = 0

    def extract_data(self, file_pt, pos_stats):
        """Extracts the archive data to a temp file."""
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
        """Arrange the register in common form."""
        for val in self._reg.values():
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
            raise f"{err}: Problem with the format data encountered. Perhaps " \
                "the RPA is malformed."
        except TypeError as err:
            raise f"{err}: Somehow the wrong data types had a meeting in here. " \
                "They did'n like each other."
        return offset, key

    def collect_register(self):
        """Gets the depot's register through unzip and unpickle."""
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
                self.inf(1, "UnicodeDecodeError: Found possibly old RPA-1 format.",
                         m_sort='warn')
            else:
                magic = str()
        return magic

    def guess_version(self):
        """Determines probable archive version from header/suffix and pairs alias
        variants with a main format ID.
        """
        magic = self.get_header_start()
        try:
            for key, val in self.rpaformats.items():
                if key in magic:
                    self.version.update(val)
                    self.count['fid_found'] += 1

            # NOTE:If no version is found the dict is empty; searching with a key
            # slice for 'rpaid' excepts a KeyError (better init dict with key?)
            if 'rpa1' in self.version.values() and self.depot.suffix != '.rpi':
                # self.version = {}
                self.version.clear()
            elif not self.version:
                raise NoRpaOrUnknownWarning(self.depot, self.header)
            elif self.count['fid_found'] > 1:
                raise AmbiguousHeaderError(self.version)
            elif 'zix12a' in self.version.values() or 'zix12b' in self.version.values():
                raise NotImplementedError(
                    self.inf(0, f"{self.depot!r} is a unsupported format.\nFound "
                             f"archive header: > {self._header}", m_sort='cau'))

        except (NoRpaOrUnknownWarning, NotImplementedError):
            self.dep_initstate = False
        except LookupError as err:
            raise self.inf(0, f"{err} A unknown problem with the archives format "
                           "ID occured. Unable to continue.", m_sort='cau')
        else:
            self.dep_initstate = True

    def get_header(self):
        """Opens file and reads header line in."""
        with self.depot.open('rb') as of:
            of.seek(0)
            self.header = of.readline()

    # FIXME Path related - should be in on of the other classes
    def check_out_pt(self, f_pt):
        """Checks output path and if needet renames file."""
        tmp_pt = self.rk_tmp_dir / f_pt
        # tmp_pt = self.out_pt / f_pt
        if tmp_pt.is_dir() or f_pt == "":
            rand_fn = '0_' + os.urandom(2).hex() + '.BAD'
            tmp_pt = self.rk_tmp_dir / rand_fn
            # tmp_pt = self.out_pt / rand_fn
            self.inf(2, "Possible invalid archive! A filename was replaced with"
                     f"the new name '{rand_fn}'.")
        return tmp_pt

    def unpack_depot(self):
        """Manages the unpacking of the depot files."""
        for file_num, (file_pt, pos_stats) in enumerate(self.reg.items()):
            try:
                tmp_path = self.check_out_pt(file_pt)
                self.make_dirstruct(tmp_path.parent)

                tmp_file_data = self.extract_data(file_pt, pos_stats)
                self.inf(2, f"{self.telltale(file_num, RkCommon.count['fle_total'], file_pt)}")

                with tmp_path.open('wb') as of:
                    of.write(tmp_file_data)
            except TypeError as err:
                raise f"{err}: Unknown error while trying to extract a file."

        if self.void_dir(self.rk_tmp_dir):
            self.inf(2, "No files from archive unpacked.")
        else:
            self.inf(2, f"Unpacked {RkCommon.count['fle_total']} files from archive: "
                     f"{self.depot!s}")

    def list_depot_content(self):
        """Lists the file content of a renpy archive without unpacking."""
        # outp_dst = sys.stdout if "bla" else fl
        self.inf(2, "Listing archive files:")
        print(f"Depot {RkCommon.count['dep_done'] + 1}: {self.depot.name}")
        for num, (fln, flidx) in enumerate(sorted(self._reg.items())):
            print(f"{' ' * 2}File {num}: {fln}\n{' ' * 4}Index data: {flidx}")

        self.inf(1, f"Archive {self.depot.name!s} holds "
                 f"{len(self._reg.keys())} files.")

    def test_depot(self):
        """Tests archives for their format type and outputs this."""
        self.inf(0, f"For archive > {self.depot.name} the identified version "
                 f"variant is: {self.bg_blu}{self._version['desc']!r}{self.std}")

    def init_depot(self):
        """Initializes depot files to a ready state for further operations."""
        try:
            self.get_header()
            self.guess_version()

            if self.dep_initstate is False:
                self.inf(0, f"Skipping bogus archive: {self.depot!s}", m_sort='warn')
            elif self.dep_initstate is True:
                self.get_version_specs()
                self.collect_register()
                self.reg = {str(_pt): _d for _pt, _d in self.reg.items()}
                RkCommon.count['fle_total'] = len(self.reg)

            if 'alias' in self.version.keys():
                self.inf(2, "Unofficial RPA found. "
                         f"RPA variant name is '{self._version['alias']}'")
            else:
                self.inf(2, "Official RPA found.")

        except OSError as err:
            raise RpaKitError(f"{err}: Error while opening archive file "
                              f">{self.depot}< for initialization.")


class RkMain(RkPathWork, RkDepotWork):
    """
    Main class to process args and executing the related methods. Parameter:
    Positional:
        {inp} takes `path` or `path/filename.suffix`
    Keyword:
        {task=['extract'|'listing'|'test'|'simulate']} the intendet request for the app run
        {outdir=NEWDIR} changes output directory for the archiv content
        {verbose=[0|1|2]} information output level; defaults to 1
    """

    def __init__(self, inpath, task, outdir=None, verbose=None):
        if verbose:
            RkCommon.verbosity = verbose
        if outdir:
            RkCommon.outdir = Path(outdir)
        super().__init__()
        self.raw_inp = Path(inpath)
        self.task = task

    def done_msg(self):
        """Outputs a info when all is done."""
        if self.task in ['extract', 'simulate']:
            if RkCommon.count["dep_done"] > 0:
                if self.task == 'extract':
                    self.inf(0, f" Done. We unpacked {RkCommon.count['dep_done']} "
                             "archive(s).")
                else:
                    self.inf(0, "We successful simulated the unpacking of"
                             f" {RkCommon.count['dep_done']} archive(s).")
            else:
                self.inf(0, "Oops! No archives where processed...")
        elif self.task in ['listing', 'test']:
            self.inf(0, "Completed!")

    def begin_msg(self):
        """Outputs a info  about the start state if verbosity is high."""
        if self.raw_inp.is_file():
            self.inf(2, f"Input is a file. Processing {self.raw_inp}.")
        elif self.raw_inp.is_dir():
            self.inf(2, f"Input is a directory. Searching for RPA in {self.raw_inp} "
                     "and below.")

    def rk_control(self):
        """Processes input, yields depot's to the functions."""
        self.begin_msg()
        self.pathworker()
        self.inf(1, f"{RkCommon.name} found {RkCommon.count['dep_found']} "
                 "potential archives.")

        while self.dep_lst:
            self.depot = self.dep_lst.pop()

            self.init_depot()
            if self.dep_initstate is False:
                continue

            if self.task in ['extract', 'simulate']:
                self.unpack_depot()
            elif self.task == 'listing':
                self.list_depot_content()
            elif self.task == 'test':
                self.test_depot()

            RkCommon.count['dep_done'] += 1
            report = self.telltale(RkCommon.count['dep_done'],  RkCommon.count['dep_found'],
                                   self.depot)
            self.inf(1, f"{report}")
            self.clear_rk_vars()

        # FIXME: Subpar behavior. Call dispose for std task of moving unpacked
        # content in place. Should be normal func first. e.g.
        if self.task in ['extract', 'simulate']:
            self.dispose()
        self.done_msg()


def parse_args():
    """Argument parser to provide functionality for the command-line interface."""

    desc = """Program for searching and unpacking RPA files. EXAMPLE USAGE:
    rpakit.py -e -o unpacked /home/{USERNAME}/somedir/search_here
    rpakit.py -t /home/{USERNAME}/otherdir/file.rpa
    rpakit.py --extract c:/Users/{USERNAME}/my_folder/A123.rpa"""
    epi = "Default output dir is set to `{Target}/rpakit_out/`. Change with option -o."
    ap = argparse.ArgumentParser(
        description=desc,
        epilog=epi,
        formatter_class=argparse.RawTextHelpFormatter)
    ap.add_argument(
        'inpath',
        metavar='Target',
        action='store',
        type=str,
        help='Directory path (to search) OR rpa file path to unpack.')
    opts = ap.add_mutually_exclusive_group(required=True)
    opts.add_argument(
        '-e',
        '--extract',
        dest='task',
        action='store_const',
        const='extract',
        help='Extracts all stored files and dirs.')
    opts.add_argument(
        '-l',
        '--list',
        dest='task',
        action='store_const',
        const='listing',
        help='Prints a listing of all stored files.')
    opts.add_argument(
        '-t',
        '--test',
        dest='task',
        action='store_const',
        const='test',
        help='Tests if archive(s) are a known format.')
    opts.add_argument(
        '-s',
        '--simulate',
        dest='task',
        action='store_const',
        const='simulate',
        help='Unpacks all stored files just temporary.')
    ap.add_argument(
        "-o",
        "--outdir",
        action='store',
        type=str,
        help="Extracts to the given path instead to the default destination.")
    ap.add_argument(
        '--verbose',
        metavar='level [0-2]',
        type=int,
        choices=range(0, 3),
        help='Amount of info output. 0:none, 2:much, default:1')
    ap.add_argument(
        '--version',
        action='version',
        version=f"{ __title__} {__version__}")
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
    rkm = RkMain(cfg.inpath, cfg.task, outdir=cfg.outdir, verbose=cfg.verbose)
    rkm.rk_control()


if __name__ == '__main__':
    main()
