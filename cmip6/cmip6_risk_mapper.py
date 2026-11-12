#!/usr/bin/env python3
"""
CMIP6 Risk Map Plotting
=========================
Builds the three-panel figures (historical / future period / change) and
NetCDF outputs for CMIP6 ensemble-median climate risk maps, using the
periods and data loaded via cmip6_loader.py and the styling defined in
cmip6_variable_config.py.

Change is always defined as Future - Historical.
"""

from datetime import datetime
from pathlib import Path
import warnings

import numpy as np
import xarray as xr
import matplotlib.pyplot as plt
import matplotlib.ticker as mticker
import cartopy.crs as ccrs
import cartopy.feature as cfeature
from cartopy.mpl.gridliner import LONGITUDE_FORMATTER, LATITUDE_FORMATTER

# Optional custom colormap package (e.g. provides NCL-style colormaps like
# 'nice_gfdl'). Falls back to treating cmap names as standard matplotlib
# colormaps if this package isn't installed.
try:
    import colormaps as cmaps
    HAS_CUSTOM_CMAPS = True
except ImportError:
    HAS_CUSTOM_CMAPS = False
    warnings.warn(
        "Custom 'colormaps' package not found; any cmap name in "
        "CMIP6_VARIABLE_CONFIG that isn't a standard matplotlib colormap "
        "(e.g. 'nice_gfdl') will fail. Install it with: "
        "pip install colormaps --break-system-packages"
    )


def resolve_cmap(spec):
    """
    Resolve a colormap spec from CMIP6_VARIABLE_CONFIG to something
    matplotlib can actually use.

    Two forms are supported:

    1. Plain string, e.g. 'nice_gfdl' or 'Spectral' -- AUTO-DETECTED:
       checks the custom `colormaps` package first; if not found there
       (or the package isn't installed), falls back to treating the name
       as a standard matplotlib colormap. This is the common case and
       what nearly every variable in CMIP6_VARIABLE_CONFIG uses.

    2. Explicit ('source', 'name') tuple -- use this ONLY if you need to
       force a specific source, e.g. because a name happens to exist in
       both matplotlib and the custom package and you want to guarantee
       which one you get:
         ('custom', 'nice_gfdl')  -- must come from the colormaps package
         ('mpl', 'Spectral')      -- must be matplotlib's built-in, even
                                      if a custom colormap of the same
                                      name also exists
       This form raises a clear error immediately if the requested source
       doesn't have that colormap, rather than silently falling back.

    This is config-driven and per-panel: unlike the original ERA5 script,
    it does NOT force a custom colormap onto every variable/panel just
    because the package is available -- only variables/panels that
    explicitly name a custom colormap get one.

    Parameters
    ----------
    spec : str or tuple
        Colormap name (auto-detected) or ('source', 'name') tuple (explicit)

    Returns
    -------
    str or matplotlib.colors.Colormap
        Either a name (matplotlib built-in) or a resolved Colormap object
    """
    if isinstance(spec, tuple):
        source, name = spec
        if source == 'custom':
            if not HAS_CUSTOM_CMAPS:
                raise ValueError(
                    f"Colormap '{name}' requested from the custom 'colormaps' "
                    f"package, but that package isn't installed."
                )
            if not hasattr(cmaps, name):
                raise ValueError(
                    f"Colormap '{name}' not found in the custom 'colormaps' package."
                )
            return getattr(cmaps, name)
        elif source in ('mpl', 'matplotlib'):
            return name  # let matplotlib resolve it directly; no custom lookup
        else:
            raise ValueError(
                f"Unknown colormap source '{source}' (expected 'custom' or 'mpl')"
            )

    # Plain string: auto-detect, custom package first
    if HAS_CUSTOM_CMAPS and hasattr(cmaps, spec):
        return getattr(cmaps, spec)
    return spec


# =============================================================================
# CHANGE CALCULATION
# =============================================================================

def calculate_change(historical_field, future_field):
    """
    Compute the change field: Future - Historical.

    Parameters
    ----------
    historical_field : xarray.DataArray
        Historical period mean/median field (lat, lon)
    future_field : xarray.DataArray
        Future period (mid-century or end-century) mean/median field (lat, lon)

    Returns
    -------
    xarray.DataArray
        future_field - historical_field, on the shared (lat, lon) grid
    """
    change = future_field - historical_field
    change.name = "change"
    change.attrs = {}  # subtraction attrs are unreliable/misleading; set explicitly downstream
    return change


