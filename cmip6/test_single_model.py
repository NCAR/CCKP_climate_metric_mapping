#!/usr/bin/env python3
"""
Scratch test: run ONE individual CMIP6 model through the existing
historical / future / change pipeline, to sanity-check the single-model
URL/percentile handling before building the full multi-model panel plot.

Historical period: 1990-2019, blended from the CMIP6 historical
experiment (1990-2014) with ssp245 (2015-2019) -- same convention as
the ensemble-all pipeline. load_annual_series() handles this blend
automatically since the requested range straddles 2014/2015.

Future period: mid-century 2040-2069, ssp245 (edit below to try others).

Model: access-cm2-r1i1p1f1 (edit below to try a different one from your
25-model common set).
"""

from pathlib import Path

from cmip6_loader import calculate_period_mean
from cmip6_risk_mapper import calculate_change, create_cmip6_risk_map, create_cmip6_netcdf
from cmip6_variable_config import CMIP6_VARIABLE_CONFIG

VARIABLE = "tas"
MODEL = "access-cm2-r1i1p1f1"
SCENARIO = "ssp245"

HISTORICAL_PERIOD = (1990, 2019)
FUTURE_PERIOD = (2040, 2069)   # mid-century
FUTURE_LABEL = "Mid-Century"

OUTPUT_DIR = Path("./single_model_test")
CACHE_DIR = Path("./cckp_cache")

OUTPUT_DIR.mkdir(parents=True, exist_ok=True)
CACHE_DIR.mkdir(parents=True, exist_ok=True)

config = CMIP6_VARIABLE_CONFIG[VARIABLE]

print(f"=== Single-model test: {MODEL}, {VARIABLE}, {SCENARIO} ===\n")

historical = calculate_period_mean(
    VARIABLE, *HISTORICAL_PERIOD,
    scenario=SCENARIO, model=MODEL, cache_dir=str(CACHE_DIR)
)
print(f"Historical ({HISTORICAL_PERIOD[0]}-{HISTORICAL_PERIOD[1]}) mean: "
      f"{float(historical.mean().values):.3f}")

future = calculate_period_mean(
    VARIABLE, *FUTURE_PERIOD,
    scenario=SCENARIO, model=MODEL, cache_dir=str(CACHE_DIR)
)
print(f"Future ({FUTURE_PERIOD[0]}-{FUTURE_PERIOD[1]}, {SCENARIO}) mean: "
      f"{float(future.mean().values):.3f}")

change = calculate_change(historical, future)
print(f"Change (mean): {float(change.mean().values):.3f}")

tag = f"{VARIABLE}_{MODEL}_{SCENARIO}_midcentury"
fig_path = OUTPUT_DIR / f"{tag}_map.png"
nc_path = OUTPUT_DIR / f"{tag}.nc"

create_cmip6_risk_map(
    historical, future, change, config,
    output_path=str(fig_path),
    future_label=FUTURE_LABEL,
    historical_period=HISTORICAL_PERIOD,
    future_period=FUTURE_PERIOD,
    scenario=SCENARIO,
)

create_cmip6_netcdf(
    historical, future, change, config,
    output_path=str(nc_path),
    future_label="mid-century",
    historical_period=HISTORICAL_PERIOD,
    future_period=FUTURE_PERIOD,
    scenario=SCENARIO,
    variable=VARIABLE,
    source_mode="single-model",
    models=[MODEL],
)

print(f"\nDone. Figure: {fig_path}\nNetCDF: {nc_path}")
