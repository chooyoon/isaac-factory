"""Small numeric helpers for transform validation.

Pure-math (no numpy) so this module imports the same way in conda env
(Python 3.10) and Isaac Sim Kit Python (3.11).
"""

from __future__ import annotations

import math
from typing import Sequence


def quaternion_magnitude(values: Sequence[float]) -> float:
    """Magnitude of a quaternion ``(w, x, y, z)``.

    Returns ``nan`` if the input length is not 4 or any component is non-finite.
    """
    if len(values) != 4:
        return float("nan")
    if any(not math.isfinite(v) for v in values):
        return float("nan")
    w, x, y, z = values
    return math.sqrt(w * w + x * x + y * y + z * z)


def matrix_rotation_orthogonality_error(values: Sequence[float]) -> float:
    """Frobenius norm of ``Rᵀ R − I`` for the upper-left 3×3 of a 16-element
    row-major matrix.

    Returns ``nan`` if the input length is not 16 or any component is non-finite.
    Zero indicates a perfectly orthogonal rotation submatrix.
    """
    if len(values) != 16:
        return float("nan")
    if any(not math.isfinite(v) for v in values):
        return float("nan")
    # Row-major: m[row][col] = values[row*4 + col]; rotation is upper-left 3x3.
    r = (
        (values[0], values[1], values[2]),
        (values[4], values[5], values[6]),
        (values[8], values[9], values[10]),
    )
    err_sq = 0.0
    for i in range(3):
        for j in range(3):
            # (RᵀR)[i,j] = Σ_k R[k,i] * R[k,j]
            dot = r[0][i] * r[0][j] + r[1][i] * r[1][j] + r[2][i] * r[2][j]
            delta = dot - (1.0 if i == j else 0.0)
            err_sq += delta * delta
    return math.sqrt(err_sq)


def vec3_magnitude(values: Sequence[float]) -> float:
    """Euclidean norm of a 3-vector. ``nan`` if length != 3 or non-finite."""
    if len(values) != 3:
        return float("nan")
    if any(not math.isfinite(v) for v in values):
        return float("nan")
    x, y, z = values
    return math.sqrt(x * x + y * y + z * z)


def vec3_distance(a: Sequence[float], b: Sequence[float]) -> float:
    """Euclidean distance between two 3-vectors. ``nan`` on bad inputs."""
    if len(a) != 3 or len(b) != 3:
        return float("nan")
    dx = a[0] - b[0]
    dy = a[1] - b[1]
    dz = a[2] - b[2]
    if not (math.isfinite(dx) and math.isfinite(dy) and math.isfinite(dz)):
        return float("nan")
    return math.sqrt(dx * dx + dy * dy + dz * dz)


def quaternion_angle_delta(
    q_a: Sequence[float], q_b: Sequence[float],
) -> float:
    """Geodesic angle (radians) between two quaternions (w, x, y, z).

    Treats `q` and `-q` as the same orientation (uses |dot|). Returns
    ``nan`` if either input is malformed or non-finite. Numerically safe:
    dot is clamped to ``[0.0, 1.0]`` before ``acos``.
    """
    if len(q_a) != 4 or len(q_b) != 4:
        return float("nan")
    if any(not math.isfinite(v) for v in q_a) or any(not math.isfinite(v) for v in q_b):
        return float("nan")
    dot = (q_a[0] * q_b[0] + q_a[1] * q_b[1]
           + q_a[2] * q_b[2] + q_a[3] * q_b[3])
    dot = min(1.0, max(0.0, abs(dot)))
    return 2.0 * math.acos(dot)
