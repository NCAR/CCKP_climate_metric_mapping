# CMIP6 Climate Risk Mapping Pipeline

Builds multi-model ensemble median maps (historical, mid-century, end-century, and change) of CMIP6 climate indicators from the World Bank Climate Change Knowledge Portal (CCKP, 0.25 degree grid).

## Method summary

| Item | Definition |
|---|---|
| Historical period | 1990-2019 (CMIP6 `historical` for 1990-2014 blended with `ssp245` for 2015-2019) |
| Mid-century | 2040-2069 |
| End-century | 2070-2099 |
| Scenarios | ssp126, ssp245, ssp370, ssp585 |
| Field per model/period | 30-year time mean of the CCKP annual timeseries |
| Change | Future minus historical |
| Ensemble statistic (Stage 2) | Median across models. Change is the median of per-model differences, not the difference of medians |

## Setup

Python 3.9+ with:

```
xarray  netCDF4  numpy  matplotlib  cartopy
colormaps   # optional, needed for custom colormaps such as 'nice_gfdl'
```

Example:

```bash
conda install -c conda-forge xarray netcdf4 numpy matplotlib cartopy colormaps
```

Notes:
- Stage 1 downloads data from `https://wbg-cckp.s3.amazonaws.com/`. Run it on a machine with internet access (on HPC systems, typically a login node, not a compute node).
- Run all scripts from the directory that contains them. Default paths are relative to the working directory.

## Pipeline overview

```
(optional) list_cckp_models.py        what models exist?
        |
build_model_intermediates.py          Stage 1: per-model fields (9 NetCDFs per model)
        |
(optional) run_model_diagnostics.py   per-model sanity plots
        |
build_ensemble_medians.py             Stage 2: ensemble median maps + NetCDFs
```

Default directories:

| Purpose | Default |
|---|---|
| Raw CCKP download cache | `./cckp_cache/<variable>/` |
| Stage 1 intermediates | `./cmip6_model_intermediates/<variable>/` |
| Per-model diagnostic plots | `./cmip6_model_diagnostics/<variable>/` |
| Stage 2 ensemble medians | `./cmip6_ensemble_medians/<variable>/` |

## Step by step

### 0. (Optional) Explore what CCKP has

```bash
python3 list_cckp_models.py tas                          # models per scenario + common set
python3 list_cckp_models.py tas historical ssp245 ssp585 # custom scenario list
python3 list_cckp_files.py tas/ensemble-all-historical/  # raw file listing for a prefix
```

### 1. Build per-model intermediates (Stage 1)

```bash
python3 build_model_intermediates.py --variable tas
python3 build_model_intermediates.py --variable tas wsdi gsl
python3 build_model_intermediates.py --variable tas --limit 3     # quick test
```

| Option | Default | Meaning |
|---|---|---|
| `--variable` | `tas` | One or more CCKP variable codes (must be keys in `cmip6_variable_config.py`) |
| `--models` | all common models | Explicit model list, applied to every variable |
| `--limit N` | none | Only the first N common models (testing) |
| `--output-dir` | `./cmip6_model_intermediates` | Base output dir (variable subfolder added) |
| `--cache-dir` | `./cckp_cache` | Base cache dir (variable subfolder added) |

Details:
- Models are those with data for historical and all four SSPs (verified by HEAD request).
- Writes 9 files per model: 1 historical + 4 scenarios x 2 future periods.
- Resumable: any output file that already exists is skipped, so an interrupted run can simply be rerun.
- The resumability check only tests that the file exists. It does not test that the file is valid, so if a run was killed mid-write, delete any partial output file before rerunning.
- Exits non-zero if any job failed.

### 2. (Optional) Per-model diagnostic plots

Two-by-three sanity figures (historical, mid, end on top; mid minus hist and end minus hist below), one per model per scenario:

```bash
python3 run_model_diagnostics.py --variable tas
python3 run_model_diagnostics.py --variable tas --models access-cm2-r1i1p1f1 --scenarios ssp245 ssp585
```

| Option | Default | Meaning |
|---|---|---|
| `--variable` | `tas` | A single variable code |
| `--models` | all found on disk | Models to plot |
| `--scenarios` | all four SSPs | Scenarios to plot |
| `--intermediate-dir` | `./cmip6_model_intermediates` | Stage 1 base dir |
| `--output-dir` | `./cmip6_model_diagnostics` | Output base dir |

Models with any missing intermediate file for a scenario are skipped with a message.

### 3. Build ensemble medians (Stage 2)

