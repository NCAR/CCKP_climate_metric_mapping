#!/usr/bin/env python3
"""
Build Model Intermediates (Stage 1)
=====================================
For every individual CMIP6 model that has data across historical +
ssp126/ssp245/ssp370/ssp585, compute and save:

    <var>_<model>_historical.nc                    (1990-2019, blended w/ ssp245)
    <var>_<model>_<scenario>_midcentury.nc          (2040-2069)
    <var>_<model>_<scenario>_endcentury.nc          (2070-2099)

That's 1 + (4 scenarios x 2 periods) = 9 files per model.

This is Stage 1 of the multi-model pipeline: raw per-model/scenario/period
fields only (no change calc, no ensemble stats -- that's Stage 2, built on
top of these files).

Resumable: skips any output file that already exists, so an interrupted
run (network hiccup, one bad model) can just be rerun and will only
(re)do what's missing. Per-job errors are caught and reported at the end
rather than aborting the whole run.

Usage
-----
    python3 build_model_intermediates.py                     # tas, all common models
    python3 build_model_intermediates.py --variable tasmax
    python3 build_model_intermediates.py --variable tas wsdi gsl   # multiple variables in one run
    python3 build_model_intermediates.py --models access-cm2-r1i1p1f1 bcc-csm2-mr-r1i1p1f1   # test on a subset first
    python3 build_model_intermediates.py --limit 3           # just the first 3 common models
"""

import argparse
import sys
import traceback
from pathlib import Path

import xarray as xr

from cmip6_loader import calculate_period_mean, get_common_models, STANDARD_PERIODS
from cmip6_variable_config import CMIP6_VARIABLE_CONFIG

REQUIRED_SCENARIOS = ["historical", "ssp126", "ssp245", "ssp370", "ssp585"]
FUTURE_SCENARIOS = ["ssp126", "ssp245", "ssp370", "ssp585"]
HISTORICAL_BLEND_SCENARIO = "ssp245"  # confirmed convention: always ssp245 for 2015-2019

PERIOD_LABELS = {"mid-century": "midcentury", "end-century": "endcentury"}


def save_field_netcdf(da, output_path, variable, model, scenario, period_key,
                       period_years, config):
    """Save a single (lat, lon) field to NetCDF with descriptive metadata."""
    start, end = period_years
    ds_out = xr.Dataset({variable: da})
    ds_out[variable].attrs = {
        "long_name": config["long_name"],
        "units": config["units"],
    }
    ds_out.attrs = {
        "title": f"CMIP6 {config['long_name']}: {model}, {scenario}, {period_key} ({start}-{end})",
        "source": f"CMIP6 individual model run ({model}) via Climate Change Knowledge Portal (CCKP)",
        "source_url": "https://climateknowledgeportal.worldbank.org/",
        "model": model,
        "scenario": scenario,
        "period": period_key,
        "period_years": f"{start}-{end}",
        "variable": variable,
    }
    output_path = Path(output_path)
    output_path.parent.mkdir(parents=True, exist_ok=True)
    ds_out.to_netcdf(output_path, encoding={variable: {"zlib": True, "complevel": 4}})


def build_jobs(variable, models):
    """List every (model, scenario, period_key, period_label, years) job to run."""
    jobs = []
    for model in models:
        jobs.append((model, "historical", "historical", "historical", STANDARD_PERIODS["historical"]))
        for scenario in FUTURE_SCENARIOS:
            for period_key in ("mid-century", "end-century"):
                label = PERIOD_LABELS[period_key]
                jobs.append((model, scenario, period_key, label, STANDARD_PERIODS[period_key]))
    return jobs


def run_job(variable, model, scenario, period_key, period_label, years,
            output_dir, cache_dir, config):
    """Compute one field and save it, unless the output already exists."""
    start, end = years
    year_tag = f"{start}-{end}"
    if period_key == "historical":
        tag = f"{variable}_{model}_historical_{year_tag}"
    else:
        tag = f"{variable}_{model}_{scenario}_{period_label}_{year_tag}"

    out_path = Path(output_dir) / f"{tag}.nc"
    if out_path.exists():
        print(f"  SKIP  (already exists): {out_path.name}")
        return

    # Historical always blends with ssp245 for 2015-2019, regardless of the
    # future scenario being processed elsewhere for this model.
    load_scenario = HISTORICAL_BLEND_SCENARIO if period_key == "historical" else scenario

    field = calculate_period_mean(
        variable, *years, scenario=load_scenario, model=model, cache_dir=str(cache_dir)
    )
    save_field_netcdf(field, out_path, variable, model, scenario, period_key, years, config)
    print(f"  OK    {out_path.name}")


