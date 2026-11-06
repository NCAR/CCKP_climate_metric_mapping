#!/usr/bin/env python3
"""
CMIP6 CCKP Data Loader
=======================
Loads CMIP6 climate model data (ensemble statistics) from the World Bank
Climate Change Knowledge Portal (CCKP), for use in historical/mid-century/
end-of-century risk mapping.

CCKP CMIP6 filename convention (from worldbank/climateknowledgeportal docs):
    product-variable-aggregationperiod-statistic_collection_modelwithscenario_
    category_percentile_timeperiod.nc

This module uses only the "timeseries" product (continuous annual values),
not CCKP's pre-built "climatology" files. CCKP's climatology files are
fixed at 20-year windows (2020-2039, 2040-2059, 2060-2079, 2080-2099), but
this project uses custom 30-year windows:

    historical:  1990-2019
    mid-century: 2040-2069
    end-century: 2070-2099

The CMIP6 historical experiment covers 1950-2014 and each SSP scenario
covers 2015-2100 as separate files. Any requested period that straddles
2014/2015 (like the 1990-2019 historical baseline here) must be built by
loading both files and concatenating the relevant years. Periods entirely
within 2015-2100 (mid-century, end-century) only need the scenario file.
"""

import hashlib
import tempfile
import urllib.request
import urllib.error
import warnings
from pathlib import Path

import xarray as xr

CCKP_S3_BASE = "https://wbg-cckp.s3.amazonaws.com/data/cmip6-x0.25"

# CCKP's historical experiment always covers this range as a timeseries file
CMIP6_HISTORICAL_TIMESERIES_PERIOD = "1950-2014"
# Each SSP scenario timeseries file covers this range
CMIP6_SCENARIO_TIMESERIES_PERIOD = "2015-2100"

# Custom 30-year analysis periods for this project (NOT CCKP's own
# pre-built climatology windows, which are 20 years).
STANDARD_PERIODS = {
    "historical": (1990, 2019),
    "mid-century": (2040, 2069),
    "end-century": (2070, 2099),
}


# =============================================================================
# LOW-LEVEL: DOWNLOAD / CACHE (shared pattern with climate_risk_mapper.py)
# =============================================================================

def _is_valid_netcdf(path):
    """Return True if the file at `path` opens cleanly as NetCDF."""
    try:
        with xr.open_dataset(path, decode_timedelta=False) as ds:
            list(ds.data_vars)  # touch it, forces at least a basic read
        return True
    except Exception:
        return False


def _download_with_validation(url, dest_path, max_attempts=2):
    """
    Download `url` to `dest_path`, validating the result actually opens as
    NetCDF. Retries once on a bad/incomplete download (e.g. a dropped
    connection mid-transfer, which can otherwise leave a truncated file
    that opens without error but has garbled contents/coordinates).
    Raises RuntimeError if it still isn't valid after retrying.
    """
    for attempt in range(1, max_attempts + 1):
        print(f"  Downloading{' (retry)' if attempt > 1 else ''}: {url}")
        urllib.request.urlretrieve(url, dest_path)
        if _is_valid_netcdf(dest_path):
            return
        print(f"  WARNING: downloaded file failed to open as valid NetCDF "
              f"(attempt {attempt}/{max_attempts})")
        if dest_path.exists():
            dest_path.unlink()
    raise RuntimeError(
        f"Failed to download a valid NetCDF file from {url} after "
        f"{max_attempts} attempt(s). The file may be corrupted on the "
        f"server, or the connection may be unreliable -- try again later."
    )


def _fetch_netcdf(url_or_path, cache_dir=None):
    """
    Open a NetCDF file from a local path or remote URL, with optional caching.

    Downloaded files are validated (confirmed to actually open as NetCDF)
    before being trusted -- a truncated/corrupted download is deleted and
    retried once rather than silently cached and reused. Existing cached
    files are also re-validated on each use, in case a previously-cached
    file was corrupted (e.g. from a network drop during an earlier run).

    Parameters
    ----------
    url_or_path : str
        URL or local file path to a NetCDF file
    cache_dir : str or Path, optional
        Directory to cache downloaded files

    Returns
    -------
    xarray.Dataset
    """
    is_url = url_or_path.startswith("http://") or url_or_path.startswith("https://")

    if not is_url:
        return xr.open_dataset(url_or_path, decode_timedelta=False)

    if cache_dir:
        cache_path = Path(cache_dir)
        cache_path.mkdir(parents=True, exist_ok=True)
        url_hash = hashlib.md5(url_or_path.encode()).hexdigest()[:16]
        cached_file = cache_path / f"cckp_{url_hash}.nc"

        if cached_file.exists():
            if _is_valid_netcdf(cached_file):
                print(f"  Using cached file: {cached_file}")
            else:
                print(f"  Cached file appears corrupted, re-downloading: {cached_file}")
                cached_file.unlink()
                _download_with_validation(url_or_path, cached_file)
                print(f"  Cached to: {cached_file}")
        else:
            _download_with_validation(url_or_path, cached_file)
            print(f"  Cached to: {cached_file}")
        return xr.open_dataset(cached_file, decode_timedelta=False)

    # No cache dir: download to a temp file, load into memory, clean up
    temp_dir = tempfile.mkdtemp()
    temp_file = Path(temp_dir) / "temp_data.nc"
    try:
        _download_with_validation(url_or_path, temp_file)
        ds = xr.open_dataset(temp_file, decode_timedelta=False).load()
    finally:
        if temp_file.exists():
            temp_file.unlink()
        try:
            Path(temp_dir).rmdir()
        except OSError:
            pass
    return ds


