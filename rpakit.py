#!/usr/bin/env python3

"""
RPAKit is a app which searches in a given path(if not file) Renpy archives
and uncompresses the content in a new subdirectory. Listing without writing
or testing the archiv is also possible.
"""

# pylint:disable=c0301, w0612, r0902, w0511, r0903, c0116

import os
import sys
import argparse
from pathlib import Path as pt
import pickle
import zlib
import textwrap


__title__ = 'RPA Kit'
__license__ = 'GPLv3'
__author__ = 'madeddy'
__status__ = 'Development'
__version__ = '0.22.0-alpha'


class RKCommon:
    """Holds some RPA Kit basic methods and variables."""
    verbosity = 1
    count = {'dep_found': 0, 'dep_done': 0, 'fle_total': 0}
    out_pt = ''
    name = 'RPAKit'


    def __str__(self):
        return f"{self.__class__.__name__}({self.name!r})"

    @classmethod
    def utfify(cls, data):
        if isinstance(data, str):
            return data
        return data.decode("utf-8")

    @classmethod
    def strify(cls, data):
        return str(data)

    @classmethod
    def inf(cls, inf_level, msg, m_sort=None):
        """Outputs by the current verboseness level allowed infos."""
        if cls.verbosity >= inf_level:  # self.tty ?
            ind1 = f"{cls.name}: > "
            ind2 = " " * 12
            if m_sort == 'note':
                ind1 = f"{cls.name}:\x1b[93m NOTE \x1b[0m> "
                ind2 = " " * 16
            elif m_sort == 'warn':
                ind1 = f"{cls.name}:\x1b[31m WARNING \x1b[0m> "
                ind2 = " " * 20
            elif m_sort == 'raw':
                print(ind1, msg)
                return
            print(textwrap.fill(msg, width=90, initial_indent=ind1, subsequent_indent=ind2))

    @classmethod
    def make_dirstruct(cls, dst):
        """Constructs needet output directorys if they not already exist."""
        if not pt(dst).exists():
            cls.inf(2, f"Creating directory structure for: {dst}")
            pt(dst).mkdir(parents=True, exist_ok=True)


