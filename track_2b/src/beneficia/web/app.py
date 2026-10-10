"""Local web interface (bound to 127.0.0.1 in the container). No external requests, no accounts."""
from __future__ import annotations

import json
import re
import threading
import traceback
from concurrent.futures import ThreadPoolExecutor
from datetime import datetime
from pathlib import Path
from typing import Optional

from fastapi import FastAPI, File, Form, HTTPException, Request, UploadFile
from fastapi.responses import HTMLResponse, JSONResponse, RedirectResponse, Response
from fastapi.staticfiles import StaticFiles
from fastapi.templating import Jinja2Templates
from markupsafe import Markup

from beneficia import config
from beneficia.extract.client import LLMClient, ModelUnavailable
from beneficia.ingest.case import IMAGE_EXT, load_case
from beneficia.model import LineRef
from beneficia.report.diagram import build_svg
from beneficia.report.i18n import LANGS, article, strings, t
from beneficia.report.note import build_note

HERE = Path(__file__).parent
ALLOWED = {".pdf", ".docx", ".txt", *IMAGE_EXT}

app = FastAPI(title="Beneficia", docs_url=None, redoc_url=None, openapi_url=None)
app.mount("/static", StaticFiles(directory=HERE / "static"), name="static")
templates = Jinja2Templates(directory=HERE / "templates")

_executor = ThreadPoolExecutor(max_workers=1)  # one analysis at a time: the model uses all cores
_jobs: dict[str, dict] = {}
_lock = threading.Lock()


def icon(name: str, cls: str = "icon") -> Markup:
    path = HERE / "static" / "icons" / f"{name}.svg"
    if not path.exists():
        return Markup("")
    svg = path.read_text(encoding="utf-8")
    return Markup(svg.replace("<svg ", f'<svg class="{cls}" aria-hidden="true" focusable="false" ', 1))


templates.env.globals.update(icon=icon, article=article)


def lang_of(request: Request) -> str:
    q = request.query_params.get("lang")
    if q in LANGS:
        return q
    c = request.cookies.get("lang")
    return c if c in LANGS else "de"


def render(request: Request, name: str, **ctx) -> HTMLResponse:
    lang = lang_of(request)
    ctx.update(request=request, lang=lang, s=strings(lang), other_lang="fr" if lang == "de" else "de")
    resp = templates.TemplateResponse(request, name, ctx)
    if request.query_params.get("lang") in LANGS:
        resp.set_cookie("lang", lang, samesite="strict", httponly=True)
    return resp


def _result_path(case_id: str) -> Path:
    return config.OUTPUT_DIR / case_id / "result.json"


def _case_dir(case_id: str) -> Path:
    if not re.fullmatch(r"[\w.]+", case_id):
        raise HTTPException(404)
    d = config.CASES_DIR / case_id
    if not d.is_dir():
        raise HTTPException(404)
    return d


def _status(case_id: str) -> str:
    job = _jobs.get(case_id)
    if job and job["state"] in ("queued", "running"):
        return "running"
    if job and job["state"] == "failed":
        return "failed"
    return "done" if _result_path(case_id).exists() else "new"


def _list_cases() -> list[dict]:
    out = []
    if not config.CASES_DIR.exists():
        return out
    for d in sorted(p for p in config.CASES_DIR.iterdir() if p.is_dir()):
        meta = {}
        if (d / "case.json").exists():
            meta = json.loads((d / "case.json").read_text(encoding="utf-8"))
        docs = [p for p in d.iterdir() if p.is_file() and p.suffix.lower() in ALLOWED]
        out.append({"id": d.name, "target": meta.get("target", ""), "documents": len(docs),
                    "status": _status(d.name)})
    return out


def _run(case_id: str) -> None:
    from beneficia.pipeline import analyse_case

    job = _jobs[case_id]
    job["state"] = "running"
    try:
        client = LLMClient()
        result = analyse_case(_case_dir(case_id), client, progress=lambda s: job.update(step=s))
        path = _result_path(case_id)
        path.parent.mkdir(parents=True, exist_ok=True)
        path.write_text(json.dumps(result, ensure_ascii=False, indent=1), encoding="utf-8")
        job["state"] = "done"
    except ModelUnavailable:
        job.update(state="failed", error="model_unreachable")
    except Exception:  # shown as a failure, details in the server log
        traceback.print_exc()
        job.update(state="failed", error="internal")


@app.get("/health")
def health() -> JSONResponse:
    return JSONResponse({"app": "ok", "model": "ok" if LLMClient().health() else "unreachable"})