def _get_single_data_array(ds):
    """Extract the first (assumed only) data variable from a Dataset."""
    var_names = list(ds.data_vars)
    if not var_names:
        raise ValueError("No data variables found in dataset")
    return ds[var_names[0]]


# =============================================================================
# URL BUILDER
# =============================================================================

def build_timeseries_url(variable, scenario, statistic="mean", percentile=None,
                          model="ensemble-all", aggregation="annual"):
    """
    Build the CCKP S3 URL for a CMIP6 annual timeseries file.

    Parameters
    ----------
    variable : str
        CCKP variable code, e.g. 'tas', 'tasmax', 'r95ptot'
    scenario : str
        'historical' or an SSP code, e.g. 'ssp245'
    statistic : str
        Statistic in the filename stem (the aggregation of monthly ->
        annual values), typically 'mean'
    percentile : str, optional
        Ensemble statistic *across models*: 'median', 'p10', 'p90'.
        NOTE: for the ensemble-all timeseries product, CCKP does NOT
        provide a 'mean' option here -- only 'median' (plus the p10/p90
        spread bounds). Confirmed against real bucket listing 2026-07.
        For INDIVIDUAL models, CCKP only provides 'mean' (there's no
        cross-model spread for a single model), so if left as None this
        is auto-selected based on `model`: 'median' for ensemble-all,
        'mean' for any individual model. Pass an explicit value to
        override.
    model : str
        'ensemble-all' for the multi-model ensemble, or an individual
        model-variant string (e.g. 'access-cm2-r1i1p1f1')
    aggregation : str
        'annual', 'seasonal', or 'monthly'

    Returns
    -------
    str
        Full URL to the NetCDF file
    """
    if percentile is None:
        percentile = "median" if model == "ensemble-all" else "mean"

    if scenario == "historical":
        time_period = CMIP6_HISTORICAL_TIMESERIES_PERIOD
    else:
        time_period = CMIP6_SCENARIO_TIMESERIES_PERIOD

    model_scenario = f"{model}-{scenario}"
    filename = (
        f"timeseries-{variable}-{aggregation}-{statistic}_"
        f"cmip6-x0.25_{model_scenario}_timeseries_{percentile}_{time_period}.nc"
    )
    return f"{CCKP_S3_BASE}/{variable}/{model_scenario}/{filename}"


# =============================================================================
# LOADER
# =============================================================================

