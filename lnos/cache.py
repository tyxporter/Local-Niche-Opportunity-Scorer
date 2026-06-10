"""Disk cache + freshness metadata for the data layer (§4.0, §4.3).

Every external fetch (Census, Trends, FINRA, FRED) flows through here so that:
  * results are cached on disk keyed by source + params,
  * each result carries freshness metadata (what date the data represents,
    when we fetched it, whether it is stale),
  * an unavailable / thin source yields an explicit `SignalResult` with
    `available=False` and a plain-language note — NEVER a fabricated value
    (§4.3).

Nothing here is a source of truth for methodology (D6); it only transports
raw observed values plus provenance to the scorer / brief layers.
"""

from __future__ import annotations

import hashlib
import json
import os
import time
from dataclasses import dataclass, field, asdict
from datetime import date, datetime, timezone
from pathlib import Path
from typing import Any, Optional


def cache_dir() -> Path:
    """Resolve the cache directory (env override or ./.cache)."""
    d = os.environ.get("LNOS_CACHE_DIR") or os.path.join(os.getcwd(), ".cache")
    p = Path(d)
    p.mkdir(parents=True, exist_ok=True)
    return p


# --- Freshness + result envelopes -------------------------------------------
@dataclass
class FreshnessMeta:
    """Provenance for a single observed value."""

    source: str                      # e.g. "census_acs", "fred", "google_trends"
    as_of: Optional[str] = None      # the period the DATA represents (ISO date/yr)
    fetched_at: Optional[str] = None # when WE retrieved it (ISO 8601 UTC)
    ttl_days: Optional[int] = None   # how long this source stays "fresh"
    is_stale: bool = False           # True -> caller must narrow the claim (§4.3)
    lagged: bool = False             # True for inherently lagged sources (ACS)
    note: str = ""                   # plain-language provenance / caveat

    def stamp_now(self) -> "FreshnessMeta":
        self.fetched_at = datetime.now(timezone.utc).isoformat(timespec="seconds")
        return self


@dataclass
class SignalResult:
    """A raw observed value plus provenance.

    IMPORTANT: this carries the *raw* observation only. Normalization and the
    combination into Wealth/Demand/Saturation/Opp is §2.1 methodology and lives
    in scoring.py — never here.
    """

    source: str
    available: bool
    value: Any = None                # raw observed value (None if unavailable)
    unit: Optional[str] = None       # e.g. "USD", "index_0_100", "count", "pct"
    meta: FreshnessMeta = field(default_factory=lambda: FreshnessMeta(source="?"))
    note: str = ""                   # plain-language status, esp. when unavailable

    @classmethod
    def unavailable(cls, source: str, note: str, **meta_kw) -> "SignalResult":
        """Build an explicit 'no data' result — the only honest empty state."""
        return cls(
            source=source,
            available=False,
            value=None,
            meta=FreshnessMeta(source=source, note=note, **meta_kw),
            note=note,
        )


# --- Disk cache -------------------------------------------------------------
def _key_path(source: str, params: dict) -> Path:
    blob = json.dumps({"source": source, "params": params}, sort_keys=True)
    digest = hashlib.sha1(blob.encode("utf-8")).hexdigest()[:16]
    return cache_dir() / f"{source}__{digest}.json"


def read_cache(source: str, params: dict, max_age_days: Optional[int]) -> Optional[dict]:
    """Return cached payload if present and within max_age_days, else None."""
    path = _key_path(source, params)
    if not path.exists():
        return None
    try:
        raw = json.loads(path.read_text())
    except (json.JSONDecodeError, OSError):
        return None
    if max_age_days is not None:
        fetched = raw.get("_fetched_epoch")
        if fetched is None or (time.time() - fetched) > max_age_days * 86400:
            return None
    return raw.get("payload")


def write_cache(source: str, params: dict, payload: dict) -> None:
    """Persist a payload with a fetch timestamp."""
    path = _key_path(source, params)
    record = {
        "_fetched_epoch": time.time(),
        "_fetched_at": datetime.now(timezone.utc).isoformat(timespec="seconds"),
        "payload": payload,
    }
    try:
        path.write_text(json.dumps(record, indent=2))
    except OSError:
        # Cache is best-effort; a write failure must never break a fetch.
        pass
