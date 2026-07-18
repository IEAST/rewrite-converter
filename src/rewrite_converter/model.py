from __future__ import annotations

from dataclasses import asdict, dataclass, field
from enum import Enum
from typing import Any


class Action(str, Enum):
    REDIRECT = "redirect"
    REJECT = "reject"
    SCRIPT_REQUEST = "script-request"
    SCRIPT_RESPONSE = "script-response"
    JSON_JQ_RESPONSE = "json-jq-response"


@dataclass
class RewriteRule:
    pattern: str
    action: Action
    tag: str = ""
    status: int | None = None
    target: str | None = None
    reject_type: str | None = None
    script: str | None = None
    expression: str | None = None
    requires_body: bool = False
    timeout: int = 30
    enabled: bool = True
    source_line: int | None = None

    @classmethod
    def from_dict(cls, value: dict[str, Any]) -> "RewriteRule":
        data = dict(value)
        data["action"] = Action(data["action"])
        return cls(**data)


@dataclass
class MitmConfig:
    hostnames: list[str] = field(default_factory=list)
    skip_server_cert_verify: bool = False

    @classmethod
    def from_dict(cls, value: dict[str, Any] | None) -> "MitmConfig":
        return cls(**(value or {}))


@dataclass
class Manifest:
    name: str
    description: str = ""
    author: str = ""
    homepage: str = ""
    rewrites: list[RewriteRule] = field(default_factory=list)
    mitm: MitmConfig = field(default_factory=MitmConfig)
    warnings: list[str] = field(default_factory=list)

    @classmethod
    def from_dict(cls, value: dict[str, Any]) -> "Manifest":
        data = dict(value)
        data["rewrites"] = [RewriteRule.from_dict(item) for item in data.get("rewrites", [])]
        data["mitm"] = MitmConfig.from_dict(data.get("mitm"))
        return cls(**data)

    def to_dict(self) -> dict[str, Any]:
        return asdict(self)
