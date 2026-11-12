#!/usr/bin/env python3
"""
Run CMIP6 Risk Mapper
=======================
Driver script to run the CMIP6 historical/mid-century/end-century risk
mapping pipeline across one or more variables and scenarios, without
needing to type each call out interactively.

Usage
-----
Run everything with defaults (tas, ssp245):
    python3 run_cmip6_risk_mapper.py

Run multiple variables and scenarios:
    python3 run_cmip6_risk_mapper.py --variables tas tasmax tasmin --scenarios ssp245 ssp585

Only generate mid-century (skip end-century), custom output/cache dirs:
    python3 run_cmip6_risk_mapper.py --variables tas --periods mid-century \
        --output-dir ./risk_maps --cache-dir ./cckp_cache

Use the fixed vmin/vmax from cmip6_variable_config.py instead of auto limits:
    python3 run_cmip6_risk_mapper.py --variables tas --limits config

Color limits (--limits auto, default) are set PER FIGURE from land-only
5th-95th percentiles (cmip6_plot_limits.py): the median-panel range from
that figure's historical + future fields, the change-panel range from its
change field. No pooling across scenarios/periods, so ranges differ between
figures. The land mask is used only for the limits; the data written to
NetCDF is not masked. --limits auto needs regionmask's Natural Earth land
polygons; fetch them once from a node with internet access:
    python3 -c "import regionmask; regionmask.defined_regions.natural_earth_v5_0_0.land_50"

See --help for all options.
"""

import argparse
import sys
import traceback
from pathlib import Path

import matplotlib.pyplot as plt

from cmip6_loader import calculate_period_mean, STANDARD_PERIODS
from cmip6_risk_mapper import calculate_change, create_cmip6_risk_map, create_cmip6_netcdf
from cmip6_variable_config import CMIP6_VARIABLE_CONFIG
from cmip6_plot_limits import median_limits, change_limits

# Human-readable labels for each future period, used in plot titles/filenames
FUTURE_PERIOD_LABELS = {
    "mid-century": "Mid-Century",
    "end-century": "End-of-Century",
}


def run_one(variable, scenario, future_period_key, output_dir, cache_dir,
            historical_cache=None, limits="auto"):
    """
    Run the full pipeline for one (variable, scenario, future_period)
    combination: load historical + future means, compute change, write
    the figure and NetCDF.

    Parameters
    ----------
    variable : str
        CCKP variable code, must be a key in CMIP6_VARIABLE_CONFIG
    scenario : str
        SSP scenario, e.g. 'ssp245'
    future_period_key : str
        'mid-century' or 'end-century' (key into STANDARD_PERIODS)
    output_dir : Path
        Directory to write figures/NetCDFs into
    cache_dir : Path
        Directory for cached downloaded files
    historical_cache : dict, optional
        Dict of {(variable, scenario): historical_field} to avoid
        recomputing the historical blend once per future period
    limits : {'auto', 'config'}
        'auto': per-figure land-only percentile limits (cmip6_plot_limits.py).
        'config': fixed vmin/vmax from CMIP6_VARIABLE_CONFIG.

    Returns
    -------
    xarray.DataArray
        The historical field (so the caller can reuse/cache it)
    """
    if variable not in CMIP6_VARIABLE_CONFIG:
        raise KeyError(
            f"'{variable}' not found in CMIP6_VARIABLE_CONFIG. "
            f"Available: {', '.join(CMIP6_VARIABLE_CONFIG.keys())}"
        )

    config = CMIP6_VARIABLE_CONFIG[variable]
    future_label = FUTURE_PERIOD_LABELS[future_period_key]

    cache_key = (variable, scenario)
    if historical_cache is not None and cache_key in historical_cache:
        historical = historical_cache[cache_key]
    else:
        historical = calculate_period_mean(
            variable, *STANDARD_PERIODS["historical"],
            scenario=scenario, cache_dir=str(cache_dir)
        )
        if historical_cache is not None:
            historical_cache[cache_key] = historical

    future = calculate_period_mean(
        variable, *STANDARD_PERIODS[future_period_key],
        scenario=scenario, cache_dir=str(cache_dir)
    )
    change = calculate_change(historical, future)

    tag = f"{variable}_{scenario}_{future_period_key}"
    fig_path = output_dir / f"{tag}_map.png"
    nc_path = output_dir / f"{tag}.nc"

    median_lims = change_lims = None
    if limits == "auto":
        median_lims = median_limits([historical, future], config)
        change_lims = change_limits(change, config)
        print(f"  Median color range (land 5-95th pct): {median_lims}")
        print(f"  Change color range (land 5-95th pct): {change_lims}")

    fig = create_cmip6_risk_map(
        historical, future, change, config,
        output_path=str(fig_path),
        future_label=future_label,
        historical_period=STANDARD_PERIODS["historical"],
        future_period=STANDARD_PERIODS[future_period_key],
        scenario=scenario,
        median_lims=median_lims,
        change_lims=change_lims,
    )
    plt.close(fig)

    create_cmip6_netcdf(
        historical, future, change, config,
        output_path=str(nc_path),
        future_label=future_period_key,
        historical_period=STANDARD_PERIODS["historical"],
        future_period=STANDARD_PERIODS[future_period_key],
        scenario=scenario,
        variable=variable,
    )

    return historical


