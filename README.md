[![made-with-python](https://img.shields.io/badge/Python%20Version-3.6%2B-informational)](https://www.python.org/) [![Apache license](https://img.shields.io/github/license/madeddy/RpaKit?label=License)](https://github.com/madeddy/RpaKit/blob/master/LICENSE) [![Generic badge](https://img.shields.io/badge/RpaKit_0.24.0_alpha-development-orange.svg)](https://shields.io/) ![RpaKit issues](https://img.shields.io/github/issues/madeddy/RpaKit)

[]([![HitCount](http://hits.dwyl.io/madeddy/RpaKit.svg)](http://hits.dwyl.io/madeddy/RpaKit))

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

### Motivation - Why another RPA unpacker?
This began in 2017 as a learning experience for Python coding and understanding
RenPy internals. Its was nothing mor as a wrapper for a third party RPA decompressor with
some extra functionality like feeding it simply a directory with rpa files.

In fall 2019 i noticed the changed usability respectively unmaintained state of the
available apps. There was also the cumbersome extensibility and not working functionality
which increasingly dissatisfied me.

I began at first to change and extend _rpatool_ for my own needs and from there it got
fast out of control. I ended up with a completly rewritten script. Hopefully also of use
to other people.

## Legal
### License

__RPA Kit__ is licensed under Apache-2.0. See the [LICENSE](LICENSE) file for more details.

### Disclaimer

This program is intended for people who have the legal rights or the consent of
the authors to access or decompress the target files. Any illegal or otherwise
unindented usage of this software is highly discouraged and has here no support.

### Credits

This software was developed with some orientation on [RenPy's](github.com/renpy/renpy) and [rpatool's](github.com/shizmob/rpatool) code
for work with RPA files.
Credits for the development of the RenPy archive format belong to the contributors
of the RenPy project.
