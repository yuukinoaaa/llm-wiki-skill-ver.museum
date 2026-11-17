from __future__ import annotations

from dataclasses import asdict, dataclass


@dataclass(frozen=True)
class SourceInfo:
    path: str
    name: str
    type: str
    sha256: str

    def to_dict(self) -> dict[str, str]:
        return asdict(self)


@dataclass(frozen=True)
class TextBlock:
    id: str
    text: str
    kind: str = "paragraph"

    def to_dict(self) -> dict[str, str]:
        return asdict(self)


@dataclass(frozen=True)
class ExtractedDocument:
    schema_version: str
    source: SourceInfo
    blocks: list[TextBlock]

    def to_dict(self) -> dict[str, object]:
        return {
            "schema_version": self.schema_version,
            "source": self.source.to_dict(),
            "blocks": [block.to_dict() for block in self.blocks],
        }
