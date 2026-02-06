# Climate Risk Mapper

A generalized Python script for creating climate risk maps from ERA5-derived data available through the World Bank's Climate Change Knowledge Portal (CCKP).

## Features

- **Automated data loading** from CCKP S3 buckets or local files
- **Three-panel risk maps** showing:
  - Mean values (1990-2020 reference period, customizable)
  - Extreme values (maximum or minimum depending on variable)
  - Linear trends with significance testing
- **NetCDF output** with comprehensive metadata and CF-1.8 conventions
- **Pre-configured variables** with appropriate colormaps and scales
- **Publication-quality figures** with Robinson projection

## Installation

### Required packages:
```bash
pip install xarray netCDF4 matplotlib cartopy scipy numpy
```

### Optional (for custom colormaps):
```bash
# If you have the custom colormaps module
pip install colormaps
```

## Usage

### Basic usage:
```bash
python climate_risk_mapper.py r95ptot
```

### Use cache to avoid re-downloading:
```bash
# First run downloads and caches
python climate_risk_mapper.py r95ptot --cache-dir ./data_cache

# Subsequent runs use cached file
python climate_risk_mapper.py r95ptot --cache-dir ./data_cache
```

### Specify custom reference period:
```bash
python climate_risk_mapper.py tasmax --reference-period 1981 2010
```

### Use local file instead of downloading:
```bash
python climate_risk_mapper.py pr --url /path/to/data.nc
```

### Customize output location:
```bash
python climate_risk_mapper.py r95p --output-dir ./my_results
```

### All options:
```bash
python climate_risk_mapper.py --help
```

## Supported Variables

The script includes pre-configured settings for:

| Variable | Description | Units | Extreme Type |
|----------|-------------|-------|--------------|
| `r95ptot` | Annual precipitation > 95th percentile | mm | maximum |
| `r95p` | Precipitation on very wet days | mm | maximum |
| `pr` | Total precipitation | mm | maximum |
| `tasmax` | Maximum air temperature | °C | maximum |
| `tasmin` | Minimum air temperature | °C | minimum |
| `tas` | Mean air temperature | °C | maximum |

### Adding new variables:

Edit the `VARIABLE_CONFIG` dictionary in the script:

```python
'your_variable': {
    'long_name': 'Your Variable Description',
    'units': 'your_units',
    'cmap_mean': 'Blues',           # matplotlib colormap
    'cmap_extreme': 'Blues',
    'cmap_trend': 'RdBu_r',
    'vmin_mean': 0,                 # colorbar limits
    'vmax_mean': 100,
    'vmin_extreme': 0,
    'vmax_extreme': 150,
    'vmin_trend': -5,
    'vmax_trend': 5,
    'extreme_type': 'max',          # 'max' or 'min'
    'trend_units': 'units/year'
}
```

## Output Files

### NetCDF file (`<variable>_statistics.nc`)

Contains four variables:
- **mean**: Reference period mean (default 1990-2020)
- **extreme**: Maximum or minimum value over entire period
- **trend**: Linear trend in units per year (or per decade for temperature)
- **trend_significance**: P-values from t-test (< 0.05 = significant)

Includes comprehensive global attributes:
- Source information and references
- Processing history
- Time coverage
- Spatial resolution
- CF-1.8 conventions

### Figure file (`<variable>_risk_map.png`)

Three-panel figure with:
- Panel (a): Mean during reference period
- Panel (b): Extreme value
- Panel (c): Linear trend with significance stippling

## Examples

### Example 1: Precipitation extremes
```bash
python climate_risk_mapper.py r95ptot --output-dir ./precip_analysis
```

### Example 2: Temperature trends with custom reference
```bash
python climate_risk_mapper.py tasmax \
  --reference-period 1981 2010 \
  --output-dir ./temp_analysis
```

### Example 3: Using local data
```bash
python climate_risk_mapper.py pr \
  --url /path/to/my/precipitation_data.nc \
  --output-dir ./my_results \
  --lat-range -90 90
```

## Data Sources

Default data source: [Climate Change Knowledge Portal](https://climateknowledgeportal.worldbank.org/)

ERA5 data via AWS S3:
```
https://wbg-cckp.s3.amazonaws.com/data/era5-x0.25/
```

### Working with Local Files

If you prefer to download files manually or work offline:

1. **Download the file** from CCKP S3 or via browser
2. **Use the `--url` flag** to point to your local file:
   ```bash
   python climate_risk_mapper.py r95ptot --url /path/to/downloaded_file.nc
   ```

### Caching Downloaded Files

To avoid re-downloading the same file:

```bash
# Create a cache directory
mkdir -p ./cckp_cache

# Use --cache-dir flag
python climate_risk_mapper.py r95ptot --cache-dir ./cckp_cache

# Process multiple variables using the same cache
python climate_risk_mapper.py tasmax --cache-dir ./cckp_cache
python climate_risk_mapper.py pr --cache-dir ./cckp_cache
```

The cache directory stores downloaded files with unique identifiers, so you can safely reuse it for different analyses.

## Technical Details

### Statistical Methods

- **Mean calculation**: Arithmetic mean over reference period with `skipna=True`
- **Trend estimation**: Ordinary least squares linear regression
- **Significance testing**: Two-tailed t-test with n-2 degrees of freedom
- **Significance threshold**: α = 0.05 (95% confidence level)

### Coordinate Systems

- **Input data**: Plate Carrée (geographic coordinates)
- **Output projection**: Robinson projection (for global display)
- **Default spatial extent**: 60°S to 90°N

### NetCDF Conventions

- CF-1.8 metadata conventions
- Compressed output (zlib compression level 4)
- Full provenance in global attributes
- Variable-specific attributes with descriptions

## Customization

### Custom fonts

Edit lines 31-39 in the script to point to your font file:

```python
font_dir = '/path/to/your/font.otf'
```

### Custom colormaps

Install the `colormaps` package or modify the `VARIABLE_CONFIG` to use standard matplotlib colormaps.

### Map extent

Modify the `lat_range` argument or edit the `load_cckp_data()` function for different spatial domains.

## Troubleshooting

### "No data variables found in dataset"
Check that your NetCDF file contains actual data variables, not just coordinates.

### Missing colormap warnings
Install custom colormaps package or script will fall back to matplotlib defaults.

### Font warnings
Script will use system default fonts if custom fonts are not found.

### Network errors
If downloading from CCKP fails, try downloading the file manually and using `--url` flag.

## Citation

If you use this tool in a publication, please cite:

- ERA5 reanalysis: Hersbach et al. (2020)
- CCKP: World Bank Climate Change Knowledge Portal

## Author

Jacob Stuivenvolt-Allen  
Modified: February 2026

## License

This script is provided as-is for research and educational purposes.
