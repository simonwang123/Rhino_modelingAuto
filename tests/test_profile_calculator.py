from __future__ import annotations

import pytest

from config import DEFAULT_DAM_PARAMETERS
from geometry import ApdlPreparationOptions
from geometry.profile_calculator import ProfileCalculator
from models import DamParameters, TerrainBoundary, TerrainContour
from utils import sample_bank_curves_to_terrain_boundary


def make_parameters(**overrides: object) -> DamParameters:
    values = {
        "dam_height": 80.0,
        "crest_width": 10.0,
        "upstream_slope": 2.5,
        "downstream_slope": 2.0,
        "axis_length": 300.0,
        "foundation_elevation": 100.0,
        "crest_elevation": 180.0,
    }
    values.update(overrides)
    return DamParameters(**values)


def make_terrain_boundary(**overrides: object) -> TerrainBoundary:
    values = {
        "left_bank_contours": (
            TerrainContour(
                elevation=100.0,
                points=((-205.0, 0.0, 100.0), (180.0, 0.0, 100.0)),
            ),
            TerrainContour(
                elevation=180.0,
                points=((-5.0, 0.0, 180.0), (5.0, 0.0, 180.0)),
            ),
        ),
        "right_bank_contours": (
            TerrainContour(
                elevation=100.0,
                points=((-205.0, 300.0, 100.0), (180.0, 300.0, 100.0)),
            ),
            TerrainContour(
                elevation=180.0,
                points=((-5.0, 300.0, 180.0), (5.0, 300.0, 180.0)),
            ),
        ),
        "sample_interval": 10.0,
    }
    values.update(overrides)
    return TerrainBoundary(**values)


def test_valid_parameters_are_accepted() -> None:
    parameters = make_parameters()

    assert parameters.calculated_height == pytest.approx(80.0)
    assert parameters.terrain_boundary is None
    assert parameters.construction_stage_top_elevations is None
    assert parameters.construction_stages == ()


def test_height_must_match_elevation_difference() -> None:
    with pytest.raises(ValueError, match="crest_elevation - foundation_elevation"):
        make_parameters(dam_height=79.0)


@pytest.mark.parametrize(
    "field_name",
    [
        "dam_height",
        "crest_width",
        "upstream_slope",
        "downstream_slope",
        "axis_length",
    ],
)
def test_positive_fields_must_be_positive(field_name: str) -> None:
    with pytest.raises(ValueError, match=f"{field_name} must be positive"):
        make_parameters(**{field_name: 0.0})


def test_profile_points_are_calculated_from_slopes_and_elevations() -> None:
    profile = ProfileCalculator(make_parameters()).calculate()

    assert profile.upstream_toe.as_tuple() == pytest.approx((-205.0, 0.0, 100.0))
    assert profile.upstream_crest.as_tuple() == pytest.approx((-5.0, 0.0, 180.0))
    assert profile.downstream_crest.as_tuple() == pytest.approx((5.0, 0.0, 180.0))
    assert profile.downstream_profile_points == ()
    assert profile.downstream_toe.as_tuple() == pytest.approx((165.0, 0.0, 100.0))
    assert profile.cushion_layer is None
    assert profile.transition_layer is None


def test_profile_point_order_forms_closed_trapezoid() -> None:
    profile = ProfileCalculator(make_parameters()).calculate()
    points = profile.closed_points()

    assert points[0] is profile.upstream_toe
    assert points[-1] is profile.upstream_toe
    assert profile.upstream_toe.x < profile.upstream_crest.x
    assert profile.upstream_crest.x < profile.downstream_crest.x
    assert profile.downstream_crest.x < profile.downstream_toe.x
    assert profile.upstream_toe.z == profile.downstream_toe.z
    assert profile.upstream_crest.z == profile.downstream_crest.z


