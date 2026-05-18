"""
main.py — FastAPI entry point for NOC Triage Agent v3
"""
import sys
from pathlib import Path

_BACKEND = Path(__file__).resolve().parent
if str(_BACKEND) not in sys.path:
    sys.path.insert(0, str(_BACKEND))

# Load .env before any module imports so env vars are available
from dotenv import load_dotenv
load_dotenv(_BACKEND / ".env")

from fastapi import FastAPI
from fastapi.middleware.cors import CORSMiddleware

from routers.triage import router as triage_router

app = FastAPI(title="NOC Triage Agent v3")

app.add_middleware(
    CORSMiddleware,
    allow_origins=["*"],
    allow_credentials=True,
    allow_methods=["*"],
    allow_headers=["*"],
)

app.include_router(triage_router)


@app.get("/health")
def health():
    return {"status": "ok"}
