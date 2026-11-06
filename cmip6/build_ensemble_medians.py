#!/usr/bin/env python3
"""
Build Ensemble Median Plots (Stage 2)
========================================
For each of the 4 SSP scenarios x 2 future periods (8 combinations),
compute the ensemble median historical/future/change fields across all
models found in the Stage 1 intermediates directory, and produce a
3-panel plot + NetCDF -- reusing create_cmip6_risk_map() and
create_cmip6_netcdf() from cmip6_risk_mapper.py, since these are still
just three (lat, lon) fields regardless of source. The NetCDF provenance
metadata is set via source_mode='individual-models'.

Change is computed as median-of-per-model-differences (see
cmip6_ensemble_stacking.py), not difference-of-medians.

Usage
-----
    python3 build_ensemble_medians.py --variable tas
    python3 build_ensemble_medians.py --variable tas wsdi gsl   # multiple variables in one run
    python3 build_ensemble_medians.py --variable tas --scenarios ssp245 ssp585
"""

import argparse
import sys
import traceback
from pathlib import Path

from cmip6_loader import STANDARD_PERIODS, discover_stage1_models
from cmip6_risk_mapper import create_cmip6_risk_map, create_cmip6_netcdf
from cmip6_variable_config import CMIP6_VARIABLE_CONFIG
from cmip6_ensemble_stacking import stack_models, compute_ensemble_medians

ALL_SCENARIOS = ["ssp126", "ssp245", "ssp370", "ssp585"]
FUTURE_PERIODS = ["mid-century", "end-century"]
FUTURE_PERIOD_LABELS = {"mid-century": "Mid-Century", "end-century": "End-of-Century"}


def run_variable(variable, args):
    """
    Run the full Stage 2 ensemble median build for one variable.

    Returns
    -------
    (succeeded, failed, total) : (list of tag, list of (tag, error_str), int)
    """
    if variable not in CMIP6_VARIABLE_CONFIG:
        print(f"SKIPPING '{variable}': not in CMIP6_VARIABLE_CONFIG. "
              f"Available: {', '.join(CMIP6_VARIABLE_CONFIG.keys())}")
        return [], [(variable, "not in CMIP6_VARIABLE_CONFIG")], 0
    config = CMIP6_VARIABLE_CONFIG[variable]

    intermediate_dir = Path(args.intermediate_dir) / variable
    output_dir = Path(args.output_dir) / variable
    output_dir.mkdir(parents=True, exist_ok=True)

    if args.models:
        models = sorted(args.models)
    else:
        models = discover_stage1_models(intermediate_dir, variable)
        print(f"Discovered {len(models)} models in {intermediate_dir}")

    if not models:
        print(f"SKIPPING '{variable}': no models found in {intermediate_dir}. "
              f"Run build_model_intermediates.py first.")
        return [], [(variable, f"no models found in {intermediate_dir}")], 0
    print(f"Models: {', '.join(models)}\n")

    # Historical is scenario-independent -- compute/stack it once and reuse
    # across all scenario/period combinations for this variable.
    print("Stacking historical fields across all models...")
    historical_stack = stack_models(intermediate_dir, variable, models,
                                     scenario="historical", period_key="historical")
    print(f"  Stacked {historical_stack.sizes['model']} models\n")

    jobs = [(scenario, period) for scenario in args.scenarios for period in args.periods]
    print(f"Total ensemble median plots: {len(jobs)}\n")

    succeeded, failed = [], []

    for i, (scenario, period_key) in enumerate(jobs, start=1):
        tag = f"{variable}_{scenario}_{period_key.replace('-', '')}"
        print(f"[{i}/{len(jobs)}] {tag}")
        try:
            median_hist, median_future, median_change = compute_ensemble_medians(
                intermediate_dir, variable, models, scenario, period_key,
                historical_stack=historical_stack
            )

            future_label = FUTURE_PERIOD_LABELS[period_key]
            fig_path = output_dir / f"{tag}_ensemble_median_map.png"
            nc_path = output_dir / f"{tag}_ensemble_median.nc"

            create_cmip6_risk_map(
                median_hist, median_future, median_change, config,
                output_path=str(fig_path),
                future_label=future_label,
                historical_period=STANDARD_PERIODS["historical"],
                future_period=STANDARD_PERIODS[period_key],
                scenario=scenario,
            )

            create_cmip6_netcdf(
                median_hist, median_future, median_change, config,
                output_path=str(nc_path),
                future_label=period_key,
                historical_period=STANDARD_PERIODS["historical"],
                future_period=STANDARD_PERIODS[period_key],
                scenario=scenario,
                variable=variable,
                source_mode="individual-models",
                models=models,
                historical_scenario="ssp245",  # Stage 1 always blends historical with ssp245
            )

            print(f"  OK    {fig_path.name}")
            succeeded.append(tag)
        except Exception as e:
            print(f"  FAIL  {type(e).__name__}: {e}")
            traceback.print_exc()
            failed.append((tag, str(e)))

    return succeeded, failed, len(jobs)


def main():
    parser = argparse.ArgumentParser(
        description="Compute ensemble median historical/future/change fields and plot them",
        formatter_class=argparse.RawDescriptionHelpFormatter,
    )
    parser.add_argument("--variable", nargs="+", default=["tas"],
                         help="One or more CCKP variable codes (default: tas). "
                              "e.g. --variable tas wsdi gsl")
    parser.add_argument("--scenarios", nargs="+", default=ALL_SCENARIOS,
                         help=f"SSP scenarios (default: {', '.join(ALL_SCENARIOS)})")
    parser.add_argument("--periods", nargs="+", default=FUTURE_PERIODS,
                         choices=FUTURE_PERIODS,
                         help="Future periods (default: both)")
    parser.add_argument("--models", nargs="+", default=None,
                         help="Specific models to include (default: all found in "
                              "--intermediate-dir); applied to every --variable given")
    parser.add_argument("--intermediate-dir", default="./cmip6_model_intermediates",
                         help="Base Stage 1 dir; reads from <dir>/<variable>/")
    parser.add_argument("--output-dir", default="./cmip6_ensemble_medians",
                         help="Base output dir; writes to <dir>/<variable>/")
    args = parser.parse_args()

    variables = args.variable
    multi = len(variables) > 1

    overall = {}
    for variable in variables:
        if multi:
            print("\n" + "#" * 70)
            print(f"# VARIABLE: {variable}")
            print("#" * 70)
        succeeded, failed, total = run_variable(variable, args)
        overall[variable] = (succeeded, failed, total)

        print("\n" + "=" * 70)
        print(f"ENSEMBLE MEDIAN BUILD COMPLETE -- {variable}")
        print("=" * 70)
        print(f"Succeeded: {len(succeeded)}/{total}")
        if failed:
            print(f"Failed: {len(failed)}/{total}")
            for tag, err in failed:
                print(f"  {tag}: {err}")
        print("=" * 70)

    any_failed = any(failed for _, failed, _ in overall.values())

    if multi:
        print("\n" + "#" * 70)
        print("OVERALL SUMMARY (all variables)")
        print("#" * 70)
        for variable, (succeeded, failed, total) in overall.items():
            flag = "" if not failed else "  <-- has failures"
            print(f"  {variable:12s} {len(succeeded)}/{total} succeeded{flag}")
        print("#" * 70)

    sys.exit(1 if any_failed else 0)


if __name__ == "__main__":
    main()