```bash
python3 build_ensemble_medians.py --variable tas
python3 build_ensemble_medians.py --variable tas wsdi gsl
python3 build_ensemble_medians.py --variable tas --scenarios ssp245 ssp585 --periods mid-century
```

| Option | Default | Meaning |
|---|---|---|
| `--variable` | `tas` | One or more variable codes |
| `--scenarios` | all four SSPs | Scenarios to process |
| `--periods` | `mid-century end-century` | Future periods |
| `--models` | all models with a historical file | Restrict the ensemble (applies to every variable) |
| `--intermediate-dir` | `./cmip6_model_intermediates` | Stage 1 base dir |
| `--output-dir` | `./cmip6_ensemble_medians` | Output base dir |
| `--limits` | `auto` | `auto`: land-only 5th-95th percentile color limits; `config`: fixed `vmin_*`/`vmax_*` from the config |

Output data are global (land and ocean). No land mask is applied to the NetCDF fields; the maps hide the ocean with a cartopy ocean layer. Each NetCDF carries `spatial_coverage = "global (land and ocean); no land mask applied to data"`, and the build prints the missing-value fraction of every field it writes (expect ~0, warns above 0.10).

With `--limits auto`, the land mask is used only to choose color ranges. The median-panel range is pooled over the historical field and all 8 scenario/period futures, so it is the same whether or not `--scenarios`/`--periods` restrict what gets written (all 8 are still computed). Change-panel ranges are set per plot. Range shapes come from the config: `median_floor_zero`, `median_symmetric`, `change_sign`, or, if absent, are inferred from the fixed limits (`vmin_median == 0` floors at zero; `vmin_change == 0` is positive-only; `vmax_change == 0` is negative-only). Pin either range with `median_limits` / `change_limits` = `(lo, hi)`, using `None` for a side to keep it automatic. See `cmip6_plot_limits.py`.

`--limits auto` needs regionmask's Natural Earth land polygons. Fetch them once from a node with internet access:

```bash
python3 -c "import regionmask; regionmask.defined_regions.natural_earth_v5_0_0.land_50"
```

Per scenario and period, outputs are:
- `<var>_<scenario>_<midcentury|endcentury>_ensemble_median_map.png` (three-panel map)
- `<var>_<scenario>_<midcentury|endcentury>_ensemble_median.nc` (fields: `historical`, `future`, `change`)

Models are discovered from historical files only. If a discovered model lacks a scenario file, that scenario/period job fails with `FileNotFoundError`. Rerun Stage 1 for that model or pass `--models` without it.

## Code modules (not run directly)

| File | Role |
|---|---|
| `cmip6_loader.py` | CCKP URL building, download/cache with validation, period means, model discovery, Stage 1 filename convention |
| `cmip6_ensemble_stacking.py` | Stacks Stage 1 fields along a `model` dimension, computes ensemble medians |
| `cmip6_risk_mapper.py` | Three-panel plotting and NetCDF output; `resolve_cmap()` |
| `cmip6_model_diagnostic_plots.py` | 2x3 per-model diagnostic figure |
| `cmip6_plot_limits.py` | Automatic color limits from land-only percentiles (Stage 2) |
| `cmip6_variable_config.py` | Per-variable long name, units, colormaps, and color ranges |

## Adding or tuning a variable

Edit `CMIP6_VARIABLE_CONFIG` in `cmip6_variable_config.py`. Each entry needs:

```python
'tas': {
    'long_name': ..., 'description': ..., 'units': ...,
    'cmap_median': ..., 'vmin_median': ..., 'vmax_median': ...,   # panels a and b
    'cmap_change': ..., 'vmin_change': ..., 'vmax_change': ...,   # panel c
}
```

Colormap names are looked up in the `colormaps` package first, then matplotlib. Use a `('mpl', 'Spectral')` or `('custom', 'nice_gfdl')` tuple to force a source. Variables marked `NEEDS VERIFICATION` in the file (`sd`, `gslstart`, `gslend`) should be checked against CCKP metadata before use.

## Troubleshooting

- **Download fails or file is garbled:** delete the affected file from `./cckp_cache/<variable>/` (and any matching Stage 1 output), then rerun Stage 1.
- **`'xyz' not in CMIP6_VARIABLE_CONFIG`:** add the variable to the config file.
- **Colormap not found:** install the `colormaps` package, or change the config to a matplotlib colormap.
- **Maps look saturated or empty:** the `vmin`/`vmax` values in the config may not suit the variable. Retune them.