def run_variable(variable, args):
    """
    Run the full Stage 1 build for one variable.

    Returns
    -------
    (succeeded, skipped, failed) : (int, int, list of (tag, error_str))
    """
    if variable not in CMIP6_VARIABLE_CONFIG:
        print(f"SKIPPING '{variable}': not in CMIP6_VARIABLE_CONFIG. "
              f"Available: {', '.join(CMIP6_VARIABLE_CONFIG.keys())}")
        return 0, 0, [(variable, "not in CMIP6_VARIABLE_CONFIG")]
    config = CMIP6_VARIABLE_CONFIG[variable]

    if args.models:
        models = sorted(args.models)
        print(f"Using explicitly given models ({len(models)}): {', '.join(models)}")
    else:
        print(f"Querying CCKP for models common to: {', '.join(REQUIRED_SCENARIOS)} ...")
        models = get_common_models(variable, REQUIRED_SCENARIOS)
        print(f"Found {len(models)} common models.")

    if args.limit:
        models = models[: args.limit]
        print(f"Limiting to first {len(models)} models for this run.")

    output_dir = Path(args.output_dir) / variable
    output_dir.mkdir(parents=True, exist_ok=True)
    cache_dir = Path(args.cache_dir) / variable
    cache_dir.mkdir(parents=True, exist_ok=True)

    jobs = build_jobs(variable, models)
    print(f"\nTotal jobs: {len(jobs)} ({len(models)} models x 9 files each)")
    print(f"Output dir: {output_dir}")
    print(f"Cache dir:  {cache_dir}\n")

    succeeded, skipped, failed = 0, 0, []

    for i, (model, scenario, period_key, period_label, years) in enumerate(jobs, start=1):
        tag = f"{variable}/{model}/{scenario}/{period_key}"
        print(f"[{i}/{len(jobs)}] {tag}")
        try:
            year_tag = f"{years[0]}-{years[1]}"
            before_exists = (Path(output_dir) /
                              (f"{variable}_{model}_historical_{year_tag}.nc" if period_key == "historical"
                               else f"{variable}_{model}_{scenario}_{period_label}_{year_tag}.nc")).exists()
            run_job(variable, model, scenario, period_key, period_label, years,
                    output_dir, cache_dir, config)
            if before_exists:
                skipped += 1
            else:
                succeeded += 1
        except Exception as e:
            print(f"  FAIL  {type(e).__name__}: {e}")
            traceback.print_exc()
            failed.append((tag, str(e)))

    return succeeded, skipped, failed


def main():
    parser = argparse.ArgumentParser(
        description="Build per-model/scenario/period intermediate NetCDFs (Stage 1)",
        formatter_class=argparse.RawDescriptionHelpFormatter,
    )
    parser.add_argument("--variable", nargs="+", default=["tas"],
                         help="One or more CCKP variable codes (default: tas). "
                              "e.g. --variable tas wsdi gsl")
    parser.add_argument("--models", nargs="+", default=None,
                         help="Specific models to run (default: all models common to "
                              f"{', '.join(REQUIRED_SCENARIOS)}); applied to every "
                              "--variable given")
    parser.add_argument("--limit", type=int, default=None,
                         help="Only process the first N common models (for testing)")
    parser.add_argument("--output-dir", default="./cmip6_model_intermediates",
                         help="Base output directory; a subfolder named for each "
                              "--variable is created automatically (default: "
                              "./cmip6_model_intermediates)")
    parser.add_argument("--cache-dir", default="./cckp_cache",
                         help="Base cache directory for downloaded raw CCKP files; a "
                              "subfolder named for each --variable is created "
                              "automatically (default: ./cckp_cache)")
    args = parser.parse_args()

    variables = args.variable
    multi = len(variables) > 1

    overall = {}
    for variable in variables:
        if multi:
            print("\n" + "#" * 70)
            print(f"# VARIABLE: {variable}")
            print("#" * 70)
        succeeded, skipped, failed = run_variable(variable, args)
        overall[variable] = (succeeded, skipped, failed)

        print("\n" + "=" * 70)
        print(f"STAGE 1 BUILD COMPLETE -- {variable}")
        print("=" * 70)
        print(f"Succeeded: {succeeded}  Skipped (already existed): {skipped}  Failed: {len(failed)}")
        if failed:
            print("\nFailed jobs:")
            for tag, err in failed:
                print(f"  {tag}: {err}")
        print("=" * 70)

    any_failed = any(failed for _, _, failed in overall.values())

    if multi:
        print("\n" + "#" * 70)
        print("OVERALL SUMMARY (all variables)")
        print("#" * 70)
        for variable, (succeeded, skipped, failed) in overall.items():
            flag = "" if not failed else "  <-- has failures"
            print(f"  {variable:12s} succeeded={succeeded} skipped={skipped} failed={len(failed)}{flag}")
        print("#" * 70)

    sys.exit(1 if any_failed else 0)


if __name__ == "__main__":
    main()