class RPAKit(RKCommon):
    """
    The class for analyzing and unpacking RPA files. Needet inputs
    (depot, output path) are internaly providet.
    """

    _rpaformats = {'x': {'rpaid': 'rpa1',
                         'desc': 'RPA-1.0'},
                   'RPA-2.0 ': {'rpaid': 'rpa2',
                                'desc': 'RPA-2.0'},
                   'RPA-3.0 ': {'rpaid': 'rpa3',
                                'desc': 'RPA-3.0'},
                   'RPI-3.0': {'rpaid': 'rpa32',
                               'alias': 'rpi3',
                               'desc': 'RPI-3.0'},
                   'RPA-3.1': {'rpaid': 'rpa3',
                               'alias': 'rpa31',
                               'desc': 'RPA-3.1'},
                   'RPA-3.2': {'rpaid': 'rpa32',
                               'desc': 'RPA-3.2'},
                   'RPA-4.0': {'rpaid': 'rpa3',
                               'alias': 'rpa4',
                               'desc': 'RPA-4.0'},
                   'ALT-1.0': {'rpaid': 'alt1',
                               'desc': 'ALT-1.0'},
                   'ZiX-12A': {'rpaid': 'zix12a',
                               'desc': 'ZiX-12A'},
                   'ZiX-12B': {'rpaid': 'zix12b',
                               'desc': 'ZiX-12B'}}

    _rpaspecs = {'rpa1': {'offset': 0,
                          'key': None},
                 'rpa2': {'offset': slice(8, None),
                          'key': None},
                 'rpa3': {'offset': slice(8, 24),
                          'key': slice(25, 33)},
                 'rpa32': {'offset': slice(8, 24),
                           'key': slice(27, 35)},
                 'alt1': {'offset': slice(17, 33),
                          'key': slice(8, 16),
                          'key2': 0xDABE8DF0}}

    def __init__(self):
        super().__init__()
        self.depot = ''
        self._header = ''
        self._version = {}
        self._reg = {}
        self.dep_initstate = None


    def extract_data(self, file_pt, file_data):
        """Extracts the archive data to a temp file."""
        if pt(self.depot).suffix == '.rpi':
            self.depot = pt(self.depot).with_suffix('.rpa')

        with pt(self.depot).open('rb') as ofi:
            if len(self._reg[file_pt]) == 1:
                ofs, lng, pre = file_data[0]
                ofi.seek(ofs)
                tmp_file = pre + ofi.read(lng - len(pre))
            else:
                tmp = []
                for ofs, lng, pre in file_data:
                    ofi.seek(ofs)
                    tmp.append(ofi.read(lng))
                    tmp_file = pre.join(tmp)

        return tmp_file

    def unscrample_reg(self, key):
        """Unscrambles the archive register."""
        for _kv in self._reg:
            self._reg[_kv] = [(ofs ^ key, lng ^ key, pre)
                              for ofs, lng, pre in self._reg[_kv]]

    def unify_reg(self):
        """Arrange the register in common form."""
        for val in self._reg.values():
            if len(val[0]) == 2:
                for num, _ in enumerate(val):
                    val[num] += (b'',)

    def get_cipher(self):
        """Fetches the cipher for the register from the header infos."""
        # NOTE: Slicing is error prone; perhaps use of "split to parts" as fallback
        # in they exceptions is thing; or even reverse the order of this methods then
        offset, key = 0, None
        try:
            slos, slky = self._version['offset'], self._version['key']
            if self._version['rpaid'] != 'rpa1':
                offset = int(self._header[slos], 16)
                if self._version['rpaid'] != 'rpa2':
                    key = int(self._header[slky], 16)
        except (LookupError, ValueError) as err:
            print(sys.exc_info())
            raise f"{err}: Problem with the format data encountered. Perhabs " \
                    "the RPA is malformed."
        except TypeError as err:
            raise f"{err}: Somehow the wrong data types had a meeting in here. " \
                    "They did'n like each other."
        return offset, key

    def collect_register(self):
        """Gets the depot's register."""
        offset, key = self.get_cipher()
        with pt(self.depot).open('rb') as ofi:
            ofi.seek(offset)
            self._reg = pickle.loads(zlib.decompress(ofi.read()), encoding='bytes')

        self.unify_reg()
        if key is not None:
            if 'key2' in self._version.keys():
                key = key ^ self._version['key2']
            self.unscrample_reg(key)

    def get_version_specs(self):
        """Yields for the given archive version the cipher data."""
        try:
            for key, val in self._rpaspecs.items():
                if key == self._version['rpaid']:
                    self._version.update(val)
                    break
        except KeyError:
            raise f"Error while aquiring version specifications for {self.depot}."

    def get_header_start(self):
        """Reads the header start in and decodes to string."""
        try:
            magic = self._header[:12].decode()
        except UnicodeDecodeError:
            self.inf(1, "UnicodeDecodeError: Found possible old RPA-1 format.", m_sort='note')
            # FIXME: Ugly code; needs improvement
            # Needs to be twice catched for rpa1 type and weirdo files
            try:
                magic = self._header[:1].decode()
            except UnicodeError:
                self.inf(0, "UnicodeError: Header unreadable. Tested file is " \
                         "perhabs no RPA or very weird.", m_sort='warn')
                magic = ''
        return magic

    def guess_version(self):
        """
        Determines archive version from header or suffix and pairs alias variants
        with a main format id.
        """
        # HACK:We reset both or the val from last depot is still there. Weird files
        # slip in and error
        self.dep_initstate = None
        self._version = {}
        magic = self.get_header_start()
        try:
            for key, val in self._rpaformats.items():
                if key in magic:
                    self._version = val
            # NOTE:If no version is found the dict is empty; searching with a key
            # slice for 'rpaid' excepts a KeyError (better init dict with key?)
            if 'rpa1' in self._version.values() and pt(self.depot).suffix != '.rpi':
                self._version = {}
            elif not self._version:
                raise ValueError
            elif 'zix12a' in self._version.values() or 'zix12b' in self._version.values():
                raise NotImplementedError

        except (ValueError, NotImplementedError):
            self.inf(0, f"\"{self.depot}\" is not a Ren\'Py archive or a unsupported " \
                     f"variation.\nFound archive header: <{self._header}>", m_sort='warn')
            self.dep_initstate = False
        except LookupError:
            raise "There was some problem with the key of the archive..."
        else:
            self.dep_initstate = True

    def collect_header(self):
        """Opens file and reads header line in."""
        with pt(self.depot).open('rb') as ofi:
            ofi.seek(0)
            self._header = ofi.readline()

    def unpack_depot(self):
        """Manages the unpacking of the depot files."""
        for file_num, (file_pt, file_data) in enumerate(self._reg.items()):
            try:
                self.make_dirstruct(pt(self.out_pt) / pt(file_pt).parent)

                tmp_file = self.extract_data(file_pt, file_data)
                self.inf(2, f"[{file_num / float(self.count['fle_total']):05.1%}] " \
                         f"{file_pt:>4}")

                with pt(self.out_pt / file_pt).open('wb') as ofi:
                    ofi.write(tmp_file)
            except TypeError as err:
                raise f"{err}: Unknown error while trying to extract a file."

        self.count['dep_done'] += 1
        if any(pt(self.out_pt).iterdir()):
            self.inf(2, f"Unpacked {self.count['fle_total']} files from archive: " \
                     f"{self.strify(self.depot)}")
        else:
            self.inf(2, "No files from archive unpacked.")

    def show_depot_content(self):
        """Lists the file content of a renpy archive without unpacking."""
        self.inf(2, "Listing archive files:")
        for item in sorted(self._reg.keys()):
            print(f"{item}")
        self.count['dep_done'] += 1
        self.inf(1, f"Archive {self.strify(pt(self.depot).name)} holds " \
                 f"{len(self._reg.keys())} files.")

    def test_depot(self):
        """Tests archives for their format type and outputs this."""
        self.inf(0, f"For archive <{self.depot.name}> the identified version " \
                 f"variant is: `{self._version['rpaid']}`")
        self.count['dep_done'] += 1

    def init_depot(self):
        """Initializes depot files to a ready state for further operations."""
        try:
            self.collect_header()
            self.guess_version()

            if 'alias' in self._version.keys():
                self.inf(2, "Unofficial RPA found.")
            else:
                self.inf(2, "Official RPA found.")

            if self.dep_initstate is False:
                self.inf(0, f"Skipping bogus archive: {self.strify(self.depot)}", m_sort='note')
            elif self.dep_initstate is True:
                self.get_version_specs()
                self.collect_register()
                self._reg = {self.utfify(_pt): _d for _pt, _d in self._reg.items()}
                self.count['fle_total'] = len(self._reg)
        except Exception:
            raise Exception("Unknown error while reading depot in.")