def test_profile_with_manual_downstream_benches() -> None:
    profile = ProfileCalculator(
        make_parameters(
            bench_count=3,
            bench_elevations=(160.0, 140.0, 120.0),
            bench_width=5.0,
        )
    ).calculate()

    assert [point.as_tuple() for point in profile.downstream_boundary_points()] == pytest.approx(
        [
            (5.0, 0.0, 180.0),
            (45.0, 0.0, 160.0),
            (50.0, 0.0, 160.0),
            (90.0, 0.0, 140.0),
            (95.0, 0.0, 140.0),
            (135.0, 0.0, 120.0),
            (140.0, 0.0, 120.0),
            (180.0, 0.0, 100.0),
        ]
    )
    assert len(profile.points()) == 10


def test_manual_bench_elevations_are_sorted_from_high_to_low() -> None:
    parameters = make_parameters(
        bench_count=3,
        bench_elevations=(120.0, 160.0, 140.0),
        bench_width=5.0,
    )

    assert parameters.bench_elevations == (160.0, 140.0, 120.0)


def test_bench_elevations_are_auto_spaced_when_omitted() -> None:
    parameters = make_parameters(bench_count=3, bench_width=5.0)

    assert parameters.bench_elevations == pytest.approx((160.0, 140.0, 120.0))


def test_bench_count_must_match_manual_elevation_count() -> None:
    with pytest.raises(ValueError, match="bench_elevations length must equal bench_count"):
        make_parameters(
            bench_count=2,
            bench_elevations=(160.0, 140.0, 120.0),
            bench_width=5.0,
        )


@pytest.mark.parametrize("elevation", [100.0, 180.0, 90.0, 190.0])
def test_bench_elevations_must_be_inside_dam_height(elevation: float) -> None:
    with pytest.raises(ValueError, match="bench_elevations must be strictly between"):
        make_parameters(
            bench_count=1,
            bench_elevations=(elevation,),
            bench_width=5.0,
        )


def test_bench_width_must_be_positive_when_benches_exist() -> None:
    with pytest.raises(ValueError, match="bench_width must be positive"):
        make_parameters(bench_count=1, bench_width=0.0)


def test_bench_count_must_be_non_negative() -> None:
    with pytest.raises(ValueError, match="bench_count must be non-negative"):
        make_parameters(bench_count=-1)


def test_bench_width_must_be_zero_without_benches() -> None:
    with pytest.raises(ValueError, match="bench_width must be 0"):
        make_parameters(bench_width=5.0)


def test_downstream_profile_is_monotonic_with_benches() -> None:
    profile = ProfileCalculator(
        make_parameters(bench_count=3, bench_width=5.0)
    ).calculate()
    downstream_points = profile.downstream_boundary_points()

    for previous, current in zip(downstream_points, downstream_points[1:]):
        assert previous.x < current.x
        assert previous.z >= current.z


def test_secondary_rockfill_is_absent_by_default() -> None:
    profile = ProfileCalculator(make_parameters()).calculate()

    assert profile.secondary_rockfill_zone is None


def test_terrain_boundary_is_accepted_when_it_matches_dam_elevations() -> None:
    parameters = make_parameters(terrain_boundary=make_terrain_boundary())

    assert parameters.terrain_boundary is not None
    assert parameters.terrain_boundary.elevations == pytest.approx((100.0, 180.0))


def test_default_terrain_boundary_uses_polyline_contours() -> None:
    assert DEFAULT_DAM_PARAMETERS.terrain_boundary is not None

    terrain_boundary = DEFAULT_DAM_PARAMETERS.terrain_boundary
    assert all(
        len(contour.points) > 2
        for contour in (
            *terrain_boundary.left_bank_contours,
            *terrain_boundary.right_bank_contours,
        )
    )


def test_terrain_boundary_requires_at_least_two_contours_per_bank() -> None:
    with pytest.raises(ValueError, match="left_bank_contours"):
        make_terrain_boundary(
            left_bank_contours=(
                TerrainContour(
                    elevation=100.0,
                    points=((-205.0, 0.0, 100.0), (180.0, 0.0, 100.0)),
                ),
            )
        )


def test_terrain_boundary_requires_matching_bank_elevations() -> None:
    with pytest.raises(ValueError, match="same elevations"):
        make_terrain_boundary(
            right_bank_contours=(
                TerrainContour(
                    elevation=100.0,
                    points=((-205.0, 300.0, 100.0), (180.0, 300.0, 100.0)),
                ),
                TerrainContour(
                    elevation=170.0,
                    points=((-30.0, 300.0, 170.0), (30.0, 300.0, 170.0)),
                ),
            )
        )


