#!/usr/bin/env python3
"""
Climate Risk Mapper
===================
A generalized script for creating climate risk maps from ERA5-derived data 
from the Climate Change Knowledge Portal (CCKP).

Author: Jacob Stuivenvolt-Allen
Modified: February 2026

This script:
1. Downloads and processes ERA5 climate data from CCKP
2. Calculates mean (1990-2020 reference period), extremes, and trends
3. Creates publication-quality three-panel risk maps
4. Exports processed data as NetCDF with comprehensive metadata

Usage:
    python climate_risk_mapper.py <variable_name> [options]
    
Example:
    python climate_risk_mapper.py r95ptot --output-dir ./output
"""

import xarray as xr
import matplotlib.pyplot as plt
import numpy as np
from scipy import stats
import argparse
from pathlib import Path
from datetime import datetime
import warnings

import cartopy.crs as ccrs
import cartopy.feature as cfeature
from cartopy.mpl.gridliner import LONGITUDE_FORMATTER, LATITUDE_FORMATTER
import matplotlib.ticker as mticker

# Try to import custom colormaps, fall back to matplotlib defaults
try:
    import colormaps as cmaps
    HAS_CUSTOM_CMAPS = True
except ImportError:
    HAS_CUSTOM_CMAPS = False
    warnings.warn("Custom colormaps not found. Using matplotlib defaults.")

# Try to set custom font, fall back to system defaults
try:
    import matplotlib.font_manager as font_manager
    font_dir = '/glade/work/jsallen/conda-envs/earth/fonts/Avenir-Medium.otf'
    if Path(font_dir).exists():
        font_manager.fontManager.addfont(font_dir)
        prop = font_manager.FontProperties(fname=font_dir)
        plt.rcParams['font.family'] = 'sans-serif'
        plt.rcParams['font.sans-serif'] = prop.get_name()
except:
    pass


# =============================================================================
# CONFIGURATION DICTIONARIES
# =============================================================================