class RPAPathwork(RKCommon):
    """
    A support class for RPA Kit for the pathwork part. Needet inputs
    (file/dir path) are internaly providet. If input is a dir it searches
    there for archives, checks and filters them and puts them in a list.
    A archiv as input skips the search part.
    """

    def __init__(self):
        super().__init__()
        self.dep_lst = []
        self._inp_pt = None
        self.raw_inp = None
        self.outdir = None

    def make_output(self):
        """Constructing outdir and -path."""
        if self.outdir is None:
            self.outdir = 'rpakit_out'
        self.out_pt = pt(self._inp_pt) /  self.outdir
        self.make_dirstruct(self.out_pt)

    def ident_paired_rpa(self):
        """Identifys rpa1 type paired archives and removes one from the list."""
        lst_copy = self.dep_lst
        for entry in list(lst_copy):
            if pt(entry).suffix == '.rpi':
                twin = str(pt(entry).with_suffix('.rpa'))
                if twin in self.dep_lst:
                    self.dep_lst.remove(twin)
                    self.count['dep_found'] -= 1

    @staticmethod
    def valid_archives(entry):
        """Checks path objects for identity by extension. RPA have no real magic num."""
        return bool(pt(entry).is_file() and pt(entry).suffix
                    in ['.rpa', '.rpi', '.rpc'])

    def search_rpa(self):
        """Searches RPA files in given directory and adds them to the deque."""
        for entry in os.scandir(self._inp_pt):
            if self.valid_archives(entry):
                self.dep_lst.append(entry.path)
                self.count['dep_found'] += 1

    def transf_winpt(self):
        """Check if WinOS and a win-path was given. Returns as posix."""
        if sys.platform.startswith('win32') and '\\' in self.raw_inp:
            self.inf(2, "The input appears to be a windows path. It should be" \
                     "given in posix style to minimize the error risk.", m_sort='note')
            self.raw_inp = pt(self.raw_inp).as_posix()

    def pathworker(self):
        """
        This prepairs the given path and output dir. It will dicover if the input
        is a file or directory and takes the according actions.
        """
        self.transf_winpt()
        self.raw_inp = pt(self.raw_inp).resolve(strict=True)

        try:
            if pt(self.raw_inp).is_dir():
                self._inp_pt = self.raw_inp
                self.search_rpa()
            elif pt(self.raw_inp).is_file():
                if self.valid_archives(self.raw_inp):
                    self.dep_lst.append(self.raw_inp)
                    self.count['dep_found'] += 1
                self._inp_pt = pt(self.raw_inp).parent
            else:
                raise FileNotFoundError("File not found!")
        except Exception as err:  # pylint:disable=w0703
            print(f"{err}: Unexpected error from the given target path. \n{sys.exc_info()}")

        self.make_output()
        self.ident_paired_rpa()

        if self.count['dep_found'] > 0:
            self.inf(1, f"{self.count['dep_found']} RPA files to process:\n"
                     f"{chr(10).join([*map(str, self.dep_lst)])}", m_sort='raw')
        else:
            self.inf(1, "No RPA files found. Was the correct path given?")


