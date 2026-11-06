#!/usr/bin/env python3
"""
Run Model Diagnostics
========================
Generates the 4 per-model sanity-check plots (one per SSP scenario) for
every model found in the Stage 1 intermediates directory, using the 2x3
layout from cmip6_model_diagnostic_plots.py:

    Historical | Mid-Century | End-Century
    (blank)    | Mid - Hist  | End - Hist

Model list is discovered automatically by scanning for
"<variable>_<model>_historical_<years>.nc" files in --intermediate-dir,
so it naturally reflects whichever models actually succeeded in Stage 1
(e.g. excludes any model dropped for missing data).

Usage
-----
    python3 run_model_diagnostics.py --variable tas
    python3 run_model_diagnostics.py --variable tas --models access-cm2-r1i1p1f1
    python3 run_model_diagnostics.py --variable tas --scenarios ssp245 ssp585
"""

import argparse
import re
import sys
import traceback
from pathlib import Path

import xarray as xr

from cmip6_loader import STANDARD_PERIODS
from cmip6_variable_config import CMIP6_VARIABLE_CONFIG
from cmip6_model_diagnostic_plots import create_model_diagnostic_plot

ALL_SCENARIOS = ["ssp126", "ssp245", "ssp370", "ssp585"]


def discover_models(intermediate_dir, variable):
    """Find all models with a historical intermediate file present."""
    pattern = re.compile(rf"^{re.escape(variable)}_(.+)_historical_\d{{4}}-\d{{4}}\.nc$")
    models = []
    for f in sorted(Path(intermediate_dir).glob(f"{variable}_*_historical_*.nc")):
        m = pattern.match(f.name)
        if m:
            models.append(m.group(1))
    return sorted(set(models))


def load_field(path, variable):
    """Open an intermediate NetCDF and return its single data variable."""
    ds = xr.open_dataset(path, decode_timedelta=False)
    return ds[variable]


def main():
    parser = argparse.ArgumentParser(
        description="Generate per-model 2x3 diagnostic plots from Stage 1 intermediates",
        formatter_class=argparse.RawDescriptionHelpFormatter,
    )
    parser.add_argument("--variable", default="tas",
                         help="CCKP variable code (default: tas)")
    parser.add_argument("--models", nargs="+", default=None,
                         help="Specific models to plot (default: all found in --intermediate-dir)")
    parser.add_argument("--scenarios", nargs="+", default=ALL_SCENARIOS,
                         help=f"SSP scenarios to plot (default: {', '.join(ALL_SCENARIOS)})")
    parser.add_argument("--intermediate-dir", default="./cmip6_model_intermediates",
                         help="Base Stage 1 output dir; reads from <dir>/<variable>/")
    parser.add_argument("--output-dir", default="./cmip6_model_diagnostics",
                         help="Base output dir for diagnostic plots; writes to <dir>/<variable>/")
    args = parser.parse_args()

    if args.variable not in CMIP6_VARIABLE_CONFIG:
        sys.exit(f"'{args.variable}' not in CMIP6_VARIABLE_CONFIG. "
                  f"Available: {', '.join(CMIP6_VARIABLE_CONFIG.keys())}")
    config = CMIP6_VARIABLE_CONFIG[args.variable]

    intermediate_dir = Path(args.intermediate_dir) / args.variable
    output_dir = Path(args.output_dir) / args.variable
    output_dir.mkdir(parents=True, exist_ok=True)

    if args.models:
        models = sorted(args.models)
    else:
        models = discover_models(intermediate_dir, args.variable)
        print(f"Discovered {len(models)} models in {intermediate_dir}")

    if not models:
        sys.exit(f"No models found in {intermediate_dir}. Run build_model_intermediates.py first.")

    hist_start, hist_end = STANDARD_PERIODS["historical"]
    mid_start, mid_end = STANDARD_PERIODS["mid-century"]
    end_start, end_end = STANDARD_PERIODS["end-century"]

    jobs = [(model, scenario) for model in models for scenario in args.scenarios]
    print(f"Total plots to generate: {len(jobs)} ({len(models)} models x {len(args.scenarios)} scenarios)")
    print(f"Output dir: {output_dir}\n")

    succeeded, skipped, failed = 0, 0, []

    for i, (model, scenario) in enumerate(jobs, start=1):
        tag = f"{model}/{scenario}"
        print(f"[{i}/{len(jobs)}] {tag}")

        hist_path = intermediate_dir / f"{args.variable}_{model}_historical_{hist_start}-{hist_end}.nc"
        mid_path = intermediate_dir / f"{args.variable}_{model}_{scenario}_midcentury_{mid_start}-{mid_end}.nc"
        end_path = intermediate_dir / f"{args.variable}_{model}_{scenario}_endcentury_{end_start}-{end_end}.nc"

        missing = [p.name for p in (hist_path, mid_path, end_path) if not p.exists()]
        if missing:
            print(f"  SKIP  missing intermediate file(s): {', '.join(missing)}")
            skipped += 1
            continue

        out_path = output_dir / f"{args.variable}_{model}_{scenario}_diagnostic.png"
        try:
            historical = load_field(hist_path, args.variable)
            midcentury = load_field(mid_path, args.variable)
            endcentury = load_field(end_path, args.variable)

            create_model_diagnostic_plot(
                historical, midcentury, endcentury, config,
                output_path=str(out_path),
                model=model, variable=args.variable, scenario=scenario,
                historical_period=(hist_start, hist_end),
                midcentury_period=(mid_start, mid_end),
                endcentury_period=(end_start, end_end),
            )
            print(f"  OK    {out_path.name}")
            succeeded += 1
        except Exception as e:
            print(f"  FAIL  {type(e).__name__}: {e}")
            traceback.print_exc()
            failed.append((tag, str(e)))

    print("\n" + "=" * 70)
    print("DIAGNOSTIC PLOT GENERATION COMPLETE")
    print("=" * 70)
    print(f"Succeeded: {succeeded}  Skipped: {skipped}  Failed: {len(failed)}")
    if failed:
        print("\nFailed jobs:")
        for tag, err in failed:
            print(f"  {tag}: {err}")
    print("=" * 70)

    sys.exit(1 if failed else 0)


if __name__ == "__main__":
    main()
