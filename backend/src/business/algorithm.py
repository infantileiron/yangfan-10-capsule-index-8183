"""Validate rows and order the bench's candidate cabinets for review."""

from math import isfinite

from .detector import Detector
from .signals import COHORTS, FORMATS, SIGNALS


def _partition(rows: list[dict]) -> dict:
    groups = {diameter: {key: [] for key in COHORTS} for diameter in FORMATS}
    seen = set()
    for row in rows:
        key = row["sample_id"]
        if key in seen:
            raise ValueError(f"试转编号 {key} 重复。")
        seen.add(key)
        size = row["capsule_mm"]
        cohort = row["cohort"]
        if size not in FORMATS or cohort not in COHORTS:
            raise ValueError(f"{key} 的胶囊口径或数据用途无法识别。")
        for signal in SIGNALS:
            value = row[signal.key]
            if not isfinite(value) or not signal.low <= value <= signal.high:
                raise ValueError(f"{key} 的{signal.label}超出量测范围。")
        if row["retries"] != int(row["retries"]):
            raise ValueError(f"{key} 的重复推送次数需要填写整数。")
        groups[size][cohort].append(row)
    return groups


def validate_rows(rows: list[dict]) -> dict:
    """Validate a complete source version and return its cohort partitions."""
    return _partition(rows)


def _version_scope(versions, diameter: str) -> dict:
    if not versions:
        return {}
    if isinstance(versions, str):
        return {"fit_version": versions, "threshold_version": versions, "inspection_version": versions}
    scope = versions.get(diameter, versions) if isinstance(versions, dict) else {}
    if isinstance(scope, str):
        return {"fit_version": scope, "threshold_version": scope, "inspection_version": scope}
    return dict(scope or {})


def _version_entry(diameter: str, parameter: float, detector: Detector, versions, line_info: dict) -> dict:
    scope = _version_scope(versions, diameter)

    def first(*keys, default=None):
        for key in keys:
            if key in scope and scope[key] is not None:
                return scope[key]
        return default

    inspection = first("inspection_version", "candidate_version", "pending_version", "dataset_id", "version")
    fit = first("fit_version", "fitting_version", "reference_version", default=inspection)
    threshold_version = first(
        "threshold_version", "line_version", "calibration_version", "holdout_version", default=inspection
    )
    entry = {
        "capsule_mm": diameter,
        "fit_version": fit,
        "threshold_version": threshold_version,
        "inspection_version": inspection,
        # Alias kept for API consumers that name the pending reading version
        # after the calculation's source dataset.
        "candidate_version": inspection,
        "quantile": parameter,
        "threshold": round(float(detector.threshold), 6) if isfinite(detector.threshold) else None,
        "fit_rows": detector.fit_rows,
        "fit_cabinets": len(detector.fit_cabinets),
        "threshold_rows": detector.calibration_rows,
        "threshold_cabinets": len(detector.calibration_cabinets),
        "excluded_same_cabinet_rows": detector.excluded_same_cabinet_rows,
        "credible": detector.credible,
        "calibration_id": first("calibration_id", "line_id"),
        "line_mode": first("line_mode", default=line_info.get("mode", "fitted_now")),
    }
    entry["version_note"] = (
        f"拟合 {_short(fit)}；估线 {_short(threshold_version)}；待检 {_short(inspection)}"
    )
    return entry


def _short(version) -> str:
    if not version:
        return "未注明版本"
    text = str(version)
    return text[:8] if len(text) > 8 else text


def analyze(
    rows: list[dict],
    parameter: float,
    versions: dict | str | None = None,
    detectors: dict[str, Detector] | None = None,
    line_info: dict[str, dict] | None = None,
) -> dict:
    if not isfinite(parameter) or not 0.8 <= parameter <= 0.99:
        raise ValueError("复检线分位需填写 0.80 到 0.99 之间的数值。")
    groups = _partition(rows)
    detectors = detectors or {}
    line_info = line_info or {}
    results = []
    notes = []
    source_versions = []
    for diameter, group in groups.items():
        if not group["待检"]:
            continue
        detector = detectors.get(diameter)
        if detector is None:
            detector = Detector.train(group["参照"], group["留出"], diameter, parameter)
        ranked = detector.rank(group["待检"])
        entry = _version_entry(diameter, parameter, detector, versions, line_info.get(diameter, {}))
        version_fields = {
            "fit_version": entry["fit_version"],
            "threshold_version": entry["threshold_version"],
            "inspection_version": entry["inspection_version"],
            "calibration_id": entry["calibration_id"],
            "line_mode": entry["line_mode"],
            "version_note": entry["version_note"],
        }
        for row in ranked:
            row.update(version_fields)
        results.extend(ranked)
        source_versions.append(entry)
        notes.append(
            f"{diameter} mm：拟合使用 {detector.fit_rows} 条参照（{len(detector.fit_cabinets)} 台机），"
            f"估线使用 {detector.calibration_rows} 条未参与拟合的留出读数"
            f"（{len(detector.calibration_cabinets)} 台机，已剔除 "
            f"{detector.excluded_same_cabinet_rows} 条同台重合读数），"
            f"留出机台异常度第 {parameter:.0%} 分位复检线为 {detector.threshold:.2f}。"
        )
        notes.append(
            f"{diameter} mm 版本追溯：拟合读数 {entry['fit_version'] or '未注明'}；"
            f"估线读数 {entry['threshold_version'] or '未注明'}；"
            f"待检读数 {entry['inspection_version'] or '未注明'}；"
            f"用线方式：{entry['line_mode']}。"
        )
    if not results:
        raise ValueError("请添加至少一台有量测结果的待检机台。")
    results.sort(key=lambda row: (-row["margin"], -row["score"], row["sample_id"]))
    urgent = sum(row["decision"].startswith("优先复检") for row in results)
    version_summary = "；".join(
        f"{item['capsule_mm']} mm（拟合 {_short(item['fit_version'])} / "
        f"估线 {_short(item['threshold_version'])} / 待检 {_short(item['inspection_version'])}）"
        for item in source_versions
    )
    return {
        "summary": f"已筛查 {len(results)} 条试转，其中 {urgent} 条进入优先复检队列。",
        "metrics": [
            {"label": "待检记录", "value": len(results)},
            {"label": "优先复检", "value": urgent},
            {"label": "例行抽检", "value": len(results) - urgent},
            {"label": "比较口径", "value": len(source_versions)},
        ],
        "rows": results,
        "notes": notes + [
            (f"各口径均按未参与拟合的机台估线，同台多测先合并为机台分数。版本：{version_summary}。"),
            "超线分差为正的机台排在前面。实测偏移用于选择人工复检工序，需现场确认原因。",
        ],
        "source_versions": source_versions,
        "reading_versions": source_versions,
        "data_versions": source_versions,
        "line_versions": source_versions,
        "versions": source_versions,
        "versioning": {"readings": source_versions, "sources": source_versions},
    }