def test_terrain_contour_requires_at_least_two_points() -> None:
    with pytest.raises(ValueError, match="at least 2 points"):
        TerrainContour(elevation=100.0, points=((0.0, 0.0, 100.0),))


def test_terrain_contour_points_must_match_elevation() -> None:
    with pytest.raises(ValueError, match="match the contour elevation"):
        TerrainContour(
            elevation=100.0,
            points=((0.0, 0.0, 100.0), (1.0, 0.0, 101.0)),
        )


def test_terrain_boundary_left_bank_must_precede_right_bank_along_y() -> None:
    with pytest.raises(ValueError, match="before right_bank_contours"):
        make_terrain_boundary(
            left_bank_contours=(
                TerrainContour(
                    elevation=100.0,
                    points=((-205.0, 300.0, 100.0), (180.0, 300.0, 100.0)),
                ),
                TerrainContour(
                    elevation=180.0,
                    points=((-5.0, 300.0, 180.0), (5.0, 300.0, 180.0)),
                ),
            ),
            right_bank_contours=(
                TerrainContour(
                    elevation=100.0,
                    points=((-205.0, 0.0, 100.0), (180.0, 0.0, 100.0)),
                ),
                TerrainContour(
                    elevation=180.0,
                    points=((-5.0, 0.0, 180.0), (5.0, 0.0, 180.0)),
                ),
            ),
        )


def test_terrain_boundary_must_span_foundation_to_crest_elevations() -> None:
    with pytest.raises(ValueError, match="lowest elevation"):
        make_parameters(
            terrain_boundary=make_terrain_boundary(
                left_bank_contours=(
                    TerrainContour(
                        elevation=110.0,
                        points=((-180.0, 0.0, 110.0), (160.0, 0.0, 110.0)),
                    ),
                    TerrainContour(
                        elevation=180.0,
                        points=((-5.0, 0.0, 180.0), (5.0, 0.0, 180.0)),
                    ),
                ),
                right_bank_contours=(
                    TerrainContour(
                        elevation=110.0,
                        points=((-180.0, 300.0, 110.0), (160.0, 300.0, 110.0)),
                    ),
                    TerrainContour(
                        elevation=180.0,
                        points=((-5.0, 300.0, 180.0), (5.0, 300.0, 180.0)),
                    ),
                ),
            )
        )


def test_terrain_boundary_points_must_stay_within_axis_length() -> None:
    with pytest.raises(ValueError, match="within the dam axis length"):
        make_parameters(
            terrain_boundary=make_terrain_boundary(
                right_bank_contours=(
                    TerrainContour(
                        elevation=100.0,
                        points=((-205.0, 310.0, 100.0), (180.0, 310.0, 100.0)),
                    ),
                    TerrainContour(
                        elevation=180.0,
                        points=((-5.0, 310.0, 180.0), (5.0, 310.0, 180.0)),
                    ),
                )
            )
        )


def test_bank_curve_sampling_requires_matching_elevation_count() -> None:
    with pytest.raises(ValueError, match="left_bank_curves length"):
        sample_bank_curves_to_terrain_boundary(
            left_bank_curves=(),
            right_bank_curves=(),
            elevations=(100.0,),
        )


def test_construction_stage_top_elevations_create_stage_intervals() -> None:
    parameters = make_parameters(
        construction_stage_top_elevations=(120.0, 150.0, 180.0)
    )

    assert [
        (
            stage.stage_index,
            stage.bottom_elevation,
            stage.top_elevation,
        )
        for stage in parameters.construction_stages
    ] == [
        (1, 100.0, 120.0),
        (2, 120.0, 150.0),
        (3, 150.0, 180.0),
    ]


