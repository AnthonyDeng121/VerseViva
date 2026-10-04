import pytest

from server.models.song import PitchPoint
from server.services.difference import cents_between, interpolate_pitch


def make_point(time_seconds: float, midi: float, confidence: float = 0.9) -> PitchPoint:
    return PitchPoint(
        time_seconds=time_seconds,
        frequency_hz=440 * 2 ** ((midi - 69) / 12),
        midi=midi,
        confidence=confidence,
    )


def test_cents_between_preserves_high_and_low_direction() -> None:
    assert cents_between(60, 60.5) == 50
    assert cents_between(60, 59) == -100


def test_interpolate_pitch_returns_reference_at_requested_time() -> None:
    result = interpolate_pitch([make_point(1.0, 60), make_point(1.1, 61, 0.8)], 1.05)

    assert result is not None
    assert result.time_seconds == 1.05
    assert result.midi == pytest.approx(60.5)
    assert result.confidence == 0.8


def test_interpolate_pitch_does_not_bridge_silence_or_extrapolate() -> None:
    points = [make_point(1.0, 60), make_point(1.3, 62)]

    assert interpolate_pitch(points, 1.15) is None
    assert interpolate_pitch(points, 0.9) is None
    assert interpolate_pitch(points, 1.4) is None
