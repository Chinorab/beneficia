"""Ownership chain diagram as SVG. Every node and edge carries the reference of its source line.

Layout: target company at the bottom, holders above it, one row per level. Percentages are computed by
the rules code from cited units and are shown for orientation only.
"""
from __future__ import annotations

from collections import defaultdict
from html import escape

from beneficia.report.i18n import t

BOX_W, BOX_H, ROW_H, GAP, PAD = 214, 54, 118, 26, 24


def _short(text: str, n: int = 30) -> str:
    return text if len(text) <= n else text[: n - 1].rstrip() + "…"


def _pct(share: dict | None) -> str:
    if not share:
        return ""
    v = share["percent"]
    return f"{v:.2f}".rstrip("0").rstrip(".") + " %"


def build_svg(result: dict, lang: str) -> str:
    target = result["target"]
    if not target:
        return ""
    parties = {p["id"]: p for p in result["parties"]}
    status = {f["person"]: f["status"] for f in result["findings"]}

    edges = []  # (owner, company, holding)
    for h in result["holdings"]:
        owner = h["holder"]
        edges.append((owner, h["company"], h))
        if h["held_for"]:
            edges.append((h["held_for"], h["holder"], {**h, "fiduciary_link": True}))
    up = defaultdict(list)
    for owner, comp, h in edges:
        up[comp].append((owner, h))

    level = {target: 0}
    frontier = [target]
    while frontier:
        nxt = []
        for comp in frontier:
            for owner, _ in up.get(comp, []):
                if owner not in level or level[owner] < level[comp] + 1:
                    if level.get(owner, -1) < level[comp] + 1 and level[comp] + 1 <= 8:
                        level[owner] = level[comp] + 1
                        nxt.append(owner)
        frontier = nxt
    for f in result["findings"]:  # default manager or other means: shown above the target
        level.setdefault(f["person"], 1)

    rows = defaultdict(list)
    for node, lv in level.items():
        rows[lv].append(node)
    for lv in rows:
        rows[lv].sort(key=lambda n: (parties.get(n, {}).get("kind") != "legal_entity", parties.get(n, {}).get("name", n)))
    depth = max(rows)
    width = max(len(r) for r in rows.values()) * (BOX_W + GAP) - GAP + 2 * PAD
    width = max(width, BOX_W + 2 * PAD)
    height = (depth + 1) * ROW_H - (ROW_H - BOX_H) + 2 * PAD

    pos = {}
    for lv, nodes in rows.items():
        row_w = len(nodes) * (BOX_W + GAP) - GAP
        x0 = (width - row_w) / 2
        y = PAD + (depth - lv) * ROW_H
        for i, n in enumerate(nodes):
            pos[n] = (x0 + i * (BOX_W + GAP), y)

    out = [f'<svg xmlns="http://www.w3.org/2000/svg" viewBox="0 0 {width:.0f} {height:.0f}" class="chain" '
           f'role="img" aria-label="{escape(t(lang, "diagram_title"))}">']
    for owner, comp, h in edges:
        if owner not in pos or comp not in pos:
            continue
        x1, y1 = pos[owner][0] + BOX_W / 2, pos[owner][1] + BOX_H
        x2, y2 = pos[comp][0] + BOX_W / 2, pos[comp][1]
        cls = "edge fiduciary" if h.get("fiduciary_link") or h["held_for"] else "edge"
        ref = h.get("ref") or ""
        mid_y = (y1 + y2) / 2
        path = f"M{x1:.0f},{y1:.0f} C{x1:.0f},{mid_y:.0f} {x2:.0f},{mid_y:.0f} {x2:.0f},{y2:.0f}"
        out.append(f'<g class="{cls}" data-ref="{escape(ref)}" tabindex="0">'
                   f'<path d="{path}"/><path class="hit" d="{path}"/>')
        label = "" if h.get("fiduciary_link") else _pct(h["capital_share"])
        if label:
            lx, ly = (x1 + x2) / 2, mid_y
            out.append(f'<rect class="label-bg" x="{lx - 30:.0f}" y="{ly - 11:.0f}" width="60" height="20"/>'
                       f'<text class="label" x="{lx:.0f}" y="{ly + 4:.0f}">{escape(label)}</text>')
        out.append("</g>")
    for node, (x, y) in pos.items():
        p = parties.get(node, {"name": node, "kind": "natural_person", "refs": []})
        kind = p["kind"]
        cls = ["node", "entity" if kind == "legal_entity" else "person"]
        if node == target:
            cls.append("target")
        if node in status:
            cls.append("owner-" + status[node])
        ref = (p.get("refs") or [""])[0]
        sub = t(lang, "diagram_entity") if kind == "legal_entity" else t(lang, "diagram_person")
        out.append(f'<g class="{" ".join(cls)}" data-ref="{escape(ref)}" tabindex="0">'
                   f'<rect x="{x:.0f}" y="{y:.0f}" width="{BOX_W}" height="{BOX_H}"/>'
                   f'<text class="name" x="{x + 12:.0f}" y="{y + 23:.0f}">{escape(_short(p["name"]))}</text>'
                   f'<text class="sub" x="{x + 12:.0f}" y="{y + 41:.0f}">{escape(sub)}</text>'
                   f'<title>{escape(p["name"])}</title></g>')
    out.append("</svg>")
    return "".join(out)
