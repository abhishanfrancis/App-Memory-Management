"""
adb_utils.py — Low-level Android Debug Bridge helpers.

Provides wrappers around `subprocess.run` for executing ADB commands,
checking device connectivity, fetching device info, and force-stopping apps.
"""

import os
import platform
import shutil
import subprocess
from typing import Dict, Optional

from config import ADB_TIMEOUT_SECONDS

# On Windows, suppress the CMD flash window that appears with each subprocess call.
_CREATION_FLAGS = (
    subprocess.CREATE_NO_WINDOW
    if platform.system() == "Windows"
    else 0
)


def _find_adb() -> str:
    """Locate the adb executable.

    Checks (in order):
      1. Already on PATH (shutil.which)
      2. Common Windows install locations
    Returns the full path to adb, or just "adb" as fallback.
    """
    found = shutil.which("adb")
    if found:
        return found

    # Check known install locations on Windows
    if platform.system() == "Windows":
        candidates = [
            os.path.join(os.environ.get("LOCALAPPDATA", ""), "Android", "platform-tools", "adb.exe"),
            os.path.join(os.environ.get("USERPROFILE", ""), "Android", "platform-tools", "adb.exe"),
            os.path.join(os.environ.get("PROGRAMFILES", ""), "Android", "platform-tools", "adb.exe"),
            os.path.join(os.environ.get("LOCALAPPDATA", ""), "Android", "Sdk", "platform-tools", "adb.exe"),
            os.path.join(os.environ.get("USERPROFILE", ""), "AppData", "Local", "Android", "Sdk", "platform-tools", "adb.exe"),
        ]
        for path in candidates:
            if path and os.path.isfile(path):
                return path

    return "adb"  # fallback — will raise FileNotFoundError if truly missing


# Resolve once at import time
_ADB = _find_adb()


# ── Core runners ─────────────────────────────────────────────────────

def run_adb_host(args: list[str]) -> str:
    """Run an ADB command that does NOT go through the device shell.

    Examples:
        run_adb_host(["devices"])
        run_adb_host(["start-server"])
    """
    try:
        result = subprocess.run(
            [_ADB] + args,
            capture_output=True,
            text=True,
            timeout=ADB_TIMEOUT_SECONDS,
            creationflags=_CREATION_FLAGS,
        )
        if result.returncode != 0 and result.stderr.strip():
            raise RuntimeError(f"ADB error: {result.stderr.strip()}")
        return result.stdout
    except FileNotFoundError:
        raise RuntimeError(
            "ADB not found. Install Android Platform Tools and add to PATH."
        )
    except subprocess.TimeoutExpired:
        raise RuntimeError("ADB host command timed out.")


def run_adb(command: str) -> str:
    """Run an ADB *shell* command and return its stdout.

    The *command* string is split on whitespace and passed as:
        adb shell <token1> <token2> …

    Raises RuntimeError on failure, timeout, or if ADB is not installed.
    """
    try:
        result = subprocess.run(
            [_ADB, "shell"] + command.split(),
            capture_output=True,
            text=True,
            timeout=ADB_TIMEOUT_SECONDS,
            creationflags=_CREATION_FLAGS,
        )
        if result.returncode != 0 and result.stderr.strip():
            raise RuntimeError(f"ADB shell error: {result.stderr.strip()}")
        return result.stdout
    except FileNotFoundError:
        raise RuntimeError(
            "ADB not found. Install Android Platform Tools and add to PATH."
        )
    except subprocess.TimeoutExpired:
        raise RuntimeError("ADB shell command timed out.")


# ── Device connectivity ──────────────────────────────────────────────

def is_device_connected() -> bool:
    """Return True if at least one device is attached and authorised."""
    try:
        output = run_adb_host(["devices"])
    except RuntimeError:
        return False
    # Each connected device line looks like:  <serial>\tdevice
    lines = output.strip().splitlines()[1:]  # skip header
    return any("\tdevice" in line for line in lines)


def get_device_info() -> Dict[str, str]:
    """Return a dict with model name and Android version from the device."""
    info: Dict[str, str] = {}
    try:
        info["model"] = run_adb("getprop ro.product.model").strip() or "Unknown"
    except RuntimeError:
        info["model"] = "Unknown"
    try:
        info["android_version"] = run_adb("getprop ro.build.version.release").strip() or "Unknown"
    except RuntimeError:
        info["android_version"] = "Unknown"
    return info


# ── App control ──────────────────────────────────────────────────────

def force_stop_app(package: str) -> bool:
    """Force-stop a single package. Fast single-call version."""
    try:
        run_adb(f"am force-stop {package}")
        return True
    except RuntimeError:
        return False


def force_stop_batch(packages: list[str]) -> dict[str, bool]:
    """Force-stop many packages in one ADB shell call.

    Concatenates all force-stop commands with ';' so they execute
    inside a single adb shell invocation — much faster than spawning
    one subprocess per package.

    Returns {package_name: success_bool}.
    """
    if not packages:
        return {}

    # Build a single shell line: am force-stop pkg1; am force-stop pkg2; …
    cmds = "; ".join(f"am force-stop {p}" for p in packages)
    try:
        result = subprocess.run(
            [_ADB, "shell", cmds],
            capture_output=True,
            text=True,
            timeout=max(ADB_TIMEOUT_SECONDS, len(packages) * 0.5 + 5),
            creationflags=_CREATION_FLAGS,
        )
        if result.returncode != 0:
            # Batch call failed — fall back to individual calls
            results = {}
            for p in packages:
                results[p] = force_stop_app(p)
            return results
        # Check stderr for per-package errors
        stderr_lower = (result.stderr or "").lower()
        return {
            p: p not in stderr_lower
            for p in packages
        }
    except (subprocess.TimeoutExpired, FileNotFoundError, RuntimeError):
        # Fallback: try individually
        results = {}
        for p in packages:
            results[p] = force_stop_app(p)
        return results
