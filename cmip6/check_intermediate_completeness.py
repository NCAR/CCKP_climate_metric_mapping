#!/usr/bin/env python3
"""
Check Intermediate Completeness
==================================
Audits cmip6_model_intermediates/ for gaps and corruption, across every
variable subfolder found (or just the ones you name).

For each variable:
  1. Discovers every model that has AT LEAST ONE file present (not just
     historical -- catches partial completions where e.g. only some
     scenarios succeeded).
  2. For each such model, checks all 9 expected files (historical +
     4 scenarios x 2 periods):
       - MISSING   file doesn't exist at all
       - CORRUPT   file exists but doesn't open cleanly as NetCDF
                   (e.g. left over from an interrupted write -- this is
                   NOT caught by build_model_intermediates.py's own
                   resumability check, which only tests existence)
       - OK        exists and opens cleanly

Prints a per-variable summary (how many models are fully complete vs.
not) and a detailed list of exactly what's missing/corrupt, so you know
precisely what to rerun.

Usage
-----
    python3 check_intermediate_completeness.py                  # all variables found
    python3 check_intermediate_completeness.py --variable tas wsdi
    python3 check_intermediate_completeness.py --intermediate-dir ./cmip6_model_intermediates
"""

import argparse
import re
from pathlib import Path

from cmip6_loader import stage1_filename, STANDARD_PERIODS, _is_valid_netcdf

FUTURE_SCENARIOS = ["ssp126", "ssp245", "ssp370", "ssp585"]
FUTURE_PERIODS = ["mid-century", "end-century"]

# Matches both filename forms:
#   <var>_<model>_historical_<start>-<end>.nc
#   <var>_<model>_<scenario>_<midcentury|endcentury>_<start>-<end>.nc
FILENAME_RE_TEMPLATE = (
    r"^{var}_(?P<model>.+)_(?P<scenario>historical|ssp126|ssp245|ssp370|ssp585)"
    r"(?:_(?P<label>midcentury|endcentury))?_\d{{4}}-\d{{4}}\.nc$"
)


def discover_models_any_file(variable_dir, variable):
    """Find every model with at least one file present, from filenames alone."""
    pattern = re.compile(FILENAME_RE_TEMPLATE.format(var=re.escape(variable)))
    models = set()
    for f in variable_dir.glob(f"{variable}_*.nc"):
        m = pattern.match(f.name)
        if m:
            models.add(m.group("model"))
    return sorted(models)


def expected_jobs():
    """List every (scenario, period_key) combination expected per model."""
    jobs = [("historical", "historical")]
    for scenario in FUTURE_SCENARIOS:
        for period_key in FUTURE_PERIODS:
            jobs.append((scenario, period_key))
    return jobs


def audit_variable(variable_dir, variable):
    """
    Returns
    -------
    dict: {model: {(scenario, period_key): status}}
        status is one of 'OK', 'MISSING', 'CORRUPT'
    """
    models = discover_models_any_file(variable_dir, variable)
    jobs = expected_jobs()
    results = {}

    for model in models:
        results[model] = {}
        for scenario, period_key in jobs:
            fname = stage1_filename(variable, model, scenario, period_key)
            path = variable_dir / fname
            if not path.exists():
                status = "MISSING"
            elif _is_valid_netcdf(path):
                status = "OK"
            else:
                status = "CORRUPT"
            results[model][(scenario, period_key)] = status

    return results


def print_variable_report(variable, results):
    n_models = len(results)
    n_jobs_per_model = len(expected_jobs())
    n_expected = n_models * n_jobs_per_model

    n_ok = sum(1 for jobs in results.values() for s in jobs.values() if s == "OK")
    n_missing = sum(1 for jobs in results.values() for s in jobs.values() if s == "MISSING")
    n_corrupt = sum(1 for jobs in results.values() for s in jobs.values() if s == "CORRUPT")

    complete_models = [m for m, jobs in results.items() if all(s == "OK" for s in jobs.values())]
    incomplete_models = [m for m in results if m not in complete_models]

    print(f"\n{'=' * 70}")
    print(f"VARIABLE: {variable}")
    print(f"{'=' * 70}")
    print(f"Models found on disk:     {n_models}")
    print(f"Fully complete (9/9 OK):  {len(complete_models)}")
    print(f"Incomplete/corrupt:       {len(incomplete_models)}")
    print(f"Files: {n_ok} OK, {n_missing} missing, {n_corrupt} corrupt "
          f"(of {n_expected} expected = {n_models} models x {n_jobs_per_model} files)")

    if incomplete_models:
        print(f"\nDetails for incomplete models:")
        for model in sorted(incomplete_models):
            problems = [(s, p, status) for (s, p), status in results[model].items()
                        if status != "OK"]
            print(f"  {model}:")
            for scenario, period_key, status in problems:
                fname = stage1_filename(variable, model, scenario, period_key)
                print(f"    {status:8s} {fname}")


def main():
    parser = argparse.ArgumentParser(
        description="Audit Stage 1 intermediate files for completeness and integrity",
        formatter_class=argparse.RawDescriptionHelpFormatter,
    )
    parser.add_argument("--variable", nargs="+", default=None,
                         help="Specific variable(s) to check (default: all found in --intermediate-dir)")
    parser.add_argument("--intermediate-dir", default="./cmip6_model_intermediates",
                         help="Base Stage 1 output directory (default: ./cmip6_model_intermediates)")
    args = parser.parse_args()

    base_dir = Path(args.intermediate_dir)
    if not base_dir.exists():
        raise SystemExit(f"Directory not found: {base_dir}")

    if args.variable:
        variables = args.variable
    else:
        variables = sorted(d.name for d in base_dir.iterdir() if d.is_dir())

    if not variables:
        raise SystemExit(f"No variable subdirectories found under {base_dir}")

    print(f"Checking {len(variables)} variable(s): {', '.join(variables)}")

    all_results = {}
    for variable in variables:
        variable_dir = base_dir / variable
        if not variable_dir.exists():
            print(f"\nWARNING: {variable_dir} not found, skipping '{variable}'")
            continue
        results = audit_variable(variable_dir, variable)
        all_results[variable] = results
        print_variable_report(variable, results)

    # Overall summary line
    print(f"\n{'=' * 70}")
    print("OVERALL SUMMARY")
    print(f"{'=' * 70}")
    for variable, results in all_results.items():
        complete = sum(1 for jobs in results.values() if all(s == "OK" for s in jobs.values()))
        total = len(results)
        flag = "" if complete == total else "  <-- has gaps"
        print(f"  {variable:12s} {complete}/{total} models fully complete{flag}")
    print(f"{'=' * 70}")


if __name__ == "__main__":
    main()
