# RPA Kit
RPA Kit is a application which searches in a given path(if not archive file) Renpy
archives and uncompresses the content in a new subdirectory.
Listing without writing or testing the archiv is also possible.

## Command line usage
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

## Example usage

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


## API

  TBD

## Legal
### License

`RPA Kit` is licensed under the GPLv3. See the LICENSE file for more details.

### Disclaimer

This program is intended for people who have the legal rights or the consent of
the authors to access or decompress the target files. Any illegal or otherwise
unindented usage of this software is highly discouraged and has here no support.

### Credits

This software was developed with some orientation on "RenPy's" and "rpatool's" code
for work with RPA files.
Credits for the development of the RenPy archive format belong to the contributors
of the RenPy project.
