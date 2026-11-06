"""
STAR-ESDM Return Level Analysis for HUC8 Watersheds (L-moments + pooling)
=========================================================================

Recalculates 50-year precipitation return levels from STAR-ESDM downscaled
data across global warming levels (+1.0/+2.0/+3.0 C), using the GEV-fitting
methodology from the ERA5 validation script:

1.  L-moments (Hosking 1985/1990) initial guess for (shape, loc, scale)
2. MLE refinement via scipy.stats.genextreme.fit seeded with that guess
3. Regional pooling of all (cell, year) values per HUC8 basin (primary),
3.  with a toggle to instead spatially-average each basin before fitting.

Pooling vs. averaging
---------------------
POOL_METHOD = 'pool'    : pool every (cell, year) sample per basin, then fit.
                           Estimates the regional extreme distribution. Return
                          periods are in "cell-years". More robust to localized
                          extremes but assumes within-basin homogeneity and is
                          sensitive to spatial covariance (a known soft spot of
                           statistical downscaling).
POOL_METHOD = 'average' : spatial-mean across cells per timestep, then fit the
                           basin-averaged annual-max series. Leans on per-cell
                          marginals (what stat-downscaling reproduces best) but
                           dilutes localized high-intensity events.

Run both and compare maps + shape parameters. Agreement => robust. Divergence
=> the divergence flags basins where within-basin homogeneity is breaking; the
diagnostic fit plots will show empirical points fanning off a single GEV curve.

Author: Jacob Stuivenvolt-Allen, jsallen@ucar.edu
"""

import os
from math import gamma

import pandas as pd
import numpy as np
import xarray as xr
import geopandas as gpd
import rioxarray  # noqa: F401  (registers .rio accessor)
import matplotlib.pyplot as plt
from scipy.stats import genextreme

try:
    import colormaps as cmaps
    PRECIP_CMAP = cmaps.precip_11lev
except ImportError:
    PRECIP_CMAP = 'YlGnBu'

# Optional custom font (silently falls back to system default)
try:
    import matplotlib.font_manager as font_manager
    _font = '/glade/work/jsallen/conda-envs/earth/fonts/Avenir-Medium.otf'
    if os.path.exists(_font):
        font_manager.fontManager.addfont(_font)
        plt.rcParams['font.family'] = 'sans-serif'
        plt.rcParams['font.sans-serif'] = font_manager.FontProperties(
            fname=_font).get_name()
except Exception:
    pass

# ==============================================================================
# CONFIGURATION
# ==============================================================================
PROJ_PATH = '/glade/u/home/jsallen/projects/tnc_2025/return_periods/'
SHAPEFILE = f'{PROJ_PATH}shape/USGS_HUC_8_Subbasin.shp'

GLW_PATH = '/glade/u/home/jsallen/projects/tnc_2025/warming_levels/output/'
GLW_FILE = 'CMIP6.global.warming.levels.ssp585.csv'

STAR_PATH = '/glade/work/hartke/STARESDM_TX/data/'
STAR_FILE = 'STAR-ESDM-TX_ssp585_pr_max.nc'

OUTDIR = 'rl_figures_lmoment'

POOL_METHOD = 'pool'        # 'pool' (primary) or 'average'
RETURN_PERIOD = 50          # years
RPS_GRID = np.arange(5, 101, 5)
TEMPS = [1.0, 2.0, 3.0]     # warming levels (C above pre-industrial)
SKIP_MODELS = ['BCC-CSM2-MR']
MIN_SAMPLES = 30            # minimum valid samples to attempt a fit
PLOT_DIAGNOSTICS = True     # write per-(model, warming-level) diagnostic fits
DIAG_N_BASINS = 6
RANDOM_SEED = 42

# Colorbar limits for the choropleth (match original script)
VMIN, VMAX = 100, 250
COLORS = ['darkorange', 'indianred', 'maroon']  # warming-level annotations

# Return periods to write to the NetCDF (subset of RPS_GRID)
NC_RETURN_PERIODS = [10, 25, 50, 100]
NC_OUTFILE = f'{OUTDIR}/STAR-ESDM_HUC8_return_levels.{POOL_METHOD}.nc'
# Candidate column in the shapefile holding a numeric HUC8 code (optional)
HUC_ID_CANDIDATES = ['HUC8', 'HUC_8', 'huc8', 'HUC8_CODE']

os.makedirs(OUTDIR, exist_ok=True)


