[![Python Version][b_py]][l_py] [![Ren'Py Version][renpy]][l_renpy] [![License][b_licence]][l_licence] ![App_version][b_app_version] [![hits][b_hits]][l_hits]

<!--  [![Latest Version][b_release]][l_releases] ![check][b_check_master]  -->
<!-- Badge links -->
[b_py]: https://img.shields.io/badge/3.9%2B-3776AB?style=flat-square&logo=python&logoColor=fff&label=Python%20Version&labelColor=3776AB&color=gold
[l_py]: https://python.org
[renpy]: https://img.shields.io/badge/Ren'Py-ac6464?logo=renpy&logoColor=fff&style=flat-square
[l_renpy]: https://renpy.org

[b_licence]: https://img.shields.io/github/license/madeddy/RpaKit?label=License&style=flat-square
[l_licence]: LICENSE

[b_app_version]: https://img.shields.io/badge/RpaKit_0.46.0_alpha-development-orange.svg?style=flat-square

[b_release]: https://img.shields.io/github/v/release/madeddy/RpaKit?style=flat-square
[l_releases]: https://github.com/madeddy/RpaKit/releases
[b_check_master]: https://img.shields.io/github/actions/workflow/status/madeddy/RpaKit/python-app.yaml?branch=master&style=flat-square&logo=github&label=Tests:%20master

[b_hits]: https://hits.sh/github.com/madeddy/RpaKit.svg?style=flat-square&label=Access%20Count&color=lightgrey
[l_hits]: https://hits.sh/github.com/madeddy/RpaKit

# RPA Kit
RPA Kit is a application for decompressing Ren'Py archives.

It needs as input a target archive-file or a directory wich contains such archives. These
will if possible identified and the content of them unpacked in a directory of choice. It is
also possible to output a read-only listing of the content or to test, if the format-type of
the given archives supported is.

## Usage
### Command line parameter overview
**~$** rpakit.py [-e|-l|-t|-s] [--overwrite] [-o OUTPUT] [--verbose] [--version] [-h, --help] target

- *Positional options(required):*
  + `target`                Directory path to search OR path of a RPA file to work on

- *Tasks(one required):*
  + `-e`, `--expand`        Unpacks all stored files
  + `-l`, `--list`          Lists all stored files
  + `-t`, `--test`          Tests if archive(s) are a known format
  + `-s`, `--simulate`      Simulates unpacking process

- *Optional:*
  + `--overwrite`           Overwrites outdir and any content
  + `-o`, `--outdir OUTPUT` Extracts to the given path instead of standard
  + `--no_log`              Deactivates the use of a logfile in the script path
  + `--loglevel`            Set minimum log-level for the console: Default is `notable`; Use
                            `warning` or higher to reduce output
  + `--version`             Prints the RpaKit version
  + `-h`, `--help `         Print this help

### Example CLI usage
- rpakit.py -e -o unpacked /home/{USERNAME}/somedir/search_here
- rpakit.py -t /home/{USERNAME}/otherdir/file.rpa
- rpakit.py --extract c:/Users/{USERNAME}/my_folder/A123.rpa

`rpa_kit.py -e /home/{USERNAME}/otherdir/archive.rpa`
Will extract every file from archive into the default output directory, making
subdirectories when necessary.

`rpa_kit.py /home/{USERNAME}/somedir/search_here/ -e -o unpacked`
Searches RenPy archives in this directory and uncompresses them in the subdir
'unpacked'.

`rpa_kit.py -t c:/Users/{username}/my_folder/A123.rpa`
This will test the given archive for his format and if valide prints it out.

`rpa_kit.py -l c:/Users/{username}/game_dir/foo/ --verbose 2`
Searches for RenPy archives in this directory and lists their file content in the
console. The verboseness was also set to highest level (tell everything).

### Motivation - _Why this project?_
This started 2017 as another learning experience in Python and and to understand a bit more
about RenPy internals. So i needed a project for this.

Some of the goals where:
- Input as a directory with rpa files instead just a file
- Easy extensibility for new formats
- Support for more rpa formats
- Additional info output

In the future there will possibly other changes if time allows it and motivation at the same
time on a high is. Possible changes could be:
- Info output with classic logging
- Format specs and some mechanics move to dedicated classes per type


## Legal
### License
__RPA Kit__ is licensed under Apache-2.0. See the [LICENSE](LICENSE) file for more details.

### Disclaimer
This program is intended for people who have the legal rights or the consent of the target
app authors to access or decompress the archive files. Any illegal or otherwise unindented
usage of this software is discouraged and unsupported.

### Credits
This software was developed with some orientation on [RenPy's](https://github.com/renpy/renpy) and [rpatool's](https://github.com/shizmob/rpatool) code for
the work with RPA files.
Credits for the development of the RenPy archive format belong to the contributors of the
Ren'Py project.
