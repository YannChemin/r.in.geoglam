#!/usr/bin/env python3

"""
MODULE:    r.in.geoglam

AUTHOR(S): Yann Chemin

PURPOSE:   Lists and downloads GEOGLAM Crop Monitor raster maps (crop
           conditions and synthesis products) from the GEOGLAM ArcGIS
           WMTS tile service, for any available crop and month.

This is free and unencumbered software released into the public
domain. See the LICENSE file (Unlicense) for details.

SPDX-License-Identifier: Unlicense
"""

# %module
# % description: Lists and downloads GEOGLAM Crop Monitor raster maps from the GEOGLAM ArcGIS WMTS tile service.
# % keyword: raster
# % keyword: import
# % keyword: OGC web services
# % keyword: OGC WMTS
# % keyword: crop monitor
# % keyword: GEOGLAM
# %end

# %option
# % key: crop
# % type: string
# % description: Crop or synthesis product to download
# % options: Maize,Millet,Rice,Sorghum,Soybean,Synthesis,Wheat
# % required: no
# % guisection: Request
# %end

# %option
# % key: year
# % type: integer
# % description: Year of the crop condition report
# % required: no
# % guisection: Request
# %end

# %option
# % key: month
# % type: integer
# % description: Month of the crop condition report
# % options: 1-12
# % required: no
# % guisection: Request
# %end

# %option G_OPT_R_OUTPUT
# % required: no
# %end

# %flag
# % key: l
# % description: List available crop/year/month datasets and exit
# % suppress_required: yes
# %end

# %flag
# % key: w
# % description: Download the whole extent of the dataset instead of the current computational region
# %end

import base64
import json
import os
import re
import struct
import sys
import zlib
from urllib.request import urlopen
from urllib.error import URLError

import grass.script as gs

REST_BASE = "https://tiles.arcgis.com/tiles/qTQ6qYkHpxlu0G82/arcgis/rest/services"

SERVICE_RE = re.compile(
    r"^GEOGLAM_Crop_Monitor_(?P<crop>[A-Za-z]+)_Conditions_(?P<year>\d{4})_(?P<month>\d{2})$"
)

# GEOGLAM Crop Monitor condition classes, in decreasing order of severity.
# The category code assigned to each class (its position in this list, 1-based)
# is fixed regardless of the order the server's legend happens to return, so
# that the same condition always gets the same code across datasets.
CANONICAL_CLASSES = [
    "Exceptional",
    "Favourable",
    "Watch",
    "Poor",
    "Failure",
    "Out of Season",
    "No Data",
]


def _fetch_json(url):
    try:
        with urlopen(url, timeout=60) as resp:
            return json.load(resp)
    except URLError as error:
        gs.fatal(_("Unable to reach GEOGLAM server <%s>: %s") % (url, error))
    except json.JSONDecodeError as error:
        gs.fatal(_("Unable to parse server response from <%s>: %s") % (url, error))


def list_datasets():
    """Return a list of (crop, year, month, service_name) tuples for all
    datasets currently published by the GEOGLAM tile server."""
    data = _fetch_json(f"{REST_BASE}?f=json")
    datasets = []
    for service in data.get("services", []):
        match = SERVICE_RE.match(service["name"])
        if not match:
            continue
        datasets.append(
            (
                match.group("crop"),
                int(match.group("year")),
                int(match.group("month")),
                service["name"],
            )
        )
    return sorted(datasets)


def print_datasets(datasets):
    gs.message(_("Available GEOGLAM Crop Monitor datasets:"))
    print("crop|year|month|service_name")
    for crop, year, month, service_name in datasets:
        print(f"{crop}|{year}|{month:02d}|{service_name}")


def resolve_service(crop, year, month, datasets):
    service_name = f"GEOGLAM_Crop_Monitor_{crop}_Conditions_{year}_{month:02d}"
    if any(d[3] == service_name for d in datasets):
        return service_name

    available_months = sorted(
        f"{y}-{m:02d}" for c, y, m, _n in datasets if c == crop
    )
    if available_months:
        gs.fatal(
            _(
                "No GEOGLAM dataset found for crop=<%s> year=<%d> month=<%02d>.\n"
                "Available year-month combinations for crop=<%s>: %s\n"
                "Run with -l to list all available datasets."
            )
            % (crop, year, month, crop, ", ".join(available_months))
        )
    else:
        gs.fatal(
            _("No GEOGLAM dataset found for crop=<%s>. Run with -l to list all available datasets.")
            % crop
        )
    return None  # not reached


def get_service_info(service_name):
    url = f"{REST_BASE}/{service_name}/MapServer?f=json"
    data = _fetch_json(url)
    if "error" in data:
        gs.fatal(
            _("GEOGLAM server returned an error for service <%s>: %s")
            % (service_name, data["error"])
        )
    return data


