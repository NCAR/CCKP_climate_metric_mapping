#!/usr/bin/env python3
"""
List real filenames in the public CCKP S3 bucket for a given prefix.

Uses only the Python standard library (urllib + xml.etree) -- no pip
install, no aws-cli, no boto3 required. This queries S3's public
"list objects" HTTP API directly.

Usage:
    python3 list_cckp_files.py                     # lists tas/ensemble-all-historical/
    python3 list_cckp_files.py tas/ensemble-all-ssp245/
    python3 list_cckp_files.py tas/                # lists everything under tas/ (all models)
"""

import sys
import urllib.request
import xml.etree.ElementTree as ET

BUCKET_URL = "https://wbg-cckp.s3.amazonaws.com/"


def list_prefix(prefix):
    """Print all object keys in the bucket under the given prefix."""
    # S3's list-objects-v2 API returns XML. Delimiter='/' groups
    # "subfolders" so we're not flooded with every file at once.
    url = f"{BUCKET_URL}?list-type=2&prefix=data/cmip6-x0.25/{prefix}&delimiter=/"
    print(f"Querying: {url}\n")

    with urllib.request.urlopen(url) as response:
        xml_data = response.read()

    # S3 XML responses use this namespace
    ns = {"s3": "http://s3.amazonaws.com/doc/2006-03-01/"}
    root = ET.fromstring(xml_data)

    # "CommonPrefixes" = subfolders at this level (e.g. model-scenario dirs)
    subfolders = [
        cp.find("s3:Prefix", ns).text
        for cp in root.findall("s3:CommonPrefixes", ns)
    ]
    # "Contents" = actual files at this level
    files = [
        c.find("s3:Key", ns).text
        for c in root.findall("s3:Contents", ns)
    ]

    if subfolders:
        print(f"Subfolders under this prefix ({len(subfolders)}):")
        for sf in subfolders:
            print(f"  {sf}")
        print()

    if files:
        print(f"Files at this level ({len(files)}):")
        for f in files:
            print(f"  {f}")
    elif not subfolders:
        print("No results found. Check the prefix / variable name.")


if __name__ == "__main__":
    prefix = sys.argv[1] if len(sys.argv) > 1 else "tas/ensemble-all-historical/"
    list_prefix(prefix)