# Variable-specific configuration
# Format: 'variable_code': {config_dict}
VARIABLE_CONFIG = {
    'sfcgustx': {
        'long_name': 'estimated maximum 3-second wind gust at the surface',
        'units': 'm/s',
        'cmap_mean': 'Spectral',
        'cmap_extreme': 'Spectral',
        'cmap_trend': 'RdYlBu_r',
        'vmin_mean': 5,
        'vmax_mean': 60,
        'vmin_extreme': 5,
        'vmax_extreme': 60,
        'vmin_trend': -0.05, # set to 0.1% of vmax/vmin
        'vmax_trend': 0.05,
        'extreme_type': 'max',  # 'max' or 'min'
        'trend_units': 'm/s/year'
    },
    'spei12': {
        'long_name': 'Standardized Precipitation Evapotranspiration Index\n(Pearson distribution), 12-month',
        'units': 'dimensionless index',
        'cmap_mean': 'Spectral',
        'cmap_extreme': 'Spectral',
        'cmap_trend': 'RdYlBu_r',
        'vmin_mean': -3.5,
        'vmax_mean': 3.5,
        'vmin_extreme': -3.5,
        'vmax_extreme': 3.5,
        'vmin_trend': -0.05, # set to 0.1% of vmax/vmin
        'vmax_trend': 0.05,
        'extreme_type': 'min',  # 'max' or 'min'
        'trend_units': 'index/year'
    },
    'gsl': {
        'long_name': 'GSL : annual length of growing season\n(first 5+ days > 5C to first 5+ days < 5C)',
        'units': 'days',
        'cmap_mean': 'Spectral',
        'cmap_extreme': 'Spectral',
        'cmap_trend': 'RdYlBu_r',
        'vmin_mean': 0,
        'vmax_mean': 365,
        'vmin_extreme': 0,
        'vmax_extreme': 365,
        'vmin_trend': 0, # set to 0.1% of vmax/vmin
        'vmax_trend': 0.365,
        'extreme_type': 'max',  # 'max' or 'min'
        'trend_units': 'days/year'
    },
    'sdii': {
        'long_name': 'simple precipitation intensity index:\nmean precipitation per day with rainfall',
        'units': 'mm',
        'cmap_mean': 'Spectral',
        'cmap_extreme': 'Spectral',
        'cmap_trend': 'RdYlBu_r',
        'vmin_mean': 0,
        'vmax_mean': 12,
        'vmin_extreme': 0,
        'vmax_extreme': 12,
        'vmin_trend': -0.012, # set to 0.1% of vmax/vmin
        'vmax_trend': 0.012,
        'extreme_type': 'max',  # 'max' or 'min'
        'trend_units': 'mm/year'
    },
    'hi': {
        'long_name': 'NWS_heat_index',
        'units': 'degree_Celsius',
        'cmap_mean': 'Spectral',
        'cmap_extreme': 'Spectral',
        'cmap_trend': 'RdYlBu_r',
        'vmin_mean': -40,
        'vmax_mean': 40,
        'vmin_extreme': -40,
        'vmax_extreme': 40,
        'vmin_trend': -0.04, # set to 0.1% of vmax/vmin
        'vmax_trend': 0.04,
        'extreme_type': 'max',  # 'max' or 'min'
        'trend_units': '°C/year'
    },
    'cwd': {
        'long_name': 'longest consecutive sequence of wet days (>=1mm) within annual data',
        'units': 'days',
        'cmap_mean': 'Spectral',
        'cmap_extreme': 'Spectral',
        'cmap_trend': 'RdYlBu_r',
        'vmin_mean': 0,
        'vmax_mean': 360,
        'vmin_extreme': 0,
        'vmax_extreme': 360,
        'vmin_trend': -0.36, # set to 0.1% of vmax/vmin
        'vmax_trend': 0.36,
        'extreme_type': 'max',  # 'max' or 'min'
        'trend_units': 'days/year'
    },
    'cdd': {
        'long_name': 'longest consecutive sequence of dry days (<1mm) within annual data',
        'units': 'days',
        'cmap_mean': 'Spectral',
        'cmap_extreme': 'Spectral',
        'cmap_trend': 'RdYlBu_r',
        'vmin_mean': 0,
        'vmax_mean': 360,
        'vmin_extreme': 0,
        'vmax_extreme': 360,
        'vmin_trend': -0.36, # 
        'vmax_trend': 0.36,
        'extreme_type': 'max',  # 'max' or 'min'
        'trend_units': 'days/year'
    },
    'hdd65': {
        'long_name': 'hdd65: heating degree days (degF)',
        'units': 'degree days (F)',
        'cmap_mean': 'Spectral',
        'cmap_extreme': 'Spectral',
        'cmap_trend': 'RdYlBu_r',
        'vmin_mean': 0,
        'vmax_mean': 22000,
        'vmin_extreme': 0,
        'vmax_extreme': 22000,
        'vmin_trend': -22,
        'vmax_trend': 22,
        'extreme_type': 'max',  # 'max' or 'min'
        'trend_units': 'degree days (F)/year'
    },
    'cdd65': {
        'long_name': 'sum of degrees F above 65.F',
        'units': 'degree days (F)',
        'cmap_mean': 'Spectral',
        'cmap_extreme': 'Spectral',
        'cmap_trend': 'RdYlBu_r',
        'vmin_mean': 0,
        'vmax_mean': 6000,
        'vmin_extreme': 0,
        'vmax_extreme': 6000,
        'vmin_trend': -6,
        'vmax_trend': 6,
        'extreme_type': 'max',  # 'max' or 'min'
        'trend_units': 'degree days (F)/year'
    },
    'r95ptot': {
        'long_name': 'Annual precipitation > 95th percentile',
        'units': 'mm',
        'cmap_mean': 'Spectral',
        'cmap_extreme': 'Spectral',
        'cmap_trend': 'BrBG',
        'vmin_mean': 0,
        'vmax_mean': 200,
        'vmin_extreme': 0,
        'vmax_extreme': 200,
        'vmin_trend': -0.2,
        'vmax_trend': 0.2,
        'extreme_type': 'max',  # 'max' or 'min'
        'trend_units': 'mm/year'
    },
    'r95p': {
        'long_name': 'Precipitation amount on very wet days (>95th percentile)',
        'units': 'mm',
        'cmap_mean': 'Spectral',
        'cmap_extreme': 'Spectral',
        'cmap_trend': 'BrBG',
        'vmin_mean': 0,
        'vmax_mean': 1000,
        'vmin_extreme': 0,
        'vmax_extreme': 1000,
        'vmin_trend': -1,
        'vmax_trend': 1,
        'extreme_type': 'max',
        'trend_units': 'mm/year'
    },
    'tasmax': {
        'long_name': 'Maximum air temperature',
        'units': 'degree_Celsius',
        'cmap_mean': 'RdYlBu_r',
        'cmap_extreme': 'RdYlBu_r',
        'cmap_trend': 'RdBu_r',
        'vmin_mean': -40,
        'vmax_mean': 50,
        'vmin_extreme': -40,
        'vmax_extreme': 50,
        'vmin_trend': -0.05,
        'vmax_trend': 0.05,
        'extreme_type': 'max',
        'trend_units': '°C/year'
    },
    'tasmin': {
        'long_name': 'Minimum air temperature',
        'units': 'degree_Celsius',
        'cmap_mean': 'RdYlBu_r',
        'cmap_extreme': 'RdYlBu_r',
        'cmap_trend': 'RdBu_r',
        'vmin_mean': -40,
        'vmax_mean': 40,
        'vmin_extreme': -40,
        'vmax_extreme': 40,
        'vmin_trend': -0.04,
        'vmax_trend': 0.04,
        'extreme_type': 'min',
        'trend_units': 'degree_Celsius/year'
    },
}


