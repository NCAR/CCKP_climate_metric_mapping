#!/usr/bin/env python3
"""
ERA5 Daily Precipitation Return Levels
======================================
Reformats per-return-period ERA5 frequency-analysis files into a single
CF-1.8 NetCDF, and makes a three-panel comparison map (1, 10, 30 yr).

Note on naming: the source files are named "idf_*", but they contain a single
daily-duration return level per grid cell (mm/day) with no duration axis.
This is a frequency analysis / return-level product, NOT an IDF surface, so
labels and metadata below say "return level" rather than "IDF".

Author: (reformatting pipeline)
Modified: June 2026
"""

import glob
import re
from pathlib import Path
from datetime import datetime

import numpy as np
import xarray as xr
import matplotlib.pyplot as plt
import matplotlib.ticker as mticker
import cartopy.crs as ccrs
import cartopy.feature as cfeature
from cartopy.mpl.gridliner import LONGITUDE_FORMATTER, LATITUDE_FORMATTER

# Optional custom colormaps, fall back to matplotlib if absent
try:
    import colormaps as cmaps
    HAS_CUSTOM_CMAPS = True
except ImportError:
    HAS_CUSTOM_CMAPS = False


# =============================================================================
# USER SETTINGS  (edit these)
# =============================================================================

DATA_DIR   = Path('/glade/derecho/scratch/hopson/NatureConservancy/Multiyr')
OUTPUT_DIR = Path('./return_level_outputs')

# Return periods to load into the consolidated NetCDF (all available).
ALL_RETURN_PERIODS = [1, 5, 10, 15, 20, 25, 30]
# Filename pattern: idf_era5_<N>yr.nc
FILENAME_TEMPLATE = 'idf_era5_{rp}yr.nc'

# Return periods to plot in the 3-panel figure.
PLOT_RETURN_PERIODS = [1, 10, 30]

FILL_VALUE = -9999.0
VAR_UNITS  = 'mm/day'

# Color settings. vmax is derived robustly from the longest plotted return
# period unless you hard-set it here (set VMAX = some number to override).
VMIN = 0.0
VMAX = None              # None -> 99th percentile of the longest RP field
VMAX_PERCENTILE = 99.0
CMAP = 'Spectral'        # used if custom colormaps unavailable

OUTPUT_DIR.mkdir(parents=True, exist_ok=True)


# =============================================================================
# LOAD + CONSOLIDATE
# =============================================================================

def load_return_level(rp):
    """Load one return-period file, mask the fill value, return a DataArray."""
    path = DATA_DIR / FILENAME_TEMPLATE.format(rp=rp)
    ds = xr.open_dataset(path)

    if 'return_level' not in ds:
        raise KeyError(f"'return_level' not found in {path}. Vars: {list(ds.data_vars)}")

    da = ds['return_level']

    # The source stores Fill Value as a string attribute, so it is NOT
    # auto-masked on load. Mask it explicitly.
    da = da.where(da != FILL_VALUE)

    return da


print("=" * 70)
print("ERA5 RETURN LEVELS - reformat + plot")
print("=" * 70)
print(f"Data dir:   {DATA_DIR}")
print(f"Output dir: {OUTPUT_DIR}")

arrays = []
for rp in ALL_RETURN_PERIODS:
    print(f"  loading {rp}-yr ...")
    arrays.append(load_return_level(rp))

# Stack along a new return_period coordinate -> (return_period, lat, lon)
return_level = xr.concat(arrays, dim='return_period')
return_level = return_level.assign_coords(return_period=ALL_RETURN_PERIODS)
return_level.name = 'return_level'

print(f"  consolidated shape: {return_level.shape} "
      f"(return_period, lat, lon)")


# =============================================================================
# WRITE CONSOLIDATED NETCDF (CF-1.8)
# =============================================================================

ds_out = xr.Dataset({'return_level': return_level})

ds_out['return_period'].attrs = {
    'long_name': 'return period',
    'units': 'years',
    'description': 'Average recurrence interval of the daily precipitation return level'
}
ds_out['return_level'].attrs = {
    'long_name': 'Daily precipitation return level',
    'units': VAR_UNITS,
    'description': ('Return level (magnitude expected to be equalled or exceeded '
                    'on average once per return period) of daily precipitation, '
                    'from extreme-value frequency analysis of ERA5.'),
    'coordinates': 'return_period lat lon'
}
if 'lat' in ds_out:
    ds_out['lat'].attrs = {'long_name': 'latitude', 'units': 'degrees_north'}
if 'lon' in ds_out:
    ds_out['lon'].attrs = {'long_name': 'longitude', 'units': 'degrees_east'}

