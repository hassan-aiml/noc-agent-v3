# NOC Triage Agent v2 — Digital Twin Dashboard

## Start Backend
```bash
cd backend
pip install -r requirements.txt
export ANTHROPIC_API_KEY=your_key_here
uvicorn main:app --reload --port 8000
```

## Start Frontend
```bash
cd frontend
npm install
npm start
# Opens at http://localhost:3000
```

## Scenarios
1. **Single RU Failure** — Isolated VSWR fault on RU-01. Sev 2.
2. **Food Court Hub Failure** — All 5 RUs under EH-01 offline. Correlation engine identifies EH-01 as root cause (not the 5 individual RUs). Sev 3.
3. **Meridian n41 Signal Loss** — DL_POWER_LOW on all RUs for MDN/n41. Correlation engine traces to POI-MDN-N41. Sev 4.
