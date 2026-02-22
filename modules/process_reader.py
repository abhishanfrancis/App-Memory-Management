"""
process_reader.py — Extract per-app memory and process priority information.

Combines data from two ADB sources:
  • `dumpsys meminfo`             → per-process PSS (KB)
  • `dumpsys activity processes`  → OOM adjustment level (fore/vis/bak/cch…)
"""

import re
from dataclasses import dataclass
from typing import Dict, List

from config import OOM_DEFAULT_LABEL, OOM_DEFAULT_SCORE, OOM_PRIORITY
from modules.adb_utils import run_adb


# ── Data model ───────────────────────────────────────────────────────

@dataclass
class ProcessInfo:
    """Information about a single running Android process."""
    pid: int
    package_name: str
    pss_kb: int
    oom_adj: str            # short code, e.g. "fore", "bak", "cch"
    oom_label: str          # human-readable, e.g. "Foreground"
    kill_score: int         # 0-5; higher = safer to kill
    user: str = ""

    @property
    def pss_mb(self) -> float:
        return round(self.pss_kb / 1024, 1)


# ── Regex ────────────────────────────────────────────────────────────

# Matches lines like:   248,671K: com.google.android.gms (pid 1234 / activities)
# Only matches lines that contain "(pid" — excludes category/OOM-adjustment totals.
_RE_PSS_LINE = re.compile(
    r"^\s+([\d,]+)\s*K:\s+(\S+)\s+\(pid\s+(\d+)"
    , re.MULTILINE
)

# Section header that starts the per-process block
_RE_SECTION_START = re.compile(r"Total PSS by process:", re.IGNORECASE)
# Next section header (stop parsing here)
_RE_SECTION_END = re.compile(r"Total PSS by OOM adjustment:", re.IGNORECASE)

# Matches lines from `dumpsys activity processes` on Android 10-15:
#   Android <15:  Proc #42: fore  T/A/FGS  trm: 0 3456:com.whatsapp/u0a123 (service)
#   Android 15:   Proc # 0: fg     T/A/TOP  LCMNFUA  t: 0 9993:com.android.settings/1000 (top-activity)
#                 PERS #98: sys    F/ /PER  LCMNFUA  t: 0 2052:system/1000 (fixed)
_RE_PROC_LINE = re.compile(
    r"(?:Proc|PERS)\s+#\s*\d+:\s+(\w+)\s+\S+\s+\S+\s+\S*\s*(?:trm|t):\s+\d+\s+(\d+):(\S+?)(?:/(\S+))?\s+\((.+?)\)"
    , re.MULTILINE
)


def _parse_kb(text: str) -> int:
    return int(text.replace(",", ""))


def _oom_info(code: str):
    """Return (label, score) for an OOM adjustment code."""
    entry = OOM_PRIORITY.get(code)
    if entry:
        return entry["label"], entry["score"]
    return OOM_DEFAULT_LABEL, OOM_DEFAULT_SCORE


# ── Public API ───────────────────────────────────────────────────────

def _get_pss_map() -> Dict[str, tuple]:
    """Parse `dumpsys meminfo` → dict mapping package → (pss_kb, pid).

    Only parses the 'Total PSS by process' section, skipping category and
    OOM-adjustment sections that would pollute results.
    """
    raw = run_adb("dumpsys meminfo")

    # Extract only the "Total PSS by process:" section
    start_m = _RE_SECTION_START.search(raw)
    end_m = _RE_SECTION_END.search(raw)
    if start_m and end_m:
        section = raw[start_m.end():end_m.start()]
    elif start_m:
        section = raw[start_m.end():]
    else:
        section = raw   # fallback: parse everything

    pss_map: Dict[str, tuple] = {}
    for m in _RE_PSS_LINE.finditer(section):
        pss_kb = _parse_kb(m.group(1))
        package = m.group(2)
        pid = int(m.group(3))
        # Keep the first (largest) entry per package
        if package not in pss_map:
            pss_map[package] = (pss_kb, pid)
    return pss_map


def _get_oom_map() -> Dict[str, tuple]:
    """Parse `dumpsys activity processes` → dict mapping package → (oom_code, pid, user)."""
    try:
        raw = run_adb("dumpsys activity processes")
    except RuntimeError:
        return {}
    oom_map: Dict[str, tuple] = {}
    for m in _RE_PROC_LINE.finditer(raw):
        oom_code = m.group(1)   # e.g. "fore", "bak"
        pid = int(m.group(2))
        package = m.group(3)
        user = m.group(4) or ""
        oom_map[package] = (oom_code, pid, user)
    return oom_map


def get_running_processes() -> List[ProcessInfo]:
    """Return a list of ProcessInfo for every running app, sorted by PSS descending."""
    pss_map = _get_pss_map()
    oom_map = _get_oom_map()

    processes: List[ProcessInfo] = []
    for package, (pss_kb, pid_pss) in pss_map.items():
        oom_code = "bak"   # default if not found in activity dump
        pid = pid_pss
        user = ""
        if package in oom_map:
            oom_code, pid_oom, user = oom_map[package]
            pid = pid_oom or pid_pss

        label, score = _oom_info(oom_code)

        processes.append(ProcessInfo(
            pid=pid,
            package_name=package,
            pss_kb=pss_kb,
            oom_adj=oom_code,
            oom_label=label,
            kill_score=score,
            user=user,
        ))

    # Sort: highest memory first
    processes.sort(key=lambda p: p.pss_kb, reverse=True)
    return processes
