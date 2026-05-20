from __future__ import annotations

import pytest

from config import DEFAULT_DAM_PARAMETERS
from geometry.profile_calculator import ProfileCalculator
from models import DamParameters


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


def test_valid_parameters_are_accepted() -> None:
    parameters = make_parameters()

    assert parameters.calculated_height == pytest.approx(80.0)


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

    assert profile.secondary_rockfill_zone is not None
