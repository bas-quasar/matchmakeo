import matplotlib.pyplot as plt
from geoalchemy2.shape import to_shape


def _plot_outline(ax, geom, color, label_id):
    """Helper to draw polygon boundaries and label their centroids."""
    polys = geom.geoms if geom.geom_type == "MultiPolygon" else [geom]

    for i, poly in enumerate(polys):
        x, y = poly.exterior.xy
        ax.plot(
            x, y, color=color, linewidth=2, label=f"ID {label_id}" if i == 0 else ""
        )
        ax.fill(x, y, color=color, alpha=0.15)

    centroid = geom.centroid
    ax.text(
        centroid.x,
        centroid.y,
        str(label_id),
        color=color,
        fontsize=10,
        fontweight="bold",
        ha="center",
        va="center",
        bbox={"boxstyle": "round,pad=0.2", "fc": "white", "ec": color, "alpha": 0.85},
    )


def visualise_matched_pairs(
    match_result_set,
    id_attrs=("id", "id"),
    time_attrs=("timestamp", "timestamp"),
    max_cols=3,
    output_path="debug_spatial_match.png",
):
    """
    Plots matched pairs directly from a MatchResultSet object.

    :param match_result_set: An instance of MatchResultSet.
    :param id_attrs: Attribute name string or tuple of attribute names for record IDs.
    :param time_attrs: Attribute name string or tuple of attribute names for timestamps.
    :param max_cols: Maximum number of subplot columns in the grid.
    :param output_path: Destination path for the saved debug plot.
    """
    pairs = list(match_result_set)
    num_pairs = len(pairs)
    if num_pairs == 0:
        print("No matched pairs in MatchResultSet to plot.")
        return

    # Extract Product references attached to the MatchResultSet
    prod_a = match_result_set.products[0]
    prod_b = match_result_set.products[1]

    # Normalize column names in case products use different column names for ID or time
    id_attr_a, id_attr_b = (
        (id_attrs, id_attrs) if isinstance(id_attrs, str) else id_attrs
    )
    time_attr_a, time_attr_b = (
        (time_attrs, time_attrs) if isinstance(time_attrs, str) else time_attrs
    )

    cols = min(num_pairs, max_cols)
    rows = (num_pairs + cols - 1) // cols

    fig, axes = plt.subplots(rows, cols, figsize=(5 * cols, 5 * rows), squeeze=False)
    axes_flat = axes.flatten()

    for idx, row_group in enumerate(pairs):
        ax = axes_flat[idx]
        row_a, row_b = row_group[0], row_group[1]

        # 1. Fetch values from row bundles
        id_a = getattr(row_a, id_attr_a)
        id_b = getattr(row_b, id_attr_b)

        time_a = getattr(row_a, time_attr_a, None)
        time_b = getattr(row_b, time_attr_b, None)

        # Retrieve WKB geometry dynamically via product.geometry_column
        wkb_a = getattr(row_a, prod_a.geometry_column)
        wkb_b = getattr(row_b, prod_b.geometry_column)

        # 2. Convert WKB to Shapely shapes
        geom_a = to_shape(wkb_a)
        geom_b = to_shape(wkb_b)

        # 3. Draw outlines
        _plot_outline(ax, geom_a, color="red", label_id=id_a)
        _plot_outline(ax, geom_b, color="blue", label_id=id_b)

        # 4. Calculate spatial overlap fraction relative to the smaller polygon
        intersection_area = geom_a.intersection(geom_b).area
        min_area = min(geom_a.area, geom_b.area)
        overlap_fraction = intersection_area / min_area if min_area > 0 else 0.0

        # 5. Format timestamp difference
        if time_a is not None and time_b is not None:
            time_diff = abs(time_b - time_a)
            time_str = f"Δt: {time_diff}"
        else:
            time_str = "Δt: N/A"

        # 6. Styling
        ax.set_title(
            f"Pair #{idx + 1} (IDs: {id_a} vs {id_b})\n"
            f"{time_str} | Overlap: {overlap_fraction:.1%}",
            fontsize=11,
            fontweight="semibold",
        )
        ax.set_aspect("equal")
        ax.grid(True, linestyle="--", alpha=0.4)
        ax.legend(loc="upper right")

    # Hide unused subplot axes
    for j in range(num_pairs, len(axes_flat)):
        fig.delaxes(axes_flat[j])

    plt.tight_layout()
    plt.savefig(output_path, dpi=200, bbox_inches="tight")
    plt.close(fig)
    print(f"Saved debug plot to {output_path}")
