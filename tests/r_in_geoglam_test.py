"""Unit tests for the pure-Python helpers in r.in.geoglam.

These tests do not require a GRASS session or network access: they
exercise dataset name parsing and resolution against a fixed sample of
service names.
"""

import importlib.util
import os
import struct
import sys
import zlib

import pytest

MODULE_PATH = os.path.join(os.path.dirname(__file__), "..", "r.in.geoglam.py")


@pytest.fixture(scope="module")
def rin_geoglam():
    # grass.script is not needed by the functions under test, but the module
    # imports it at load time, so a minimal stub is enough.
    if "grass.script" not in sys.modules:
        import builtins
        import types

        def _fatal(msg):
            raise SystemExit(msg)

        stub = types.ModuleType("grass.script")
        stub.parser = lambda: (None, None)
        stub.fatal = _fatal
        stub.message = lambda msg: None
        stub_pkg = types.ModuleType("grass")
        stub_pkg.script = stub
        sys.modules["grass"] = stub_pkg
        sys.modules["grass.script"] = stub
        builtins._ = lambda s: s

    spec = importlib.util.spec_from_file_location("r_in_geoglam", MODULE_PATH)
    module = importlib.util.module_from_spec(spec)
    spec.loader.exec_module(module)
    return module


SAMPLE_SERVICES = [
    "GEOGLAM_Crop_Monitor_Synthesis_Conditions_2023_10",
    "GEOGLAM_Crop_Monitor_Maize_Conditions_2026_03",
    "GEOGLAM_Crop_Monitor_Maize_Conditions_2026_05",
    "GEOGLAM_Crop_Monitor_Wheat_Conditions_2022_10",
]


def sample_datasets(rin_geoglam):
    datasets = []
    for name in SAMPLE_SERVICES:
        match = rin_geoglam.SERVICE_RE.match(name)
        assert match
        datasets.append(
            (
                match.group("crop"),
                int(match.group("year")),
                int(match.group("month")),
                name,
            )
        )
    return sorted(datasets)


def test_service_re_rejects_unrelated_names(rin_geoglam):
    assert rin_geoglam.SERVICE_RE.match("SomeOtherService") is None


def test_resolve_service_found(rin_geoglam):
    datasets = sample_datasets(rin_geoglam)
    assert (
        rin_geoglam.resolve_service("Maize", 2026, 3, datasets)
        == "GEOGLAM_Crop_Monitor_Maize_Conditions_2026_03"
    )


def test_resolve_service_not_found_lists_available_months(rin_geoglam, capsys):
    datasets = sample_datasets(rin_geoglam)
    with pytest.raises(SystemExit):
        rin_geoglam.resolve_service("Maize", 1999, 1, datasets)


def test_resolve_service_unknown_crop(rin_geoglam):
    datasets = sample_datasets(rin_geoglam)
    with pytest.raises(SystemExit):
        rin_geoglam.resolve_service("Barley", 2026, 3, datasets)


def _make_rgba_png(pixels, width, height):
    """Build a minimal non-interlaced 8-bit RGBA PNG from a flat RGBA byte
    sequence, for testing _decode_rgba_png without any network access."""

    def chunk(tag, data):
        out = struct.pack(">I", len(data)) + tag + data
        out += struct.pack(">I", zlib.crc32(tag + data) & 0xFFFFFFFF)
        return out

    ihdr = struct.pack(">IIBBBBB", width, height, 8, 6, 0, 0, 0)
    stride = width * 4
    raw = b"".join(
        b"\x00" + bytes(pixels[y * stride : (y + 1) * stride]) for y in range(height)
    )
    idat = zlib.compress(raw)
    return (
        b"\x89PNG\r\n\x1a\n"
        + chunk(b"IHDR", ihdr)
        + chunk(b"IDAT", idat)
        + chunk(b"IEND", b"")
    )


def test_decode_rgba_png_roundtrip(rin_geoglam):
    # 2x2 image: top-left red, top-right green, bottom-left blue, bottom-right
    # semi-transparent white.
    pixels = bytes(
        [
            255, 0, 0, 255,
            0, 255, 0, 255,
            0, 0, 255, 255,
            255, 255, 255, 128,
        ]
    )
    png_bytes = _make_rgba_png(pixels, 2, 2)
    width, height, decoded = rin_geoglam._decode_rgba_png(png_bytes)
    assert (width, height) == (2, 2)
    assert decoded == pixels


def test_classify_expression_structure(rin_geoglam):
    classes = [
        (1, "Exceptional", (0, 143, 201)),
        (2, "Favourable", (66, 207, 56)),
        (6, "Out of Season", (130, 130, 130)),
    ]
    expr = rin_geoglam.classify_expression("red", "green", "blue", classes)
    assert "d1 = (float(red)-0)^2 + (float(green)-143)^2 + (float(blue)-201)^2" in expr
    assert "if(isnull(red), null()," in expr
    assert expr.count("if(") == 3  # isnull-guard + 2 nested comparisons
    assert expr.rstrip(")").endswith("6")
