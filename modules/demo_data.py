"""
demo_data.py — Realistic fake data generator for demo / presentation mode.

Activated automatically when no Android device is connected via ADB.
Returns the same dataclass types as the real readers so the dashboard
code does not need any branching.
"""

import random
from datetime import datetime
from typing import Dict, List

from config import (
    DEMO_PACKAGES,
    DEMO_TOTAL_RAM_KB,
    DEMO_USED_RAM_MEAN_KB,
    DEMO_USED_RAM_STD_KB,
    OOM_PRIORITY,
    OOM_DEFAULT_LABEL,
    OOM_DEFAULT_SCORE,
)
from modules.memory_reader import MemoryInfo
from modules.process_reader import ProcessInfo


# ── Helpers ──────────────────────────────────────────────────────────

def _jitter(value: int, pct: float = 0.05) -> int:
    """Add ± pct random noise to a value."""
    delta = int(value * pct)
    return value + random.randint(-delta, delta)


def _oom_info(code: str):
    entry = OOM_PRIORITY.get(code)
    if entry:
        return entry["label"], entry["score"]
    return OOM_DEFAULT_LABEL, OOM_DEFAULT_SCORE


# ── Public API ───────────────────────────────────────────────────────

def get_fake_memory() -> MemoryInfo:
    """Return a realistic MemoryInfo snapshot with slight random variation."""
    total_kb = int(DEMO_TOTAL_RAM_KB)
    used_kb  = max(0, int(random.gauss(DEMO_USED_RAM_MEAN_KB, DEMO_USED_RAM_STD_KB)))
    used_kb  = min(used_kb, total_kb)            # clamp
    free_kb  = total_kb - used_kb

    usage_pct = (used_kb / total_kb) * 100
    if usage_pct >= 80:
        status = "critical"
    elif usage_pct >= 60:
        status = "low"
    else:
        status = "normal"

    return MemoryInfo(
        total_kb=total_kb,
        used_kb=used_kb,
        free_kb=free_kb,
        lost_kb=_jitter(150_000, 0.10),
        status=status,
        timestamp=datetime.now(),
    )


def get_fake_processes() -> List[ProcessInfo]:
    """Return a list of realistic ProcessInfo objects."""
    processes: List[ProcessInfo] = []

    for package, friendly_name, oom_code, base_pss in DEMO_PACKAGES:
        label, score = _oom_info(oom_code)
        processes.append(ProcessInfo(
            pid=random.randint(1000, 30000),
            package_name=package,
            pss_kb=_jitter(base_pss, 0.08),
            oom_adj=oom_code,
            oom_label=label,
            kill_score=score,
            user=f"u0_a{random.randint(10, 200)}",
        ))

    # Sort by PSS descending (like the real reader)
    processes.sort(key=lambda p: p.pss_kb, reverse=True)
    return processes


def get_fake_device_info() -> Dict[str, str]:
    """Return demo device metadata."""
    return {
        "model": "Pixel 7 (Demo)",
        "android_version": "14",
    }
