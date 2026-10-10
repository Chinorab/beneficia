"""Data model shared by ingestion, extraction, rules and reports (see specs data-model.md)."""
from __future__ import annotations

import re
from dataclasses import dataclass, field
from fractions import Fraction
from typing import Optional

REF_RE = re.compile(r"^(D\d+)\.P(\d+)\.L(\d+)$")


@dataclass(frozen=True, order=True)
class LineRef:
    doc: str
    page: int
    line: int

    def __str__(self) -> str:
        return f"{self.doc}.P{self.page}.L{self.line}"

    @classmethod
    def parse(cls, text: str) -> "LineRef":
        m = REF_RE.match(text.strip())
        if not m:
            raise ValueError(f"not a line reference: {text!r}")
        return cls(m.group(1), int(m.group(2)), int(m.group(3)))


@dataclass
class Page:
    number: int
    lines: list[str]
    ocr_confidence: Optional[float] = None


@dataclass
class Document:
    id: str
    filename: str
    kind: str  # pdf_text | pdf_scan | image | docx | txt
    pages: list[Page] = field(default_factory=list)
    language: str = "unknown"
    readable: bool = True
    error: Optional[str] = None

    def line(self, page: int, line: int) -> Optional[str]:
        if 1 <= page <= len(self.pages):
            lines = self.pages[page - 1].lines
            if 1 <= line <= len(lines):
                return lines[line - 1]
        return None


@dataclass
class Field:
    value: str
    ref: LineRef


@dataclass
class Party:
    id: str
    kind: str  # natural_person | legal_entity
    name: str
    refs: list[LineRef] = field(default_factory=list)
    fields: dict[str, Field] = field(default_factory=dict)
    total_capital: Optional[int] = None  # total units of capital (shares or quotas), legal entities
    total_votes: Optional[int] = None  # total votes when they differ from capital units
    total_ref: Optional[LineRef] = None
    special_kind: Optional[str] = None  # listed | pension | fund | foundation | association | trust
    foreign: Optional[bool] = None


@dataclass
class Holding:
    holder: str  # party id
    company: str  # party id
    units_held: int
    basis: str = "both"  # capital | votes | both
    held_for: Optional[str] = None  # party id of the principal for fiduciary holdings
    written_percent: Optional[Fraction] = None
    ref: Optional[LineRef] = None


@dataclass
class ControlAgreement:
    kind: str  # voting | fiduciary | veto | appointment | other
    controller: str
    controlled: str
    company: Optional[str]
    ref: Optional[LineRef] = None


@dataclass
class BoardRole:
    person: str
    company: Optional[str]
    role_raw: str
    role: str  # chair | member | managing_officer | sole_officer | other
    ref: Optional[LineRef] = None


@dataclass
class ReviewItem:
    reason: str
    article: str
    parties: list[str] = field(default_factory=list)
    refs: list[LineRef] = field(default_factory=list)
    detail: dict = field(default_factory=dict)


@dataclass
class MissingDocument:
    what: str  # ownership_proof | identification | readable_copy | board_extract | share_register
    about: str
    reason: str


@dataclass
class Finding:
    person: str
    basis: str  # direct | indirect | other_means | default_manager
    control_type: dict
    band: Optional[str]
    chain: list[str]
    chain_info_required: bool
    articles: list[str]
    refs: list[LineRef]
    status: str  # settled | pending_review
    share: Optional[Fraction] = None  # stake used for the band, display only


@dataclass
class CaseFacts:
    """Everything the rules engine needs, produced by extraction or written by hand in tests."""
    target: str
    parties: dict[str, Party]
    holdings: list[Holding] = field(default_factory=list)
    agreements: list[ControlAgreement] = field(default_factory=list)
    board: list[BoardRole] = field(default_factory=list)
    low_confidence_refs: list[LineRef] = field(default_factory=list)