def test_apdl_preparation_options_default_to_stage_only_meter_model() -> None:
    options = ApdlPreparationOptions()

    assert options.include_global_geometry is False
    assert options.target_unit_system == "Meters"
    assert options.min_edge_length == pytest.approx(1.0)
    assert options.min_face_area == pytest.approx(1.0)
    assert options.shrink_trimmed_faces is True
    assert options.merge_coplanar_faces is True
    assert options.fail_on_remaining_small_features is True


def test_apdl_preparation_options_reject_global_geometry() -> None:
    with pytest.raises(ValueError, match="must not include global geometry"):
        ApdlPreparationOptions(include_global_geometry=True)


def test_construction_stage_top_elevations_must_be_strictly_increasing() -> None:
    with pytest.raises(ValueError, match="strictly increasing"):
        make_parameters(construction_stage_top_elevations=(120.0, 120.0, 180.0))


def test_construction_stage_top_elevations_must_be_above_foundation() -> None:
    with pytest.raises(ValueError, match="greater than foundation_elevation"):
        make_parameters(construction_stage_top_elevations=(100.0, 120.0, 180.0))


def test_construction_stage_top_elevations_must_not_exceed_crest() -> None:
    with pytest.raises(ValueError, match="must not exceed crest_elevation"):
        make_parameters(construction_stage_top_elevations=(120.0, 190.0))


def test_construction_stage_top_elevations_must_end_at_crest() -> None:
    with pytest.raises(ValueError, match="last value must equal crest_elevation"):
        make_parameters(construction_stage_top_elevations=(120.0, 160.0))


def test_cushion_layer_points_are_calculated_from_horizontal_thicknesses() -> None:
    profile = ProfileCalculator(
        make_parameters(
            cushion_layer_top_thickness=2.0,
            cushion_layer_bottom_thickness=8.0,
        )
    ).calculate()

    assert profile.cushion_layer is not None
    assert [
        point.as_tuple() for point in profile.cushion_layer.boundary_points()
    ] == pytest.approx(
        [
            (-205.0, 0.0, 100.0),
            (-5.0, 0.0, 180.0),
            (-3.0, 0.0, 180.0),
            (-197.0, 0.0, 100.0),
        ]
    )
    assert profile.transition_layer is None


def test_transition_layer_reuses_cushion_layer_inner_boundary() -> None:
    profile = ProfileCalculator(
        make_parameters(
            cushion_layer_top_thickness=2.0,
            cushion_layer_bottom_thickness=8.0,
            transition_layer_top_thickness=3.0,
            transition_layer_bottom_thickness=12.0,
        )
    ).calculate()

    assert profile.cushion_layer is not None
    assert profile.transition_layer is not None
    cushion_points = profile.cushion_layer.boundary_points()
    transition_points = profile.transition_layer.boundary_points()

    assert transition_points[0].as_tuple() == pytest.approx(cushion_points[3].as_tuple())
    assert transition_points[1].as_tuple() == pytest.approx(cushion_points[2].as_tuple())
    assert [point.as_tuple() for point in transition_points] == pytest.approx(
        [
            (-197.0, 0.0, 100.0),
            (-3.0, 0.0, 180.0),
            (0.0, 0.0, 180.0),
            (-185.0, 0.0, 100.0),
        ]
    )


def test_upstream_layer_thicknesses_must_be_non_negative() -> None:
    with pytest.raises(ValueError, match="cushion_layer thicknesses"):
        make_parameters(cushion_layer_top_thickness=-1.0)


def test_upstream_layer_top_and_bottom_thicknesses_must_be_enabled_together() -> None:
    with pytest.raises(ValueError, match="both be positive"):
        make_parameters(cushion_layer_top_thickness=2.0)


def test_transition_layer_requires_cushion_layer() -> None:
    with pytest.raises(ValueError, match="requires cushion_layer"):
        make_parameters(
            transition_layer_top_thickness=3.0,
            transition_layer_bottom_thickness=12.0,
        )


def test_upstream_layers_must_stay_inside_dam_section() -> None:
    with pytest.raises(ValueError, match="cushion_layer must stay inside"):
        ProfileCalculator(
            make_parameters(
                cushion_layer_top_thickness=11.0,
                cushion_layer_bottom_thickness=8.0,
            )
        ).calculate()


