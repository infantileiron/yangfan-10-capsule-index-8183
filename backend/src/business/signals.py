"""Readings collected by the checkout bench during its 20-cycle test."""

from dataclasses import dataclass


@dataclass(frozen=True)
class Signal:
    key: str
    label: str
    unit: str
    low: float
    high: float
    resolution: float
    review: str


SIGNALS = (
    Signal("cycle_p90", "出货间隔 P90", "s", 0.1, 60, 0.04, "核对出货间隔记录"),
    Signal("index_error", "停位偏差", "mm", 0, 30, 0.02, "复核停位标记与导槽"),
    Signal("current", "转盘电流 P50", "A", 0.05, 10, 0.012, "复核出货盘传动与电流"),
    Signal("vibration", "壳体振动 RMS", "mm/s", 0, 60, 0.05, "复测壳体振动及安装状态"),
    Signal("retries", "重复推送", "次", 0, 20, 1, "复数推送循环并核对盘孔对准"),
)
FORMATS = ("48", "65")
COHORTS = ("参照", "留出", "待检")
