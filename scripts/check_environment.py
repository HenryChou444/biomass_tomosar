"""Check core dependencies, original GDAL loader, and local dataset path."""

import platform
import sys

import lxml
import netCDF4
import numpy
import scipy
from biomass_tomosar.paths import PROJECT_ROOT, biomass_stack_dir


def main() -> int:
    print("Python:", sys.version.split()[0], "on", platform.system())
    for name, mod in [
        ("NumPy", numpy),
        ("SciPy", scipy),
        ("netCDF4", netCDF4),
        ("lxml", lxml),
    ]:
        print(f"{name}: {getattr(mod, '__version__', 'available')}")

    try:
        from osgeo import gdal, gdal_array
        from biomass_tomosar.bm_data_loader import bmStack
    except ImportError as exc:
        print("GDAL/original loader import: FAILED")
        print(f"Details: {exc}")
        print("Install matching GDAL Python bindings; see README -> GDAL setup.")
        return 1

    print("GDAL:", gdal.VersionInfo("--version"))
    print("GDAL NumPy support: OK", gdal_array.__name__)
    print("Original loader import: OK", bmStack.__name__)
    print("Project root:", PROJECT_ROOT)
    data_dir = biomass_stack_dir()
    print("BIOMASS stack path:", data_dir)
    print("Data directory found:", data_dir.is_dir())
    if data_dir.is_dir():
        products = [p for p in data_dir.glob("BIO*") if p.is_dir()]
        print("Product directories:", len(products))
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
