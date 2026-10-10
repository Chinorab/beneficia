from beneficia.extract.passes import RawRow
from beneficia.extract.resolve import Resolver, name_on, numbers_on
from beneficia.model import Document, Page

LINES = [
    "AKTIENBUCH der Alpenblick Holding AG, mit Sitz in Luzern",
    "Aktienkapital: CHF 100'000, eingeteilt in 1'000 Namenaktien zu nominal CHF 100.",
    "1 | Petra Imhof, geb. 12.03.1971, Schweizer Bürgerin | Seestrasse 4, 6006 Luzern | 520 | 1 bis 520",
    "2 | Bergkristall Beteiligungen GmbH | Bahnhofplatz 2, 6300 Zug | 300 | 521 bis 820",
    "3 | Lukas Ammann, geb. 02.11.1985, Schweizer Bürger | Dorfweg 9, 6010 Kriens | 180 | 821 bis 1000",
]


def docs():
    return {"D1": Document("D1", "aktienbuch.txt", "txt", [Page(1, LINES)])}


def row(p, values, line):
    return RawRow(p, "D1", values, line)


def test_numbers_and_names_on_line():
    assert {1000, 100000}.issubset(numbers_on(LINES[1]))
    assert name_on("Frau Petra Imhof", LINES[2])
    assert not name_on("Sandra Keller", LINES[2])


def test_resolver_builds_cited_facts_and_drops_hallucinations():
    r = Resolver(docs(), "Alpenblick Holding AG")
    r.add(row("companies", ["Alpenblick Holding AG", "AG", "Luzern", 1000, "shares"], "P1.L2"))
    r.add(row("holdings", ["Petra Imhof", "Alpenblick Holding AG", 520, None, None, "both"], "P1.L3"))
    r.add(row("holdings", ["Bergkristall Beteiligungen GmbH", "Alpenblick Holding AG", 300, None, None, None], "P1.L4"))
    r.add(row("holdings", ["Lukas Ammann", "Alpenblick Holding AG", 180, None, None, "both"], "P1.L5"))
    r.add(row("holdings", ["Lukas Ammann", "Alpenblick Holding AG", 999, None, None, "both"], "P1.L5"))  # not written
    r.add(row("holdings", ["Sandra Keller", "Alpenblick Holding AG", 300, None, None, "both"], "P1.L4"))  # wrong line
    r.add(row("persons", ["Petra Imhof", "12.03.1971", "Schweizer Bürgerin", "6006 Luzern"], "P1.L3"))
    r.add(row("holdings", ["X", "Y", 1, None, None, None], "P9.L9"))  # line does not exist
    res = r.finish()
    f = res.facts
    target = f.parties[f.target]
    assert target.total_capital == 1000
    assert sorted(h.units_held for h in f.holdings) == [180, 300, 520]
    assert {d["reason"] for d in res.dropped} == {"units_not_on_line", "holder_not_on_line", "line_not_found"}
    imhof = next(p for p in f.parties.values() if p.name == "Petra Imhof")
    assert imhof.kind == "natural_person" and imhof.fields["birth_date"].value == "12.03.1971"
    berg = next(p for p in f.parties.values() if p.name.startswith("Bergkristall"))
    assert berg.kind == "legal_entity"
    assert all(str(h.ref).startswith("D1.P1.L") for h in f.holdings)


def test_register_row_detection():
    from beneficia.extract.passes import _is_register_row as f
    assert f("Julien Perrin, né le 9 mai 1979, suisse 1700 Fribourg 300")
    assert f("Titlis Invest AG, Engelberg 8'000 Aktien")
    assert not f("Aktienkapital CHF 200'000, eingeteilt in 2'000 Namenaktien zu je CHF 100.")
    assert not f("Stand per 30. September 2026")
    assert not f("Aktionär Wohnsitz Anzahl Aktien")


def test_total_must_be_on_a_capital_line_and_agreements_need_wording():
    r = Resolver(docs(), "Alpenblick Holding AG")
    r.add(row("companies", ["Bergkristall Beteiligungen GmbH", "GmbH", "Zug", 300, "shares"], "P1.L4"))
    r.add(row("agreements", ["other", "Petra Imhof", "Alpenblick Holding AG", None], "P1.L3"))
    res = r.finish()
    assert {d["reason"] for d in res.dropped} == {"total_not_on_capital_line", "no_agreement_wording"}
