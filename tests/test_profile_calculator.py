from __future__ import annotations

import pytest

from geometry.profile_calculator import ProfileCalculator
from models import DamParameters


def make_parameters(**overrides: float) -> DamParameters:
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
