#!/usr/bin/env python3
"""
List available individual CMIP6 models on CCKP S3 for a given variable,
broken out by scenario, plus the intersection across scenarios.

Usage:
    python3 list_cckp_models.py                  # variable=tas, default scenarios
    python3 list_cckp_models.py tasmax
    python3 list_cckp_models.py tas historical ssp245 ssp585
"""

import sys
import urllib.request
import xml.etree.ElementTree as ET

BUCKET_URL = "https://wbg-cckp.s3.amazonaws.com/"
DEFAULT_SCENARIOS = ["historical", "ssp126", "ssp245", "ssp370", "ssp585"]


def list_subfolders(variable):
    """One listing call: return all '<model>-<scenario>/' subfolders under variable/."""
    url = f"{BUCKET_URL}?list-type=2&prefix=data/cmip6-x0.25/{variable}/&delimiter=/"
    with urllib.request.urlopen(url) as response:
        xml_data = response.read()
    ns = {"s3": "http://s3.amazonaws.com/doc/2006-03-01/"}
    root = ET.fromstring(xml_data)
    prefixes = [cp.find("s3:Prefix", ns).text for cp in root.findall("s3:CommonPrefixes", ns)]
    # prefixes look like: data/cmip6-x0.25/tas/access-cm2-r1i1p1f1-historical/
    names = [p.rstrip("/").split("/")[-1] for p in prefixes]
    return names


def models_by_scenario(variable, scenarios):
    """Return {scenario: sorted list of model names (ensemble-all excluded)}."""
    all_names = list_subfolders(variable)
    result = {}
    for scenario in scenarios:
        suffix = f"-{scenario}"
        models = sorted(
            name[: -len(suffix)]
            for name in all_names
            if name.endswith(suffix) and name != f"ensemble-all{suffix}"
        )
        result[scenario] = models
    return result


def main():
    variable = sys.argv[1] if len(sys.argv) > 1 else "tas"
    scenarios = sys.argv[2:] if len(sys.argv) > 2 else DEFAULT_SCENARIOS

    print(f"Variable: {variable}")
    print(f"Scenarios: {', '.join(scenarios)}\n")

    by_scenario = models_by_scenario(variable, scenarios)

    for scenario, models in by_scenario.items():
        print(f"{scenario} ({len(models)} models):")
        for m in models:
            print(f"  {m}")
        print()

    common = set(by_scenario[scenarios[0]])
    for scenario in scenarios[1:]:
        common &= set(by_scenario[scenario])
    common = sorted(common)

    print(f"Models common to ALL {len(scenarios)} scenarios ({len(common)}):")
    for m in common:
        print(f"  {m}")

    # Also show what's missing per scenario, relative to the union, so you
    # can see which models to potentially drop / which scenario they're
    # missing from
    union = set()
    for models in by_scenario.values():
        union |= set(models)
    missing_any = sorted(union - set(common))
    if missing_any:
        print(f"\nModels missing from at least one scenario ({len(missing_any)}):")
        for m in missing_any:
            have = [s for s in scenarios if m in by_scenario[s]]
            missing = [s for s in scenarios if m not in by_scenario[s]]
            print(f"  {m}: has {have}, missing {missing}")


if __name__ == "__main__":
    main()