class RKmain(RPAPathwork, RPAKit):
    """
    Main class to process args and executing the related methods. Args:
    Positional: {inp} takes `path` or `path + filename.suffix`
    Keyword: {task=['exp'|'lst'|'tst']} expand/list content of the archiv(s) or test it
             {outdir=NEWDIR} changes output directory for the archiv content
             {verbose=[0|1|2]} information output level; defaults to 1
    """

    def __init__(self, inpath, outdir=None, verbose=None, **kwargs):
        if verbose is not None:
            RKCommon.verbosity = verbose
        super().__init__()
        self.raw_inp = inpath
        if outdir is not None:
            self.outdir = outdir
        self.task = kwargs.get('task')

    def done_msg(self):
        """Gives a final info when all is done."""
        if self.task == 'exp':
            if self.count['dep_done'] > 0:
                self.inf(0, f" Done. We unpacked {self.count['dep_done']} archive(s).")
            else:
                self.inf(0, f"Oops! No archives where processed...")
        elif self.task  in ['lst', 'tst']:
            self.inf(0, f"Completed!")

    def cfg_control(self):
        """Processes input, yields depot's to the functions."""
        if pt(self.raw_inp).is_file():
            self.inf(2, f"Input is a file. Processing {self.raw_inp}.")
        elif pt(self.raw_inp).is_dir():
            self.inf(2, f"Input is a directory. Searching for RPA in {self.raw_inp} " \
                     "and below.")

        try:
            self.pathworker()
        except OSError as err:
            raise Exception(
                f"{err}: Error while testing and prepairing input path " \
                f"< {self.raw_inp} > for the main job.")

        while self.dep_lst:
            self.depot = self.dep_lst.pop()
            try:
                self.init_depot()
            except OSError as err:
                raise Exception(f"{err}: Error while opening archive file " \
                                f"< {self.depot} > for initialization.")

            if self.dep_initstate is False:
                continue

            if self.task == 'exp':
                self.unpack_depot()
            elif self.task == 'lst':
                self.show_depot_content()
            elif self.task == 'tst':
                self.test_depot()

            self.inf(1, f"[{self.count['dep_done'] / float(self.count['dep_found']):05.1%}] {self.strify(self.depot):>4}")
        self.done_msg()


def parse_args():
    """
    Argument parser and test for input path to provide functionality for the
    command line interface.
    """
    def check_path(inp):
        """Helper to check if given path exist."""
        if pt(inp).exists() and not pt(inp).is_symlink():
            return inp
        raise FileNotFoundError(f"Could the given path object ({inp}) not find! " \
                                "Check the given input.")

    def valid_switch():
        """Helper function to determine if a task is choosen."""
        if not args.task:
            aps.print_help()
            raise argparse.ArgumentError(args.task, f"\nNo task requested; " \
                                         "either -e, -l or -t is required.")

    desc = """Program for searching and unpacking RPA files. EXAMPLE USAGE:
    rpa_kit.py -e -o unpacked /home/{USERNAME}/somedir/search_here
    rpa_kit.py -e /home/{USERNAME}/otherdir/file.rpa
    rpa_kit.py -t c:/Users/{username}/my_folder/A123.rpa"""
    epi = "Standard output dir is set to ´{Target}/rpakit_out/´. Change with option -o."
    aps = argparse.ArgumentParser(description=desc, epilog=epi, formatter_class=argparse.RawTextHelpFormatter)
    aps.add_argument('inpath',
                     metavar='Target',
                     type=check_path,
                     help='Directory path to search OR name of a RPA file to unpack.')
    opts = aps.add_mutually_exclusive_group()
    opts.add_argument('-e', '--expand',
                      dest='task',
                      action='store_const',
                      const='exp',
                      help='Unpacks all stored files.')
    opts.add_argument('-l', '--list',
                      dest='task',
                      action='store_const',
                      const='lst',
                      help='Gives a listing of all stored files.')
    opts.add_argument('-t', '--test',
                      dest='task',
                      action='store_const',
                      const='tst',
                      help='Tests if archive(s) are a known format.')
    aps.add_argument("-o", "--outdir",
                     action="store",
                     type=str,
                     help="Extracts to the given path instead of standard.")
    aps.add_argument('--verbose',
                     metavar='level [0-2]',
                     type=int,
                     choices=range(0, 3),
                     help='Amount of info output. 0:none, 2:much, default:1')
    aps.add_argument('--version',
                     action='version',
                     version=f'%(prog)s : { __title__} {__version__}')
    args = aps.parse_args()
    valid_switch()
    return args


if __name__ == '__main__':
    assert sys.version_info >= (3, 6), \
        f"Must be executed in Python 3.6 or later. You are running {sys.version}"
    CFG = parse_args()
    RKM = RKmain(CFG.inpath, outdir=CFG.outdir, verbose=CFG.verbose, task=CFG.task)
    RKM.cfg_control()
