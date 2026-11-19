# Original reference files

- `bioIngest.yaml`: the supplied Linux Conda environment export, kept unchanged as a reference, not used by UV.
- `../notebooks/reference/2023_MAAP_PolInSAR_TomoSAR_solutions.ipynb`: ESA course notebook, preserved **byte-for-byte** (including existing outputs and metadata). Reference only; not run by setup.
- `../src/biomass_tomosar/bm_data_loader.py`: the original supplied BIOMASS STA loader, **unchanged**. It requires `from osgeo import gdal`.

Only the active `notebooks/01_biomass_overview.ipynb` is configured for the new `biomass_tomosar` package import. Reference notebooks are archival, so their original code, old paths, and kernel metadata are intentionally untouched.
