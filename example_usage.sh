#!/bin/bash
#
# Example usage script for climate_risk_mapper.py
# This shows various ways to use the script

echo "==============================================="
echo "Climate Risk Mapper - Example Usage"
echo "==============================================="

# Create output directory
mkdir -p ./cckp_outputs

echo ""
echo "Example 1: Basic usage with r95ptot"
echo "-----------------------------------"
python climate_risk_mapper.py r95ptot --output-dir ./cckp_outputs

echo ""
echo "Example 2: Temperature maximum with custom reference period"
echo "-----------------------------------------------------------"
python climate_risk_mapper.py tasmax \
  --reference-period 1981 2010 \
  --output-dir ./cckp_outputs

echo ""
echo "Example 3: Precipitation without significance stippling"
echo "-------------------------------------------------------"
python climate_risk_mapper.py pr \
  --no-significance \
  --output-dir ./cckp_outputs

echo ""
echo "Example 4: Using a local file (if available)"
echo "--------------------------------------------"
 python climate_risk_mapper.py r95p \
   --url /path/to/local/file.nc \
   --output-dir ./cckp_outputs

echo ""
echo "==============================================="
echo "Examples complete! Check ./cckp_outputs/"
echo "==============================================="
