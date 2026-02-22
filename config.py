"""
Configuration constants for the Mobile OS Memory Management System.
"""

# ── Refresh & Timing ─────────────────────────────────────────────────
REFRESH_INTERVAL_MS = 30000         # Dashboard auto-refresh interval (milliseconds)
ADB_TIMEOUT_SECONDS = 10            # Max wait time for any ADB command
CACHE_TTL_SECONDS = 25              # How long to serve cached ADB data before re-fetching

# ── Memory Thresholds (percentage) ───────────────────────────────────
THRESHOLD_CRITICAL = 80             # >= 80 % → critical (red)
THRESHOLD_WARNING  = 60             # >= 60 % → warning  (yellow)
# Below 60 % → healthy (green)

# ── OOM Adjustment Labels ────────────────────────────────────────────
# Maps short codes from `dumpsys activity processes` to human-readable
# labels and numeric kill-priority scores.
# Higher score ⇒ safer to kill.
OOM_PRIORITY = {
    "fore":  {"label": "Foreground",  "score": 0},
    "fg":    {"label": "Foreground",  "score": 0},
    "vis":   {"label": "Visible",     "score": 1},
    "percep":{"label": "Perceptible", "score": 2},
    "prev":  {"label": "Previous",    "score": 3},
    "bak":   {"label": "Background",  "score": 4},
    "cch":   {"label": "Cached",      "score": 5},
    "svc":   {"label": "Service",     "score": 2},
    "svcb":  {"label": "Service-B",   "score": 3},
    "psvc":  {"label": "Persist-Svc", "score": 0},
    "home":  {"label": "Home",        "score": 1},
    "pers":  {"label": "Persistent",  "score": 0},
    "sys":   {"label": "System",      "score": 0},
}

# Default for unknown OOM codes
OOM_DEFAULT_LABEL = "Unknown"
OOM_DEFAULT_SCORE = 3

# ── Kill Blocklist ───────────────────────────────────────────────────
# These packages will NEVER be offered for force-stop.
KILL_BLOCKLIST = {
    "system",
    "system_server",
    "com.android.systemui",
    "com.android.launcher3",
    "com.google.android.launcher",
    "com.android.phone",
    "com.android.dialer",
    "com.android.providers.telephony",
    "com.android.providers.contacts",
    "com.android.settings",
    "com.android.inputmethod.latin",
    "android",
    "android.process.acore",
    "android.process.media",
}

# Minimum kill-priority score to be considered a candidate
MIN_KILL_SCORE = 3

# ── Demo Data Defaults ───────────────────────────────────────────────
DEMO_TOTAL_RAM_KB = 4 * 1024 * 1024       # 4 GB
DEMO_USED_RAM_MEAN_KB = 2.6 * 1024 * 1024 # ~2.6 GB average
DEMO_USED_RAM_STD_KB  = 0.3 * 1024 * 1024 # ±0.3 GB std-dev

DEMO_PACKAGES = [
    ("com.whatsapp",               "WhatsApp",       "bak",  180_000),
    ("com.instagram.android",      "Instagram",      "cch",  210_000),
    ("com.google.android.youtube", "YouTube",        "prev", 250_000),
    ("com.google.android.gms",     "Google Services","vis",   95_000),
    ("com.android.chrome",         "Chrome",         "cch",  310_000),
    ("com.spotify.music",          "Spotify",        "bak",  120_000),
    ("com.snapchat.android",       "Snapchat",       "cch",  175_000),
    ("com.facebook.katana",        "Facebook",       "cch",  260_000),
    ("com.twitter.android",        "Twitter/X",      "bak",  140_000),
    ("com.google.android.apps.maps","Google Maps",   "cch",  155_000),
    ("com.amazon.mShop.android",   "Amazon",         "cch",  130_000),
    ("com.android.vending",        "Play Store",     "prev",  85_000),
    ("com.google.android.gm",      "Gmail",          "bak",   70_000),
    ("com.android.systemui",       "System UI",      "pers",  65_000),
    ("system",                     "System",         "sys",   55_000),
]
