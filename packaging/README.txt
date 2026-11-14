eza @VERSION@ for AROS
Build: @TARGET@ (@SYSTEM@)

eza is a modern replacement for List and Dir: colours, file-type icons, a
tree view and Git status for local repositories. This is a native AROS build
of eza 0.23.5 (https://github.com/eza-community/eza).

Requirements
------------
Limpet 0.7.0 or later (https://github.com/tomaszstaniak/limpet). eza lists
files in a console that reports its capabilities, as Limpet does. In the
standard Shell window (CON:) a listing is refused with return code 5; help
and --version work everywhere. Output sent to a file or a pipe is always
plain text, also with --color=always.

Installation
------------
With apkg:

    apkg install eza

By hand: unpack the archive into any drawer, for example Work:, and add
the Eza drawer to the Shell's search path, e.g. in S:User-Startup:

    Path Work:Eza ADD

Use
---
    eza                               the current drawer
    eza -l --icons --git --header     details, icons and Git status
    eza -T -L2 Work:                  a tree, two levels deep
    eza -1 --sort=size SYS:C          one name per line, sorted by size
    eza -l --time-style=long-iso SYS:
    eza --help                        all options

Notes
-----
- Permissions are the AmigaDOS bits hsparwed, not Unix rwx. Owner and group
  are shown as ? where the filesystem records none.
- --git and --git-repos read local repositories directly; no git program is
  needed. Remote operations are not available.
- Icons (--icons) and file links (--hyperlink) are shown only when the
  console reports that it can show them; otherwise the options are ignored.
  Limpet shows the icons with its own font at the default size of 13
  pixels. Ctrl+click on a linked name opens the file as a double-click in
  Workbench would.
- Names with bytes that are not valid UTF-8 are shown as \xNN.
- On AROS One, pipes in the Shell need "Set _mchar @@" first.
@PI@
Licence
-------
eza is under the EUPL 1.2 (LICENSE.txt). Copyright Christina Sørensen, eza
contributors, Benjamin Sago and the other copyright holders named in the
source. The licences of the libraries built into the program are in the
Licenses drawer; the modified source, the patches and the build record are
in Source.

AROS port: https://github.com/tomaszstaniak/aros-eza