@app.get("/", response_class=HTMLResponse)
def index(request: Request):
    return render(request, "index.html", cases=_list_cases())


@app.get("/privacy", response_class=HTMLResponse)
def privacy(request: Request):
    return render(request, "privacy.html")


@app.post("/cases")
async def create_case(request: Request, name: str = Form(...), target: str = Form(...),
                      files: list[UploadFile] = File(...)):
    slug = re.sub(r"[^\w]+", "_", name.strip().lower()).strip("_")[:60] or "fall"
    case_id = slug
    n = 2
    while (config.CASES_DIR / case_id).exists():
        case_id, n = f"{slug}_{n}", n + 1
    d = config.CASES_DIR / case_id
    d.mkdir(parents=True)
    saved = 0
    for i, f in enumerate(files, 1):
        ext = Path(f.filename or "").suffix.lower()
        if ext not in ALLOWED:
            continue
        safe = re.sub(r"[^\w.]+", "_", Path(f.filename).stem)[:80] or f"dokument_{i}"
        (d / f"{i:02d}_{safe}{ext}").write_bytes(await f.read())
        saved += 1
    (d / "case.json").write_text(json.dumps({"target": target.strip(), "created": datetime.now().isoformat(
        timespec="seconds")}, ensure_ascii=False, indent=1), encoding="utf-8")
    return RedirectResponse(f"/cases/{case_id}", status_code=303)


@app.post("/cases/{case_id}/analyze")
def analyze(case_id: str):
    _case_dir(case_id)
    with _lock:
        if _status(case_id) != "running":
            _jobs[case_id] = {"state": "queued", "step": "", "started": datetime.now().isoformat(timespec="seconds")}
            _executor.submit(_run, case_id)
    return RedirectResponse(f"/cases/{case_id}", status_code=303)


def _load_result(case_id: str) -> Optional[dict]:
    p = _result_path(case_id)
    return json.loads(p.read_text(encoding="utf-8")) if p.exists() else None


@app.get("/cases/{case_id}", response_class=HTMLResponse)
def case_page(request: Request, case_id: str):
    d = _case_dir(case_id)
    status = _status(case_id)
    meta = json.loads((d / "case.json").read_text(encoding="utf-8")) if (d / "case.json").exists() else {}
    docs = sorted(p.name for p in d.iterdir() if p.is_file() and p.suffix.lower() in ALLOWED)
    result = _load_result(case_id) if status == "done" else None
    ctx = {"case_id": case_id, "meta": meta, "docs": docs, "status": status, "job": _jobs.get(case_id, {})}
    if result:
        lang = lang_of(request)
        ctx.update(result=result, names={p["id"]: p for p in result["parties"]},
                   svg=Markup(build_svg(result, lang)), note=build_note(result, lang))
    return render(request, "case.html", **ctx)


@app.get("/cases/{case_id}/status")
def case_status(case_id: str) -> JSONResponse:
    _case_dir(case_id)
    job = _jobs.get(case_id, {})
    return JSONResponse({"status": _status(case_id), "step": job.get("step", "")})


@app.get("/cases/{case_id}/source/{ref}")
def source(case_id: str, ref: str) -> JSONResponse:
    result = _load_result(case_id)
    if result is None:
        raise HTTPException(404)
    try:
        r = LineRef.parse(ref)
    except ValueError:
        raise HTTPException(404)
    case = load_case(_case_dir(case_id))
    doc = case.docs.get(r.doc)
    if doc is None or doc.line(r.page, r.line) is None:
        raise HTTPException(404)
    lines = []
    for n in range(r.line - 2, r.line + 3):
        text = doc.line(r.page, n)
        if text is not None:
            lines.append({"n": n, "text": text, "hit": n == r.line})
    return JSONResponse({"ref": str(r), "filename": doc.filename, "page": r.page, "line": r.line, "lines": lines})


@app.get("/cases/{case_id}/export.json")
def export_json(case_id: str) -> Response:
    result = _load_result(case_id)
    if result is None:
        raise HTTPException(404)
    return Response(json.dumps(result, ensure_ascii=False, indent=1), media_type="application/json",
                    headers={"Content-Disposition": f'attachment; filename="{case_id}_entwurf.json"'})


@app.get("/cases/{case_id}/export.html", response_class=HTMLResponse)
def export_html(request: Request, case_id: str):
    result = _load_result(case_id)
    if result is None:
        raise HTTPException(404)
    lang = lang_of(request)
    return render(request, "export.html", case_id=case_id, result=result,
                  names={p["id"]: p for p in result["parties"]}, svg=Markup(build_svg(result, lang)),
                  note=build_note(result, lang))
