from __future__ import annotations

from dataclasses import dataclass, field

DEFAULT_WRITE_SCOPES = frozenset(
    {"contents", "packages", "id-token", "security-events", "pull-requests", "issues"}
)


@dataclass(frozen=True)
class Config:
    disabled: frozenset[str] = frozenset()
    write_scopes: frozenset[str] = DEFAULT_WRITE_SCOPES
    ignores: tuple = field(default_factory=tuple)
