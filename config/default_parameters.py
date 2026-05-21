from models import DamParameters, TerrainBoundary, TerrainContour


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
    terrain_boundary=TerrainBoundary(
        left_bank_contours=(
            TerrainContour(
                elevation=100.0,
                points=(
                    (-170.0, 42.0, 100.0),
                    (-95.0, 28.0, 100.0),
                    (-20.0, 36.0, 100.0),
                    (65.0, 24.0, 100.0),
                    (150.0, 46.0, 100.0),
                ),
            ),
            TerrainContour(
                elevation=180.0,
                points=(
                    (-5.0, 4.0, 180.0),
                    (-2.5, 0.0, 180.0),
                    (0.0, 3.0, 180.0),
                    (2.5, 1.0, 180.0),
                    (5.0, 5.0, 180.0),
                ),
            ),
        ),
        right_bank_contours=(
            TerrainContour(
                elevation=100.0,
                points=(
                    (-170.0, 258.0, 100.0),
                    (-95.0, 276.0, 100.0),
                    (-20.0, 264.0, 100.0),
                    (65.0, 282.0, 100.0),
                    (150.0, 254.0, 100.0),
                ),
            ),
            TerrainContour(
                elevation=180.0,
                points=(
                    (-5.0, 296.0, 180.0),
                    (-2.5, 300.0, 180.0),
                    (0.0, 297.0, 180.0),
                    (2.5, 299.0, 180.0),
                    (5.0, 295.0, 180.0),
                ),
            ),
        ),
        sample_interval=10.0,
    ),
)