# =============================================================================
# MAP HELPERS (same conventions as climate_risk_mapper.py)
# =============================================================================

def setup_map_axes(ax):
    """Set up cartopy map with standard features (coastlines, borders, gridlines)."""
    xticks = np.arange(-180, 181, 90)
    yticks = np.arange(-60, 91, 30)

    ax.add_feature(cfeature.OCEAN, facecolor='gainsboro', zorder=2)
    ax.add_feature(cfeature.COASTLINE.with_scale('110m'), linewidths=1.2)
    ax.add_feature(cfeature.BORDERS.with_scale('110m'), linewidths=0.5)

    gl = ax.gridlines(draw_labels=True, crs=ccrs.PlateCarree(),
                       x_inline=False, y_inline=False, color='white',
                       alpha=0.2)
    gl.xlocator = mticker.FixedLocator(xticks)
    gl.ylocator = mticker.FixedLocator(yticks)
    gl.xformatter = LONGITUDE_FORMATTER
    gl.yformatter = LATITUDE_FORMATTER
    gl.top_labels = False
    gl.right_labels = False

    return ax, gl


def add_colorbar(fig, ax, mappable, label):
    """Add a colorbar to the right of an axes, matched to its height."""
    pos = ax.get_position()
    cbar_ax = fig.add_axes([pos.x1 + 0.02, pos.y0 + 0.02, 0.02, pos.y1 - pos.y0 - 0.04])
    fig.colorbar(mappable, cax=cbar_ax, orientation='vertical', label=label)


# =============================================================================
# PLOTTING
# =============================================================================

def create_cmip6_risk_map(historical_field, future_field, change_field, config,
                           output_path, future_label, historical_period,
                           future_period, scenario,
                           median_lims=None, change_lims=None):
    """
    Create a three-panel figure: (a) historical median, (b) future period
    median, (c) change (future - historical).

    Parameters
    ----------
    historical_field, future_field, change_field : xarray.DataArray
        (lat, lon) fields from cmip6_loader.calculate_period_mean() and
        calculate_change()
    config : dict
        Entry from CMIP6_VARIABLE_CONFIG for this variable
    output_path : str or Path
        Output figure path
    future_label : str
        e.g. "Mid-Century" or "End-of-Century", used in panel (b)'s title
    historical_period, future_period : tuple
        (start_year, end_year) for each period, used in titles
    scenario : str
        SSP scenario code, e.g. 'ssp245', used in panel (b)/(c) titles
    median_lims, change_lims : (vmin, vmax) tuple, optional
        Color limits for panels (a)/(b) and (c). If None, the fixed
        vmin_*/vmax_* values from config are used.

    Returns
    -------
    matplotlib.figure.Figure
    """
    print(f"\nCreating CMIP6 risk map figure: {output_path}")

    if median_lims is None:
        median_lims = (config['vmin_median'], config['vmax_median'])
    if change_lims is None:
        change_lims = (config['vmin_change'], config['vmax_change'])

    vis_data = [historical_field, future_field, change_field]
    vmins = [median_lims[0], median_lims[0], change_lims[0]]
    vmaxs = [median_lims[1], median_lims[1], change_lims[1]]
    cmaps_list = [
        resolve_cmap(config['cmap_median']),
        resolve_cmap(config['cmap_median']),
        resolve_cmap(config['cmap_change']),
    ]
    labels = [config['units'], config['units'], config['units']]

    hist_start, hist_end = historical_period
    fut_start, fut_end = future_period

    titles = [
        f"a) Historical {config['long_name']} ({hist_start}-{hist_end})",
        f"b) {future_label} {config['long_name']} ({fut_start}-{fut_end}, {scenario})",
        f"c) Change: {future_label} \u2212 Historical ({scenario})",
    ]

    pcrs = ccrs.Robinson()
    tcrs = ccrs.PlateCarree()

    fig, axes = plt.subplots(3, 1, figsize=(6, 8.3),
                              subplot_kw={"projection": pcrs})
    fig.subplots_adjust(left=0.03, right=0.90, top=0.95,
                         bottom=0.05, hspace=0.25)

    for i, ax in enumerate(axes):
        lon = vis_data[i].lon.values
        lat = vis_data[i].lat.values
        X, Y = np.meshgrid(lon, lat)

        cf = ax.pcolormesh(X, Y, vis_data[i],
                            vmin=vmins[i], vmax=vmaxs[i],
                            cmap=cmaps_list[i],
                            transform=tcrs)

        setup_map_axes(ax)
        add_colorbar(fig, ax, cf, labels[i])
        ax.set_title(titles[i], loc='left', fontsize=10)

    plt.savefig(output_path, dpi=300, bbox_inches='tight')
    print(f"  Figure saved successfully")

    return fig


