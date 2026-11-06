"""
CMIP6 Variable Configuration
=============================
Plot configuration for CMIP6 ensemble-median climate risk maps
(historical / mid-century / end-century / change).

This mirrors the structure of VARIABLE_CONFIG in climate_risk_mapper.py,
but with a different panel layout:

  ERA5 script:  mean / extreme / trend
  This script:  historical median / future median / change (future - historical)

Since the historical, mid-century, and end-century panels all show the same
*kind* of quantity (an ensemble median field), they share one colormap and
range: cmap_median / vmin_median / vmax_median. The change panels (mid -
historical, end - historical) get a separate diverging colormap and range:
cmap_change / vmin_change / vmax_change.

Starting points below:
  - cmap_median / vmin_median / vmax_median: for the original variable set
    (tas, tasmax, tasmin, r95ptot, r95p, sfcgustx, spei12, gsl, sdii, hi,
    cwd, cdd, hdd65, cdd65), copied directly from the ERA5 script's
    cmap_mean / vmin_mean / vmax_mean, since it's the same physical
    quantity on the same natural scale. Everything else added below is a
    fresh ESTIMATE based on the variable's typical physical range -- NOT
    yet checked against real CCKP/CMIP6 data.
  - cmap_change: reused the ERA5 script's cmap_trend choice where
    available (RdYlBu_r/RdBu_r for temperature-like variables, BrBG for
    precipitation-like variables); extended the same convention to new
    variables by physical family.
  - vmin_change / vmax_change: **PLACEHOLDER ONLY, for every variable in
    this file, original and new alike.** None of these have been checked
    against real CMIP6 change fields. Expect to iterate once you've
    plotted actual data -- a 30-year total change is a very different
    scale than a per-year trend slope, and projected model change need
    not resemble any historical observed trend.

NEEDS VERIFICATION -- flagged inline below, worth confirming against
CCKP's own variable metadata (e.g. via the file's long_name/units
attributes once downloaded, the way 'Warm Spell Duration Index' was
confirmed for wsdi) before trusting the numbers:
  - sd:      definition/units genuinely unclear (snow depth vs. snow
             water equivalent, mm vs. cm) -- placeholder assumes mm.
  - tx84rr:  not a standard climate-index name; likely a CCKP-specific
             threshold/return-period metric. Treated here as a generic
             hot-day-count placeholder pending confirmation.
  - gslstart / gslend: assumed to be day-of-year (1-365) values.

For the hd*/hi*/tr*/wbt* threshold-count families, vmin_change/
vmax_change estimates are scaled DOWN as the threshold gets more
extreme, since a higher threshold implies a smaller baseline day-count
and so plausibly a smaller absolute change too. These are still guesses.
"""

