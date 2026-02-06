# Variable Configuration Quick Reference

## How the Configuration Works

Each variable in `VARIABLE_CONFIG` dictionary controls:
1. Plot aesthetics (colormaps, ranges)
2. Statistical calculations (extreme type)
3. Metadata (units, descriptions)
4. Output formatting

## Configuration Parameters Explained

```python
'variable_code': {
    'long_name': str,        # Descriptive name for labels
    'units': str,            # Data units (e.g., 'mm', '°C')
    'cmap_mean': str,        # Colormap for mean panel
    'cmap_extreme': str,     # Colormap for extreme panel
    'cmap_trend': str,       # Colormap for trend panel (diverging)
    'vmin_mean': float,      # Min value for mean colorbar
    'vmax_mean': float,      # Max value for mean colorbar
    'vmin_extreme': float,   # Min value for extreme colorbar
    'vmax_extreme': float,   # Max value for extreme colorbar
    'vmin_trend': float,     # Min value for trend colorbar
    'vmax_trend': float,     # Max value for trend colorbar
    'extreme_type': str,     # 'max' or 'min'
    'trend_units': str       # Units for trend (e.g., 'mm/year')
}
```

## Pre-configured Variables

### Precipitation Variables

#### r95ptot - Annual precipitation > 95th percentile
- **Units**: mm
- **Extreme**: Maximum
- **Trend**: mm/year
- **Use case**: Extreme precipitation events
- **Color scheme**: Blues (sequential)

#### r95p - Very wet day precipitation
- **Units**: mm  
- **Extreme**: Maximum
- **Trend**: mm/year
- **Use case**: Heavy rainfall intensity
- **Color scheme**: Blues (sequential)

#### pr - Total precipitation
- **Units**: mm
- **Extreme**: Maximum  
- **Trend**: mm/year
- **Use case**: Overall precipitation patterns
- **Color scheme**: Blues (sequential)

### Temperature Variables

#### tasmax - Maximum temperature
- **Units**: °C
- **Extreme**: Maximum
- **Trend**: °C/decade
- **Use case**: Heat extremes
- **Color scheme**: RdYlBu_r (diverging)

#### tasmin - Minimum temperature  
- **Units**: °C
- **Extreme**: Minimum (note: minimum of minimums)
- **Trend**: °C/decade
- **Use case**: Cold extremes
- **Color scheme**: RdYlBu_r (diverging)

#### tas - Mean temperature
- **Units**: °C
- **Extreme**: Maximum
- **Trend**: °C/decade  
- **Use case**: Average temperature trends
- **Color scheme**: RdYlBu_r (diverging)

## Choosing Colormap Ranges

### Tips for setting vmin/vmax:

1. **Check data range first**: Load sample data to see actual values
2. **Use symmetric ranges for trends**: e.g., -10 to +10
3. **Consider your audience**: Scientific vs. general public
4. **Regional vs. global**: Global maps need wider ranges

### Example workflow:
```python
# Quick data exploration
import xarray as xr
da = xr.open_dataset('your_file.nc')
print(da.min(), da.max(), da.mean())
```

## Colormap Recommendations

### Matplotlib sequential colormaps (for positive-only data):
- `'Blues'` - Precipitation
- `'YlOrRd'` - Temperature extremes  
- `'Greens'` - Vegetation
- `'Purples'` - Other quantities

### Matplotlib diverging colormaps (for trends/anomalies):
- `'RdBu_r'` - Temperature (red=warm, blue=cold)
- `'BrBG'` - Precipitation (brown=dry, green=wet)
- `'PiYG'` - Generic (purple=negative, yellow-green=positive)
- `'RdYlBu_r'` - Temperature ranges

### Custom colormaps (if available):
- `cmaps.nice_gfdl` - Clean sequential
- `cmaps.precip_diff_12lev` - Precipitation anomalies

## Adding a New Variable

### Template:
```python
'your_var': {
    'long_name': 'Your Variable Description',
    'units': 'unit',
    'cmap_mean': 'appropriate_sequential_cmap',
    'cmap_extreme': 'appropriate_sequential_cmap',
    'cmap_trend': 'appropriate_diverging_cmap',
    'vmin_mean': min_value,
    'vmax_mean': max_value,
    'vmin_extreme': min_extreme,
    'vmax_extreme': max_extreme,
    'vmin_trend': -symmetric_value,
    'vmax_trend': +symmetric_value,
    'extreme_type': 'max',  # or 'min'
    'trend_units': 'unit/year'  # or '/decade'
}
```

### Example - Adding wind speed:
```python
'sfcWind': {
    'long_name': 'Near-surface wind speed',
    'units': 'm/s',
    'cmap_mean': 'YlOrRd',
    'cmap_extreme': 'YlOrRd',
    'cmap_trend': 'RdBu_r',
    'vmin_mean': 0,
    'vmax_mean': 15,
    'vmin_extreme': 0,
    'vmax_extreme': 25,
    'vmin_trend': -1,
    'vmax_trend': 1,
    'extreme_type': 'max',
    'trend_units': 'm/s/decade'
}
```

## Other CCKP ERA5 Variables

Variables you might want to add configurations for:

- `cdd` - Consecutive dry days
- `cwd` - Consecutive wet days  
- `r20mm` - Days with >20mm precipitation
- `rx1day` - Maximum 1-day precipitation
- `rx5day` - Maximum 5-day precipitation
- `tr` - Tropical nights (Tmin > 20°C)
- `su` - Summer days (Tmax > 25°C)
- `tn10p` - Cold night frequency
- `tx90p` - Hot day frequency

Visit [CCKP Data Catalog](https://wbg-cckp.s3.amazonaws.com/index.html) for complete list.

## Troubleshooting Variable Configs

### Problem: Data values way outside colorbar range
**Solution**: Adjust vmin/vmax after checking actual data range

### Problem: Trend panel hard to interpret
**Solution**: Ensure diverging colormap with symmetric range around 0

### Problem: Mean and extreme look identical  
**Solution**: Adjust vmax_extreme to be higher than vmax_mean

### Problem: Wrong extreme shown (e.g., minimum when should be maximum)
**Solution**: Check `extreme_type` setting in config

## Best Practices

1. **Always check your data first** before setting colorbar ranges
2. **Use consistent color schemes** across related variables
3. **Document your choices** if deviating from standards
4. **Test with real data** before producing final figures
5. **Consider colorblind-friendly palettes** for publications

## References

- [Matplotlib colormaps](https://matplotlib.org/stable/tutorials/colors/colormaps.html)
- [ColorBrewer](https://colorbrewer2.org/) - Scientific color schemes
- [CCKP documentation](https://climateknowledgeportal.worldbank.org/)