def _decode_rgba_png(data):
    """Decode a non-interlaced, 8-bit RGBA PNG into (width, height, pixels).

    ``pixels`` is a bytes object of width*height*4 bytes (RGBA, row-major).
    Only the minimal PNG subset used by the ArcGIS legend swatch images
    is supported (color type 6, bit depth 8, no interlacing).
    """
    if data[:8] != b"\x89PNG\r\n\x1a\n":
        raise ValueError("not a PNG file")

    pos = 8
    idat = b""
    width = height = None
    while pos < len(data):
        length = struct.unpack(">I", data[pos : pos + 4])[0]
        chunk_type = data[pos + 4 : pos + 8]
        chunk = data[pos + 8 : pos + 8 + length]
        if chunk_type == b"IHDR":
            width, height, bitdepth, colortype, _comp, _filt, interlace = (
                struct.unpack(">IIBBBBB", chunk)
            )
            if bitdepth != 8 or colortype != 6 or interlace != 0:
                raise ValueError("unsupported PNG encoding for legend swatch")
        elif chunk_type == b"IDAT":
            idat += chunk
        elif chunk_type == b"IEND":
            break
        pos += 12 + length

    raw = zlib.decompress(idat)
    stride = width * 4
    pixels = bytearray(width * height * 4)
    prev = bytearray(stride)
    idx = 0
    for y in range(height):
        filter_type = raw[idx]
        idx += 1
        line = bytearray(raw[idx : idx + stride])
        idx += stride
        for x in range(stride):
            left = line[x - 4] if x >= 4 else 0
            up = prev[x]
            up_left = prev[x - 4] if x >= 4 else 0
            if filter_type == 0:
                predictor = 0
            elif filter_type == 1:
                predictor = left
            elif filter_type == 2:
                predictor = up
            elif filter_type == 3:
                predictor = (left + up) // 2
            elif filter_type == 4:
                p = left + up - up_left
                pa, pb, pc = abs(p - left), abs(p - up), abs(p - up_left)
                if pa <= pb and pa <= pc:
                    predictor = left
                elif pb <= pc:
                    predictor = up
                else:
                    predictor = up_left
            else:
                raise ValueError("unsupported PNG filter type")
            line[x] = (line[x] + predictor) & 0xFF
        pixels[y * stride : (y + 1) * stride] = line
        prev = line
    return width, height, bytes(pixels)


def get_legend(service_name):
    """Return {label: (r, g, b)} for the GEOGLAM legend of a service, decoded
    from the swatch icons in its ArcGIS MapServer legend."""
    url = f"{REST_BASE}/{service_name}/MapServer/legend?f=json"
    data = _fetch_json(url)
    try:
        entries = data["layers"][0]["legend"]
    except (KeyError, IndexError):
        gs.fatal(_("Unable to read legend for service <%s>") % service_name)

    legend = {}
    for entry in entries:
        label = entry["label"]
        png_bytes = base64.b64decode(entry["imageData"])
        try:
            width, height, pixels = _decode_rgba_png(png_bytes)
        except ValueError as error:
            gs.fatal(
                _("Unable to decode legend swatch for <%s>: %s") % (label, error)
            )
        cx, cy = width // 2, height // 2
        offset = (cy * width + cx) * 4
        r, g, b, a = pixels[offset : offset + 4]
        if a == 0:
            gs.fatal(
                _("Legend swatch for <%s> has a transparent center pixel") % label
            )
        legend[label] = (r, g, b)
    return legend


def classified_legend(service_name):
    """Return the ordered list of (code, label, (r, g, b)) classes that this
    service's legend actually defines, coded per CANONICAL_CLASSES order."""
    legend = get_legend(service_name)
    classes = []
    for code, label in enumerate(CANONICAL_CLASSES, start=1):
        if label in legend:
            classes.append((code, label, legend[label]))
    if not classes:
        gs.fatal(
            _("None of the expected GEOGLAM classes were found in the legend of <%s>")
            % service_name
        )
    return classes


def classify_expression(red, green, blue, classes):
    """Build an r.mapcalc expression classifying (red, green, blue) bands into
    the nearest-color GEOGLAM class from ``classes``."""
    dist_names = [f"d{code}" for code, _label, _rgb in classes]
    assigns = ", ".join(
        f"{name} = (float({red})-{r})^2 + (float({green})-{g})^2 + (float({blue})-{b})^2"
        for name, (_code, _label, (r, g, b)) in zip(dist_names, classes)
    )

    best_expr = str(classes[-1][0])
    for (code, _label, _rgb), name in list(zip(classes, dist_names))[-2::-1]:
        best_expr = f"if({name} == m, {code}, {best_expr})"

    return (
        f"eval({assigns}, m = min({', '.join(dist_names)}), "
        f"if(isnull({red}), null(), {best_expr}))"
    )


