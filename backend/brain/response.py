from dataclasses import asdict, dataclass, field
from typing import Any


@dataclass
class BrainRequest:
    query: str
    mode: str = "auto"
    image_path: str | None = None
    metadata: dict[str, Any] = field(default_factory=dict)

    @classmethod
    def from_any(cls, data: "BrainRequest | dict | str") -> "BrainRequest":
        if isinstance(data, cls):
            return data
        if isinstance(data, str):
            return cls(query=data)
        return cls(**data)


@dataclass
class BrainResponse:
    answer: str
    route: str
    confidence: float = 0.0
    confidence_type: str = "none"
    sources: list[str] = field(default_factory=list)
    metadata: dict[str, Any] = field(default_factory=dict)
    warnings: list[str] = field(default_factory=list)

    def to_dict(self) -> dict[str, Any]:
        return asdict(self)

    @property
    def status(self) -> str:
        return "unknown" if self.route == "unknown" or self.confidence <= 0 else "ok"

    @property
    def data(self) -> dict[str, Any]:
        return self.metadata