# =============================================================================
# CORE FUNCTIONS
# =============================================================================

def load_cckp_data(url_or_path, lat_range=(-60, 90), cache_dir=None):
    """
    Load ERA5 data from CCKP (Climate Change Knowledge Portal).
    
    Parameters
    ----------
    url_or_path : str
        URL or local file path to NetCDF file
    lat_range : tuple
        Latitude range to subset (min, max)
    cache_dir : str or Path, optional
        Directory to cache downloaded files. If provided and file exists,
        will use cached version instead of re-downloading.
        
    Returns
    -------
    xarray.DataArray
        Loaded data array with spatial subset applied
    """
    print(f"Loading data from: {url_or_path}")
    
    # Check if URL or local path
    is_url = url_or_path.startswith('http://') or url_or_path.startswith('https://')
    
    if is_url:
        # For remote files, download to cache or temp location
        import tempfile
        import urllib.request
        import hashlib
        
        if cache_dir:
            # Use cache directory
            cache_path = Path(cache_dir)
            cache_path.mkdir(parents=True, exist_ok=True)
            
            # Create unique filename based on URL hash
            url_hash = hashlib.md5(url_or_path.encode()).hexdigest()[:16]
            cached_file = cache_path / f"cckp_{url_hash}.nc"
            
            if cached_file.exists():
                print(f"  Using cached file: {cached_file}")
                ds = xr.open_dataset(cached_file)
            else:
                print("  Downloading remote file...")
                urllib.request.urlretrieve(url_or_path, cached_file)
                print(f"  Downloaded and cached to: {cached_file}")
                ds = xr.open_dataset(cached_file)
        else:
            # Use temporary file
            print("  Downloading remote file to temporary location...")
            print("  (Tip: Use --cache-dir to avoid re-downloading)")
            temp_dir = tempfile.mkdtemp()
            temp_file = Path(temp_dir) / "temp_data.nc"
            
            try:
                urllib.request.urlretrieve(url_or_path, temp_file)
                print(f"  Downloaded successfully")
                ds = xr.open_dataset(temp_file)
            except Exception as e:
                # Clean up temp file on error
                if temp_file.exists():
                    temp_file.unlink()
                if Path(temp_dir).exists():
                    try:
                        Path(temp_dir).rmdir()
                    except:
                        pass
                raise RuntimeError(f"Failed to download or open remote file: {e}")
    else:
        # Local file - open directly
        ds = xr.open_dataset(url_or_path)
    
    # Get the main data variable (assuming it's the first data variable)
    var_names = [v for v in ds.data_vars]
    if len(var_names) == 0:
        raise ValueError("No data variables found in dataset")
    
    var_name = var_names[0]
    print(f"  Variable found: {var_name}")
    
    da = ds[var_name]

    # Convert timedelta data to numeric (days) if needed
    if np.issubdtype(da.dtype, np.timedelta64):
        print(f"  Converting timedelta64 data to days (float)...")
        da = da.copy()
        da.values = da.values.astype('timedelta64[D]').astype(np.float64)
    
    # Apply latitude subset if lat coordinate exists
    if 'lat' in da.coords:
        da = da.sel(lat=slice(lat_range[0], lat_range[1]))
    
    print(f"  Time range: {da.time.values[0]} to {da.time.values[-1]}")
    print(f"  Shape: {da.shape}")
    
    # Load data into memory if using temp file to allow cleanup
    if is_url and not cache_dir:
        print("  Loading data into memory...")
        da = da.load()
        ds.close()
        # Clean up temp file
        if 'temp_file' in locals() and temp_file.exists():
            temp_file.unlink()
        if 'temp_dir' in locals() and Path(temp_dir).exists():
            try:
                Path(temp_dir).rmdir()
            except:
                pass
    
    return da


