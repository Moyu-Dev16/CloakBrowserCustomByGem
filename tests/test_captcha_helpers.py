"""Unit tests for core.captcha.geetest_solver helper functions"""
import math
import pytest

import core.captcha.geetest_solver as gs

# Double-underscore name at module level: not subject to name mangling,
# but can't be imported via `from ... import __name`. Use getattr instead.
ease_out_expo = getattr(gs, '__ease_out_expo')


class TestEaseOutExpo:
    def test_zero(self):
        result = ease_out_expo(0)
        assert result == pytest.approx(0.0, abs=0.001)

    def test_one(self):
        assert ease_out_expo(1) == 1

    def test_half(self):
        result = ease_out_expo(0.5)
        expected = 1 - math.pow(2, -5)
        assert result == pytest.approx(expected)

    def test_monotonically_increasing(self):
        prev = ease_out_expo(0)
        for i in range(1, 11):
            t = i / 10.0
            curr = ease_out_expo(t)
            assert curr >= prev
            prev = curr

    def test_output_in_range(self):
        for i in range(11):
            t = i / 10.0
            result = ease_out_expo(t)
            assert 0 <= result <= 1
