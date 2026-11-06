#!/usr/bin/env python3
"""
Clean Corrupted Cache
========================
Scans cckp_cache/ across all variables (or ones you name) and checks
every cached .nc file with the same validity check used by the loader
itself (_is_valid_netcdf: opens cleanly AND has a monotonic time
coordinate). Reports what's bad, and optionally deletes it so the next
build_model_intermediates.py run will redownload cleanly.

By default this is a DRY RUN -- it only reports what it would delete.
Pass --delete to actually remove the bad files.

Usage
-----
    python3 clean_corrupted_cache.py                       # dry run, all variables
    python3 clean_corrupted_cache.py --delete              # actually delete bad files
    python3 clean_corrupted_cache.py --variable gsl tas    # limit to specific variables
"""

import argparse
from pathlib import Path

from cmip6_loader import _is_valid_netcdf


def main():
    parser = argparse.ArgumentParser(
        description="Find (and optionally delete) corrupted cached CCKP downloads",
        formatter_class=argparse.RawDescriptionHelpFormatter,
    )
    parser.add_argument("--variable", nargs="+", default=None,
                         help="Specific variable(s) to check (default: all found in --cache-dir)")
    parser.add_argument("--cache-dir", default="./cckp_cache",
                         help="Base cache directory (default: ./cckp_cache)")
    parser.add_argument("--delete", action="store_true",
                         help="Actually delete corrupted files (default: dry run, report only)")
    args = parser.parse_args()

    base_dir = Path(args.cache_dir)
    if not base_dir.exists():
        raise SystemExit(f"Directory not found: {base_dir}")

    if args.variable:
        variables = args.variable
    else:
        variables = sorted(d.name for d in base_dir.iterdir() if d.is_dir())

    if not variables:
        raise SystemExit(f"No variable subdirectories found under {base_dir}")

    print(f"Checking cache for {len(variables)} variable(s): {', '.join(variables)}")
    if not args.delete:
        print("(DRY RUN -- pass --delete to actually remove corrupted files)\n")
    else:
        print("(--delete given -- corrupted files WILL be removed)\n")

    total_checked = 0
    total_bad = 0
    bad_by_variable = {}

    for variable in variables:
        variable_dir = base_dir / variable
        if not variable_dir.exists():
            continue

        files = sorted(variable_dir.glob("*.nc"))
        bad_files = []

        for f in files:
            total_checked += 1
            if not _is_valid_netcdf(f):
                bad_files.append(f)
                total_bad += 1

        if bad_files:
            bad_by_variable[variable] = bad_files
            print(f"{variable}: {len(bad_files)}/{len(files)} corrupted")
            for f in bad_files:
                size_mb = f.stat().st_size / (1024 * 1024)
                print(f"    {f.name}  ({size_mb:.1f} MB)")
                if args.delete:
                    f.unlink()
                    print(f"      -> deleted")
        else:
            print(f"{variable}: {len(files)}/{len(files)} OK")

    print(f"\n{'=' * 70}")
    print(f"Checked {total_checked} cached files across {len(variables)} variable(s)")
    print(f"Corrupted: {total_bad}")
    if bad_by_variable:
        label = "Deleted from" if args.delete else "Corrupted in"
        print(f"\n{label} these variables:")
        for variable, bad_files in bad_by_variable.items():
            print(f"  {variable}: {len(bad_files)} file(s)")
    if total_bad and not args.delete:
        print("\nRerun with --delete to remove these, then rerun "
              "build_model_intermediates.py for the affected variables "
              "to redownload them.")
    elif total_bad and args.delete:
        print("\nDeleted. Rerun build_model_intermediates.py for the affected "
              "variables to redownload them.")
    print(f"{'=' * 70}")


if __name__ == "__main__":
    main()