def calculate_statistics(da, reference_period=(1990, 2020), extreme_type='max'):
    """
    Calculate mean, extreme, and trend statistics for climate data.
    
    Parameters
    ----------
    da : xarray.DataArray
        Input climate data with time dimension
    reference_period : tuple
        Years for reference period mean (start, end)
    extreme_type : str
        Type of extreme to calculate: 'max' or 'min'
        
    Returns
    -------
    dict
        Dictionary containing 'mean', 'extreme', 'slope', 't_stat', and 'p_values'
    """
    print("\nCalculating statistics...")
    
    # Reference period mean
    ref_start, ref_end = reference_period
    print(f"  Reference period mean: {ref_start}-{ref_end}")
    da_ref = da.sel(time=slice(str(ref_start), str(ref_end)))
    mean = da_ref.mean(dim='time', skipna=True)
    
    # Extreme value
    if extreme_type == 'max':
        extreme = da.max(dim='time', skipna=True)
        print(f"  Calculating maximum values")
    else:
        extreme = da.min(dim='time', skipna=True)
        print(f"  Calculating minimum values")
    
    # Trend calculation
    print("  Calculating trends and significance...")
    time_numeric = (da['time'] - da['time'][0]).astype('timedelta64[D]').astype("int64")

    slope = calculate_trend(da[1:])
    t_stat = xr.apply_ufunc(
        calculate_t_statistic,
        da,
        time_numeric,
        input_core_dims=[['time'], ['time']],
        exclude_dims={'time'},
        vectorize=True,
        dask='parallelized',
        output_dtypes=[float]
    )
    
    # Calculate p-values
    df = len(da['time']) - 2
    p_values = xr.apply_ufunc(
        lambda t: 2 * (1 - stats.t.cdf(np.abs(t), df)),
        t_stat,
        output_dtypes=[float]
    )
    
    return {
        'mean': mean,
        'extreme': extreme,
        'slope': slope,
        't_stat': t_stat,
        'p_values': p_values
    }

def calculate_trend(da):
    """
    Calculate linear trend using polynomial fit.
    
    Parameters
    ----------
    da : xarray.DataArray
        Data with time dimension
        
    Returns
    -------
    xarray.DataArray
        Slope values (units per year)
    """
    # Simple approach: use integer indices for time (0, 1, 2, 3, ...)
    n_times = len(da['time'])
    time_indices = np.arange(n_times, dtype=float)
    
    # Calculate actual time spacing in years for unit conversion
    time_values = da['time'].values
    try:
        # Try to get year from datetime
        years = np.array([pd.Timestamp(t).year for t in time_values])
        time_span_years = years[-1] - years[0]
        years_per_index = time_span_years / (n_times - 1)
    except:
        # Fallback: assume annual data
        years_per_index = 1.0
    
    # Create new DataArray with numeric data and integer time indices
    da_numeric = xr.DataArray(
        da.values.astype(np.float64),  # Ensure float64
        dims=['time', 'lat', 'lon'],
        coords={
            'lat': da['lat'].values,
            'lon': da['lon'].values
        }
    )
    # Assign numeric time coordinate
    da_numeric = da_numeric.assign_coords(time=time_indices)
    
    # Polyfit with integer indices
    linear_trend = da_numeric.polyfit(dim='time', deg=1, skipna=True)
    
    # Extract slope (units per index)
    slope = linear_trend.polyfit_coefficients.sel(degree=1)
    
    # Convert from per-index to per-year
    slope = slope * (1.0 / years_per_index)
    
    # Clean up coordinates
    if 'time' in slope.coords:
        slope = slope.drop_vars('time')
    
    return slope

