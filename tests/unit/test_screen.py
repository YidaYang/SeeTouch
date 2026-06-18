"""screen.py 单测。"""

from __future__ import annotations

import pytest

from seetouch.perception.screen import norm_to_pixel, pixel_to_norm


SCREEN = (1080, 2400)


def test_norm_to_pixel_center():
    assert norm_to_pixel(500, 500, SCREEN) == (540, 1200)


def test_norm_to_pixel_origin():
    assert norm_to_pixel(0, 0, SCREEN) == (0, 0)


def test_norm_to_pixel_clipped_at_edge():
    # 1000 norm -> would map to width pixel,但实现 clip 到 width-1 防越界
    x, y = norm_to_pixel(1000, 1000, SCREEN)
    assert x == SCREEN[0] - 1
    assert y == SCREEN[1] - 1


def test_pixel_to_norm_center():
    assert pixel_to_norm(540, 1200, SCREEN) == (500, 500)


def test_round_trip_within_one_unit():
    for nx, ny in [(0, 0), (250, 750), (500, 500), (1000, 1000)]:
        px, py = norm_to_pixel(nx, ny, SCREEN)
        rx, ry = pixel_to_norm(px, py, SCREEN)
        assert abs(rx - nx) <= 1
        assert abs(ry - ny) <= 1


def test_invalid_screen_size():
    with pytest.raises(ValueError):
        norm_to_pixel(500, 500, (0, 1000))
    with pytest.raises(ValueError):
        pixel_to_norm(500, 500, (1000, 0))
