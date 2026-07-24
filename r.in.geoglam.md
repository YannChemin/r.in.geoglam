## DESCRIPTION

*r.in.geoglam* lists and downloads raster maps published by the
[GEOGLAM Crop Monitor](https://cropmonitor.org/) (AMIS and Early
Warning) ArcGIS tile server. The server publishes one map service per
crop (or the multi-crop *Synthesis* product) and per monthly report,
each available as an [OGC WMTS](https://www.ogc.org/publications/standard/wmts/)
tile layer. Internally *r.in.geoglam* reuses
*[r.in.wms](r.in.wms.md)* (driver **WMTS_GRASS**) to fetch and reproject
the RGB tiles.

The tile server only serves pre-rendered cartography (a handful of
fixed legend colours), not the underlying condition codes. *r.in.geoglam*
therefore reads the service's own ArcGIS legend (crop condition class
names and their exact swatch colours), classifies every pixel to the
nearest legend colour with *r.mapcalc*, and discards the intermediate
RGB bands. The output is a single categorical (CELL) raster with GEOGLAM
category labels (*r.category*) and the original legend colours
(*r.colors*) attached directly to the map — not the raw imagery.

Use the **-l** flag to list all crop/year/month combinations currently
published by the server:

```sh
r.in.geoglam -l
```

To download a dataset, set **crop**, **year**, **month** and
**output**. By default the data is clipped to the current
computational region:

```sh
g.region n=40 s=30 e=40 w=20 res=0:06
r.in.geoglam crop=Synthesis year=2023 month=10 output=synthesis_2023_10
```

Use the **-w** flag to instead download the whole extent of the
dataset (the current computational region is left untouched):

```sh
r.in.geoglam -w crop=Maize year=2026 month=06 output=maize_2026_06_world
```

## NOTES

Category codes are fixed across all datasets, in decreasing order of
severity, regardless of the order the server's legend happens to list
them in:

```
1  Exceptional
2  Favourable
3  Watch
4  Poor
5  Failure
6  Out of Season
7  No Data
```

Not every dataset uses every class (for example the *Synthesis*
product has no *Failure* class, which only applies to Early Warning
countries); only the classes actually present in a given service's
legend are attached to its output raster.

Classification is a nearest-legend-colour match per pixel; a small
number of anti-aliased boundary pixels between adjacent country
polygons may be assigned to a neighbouring class. Pixels outside any
rendered country polygon (ocean, no data tile) are NULL.

The list of available crop/year/month combinations, and each dataset's
legend, are retrieved live from the server, so newly published reports
(or legend changes) become available to *r.in.geoglam* without any
change to the module.

## REQUIREMENTS

*r.in.geoglam* requires *r.in.wms* and the
[gdalwarp](https://gdal.org/en/stable/programs/gdalwarp.html) and
[gdaltransform](https://gdal.org/en/stable/programs/gdaltransform.html)
utilities from the GDAL/OGR library.

## EXAMPLES

### List available datasets

```sh
r.in.geoglam -l
```

### Download wheat conditions for a region

```sh
g.region n=55 s=45 e=40 w=20 res=0:06
r.in.geoglam crop=Wheat year=2022 month=10 output=wheat_2022_10
```

### Download the global synthesis product

```sh
r.in.geoglam -w crop=Synthesis year=2023 month=10 output=synthesis_2023_10_world
```

## SEE ALSO

*[r.in.wms](r.in.wms.md), [r.category](r.category.md),
[r.colors](r.colors.md), [r.mapcalc](r.mapcalc.md)*

- [GEOGLAM Crop Monitor](https://cropmonitor.org/)
- [OGC WMTS](https://www.ogc.org/publications/standard/wmts/)

## AUTHOR

Yann Chemin
