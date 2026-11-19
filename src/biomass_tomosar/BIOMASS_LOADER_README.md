# BIOMASS TomoSAR — Guide to the original data loader

This guide documents the `src/biomass_tomosar/bm_data_loader.py` supplied for the project.

> **Quick start:** construct `bmStack(...)` to open annotations and LUTs; only call `stack.importSlcs(...)` when you are ready to load all the SAR measurements into RAM. For an initial image, the windowed-GDAL example below is safer.

## 1. What the loader reads

Each BIOMASS product is expected to have folders resembling:

```text
data/BIOMASS_STACK/
├── BIO_S2_STA__.../
│   ├── annotation_primary/          # reference annotation, when available
│   ├── annotation_coregistered/     # stack annotations and LUT
│   ├── annotation/                  # alternate, non-stack layout
│   └── measurement/
│       ├── <product-prefix>_i_abs.tiff
│       └── <product-prefix>_i_phase.tiff
└── ...                             # other acquisitions
```

The exact file prefix is formed in the original code using `product_directory_name[:70].lower()`. Do not rename the BIOMASS product folders or their internal files.

| Input | Read by | Purpose |
|---|---|---|
| XML annotation (`*_annot.xml`) | `lxml.etree` | Range/azimuth dimensions, sampling, timing, no-data value, primary geometry |
| NetCDF LUT (`*_lut.nc`) | `netCDF4` | Geometric/correction lookup tables, including the `flatteningPhaseScreen` when present |
| Amplitude TIFF (`*_i_abs.tiff`) | GDAL | Amplitude of the SAR signal for all bands/polarizations in the TIFF |
| Phase TIFF (`*_i_phase.tiff`) | GDAL | Phase in radians, combined with amplitude to form a complex SLC |

The source code expects four polarizations in its supplied usage example: **HH, HV, VH, VV**. Verify the actual TIFF band count and order in your products before relying on this convention.

## 2. What happens when you initialize `bmStack`

```python
from biomass_tomosar.bm_data_loader import bmStack
stack = bmStack(base_dirs)
```

The constructor:

1. Stores the ordered product paths (`stack.baseDirs`) and names (`stack.basenames`).
2. Sets the assumed radar carrier frequency to **435 MHz** and computes `stack.lamb = c / f` (about 0.689 m).
3. Calls `getAnots(self)` to parse XML annotations.
4. Calls `getLuts(self)` to open NetCDF LUTs and build one `bmLut` per product.
5. Reads primary image dimensions and builds range, azimuth and azimuth-time axes.
6. Leaves `stack._slcs` empty: **the full TIFF data have not been loaded**.

### Why the first path matters

The code checks for a specific XML file under **`base_dirs[0]/annotation_primary/`**. If found, it assumes it is handling a co-registered stack, then reads `annotation_coregistered/` for every product. Otherwise it falls back to `annotation/` for all products and prints a warning.

Therefore, `base_dirs[0]` should be the **verified** reference/primary product. Finding an `annotation_primary` directory is a useful test, but it is not, by itself, proof that a given product is the scientifically correct reference. The loader does not independently verify the master selection or baseline ordering.

**Do not simply use alphabetical sort as the final input order** without inspecting the products. Keep a separate chronological list if you will later use acquisition dates or baselines.

### Key properties after initialization

| Property | Meaning for co-registered stack |
|---|---|
| `stack.Ntracks` | Number of acquisition directories supplied |
| `stack.annot_prim` | Parsed primary annotation XML (`lxml` tree) |
| `stack.annot_coreg[i]` | Parsed annotation for product `i` |
| `stack.luts[i]` | `bmLut` object for product `i` |
| `stack.nli` | Number of azimuth lines |
| `stack.nsa` | Number of slant-range samples |
| `stack.rg` | 1D slant-range coordinates in metres |
| `stack.az` | 1D along-track azimuth coordinates in metres (relative origin) |
| `stack.t` | 1D azimuth times in seconds relative to a hard-coded reference epoch |
| `stack.noDataValue` | Value used to mark invalid pixels |
| `stack.lamb` | Radar wavelength in metres |

