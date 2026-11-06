#!/usr/bin/env python3
"""
CMIP6 Ensemble Median Stacking (Stage 2)
===========================================
Loads Stage 1 per-model intermediate NetCDFs, stacks them along a `model`
dimension, and computes ensemble median fields:

    median historical      = median across models of the historical field
    median future           = median across models of the future field
    median change            = median across models of (future - historical),
                                i.e. MEDIAN-OF-DIFFERENCES, not
                                difference-of-medians. Each model's own
                                change is computed first (paired, same
                                model, future minus its own historical),
                                and only then is the median taken across
                                models. This is deliberately different
                                from (median future - median historical).

Per-model change fields are computed in-memory and NOT persisted to
disk -- they're a cheap local subtraction of already-downloaded data, so
there's no benefit to caching them as separate files. Only the final
ensemble median fields are worth saving.
"""

from pathlib import Path

import xarray as xr

from cmip6_loader import stage1_filename, discover_stage1_models, STANDARD_PERIODS


def load_stage1_field(intermediate_dir, variable, model, scenario, period_key):
    """Load one Stage 1 intermediate field as a DataArray."""
    fname = stage1_filename(variable, model, scenario, period_key)
    path = Path(intermediate_dir) / fname
    if not path.exists():
        raise FileNotFoundError(f"Stage 1 file not found: {path}")
    ds = xr.open_dataset(path, decode_timedelta=False)
    return ds[variable]


def stack_models(intermediate_dir, variable, models, scenario, period_key):
    """
    Load and stack a field across all given models, along a labeled
    `model` coordinate (not just a positional dimension) -- this ensures
    later arithmetic between two stacks (e.g. future - historical) aligns
    each model to itself by name, not by load order.

    Returns
    -------
    xarray.DataArray
        Dims: (model, lat, lon)
    """
    fields = []
    for model in models:
        da = load_stage1_field(intermediate_dir, variable, model, scenario, period_key)
        fields.append(da)
    stacked = xr.concat(fields, dim="model")
    stacked = stacked.assign_coords(model=models)
    return stacked


def compute_ensemble_medians(intermediate_dir, variable, models, scenario, period_key,
                              historical_stack=None):
    """
    Compute the three ensemble median fields for one scenario/period:
    median historical, median future, and median change (median-of-
    per-model-differences).

    Parameters
    ----------
    historical_stack : xarray.DataArray, optional
        Pre-computed (model, lat, lon) historical stack, to avoid
        reloading/restacking historical data for every scenario/period
        combination (historical is scenario-independent).

    Returns
    -------
    (median_historical, median_future, median_change) : tuple of xarray.DataArray
        Each (lat, lon)
    """
    if historical_stack is None:
        historical_stack = stack_models(intermediate_dir, variable, models,
                                         scenario="historical", period_key="historical")

    future_stack = stack_models(intermediate_dir, variable, models, scenario, period_key)

    # Paired per-model differences FIRST (aligned by the 'model' coordinate),
    # THEN take the median across models -- median-of-differences, not
    # difference-of-medians.
    diff_stack = future_stack - historical_stack

    median_historical = historical_stack.median(dim="model", skipna=True, keep_attrs=True)
    median_future = future_stack.median(dim="model", skipna=True, keep_attrs=True)
    median_change = diff_stack.median(dim="model", skipna=True, keep_attrs=True)
    median_change.name = "change"
    median_change.attrs = {}

    return median_historical, median_future, median_change
