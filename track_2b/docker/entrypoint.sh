#!/bin/sh
# Start the Apertus model server on loopback, wait until it is ready, then run the requested command:
#   web            local interface on port 8080 (default)
#   eval           batch evaluation of /data/cases (or the built-in fictitious cases)
#   offline-check  eval, then fail unless every case produced a result and no network interface is up
#   test           unit and integration tests (no model needed)
#   replay         recompute the reported scores from data/results (no model needed)
set -eu

MODE="${1:-web}"
PY=/opt/venv/bin/python

if [ "$MODE" = "test" ]; then
  exec "$PY" -m pytest -q /opt/beneficia/src/tests
fi
if [ "$MODE" = "replay" ]; then  # recorded model outputs, no model needed
  exec "$PY" -m beneficia.cli replay /data/results /data/cases --out /data/output/replay
fi

# Use the fictitious evaluation cases shipped in the image when no case folder is mounted.
if [ ! -d "${BENEFICIA_CASES_DIR}" ] || [ -z "$(ls -A "${BENEFICIA_CASES_DIR}" 2>/dev/null)" ]; then
  mkdir -p "${BENEFICIA_CASES_DIR}"
  cp -r /opt/beneficia/cases/. "${BENEFICIA_CASES_DIR}/"
fi
mkdir -p "${BENEFICIA_OUTPUT_DIR}"

THREADS="${LLM_THREADS:-$(nproc)}"
/app/llama-server -m /models/apertus.gguf --host 127.0.0.1 --port 8081 --alias "$LLM_NAME" \
  --jinja --override-kv tokenizer.ggml.eos_token_id=int:68 \
  -c "${LLM_CTX:-4096}" -np 1 -t "$THREADS" > /tmp/llama-server.log 2>&1 &

echo "Starting Apertus v1.5 8B on ${THREADS} threads..."
i=0
until curl -fs http://127.0.0.1:8081/health > /dev/null 2>&1; do
  i=$((i + 1))
  if [ "$i" -gt 300 ]; then echo "model server did not start"; tail -n 40 /tmp/llama-server.log; exit 2; fi
  sleep 1
done
echo "Model ready."

case "$MODE" in
  web)
    echo "Open http://127.0.0.1:8080 in your browser."
    exec "$PY" -m uvicorn beneficia.web.app:app --host 0.0.0.0 --port 8080 --no-access-log
    ;;
  eval)
    shift
    exec "$PY" -m beneficia.cli eval "${BENEFICIA_CASES_DIR}" --out "${BENEFICIA_OUTPUT_DIR}/eval" "$@"
    ;;
  offline-check)
    shift
    # Only the loopback interface may be up (container started with --network none).
    up=$(ls /sys/class/net | grep -v '^lo$' || true)
    if [ -n "$up" ]; then echo "OFFLINE TEST FAILED: network interfaces present: $up"; exit 1; fi
    if "$PY" -c "import socket; socket.create_connection(('huggingface.co', 443), timeout=3)" 2>/dev/null; then
      echo "OFFLINE TEST FAILED: outbound connection succeeded"; exit 1
    fi
    "$PY" -m beneficia.cli eval "${BENEFICIA_CASES_DIR}" --out "${BENEFICIA_OUTPUT_DIR}/offline" "$@"
    "$PY" - <<'EOF'
import json, os, sys
from pathlib import Path
out = Path(os.environ["BENEFICIA_OUTPUT_DIR"]) / "offline"
summary = json.loads((out / "summary.json").read_text(encoding="utf-8"))
done = [r["case"] for r in summary["cases"]]
ok = all((out / c / "result.json").exists() for c in done) and summary["totals"]["citation_validity"] == 1.0
print(json.dumps(summary["totals"], indent=1))
if ok and done:
    print(f"OFFLINE TEST PASSED: {len(done)} cases analysed with no network, all citations resolve.")
else:
    print("OFFLINE TEST FAILED"); sys.exit(1)
EOF
    ;;
  *)
    exec "$@"
    ;;
esac
