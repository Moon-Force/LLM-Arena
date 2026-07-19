"""SciCode-style hard tests for RK4 two-body orbit."""

from __future__ import annotations

import math

import pytest

from orbit import (
    integrate_orbit,
    rk4_step,
    specific_angular_momentum_z,
    specific_energy,
)


MU = 1.0
# Circular orbit: r=1, v=1, period 2π
Y0 = [1.0, 0.0, 0.0, 1.0]


class TestEnergyAngular:
    def test_specific_energy_circular(self):
        e = specific_energy(Y0, MU)
        assert e == pytest.approx(-0.5, rel=1e-12, abs=1e-12)

    def test_angular_momentum_circular(self):
        hz = specific_angular_momentum_z(Y0)
        assert hz == pytest.approx(1.0, rel=1e-12, abs=1e-12)

    def test_energy_formula_general(self):
        y = [3.0, 4.0, 0.1, -0.2]  # r=5
        e = specific_energy(y, 2.0)
        # |v|^2/2 = 0.025, mu/r = 0.4 → E = 0.025 - 0.4
        assert e == pytest.approx(-0.375, abs=1e-12)


class TestRK4Step:
    def test_does_not_mutate_input(self):
        y = [1.0, 0.0, 0.0, 1.0]
        y_copy = y[:]
        _ = rk4_step(y, 0.0, 1e-3, MU)
        assert y == y_copy

    def test_step_moves_forward(self):
        y1 = rk4_step(Y0, 0.0, 1e-2, MU)
        assert len(y1) == 4
        # for circular, after small dt, x decreases slightly from cos, y increases
        assert y1[1] > 0  # y position
        assert abs(y1[0] - 1.0) < 0.01


class TestIntegrationHard:
    def test_period_return(self):
        period = 2.0 * math.pi
        dt = period / 2000.0
        traj = integrate_orbit(Y0, 0.0, period, dt, MU)
        final = traj[-1]
        # Should return near starting point after one period
        assert final[0] == pytest.approx(1.0, abs=2e-4)
        assert final[1] == pytest.approx(0.0, abs=2e-4)
        assert final[2] == pytest.approx(0.0, abs=2e-4)
        assert final[3] == pytest.approx(1.0, abs=2e-4)

    def test_energy_conservation_long(self):
        period = 2.0 * math.pi
        t1 = 8.0 * period
        dt = period / 1500.0
        traj = integrate_orbit(Y0, 0.0, t1, dt, MU)
        e0 = specific_energy(traj[0], MU)
        e1 = specific_energy(traj[-1], MU)
        rel = abs(e1 - e0) / abs(e0)
        assert rel < 1e-6, f"energy relative drift {rel}"

    def test_angular_momentum_conservation(self):
        period = 2.0 * math.pi
        t1 = 5.0 * period
        dt = period / 1200.0
        traj = integrate_orbit(Y0, 0.0, t1, dt, MU)
        h0 = specific_angular_momentum_z(traj[0])
        h1 = specific_angular_momentum_z(traj[-1])
        assert abs(h1 - h0) / abs(h0) < 1e-6

    def test_elliptical_orbit_energy(self):
        # Elliptical-ish: x=1, v_y smaller → less circular
        y0 = [1.0, 0.0, 0.0, 0.7]
        e0 = specific_energy(y0, MU)
        assert e0 < 0  # still bound for mu=1
        traj = integrate_orbit(y0, 0.0, 10.0, 1e-3, MU)
        e1 = specific_energy(traj[-1], MU)
        assert abs(e1 - e0) / abs(e0) < 5e-5

    def test_partial_final_step(self):
        # t1-t0 not multiple of dt
        traj = integrate_orbit(Y0, 0.0, 0.123456, 0.01, MU)
        assert len(traj) >= 2
        # total time should effectively reach ~0.123456
        # we only check state length and energy stability over short time
        e0 = specific_energy(traj[0], MU)
        e1 = specific_energy(traj[-1], MU)
        assert abs(e1 - e0) < 1e-8