def main():
    parser = argparse.ArgumentParser(
        description="Run the CMIP6 risk mapping pipeline across variables/scenarios",
        formatter_class=argparse.RawDescriptionHelpFormatter,
        epilog="""
Examples:
  python3 run_cmip6_risk_mapper.py
  python3 run_cmip6_risk_mapper.py --variables tas tasmax tasmin --scenarios ssp245 ssp585
  python3 run_cmip6_risk_mapper.py --variables tas --periods mid-century
  python3 run_cmip6_risk_mapper.py --variables tas --limits config
        """
    )
    parser.add_argument('--variables', nargs='+', default=['tas'],
                         help='Variable codes to process (default: tas). '
                              f'Available: {", ".join(CMIP6_VARIABLE_CONFIG.keys())}')
    parser.add_argument('--scenarios', nargs='+', default=['ssp245'],
                         help='SSP scenarios to process (default: ssp245)')
    parser.add_argument('--periods', nargs='+', default=['mid-century', 'end-century'],
                         choices=['mid-century', 'end-century'],
                         help='Future periods to generate (default: both)')
    parser.add_argument('--output-dir', default='./cmip6_risk_maps',
                         help='Output directory for figures/NetCDFs (default: ./cmip6_risk_maps)')
    parser.add_argument('--cache-dir', default='./cckp_cache',
                         help='Cache directory for downloaded CCKP files (default: ./cckp_cache)')
    parser.add_argument('--limits', choices=['auto', 'config'], default='auto',
                         help="Color limits: 'auto' = per-figure land-only 5-95th "
                              "percentiles (default); 'config' = fixed vmin/vmax "
                              "from cmip6_variable_config.py")

    args = parser.parse_args()

    output_dir = Path(args.output_dir)
    output_dir.mkdir(parents=True, exist_ok=True)
    cache_dir = Path(args.cache_dir)
    cache_dir.mkdir(parents=True, exist_ok=True)

    # Build the full list of (variable, scenario, period) jobs up front
    jobs = [
        (variable, scenario, period)
        for variable in args.variables
        for scenario in args.scenarios
        for period in args.periods
    ]

    print("=" * 70)
    print("CMIP6 RISK MAPPER - BATCH RUN")
    print("=" * 70)
    print(f"Variables: {', '.join(args.variables)}")
    print(f"Scenarios: {', '.join(args.scenarios)}")
    print(f"Periods:   {', '.join(args.periods)}")
    print(f"Output dir: {output_dir}")
    print(f"Cache dir:  {cache_dir}")
    print(f"Limits:     {args.limits}")
    print(f"Total jobs: {len(jobs)}")
    print("=" * 70)

    # Cache historical fields per (variable, scenario) across periods within
    # this run, so e.g. mid-century and end-century for the same
    # variable/scenario don't redundantly recompute the historical blend.
    historical_cache = {}
    succeeded = []
    failed = []

    for i, (variable, scenario, period) in enumerate(jobs, start=1):
        tag = f"{variable}_{scenario}_{period}"
        print(f"\n[{i}/{len(jobs)}] Running: {tag}")
        print("-" * 70)
        try:
            run_one(variable, scenario, period, output_dir, cache_dir,
                    historical_cache=historical_cache, limits=args.limits)
            succeeded.append(tag)
        except Exception as e:
            print(f"  FAILED: {type(e).__name__}: {e}")
            traceback.print_exc()
            failed.append((tag, str(e)))

    print("\n" + "=" * 70)
    print("BATCH RUN COMPLETE")
    print("=" * 70)
    print(f"Succeeded: {len(succeeded)}/{len(jobs)}")
    for tag in succeeded:
        print(f"  OK   {tag}")
    if failed:
        print(f"Failed: {len(failed)}/{len(jobs)}")
        for tag, err in failed:
            print(f"  FAIL {tag}: {err}")
    print("=" * 70)

    # Exit non-zero if anything failed, so this is detectable in a batch
    # job's exit code (e.g. for PBS job status / notification purposes)
    sys.exit(1 if failed else 0)


if __name__ == '__main__':
    main()
