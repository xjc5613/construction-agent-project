# -*- coding: utf-8 -*-
from dataclasses import asdict, dataclass, field
from typing import Any, Dict, List, Optional


@dataclass
class ParsedSection:
    content: str
    section: str = ""
    ordinal: int = 0
    page_number: Optional[int] = None


@dataclass
class ParsedDocument:
    title: str
    text: str
    sections: List[ParsedSection] = field(default_factory=list)
    metadata: Dict[str, Any] = field(default_factory=dict)
    text_coverage: float = 1.0
    warnings: List[str] = field(default_factory=list)

    def as_dict(self) -> Dict[str, Any]:
        payload = asdict(self)
        payload["sections"] = [asdict(section) for section in self.sections]
        return payload


@dataclass
class ParsedTable:
    columns: List[str]
    rows: List[Dict[str, Any]]
    sheet_name: str = ""
    warnings: List[str] = field(default_factory=list)

    def as_dict(self) -> Dict[str, Any]:
        return asdict(self)
