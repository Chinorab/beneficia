"""Identification data the register needs for each beneficial owner (TJPV art. 10 para. 1)."""
from __future__ import annotations

from typing import TYPE_CHECKING

from beneficia.model import CaseFacts, MissingDocument

if TYPE_CHECKING:
    from beneficia.rules.engine import AnalysisResult

REQUIRED_PERSON_FIELDS = ("birth_date", "nationality", "residence")


def identification(facts: CaseFacts, result: "AnalysisResult") -> None:
    for f in result.findings:
        party = facts.parties.get(f.person)
        if party is None:
            continue
        absent = [k for k in REQUIRED_PERSON_FIELDS if k not in party.fields]
        if absent:
            result.add_missing(MissingDocument("identification", f.person, ",".join(absent)))