# =============================================================================
# NETCDF OUTPUT
# =============================================================================

def create_cmip6_netcdf(historical_field, future_field, change_field, config,
                         output_path, future_label, historical_period,
                         future_period, scenario, variable,
                         source_mode="ensemble-all", models=None,
                         historical_scenario=None):
    """
    Save historical / future / change fields to a NetCDF file with
    comprehensive metadata, matching the conventions of the ERA5 script's
    create_output_netcdf().

    The provenance metadata (source, ensemble_statistic, and each
    variable's 'method' attribute) depends on how the fields were built,
    which is set by `source_mode`:

      'ensemble-all'      CCKP's pre-computed multi-model median timeseries
                          (run_cmip6_risk_mapper.py). Change is the
                          difference of two ensemble medians.
      'individual-models' Stage 2 (build_ensemble_medians.py): median across
                          individual models of each model's 30-year mean.
                          Change is the median across models of per-model
                          differences (NOT difference of medians).
      'single-model'      One individual model, no ensemble statistic
                          (test_single_model.py).

    Parameters
    ----------
    historical_field, future_field, change_field : xarray.DataArray
        (lat, lon) fields
    config : dict
        Entry from CMIP6_VARIABLE_CONFIG for this variable
    output_path : str or Path
        Output NetCDF path
    future_label : str
        e.g. "mid-century" or "end-century"
    historical_period, future_period : tuple
        (start_year, end_year) for each period
    scenario : str
        SSP scenario code of the future period, e.g. 'ssp245'
    variable : str
        CCKP variable code, e.g. 'tas'
    source_mode : str
        'ensemble-all', 'individual-models', or 'single-model' (see above)
    models : list of str, optional
        Model names. For 'individual-models', the models in the ensemble
        (recorded as 'n_models' and 'models'). For 'single-model', a
        one-element list (or the model name as a string).
    historical_scenario : str, optional
        Scenario used for the 2015 onward portion of the historical period.
        Defaults to `scenario`, which matches run_cmip6_risk_mapper.py and
        test_single_model.py. Stage 2 (build_ensemble_medians.py) must pass
        'ssp245', because Stage 1 historical fields always blend with
        ssp245 regardless of the future scenario being processed.
    """
    valid_modes = ("ensemble-all", "individual-models", "single-model")
    if source_mode not in valid_modes:
        raise ValueError(f"source_mode must be one of {valid_modes}, got '{source_mode}'")

    if isinstance(models, str):
        models = [models]
    if source_mode == "individual-models" and not models:
        raise ValueError("source_mode='individual-models' requires `models`")
    if source_mode == "single-model" and (not models or len(models) != 1):
        raise ValueError("source_mode='single-model' requires exactly one model in `models`")

    if historical_scenario is None:
        historical_scenario = scenario

    print(f"\nCreating CMIP6 output NetCDF: {output_path}")

    hist_start, hist_end = historical_period
    fut_start, fut_end = future_period
    description = config.get('description', config['long_name'])

    hist_blend = (
        f"blended from the CMIP6 historical experiment ({hist_start}-2014) and "
        f"the {historical_scenario} scenario (2015-{hist_end})"
    )

    if source_mode == "individual-models":
        n_models = len(models)
        hist_method = (
            f"Median across {n_models} individual CMIP6 models of each model's "
            f"{hist_start}-{hist_end} time mean, {hist_blend}"
        )
        fut_method = (
            f"Median across {n_models} individual CMIP6 models of each model's "
            f"{fut_start}-{fut_end} time mean under {scenario}"
        )
        chg_method = (
            f"Median across {n_models} individual CMIP6 models of the per-model "
            f"difference (each model's {fut_start}-{fut_end} {scenario} mean minus "
            f"its own {hist_start}-{hist_end} historical mean); this is the "
            f"median of differences, not the difference of the median fields; "
            f"positive values indicate an increase"
        )
        source = ('Individual CMIP6 model runs via Climate Change Knowledge '
                  'Portal (CCKP); ensemble statistic computed from the models listed')
        ensemble_statistic = (f'median (50th percentile) across {n_models} individual '
                              f'CMIP6 models')
    elif source_mode == "single-model":
        model = models[0]
        hist_method = f"{model} {hist_start}-{hist_end} time mean, {hist_blend}"
        fut_method = f"{model} {fut_start}-{fut_end} time mean under {scenario}"
        chg_method = (
            f"{model} future ({fut_start}-{fut_end}, {scenario}) minus historical "
            f"({hist_start}-{hist_end}); positive values indicate an increase"
        )
        source = (f'Single CMIP6 model run ({model}) via Climate Change Knowledge '
                  f'Portal (CCKP)')
        ensemble_statistic = 'none (single model)'
    else:  # ensemble-all
        hist_method = (
            f"Time mean of the CCKP pre-computed multi-model ensemble median "
            f"timeseries, {hist_blend}"
        )
        fut_method = (
            f"Time mean of the CCKP pre-computed multi-model ensemble median "
            f"timeseries under {scenario}, {fut_start}-{fut_end}"
        )
        chg_method = (
            f"Difference of ensemble median fields: future ({fut_start}-{fut_end}, "
            f"{scenario}) minus historical ({hist_start}-{hist_end}); positive "
            f"values indicate an increase"
        )
        source = ('CMIP6 multi-model ensemble (ensemble-all, median) via Climate '
                  'Change Knowledge Portal (CCKP)')
        ensemble_statistic = 'median (50th percentile across CMIP6 models), as pre-computed by CCKP'

    ds_out = xr.Dataset({
        'historical': historical_field,
        'future': future_field,
        'change': change_field,
    })

    ds_out['historical'].attrs = {
        'long_name': f"Historical {config['long_name']} ({hist_start}-{hist_end})",
        'units': config['units'],
        'description': description,
        'method': hist_method,
    }
    ds_out['future'].attrs = {
        'long_name': f"{future_label.title()} {config['long_name']} ({fut_start}-{fut_end})",
        'units': config['units'],
        'description': description,
        'method': fut_method,
    }
    ds_out['change'].attrs = {
        'long_name': f"Change in {config['long_name']}: {future_label} minus historical",
        'units': config['units'],
        'description': description,
        'method': chg_method,
    }

    ds_out.attrs = {
        'title': f"CMIP6 Climate Risk Statistics: {config['long_name']}",
        'source': source,
        'source_url': 'https://climateknowledgeportal.worldbank.org/',
        'institution': 'World Bank Climate Change Knowledge Portal',
        'history': f'Created on {datetime.now().strftime("%Y-%m-%d %H:%M:%S")} using cmip6_risk_mapper.py',
        'variable': variable,
        'scenario': scenario,
        'historical_scenario_blend': historical_scenario,
        'source_mode': source_mode,
        'historical_period': f'{hist_start}-{hist_end}',
        'future_period': f'{fut_start}-{fut_end}',
        'future_period_label': future_label,
        'ensemble_statistic': ensemble_statistic,
        'spatial_resolution': '0.25 degrees',
        'spatial_coverage': 'global (land and ocean); no land mask applied to data',
        'conventions': 'CF-1.8',
        'comment': 'Change is defined as future minus historical.',
    }
    if source_mode == "individual-models":
        ds_out.attrs['n_models'] = len(models)
        ds_out.attrs['models'] = ', '.join(models)
    elif source_mode == "single-model":
        ds_out.attrs['model'] = models[0]

    ds_out.to_netcdf(
        output_path,
        encoding={var: {'zlib': True, 'complevel': 4} for var in ds_out.data_vars}
    )
    print(f"  Successfully saved NetCDF file")
    print(f"  Variables: {list(ds_out.data_vars)}")
