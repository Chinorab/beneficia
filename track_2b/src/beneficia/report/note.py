"""Justification note: one plain sentence per conclusion, with articles and sources."""
from __future__ import annotations

from beneficia.report.i18n import article, t

TEMPLATES = {
    "de": {
        "direct": "{name} hält direkt {pct} Prozent der {target}. Damit ist die Schwelle von 25 Prozent erreicht.",
        "indirect": "{name} hält mehr als 50 Prozent an {via}. {via_holds} hält {pct} Prozent der {target}. "
                    "{name} kontrolliert die {target} damit indirekt.",
        "other_means": "{name} könnte die {target} auf andere Weise kontrollieren, zusammen mit den gebundenen "
                       "Stimmen {pct_txt}. Dies ist durch die Treuhänderin oder den Treuhänder zu beurteilen.",
        "default_manager": "Keine natürliche Person erreicht die Schwelle von 25 Prozent. Als oberstes Mitglied des "
                           "leitenden Organs wird {name} vorgeschlagen.",
        "pending": "Diese Angabe ist zu prüfen.",
        "articles": "Rechtsgrundlage",
        "sources": "Fundstellen",
        "none": "Aus den Dokumenten ergibt sich keine wirtschaftlich berechtigte Person.",
    },
    "fr": {
        "direct": "{name} détient directement {pct} pour cent de {target}. Le seuil de 25 pour cent est atteint.",
        "indirect": "{name} détient plus de 50 pour cent de {via}. {via_holds} détient {pct} pour cent de {target}. "
                    "{name} contrôle donc {target} indirectement.",
        "other_means": "{name} pourrait contrôler {target} par d'autres moyens, en tenant compte des voix liées "
                       "{pct_txt}. La fiduciaire doit en juger.",
        "default_manager": "Aucune personne physique n'atteint le seuil de 25 pour cent. Proposition au titre du "
                           "membre le plus élevé de l'organe de direction : {name}.",
        "pending": "Cette indication est à vérifier.",
        "articles": "Base légale",
        "sources": "Sources",
        "none": "Les documents ne permettent d'identifier aucun ayant droit économique.",
    },
}


def _pct(share: dict | None, lang: str) -> str:
    if not share:
        return ""
    value = share["percent"]
    text = f"{value:.2f}".rstrip("0").rstrip(".")
    return text.replace(".", ",") if lang == "fr" else text


def build_note(result: dict, lang: str) -> list[dict]:
    names = {p["id"]: p["name"] for p in result["parties"]}
    tpl = TEMPLATES.get(lang, TEMPLATES["de"])
    target = names.get(result["target"], result["target"] or "")
    items = []
    for f in result["findings"]:
        name = names.get(f["person"], f["person"])
        chain = f["chain"]
        ctx = {"name": name, "target": target, "pct": _pct(f["share"], lang),
               "pct_txt": f"({_pct(f['share'], lang)} %)" if f["share"] else ""}
        if f["basis"] == "indirect" and len(chain) >= 3:
            ctx["via"] = names.get(chain[1], chain[1])
            ctx["via_holds"] = names.get(chain[-2], chain[-2])
        text = tpl[f["basis"]].format(**ctx)
        if f["status"] == "pending_review":
            text += " " + tpl["pending"]
        items.append({"kind": "finding", "text": text, "status": f["status"],
                      "articles": [article(a, lang) for a in f["articles"]], "refs": f["refs"]})
    if not result["findings"]:
        items.append({"kind": "none", "text": tpl["none"], "status": "pending_review", "articles": [], "refs": []})
    for r in result["review"]:
        parties = ", ".join(names.get(p, p) for p in r["parties"])
        colon = " : " if lang == "fr" else ": "
        text = t(lang, "reason_" + r["reason"]) + (f"{colon}{parties}" if parties else "") + "."
        items.append({"kind": "review", "text": text, "status": "pending_review",
                      "articles": [article(r["article"], lang)], "refs": r["refs"]})
    return items