In the **non-stack fallback**, several geometric properties (`nli`, `nsa`, `rg`, `az`, `t`, `noDataValue`) become **lists**, one per product, rather than one common array/scalar.

**Time reference caution:** the original file hard-codes `2025-05-22T09:47:44` when converting time stamps. Keep this assumption visible if you process other datasets or compare with external timestamps.

## 3. First notebook: discover products and find the primary

Open the repository in WSL with `code .`, select the UV `.venv/bin/python` kernel in VS Code, and make sure `config/local.toml` contains:

```toml
[paths]
biomass_stack = "data/BIOMASS_STACK"
```

Then run:

```python
from pathlib import Path
from biomass_tomosar.paths import biomass_stack_dir

root = biomass_stack_dir()
products_by_name = sorted(p for p in root.glob("BIO*") if p.is_dir())
assert products_by_name, f"No BIOMASS product folders found under {root}"

for i, product in enumerate(products_by_name):
    prefix = product.name[:70].lower()
    primary_xml = product / "annotation_primary" / f"{prefix}_annot.xml"
    coreg_xml = product / "annotation_coregistered" / f"{prefix}_annot.xml"
    amp_tif = product / "measurement" / f"{prefix}_i_abs.tiff"
    phase_tif = product / "measurement" / f"{prefix}_i_phase.tiff"
    print(f"[{i}] {product.name}")
    print(f"    primary={primary_xml.is_file()} coreg={coreg_xml.is_file()} "
          f"amplitude={amp_tif.is_file()} phase={phase_tif.is_file()}")

candidates = [
    p for p in products_by_name
    if (p / "annotation_primary" / f"{p.name[:70].lower()}_annot.xml").is_file()
]
print("Primary-annotation candidates:", [p.name for p in candidates])
```

**Choose the primary deliberately:** if exactly one candidate exists and it matches the master specified in your stack documentation, you can use it. If there are several candidates, inspect their XML metadata / product documentation before choosing. The instruction that the “middle image is the master” should be verified, not automatically assumed from lexical sorting.

```python
# After confirming the primary product:
if len(candidates) != 1:
    raise ValueError("Choose the verified primary manually; candidates are ambiguous.")
primary = candidates[0]

# Keep the remaining products in a documented order.
ordered_products = [primary] + [p for p in products_by_name if p != primary]
base_dirs = [str(p) for p in ordered_products]  # original loader expects strings

from biomass_tomosar.bm_data_loader import bmStack
stack = bmStack(base_dirs)

print("Acquisitions:", stack.Ntracks)
print("Wavelength (m):", stack.lamb)
print("Azimuth lines:", stack.nli)
print("Range samples:", stack.nsa)
print("Slant range from/to (km):", stack.rg[0] / 1e3, stack.rg[-1] / 1e3)
print("Acquisition input order:", [p.name for p in ordered_products])
```

If several product folders legitimately contain a matching primary annotation, replace the `len(candidates)` check with an explicit, documented `primary = next(p for p in products_by_name if p.name == "EXACT_VERIFIED_PRODUCT_NAME")`.

> The `bmStack(...)` example above assumes the supplied data use the co-registered STA stack layout. If the loader falls back to non-stack mode, inspect its warning and the product directory structure before continuing.

## 4. NetCDF lookup tables: `bmLut` and `lutWrapper`

`stack.luts` has one `bmLut` per product. Its `get(...)` method returns a `lutWrapper` with three interfaces:

- `.nc`: the underlying `netCDF4` dataset, group or variable (no conversion).
- `.data`: the variable at its **native, usually coarser LUT resolution** as a NumPy array.
- `.upsampled`: interpolates a variable onto the full SAR image's azimuth × range grid using `scipy.interpolate.RegularGridInterpolator`.

