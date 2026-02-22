"""
smart_manager.py — Adaptive memory-management decision engine.

Analyses current memory utilisation and per-process data to produce:
  • A system-level health verdict (critical / warning / healthy)
  • A ranked list of kill-candidates (background & cached apps)
  • An estimated MB that would be freed by killing all candidates

This module is pure logic — it never calls ADB directly.
"""

from typing import List, Tuple

from config import (
    KILL_BLOCKLIST,
    MIN_KILL_SCORE,
    THRESHOLD_CRITICAL,
    THRESHOLD_WARNING,
)
from modules.memory_reader import MemoryInfo
from modules.process_reader import ProcessInfo


# ── System-level analysis ────────────────────────────────────────────

def calculate_usage_percent(memory: MemoryInfo) -> float:
    """Return RAM usage as a percentage (0-100)."""
    if memory.total_kb == 0:
        return 0.0
    return (memory.used_kb / memory.total_kb) * 100


def get_system_recommendation(usage_pct: float) -> Tuple[str, str, str]:
    """Classify current memory pressure.

    Returns:
        (severity, title, detail)

        severity — "critical" | "warning" | "healthy"
        title    — short human-readable heading
        detail   — longer explanation / suggestion
    """
    if usage_pct >= THRESHOLD_CRITICAL:
        return (
            "critical",
            "High Memory Pressure",
            f"RAM usage is at {usage_pct:.1f} %. "
            "Recommend killing low-priority background apps immediately "
            "to prevent system slowdown and app crashes.",
        )
    if usage_pct >= THRESHOLD_WARNING:
        return (
            "warning",
            "Moderate Memory Usage",
            f"RAM usage is at {usage_pct:.1f} %. "
            "Consider closing unused background apps to keep the device responsive.",
        )
    return (
        "healthy",
        "Memory Healthy",
        f"RAM usage is at {usage_pct:.1f} %. "
        "The device has adequate free memory. No action required.",
    )


# ── Per-process scoring ─────────────────────────────────────────────

def score_process(proc: ProcessInfo) -> int:
    """Return the kill-priority score already stored on the ProcessInfo.

    Provided for external callers that receive a single process object.
    """
    return proc.kill_score


# ── Kill-candidate selection ─────────────────────────────────────────

def get_kill_candidates(
    processes: List[ProcessInfo],
    memory: MemoryInfo,
) -> List[ProcessInfo]:
    """Return processes that are safe to force-stop, ordered by PSS descending.

    Criteria:
      • kill_score >= MIN_KILL_SCORE  (background, cached, service-B …)
      • package not in KILL_BLOCKLIST  (never kill system-critical packages)
    """
    candidates = [
        p for p in processes
        if p.kill_score >= MIN_KILL_SCORE
        and p.package_name not in KILL_BLOCKLIST
    ]
    # Highest memory hog first → will free the most RAM if killed
    candidates.sort(key=lambda p: p.pss_kb, reverse=True)
    return candidates


def estimate_freed_mb(candidates: List[ProcessInfo]) -> float:
    """Estimate how many MB would be freed by killing all candidates."""
    return round(sum(p.pss_kb for p in candidates) / 1024, 1)


# ── Comparison helper (for presentation) ─────────────────────────────

def android_vs_model_comparison() -> list[dict]:
    """Return a comparison table: stock Android LMK vs our smart model.

    Useful for the "Innovation" slide in the presentation.
    """
    return [
        {
            "Aspect": "Kill Strategy",
            "Stock Android (LMK)": "Kills lowest OOM-adj process blindly",
            "Our Smart Model": "Ranks by PSS + priority + user-recency",
        },
        {
            "Aspect": "User Awareness",
            "Stock Android (LMK)": "No user notification",
            "Our Smart Model": "Dashboard shows candidates before action",
        },
        {
            "Aspect": "Adaptiveness",
            "Stock Android (LMK)": "Static OOM thresholds",
            "Our Smart Model": "Threshold-aware recommendations (60%/80%)",
        },
        {
            "Aspect": "Visibility",
            "Stock Android (LMK)": "Hidden kernel process",
            "Our Smart Model": "Real-time GUI with history & gauges",
        },
        {
            "Aspect": "Control",
            "Stock Android (LMK)": "Fully automatic, no user choice",
            "Our Smart Model": "User can review & selectively kill",
        },
    ]