def calculate_t_statistic(data, time_coords):
    """
    Calculate t-statistic for trend significance.
    
    Parameters
    ----------
    data : numpy.ndarray
        Time series data
    time_coords : numpy.ndarray
        Numeric time coordinates
        
    Returns
    -------
    float
        t-statistic value
    """
    slope, intercept, r_value, p_value, std_err = stats.linregress(time_coords, data)
    
    if std_err == 0:  # Handle constant data
        return np.nan
    else:
        return slope / std_err


def create_output_netcdf(stats_dict, config, original_da, output_path, 
                        reference_period=(1990, 2020)):
    """
    Create NetCDF file with processed statistics and comprehensive metadata.
    
    Parameters
    ----------
    stats_dict : dict
        Dictionary with 'mean', 'extreme', and 'slope' DataArrays
    config : dict
        Variable configuration dictionary
    original_da : xarray.DataArray
        Original input data for coordinate reference
    output_path : str or Path
        Output file path
    reference_period : tuple
        Reference period used for mean calculation
    """
    print(f"\nCreating output NetCDF: {output_path}")
    
    # Create dataset with all statistics
    ds_out = xr.Dataset({
        'mean': stats_dict['mean'],
        'extreme': stats_dict['extreme'],
        'trend': stats_dict['slope'],
        'trend_significance': stats_dict['p_values']
    })
    
    # Add variable attributes
    ds_out['mean'].attrs = {
        'long_name': f"Mean {config['long_name']} ({reference_period[0]}-{reference_period[1]})",
        'units': config['units'],
        'description': f"Mean calculated over reference period {reference_period[0]}-{reference_period[1]}"
    }
    
    extreme_label = 'Maximum' if config['extreme_type'] == 'max' else 'Minimum'
    ds_out['extreme'].attrs = {
        'long_name': f"{extreme_label} {config['long_name']}",
        'units': config['units'],
        'description': f"{extreme_label} value over entire time period"
    }
    
    ds_out['trend'].attrs = {
        'long_name': f"Linear trend of {config['long_name']}",
        'units': config['trend_units'],
        'description': 'Linear trend calculated using least squares regression'
    }
    
    ds_out['trend_significance'].attrs = {
        'long_name': 'Two-tailed p-value for trend significance',
        'units': '1',
        'description': 'P-values from t-test. Values < 0.05 indicate statistical significance at 95% confidence level'
    }
    
    # Add global attributes
    time_start = str(original_da.time.values[0])[:10]
    time_end = str(original_da.time.values[-1])[:10]
    
    ds_out.attrs = {
        'title': f'Climate Risk Statistics: {config["long_name"]}',
        'source': 'ERA5 reanalysis via Climate Change Knowledge Portal (CCKP)',
        'source_url': 'https://climateknowledgeportal.worldbank.org/',
        'institution': 'World Bank Climate Change Knowledge Portal',
        'history': f'Created on {datetime.now().strftime("%Y-%m-%d %H:%M:%S")} using climate_risk_mapper.py',
        'references': 'Hersbach et al. (2020): ERA5 reanalysis',
        'time_coverage_start': time_start,
        'time_coverage_end': time_end,
        'reference_period': f'{reference_period[0]}-{reference_period[1]}',
        'spatial_resolution': '0.25 degrees',
        'conventions': 'CF-1.8',
        'comment': 'Statistics calculated for climate risk assessment'
    }
    
    # Save to NetCDF
    ds_out.to_netcdf(output_path, 
                     encoding={var: {'zlib': True, 'complevel': 4} 
                              for var in ds_out.data_vars})
    
    print(f"  Successfully saved NetCDF file")
    print(f"  Variables: {list(ds_out.data_vars)}")


# =============================================================================
# PLOTTING FUNCTIONS
# =============================================================================

