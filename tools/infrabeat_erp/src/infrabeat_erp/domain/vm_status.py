"""Domain model: VM status snapshot (Sprint 1 Task 4, spec C2)."""
from __future__ import annotations

from dataclasses import dataclass
from datetime import datetime, timezone
from typing import Optional


@dataclass
class VmStatus:
    """Immutable snapshot of one VM's state at a point in time.

    Task 4 MVP fields. Additional fields (services_ok, site_up, mcp_ok,
    disk_usage_pct) added in Sprint 2/3 per spec F1 visual design.
    """

    name: str
    host: str
    timestamp: datetime
    reachable: bool

    branch: Optional[str] = None
    commit_short: Optional[str] = None
    last_commit_age_seconds: Optional[int] = None
    error: Optional[str] = None

    def age_seconds(self, now: Optional[datetime] = None) -> float:
        n = now if now is not None else datetime.now(timezone.utc)
        return (n - self.timestamp).total_seconds()

    def is_stale(self, max_age_seconds: int = 30) -> bool:
        return self.age_seconds() > max_age_seconds
