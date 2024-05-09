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

It takes as input a archive file or a directory, which is then searched for legit archives,
and unpacks the content of them in a directory of choice. Its also possible to read-only
listing of the content or testing if the given archives format type supported is.

## Usage
### Command line parameter overview
```
usage: rpakit.py [-h] (-e | -l | -t | -s) [-o OUTDIR] [--verbose level [0-2]] [--version] Target

Program for searching and unpacking RPA files.

positional arguments:
Target                Directory path (to search) OR rpa file path to unpack.

options:
-h, --help            show this help message and exit
-o OUTDIR, --outdir OUTDIR
Extracts to the given path instead to the default destination.
--verbose level [0-2]
Amount of info output. 0:none, 2:much, default:1
--version             show program's version number and exit

Tasks:
-e, --extract         Extracts all stored files and dirs.
-l, --list            Prints a listing of all stored files.
-t, --test            Tests if archive(s) are a known format.
-s, --simulate        Unpacks all stored files just temporary.

Default output dir is set to `{Target}/rpakit_out/`. Change with option -o.
```

### Example CLI usage
- rpakit.py -e -o unpacked /home/{USERNAME}/somedir/search_here
- rpakit.py -t /home/{USERNAME}/otherdir/file.rpa
- rpakit.py --extract c:/Users/{USERNAME}/my_folder/A123.rpa

`rpa_kit.py -e /home/{USERNAME}/otherdir/archive.rpa`
Will extract every file from archive into the default output directory, making
subdirectories when necessary.

`rpa_kit.py -e -o unpacked /home/{USERNAME}/somedir/search_here`
Searches RenPy archives in this directory and uncompresses them in the subdir
'unpacked'.

`rpa_kit.py -t c:/Users/{username}/my_folder/A123.rpa`
This will test the given archive for his format and if valide prints it out.

`rpa_kit.py -l -verbose 2 c:/Users/{username}/game_dir/blub8/`
Searches for RenPy archives in this directory and lists their file content in the
console. The verboseness was also set to highest level (tell everything).


### API
>The API is possible not final!

To provide the functionality of _**Rpa Kit**_ in other projects, the programs classes can be
included. Besides the code for CLI use, the core functionality is organized in four classes in
diamond inheritance.
Short overview of this classes:

#### class RkMain
Entry class to process args and executing the related methods. Parameters:
* `inpath`: _**str or pathlike, required**_
    The archive file-path to open or a directory path with archives.
    Absolute paths are preferred.
* `task`: _**str, required**_
    Sets the wanted task. Possible arguments are _exp_ (expand), _lst_ (listing),
    _tst_(testing), _sim_(simulate)
* `outdir`: _**str or pathlike, optional**_
    Sets the name of the output directory. If _None_ the default is used.
* `verbose`: _**int, optional**_
    Print info about what we are doing. Values: 0-2; Defaults to 1


#### class RkDepotWork
This class is the apps core for analyzing, testing and unpacking/decoding RPA files. All
needed inputs (depot, output path) are internaly providet.

This class holds also two important dicts with the informations about the RPA formats. Here
can be easily additional formats configured.
<!-- `_rpaformats = {"header":{'rpaid': ''
                          'desc': ''
                          'alias': ''}}`

`_rpaspecs = {{}}` -->

#### class RkPathwork
Support class for RPA Kit's path related tasks. Needet inputs (file-/dir path) are internaly
provided. If input is a dir it searches there for archives, checks and filters them and puts
them in a list. A archiv as input skips the search part.

If wanted, users can do the path preparations in some other way/place and provide the archives
itself to the other classes, instead with use of this one.

#### class RkCommon
Simple base class to provide some shared methods and variables for the other classes.


### Motivation - _Why this project?_
This began in 2017 as another learning experience in Python and and to understand some more
about RenPy internals. So i needed a project for this.

Some of the goals where:
- Input as a directory with rpa files instead just a file
- Easy extensibility for new formats
- Support for more rpa formats
- Additional info output

In the future there will possibly other changes or extensions. If time allows and motivation at
the same time on a high is, we copuld see:
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