def setup_map_axes(ax):
    """
    Set up cartopy map with standard features.
    
    Parameters
    ----------
    ax : matplotlib.axes.Axes
        Axes with cartopy projection
        
    Returns
    -------
    tuple
        (ax, gridlines) objects
    """
    xticks = np.arange(-180, 181, 90)
    yticks = np.arange(-60, 91, 30)
    
    # Add map features
    ax.add_feature(cfeature.OCEAN, facecolor='gainsboro', zorder=2)
    ax.add_feature(cfeature.COASTLINE.with_scale('110m'), linewidths=1.2)
    ax.add_feature(cfeature.BORDERS.with_scale('110m'), linewidths=0.5)
    
    # Add gridlines
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
    """
    Add colorbar to the right of an axes.
    
    Parameters
    ----------
    fig : matplotlib.figure.Figure
        Figure object
    ax : matplotlib.axes.Axes
        Axes to align colorbar with
    mappable : matplotlib.cm.ScalarMappable
        Mappable object from contour/pcolormesh
    label : str
        Colorbar label
    """
    pos = ax.get_position()
    cbar_ax = fig.add_axes([pos.x1 + 0.02, pos.y0 + 0.02, 0.02, pos.y1 - pos.y0 - 0.04])
    fig.colorbar(mappable, cax=cbar_ax, orientation='vertical', label=label)


def create_risk_map(stats_dict, config, output_path, show_significance=True):
    """
    Create three-panel risk map figure.
    
    Parameters
    ----------
    stats_dict : dict
        Dictionary with statistical results
    config : dict
        Variable configuration
    output_path : str or Path
        Output figure path
    show_significance : bool
        Whether to show stippling for significant trends
    """
    print(f"\nCreating risk map figure: {output_path}")
    
    # Get colormaps
    if HAS_CUSTOM_CMAPS:
        cmap_mean = getattr(cmaps, 'nice_gfdl', config['cmap_mean'])
        cmap_extreme = getattr(cmaps, 'nice_gfdl', config['cmap_extreme'])
        cmap_trend = getattr(cmaps, 'cmaps.BlueWhiteOrangeRed', config['cmap_trend'])
    else:
        cmap_mean = config['cmap_mean']
        cmap_extreme = config['cmap_extreme']
        cmap_trend = config['cmap_trend']
    
    # Prepare data for plotting
    vis_data = [stats_dict['mean'], stats_dict['extreme'], stats_dict['slope']]
    vmins = [config['vmin_mean'], config['vmin_extreme'], config['vmin_trend']]
    vmaxs = [config['vmax_mean'], config['vmax_extreme'], config['vmax_trend']]
    
    extreme_label = 'Maximum' if config['extreme_type'] == 'max' else 'Minimum'
    titles = [
        f"a) Mean {config['long_name']} (1990-2020)",
        f"b) {extreme_label} {config['long_name']}",
        f"c) Trend of {config['long_name']}"
    ]
    
    labels = [config['units'], config['units'], config['trend_units']]
    cmaps_list = [cmap_mean, cmap_extreme, cmap_trend]
    
    # Create figure
    pcrs = ccrs.Robinson()
    tcrs = ccrs.PlateCarree()
    
    fig, axes = plt.subplots(3, 1, figsize=(6, 8.3),
                            subplot_kw={"projection": pcrs})
    
    fig.subplots_adjust(left=0.03, right=0.90, top=0.95, 
                       bottom=0.05, hspace=0.25)
    
    # Plot each panel
    for i, ax in enumerate(axes):
        # Get coordinates
        lon = vis_data[i].lon.values
        lat = vis_data[i].lat.values
        X, Y = np.meshgrid(lon, lat)
        
        # Create plot
        cf = ax.pcolormesh(X, Y, vis_data[i], 
                          vmin=vmins[i], vmax=vmaxs[i],
                          cmap=cmaps_list[i],
                          transform=tcrs)
        
        # Add map features
        setup_map_axes(ax)
        add_colorbar(fig, ax, cf, labels[i])
        ax.set_title(titles[i], loc='left', fontsize=10)
    
    # Add significance stippling to trend panel
    if show_significance and 'p_values' in stats_dict:
        alpha = 0.05
        significant_mask = stats_dict['p_values'] < alpha
        axes[2].contourf(X, Y, significant_mask,
                        levels=[0.5, 1.5],
                        colors='none',
                        hatches=['...'],
                        transform=tcrs)
    
    # Save figure
    plt.savefig(output_path, dpi=300, bbox_inches='tight')
    print(f"  Figure saved successfully")
    
    return fig