def load_annual_series(variable, start_year, end_year, scenario="ssp245",
                        statistic="mean", percentile=None, model="ensemble-all",
                        lat_range=(-60, 90), cache_dir=None):
    """
    Load a continuous annual CMIP6 series for an arbitrary year range,
    transparently blending the historical experiment (ends 2014) with an
    SSP scenario run (starts 2015) if the requested range straddles that
    boundary. Periods entirely on one side of 2014/2015 only load one file.

    Examples
    --------
    load_annual_series('tas', 1990, 2019, scenario='ssp245')
        -> blends historical (1990-2014) + ssp245 (2015-2019)
    load_annual_series('tas', 2040, 2069, scenario='ssp245')
        -> loads ssp245 only, sliced to 2040-2069
    load_annual_series('tas', 2070, 2099, scenario='ssp245')
        -> loads ssp245 only, sliced to 2070-2099

    Parameters
    ----------
    variable : str
        CCKP variable code, e.g. 'tas', 'tasmax'
    start_year, end_year : int
        Desired period, inclusive, e.g. 1990, 2019
    scenario : str
        SSP scenario to use for any portion of the period from 2015 onward
        (ignored entirely if end_year < 2015)
    statistic, percentile, model : str
        See build_timeseries_url
    lat_range : tuple
        Latitude subset to apply
    cache_dir : str or Path, optional
        Cache directory for downloaded files

    Returns
    -------
    xarray.DataArray
        Continuous annual data array spanning start_year-end_year
    """
    print(f"Loading CMIP6 annual series for '{variable}': "
          f"{start_year}-{end_year} (scenario: {scenario})")

    needs_historical = start_year < 2015
    needs_scenario = end_year >= 2015

    pieces = []

    if needs_historical:
        hist_url = build_timeseries_url(
            variable, scenario="historical", statistic=statistic,
            percentile=percentile, model=model
        )
        ds_hist = _fetch_netcdf(hist_url, cache_dir=cache_dir)
        da_hist = _get_single_data_array(ds_hist)
        hist_slice_end = min(end_year, 2014)
        da_hist = da_hist.sel(time=slice(str(start_year), str(hist_slice_end)))
        print(f"  Historical portion: {start_year}-{hist_slice_end} "
              f"({da_hist.sizes.get('time', '?')} years)")
        pieces.append(da_hist)

    if needs_scenario:
        scen_url = build_timeseries_url(
            variable, scenario=scenario, statistic=statistic,
            percentile=percentile, model=model
        )
        ds_scen = _fetch_netcdf(scen_url, cache_dir=cache_dir)
        da_scen = _get_single_data_array(ds_scen)
        scen_slice_start = max(start_year, 2015)
        da_scen = da_scen.sel(time=slice(str(scen_slice_start), str(end_year)))
        print(f"  Scenario portion ({scenario}): {scen_slice_start}-{end_year} "
              f"({da_scen.sizes.get('time', '?')} years)")
        pieces.append(da_scen)

    da = xr.concat(pieces, dim="time") if len(pieces) > 1 else pieces[0]

    # Sanity check: make sure we actually got a continuous run with no
    # gaps or overlaps between the historical and scenario files.
    n_years_expected = end_year - start_year + 1
    n_years_got = da.sizes.get("time", 0)
    if n_years_got != n_years_expected:
        warnings.warn(
            f"Expected {n_years_expected} years in '{variable}' series "
            f"({start_year}-{end_year}) but got {n_years_got}. Check for "
            f"gaps/overlaps between the historical and {scenario} files."
        )

    if "lat" in da.coords:
        da = da.sel(lat=slice(lat_range[0], lat_range[1]))

    return da


def calculate_period_mean(variable, start_year, end_year, scenario="ssp245",
                           statistic="mean", percentile=None, model="ensemble-all",
                           lat_range=(-60, 90), cache_dir=None):
    """
    Convenience wrapper: load an annual series for a period and return its
    time-mean field (lat, lon) -- i.e. the 30-year average for that period.
    """
    da = load_annual_series(
        variable, start_year, end_year, scenario=scenario,
        statistic=statistic, percentile=percentile, model=model,
        lat_range=lat_range, cache_dir=cache_dir
    )
    return da.mean(dim="time", skipna=True, keep_attrs=True)


# =============================================================================
# MODEL DISCOVERY (individual models, not ensemble-all)
# =============================================================================

CCKP_BUCKET_URL = "https://wbg-cckp.s3.amazonaws.com/"


def list_available_models(variable, scenario):
    """
    Query CCKP S3 for the individual models available for a given
    variable/scenario combination (ensemble-all excluded).

    Parameters
    ----------
    variable : str
        CCKP variable code, e.g. 'tas'
    scenario : str
        'historical' or an SSP code, e.g. 'ssp245'

    Returns
    -------
    list of str
        Sorted model names, e.g. ['access-cm2-r1i1p1f1', 'bcc-csm2-mr-r1i1p1f1', ...]
    """
    import urllib.request as _urlreq
    import xml.etree.ElementTree as _ET

    url = f"{CCKP_BUCKET_URL}?list-type=2&prefix=data/cmip6-x0.25/{variable}/&delimiter=/"
    with _urlreq.urlopen(url) as response:
        xml_data = response.read()

    ns = {"s3": "http://s3.amazonaws.com/doc/2006-03-01/"}
    root = _ET.fromstring(xml_data)
    prefixes = [cp.find("s3:Prefix", ns).text for cp in root.findall("s3:CommonPrefixes", ns)]
    names = [p.rstrip("/").split("/")[-1] for p in prefixes]

    suffix = f"-{scenario}"
    return sorted(
        name[: -len(suffix)]
        for name in names
        if name.endswith(suffix) and name != f"ensemble-all{suffix}"
    )


def _timeseries_file_exists(variable, scenario, model):
    """
    Check whether the actual timeseries NetCDF file exists for this
    variable/scenario/model, via a lightweight HTTP HEAD request (no
    download). A model's S3 folder can exist (and so show up in a
    CommonPrefixes listing) while only containing CCKP's pre-built
    'climatology'/'natvar' products and NOT the raw 'timeseries' product
    this pipeline needs -- seen in practice with taiesm1-r1i1p1f1's
    historical folder. Folder presence alone is not a reliable signal.
    """
    url = build_timeseries_url(variable, scenario, model=model)
    req = urllib.request.Request(url, method="HEAD")
    try:
        with urllib.request.urlopen(req) as response:
            return response.status == 200
    except urllib.error.HTTPError:
        return False


