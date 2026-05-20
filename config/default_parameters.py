from models import DamParameters


DEFAULT_DAM_PARAMETERS = DamParameters(
    dam_height=80.0,
    crest_width=10.0,
    upstream_slope=2.5,
    downstream_slope=2.0,
    axis_length=300.0,
    foundation_elevation=100.0,
    crest_elevation=180.0,
    cushion_layer_top_thickness=2.0,
    cushion_layer_bottom_thickness=8.0,
    transition_layer_top_thickness=3.0,
    transition_layer_bottom_thickness=12.0,
    bench_count=3,
    bench_elevations=(160.0, 140.0, 120.0),
    bench_width=5.0,
    secondary_rockfill_points=(
        (45.0, 150.0),
        (70.0, 150.0),
        (160.0, 110.0),
        (120.0, 110.0),
    ),
)
