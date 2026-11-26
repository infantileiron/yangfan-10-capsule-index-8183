"""Fit models and estimate cabinet-level review lines."""

from dataclasses import dataclass, field

import numpy as np
from sklearn.ensemble import IsolationForest

from .signals import SIGNALS


def _matrix(rows: list[dict]) -> np.ndarray:
    return np.asarray([[row[signal.key] for signal in SIGNALS] for row in rows], dtype=float)


def machine_level_scores(rows: list[dict], scores: np.ndarray) -> tuple[tuple[str, ...], np.ndarray]:
    """Return one equal-weight score per cabinet.

    A cabinet can contribute several trial readings, but the review line is a
    line over machines.  Averaging its anomaly scores gives that cabinet one
    vote in the empirical quantile.
    """
    grouped: dict[str, list[float]] = {}
    for row, score in zip(rows, scores):
        grouped.setdefault(str(row["cabinet"]), []).append(float(score))
    cabinets = tuple(sorted(grouped))
    values = np.asarray([float(np.mean(grouped[cabinet])) for cabinet in cabinets], dtype=float)
    return cabinets, values


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
    quantile: float | None = None
    fit_rows: int = 0
    fit_cabinets: tuple[str, ...] = ()
    calibration_rows: int = 0
    calibration_cabinets: tuple[str, ...] = ()
    excluded_same_cabinet_rows: int = 0
    cabinet_scores: dict[str, float] = field(default_factory=dict)
    credible: bool = True

    @classmethod
    def fit_model(cls, train: list[dict], diameter: str) -> "Detector":
        if len(train) < 30:
            raise ValueError(f"{diameter} mm 口径至少需要 30 条参照。")
        matrix = _matrix(train)
        if not np.any(np.ptp(matrix, axis=0)):
            raise ValueError(f"{diameter} mm 口径的参照读数全无变化，请检查采样。")
        estimator = IsolationForest(
            n_estimators=144, max_samples=min(128, len(train)), random_state=112510, n_jobs=1
        ).fit(matrix)
        cabinets = tuple(sorted({str(row["cabinet"]) for row in train}))
        return cls(
            estimator=estimator,
            reference=InterquartileReference.from_measurements(matrix),
            threshold=float("nan"),
            fit_rows=len(train),
            fit_cabinets=cabinets,
        )

    def calibrate(
        self, holdout: list[dict], diameter: str, quantile: float, *, minimum_cabinets: int = 12
    ) -> "Detector":
        if len(holdout) < 12:
            raise ValueError(f"{diameter} mm 口径至少需要 12 条留出记录。")
        fit_cabinets = set(self.fit_cabinets)
        unseen_holdout = [row for row in holdout if str(row["cabinet"]) not in fit_cabinets]
        excluded = len(holdout) - len(unseen_holdout)
        if not unseen_holdout:
            raise ValueError(
                f"{diameter} mm 口径缺少未参与参照拟合的留出机台，无法估计同口径复检线；"
                "请补充跨班且机台编号不与参照重合的留出读数。"
            )
        holdout_scores = -100 * self.estimator.score_samples(_matrix(unseen_holdout))
        cabinets, machine_scores = machine_level_scores(unseen_holdout, holdout_scores)
        threshold = float(np.quantile(machine_scores, quantile))
        cabinet_score_map = {
            cabinet: round(float(score), 6) for cabinet, score in zip(cabinets, machine_scores)
        }
        return Detector(
            estimator=self.estimator,
            reference=self.reference,
            threshold=threshold,
            quantile=quantile,
            fit_rows=self.fit_rows,
            fit_cabinets=self.fit_cabinets,
            calibration_rows=len(unseen_holdout),
            calibration_cabinets=cabinets,
            excluded_same_cabinet_rows=excluded,
            cabinet_scores=cabinet_score_map,
            # The existing domain minimum is 12 holdout readings.  Cabinet
            # count is reported separately; one successful disjoint-machine
            # calibration remains usable as a stale fallback until replaced.
            credible=True,
        )

    @classmethod
    def train(cls, train: list[dict], holdout: list[dict], diameter: str, quantile: float) -> "Detector":
        return cls.fit_model(train, diameter).calibrate(holdout, diameter, quantile)

    def with_line(
        self,
        threshold: float,
        *,
        quantile: float | None = None,
        calibration_rows: int = 0,
        calibration_cabinets: tuple[str, ...] | list[str] = (),
        excluded_same_cabinet_rows: int = 0,
        credible: bool = True,
        cabinet_scores: dict[str, float] | None = None,
    ) -> "Detector":
        cabinets = tuple(calibration_cabinets)
        return Detector(
            estimator=self.estimator,
            reference=self.reference,
            threshold=float(threshold),
            quantile=quantile if quantile is not None else self.quantile,
            fit_rows=self.fit_rows,
            fit_cabinets=self.fit_cabinets,
            calibration_rows=calibration_rows or self.calibration_rows,
            calibration_cabinets=cabinets or self.calibration_cabinets,
            excluded_same_cabinet_rows=excluded_same_cabinet_rows,
            cabinet_scores=cabinet_scores or self.cabinet_scores,
            credible=credible,
        )

    def for_quantile(self, quantile: float) -> "Detector":
        """Recompute a requested quantile from stored cabinet-level scores."""
        if not self.cabinet_scores:
            raise ValueError("缺少机台级异常度，无法按新的分位重算复检线。")
        values = np.asarray(list(self.cabinet_scores.values()), dtype=float)
        return self.with_line(float(np.quantile(values, quantile)), quantile=quantile)

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