def test_secondary_rockfill_zone_with_boundary_right_side_is_valid() -> None:
    profile = ProfileCalculator(
        make_parameters(
            bench_count=3,
            bench_width=5.0,
            secondary_rockfill_points=(
                (45.0, 150.0),
                (70.0, 150.0),
                (160.0, 110.0),
                (120.0, 110.0),
            ),
        )
    ).calculate()

    assert profile.secondary_rockfill_zone is not None
    assert [
        point.as_tuple() for point in profile.secondary_rockfill_zone.points
    ] == pytest.approx(
        [
            (45.0, 0.0, 150.0),
            (70.0, 0.0, 150.0),
            (160.0, 0.0, 110.0),
            (120.0, 0.0, 110.0),
        ]
    )
    assert [
        point.as_tuple() for point in profile.secondary_rockfill_zone.boundary_points()
    ] == pytest.approx(
        [
            (160.0, 0.0, 110.0),
            (120.0, 0.0, 110.0),
            (45.0, 0.0, 150.0),
            (70.0, 0.0, 150.0),
            (90.0, 0.0, 140.0),
            (95.0, 0.0, 140.0),
            (135.0, 0.0, 120.0),
            (140.0, 0.0, 120.0),
        ]
    )


def test_secondary_rockfill_right_boundary_follows_downstream_boundary_across_bench() -> None:
    profile = ProfileCalculator(
        make_parameters(
            bench_count=3,
            bench_width=5.0,
            secondary_rockfill_points=(
                (20.0, 170.0),
                (25.0, 170.0),
                (70.0, 150.0),
                (45.0, 150.0),
            ),
        )
    ).calculate()

    assert profile.secondary_rockfill_zone is not None
    assert [
        point.as_tuple() for point in profile.secondary_rockfill_zone.boundary_points()
    ] == pytest.approx(
        [
            (70.0, 0.0, 150.0),
            (45.0, 0.0, 150.0),
            (20.0, 0.0, 170.0),
            (25.0, 0.0, 170.0),
            (45.0, 0.0, 160.0),
            (50.0, 0.0, 160.0),
        ]
    )


def test_secondary_rockfill_right_boundary_uses_line_when_one_point_is_internal() -> None:
    profile = ProfileCalculator(
        make_parameters(
            bench_count=3,
            bench_width=5.0,
            secondary_rockfill_points=(
                (20.0, 170.0),
                (25.0, 170.0),
                (55.0, 150.0),
                (35.0, 150.0),
            ),
        )
    ).calculate()

    assert profile.secondary_rockfill_zone is not None
    assert [
        point.as_tuple() for point in profile.secondary_rockfill_zone.boundary_points()
    ] == pytest.approx(
        [
            (55.0, 0.0, 150.0),
            (35.0, 0.0, 150.0),
            (20.0, 0.0, 170.0),
            (25.0, 0.0, 170.0),
        ]
    )


def test_secondary_rockfill_right_boundary_uses_line_when_both_points_are_internal() -> None:
    profile = ProfileCalculator(
        make_parameters(
            bench_count=3,
            bench_width=5.0,
            secondary_rockfill_points=(
                (20.0, 170.0),
                (24.0, 170.0),
                (55.0, 150.0),
                (35.0, 150.0),
            ),
        )
    ).calculate()

    assert profile.secondary_rockfill_zone is not None
    assert len(profile.secondary_rockfill_zone.boundary_points()) == 4


def test_secondary_rockfill_straight_right_boundary_must_not_cross_downstream_boundary() -> None:
    with pytest.raises(ValueError, match="must not intersect"):
        ProfileCalculator(
            make_parameters(
                bench_count=3,
                bench_width=5.0,
                secondary_rockfill_points=(
                    (-1.0, 170.0),
                    (5.0, 180.0),
                    (155.0, 105.0),
                    (50.0, 105.0),
                ),
            )
        ).calculate()


