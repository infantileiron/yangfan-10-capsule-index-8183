"""Generate a mixed unlabeled bench log and one shift's trial-segment readings."""

from random import Random

from .signals import FORMATS, SIGNALS


CENTERS = {"48": (1.62, 0.31, 0.39, 0.83, 0), "65": (2.34, 0.47, 0.63, 1.22, 0)}
DEVIATIONS = (0.082, 0.054, 0.037, 0.15)


def _readings(diameter: str, rng: Random, centered=False) -> dict:
    centers = CENTERS[diameter]
    if centered:
        return {signal.key: value for signal, value in zip(SIGNALS, centers)}
    friction = rng.gauss(0, 0.9)
    misalignment = rng.gauss(0, 0.85)
    variation = (
        0.13 * friction + 0.04 * misalignment,
        0.03 * friction + 0.07 * misalignment,
        0.055 * friction + 0.014 * misalignment,
        0.14 * friction + 0.08 * misalignment,
    )
    readings = [
        round(max(signal.low, center + shift + rng.gauss(0, deviation)), 3)
        for signal, center, shift, deviation in zip(SIGNALS, centers, variation, DEVIATIONS)
    ]
    readings.append(max(0, round((friction + misalignment - 0.6) * 0.7)))
    return {signal.key: value for signal, value in zip(SIGNALS, readings)}


def demo_rows() -> list[dict]:
    rng = Random(112510)
    rows = []
    for prefix, diameter in zip(("A", "B"), FORMATS):
        for cohort, stage, count in (("参照", "REF", 44), ("留出", "CHK", 24)):
            for i in range(count):
                if cohort == "留出":
                    # Deliberately leave eight cross-shift readings on fit
                    # cabinets; the line estimator must reject those and use
                    # twelve independent holdout cabinets.
                    cabinet = (
                        f"ZM-{prefix}{i % 8 + 1:02d}"
                        if i < 8
                        else f"ZM-{prefix}{21 + (i - 8) % 12:02d}"
                    )
                else:
                    cabinet = f"ZM-{prefix}{i % 12 + 1:02d}"
                rows.append(
                    {
                        "sample_id": f"ZM-{stage}{diameter}-{i + 1:02d}",
                        "cabinet": cabinet,
                        "capsule_mm": diameter,
                        "cohort": cohort,
                        **_readings(diameter, rng),
                    }
                )
        for i in range(1, 6):
            readings = _readings(diameter, rng, centered=(i == 1))
            if diameter == "48" and i == 3:
                readings.update(index_error=1.64, cycle_p90=2.31, retries=4)
            if diameter == "65" and i == 4:
                readings.update(current=1.86, vibration=2.86, cycle_p90=3.94, index_error=0.70, retries=3)
            rows.append(
                {
                    "sample_id": f"ZM-TR{diameter}-{i:02d}",
                    "cabinet": f"ZM-{prefix}{i + 13:02d}",
                    "capsule_mm": diameter,
                    "cohort": "待检",
                    **readings,
                }
            )
    return rows
