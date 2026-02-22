"""
memory_reader.py — Extract system-wide memory statistics from an Android device.

Two data sources are supported:
  • `dumpsys meminfo`   — richer (includes used/free/lost), ~2-5 s
  • `cat /proc/meminfo` — faster (~50 ms), kernel-level totals only
"""

import re
from dataclasses import dataclass, field
from datetime import datetime

from modules.adb_utils import run_adb


# ── Data model ───────────────────────────────────────────────────────

@dataclass
class MemoryInfo:
    """Snapshot of system-wide RAM statistics (all values in KB)."""
    total_kb: int = 0
    used_kb: int = 0
    free_kb: int = 0
    lost_kb: int = 0
    status: str = "normal"        # "normal" | "low" | "critical"
    timestamp: datetime = field(default_factory=datetime.now)


# ── Regex patterns for `dumpsys meminfo` ─────────────────────────────

_RE_TOTAL = re.compile(r"Total RAM:\s+([\d,]+)\s*K", re.IGNORECASE)
_RE_USED  = re.compile(r"Used RAM:\s+([\d,]+)\s*K",  re.IGNORECASE)
_RE_FREE  = re.compile(r"Free RAM:\s+([\d,]+)\s*K",  re.IGNORECASE)
_RE_LOST  = re.compile(r"Lost RAM:\s+([\d,]+)\s*K",  re.IGNORECASE)
_RE_STATUS = re.compile(r"Total RAM:.*\(status\s+(\w+)\)", re.IGNORECASE)

# ── Regex patterns for `/proc/meminfo` ───────────────────────────────

_RE_MEM_TOTAL     = re.compile(r"MemTotal:\s+(\d+)\s+kB", re.IGNORECASE)
_RE_MEM_FREE      = re.compile(r"MemFree:\s+(\d+)\s+kB",  re.IGNORECASE)
_RE_MEM_AVAILABLE = re.compile(r"MemAvailable:\s+(\d+)\s+kB", re.IGNORECASE)


def _parse_kb(text: str) -> int:
    """Strip commas and convert a string like '3,764,392' to int."""
    return int(text.replace(",", ""))


# ── Public API ───────────────────────────────────────────────────────

def get_system_memory() -> MemoryInfo:
    """Parse `adb shell dumpsys meminfo` and return a MemoryInfo snapshot.

    Falls back to `/proc/meminfo` if the dumpsys output cannot be parsed.
    """
    raw = run_adb("dumpsys meminfo")

    total_m = _RE_TOTAL.search(raw)
    used_m  = _RE_USED.search(raw)
    free_m  = _RE_FREE.search(raw)
    lost_m  = _RE_LOST.search(raw)
    status_m = _RE_STATUS.search(raw)

    # If we got the main fields, use them
    if total_m and used_m and free_m:
        return MemoryInfo(
            total_kb=_parse_kb(total_m.group(1)),
            used_kb=_parse_kb(used_m.group(1)),
            free_kb=_parse_kb(free_m.group(1)),
            lost_kb=_parse_kb(lost_m.group(1)) if lost_m else 0,
            status=status_m.group(1).lower() if status_m else "normal",
            timestamp=datetime.now(),
        )

    # Fallback: try /proc/meminfo
    return get_proc_meminfo()


def get_proc_meminfo() -> MemoryInfo:
    """Parse `cat /proc/meminfo` for a lightweight memory snapshot.

    Only Total and Free are reliably present; Used is calculated.
    """
    raw = run_adb("cat /proc/meminfo")

    total_m = _RE_MEM_TOTAL.search(raw)
    free_m  = _RE_MEM_FREE.search(raw)
    avail_m = _RE_MEM_AVAILABLE.search(raw)

    total_kb = int(total_m.group(1)) if total_m else 0
    free_kb  = int(avail_m.group(1)) if avail_m else (int(free_m.group(1)) if free_m else 0)
    used_kb  = total_kb - free_kb

    return MemoryInfo(
        total_kb=total_kb,
        used_kb=used_kb,
        free_kb=free_kb,
        lost_kb=0,
        status="normal",
        timestamp=datetime.now(),
    )