def test_secondary_rockfill_straight_right_boundary_must_stay_inside_section() -> None:
    with pytest.raises(ValueError, match="must stay inside"):
        ProfileCalculator(
            make_parameters(
                bench_count=3,
                bench_width=5.0,
                secondary_rockfill_points=(
                    (-1.0, 170.0),
                    (5.0, 180.0),
                    (160.0, 105.0),
                    (50.0, 105.0),
                ),
            )
        ).calculate()


def test_secondary_rockfill_requires_exactly_four_points() -> None:
    with pytest.raises(ValueError, match="exactly 4 points"):
        make_parameters(
            secondary_rockfill_points=(
                (45.0, 150.0),
                (70.0, 150.0),
                (120.0, 110.0),
            )
        )


def test_secondary_rockfill_elevations_must_be_in_dam_height() -> None:
    with pytest.raises(ValueError, match="within the dam height"):
        make_parameters(
            secondary_rockfill_points=(
                (45.0, 150.0),
                (70.0, 150.0),
                (160.0, 190.0),
                (120.0, 110.0),
            )
        )


def test_secondary_rockfill_rejects_duplicate_points() -> None:
    with pytest.raises(ValueError, match="duplicate"):
        ProfileCalculator(
            make_parameters(
                bench_count=3,
                bench_width=5.0,
                secondary_rockfill_points=(
                    (45.0, 150.0),
                    (70.0, 150.0),
                    (70.0, 150.0),
                    (120.0, 110.0),
                ),
            )
        ).calculate()


def test_secondary_rockfill_rejects_zero_area_polygon() -> None:
    with pytest.raises(ValueError, match="positive area"):
        ProfileCalculator(
            make_parameters(
                bench_count=3,
                bench_width=5.0,
                secondary_rockfill_points=(
                    (45.0, 150.0),
                    (65.0, 150.0),
                    (85.0, 150.0),
                    (105.0, 150.0),
                ),
            )
        ).calculate()


def test_secondary_rockfill_rejects_self_intersection() -> None:
    with pytest.raises(ValueError, match="non-self-intersecting"):
        ProfileCalculator(
            make_parameters(
                bench_count=3,
                bench_width=5.0,
                secondary_rockfill_points=(
                    (45.0, 150.0),
                    (160.0, 110.0),
                    (70.0, 150.0),
                    (120.0, 105.0),
                ),
            )
        ).calculate()


def test_secondary_rockfill_left_side_must_be_strictly_inside() -> None:
    with pytest.raises(ValueError, match="left secondary_rockfill_points"):
        ProfileCalculator(
            make_parameters(
                bench_count=3,
                bench_width=5.0,
                secondary_rockfill_points=(
                    (75.0, 150.0),
                    (80.0, 150.0),
                    (160.0, 110.0),
                    (120.0, 110.0),
                ),
            )
        ).calculate()


def test_secondary_rockfill_right_side_must_not_extend_outside_downstream_boundary() -> None:
    with pytest.raises(ValueError, match="right secondary_rockfill_points"):
        ProfileCalculator(
            make_parameters(
                bench_count=3,
                bench_width=5.0,
                secondary_rockfill_points=(
                    (45.0, 150.0),
                    (80.0, 150.0),
                    (170.0, 110.0),
                    (120.0, 110.0),
                ),
            )
        ).calculate()


def test_default_parameters_include_valid_secondary_rockfill_zone() -> None:
    profile = ProfileCalculator(DEFAULT_DAM_PARAMETERS).calculate()

    assert DEFAULT_DAM_PARAMETERS.terrain_boundary is not None
    assert DEFAULT_DAM_PARAMETERS.construction_stage_top_elevations is not None
    assert DEFAULT_DAM_PARAMETERS.construction_stage_top_elevations[-1] == pytest.approx(
        DEFAULT_DAM_PARAMETERS.crest_elevation
    )
    assert DEFAULT_DAM_PARAMETERS.construction_stage_top_elevations == tuple(
        sorted(DEFAULT_DAM_PARAMETERS.construction_stage_top_elevations)
    )
    assert len(DEFAULT_DAM_PARAMETERS.construction_stages) == 8
    assert profile.secondary_rockfill_zone is not None
    assert profile.cushion_layer is not None
    assert profile.transition_layer is not None