# =============================================================================
# MAIN EXECUTION
# =============================================================================

def main():
    """Main execution function."""
    
    parser = argparse.ArgumentParser(
        description='Create climate risk maps from CCKP ERA5 data',
        formatter_class=argparse.RawDescriptionHelpFormatter,
        epilog="""
Examples:
  python climate_risk_mapper.py r95ptot
  python climate_risk_mapper.py tasmax --output-dir ./output --no-significance
  python climate_risk_mapper.py pr --reference-period 1981 2010
        """
    )
    
    parser.add_argument('variable', 
                       help='Variable code (e.g., r95ptot, tasmax, pr)')
    parser.add_argument('--url', 
                       help='URL or path to NetCDF file (if not provided, uses CCKP default)')
    parser.add_argument('--output-dir', default='./output',
                       help='Output directory (default: ./output)')
    parser.add_argument('--cache-dir', 
                       help='Cache directory for downloaded files (optional, skips re-downloading)')
    parser.add_argument('--reference-period', nargs=2, type=int, 
                       default=[1990, 2020],
                       help='Reference period for mean (default: 1990 2020)')
    parser.add_argument('--no-significance', action='store_true',
                       help='Do not show significance stippling on trend map')
    parser.add_argument('--lat-range', nargs=2, type=float,
                       default=[-60, 90],
                       help='Latitude range (default: -60 90)')
    
    args = parser.parse_args()
    
    # Check if variable is configured
    if args.variable not in VARIABLE_CONFIG:
        print(f"Warning: Variable '{args.variable}' not in predefined configurations.")
        print(f"Available variables: {', '.join(VARIABLE_CONFIG.keys())}")
        print("Attempting to load with default settings...")
        config = VARIABLE_CONFIG['pr'].copy()  # Use precipitation defaults
        config['long_name'] = args.variable
    else:
        config = VARIABLE_CONFIG[args.variable]
    
    # Create output directory
    output_dir = Path(args.output_dir)
    output_dir.mkdir(parents=True, exist_ok=True)
    
    # Determine data URL/path
    if args.url:
        data_source = args.url
    else:
        # Default CCKP URL pattern
        var_map = {
            'r95ptot': 'r95ptot',
            'r95p': 'r95p',
            'tasmax': 'tasmax',
            'tasmin': 'tasmin',
            'tas': 'tas',
            'pr': 'pr'
        }
        var_path = var_map.get(args.variable, args.variable)
        data_source = (
            f"https://wbg-cckp.s3.amazonaws.com/data/era5-x0.25/{var_path}/"
            f"era5-x0.25-historical/timeseries-{var_path}-annual-mean_"
            f"era5-x0.25_era5-x0.25-historical_timeseries_mean_1950-2024.nc"
        )
    
    print("=" * 70)
    print("CLIMATE RISK MAPPER")
    print("=" * 70)
    print(f"Variable: {args.variable}")
    print(f"Configuration: {config['long_name']}")
    print(f"Data source: {data_source}")
    print(f"Output directory: {output_dir}")
    print("=" * 70)
    
    # Load data
    da = load_cckp_data(data_source, 
                        lat_range=tuple(args.lat_range),
                        cache_dir=args.cache_dir)
    
    # Calculate statistics
    stats_dict = calculate_statistics(
        da, 
        reference_period=tuple(args.reference_period),
        extreme_type=config['extreme_type']
    )
    
    # Create outputs
    output_nc = output_dir / f"{args.variable}_statistics.nc"
    output_fig = output_dir / f"{args.variable}_risk_map.png"
    
    create_output_netcdf(
        stats_dict, config, da, output_nc,
        reference_period=tuple(args.reference_period)
    )
    
    create_risk_map(
        stats_dict, config, output_fig,
        show_significance=not args.no_significance
    )
    
    print("\n" + "=" * 70)
    print("PROCESSING COMPLETE")
    print("=" * 70)
    print(f"NetCDF output: {output_nc}")
    print(f"Figure output: {output_fig}")
    print("=" * 70)


if __name__ == '__main__':
    main()