CMIP6_VARIABLE_CONFIG = {
    'cdd': {
        'long_name': 'cdd: consecutive dry days',
        'description': 'Longest run of consecutive dry days with rainfall rate (<1mm)',
        'units': 'days',
        'cmap_median': 'nice_gfdl',
        'vmin_median': 0,
        'vmax_median': 300,
        'cmap_change': 'RdYlBu_r',
        'vmin_change': -30,  # PLACEHOLDER
        'vmax_change': 30,   # PLACEHOLDER
    },
    'cdd65': {
        'long_name': 'cdd65: cooling degree days (degF)',
        'description': 'Sum of (Tavg - 65°F) on days when Tavg > 65°F; indicator of when airconditiong/cooling needed',
        'units': 'degree days (F)',
        'cmap_median': 'nice_gfdl',
        'vmin_median': 0,
        'vmax_median': 10000,
        'cmap_change': 'YlOrRd',
        'vmin_change': 0,
        'vmax_change': 2000,
    },
    'cwd': {
        'long_name': 'cwd: consecutive wet days',
        'description': 'Longest run of consecutive days with RR >= 1 mm',
        'units': 'days',
        'cmap_median': 'nice_gfdl',
        'vmin_median': 0,
        'vmax_median': 200,
        'cmap_change': 'RdYlBu',
        'vmin_change': -20,
        'vmax_change': 20,
    },
    'fd': {
        'long_name': 'fd: frost days',
        'description': 'Count of days with Tmin < freezing (0°C / 32°F)',
        'units': 'days',
        'cmap_median': 'nice_gfdl',
        'vmin_median': 0,
        'vmax_median': 360,
        'cmap_change': 'Blues_r',
        'vmin_change': -60,
        'vmax_change': 0,
    },
    'gsl': {
        'long_name': 'gsl: growing season length',
        'description': 'Count of days after the first 5+ days >5ºC to first 5+ days <5ºC',
        'units': 'days',
        'cmap_median': 'nice_gfdl',
        'vmin_median': 0,
        'vmax_median': 365,
        'cmap_change': 'YlGn',
        'vmin_change': 0,
        'vmax_change': 50,
    },
    'gslend': {
        # NEEDS VERIFICATION: assumed day-of-year
        'long_name': 'gsl end: day of year the growing season ends',
        'description': 'First date with 5+ days <5ºC',        
        'units': 'day of year',
        'cmap_median': 'Spectral',
        'vmin_median': 1,
        'vmax_median': 365,
        'cmap_change': 'RdYlBu_r',
        'vmin_change': -30,  # PLACEHOLDER
        'vmax_change': 30,   # PLACEHOLDER
    },
    'gslstart': {
        # NEEDS VERIFICATION: assumed day-of-year
        'long_name': 'gsl start: day of year the growing season begins',
        'description': 'First date with 5+ days >5ºC', 
        'units': 'day of year',
        'cmap_median': 'Spectral',
        'vmin_median': 1,
        'vmax_median': 365,
        'cmap_change': 'RdYlBu_r',
        'vmin_change': -30,  # PLACEHOLDER
        'vmax_change': 30,   # PLACEHOLDER
    },
    'hd30': {
        'long_name': 'HD30: annual count of days with Tmax > 30 degC',
        'description': 'annual count of days with Tmax > 30 degC',
        'units': 'days',
        'cmap_median': 'nice_gfdl',
        'vmin_median': 0,
        'vmax_median': 365,
        'cmap_change': 'YlOrRd',
        'vmin_change': 0,
        'vmax_change': 120,
    },
    'hd35': {
        'long_name': 'HD35: annual count of days with Tmax > 35 degC',
        'description': 'annual count of days with Tmax > 35 degC',
        'units': 'days',
        'cmap_median': 'nice_gfdl',
        'vmin_median': 0,
        'vmax_median': 300,
        'cmap_change': 'YlOrRd',
        'vmin_change': 0,
        'vmax_change': 120,
    },
    'hd40': {
        'long_name': 'HD40: annual count of days with Tmax > 40 degC',
        'description': 'annual count of days with Tmax > 40 degC',
        'units': 'days',
        'cmap_median': 'nice_gfdl',
        'vmin_median': 0,
        'vmax_median': 150,
        'cmap_change': 'YlOrRd',
        'vmin_change': 0,
        'vmax_change': 100,
    },
    'hd42': {
        'long_name': 'HD42: annual count of days with Tmax > 42 degC',
        'description': 'annual count of days with Tmax > 42 degC',
        'units': 'days',
        'cmap_median': 'nice_gfdl',
        'vmin_median': 0,
        'vmax_median': 100,
        'cmap_change': 'YlOrRd',
        'vmin_change': 0,
        'vmax_change': 80,
    },
    'hd45': {
        'long_name': 'HD45: annual count of days with Tmax > 45 degC',
        'description': 'annual count of days with Tmax > 45 degC',
        'units': 'days',
        'cmap_median': 'nice_gfdl',
        'vmin_median': 0,
        'vmax_median': 75,
        'cmap_change': 'YlOrRd',
        'vmin_change': 0,
        'vmax_change': 60,
    },
    'hd50': {
        'long_name': 'HD50: annual count of days with Tmax > 50 degC',
        'description': 'annual count of days with Tmax > 50 degC',
        'units': 'days',
        'cmap_median': 'nice_gfdl',
        'vmin_median': 0,
        'vmax_median': 50,
        'cmap_change': 'YlOrRd',
        'vmin_change': 0,
        'vmax_change': 40,
    },
    'hdd65': {
        'long_name': 'hdd65: heating degree days (degF)',
        'description': 'Sum of (65ºF - Tavg) on days when Tavg < 65°F; indicator of when heating is needed',
        'units': 'degree days (F)',
        'cmap_median': 'nice_gfdl',
        'vmin_median': 0,
        'vmax_median': 22000,
        'cmap_change': 'Blues_r',
        'vmin_change': -2500,
        'vmax_change': 0,
    },
    'hi': {
        'long_name': 'NWS heat index',
        'description': 'Index used by the U.S. National Weather Service to measure how hot weather feels to the body; combines temperature and humidity',
        'units': 'degree_Celsius',
        'cmap_median': 'Spectral_r',
        'vmin_median': -50,
        'vmax_median': 50,
        'cmap_change': 'YlOrRd',
        'vmin_change': 0,
        'vmax_change': 10,
    },
    'hi35': {
        'long_name': 'HI35: annual count of days with heat index > 35 degC',
        'description': 'Number of days per year where the heat index >35 degC',
        'units': 'days',
        'cmap_median': 'nice_gfdl',
        'vmin_median': 0,
        'vmax_median': 300,
        'cmap_change': 'YlOrRd',
        'vmin_change': 0,
        'vmax_change': 45,   # PLACEHOLDER
    },
    'hi37': {
        'long_name': 'HI37: annual count of days with heat index > 37 degC',
        'description': 'Number of days per year where the heat index >37 degC',        
        'units': 'days',
        'cmap_median': 'nice_gfdl',
        'vmin_median': 0,
        'vmax_median': 250,
        'cmap_change': 'YlOrRd',
        'vmin_change': 0,
        'vmax_change': 35,   # PLACEHOLDER
    },
    'hi39': {
        'long_name': 'HI39: annual count of days with heat index > 39 degC',
        'description': 'Number of days per year where the heat index >39 degC',
        'units': 'days',
        'cmap_median': 'nice_gfdl',
        'vmin_median': 0,
        'vmax_median': 200,
        'cmap_change': 'YlOrRd',
        'vmin_change': 0,
        'vmax_change': 30,   # PLACEHOLDER
    },
    'hi41': {
        'long_name': 'HI41: annual count of days with heat index > 41 degC',
        'description': 'Number of days per year where the heat index >41 degC',
        'units': 'days',
        'cmap_median': 'nice_gfdl',
        'vmin_median': 0,
        'vmax_median': 150,
        'cmap_change': 'YlOrRd',
        'vmin_change': 0,
        'vmax_change': 25,   # PLACEHOLDER
    },
    'hurs': {
        'long_name': 'Near-surface relative humidity',
        'description': 'near surface relative humidity',
        'units': '%',
        'cmap_median': 'YlGnBu',
        'vmin_median': 0,
        'vmax_median': 100,
        'cmap_change': 'BrBG',
        'vmin_change': -8,
        'vmax_change': 8,
    },
    'id': {
        'long_name': 'ID: annual count of ice days (Tmax < 0 degC)',
        'description': 'any day where the warmenst air temperture does not rise above freezing',
        'units': 'days',
        'cmap_median': 'nice_gfdl',
        'vmin_median': 0,
        'vmax_median': 200,
        'cmap_change': 'Blues_r',
        'vmin_change': -40,
        'vmax_change': 0,
    },
    'pr': {
        'long_name': 'Annual total precipitation',
        'description': 'Annual total precipitation',
        'units': 'mm',
        'cmap_median': 'YlGnBu',
        'vmin_median': 0,
        'vmax_median': 3000,
        'cmap_change': 'BrBG',
        'vmin_change': -300, # PLACEHOLDER
        'vmax_change': 300,  # PLACEHOLDER
    },
    'r20mm': {
        'long_name': 'R20mm: annual count of days with precipitation >= 20mm',
        'description': 'Annual number of days when precipitation is greater than 20mm',
        'units': 'days',
        'cmap_median': 'Spectral',
        'vmin_median': 0,
        'vmax_median': 60,
        'cmap_change': 'BrBG',
        'vmin_change': -15,  # PLACEHOLDER
        'vmax_change': 15,   # PLACEHOLDER
    },
    'r50mm': {
        'long_name': 'R50mm: annual count of days with precipitation >= 50mm',
        'description': 'Annual number of days when precipitation is greater than 50mm',
        'units': 'days',
        'cmap_median': 'Spectral',
        'vmin_median': 0,
        'vmax_median': 20,
        'cmap_change': 'BrBG',
        'vmin_change': -8,   # PLACEHOLDER
        'vmax_change': 8,    # PLACEHOLDER
    },
    'r95p': {
        'long_name': 'r95p: Total annual precipitation amount from very wet days (>95th percentile)',
        'description': 'Total amount of precipitation that falls on very wet days, days when precipitaiton exceeds the 95th percentile',
        'units': 'mm',
        'cmap_median': 'Spectral',
        'vmin_median': 0,
        'vmax_median': 1000,
        'cmap_change': 'BrBG',
        'vmin_change': -30,  # PLACEHOLDER
        'vmax_change': 30,   # PLACEHOLDER
    },
    'r95ptot': {
        'long_name': 'r95ptot: Fraction of total annual precipitation that occurs when precipitation > 95 percentile',
        'description': 'Fraction of total annual precipitation calculated on days where precipitation exceeds the 95th percentile',
        'units': '',
        'cmap_median': 'nice_gfdl',
        'vmin_median': 0,
        'vmax_median': 200,
        'cmap_change': 'BrBG',
        'vmin_change': -6,   # PLACEHOLDER (old vmax_trend 0.2 * 30)
        'vmax_change': 6,    # PLACEHOLDER
    },
    'rx1day': {
        'long_name': 'Rx1day: Max 1-day precipitation',
        'description': 'Highest single-day precipitation total in year',
        'units': 'mm',
        'cmap_median': 'Spectral',
        'vmin_median': 0,
        'vmax_median': 300,
        'cmap_change': 'BrBG',
        'vmin_change': -60,  # PLACEHOLDER
        'vmax_change': 60,   # PLACEHOLDER
    },
    'rx5day': {
        'long_name': 'Rx5day: Max 5-day precipitation',
        'units': 'mm',
        'description': 'Highest 5-day consecutive precipitation total in year',
        'cmap_median': 'Spectral',
        'vmin_median': 0,
        'vmax_median': 500,
        'cmap_change': 'BrBG',
        'vmin_change': -100, # PLACEHOLDER
        'vmax_change': 100,  # PLACEHOLDER
    },
    'sd': {
        # NEEDS VERIFICATION: definition/units unclear (depth vs. SWE,
        # mm vs. cm) -- confirm against CCKP metadata before trusting.
        'long_name': 'SD: snow depth (units/definition unverified)',
        'description': 'SD: snow depth (units/definition unverified)',
        'units': 'mm',
        'cmap_median': 'Blues',
        'vmin_median': 0,
        'vmax_median': 500,
        'cmap_change': 'BrBG',
        'vmin_change': -100, # PLACEHOLDER
        'vmax_change': 100,  # PLACEHOLDER
    },
    'sdii': {
        'long_name': 'SDII: Simple daily intensity index',
        'units': 'mm',
        'description': 'Mean precipitation on wet days (RR >= 1 mm)',
        'cmap_median': 'Spectral',
        'vmin_median': 0,
        'vmax_median': 12,
        'cmap_change': 'RdYlBu_r',
        'vmin_change': -1,   # PLACEHOLDER
        'vmax_change': 1,    # PLACEHOLDER
    },
    'sfcgustx': {
        'long_name': 'SFCGUSTX: Maximum Surface Wind Gust (Maximum Over Period)',
        'description': 'estimated maximum 3-second wind gust at the surface',
        'units': 'm/s',
        'cmap_median': 'Spectral',
        'vmin_median': 5,
        'vmax_median': 60,
        'cmap_change': 'RdYlBu_r',
        'vmin_change': -1.5, # PLACEHOLDER
        'vmax_change': 1.5,  # PLACEHOLDER
    },
    'spei12': {
        'long_name': 'SPEI12: 12-month Standardized Precipitation Evapotranspiration Index',
        'description': '12-month Standardized Precipitation Evapotranspiration Index (Pearson distribution)',
        'units': '',
        'cmap_median': 'Spectral',
        'vmin_median': -3.5,
        'vmax_median': 3.5,
        'cmap_change': 'RdYlBu_r',
        'vmin_change': -1.5, # PLACEHOLDER
        'vmax_change': 1.5,  # PLACEHOLDER
    },
    'tas': {
        'long_name': 'Daily mean air temperature',
        'description': 'Average annual daily mean air temperature at 2m',
        'units': 'degree_Celsius',
        'cmap_median': 'RdYlBu_r',
        'vmin_median': -30,
        'vmax_median': 50,
        'cmap_change': 'RdBu_r',
        'vmin_change': -5,   # PLACEHOLDER -- tune after inspecting real data
        'vmax_change': 5,    # PLACEHOLDER
    },
    'tasmax': {
        'long_name': 'Daily maximum air temperature',
        'description': 'Average annual daily maximum air temperature at 2m',
        'units': 'degree_Celsius',
        'cmap_median': 'RdYlBu_r',
        'vmin_median': -30,
        'vmax_median': 50,
        'cmap_change': 'RdBu_r',
        'vmin_change': -5,   # PLACEHOLDER
        'vmax_change': 5,    # PLACEHOLDER
    },
    'tasmin': {
        'long_name': 'Daily minimum air temperature',
        'description': 'Average annual daily mainimum air temperature at 2m',
        'units': 'degree_Celsius',
        'cmap_median': 'RdYlBu_r',
        'vmin_median': -50,
        'vmax_median': 30,
        'cmap_change': 'RdBu_r',
        'vmin_change': -5,   # PLACEHOLDER
        'vmax_change': 5,    # PLACEHOLDER
    },
    'tnn': {
        'long_name': 'TNn: Coldest nighttime low',
        'description': 'annual minimum value of daily minimum temperature',
        'units': 'degree_Celsius',
        'cmap_median': 'RdYlBu_r',
        'vmin_median': -60,
        'vmax_median': 20,
        'cmap_change': 'RdBu_r',
        'vmin_change': -8,   # PLACEHOLDER
        'vmax_change': 8,    # PLACEHOLDER
    },
    'tr': {
        'long_name': 'TR: Tropical nights (Tmin >20 degC)',
        'description': 'annual count of tropical nights (Tmin > 20 degC)',
        'units': 'days',
        'cmap_median': 'Spectral',
        'vmin_median': 0,
        'vmax_median': 365,
        'cmap_change': 'RdYlBu_r',
        'vmin_change': -60,  # PLACEHOLDER
        'vmax_change': 60,   # PLACEHOLDER
    },
    'tr23': {
        'long_name': 'TR23: Tropical nights (Tmin > 23 degC)',
        'description': 'annual count of tropical nights (Tmin > 23 degC)',
        'units': 'days',
        'cmap_median': 'Spectral',
        'vmin_median': 0,
        'vmax_median': 300,
        'cmap_change': 'RdYlBu_r',
        'vmin_change': -50,  # PLACEHOLDER
        'vmax_change': 50,   # PLACEHOLDER
    },
    'tr26': {
        'long_name': 'TR26: Tropical nights (Tmin > 26 degC)',
        'description': 'annual count of tropical nights (Tmin > 26 degC)',
        'units': 'days',
        'cmap_median': 'Spectral',
        'vmin_median': 0,
        'vmax_median': 250,
        'cmap_change': 'RdYlBu_r',
        'vmin_change': -40,  # PLACEHOLDER
        'vmax_change': 40,   # PLACEHOLDER
    },
    'tr32': {
        'long_name': 'TR32: Tropical nights (Tmin > 32 degC)',
        'description': 'annual count of tropical nights (Tmin > 32 degC)',
        'units': 'days',
        'cmap_median': 'Spectral',
        'vmin_median': 0,
        'vmax_median': 150,
        'cmap_change': 'RdYlBu_r',
        'vmin_change': -20,  # PLACEHOLDER
        'vmax_change': 20,   # PLACEHOLDER
    },
    'tx84rr': {
        'long_name': 'TX84rr: Temperature-based excess mortality risk factor',
        'description': 'Number of days where daily maximum temperature exceeds the 84th percentile of all maximum temperatures during the baseline',
        'units': 'days',
        'cmap_median': 'Spectral',
        'vmin_median': 0,
        'vmax_median': 200,
        'cmap_change': 'RdYlBu_r',
        'vmin_change': -30,  # PLACEHOLDER
        'vmax_change': 30,   # PLACEHOLDER
    },
    'txx': {
        'long_name': 'TXx: Hottest daytime high',
        'description': 'Annual maximum value of daily maximum temperature',
        'units': 'degree_Celsius',
        'cmap_median': 'RdYlBu_r',
        'vmin_median': 0,
        'vmax_median': 55,
        'cmap_change': 'RdBu_r',
        'vmin_change': -8,   # PLACEHOLDER
        'vmax_change': 8,    # PLACEHOLDER
    },
    'wbt': {
        'long_name': 'Mean wet bulb temperature',
        'description': 'mean wet bulb temperature',
        'units': 'degree_Celsius',
        'cmap_median': 'RdYlBu_r',
        'vmin_median': -10,
        'vmax_median': 35,
        'cmap_change': 'RdBu_r',
        'vmin_change': -5,   # PLACEHOLDER
        'vmax_change': 5,    # PLACEHOLDER
    },
    'wbt25': {
        'long_name': 'WBT25: Count of days with WBT > 25 degC',
        'description': 'Number of days per year where the wet bulb temperature exceeds 25 degC',
        'units': 'days',
        'cmap_median': 'Spectral',
        'vmin_median': 0,
        'vmax_median': 300,
        'cmap_change': 'RdYlBu_r',
        'vmin_change': -45,  # PLACEHOLDER
        'vmax_change': 45,   # PLACEHOLDER
    },
    'wbt27': {
        'long_name': 'WBT27: Count of days with WBT > 27 degC',
        'description': 'Number of days per year where the wet bulb temperature exceeds 27 degC',
        'units': 'days',
        'cmap_median': 'Spectral',
        'vmin_median': 0,
        'vmax_median': 250,
        'cmap_change': 'RdYlBu_r',
        'vmin_change': -40,  # PLACEHOLDER
        'vmax_change': 40,   # PLACEHOLDER
    },
    'wbt29': {
        'long_name': 'WBT29: Count of days with WBT > 29 degC',
        'description': 'Number of days per year where the wet bulb temperature exceeds 29 degC',
        'units': 'days',
        'cmap_median': 'Spectral',
        'vmin_median': 0,
        'vmax_median': 150,
        'cmap_change': 'RdYlBu_r',
        'vmin_change': -30,  # PLACEHOLDER
        'vmax_change': 30,   # PLACEHOLDER
    },
    'wbt31': {
        'long_name': 'WBT31: Count of days with WBT > 31 degC',
        'description': 'Number of days per year where the wet bulb temperature exceeds 31 degC',        
        'units': 'days',
        'cmap_median': 'Spectral',
        'vmin_median': 0,
        'vmax_median': 60,
        'cmap_change': 'RdYlBu_r',
        'vmin_change': -15,  # PLACEHOLDER
        'vmax_change': 15,   # PLACEHOLDER
    },
    'wd': {
        'long_name': 'WD: Count of wet days (precipitation >= 1mm)',
        'description': 'Number of days per year where precipitation exceeds 1mm',
        'units': 'days',
        'cmap_median': 'Spectral',
        'vmin_median': 0,
        'vmax_median': 365,
        'cmap_change': 'BrBG',
        'vmin_change': -30,  # PLACEHOLDER
        'vmax_change': 30,   # PLACEHOLDER
    },
    'wsdi': {
        'long_name': 'WSDI: Total number of days that are part of a Warm Spell',
        'description': 'Number of days per year contributing to a warm spell where daily maximum tempreature remains above its climatological 90th percentile; must consist of at least 6 days to qualify',
        'units': 'days',
        'cmap_median': 'Spectral',
        'vmin_median': 0,
        'vmax_median': 200,
        'cmap_change': 'RdYlBu_r',
        'vmin_change': -40,  # PLACEHOLDER
        'vmax_change': 40,   # PLACEHOLDER
    },
}
