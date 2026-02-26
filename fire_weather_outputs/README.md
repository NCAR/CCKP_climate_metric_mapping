# NA-CORDEX CMIP5 Fire Weather Indices

## Overview

This dataset contains fire weather indices calculated from the North American Coordinated Regional Downscaling Experiment (NA-CORDEX) driven by CMIP5 global climate models under the RCP8.5 emissions scenario. The ensemble features dynamically downscaled simulations in which a set of global climate models (GCMs) provide boundary and input conditions for regional climate models (RCMs). Simulation output has been bias corrected using multivariate bias correction through quantile mapping (MBCn) against gridMET, and fire weather indices are calculated from those bias corrected fields.

## Fire Weather Indices

| Fire Index | Abbreviation | Description | Input Variables |
|---|---|---|---|
| 100-hour Fuel Moisture | FM100 | Moisture content of dead fuels 1–3 inches in diameter | tmax, tmin, prec, rhmin, rhmax |
| Energy Release Component | ERC | Available energy per unit area within the flaming front at the head of a fire | tmax, tmin, prec, rhmin, rhmax, huss, rsds, FM100, FM1000 |
| Vapor Pressure Deficit | VPD | Difference between the amount of moisture in the air and how much moisture the air can hold when saturated (proxy for fine fuel moisture) | tmax, tmin, huss |
| Hot Dry Windy Index | HDW (I) | Adverse atmospheric conditions that make it more difficult to manage a wildland fire | VPD, windspeed |

## Simulation Ensemble

The ensemble consists of 13 GCM–RCM combinations:

| GCM | RCM |
|---|---|
| GFDL-ESM2M | RegCM4 |
| GFDL-ESM2M | WRF |
| HadGEM2-ES | RegCM4 |
| HadGEM2-ES | WRF |
| MPI-ESM-LR | RegCM4 |
| MPI-ESM-LR | WRF |
| MPI-ESM-LR | CRCM5-UQAM |
| MPI-ESM-MR | CRCM5-UQAM |
| CanESM2 | CRCM5-UQAM |
| CanESM2 | CanRCM4 |
| CanESM2 | RCA4 |
| EC-EARTH | RCA4 |
| EC-EARTH | HIRHAM5 |

## Time Periods

- **Baseline (reference):** 1991–2020
- **Mid-century:** 2040–2059
- **Percentile thresholds** (95th, 97th, and 99th) were calculated over the baseline period.

## Global Warming Level +3°C Windows

The 20-year window centered on when each GCM reaches +3°C of global warming:

| GCM | Start Year | End Year |
|---|---|---|
| CanESM2 | 2040 | 2059 |
| EC-EARTH | 2052 | 2071 |
| GFDL-ESM2M | 2072 | 2091 |
| HadGEM2-ES | 2045 | 2064 |
| MPI-ESM-LR | 2052 | 2071 |
| MPI-ESM-MR | 2051 | 2070 |

## NetCDF File Contents

Each NetCDF file contains ensemble-mean statistics. Ensembles are composed of 10 members with varying GCM–RCM combinations. For each fire weather index and percentile threshold (95th, 97th, 99th), the files include:

- **Percentile values** — the threshold value for the baseline period (1991–2010)
- **Mid-century difference** — change in the annual count of days exceeding the threshold (mid-century minus baseline), with model agreement on the sign of change
- **GWL +3°C difference** — change in the annual count of days exceeding the threshold (GWL +3°C window minus baseline), with model agreement on the sign of change
- **Trend (2020–2100)** — linear trend in the annual count of days exceeding the threshold, with model agreement on the sign of the trend

### Example NetCDF Header (ERC)

```
netcdf firestats.erc.ensemble.changes.NA-CORDEX-CMIP5.RCP85 {
dimensions:
	lat = 258 ;
	lon = 600 ;
variables:
	double lat(lat) ;
	double lon(lon) ;
	float percentile_95(lat, lon) ;
	float percentile_97(lat, lon) ;
	float percentile_99(lat, lon) ;
	float days_above_95_midcentury_diff(lat, lon) ;
	float days_above_95_midcentury_diff_agree(lat, lon) ;
	float days_above_95_gwl3_diff(lat, lon) ;
	float days_above_95_gwl3_diff_agree(lat, lon) ;
	float days_above_95_trend(lat, lon) ;
	float days_above_95_trend_agree(lat, lon) ;
	float days_above_97_midcentury_diff(lat, lon) ;
	float days_above_97_midcentury_diff_agree(lat, lon) ;
	float days_above_97_gwl3_diff(lat, lon) ;
	float days_above_97_gwl3_diff_agree(lat, lon) ;
	float days_above_97_trend(lat, lon) ;
	float days_above_97_trend_agree(lat, lon) ;
	float days_above_99_midcentury_diff(lat, lon) ;
	float days_above_99_midcentury_diff_agree(lat, lon) ;
	float days_above_99_gwl3_diff(lat, lon) ;
	float days_above_99_gwl3_diff_agree(lat, lon) ;
	float days_above_99_trend(lat, lon) ;
	float days_above_99_trend_agree(lat, lon) ;
}
```

### Variable Naming Convention

Variables follow the pattern: `days_above_{percentile}_{period}_{statistic}`

- **percentile:** `95`, `97`, or `99`
- **period:** `midcentury` (2040–2059), `gwl3` (+3°C warming level), or `trend` (2020–2100)
- **statistic:** `diff` (ensemble-mean change in days/year) or `diff_agree` / `trend_agree` (percent of models agreeing on the sign of change)
