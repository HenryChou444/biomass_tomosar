# BIOMASS TomoSAR — notebook-first repository


## Layout

```text
biomass_tomosar/
├── config/
│   └── local.example.toml              # copy to local.toml (ignored)
├── data/                                 # optional local radar products (ignored)
├── notebooks/
│   ├── 01_biomass_overview.ipynb         # active notebook
│   └── reference/
│       ├── 2023_mondah_tomosar.ipynb    # original, reading only
│       └── 2023_MAAP_PolInSAR_TomoSAR_solutions.ipynb
├── outputs/                              # generated plots/arrays (ignored)
├── references/
│   ├── README.md
│   └── bioIngest.yaml                    # original Conda export
├── scripts/
│   ├── check_environment.py
│   └── setup_wsl.sh
├── src/
│   └── biomass_tomosar/
│       ├── __init__.py
│       ├── paths.py
│       └── bm_data_loader.py            # ORIGINAL loader, unchanged
├── .gitattributes
├── .gitignore
├── .python-version
├── pyproject.toml
└── README.md
```

## 1. WSL / Ubuntu setup (recommended)

Install **uv**, Git, VS Code, and the VS Code **Python**, **Jupyter**, and **WSL** extensions first. Keep the repo in the WSL filesystem (for example `~/projects/biomass_tomosar`) for efficient Git/Python work. Dataset paths can point to `/mnt/d/...` if data is stored on a Windows drive.

From the repository folder:

```bash
bash scripts/setup_wsl.sh
```

The script does the following:

1. Installs Ubuntu's GDAL development library, command-line utility, and build tools using `apt`.
2. Detects the **native GDAL version** from `gdal-config --version`.
3. Runs `uv python install 3.12` and **`uv add "GDAL[numpy]==$(gdal-config --version)"`**. This records the matching Python bindings as a real project dependency in `pyproject.toml` and the generated `uv.lock`.
4. Runs `uv sync`, creates a machine-local `config/local.toml`, and checks the imports and configured dataset directory.

Unlike manually installing `GDAL` with `uv pip install`, the `uv add` approach lets normal `uv sync` and `uv run` preserve GDAL because it is part of the project dependencies. **GDAL is intentionally not pre-pinned in the starter**: WSL/Ubuntu installations may use different native libgdal versions. Pin the version during initial setup, then **commit the generated `pyproject.toml` and `uv.lock`**. Teammates using an equivalent Ubuntu/WSL GDAL version can simply `uv sync`. If their native version differs, align it with the project pin or coordinate a change—do not independently commit incompatible `uv.lock` changes.

Manual equivalent:

```bash
sudo apt update
sudo apt install -y libgdal-dev gdal-bin build-essential
uv python install 3.12
uv add "GDAL[numpy]==$(gdal-config --version)"
uv sync
cp config/local.example.toml config/local.toml
uv run python scripts/check_environment.py
```

GDAL's Python extension needs native GDAL headers and libraries. UV manages the **Python binding**, but does not install Ubuntu's C/C++ `libgdal`; that's why `apt` is still used. See the [GDAL Python installation documentation](https://gdal.org/en/stable/api/python/python_bindings.html).

### Use VS Code

From a **WSL** terminal inside the project, run:

```bash
code .
```

Open `notebooks/01_biomass_overview.ipynb`, choose **Select Kernel → Python Environments → `.venv/bin/python`** (sometimes listed as the project's virtual environment). The `ipykernel` dev dependency supports notebook execution inside VS Code. There is **no need to run or install JupyterLab**.

To add other packages later, use `uv add PACKAGE` (or `uv add --dev PACKAGE`), and commit `pyproject.toml` plus `uv.lock`.

### Native Windows notes

WSL is the recommended common denominator for all three Windows machines. **The GDAL version pinned against Ubuntu `libgdal` may not work unchanged on native Windows**, since the `GDAL` Python package may need compatible native libraries or a platform-specific binary wheel. If a teammate strongly prefers native Windows, use Conda-forge for GDAL and Python, and a separate workflow for the remaining dependencies; do not assume `uv sync` with the WSL GDAL pin will install on native Windows. The archived `references/bioIngest.yaml` provides context but contains Linux-specific exact builds and is not directly portable to Windows. Agree on the common environment before making the lockfile team-wide.

## 2. Configure where the 3 GB BIOMASS data lives

Do **not** commit raw SAR imagery. Share/download it outside Git. For example, in WSL:

```toml
# config/local.toml (ignored by Git)
[paths]
biomass_stack = "/mnt/d/datasets/BIOMASS_STACK"
mondah = "data/mondah"
```

Each teammate's `config/local.toml` is private. Paths may be absolute or relative to the repo root. If the `data/` directory is used, it is excluded from Git.

```python
from biomass_tomosar.paths import biomass_stack_dir
from biomass_tomosar.bm_data_loader import bmStack

stack_root = biomass_stack_dir()
# bmStack expects an ordered list of product directory strings,
# beginning with the product containing the primary annotation.
```

`bmStack(...)` reads metadata and LUTs; `stack.importSlcs()` loads the SLC data and can consume substantial RAM. Verify product order and the primary annotation before loading the stack. The original loader has a fixed time origin, which has **not** been adjusted or validated here.

## 3. Test and commit

```bash
uv run python scripts/check_environment.py

git init -b main
uv run nbstripout --install    # once per Git clone, optional but recommended
git add .
git status             # verify data/ and config/local.toml are not staged
git commit -m "Initialize BIOMASS TomoSAR project"

# After creating an empty remote repository:
git remote add origin <REMOTE_URL>
git push -u origin main
```

The `nbstripout` installation must run **after** `git init` (or after cloning a remote repo). It suppresses active notebook outputs in commits. Two course notebooks under `notebooks/reference/` are **excluded from that filter** to preserve the uploaded originals (including the new notebook's large outputs). Avoid running them; they are educational reference material and contain historical `ste_io`/kernel paths.

Commit notebooks, source code, `.python-version`, `pyproject.toml`, `uv.lock`, and example configuration. Do not commit imagery, derived arrays, virtual environments, personal paths, or output figures. Avoid concurrently editing the same `.ipynb` to reduce Git merge conflicts.