def whole_extent_region(full_extent, srs, env):
    """Compute a computational region (n, s, e, w, rows, cols) covering the
    dataset's full extent, reprojected into the current project's CRS."""
    xmin, ymin = full_extent["xmin"], full_extent["ymin"]
    xmax, ymax = full_extent["xmax"], full_extent["ymax"]

    proj_location = gs.read_command(
        "g.proj", format="proj4", flags="pf", env=env
    ).strip()

    corners_in = f"{xmin} {ymin}\n{xmax} {ymin}\n{xmax} {ymax}\n{xmin} {ymax}\n"
    try:
        result = gs.Popen(
            ["gdaltransform", "-s_srs", f"EPSG:{srs}", "-t_srs", proj_location],
            stdin=gs.PIPE,
            stdout=gs.PIPE,
            stderr=gs.PIPE,
        )
        stdout, stderr = result.communicate(input=corners_in)
    except OSError as error:
        gs.fatal(_("Unable to run gdaltransform: %s") % error)

    if result.returncode != 0:
        gs.fatal(_("gdaltransform failed: %s") % stderr)

    eastings, northings = [], []
    for line in stdout.splitlines():
        if not line.strip():
            continue
        e, n = line.split()[:2]
        eastings.append(float(e))
        northings.append(float(n))

    n, s, e, w = max(northings), min(northings), max(eastings), min(eastings)

    width, height = e - w, n - s
    cols = 2000
    rows = max(1, round(cols * height / width)) if width else cols

    return {"n": n, "s": s, "e": e, "w": w, "rows": rows, "cols": cols}


def main():
    if flags["l"]:
        print_datasets(list_datasets())
        return 0

    crop = options["crop"]
    year = options["year"]
    month = options["month"]
    output = options["output"]

    if not (crop and year and month and output):
        gs.fatal(
            _(
                "Options <crop>, <year>, <month> and <output> are required "
                "(unless -l is used to list available datasets)."
            )
        )

    year = int(year)
    month = int(month)

    datasets = list_datasets()
    service_name = resolve_service(crop, year, month, datasets)

    service_info = get_service_info(service_name)
    srs = service_info["tileInfo"]["spatialReference"].get(
        "latestWkid", service_info["tileInfo"]["spatialReference"]["wkid"]
    )
    wmts_url = f"{REST_BASE}/{service_name}/MapServer/WMTS?"

    env = None
    if flags["w"]:
        env = os.environ.copy()
        region_manager = gs.RegionManager(env=env)
        region = whole_extent_region(service_info["fullExtent"], srs, env)
        region_manager.activate()
        region_manager.set_region(**region)

    gs.message(_("Reading GEOGLAM legend for <%s>...") % service_name)
    classes = classified_legend(service_name)

    gs.message(_("Fetching <%s>...") % service_name)

    tmp_bands = gs.append_uuid(f"tmp_{output}")
    try:
        gs.run_command(
            "r.in.wms",
            flags="b",
            output=tmp_bands,
            driver="WMTS_GRASS",
            url=wmts_url,
            layers=service_name,
            styles="default",
            srs=srs,
            format="png",
            env=env,
            overwrite=gs.overwrite(),
        )

        gs.message(_("Classifying into GEOGLAM crop condition categories..."))
        expression = "{output} = {expr}".format(
            output=output,
            expr=classify_expression(
                f"{tmp_bands}.red", f"{tmp_bands}.green", f"{tmp_bands}.blue", classes
            ),
        )
        gs.mapcalc(expression, env=env, overwrite=gs.overwrite())
    finally:
        gs.run_command(
            "g.remove",
            flags="f",
            type="raster",
            pattern=f"{tmp_bands}.*",
            quiet=True,
        )
        if flags["w"]:
            region_manager.deactivate()

    category_rules = "\n".join(f"{code}:{label}" for code, label, _rgb in classes)
    gs.write_command(
        "r.category", map=output, rules="-", separator=":", stdin=category_rules
    )

    color_rules = "\n".join(
        f"{code} {r}:{g}:{b}" for code, _label, (r, g, b) in classes
    )
    gs.write_command("r.colors", map=output, rules="-", stdin=color_rules)

    gs.raster_history(output, overwrite=True)
    gs.run_command(
        "r.support",
        map=output,
        source1="GEOGLAM Crop Monitor (GEOGLAM AMIS / Early Warning)",
        source2=service_name,
        description=f"GEOGLAM Crop Monitor {crop} conditions {year}-{month:02d}",
    )

    gs.message(_("Dataset <%s> imported as <%s>") % (service_name, output))
    return 0


if __name__ == "__main__":
    options, flags = gs.parser()
    sys.exit(main())