Example — explore safely before loading a large array:

```python
lut = stack.luts[0]
ds = lut.get().nc
print("Root groups:", list(ds.groups))
print("Root variables:", list(ds.variables))

coreg = lut.get("coregistration").nc
print("Coregistration variables:", list(coreg.variables))

flat_lowres = lut.get("coregistration", "flatteningPhaseScreen").data
print("Flattening phase LUT shape:", flat_lowres.shape)
```

Example — interpolate to the entire image (**may allocate significant RAM**):

```python
# Only do this after checking stack.nli * stack.nsa and available RAM.
flat_full = lut.get("coregistration", "flatteningPhaseScreen").upsampled
print("Full-resolution phase shape:", flat_full.shape)  # expected (azimuth, range)
```

The interpolator uses azimuth-time and slant-range-time coordinates read from the LUT, handles ionosphere-specific grids when present, and uses **linear interpolation**. Out-of-bounds coordinates are permitted; the interpolator can return NaN there. The source does **not** interpret every LUT scientifically for you: you still need the product-format documentation to know the units, sign convention and meaning of each variable.

Do not call `.data` or `.upsampled` on a whole **group**; these properties are intended for a LUT **variable**.

## 5. How `importSlcs()` reconstructs the SLCs

The original loader loops over every product. For each it:

1. Opens `measurement/<prefix>_i_abs.tiff` and `measurement/<prefix>_i_phase.tiff` with `gdal.Open(...).ReadAsArray()`.
2. Replaces amplitudes and phases equal to `noDataValue` with zero.
3. Combines amplitude `A` and phase `φ` into a complex-valued image:

   \[S = A\,e^{j\phi}\]

4. If `terrain_flatten=True` **and** the co-registered-stack branch is active, additionally multiplies by the interpolated flattening screen:

   \[S_{\mathrm{flat}} = S\,e^{j\phi_{\mathrm{flat}}}\]

5. Appends the product to `stack._slcs` and converts the co-registered stack to a `numpy.complex64` array.

### Axes and polarization

For the stack layout, the original file's usage comments expect four polarizations in the order **HH, HV, VH, VV**.

| Call | Intended array axis order |
|---|---|
| `stack.importSlcs(..., swapaxes=False)` | `(acquisition, polarization, azimuth, range)` |
| `stack.importSlcs(..., swapaxes=True)` (default) | `(acquisition, polarization, range, azimuth)` |

This assumes the measurement TIFFs actually have the expected four bands. Always check `stack.slcs.shape`. **For TomoSAR notebooks, `swapaxes=False` is usually easier** because image slices follow `(azimuth, range)`.

Note: the non-stack branch uses `slc.T`, which reverses **all** axes of a NumPy array, not merely the last two. If using the non-stack fallback with multi-band TIFFs, prefer `swapaxes=False` and inspect shapes carefully.

### RAM warning

For a co-registered stack stored as `complex64`, the approximate final array size is:

\[\mathrm{bytes} = N_{\mathrm{tracks}} \times N_{\mathrm{pol}} \times N_{\mathrm{az}} \times N_{\mathrm{range}} \times 8\]

This excludes amplitude arrays, phase arrays, complex exponentials, upsampled screens, and copies. **Peak memory can be substantially larger**.

```python
n_pol = 4  # confirm using the TIFFs first
n_bytes = stack.Ntracks * n_pol * stack.nli * stack.nsa * 8
print(f"Final complex64 stack alone: {n_bytes / (1024**3):.2f} GiB")
```

Only when it fits comfortably in memory:

```python
# Full-stack operation: potentially many GiB in RAM!
stack.importSlcs(terrain_flatten=False, swapaxes=False)
slcs = stack.slcs
print("SLC shape:", slcs.shape)
print("SLC dtype:", slcs.dtype)

# HH amplitude, first acquisition; downsample for plotting
import numpy as np
import matplotlib.pyplot as plt
hh = slcs[0, 0, ::8, ::8]
plt.imshow(20 * np.log10(np.maximum(np.abs(hh), 1e-8)), cmap="gray")
plt.colorbar(label="Amplitude (dB, uncalibrated)")
plt.title("Acquisition 0 — HH amplitude")
plt.show()
```

