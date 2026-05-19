# NOC Triage Agent v3 — RAG-Enriched DAS Alarm Triage

An agentic AI system that ingests raw DAS alarms, correlates cascading failures to their root cause, and generates equipment-specific triage guidance using a RAG pipeline backed by a NOC knowledge base.

**Live demo:** https://noc-triage-v3.vercel.app

---

## What it does

1. **Ingestion** — Normalizes raw alarms from multi-OEM DAS systems (Stratum, Orion) into a canonical alarm model. OEM-specific field mappings are resolved at ingestion only; all downstream logic operates on canonical terminology.

2. **Correlation** — Aggregates alarms within a 15-minute window per site/zone, detects cascade patterns (optical, power, sync, hub), and identifies the root cause node. Produces a blast radius with affected equipment, carriers, and bands.

3. **RAG Enrichment** — Embeds the alarm fingerprint with Voyage AI (`voyage-3`), retrieves the top-3 similar cases from a 136-chunk NOC knowledge base in Supabase pgvector, and passes retrieved context to Claude (`claude-sonnet-4-5`) to generate:
   - `probable_root_cause` — equipment-specific failure explanation
   - `recommended_action` — numbered steps for the NOC engineer

4. **Persistence** — Writes canonical alarms, site events, and triage results to Supabase.

---

## Stack

| Layer | Technology |
|---|---|
| Backend | Python, FastAPI |
| LLM | Anthropic Claude (claude-sonnet-4-5) |
| Embeddings | Voyage AI (voyage-3, 1024-dim) |
| Vector store | Supabase pgvector |
| Frontend | React |
| Deployment | Railway |

---

## Architecture

```
Raw Alarms (Stratum / Orion)
        │
        ▼
 Ingestion Agent
 - OEM normalization
 - Canonical alarm model
 - Alarm aggregation (15-min window)
        │
        ▼
 Correlation Engine
 - Cascade detection (optical / power / sync / hub)
 - Root cause identification
 - Blast radius calculation
        │
        ▼
 RAG Pipeline
 - Query embedding (Voyage AI)
 - Similar case retrieval (Supabase pgvector)
 - Triage generation (Claude)
        │
        ▼
 Triage Result
 - probable_root_cause
 - recommended_action (numbered steps)
 - rag_enriched: true
```

---

## Local setup

### Backend

```bash
cd backend
pip install -r requirements.txt

# Required environment variables
export ANTHROPIC_API_KEY=your_key
export VOYAGE_API_KEY=your_key
export SUPABASE_URL=your_url
export SUPABASE_SERVICE_KEY=your_service_role_key  # must start with eyJ

uvicorn main:app --reload --port 8000
```

### Frontend

```bash
cd frontend
npm install
npm start
# Opens at http://localhost:3000
```

### Seed the knowledge base

```bash
cd backend
python seed_vector_store.py
# Seeds 136 chunks to Supabase noc_kb_chunks
```

---

## API

### POST /triage/simulate

Run a named scenario end-to-end.

```bash
curl -X POST https://noc-triage-v3-production.up.railway.app/triage/simulate \
  -H "Content-Type: application/json" \
  -d '{"scenario": "SCN-001", "site_id": "SITE-ATX-001"}'
```

Key response fields:

```json
{
  "results": [
    {
      "rag_enriched": true,
      "rag_retrieved_count": 3,
      "probable_root_cause": "...",
      "recommended_action": "1. ...\n2. ...\n3. ..."
    }
  ]
}
```

### POST /triage

Submit raw alarms directly.

### GET /triage/topology?site_id=SITE-ATX-001

Returns site topology for the UI.

---

## Scenarios

| ID | Description | Cascade Type |
|---|---|---|
| SCN-001 | Optical module failure — OM-1 offline, RU-01/02/03 downstream loss | OPTICAL_CASCADE |
| SCN-002 | Expansion hub failure — all remotes under EH-01 offline | HUB_CASCADE |
| SCN-003 | Multi-site POI signal loss — carrier B4 degraded across zones | POI_SIGNAL_LOSS |

---

## Key design decisions

- **Canonical model at ingestion boundary** — OEM translation tables are a configuration concern; the correlation engine and RAG pipeline never see raw OEM field names.
- **Graceful RAG fallback** — if Voyage, Supabase, or Claude fail at any step, the system falls back to deterministic correlation output without crashing the request.
- **Service role key required** — Supabase anon key does not have RPC execution rights for `match_noc_chunks`; use the service role key.
