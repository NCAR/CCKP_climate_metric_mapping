#!/usr/bin/env python3
"""
CMIP6 Per-Model Diagnostic Plots
===================================
Sanity-check plots for individual models: one figure per model/scenario,
laid out as:

    Row 1:  Historical  |  Mid-Century        |  End-Century
    Row 2:  (blank)     |  Mid-Century - Hist  |  End-Century - Hist

Row 1 shares one vertical colorbar (absolute/median color scale).
Row 2 shares one vertical colorbar (change color scale), aligned under
its two populated columns.

Built on top of Stage 1 intermediate NetCDFs (one field per model/
scenario/period) -- no multi-model stacking needed here since this is a
per-model check.
"""

import numpy as np
import matplotlib.pyplot as plt
import cartopy.crs as ccrs

from cmip6_risk_mapper import setup_map_axes, resolve_cmap


def add_row_colorbar(fig, axes, mappable, label):
    """
    Add one shared vertical colorbar spanning the given row of axes,
    placed just to the right of the rightmost axis in that row.
    """
    positions = [ax.get_position() for ax in axes]
    x1 = max(p.x1 for p in positions)
    y0 = min(p.y0 for p in positions)
    y1 = max(p.y1 for p in positions)
    cbar_ax = fig.add_axes([x1 + 0.02, y0, 0.02, y1 - y0])
    fig.colorbar(mappable, cax=cbar_ax, orientation="vertical", label=label)


def create_model_diagnostic_plot(historical, midcentury, endcentury, config,
                                  output_path, model, variable, scenario,
                                  historical_period, midcentury_period,
                                  endcentury_period):
    """
    Create one 2x3 diagnostic figure for a single model/scenario.

    Parameters
    ----------
    historical, midcentury, endcentury : xarray.DataArray
        (lat, lon) fields for this model, loaded from Stage 1 intermediates
    config : dict
        Entry from CMIP6_VARIABLE_CONFIG for this variable
    output_path : str or Path
    model, variable, scenario : str
    historical_period, midcentury_period, endcentury_period : tuple
        (start_year, end_year) for each period, used in panel titles

    Returns
    -------
    matplotlib.figure.Figure
    """
    change_mid = midcentury - historical
    change_end = endcentury - historical

    tcrs = ccrs.PlateCarree()
    pcrs = ccrs.Robinson()

    fig, axes = plt.subplots(2, 3, figsize=(13, 7.5),
                              subplot_kw={"projection": pcrs})
    fig.subplots_adjust(left=0.03, right=0.88, top=0.90, bottom=0.05,
                         hspace=0.15, wspace=0.08)

    hist_start, hist_end = historical_period
    mid_start, mid_end = midcentury_period
    end_start, end_end = endcentury_period

    # --- Row 1: historical / mid-century / end-century (shared scale) ---
    row0_data = [historical, midcentury, endcentury]
    row0_titles = [
        f"Historical ({hist_start}-{hist_end})",
        f"Mid-Century ({mid_start}-{mid_end}, {scenario})",
        f"End-Century ({end_start}-{end_end}, {scenario})",
    ]
    vmin_m, vmax_m = config["vmin_median"], config["vmax_median"]
    cmap_m = resolve_cmap(config["cmap_median"])

    mappable0 = None
    for i, ax in enumerate(axes[0]):
        lon = row0_data[i].lon.values
        lat = row0_data[i].lat.values
        X, Y = np.meshgrid(lon, lat)
        mappable0 = ax.pcolormesh(X, Y, row0_data[i], vmin=vmin_m, vmax=vmax_m,
                                   cmap=cmap_m, transform=tcrs)
        setup_map_axes(ax)
        ax.set_title(row0_titles[i], loc="left", fontsize=9)

    add_row_colorbar(fig, axes[0], mappable0, config["units"])

    # --- Row 2: blank / mid-hist / end-hist (shared change scale) ---
    axes[1][0].axis("off")

    row1_data = {1: change_mid, 2: change_end}
    row1_titles = {
        1: f"Mid-Century \u2212 Historical",
        2: f"End-Century \u2212 Historical",
    }
    vmin_c, vmax_c = config["vmin_change"], config["vmax_change"]
    cmap_c = resolve_cmap(config["cmap_change"])

    mappable1 = None
    for i in (1, 2):
        ax = axes[1][i]
        data = row1_data[i]
        lon = data.lon.values
        lat = data.lat.values
        X, Y = np.meshgrid(lon, lat)
        mappable1 = ax.pcolormesh(X, Y, data, vmin=vmin_c, vmax=vmax_c,
                                   cmap=cmap_c, transform=tcrs)
        setup_map_axes(ax)
        ax.set_title(row1_titles[i], loc="left", fontsize=9)

    add_row_colorbar(fig, [axes[1][1], axes[1][2]], mappable1, config["units"])

    fig.suptitle(f"{model} \u2014 {config['long_name']} ({scenario})",
                 fontsize=12, x=0.05, ha="left")

    plt.savefig(output_path, dpi=200, bbox_inches="tight")
    plt.close(fig)
    return fig
