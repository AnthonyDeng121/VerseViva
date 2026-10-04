import math

from server.models.song import PitchPoint


def cents_between(reference_midi: float, observed_midi: float) -> float:
    """Return the signed distance from the reference pitch in cents."""

    return (observed_midi - reference_midi) * 100.0


def interpolate_pitch(
    points: list[PitchPoint],
    time_seconds: float,
    *,
    maximum_gap_seconds: float = 0.1,
) -> PitchPoint | None:
    """Interpolate a reference pitch without bridging an actual silent gap."""

    outside_range = (
        not points
        or time_seconds < points[0].time_seconds
        or time_seconds > points[-1].time_seconds
    )
    if outside_range:
        return None

    low = 0
    high = len(points) - 1
    while low <= high:
        middle = (low + high) // 2
        point = points[middle]
        if point.time_seconds < time_seconds:
            low = middle + 1
        elif point.time_seconds > time_seconds:
            high = middle - 1
        else:
            return point

    right = points[low]
    left = points[low - 1]
    interval = right.time_seconds - left.time_seconds
    if interval <= 0 or interval > maximum_gap_seconds + 1e-9:
        return None

    fraction = (time_seconds - left.time_seconds) / interval
    midi = left.midi + (right.midi - left.midi) * fraction
    confidence = min(left.confidence, right.confidence)
    return PitchPoint(
        time_seconds=time_seconds,
        frequency_hz=440.0 * math.pow(2.0, (midi - 69.0) / 12.0),
        midi=midi,
        confidence=confidence,
    )
