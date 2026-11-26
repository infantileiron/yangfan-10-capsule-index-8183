"""Hold out recent unlabeled reading sets and compare them with isolated samples."""

from dataclasses import dataclass

import numpy as np
from sklearn.ensemble import IsolationForest

from .signals import SIGNALS


def _matrix(rows: list[dict]) -> np.ndarray:
    return np.asarray([[row[signal.key] for signal in SIGNALS] for row in rows], dtype=float)


@dataclass(frozen=True)
class InterquartileReference:
    median: np.ndarray
    scale: np.ndarray

    @classmethod
    def from_measurements(cls, readings: np.ndarray) -> "InterquartileReference":
        lower, median, upper = np.quantile(readings, [0.25, 0.5, 0.75], axis=0)
        resolution = np.asarray([signal.resolution for signal in SIGNALS])
        return cls(median, np.maximum(upper - lower, resolution))

    def describe(self, reading: np.ndarray) -> tuple[str, str]:
        displacement = (reading - self.median) / self.scale
        order = sorted(range(len(SIGNALS)), key=lambda index: (-abs(displacement[index]), index))
        compare = []
        for index in order[:2]:
            signal = SIGNALS[index]
            actual = reading[index]
            typical = self.median[index]
            signed_offset = actual - typical
            compare.append(
                f"{signal.label} {actual:g} / {typical:g} {signal.unit}（{signed_offset:+.3g}）"
            )
        return "；".join(compare), SIGNALS[order[0]].review


@dataclass(frozen=True)
class Detector:
    estimator: IsolationForest
    reference: InterquartileReference
    threshold: float

    @classmethod
    def train(cls, train: list[dict], holdout: list[dict], diameter: str, quantile: float) -> "Detector":
        if len(train) < 30 or len(holdout) < 12:
            raise ValueError(f"{diameter} mm 口径至少需要 30 条参照与 12 条留出记录。")
        matrix = _matrix(train)
        if not np.any(np.ptp(matrix, axis=0)):
            raise ValueError(f"{diameter} mm 口径的参照读数全无变化，请检查采样。")
        estimator = IsolationForest(
            n_estimators=144, max_samples=min(128, len(train)), random_state=112510, n_jobs=1
        ).fit(matrix)
        holdout_scores = -100 * estimator.score_samples(_matrix(holdout))
        threshold = float(np.quantile(holdout_scores, quantile))
        return cls(estimator, InterquartileReference.from_measurements(matrix), threshold)

    def rank(self, candidates: list[dict]) -> list[dict]:
        matrix = _matrix(candidates)
        scores = -100 * self.estimator.score_samples(matrix)
        results = []
        for row, measurement, score in zip(candidates, matrix, scores):
            evidence, review = self.reference.describe(measurement)
            margin = float(score) - self.threshold
            results.append(
                {
                    "sample_id": row["sample_id"],
                    "cabinet": row["cabinet"],
                    "capsule_mm": f"{row['capsule_mm']} mm",
                    "score": round(float(score), 6),
                    "margin": round(margin, 6),
                    "evidence": evidence,
                    "decision": f"优先复检 · {review}" if margin > 0 else "例行抽检",
                }
            )
        return results
