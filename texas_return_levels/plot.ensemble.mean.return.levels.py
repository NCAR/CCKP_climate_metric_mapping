"""
Plot STAR-ESDM ensemble-mean return levels (standalone).

Reads the NetCDF written by calc_gev-fit_starESDM6_precip_lmoment.py and draws
the ensemble mean in the same 3-panel style as that script's per-model figure:
panels a/b/c across +1.0/+2.0/+3.0 C, shared color limits, a warming-level
annotation box per panel, and one shared horizontal colorbar.

Produces one figure per return period (10/25/50/100 yr).

Values are stored by basin name in the NetCDF; basin geometry is taken from the
HUC8 shapefile and matched on the SUBBASIN field.
"""

import os

import numpy as np
import xarray as xr
import geopandas as gpd
import matplotlib.pyplot as plt

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

POOL_METHOD = 'pool'  # must match the NetCDF you want to read
OUTDIR = 'rl_figures_lmoment'
NC_INFILE = f'{OUTDIR}/STAR-ESDM_HUC8_return_levels.{POOL_METHOD}.nc'

TEMPS = [1.0, 2.0, 3.0]               # warming levels to draw (must be in file)
RETURN_PERIODS = [10, 25, 50, 100]    # one figure each (must be in file)

# Color limits. Matches the calc script's fixed range by default. If a given
# return period clips badly at this range, set PER_RP_AUTOSCALE = True to let
# each figure self-scale to its own ensemble-mean min/max instead.
VMIN, VMAX = 50, 275
PER_RP_AUTOSCALE = False
COLORS = ['darkorange', 'indianred', 'maroon']  # warming-level annotation boxes

os.makedirs(OUTDIR, exist_ok=True)

# ==============================================================================
# LOAD
# ==============================================================================
print(f'Reading {NC_INFILE} ...')
ds = xr.open_dataset(NC_INFILE)
print(f'  dims: {dict(ds.sizes)}')

print('Loading HUC8 shapefile...')
gdf = gpd.read_file(SHAPEFILE).to_crs('EPSG:4326')
print(f'  {len(gdf)} basins')

ens = ds['ensemble_mean']  # (warming_level, return_period, basin)
basin_names = [str(b) for b in ds['basin'].values]

# ==============================================================================
# PLOT: one 3-panel figure per return period
# ==============================================================================
for rp in RETURN_PERIODS:
    if rp not in ds['return_period'].values:
        print(f'  [skip] return period {rp} not in file')
        continue
    print(f'Plotting ensemble mean: {rp}-yr return level')

    # Per-figure color limits
    if PER_RP_AUTOSCALE:
        vals = ens.sel(return_period=rp).values
        if np.isfinite(vals).any():
            vmin, vmax = np.nanmin(vals), np.nanmax(vals)
        else:
            vmin, vmax = VMIN, VMAX
    else:
        vmin, vmax = VMIN, VMAX

    fig, ax = plt.subplots(1, 3, figsize=(12, 5))

    for ti, temp in enumerate(TEMPS):
        if temp not in ds['warming_level'].values:
            print(f'    [skip] warming level +{temp} C not in file')
            ax[ti].set_axis_off()
            continue

        # Map basin-name -> ensemble-mean value for this (temp, rp)
        series = ens.sel(warming_level=temp, return_period=rp)
        rl_lookup = {name: float(series.values[i])
                     for i, name in enumerate(basin_names)}
        gdf['ens_value'] = gdf['SUBBASIN'].map(rl_lookup)

        gdf.plot(
            column='ens_value',
            cmap=PRECIP_CMAP,
            legend=False,
            edgecolor='black',
            linewidth=0.5,
            vmin=vmin,
            vmax=vmax,
            ax=ax[ti],
            missing_kwds={'color': 'lightgray'},
        )

        ax[ti].annotate(
            f'+{temp} C',
            xy=(0.98, 0.98), xycoords='axes fraction',
            ha='right', va='top',
            bbox=dict(boxstyle='round,pad=0.3',
                      facecolor=COLORS[ti], alpha=0.3),
        )
        ax[ti].set_axis_off()

    ax[0].set_title(
        f'a) Ensemble mean:\n{rp}-year precip. return level at +1.0 C',
        loc='left')
    ax[1].set_title('b) +2.0 C', loc='left')
    ax[2].set_title('c) +3.0 C', loc='left')

    # Shared horizontal colorbar (same placement as the calc script)
    mappable = ax[0].collections[0]
    cbar_ax = fig.add_axes([0.30, 0.12, 0.40, 0.02])
    plt.colorbar(mappable, cax=cbar_ax, orientation='horizontal',
                 label='mm/day')

    fig.subplots_adjust(left=0.05, right=0.95, top=0.95, bottom=0.12)
    out = (f'{OUTDIR}/ensemble_mean.{rp}yr.glw.return.levels.HUC8.'
           f'{POOL_METHOD}.png')
    fig.savefig(out, dpi=400, bbox_inches='tight')
    plt.close(fig)
    print(f'  wrote {out}')

print('Done.')
