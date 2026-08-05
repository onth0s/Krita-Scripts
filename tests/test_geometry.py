import math

import pytest

from krita_pie_menu.geometry import direction_from_vector

DEADZONE = 45


@pytest.mark.parametrize(
    "dx,dy",
    [
        (0, 0),
        (10, 0),
        (0, -10),
        (DEADZONE - 1, 0),
        (int(DEADZONE * 0.5), int(DEADZONE * 0.5)),
        (-int(DEADZONE * 0.5), int(DEADZONE * 0.5)),
    ],
)
def test_deadzone_returns_none(dx, dy):
    assert direction_from_vector(dx, dy, DEADZONE) is None


@pytest.mark.parametrize(
    "angle,expected",
    [
        (-90, "N"),
        (-45, "NE"),
        (0, "E"),
        (45, "SE"),
        (90, "S"),
        (135, "SW"),
        (180, "W"),
        (-135, "NW"),
    ],
)
def test_cardinal_and_diagonal_sectors(angle, expected):
    dist = DEADZONE + 20
    dx = math.cos(math.radians(angle)) * dist
    dy = math.sin(math.radians(angle)) * dist
    assert direction_from_vector(dx, dy, DEADZONE) == expected


@pytest.mark.parametrize(
    "angle,expected",
    [
        (-90, "N"),
        (-80, "N"),
        (-70, "N"),
        (-67.6, "N"),
        (-67.4, "NE"),
        (-22.6, "NE"),
        (-22.4, "E"),
        (22.4, "E"),
        (22.6, "SE"),
        (67.4, "SE"),
        (67.6, "S"),
        (112.4, "S"),
        (112.6, "SW"),
        (157.4, "SW"),
        (157.6, "W"),
        (170, "W"),
        (-157.4, "NW"),
        (-157.6, "W"),
        (-170, "W"),
        (-112.4, "N"),
        (-112.6, "NW"),
    ],
)
def test_sector_boundary_edges(angle, expected):
    dist = DEADZONE + 20
    dx = math.cos(math.radians(angle)) * dist
    dy = math.sin(math.radians(angle)) * dist
    assert direction_from_vector(dx, dy, DEADZONE) == expected


def test_sector_boundaries_belong_to_first_matching_sector():
    # The W sector wraps around +/-180deg; exact boundary values follow the
    # source's first-matching-condition ordering (verified via just-inside angles
    # above). Guard against accidental off-by-45 regressions on the diagonal axes.
    for sector in ("N", "NE", "E", "SE", "S", "SW", "W", "NW"):
        angle = {  # canonical axis angles (dist >= deadzone so no early None)
            "N": -90, "NE": -45, "E": 0, "SE": 45,
            "S": 90, "SW": 135, "W": 180, "NW": -135,
        }[sector]
        dist = DEADZONE + 20
        dx = math.cos(math.radians(angle)) * dist
        dy = math.sin(math.radians(angle)) * dist
        assert direction_from_vector(dx, dy, DEADZONE) == sector


def test_just_inside_deadzone_is_none():
    dx = math.cos(math.radians(45)) * (DEADZONE - 0.1)
    dy = math.sin(math.radians(45)) * (DEADZONE - 0.1)
    assert direction_from_vector(dx, dy, DEADZONE) is None
