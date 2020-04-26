[![made-with-python](https://img.shields.io/badge/Python%20Version-3.6%2B-informational?style=flat-square)](https://www.python.org/) [![Apache license](https://img.shields.io/github/license/madeddy/RpaKit?label=License&style=flat-square)](https://github.com/madeddy/RpaKit/blob/master/LICENSE) [![Generic badge](https://img.shields.io/badge/RpaKit_0.33.0_alpha-development-orange.svg?style=flat-square)](https://github.com/madeddy/RpaKit) [![RpaKit issues](https://img.shields.io/github/issues/madeddy/RpaKit?label=Issues&style=flat-square)](https://github.com/madeddy/RpaKit)
<!-- []([![HitCount](http://hits.dwyl.io/madeddy/RpaKit.svg)](http://hits.dwyl.io/madeddy/RpaKit))  -->

# RPA Kit
RPA Kit is a small application for decompressing RenPy archives.

It takes as input a archive file or a directory, which is then searched for legit
archives, and unpacks the content of them in a directory of choice.
Its also possible to read-only listing of the content or testing if the given archives
format type supported is.

## Usage
### Command line argument overview
```
rpakit [-e|-l|-t] [-o OUTPUT] [--verbose] [-version] [-h, --help] Target

positional arguments:
  Target                Directory path to search OR path of a RPA file to work on.

tasks:
  -e, --expand          Unpacks all stored files.
  -l, --list            Gives a listing of all stored files.
  -t, --test            Tests if archive(s) are a known format.
  -s, --simulate        Simulates the expand process.

optional arguments:
  -o, --outdir OUTPUT   Extracts to the given path instead of standard.
  --verbose             Amount of info output. 0:none, 2:much, default:1

  --version             Shows version information
  -h, --help            Print this help
```

### Example CLI usage

`rpa_kit.py -e /home/{USERNAME}/otherdir/archive.rpa`
Will extract every file from archive into the default output directory, making
subdirectories when necessary.

`rpa_kit.py -e -o unpacked /home/{USERNAME}/somedir/search_here`
Searches for RenPy archives in this directory and uncompresses them in the subdir
'unpacked'.

`rpa_kit.py -t c:/Users/{username}/my_folder/A123.rpa`
This will test the given archive for his format and if valide prints it out.

`rpa_kit.py -l -verbose 2 c:/Users/{username}/game_dir/blub8/`
Searches for RenPy archives in this directory and lists their file content in the
console. The verboseness was also set to highest level (tell everything).


### API

  TBD

(The API is very possible not final, so any description here would be a waste of time.)

### Motivation - _Why another RPA unpacker?_
This began in 2017 with a few lines of code and as another learning experience in Python
coding and to understand some more about RenPy internals. Basicly i extended _rpatool_
with some extras.

Over time i hit more walls with the codebase and the available apps for RPA work where of
limited usability to me. Unmaintained state, cumbersome extensibility and not working
functionality increasingly dissatisfied me.
Some whishes where:
- feeding it simply a directory with rpa files instead a single file
- support for more rpa formats
- easy extensibility for new rpa formats
- additional info output

Fall 2019 i began to do serious changes and extensions on _rpatools_ api. From there it
got fast out of control and i ended up with a completly rewritten app. Hopefully also
of use to other people.

## Legal
### License

__RPA Kit__ is licensed under Apache-2.0. See the [LICENSE](LICENSE) file for more details.

### Disclaimer

This program is intended for people who have the legal rights or the consent of
the authors to access or decompress the target files. Any illegal or otherwise
unindented usage of this software is highly discouraged and has here no support.

### Credits

This software was developed with some orientation on [RenPy's](github.com/renpy/renpy) and [rpatool's](github.com/shizmob/rpatool) code for
the work with RPA files.
Credits for the development of the RenPy archive format belong to the contributors of
the RenPy project.