`terrain_flatten=True` is a **phase correction using the supplied LUT**. It does not run SAR geocoding, estimate a DEM, or compute a TomoSAR reflectivity profile.

Avoid calling `importSlcs()` repeatedly on the same `bmStack`: the method appends to `self._slcs` rather than clearing it at entry. Create a fresh `bmStack` if you want to load again with different options.

## 6. Recommended first exploration: read only a small TIFF window

The original `importSlcs()` has **no region/window argument**. To view a small scene without loading all seven products, use GDAL to read a tile directly, applying the **same amplitude+phase reconstruction** as the loader. This is an inspection helper; it does not modify or replace your original `bm_data_loader.py`.

```python
from pathlib import Path
import numpy as np
from osgeo import gdal
import matplotlib.pyplot as plt


def read_slc_window(stack, track=0, xoff=0, yoff=0, width=512, height=512):
    product = Path(stack.baseDirs[track])
    prefix = product.name[:70].lower()
    amp_path = product / "measurement" / f"{prefix}_i_abs.tiff"
    phase_path = product / "measurement" / f"{prefix}_i_phase.tiff"

    amp_ds = gdal.Open(str(amp_path))
    phase_ds = gdal.Open(str(phase_path))
    if amp_ds is None or phase_ds is None:
        raise FileNotFoundError(f"Cannot open measurement TIFFs for {product}")
    if xoff + width > amp_ds.RasterXSize or yoff + height > amp_ds.RasterYSize:
        raise ValueError("Requested window exceeds raster dimensions")

    amplitude = amp_ds.ReadAsArray(xoff, yoff, width, height)
    phase = phase_ds.ReadAsArray(xoff, yoff, width, height)
    nodata = stack.noDataValue if stack._isStack else stack.noDataValue[track]
    amplitude = np.where(amplitude == nodata, 0, amplitude)
    phase = np.where(phase == nodata, 0, phase)
    return (amplitude * np.exp(1j * phase)).astype(np.complex64)


slc_tile = read_slc_window(stack, track=0, width=512, height=512)
print("Window shape:", slc_tile.shape)

# GDAL returns (bands, rows, columns) for a multi-band TIFF.
hh_tile = slc_tile[0] if slc_tile.ndim == 3 else slc_tile
plt.imshow(20 * np.log10(np.maximum(np.abs(hh_tile), 1e-8)), cmap="gray")
plt.colorbar(label="Amplitude (dB, uncalibrated)")
plt.title("First BIOMASS product — HH window (if band 0 is HH)")
plt.show()
```

`ReadAsArray(xoff, yoff, width, height)` reads a **subset** of the TIFF in GDAL pixel coordinates: `xoff` is the range/sample index and `yoff` the azimuth/line index in the conventional raster orientation. This helper **does not** apply the flattening phase. For first-look intensity plots that is typically fine, but for interferometric phase interpretation you must decide which phase corrections are needed.

If the TIFF is 4-band and the expected order is confirmed, use `slc_tile[0]` for HH, `[1]` for HV, `[2]` for VH, and `[3]` for VV.

## 7. Example: a simple interferogram on two small windows

An interferogram compares two co-registered **complex** SAR images. For the same polarization and pixel grid:

\[I_{01}(x,y) = S_0(x,y)\, S_1^*(x,y)\]

\[\phi_{01}(x,y)=\arg(I_{01}(x,y))\]

Changing the multiplication order reverses the phase sign. This is the **raw wrapped interferometric phase**, not a height map or a TomoSAR result.