# GEV FITTING (L-moments initial guess + MLE refinement)
# ------------------------------------------------------
def _sample_l_moments(x):
    """First three sample L-moments via unbiased PWM estimator (Hosking 1990)."""
    x = np.sort(np.asarray(x, dtype=float))
    n = x.size
    if n < 4:
        raise ValueError("Need at least 4 samples for L-moments.")
    j = np.arange(1, n + 1)
    b0 = x.mean()
    b1 = np.sum((j - 1) / (n - 1) * x) / n
    b2 = np.sum((j - 1) * (j - 2) / ((n - 1) * (n - 2)) * x) / n
    l1 = b0
    l2 = 2 * b1 - b0
    l3 = 6 * b2 - 6 * b1 + b0
    return l1, l2, l3


def gev_lmoment_fit(x):
    """
    Estimate GEV parameters in scipy.stats.genextreme convention via
    Hosking's (1985) rational approximation. Returns (c, loc, scale).
    """
    l1, l2, l3 = _sample_l_moments(x)

    if l2 <= 0:
        raise ValueError(f"Invalid L-moments: lambda_2 = {l2:.4g} <= 0")
    tau3 = l3 / l2
    if not np.isfinite(tau3) or abs(tau3) >= 1:
        raise ValueError(f"Invalid L-moment ratio tau_3 = {tau3:.4g}")
    if abs(tau3) > 0.7:
        raise ValueError(
            f"tau_3 = {tau3:.4g} outside reliable range (|tau_3| > 0.7)"
        )

    # Hosking's "k" matches scipy's c convention (positive = bounded upper tail)
    c_const = 2.0 / (3.0 + tau3) - np.log(2.0) / np.log(3.0)
    k = 7.8590 * c_const + 2.9554 * c_const ** 2

    g = gamma(1.0 + k)
    scale = (l2 * k) / ((1.0 - 2.0 ** (-k)) * g)
    loc = l1 - scale * (1.0 - g) / k

    if not (np.isfinite(scale) and scale > 0 and np.isfinite(loc)):
        raise ValueError(
            f"L-moments yielded invalid GEV params: loc={loc}, scale={scale}, k={k}"
        )
    return k, loc, scale


def fit_gev(data, return_periods=RPS_GRID):
    """Fit GEV (L-moments init -> MLE refine) and compute return levels."""
    data = np.asarray(data, dtype=float)
    data = data[np.isfinite(data)]
    if data.size == 0:
        raise ValueError("No valid data after NaN removal")

    c0, loc0, scale0 = gev_lmoment_fit(data)
    c, loc, scale = genextreme.fit(data, c0, loc=loc0, scale=scale0)

    return_levels = genextreme.isf(1.0 / return_periods, c, loc=loc, scale=scale)

    sorted_data = np.sort(data)
    n = sorted_data.size
    exceedance_probs = np.arange(1, n + 1) / (n + 1)
    empirical_rp = 1.0 / (1.0 - exceedance_probs)

    return {
        'gev_params': {'shape': c, 'location': loc, 'scale': scale},
        'return_periods': return_periods,
        'return_levels': return_levels,
        'sorted_data': sorted_data,
        'empirical_return_periods': empirical_rp,
    }


# PER-BASIN FIT (pool or average)
# -------------------------------
def basin_fits(da, gdf, return_period=RETURN_PERIOD, method='pool'):
    """
    For each HUC8 basin: clip, build the sample per `method`, fit GEV.

    method='pool'    -> pool all finite (cell, year) values.
    method='average' -> spatial-mean over cells per timestep (basin-avg series).

    Returns (basin_rl, full_results):
      basin_rl     : {basin_name: return_level_at_`return_period`}
      full_results : {basin_name: full fit_gev dict (+ 'n_cells')}
    """
    if method not in ('pool', 'average'):
        raise ValueError(f"Unknown method '{method}' (use 'pool' or 'average')")

    basin_rl = {}
    full_results = {}

    # Identify the spatial dims (rioxarray names them x/y after rename)
    spatial_dims = [d for d in da.dims if d in ('x', 'y', 'lon', 'lat')]

    for _, basin in gdf.iterrows():
        name = basin['SUBBASIN']
        geom = [basin.geometry]

        try:
            clipped = da.rio.clip(geom, gdf.crs, all_touched=True, drop=True)
        except Exception as e:
            print(f'    [skip] {name}: clip failed ({e})')
            continue

        # Number of cells with any finite value across the time axis
        time_dim = [d for d in clipped.dims if d not in spatial_dims][0]
        n_cells = int(np.isfinite(clipped).any(dim=time_dim).sum())

        if method == 'pool':
            sample = clipped.values.ravel()
            sample = sample[np.isfinite(sample)]
        else:  # average
            sample = clipped.mean(dim=spatial_dims, skipna=True).values
            sample = sample[np.isfinite(sample)]

        if sample.size < MIN_SAMPLES:
            print(f'    [skip] {name}: only {sample.size} valid samples '
                  f'({method})')
            continue

        try:
            res = fit_gev(sample, RPS_GRID)
        except ValueError as e:
            print(f'    [skip] {name}: GEV fit failed ({e})')
            continue

        res['n_cells'] = n_cells
        rp_idx = np.where(RPS_GRID == return_period)[0][0]
        basin_rl[name] = res['return_levels'][rp_idx]
        full_results[name] = res

    return basin_rl, full_results


