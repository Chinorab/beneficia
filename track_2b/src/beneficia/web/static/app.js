// Source panel and status polling. No external requests: everything goes to this local server.
(function () {
  "use strict";

  const panel = document.querySelector(".source");
  const body = panel && panel.querySelector(".source-body");
  const labels = document.getElementById("source-labels");
  const label = (k) => labels ? labels.content.firstElementChild.dataset[k] : k;

  function el(tag, attrs, text) {
    const e = document.createElement(tag);
    Object.entries(attrs || {}).forEach(([k, v]) => e.setAttribute(k, v));
    if (text !== undefined) e.textContent = text;
    return e;
  }

  async function show(ref, trigger) {
    if (!panel || !ref) return;
    document.querySelectorAll('.ref[aria-pressed="true"], .chain .active').forEach((x) => {
      x.removeAttribute("aria-pressed"); x.classList.remove("active");
    });
    if (trigger) trigger.matches(".ref") ? trigger.setAttribute("aria-pressed", "true") : trigger.classList.add("active");
    const res = await fetch(`/cases/${panel.dataset.case}/source/${encodeURIComponent(ref)}`);
    if (!res.ok) return;
    const data = await res.json();
    body.replaceChildren();
    const dl = el("dl", { class: "source-meta" });
    [[label("doc"), data.filename], [label("page"), String(data.page)], [label("line"), String(data.line)]]
      .forEach(([k, v]) => { dl.append(el("dt", {}, k), el("dd", {}, v)); });
    const ol = el("ol", { class: "source-lines" });
    data.lines.forEach((ln) => {
      const li = el("li", ln.hit ? { class: "hit" } : {});
      li.append(el("span", { class: "n" }, String(ln.n)), el("span", {}, ln.text));
      ol.append(li);
    });
    body.append(dl, ol);
    if (window.matchMedia("(max-width: 1080px)").matches) panel.scrollIntoView({ block: "nearest" });
  }

  document.addEventListener("click", (e) => {
    const t = e.target.closest("[data-ref]");
    if (t && t.dataset.ref) show(t.dataset.ref, t);
  });
  document.addEventListener("keydown", (e) => {
    if (e.key !== "Enter" && e.key !== " ") return;
    const t = e.target.closest && e.target.closest(".chain [data-ref]");
    if (t && t.dataset.ref) { e.preventDefault(); show(t.dataset.ref, t); }
  });

  // submit buttons: disabled once the request starts, so a long analysis is not started twice
  document.querySelectorAll("form").forEach((form) => form.addEventListener("submit", () => {
    form.querySelectorAll("button[data-once]").forEach((b) => { b.disabled = true; b.setAttribute("aria-busy", "true"); });
  }));

  const poll = document.querySelector("[data-poll]");
  if (poll) {
    const step = poll.querySelector("[data-step]");
    const tick = async () => {
      try {
        const r = await fetch(poll.dataset.poll);
        const d = await r.json();
        if (d.status !== "running") { window.location.reload(); return; }
        if (step) step.textContent = d.step || "";
      } catch (_) { /* server busy, retry */ }
      setTimeout(tick, 2500);
    };
    setTimeout(tick, 2500);
  }
})();