def get_common_models(variable, scenarios, verify_files=True):
    """
    Return the models that have data for ALL of the given scenarios --
    i.e. the safe set to use for multi-model panel plots so every model
    has every period/scenario needed.

    Parameters
    ----------
    variable : str
        CCKP variable code, e.g. 'tas'
    scenarios : list of str
        e.g. ['historical', 'ssp126', 'ssp245', 'ssp370', 'ssp585']
    verify_files : bool
        If True (default), also confirm the actual timeseries file exists
        for each model/scenario via a HEAD request, not just that the
        model's folder shows up in the bucket listing. Slower (one HEAD
        request per model per scenario) but catches models with an
        existing folder that's missing the needed product. Set False to
        skip this and just use folder-listing intersection (faster, but
        can include models that will 404 later).

    Returns
    -------
    list of str
        Sorted model names present in every scenario listed
    """
    per_scenario = {s: set(list_available_models(variable, s)) for s in scenarios}
    common = set.intersection(*per_scenario.values())

    if verify_files:
        verified = set()
        for model in sorted(common):
            if all(_timeseries_file_exists(variable, s, model) for s in scenarios):
                verified.add(model)
            else:
                print(f"  Excluding '{model}': folder exists but timeseries "
                      f"file missing for at least one scenario")
        common = verified

    return sorted(common)


# =============================================================================
# STAGE 1 INTERMEDIATE FILE HELPERS (shared naming convention)
# =============================================================================

STAGE1_PERIOD_LABELS = {"mid-century": "midcentury", "end-century": "endcentury"}


def stage1_filename(variable, model, scenario, period_key):
    """
    Build the Stage 1 intermediate filename for a given model/scenario/
    period, matching the convention used by build_model_intermediates.py.

    Parameters
    ----------
    variable : str
    model : str
    scenario : str
        Only used for non-historical periods (historical is scenario-
        independent in the filename, though it was blended using
        ssp245 internally).
    period_key : str
        'historical', 'mid-century', or 'end-century'

    Returns
    -------
    str
        Filename, e.g. 'tas_access-cm2-r1i1p1f1_ssp245_midcentury_2040-2069.nc'
    """
    start, end = STANDARD_PERIODS[period_key]
    year_tag = f"{start}-{end}"
    if period_key == "historical":
        return f"{variable}_{model}_historical_{year_tag}.nc"
    label = STAGE1_PERIOD_LABELS[period_key]
    return f"{variable}_{model}_{scenario}_{label}_{year_tag}.nc"


def discover_stage1_models(intermediate_dir, variable):
    """
    Find all models with a historical Stage 1 file present in
    `intermediate_dir` -- i.e. the models that actually succeeded in
    Stage 1, discovered from disk rather than requiring a hardcoded list.

    Returns
    -------
    list of str
        Sorted model names
    """
    import re
    hist_start, hist_end = STANDARD_PERIODS["historical"]
    pattern = re.compile(
        rf"^{re.escape(variable)}_(.+)_historical_{hist_start}-{hist_end}\.nc$"
    )
    models = []
    for f in sorted(Path(intermediate_dir).glob(f"{variable}_*_historical_*.nc")):
        m = pattern.match(f.name)
        if m:
            models.append(m.group(1))
    return sorted(set(models))


if __name__ == "__main__":
    # Quick smoke test / usage example (edit variable/scenario as needed).
    # This will attempt real downloads, so only run it when you have network
    # access and actually want to test against CCKP.
    import sys

    if len(sys.argv) > 1 and sys.argv[1] == "smoketest":
        var = "tas"
        scenario = "ssp245"

        hist_mean = calculate_period_mean(
            var, *STANDARD_PERIODS["historical"], scenario=scenario,
            cache_dir="./cckp_cache"
        )
        print(f"\nHistorical (1990-2019) mean: {float(hist_mean.mean().values):.3f}")

        mid_mean = calculate_period_mean(
            var, *STANDARD_PERIODS["mid-century"], scenario=scenario,
            cache_dir="./cckp_cache"
        )
        print(f"Mid-century (2040-2069) mean: {float(mid_mean.mean().values):.3f}")

        end_mean = calculate_period_mean(
            var, *STANDARD_PERIODS["end-century"], scenario=scenario,
            cache_dir="./cckp_cache"
        )
        print(f"End-century (2070-2099) mean: {float(end_mean.mean().values):.3f}")
