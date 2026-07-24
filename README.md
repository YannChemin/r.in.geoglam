# r.in.geoglam

A GRASS GIS addon that lists and downloads [GEOGLAM Crop
Monitor](https://cropmonitor.org/) (AMIS and Early Warning) crop
condition maps, for any crop (or the multi-crop *Synthesis* product)
and any available monthly report.

The GEOGLAM tile server only serves pre-rendered cartography (a
handful of fixed legend colours), not the underlying condition codes.
`r.in.geoglam` reads the service's own legend, classifies every pixel
to the nearest legend colour, and outputs a categorical raster with the
GEOGLAM class names and colours attached — not the raw imagery.

| Code | Category | R:G:B | Colour |
|---|---|---|---|
| 1 | Exceptional | 0:143:201 | Blue |
| 2 | Favourable | 66:207:56 | Green |
| 3 | Watch | 245:239:0 | Yellow |
| 4 | Poor | 241:89:32 | Orange |
| 5 | Failure | 168:0:0 | Dark red |
| 6 | Out of Season | 130:130:130 | Gray |
| 7 | No Data | 130:65:0 | Brown |

Not every dataset uses every class (e.g. *Synthesis* has no *Failure*
class); only the classes present in a given service's legend are
attached to its output raster.

## Usage

List all crop/year/month datasets currently published by the server:

```sh
r.in.geoglam -l
```

Download a dataset, clipped to the current computational region
(default):

```sh
g.region n=40 s=30 e=40 w=20 res=0:06
r.in.geoglam crop=Synthesis year=2023 month=10 output=synthesis_2023_10
```

Download the whole extent of the dataset instead (current region is
left untouched):

```sh
r.in.geoglam -w crop=Maize year=2026 month=06 output=maize_2026_06_world
```

See [r.in.geoglam.md](r.in.geoglam.md) for the full manual, and
[INSTALL.md](INSTALL.md) for build/installation instructions.

## How it works

Internally, `r.in.geoglam` reuses core GRASS's
[r.in.wms](https://grass.osgeo.org/grass-stable/manuals/r.in.wms.html)
(driver `WMTS_GRASS`) to fetch and reproject the RGB tiles from the
service's [OGC WMTS](https://www.ogc.org/publications/standard/wmts/)
endpoint, classifies the RGB bands into GEOGLAM categories with
`r.mapcalc`, and attaches labels and colours with `r.category` and
`r.colors`.

## Requirements

- GRASS GIS (developed against 8.6.0dev)
- GDAL/OGR command-line utilities: `gdalwarp` and `gdaltransform`
- Python 3 standard library only (no extra Python packages)

## License

Public domain, see [LICENSE](LICENSE) (Unlicense).