```python
# Same spatial window and polarization in two coregistered products.
slc0 = read_slc_window(stack, track=0, xoff=0, yoff=0, width=512, height=512)
slc1 = read_slc_window(stack, track=1, xoff=0, yoff=0, width=512, height=512)

pol = 0  # HH if the product band order is HH, HV, VH, VV
s0 = slc0[pol] if slc0.ndim == 3 else slc0
s1 = slc1[pol] if slc1.ndim == 3 else slc1

interferogram = s0 * np.conj(s1)
wrapped_phase = np.angle(interferogram)
invalid = (np.abs(s0) == 0) | (np.abs(s1) == 0)
wrapped_phase = np.where(invalid, np.nan, wrapped_phase)

plt.imshow(wrapped_phase, cmap="twilight", vmin=-np.pi, vmax=np.pi)
plt.colorbar(label="Wrapped phase (rad)")
plt.title("Track 0 × conjugate(track 1), HH")
plt.show()
```

This example assumes both products are genuinely co-registered and your window addresses the same scene pixels. It does **not** apply the per-track `flatteningPhaseScreen` that `importSlcs(terrain_flatten=True)` would apply. It also does not estimate coherence or account for arbitrary per-acquisition phase offsets, ionosphere effects or baseline geometry.

## 8. Troubleshooting and source-code limitations

| Symptom | Likely cause / next check |
|---|---|
| `FileNotFoundError` for annotation XML | Verify the exact 70-character prefix, primary first, correct directory names and stack vs non-stack layout |
| `gdal.Open(...)` returns `None` | Missing/incomplete TIFF, path mismatch, or unsupported/corrupted raster |
| `cannot import name '_gdal_array'` | GDAL NumPy bindings not built/installed correctly; `gdal.ReadAsArray()` needs them even if `from osgeo import gdal` works |
| `Lut dimensions doesn't match` | The requested LUT does not match the coordinate grid sizes expected by `bmLut.upsample()` |
| `NaN` near edges of interpolated LUT | `bounds_error=False`: requested grid points can fall outside native LUT extent |
| Kernel killed during `importSlcs()` | Insufficient RAM; use a windowed read or downsample/crop earlier |
| `stack.slcs` gives `SLCs not imported` | Call `importSlcs()` first, or use the windowed GDAL helper |
| Unexpected `(N, P, range, azimuth)` array | Default `swapaxes=True` changes last two axes in stack mode |

**Important implementation assumptions:**

- `_isStack` is selected **only by existence of a primary XML file at the first product's expected path**; it does not independently check co-registration quality.
- `getAnots` / `getLuts` assume specific XML tags and NetCDF variable names.
- The fixed time origin `2025-05-22T09:47:44` is hard-coded in multiple places.
- Full-array interpolation creates a full meshgrid and is memory intensive.
- The code neither estimates perpendicular baselines/vertical wavenumbers nor implements SKPD phase processing, coherence estimation or TomoSAR inversion.
- The NetCDF datasets remain open as long as the `bmLut` objects reference them. When completely finished with the stack, `lut._lut.close()` for each LUT closes those underlying resources; `_lut` is a private implementation attribute, not a documented public API.

## 9. Suggested order for this project

1. Run `uv run python scripts/check_environment.py` and confirm GDAL's NumPy bindings work.
2. Confirm the seven product folders and their XML/TIFF filenames.
3. Verify the primary acquisition and document the acquisition ordering.
4. Instantiate `bmStack(...)` and inspect geometry and LUT variable names.
5. Plot one 512 × 512 SLC window from each of two acquisitions.
6. Form a first wrapped interferogram on those windows and check its visual structure.
7. Study the flattening screen, phase convention, co-registration metadata and baselines before interpreting interferometric phase quantitatively.
8. Only after checking memory, consider `stack.importSlcs(...)` for the full stack.

---

**Source of truth:** `src/biomass_tomosar/bm_data_loader.py` (original, unchanged). This document is an explanation and usage guide, not an implementation change or a validation against the physical dataset.
