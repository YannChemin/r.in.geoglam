# Installing r.in.geoglam

`r.in.geoglam` is a standard GRASS GIS Python-script addon (no
compiled component), built with the same `Script.make`/`Html.make`
pattern as other addons.

## Requirements

- A GRASS GIS source tree, e.g. `$HOME/dev/grass` (used as
  `MODULE_TOPDIR` below), or an installed GRASS GIS with `g.extension`.
- GDAL/OGR command-line utilities `gdalwarp` and `gdaltransform` (used
  by `r.in.wms` and by `r.in.geoglam` itself to reproject the dataset's
  full extent for the `-w` flag).
- Python 3 (standard library only, no extra packages required).

## Build against a GRASS source tree

```sh
git clone <this repository> $HOME/dev/r.in.geoglam
cd $HOME/dev/r.in.geoglam
make MODULE_TOPDIR=$HOME/dev/grass
```

This installs the script into
`$HOME/dev/grass/dist.<arch>/scripts/r.in.geoglam`, and generates the
HTML/Markdown manual page and man page alongside the other addons in
that dist tree.

Verify the install:

```sh
$HOME/dev/grass/bin.<arch>/grass --tmp-project XY --exec r.in.geoglam --help
```

(Use whichever `grass` launcher corresponds to that dist tree — GRASS
binaries are not on `PATH` outside of a running GRASS session.)

## Develop alongside grass-addons

To keep working standalone in this directory while also having the
module show up under `grass-addons`, symlink it into the matching
category:

```sh
ln -s $HOME/dev/r.in.geoglam $HOME/dev/grass-addons/src/raster/r.in.geoglam
```

Rebuilding after edits only requires re-running `make
MODULE_TOPDIR=$HOME/dev/grass` from this directory (or from
`$HOME/dev/grass-addons/src/raster/r.in.geoglam` via the symlink).

## Install with g.extension (from a published repository)

If this addon is published in a git repository reachable by GRASS,
it can instead be installed directly into a regular GRASS GIS install
with:

```sh
g.extension extension=r.in.geoglam url=<repository-url>
```

## Running the tests

```sh
python3 -m pytest tests/
```

The tests are pure-Python (dataset name parsing, legend PNG decoding,
classification expression building) and require neither a GRASS
session nor network access.
