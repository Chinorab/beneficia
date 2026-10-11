"""Configuration from environment variables only (no secrets in code)."""
import os
from pathlib import Path

LLM_BASE_URL = os.environ.get("LLM_BASE_URL", "http://127.0.0.1:8081/v1")
LLM_NAME = os.environ.get("LLM_NAME", "apertus-v1.5-8b-text-q4_k_m")
LLM_API_KEY = os.environ.get("LLM_API_KEY", "local-not-used")

_default_data = Path(__file__).resolve().parents[2] / "data"
DATA_DIR = Path(os.environ.get("BENEFICIA_DATA_DIR", str(_default_data)))
CASES_DIR = Path(os.environ.get("BENEFICIA_CASES_DIR", str(DATA_DIR / "cases")))
OUTPUT_DIR = Path(os.environ.get("BENEFICIA_OUTPUT_DIR", str(DATA_DIR / "output")))
# recorded reference results, shown in the interface until a case is analysed on this machine
RESULTS_DIR = Path(os.environ.get("BENEFICIA_RESULTS_DIR", str(CASES_DIR.parent / "results")))
