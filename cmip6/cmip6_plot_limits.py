#!/usr/bin/env python3
"""
CMIP6 Plot Limits and Land Masking
====================================
Helpers used by build_ensemble_medians.py to (1) mask ensemble-median fields
to land and (2) derive color-scale limits from the land-only values.

Limit rules
-----------
Median panels (historical / mid-century / end-century):
    ONE range per variable, from the 5th-95th percentile of land values
    pooled over the historical field and every scenario/period median field.
    If the variable's config has 'median_floor_zero': True, the lower
    limit is pinned to 0. If it has 'median_symmetric': True, the range is
    instead -L to +L with L = max(|p_lo|, |p_hi|), centered on 0.

Change panels:
    Set PER PLOT, shape controlled by config['change_sign']:
        'positive'  ->  0 to p95
        'negative'  ->  p5 to 0
        absent      ->  symmetric, +/- max(|p5|, |p95|)

All limits are rounded to a few significant figures (see nice_number).

Fixed-limit overrides (config keys 'median_limits' / 'change_limits')
---------------------------------------------------------------------
Set either key to a (lo, hi) tuple in CMIP6_VARIABLE_CONFIG to bypass the
percentile calculation for that variable. Use None for one side to keep the
automatic value for that side, e.g. 'change_limits': (0, None) pins the
bottom at 0 and computes the top from percentiles. Fixed change limits apply
to all 8 scenario/period plots of that variable.
"""

import numpy as np

_land_regions = None
_mask_cache = {}


def _get_land_regions():
    """
    Load the Natural Earth 1:50m land polygons (lazily, on first use).

    regionmask downloads these from the internet the FIRST time and caches
    them locally (via pooch, normally under ~/.cache). If this fails on a
    node without outbound network access, run once from a node that has it:

        python3 -c "import regionmask; regionmask.defined_regions.natural_earth_v5_0_0.land_50"

    and later runs will use the cached copy.
    """
    global _land_regions
    if _land_regions is None:
        import regionmask
        try:
            _land_regions = regionmask.defined_regions.natural_earth_v5_0_0.land_50
        except Exception as e:
            raise RuntimeError(
                "Could not load Natural Earth land polygons for the land mask "
                f"({type(e).__name__}: {e}). regionmask downloads them on first use; "
                "pre-fetch once from a node with internet access (see "
                "_get_land_regions docstring), or run with --no-land-mask."
            ) from e
    return _land_regions


def mask_to_land(da):
    """Return `da` with NaN over ocean. The land mask is built once per grid."""
    key = (da.lat.size, da.lon.size,
           round(float(da.lat[0]), 4), round(float(da.lon[0]), 4))
    if key not in _mask_cache:
        _mask_cache[key] = _get_land_regions().mask(da.lon, da.lat).notnull()
    return da.where(_mask_cache[key])


def nice_number(x, sig=2):
    """Round to `sig` significant figures: 35.4 -> 35, 432 -> 430, 0.043 -> 0.043."""
    if x == 0 or not np.isfinite(x):
        return 0.0
    digits = sig - 1 - int(np.floor(np.log10(abs(x))))
    return float(np.round(x, digits))


def _finite(da):
    v = np.asarray(da.values).ravel()
    return v[np.isfinite(v)]


def _auto_median_limits(fields, config, pct=(5, 95)):
    """
    One (vmin, vmax) for the median panels of a variable.

    fields : list of land-masked (lat, lon) DataArrays (historical plus every
             scenario/period future median field)
    """
    vals = np.concatenate([_finite(f) for f in fields])
    if vals.size == 0:
        raise ValueError("No finite land values found for median limits")
    p_lo, p_hi = np.percentile(vals, pct)
    if config.get("median_symmetric"):
        lim = nice_number(max(abs(p_lo), abs(p_hi)))
        return -lim, lim
    lo = 0.0 if config.get("median_floor_zero") else nice_number(p_lo)
    hi = nice_number(p_hi)
    if hi <= lo:
        hi = nice_number(float(np.max(vals)))
    return lo, hi


def _auto_change_limits(field, config, pct=(5, 95)):
    """(vmin, vmax) for one change panel, from land-only values."""
    vals = _finite(field)
    if vals.size == 0:
        raise ValueError("No finite land values found for change limits")
    sign = config.get("change_sign")
    p_lo, p_hi = np.percentile(vals, pct)

    if sign == "positive":
        lo, hi = 0.0, nice_number(p_hi)
    elif sign == "negative":
        lo, hi = nice_number(p_lo), 0.0
    else:
        lim = nice_number(max(abs(p_lo), abs(p_hi)))
        lo, hi = -lim, lim

    # Degenerate (e.g. sparse count variable where p95 is 0): use the extreme.
    if lo == hi or (sign == "positive" and hi <= 0) or (sign == "negative" and lo >= 0):
        ext = nice_number(float(np.max(np.abs(vals))))
        lo, hi = {"positive": (0.0, ext), "negative": (-ext, 0.0)}.get(sign, (-ext, ext))
    return lo, hi


def _apply_override(auto, override):
    """
    Replace auto-computed (lo, hi) with fixed values from the config.
    `override` is (lo, hi); either side may be None to keep the automatic
    value for that side. Fixed values are used exactly as given (not rounded).
    """
    lo, hi = auto
    o_lo, o_hi = override
    lo = lo if o_lo is None else o_lo
    hi = hi if o_hi is None else o_hi
    if lo >= hi:
        raise ValueError(f"Fixed limits give lo >= hi ({lo}, {hi}); check the config")
    return lo, hi


def median_limits(fields, config, pct=(5, 95)):
    """
    One (vmin, vmax) for the median panels of a variable.

    If config has 'median_limits': (lo, hi), those values are used instead of
    percentiles (None on either side keeps the automatic value for that side).
    """
    override = config.get("median_limits")
    if override is not None and None not in override:
        return _apply_override((0.0, 1.0), override)   # fully fixed: skip data entirely
    auto = _auto_median_limits(fields, config, pct)
    return _apply_override(auto, override) if override is not None else auto


def change_limits(field, config, pct=(5, 95)):
    """
    (vmin, vmax) for one change panel.

    If config has 'change_limits': (lo, hi), those values are used for EVERY
    change plot of that variable instead of per-plot percentiles (None on
    either side keeps the automatic value for that side).
    """
    override = config.get("change_limits")
    if override is not None and None not in override:
        return _apply_override((0.0, 1.0), override)
    auto = _auto_change_limits(field, config, pct)
    return _apply_override(auto, override) if override is not None else auto
