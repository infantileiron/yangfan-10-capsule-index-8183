"""Validate and order the bench's candidate cabinets for manual reinspection."""

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


def analyze(rows: list[dict], parameter: float) -> dict:
    if not isfinite(parameter) or not 0.8 <= parameter <= 0.99:
        raise ValueError("复检线分位需填写 0.80 到 0.99 之间的数值。")
    groups = _partition(rows)
    results = []
    notes = []
    for diameter, group in groups.items():
        if not group["待检"]:
            continue
        detector = Detector.train(group["参照"], group["留出"], diameter, parameter)
        results.extend(detector.rank(group["待检"]))
        notes.append(
            f"{diameter} mm 使用 {len(group['参照'])} 条参照和 {len(group['留出'])} 条留出，"
            f"留出第 {parameter:.0%} 分位复检线为 {detector.threshold:.2f}。"
        )
    if not results:
        raise ValueError("请添加至少一台有量测结果的待检机台。")
    results.sort(key=lambda row: (-row["margin"], -row["score"], row["sample_id"]))
    urgent = sum(row["decision"].startswith("优先复检") for row in results)
    return {
        "summary": f"已筛查 {len(results)} 条试转，其中 {urgent} 条进入优先复检队列。",
        "metrics": [
            {"label": "待检记录", "value": len(results)},
            {"label": "优先复检", "value": urgent},
            {"label": "例行抽检", "value": len(results) - urgent},
            {"label": "比较口径", "value": len(notes)},
        ],
        "rows": results,
        "notes": notes + ["超线分差为正的机台排在前面。实测偏移用于选择人工复检工序，需现场确认原因。"],
    }
