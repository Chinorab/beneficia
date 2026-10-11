# Beneficia: one image with the Apertus model server (llama.cpp) and the application.
# Everything is downloaded at build time. At run time the container needs no network:
# the model listens on 127.0.0.1 inside the container and `make offline-test` runs with --network none.

# Official llama.cpp server image (Ubuntu 24.04, amd64 and arm64), pinned by digest.
FROM ghcr.io/ggml-org/llama.cpp:server-b10548@sha256:4edd7ad571186256b3b9a4b6386f515b8725f78c34828131a5c85d2a0676e241

USER root
RUN apt-get update \
 && apt-get install -y --no-install-recommends \
      python3 python3-venv ca-certificates curl \
      tesseract-ocr tesseract-ocr-deu tesseract-ocr-fra tesseract-ocr-ita poppler-utils \
 && rm -rf /var/lib/apt/lists/*

# Apertus v1.5 8B, text-only conversion, Q4_K_M GGUF (Apache 2.0, Apertus Acceptable Use Policy applies).
# Lineage: swiss-ai/Apertus-v1.5-8B -> andreasmartin/apertus-v1.5-8b-text -> Colby/apertus-v1.5-8b-text-Q4_K_M-GGUF.
# The repository is not gated, so the build needs no account or token. Pinned by revision and sha256.
ARG MODEL_URL=https://huggingface.co/Colby/apertus-v1.5-8b-text-Q4_K_M-GGUF/resolve/248ec68a63e219e3f061e4c946fc8a20d63b9975/apertus-v1.5-8b-text-q4_k_m.gguf
ARG MODEL_SHA256=a037df8d87ff6caacee794ee85f55342f2152e0d359b7389033300c3bee5f299
RUN mkdir -p /models \
 && curl -fL --retry 5 --retry-delay 5 -o /models/apertus.gguf "$MODEL_URL" \
 && echo "$MODEL_SHA256  /models/apertus.gguf" | sha256sum -c -

COPY src/requirements.txt /opt/beneficia/requirements.txt
RUN python3 -m venv /opt/venv \
 && /opt/venv/bin/pip install --no-cache-dir -r /opt/beneficia/requirements.txt

COPY src /opt/beneficia/src
COPY data/cases /opt/beneficia/cases
COPY docker/entrypoint.sh /usr/local/bin/beneficia-entrypoint
RUN chmod +x /usr/local/bin/beneficia-entrypoint

ENV LLM_BASE_URL=http://127.0.0.1:8081/v1 \
    LLM_NAME=apertus-v1.5-8b-text-q4_k_m \
    LLAMA_ARG_HOST=127.0.0.1 \
    BENEFICIA_CASES_DIR=/data/cases \
    BENEFICIA_OUTPUT_DIR=/data/output \
    PYTHONPATH=/opt/beneficia/src \
    PYTHONUNBUFFERED=1

WORKDIR /opt/beneficia/src
EXPOSE 8080
HEALTHCHECK --interval=30s --timeout=5s --start-period=180s CMD curl -fs http://127.0.0.1:8080/health || exit 1
ENTRYPOINT ["/usr/local/bin/beneficia-entrypoint"]
CMD ["web"]
