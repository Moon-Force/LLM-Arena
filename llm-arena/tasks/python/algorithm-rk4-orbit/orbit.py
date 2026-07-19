"""RK4 integrator for planar two-body orbit (SciCode-style scientific coding)."""

from __future__ import annotations


def rk4_step(y: list[float], t: float, dt: float, mu: float) -> list[float]:
    """Advance state y=[x,y,vx,vy] by one RK4 step. Do not mutate y."""
    raise NotImplementedError("Implement rk4_step")


def integrate_orbit(
    y0: list[float],
    t0: float,
    t1: float,
    dt: float,
    mu: float,
) -> list[list[float]]:
    """Integrate orbit from t0 to t1; return trajectory including start and end."""
    raise NotImplementedError("Implement integrate_orbit")


def specific_energy(y: list[float], mu: float) -> float:
    """E = |v|^2 / 2 - mu / |r|."""
    raise NotImplementedError("Implement specific_energy")


def specific_angular_momentum_z(y: list[float]) -> float:
    """hz = x*vy - y*vx."""
    raise NotImplementedError("Implement specific_angular_momentum_z")