# PLOT PLOT PLOT
# ---------------
def plot_random_basin_fits(full_results, n_basins=DIAG_N_BASINS, savepath=None,
                           random_seed=RANDOM_SEED, suptitle=None, method='pool'):
    """Plot GEV fit vs. empirical samples for N random basins."""
    if not full_results:
        print('    [diag] no successful fits to plot')
        return
    rng = np.random.default_rng(random_seed)
    names = list(full_results.keys())
    n = min(n_basins, len(names))
    chosen = rng.choice(names, size=n, replace=False)

    rp_axis_label = ('Return period (cell-years)' if method == 'pool'
                     else 'Return period (years)')

    ncols = 3
    nrows = int(np.ceil(n / ncols))
    fig, axes = plt.subplots(nrows, ncols, figsize=(4.5 * ncols, 3.5 * nrows),
                             squeeze=False)

    for i, name in enumerate(chosen):
        ax = axes[i // ncols, i % ncols]
        r = full_results[name]
        p = r['gev_params']

        emp_rp = r['empirical_return_periods']
        max_rp = max(emp_rp.max(), 100)
        rp_curve = np.logspace(np.log10(2), np.log10(max_rp), 200)
        rl_curve = genextreme.isf(1.0 / rp_curve, p['shape'],
                                  loc=p['location'], scale=p['scale'])

        ax.plot(emp_rp, r['sorted_data'],
                marker='o', linestyle='none', color='red',
                markersize=3, alpha=0.4, label='Samples')
        ax.plot(rp_curve, rl_curve,
                color='blue', linewidth=2, label='GEV fit')

        ax.set_xscale('log')
        ax.set_xlabel(rp_axis_label)
        ax.set_ylabel('Precip (mm/day)')
        n_cells = r.get('n_cells', None)
        ncells_str = f', n_cells={n_cells}' if n_cells is not None else ''
        ax.set_title(
            f"{name}{ncells_str}\n"
            f"c={p['shape']:.2f}, loc={p['location']:.1f}, scale={p['scale']:.1f}",
            fontsize=9
        )
        ax.grid(True, alpha=0.3)
        if i == 0:
            ax.legend(loc='lower right', fontsize=8)

    for k in range(n, nrows * ncols):
        axes[k // ncols, k % ncols].axis('off')

    if suptitle:
        fig.suptitle(suptitle, fontsize=12)
    fig.tight_layout()
    if savepath:
        fig.savefig(savepath, dpi=200, bbox_inches='tight')
    plt.close(fig)


# LOAD GEOGRAPHIC + WARMING-LEVEL + STAR-ESDM DATA
# ------------------------------------------------
print('Loading HUC8 shapefile...')
gdf = gpd.read_file(SHAPEFILE).to_crs('EPSG:4326')
print(f'  {len(gdf)} basins')

print('Loading global warming levels...')
glws = pd.read_csv(f'{GLW_PATH}{GLW_FILE}')

print('Loading STAR-ESDM...')
star_esdm = xr.open_dataset(f'{STAR_PATH}{STAR_FILE}')
# Longitude 0-360 -> -180-180 and sort
star_esdm = star_esdm.assign_coords(
    lon=((star_esdm.lon + 180) % 360 - 180)).sortby('lon')
star_models = star_esdm['gcm'].values
print(f'  models: {list(star_models)}')
print(f"  method: {POOL_METHOD}")

# Collect results for optional multi-model averaging downstream.
# data_frames[ti] = list of per-model {basin: RL} dicts at warming level ti
data_frames = [[] for _ in TEMPS]

# Collect full multi-RP results for the NetCDF.
# nc_records[model][temp][basin] = {rp: return_level} over NC_RETURN_PERIODS
nc_records = {}
processed_models = []  # models that actually ran (for the NetCDF model axis)

# DO THE WHOLE THANG 
# ------------------
for si, star_model in enumerate(star_models):
    if star_model in SKIP_MODELS:
        print(f'Skipping model: {star_model}')
        continue
    print(f'Processing model: {star_model}')

    model_glws = glws[glws['model'].str.contains(star_model)]
    if model_glws.empty:
        print(f'  [skip] no warming-level rows match {star_model}')
        continue

    fig, ax = plt.subplots(1, 3, figsize=(12, 5))

    for ti, temp in enumerate(TEMPS):
        print(f'  Warming level: +{temp} C')

        temp_year = int(model_glws[str(temp)].mean(axis=0))
        print(f'    reached in year: {temp_year}')

        annual_maxima = star_esdm.sel(
            gcm=star_model,
            year=slice(1850, temp_year),
        )['max_pr']

        annual_maxima = annual_maxima.rio.write_crs('EPSG:4326', inplace=True)
        annual_maxima = annual_maxima.rename({'lon': 'x', 'lat': 'y'})

        basin_rl, full_results = basin_fits(
            annual_maxima, gdf,
            return_period=RETURN_PERIOD,
            method=POOL_METHOD,
        )
        print(f'    fit succeeded for {len(basin_rl)}/{len(gdf)} basins')

        gdf['avg_value'] = gdf['SUBBASIN'].map(basin_rl)

        gdf.plot(
            column='avg_value',
            cmap=PRECIP_CMAP,
            legend=False,
            edgecolor='black',
            linewidth=0.5,
            vmin=VMIN,
            vmax=VMAX,
            ax=ax[ti],
            missing_kwds={'color': 'lightgray'},
        )

        ax[ti].annotate(
            f'1850-{temp_year}',
            xy=(0.98, 0.98), xycoords='axes fraction',
            ha='right', va='top',
            bbox=dict(boxstyle='round,pad=0.3',
                      facecolor=COLORS[ti], alpha=0.3),
        )
        ax[ti].set_axis_off()

        # Store {basin: RL} for downstream multi-model averaging
        data_frames[ti].append(basin_rl)

        # Harvest all NetCDF return periods per basin from full_results.
        # full_results[basin]['return_levels'] is indexed against RPS_GRID.
        rp_pos = {rp: int(np.where(RPS_GRID == rp)[0][0])
                  for rp in NC_RETURN_PERIODS}
        nc_records.setdefault(star_model, {})[temp] = {
            name: {rp: res['return_levels'][rp_pos[rp]]
                   for rp in NC_RETURN_PERIODS}
            for name, res in full_results.items()
        }

        if PLOT_DIAGNOSTICS:
            diag_path = (f'{OUTDIR}/{star_model}_diag_'
                         f'{POOL_METHOD}_+{temp}C.png')
            plot_random_basin_fits(
                full_results,
                n_basins=DIAG_N_BASINS,
                savepath=diag_path,
                suptitle=(f'{star_model} +{temp}C ({POOL_METHOD}): '
                          'GEV fit diagnostics'),
                method=POOL_METHOD,
            )

    ax[0].set_title(
        f'a) {star_model}:\n50-year precip. return level at +1.0 C', loc='left')
    ax[1].set_title('b) +2.0 C', loc='left')
    ax[2].set_title('c) +3.0 C', loc='left')

    mappable = ax[0].collections[0]
    cbar_ax = fig.add_axes([0.30, 0.12, 0.40, 0.02])
    plt.colorbar(mappable, cax=cbar_ax, orientation='horizontal',
                 label='mm/day')

    fig.subplots_adjust(left=0.05, right=0.95, top=0.95, bottom=0.12)
    fig.savefig(
        f'{OUTDIR}/{star_model}.glw.return.levels.HUC8.{POOL_METHOD}.png',
        dpi=400, bbox_inches='tight')
    plt.close(fig)
    print(f'  Completed {star_model}\n')
    processed_models.append(star_model)

# MULTI-MODEL MEAN RETURN LEVELS PER WARMING LEVEL
# ------------------------------------------------
# data_frames[ti] is a list of {basin: RL} dicts (one per model). Average each
# basin across models, ignoring models where the fit failed (NaN).
print('Computing multi-model mean return levels...')
for ti, temp in enumerate(TEMPS):
    if not data_frames[ti]:
        print(f'  +{temp} C: no model results')
        continue
    rl_df = pd.DataFrame(data_frames[ti])          # rows=models, cols=basins
    mean_rl = rl_df.mean(axis=0, skipna=True)       # per-basin multi-model mean

    gdf['mmm_value'] = gdf['SUBBASIN'].map(mean_rl)

    fig, ax = plt.subplots(figsize=(8, 7))
    gdf.plot(
        column='mmm_value',
        cmap=PRECIP_CMAP,
        legend=True,
        edgecolor='black',
        linewidth=0.4,
        vmin=VMIN, vmax=VMAX,
        ax=ax,
        legend_kwds={'label': f'{RETURN_PERIOD}-yr return level (mm/day)',
                     'orientation': 'horizontal', 'shrink': 0.6},
        missing_kwds={'color': 'lightgray', 'label': 'fit failed'},
    )
    ax.set_title(f'Multi-model mean: {RETURN_PERIOD}-yr precip return level '
                 f'at +{temp} C ({POOL_METHOD})', loc='left')
    ax.set_axis_off()
    fig.tight_layout()
    out = f'{OUTDIR}/MMM_+{temp}C_{RETURN_PERIOD}yr_RL.{POOL_METHOD}.png'
    fig.savefig(out, dpi=300, bbox_inches='tight')
    plt.close(fig)
    print(f'  wrote {out}')

# WRITE NETCDF: per-model return levels + ensemble mean
# -------------------------------------------------------
# Dimensions: (model, warming_level, return_period, basin).
# Every cell is filled; NaN where a basin's fit failed for that (model, temp).
# ensemble_mean is the across-model nanmean (collapses the model dimension).
print('Assembling NetCDF...')

basins = list(gdf['SUBBASIN'])
n_model = len(processed_models)
n_temp = len(TEMPS)
n_rp = len(NC_RETURN_PERIODS)
n_basin = len(basins)

rl = np.full((n_model, n_temp, n_rp, n_basin), np.nan, dtype=float)

for mi, model in enumerate(processed_models):
    for ti, temp in enumerate(TEMPS):
        per_basin = nc_records.get(model, {}).get(temp, {})
        for bi, bname in enumerate(basins):
            rec = per_basin.get(bname)
            if rec is None:
                continue
            for ri, rp in enumerate(NC_RETURN_PERIODS):
                rl[mi, ti, ri, bi] = rec[rp]

# Ensemble mean across models (ignore failed fits)
with np.errstate(invalid='ignore'):
    ens = np.nanmean(rl, axis=0)  # (warming_level, return_period, basin)

ds_out = xr.Dataset(
    data_vars={
        'return_level': (
            ('model', 'warming_level', 'return_period', 'basin'), rl),
        'ensemble_mean': (
            ('warming_level', 'return_period', 'basin'), ens),
    },
    coords={
        'model': processed_models,
        'warming_level': np.array(TEMPS, dtype=float),
        'return_period': np.array(NC_RETURN_PERIODS, dtype=int),
        'basin': basins,
    },
)

# Attach a numeric HUC8 code as an auxiliary coordinate if available
huc_col = next((c for c in HUC_ID_CANDIDATES if c in gdf.columns), None)
if huc_col is not None:
    huc_lookup = dict(zip(gdf['SUBBASIN'], gdf[huc_col].astype(str)))
    ds_out = ds_out.assign_coords(
        huc8=('basin', [huc_lookup[b] for b in basins]))
    ds_out['huc8'].attrs['long_name'] = 'HUC8 hydrologic unit code'

# Variable + coordinate metadata
ds_out['return_level'].attrs = {
    'long_name': 'GEV return level of annual-max daily precipitation per HUC8 basin',
    'units': 'mm/day',
    'fit_method': f'L-moments init + MLE refine; basin sampling = {POOL_METHOD}',
}
ds_out['ensemble_mean'].attrs = {
    'long_name': 'Multi-model mean return level (nanmean over models)',
    'units': 'mm/day',
}
ds_out['warming_level'].attrs = {
    'long_name': 'Global warming level above pre-industrial', 'units': 'degree_Celsius'}
ds_out['return_period'].attrs = {'long_name': 'Return period', 'units': 'years'}
ds_out['basin'].attrs = {'long_name': 'HUC8 subbasin name (SUBBASIN field)'}

ds_out.attrs = {
    'title': 'STAR-ESDM HUC8 precipitation return levels by warming level',
    'source': 'STAR-ESDM downscaled CMIP6 ssp585, annual max daily precip (max_pr)',
    'method': (f'Per-basin GEV ({POOL_METHOD}) with L-moments initial guess and '
               'scipy MLE refinement'),
    'history': f'Created with {os.path.basename(__file__) if "__file__" in dir() else "script"}',
    'note': ('return_level dim order: (model, warming_level, return_period, basin). '
             'NaN indicates a failed/skipped fit for that basin.'),
}

encoding = {v: {'zlib': True, 'complevel': 4} for v in ds_out.data_vars}
ds_out.to_netcdf(NC_OUTFILE, encoding=encoding)
print(f'  wrote {NC_OUTFILE}')
print(f'  dims: {dict(ds_out.sizes)}')

print('Done.')