ds_out.attrs = {
    'title': 'ERA5 daily precipitation return levels',
    'summary': ('Return-level frequency analysis of daily precipitation derived '
                'from ERA5. Single daily duration; not a multi-duration IDF product.'),
    'source': 'ERA5 reanalysis (frequency analysis by collaborator)',
    'institution': 'NSF NCAR',
    'history': (f'Created {datetime.now().strftime("%Y-%m-%d %H:%M:%S")} '
                f'by era5_return_levels.py from per-return-period files '
                f'({FILENAME_TEMPLATE.format(rp="<N>")})'),
    'references': 'Hersbach et al. (2020): ERA5 reanalysis',
    'spatial_resolution': '0.25 degrees',
    'geospatial_lat_min': float(ds_out['lat'].min()),
    'geospatial_lat_max': float(ds_out['lat'].max()),
    'geospatial_lon_min': float(ds_out['lon'].min()),
    'geospatial_lon_max': float(ds_out['lon'].max()),
    'conventions': 'CF-1.8',
    'comment': ('Return periods (years) along return_period dim: '
                f'{ALL_RETURN_PERIODS}. Fill value {FILL_VALUE} masked to NaN.')
}

nc_path = OUTPUT_DIR / 'era5_return_levels.nc'
ds_out.to_netcdf(
    nc_path,
    encoding={'return_level': {'zlib': True, 'complevel': 4,
                               '_FillValue': FILL_VALUE}}
)
print(f"\n  wrote NetCDF: {nc_path}")
print(f"  variables: {list(ds_out.data_vars)}")


# =============================================================================
# THREE-PANEL FIGURE (shared colorbar)
# =============================================================================

# Determine shared color range.
if VMAX is None:
    longest_rp = max(PLOT_RETURN_PERIODS)
    field = return_level.sel(return_period=longest_rp)
    vmax = float(np.nanpercentile(field.values, VMAX_PERCENTILE))
    print(f"\n  shared vmax = {vmax:.2f} {VAR_UNITS} "
          f"({VMAX_PERCENTILE:g}th pctile of {longest_rp}-yr field)")
else:
    vmax = VMAX
    print(f"\n  shared vmax = {vmax:.2f} {VAR_UNITS} (user-set)")
vmin = VMIN

# Colormap
if HAS_CUSTOM_CMAPS:
    cmap = getattr(cmaps, 'nice_gfdl', CMAP)
else:
    cmap = CMAP

pcrs = ccrs.Robinson()
tcrs = ccrs.PlateCarree()

fig, axes = plt.subplots(3, 1, figsize=(6, 8.3),
                         subplot_kw={'projection': pcrs})
fig.subplots_adjust(left=0.03, right=0.88, top=0.95, bottom=0.06, hspace=0.18)

xticks = np.arange(-180, 181, 90)
yticks = np.arange(-60, 91, 30)

cf = None
for ax, rp in zip(axes, PLOT_RETURN_PERIODS):
    da = return_level.sel(return_period=rp)
    lon = da.lon.values
    lat = da.lat.values
    X, Y = np.meshgrid(lon, lat)

    cf = ax.pcolormesh(X, Y, da.values, vmin=vmin, vmax=vmax,
                       cmap=cmap, transform=tcrs, shading='auto')

    ax.add_feature(cfeature.OCEAN, facecolor='gainsboro', zorder=2)
    ax.add_feature(cfeature.COASTLINE.with_scale('110m'), linewidths=1.2)
    ax.add_feature(cfeature.BORDERS.with_scale('110m'), linewidths=0.5)

    gl = ax.gridlines(draw_labels=True, crs=tcrs, x_inline=False,
                      y_inline=False, color='white', alpha=0.2)
    gl.xlocator = mticker.FixedLocator(xticks)
    gl.ylocator = mticker.FixedLocator(yticks)
    gl.xformatter = LONGITUDE_FORMATTER
    gl.yformatter = LATITUDE_FORMATTER
    gl.top_labels = False
    gl.right_labels = False

    panel = chr(ord('a') + list(PLOT_RETURN_PERIODS).index(rp))
    ax.set_title(f"{panel}) {rp}-year daily precipitation return level",
                 loc='left', fontsize=10)

# Single shared colorbar spanning all three panels.
cbar_ax = fig.add_axes([0.90, 0.08, 0.02, 0.84])
fig.colorbar(cf, cax=cbar_ax, orientation='vertical', label=VAR_UNITS)

fig_path = OUTPUT_DIR / 'era5_return_levels_map.png'
plt.savefig(fig_path, dpi=300, bbox_inches='tight')
print(f"  wrote figure: {fig_path}")

print("\n" + "=" * 70)
print("DONE")
print("=" * 70)
print(f"NetCDF: {nc_path}")
print(f"Figure: {fig_path}")
