"""
rag_pipeline.py
NOC Triage Agent v3 — RAG Enrichment Pipeline

Post-correlation step that enriches each triage result with AI-generated text:

  1. Build a compact query string from the correlation result
     (cascade_type + root_cause_type + alarm_category + equip_count + oem + severity)
  2. Embed the query with Voyage AI voyage-3 (1024-dim)
  3. Retrieve top-3 similar cases from Supabase pgvector via match_noc_chunks RPC
  4. Pass retrieved cases + current result into Claude claude-sonnet-4-5 to generate:
       - probable_root_cause  (1-2 sentences, equipment-specific)
       - recommended_action   (numbered steps for the NOC engineer)
  5. Fall back to the correlation engine's deterministic strings on ANY failure

Public API:
  enrich_result(result: dict)  -> dict   (mutates and returns)
  enrich_results(results: list[dict]) -> list[dict]
"""

from __future__ import annotations

import json
import logging
import os

logger = logging.getLogger(__name__)

# ── Config from environment ────────────────────────────────────────────
VOYAGE_API_KEY      = os.environ.get("VOYAGE_API_KEY", "")
ANTHROPIC_API_KEY   = os.environ.get("ANTHROPIC_API_KEY", "")
SUPABASE_URL        = os.environ.get("SUPABASE_URL", "")
SUPABASE_SERVICE_KEY = (
    os.environ.get("SUPABASE_SERVICE_KEY")
    or os.environ.get("SUPABASE_KEY", "")
)

CLAUDE_MODEL  = "claude-sonnet-4-5"
VOYAGE_MODEL  = "voyage-3"
TOP_K         = 3
MAX_TOKENS    = 512


# ── Step 1: Query text ─────────────────────────────────────────────────


def _build_query_text(result: dict) -> str:
    """
    Build a compact text fingerprint of the alarm pattern for embedding.
    Format matches what the seed script writes into noc_kb_chunks.content.
    """
    cascade      = result.get("cascade_type", "UNKNOWN")
    root_type    = result.get("root_cause_type", "UNKNOWN")
    alarm_cat    = result.get("alarm_category", "UNKNOWN")
    severity     = result.get("dominant_severity", "info")
    equip_count  = len(result.get("blast_radius", {}).get("affected_equipment", []))
    oems         = " ".join(result.get("das_oems", []))
    return (
        f"cascade={cascade} root_type={root_type} "
        f"alarm_category={alarm_cat} equip_count={equip_count} "
        f"oem={oems} severity={severity}"
    )


# ── Step 2: Voyage AI embedding ────────────────────────────────────────


def _embed_query(text: str) -> list[float] | None:
    """
    Embed the query text using Voyage AI voyage-3.
    Returns a 1024-dim float list, or None on any failure.
    """
    if not VOYAGE_API_KEY:
        logger.debug("VOYAGE_API_KEY not set — skipping embedding")
        return None
    try:
        import voyageai  # lazy import
        vo = voyageai.Client(api_key=VOYAGE_API_KEY)
        resp = vo.embed([text], model=VOYAGE_MODEL)
        return resp.embeddings[0]
    except Exception as exc:
        logger.warning("Voyage AI embed failed: %s", exc)
        return None


# ── Step 3: Supabase pgvector retrieval ────────────────────────────────


def _retrieve_similar(embedding: list[float], k: int = TOP_K) -> list[dict]:
    """
    Call match_noc_chunks RPC in Supabase with the embedded query vector.
    Returns a list of chunk dicts (keys: alarm_id, alarm_name, section, content, similarity).
    Returns [] on any failure so the pipeline degrades gracefully.
    """
    if not (SUPABASE_URL and SUPABASE_SERVICE_KEY):
        logger.debug("Supabase credentials missing — skipping retrieval")
        return []
    try:
        from supabase import create_client  # lazy import
        sb = create_client(SUPABASE_URL, SUPABASE_SERVICE_KEY)
        resp = sb.rpc(
            "match_noc_chunks",
            {"query_embedding": embedding, "match_count": k},
        ).execute()
        return resp.data or []
    except Exception as exc:
        logger.warning("Supabase retrieval failed: %s", exc)
        return []


# ── Step 4: Claude generation ──────────────────────────────────────────


def _format_retrieved(chunks: list[dict]) -> str:
    """Format retrieved chunks as numbered context entries for the prompt."""
    if not chunks:
        return "No similar historical cases available in the knowledge base."
    parts: list[str] = []
    for i, chunk in enumerate(chunks, 1):
        header_parts = [f"[Case {i}]"]
        if chunk.get("alarm_id"):
            header_parts.append(chunk["alarm_id"])
        if chunk.get("alarm_name"):
            header_parts.append(f"— {chunk['alarm_name']}")
        if chunk.get("section"):
            header_parts.append(f"({chunk['section']})")
        sim = chunk.get("similarity", 0)
        header_parts.append(f"similarity={sim:.2f}")
        parts.append(" ".join(header_parts) + "\n" + chunk.get("content", "").strip())
    return "\n\n".join(parts)


_PROMPT_TEMPLATE = """\
You are a senior NOC engineer for a Distributed Antenna System (DAS) network.
Produce precise, actionable triage text for the alarm event described below.

CURRENT ALARM EVENT:
- Cascade type: {cascade_type}
- Root cause: {root_cause_node} (type: {root_cause_type})
- Alarm count: {alarm_count}
- Dominant severity: {dominant_severity}
- Affected equipment: {affected_equipment}
- Affected carriers: {affected_carriers}
- Affected bands: {affected_bands}
- Service impact: {service_impact}
- OEM: {das_oems}

SIMILAR HISTORICAL CASES FROM NOC KNOWLEDGE BASE:
{retrieved_context}

Instructions:
1. probable_root_cause — 1-2 sentences. Reference the specific equipment IDs (e.g. {root_cause_node}).
   Explain the failure mechanism and which downstream nodes are affected.
2. recommended_action — Numbered list of concrete steps for the NOC engineer.
   Reference specific equipment IDs. Include who to contact, what to check, and when to dispatch.

Respond with valid JSON only (no markdown fences, no extra text):
{{"probable_root_cause": "<text>", "recommended_action": "<text>"}}"""


def _generate_rag_text(result: dict, retrieved_chunks: list[dict]) -> dict | None:
    """
    Call Claude claude-sonnet-4-5 to generate enriched triage text.
    Returns a dict with keys 'probable_root_cause' and 'recommended_action',
    or None on any failure.
    """
    if not ANTHROPIC_API_KEY:
        logger.debug("ANTHROPIC_API_KEY not set — skipping LLM generation")
        return None
    try:
        import anthropic  # lazy import

        br = result.get("blast_radius", {})
        prompt = _PROMPT_TEMPLATE.format(
            cascade_type       = result.get("cascade_type", ""),
            root_cause_node    = result.get("root_cause_node", ""),
            root_cause_type    = result.get("root_cause_type", ""),
            alarm_count        = result.get("alarm_count", 0),
            dominant_severity  = result.get("dominant_severity", ""),
            affected_equipment = ", ".join(br.get("affected_equipment", [])),
            affected_carriers  = ", ".join(br.get("affected_carriers", [])),
            affected_bands     = ", ".join(br.get("affected_bands", [])),
            service_impact     = br.get("service_impact", ""),
            das_oems           = ", ".join(result.get("das_oems", [])),
            retrieved_context  = _format_retrieved(retrieved_chunks),
        )

        client = anthropic.Anthropic(api_key=ANTHROPIC_API_KEY)
        msg = client.messages.create(
            model=CLAUDE_MODEL,
            max_tokens=MAX_TOKENS,
            messages=[{"role": "user", "content": prompt}],
        )

        raw = msg.content[0].text.strip()
        # Strip markdown fences if Claude adds them despite instructions
        if raw.startswith("```"):
            lines = raw.split("\n")
            raw = "\n".join(lines[1:-1])  # drop first and last fence line

        parsed = json.loads(raw)
        # Validate keys are present and non-empty
        if parsed.get("probable_root_cause") and parsed.get("recommended_action"):
            return parsed
        logger.warning("Claude response missing required keys: %s", list(parsed.keys()))
        return None

    except json.JSONDecodeError as exc:
        logger.warning("Claude response was not valid JSON: %s", exc)
        return None
    except Exception as exc:
        logger.warning("Claude generation failed: %s", exc)
        return None


# ── Public API ─────────────────────────────────────────────────────────


def enrich_result(result: dict) -> dict:
    """
    Enrich a single correlation result with RAG-generated probable_root_cause
    and recommended_action. Falls back to the existing hardcoded strings on error.

    Adds two diagnostic fields (ignored by the frontend):
      result["rag_enriched"]        — True if LLM generation succeeded
      result["rag_retrieved_count"] — number of similar cases retrieved
    """
    query_text = _build_query_text(result)
    logger.debug("RAG query: %s", query_text)

    # Step 1 → embed
    embedding = _embed_query(query_text)

    # Step 2 → retrieve (skip if embedding failed)
    chunks = _retrieve_similar(embedding) if embedding is not None else []

    # Step 3 → generate
    rag_output = _generate_rag_text(result, chunks)

    # Step 4 → apply or fall back
    if rag_output:
        result["probable_root_cause"] = rag_output["probable_root_cause"]
        result["recommended_action"]  = rag_output["recommended_action"]
        result["rag_enriched"]        = True
        result["rag_retrieved_count"] = len(chunks)
    else:
        result["rag_enriched"]        = False
        result["rag_retrieved_count"] = len(chunks)

    return result


def enrich_results(results: list[dict]) -> list[dict]:
    """
    Enrich a list of correlation results.
    Each result is processed independently — one failure does not block others.
    """
    enriched: list[dict] = []
    for r in results:
        try:
            enriched.append(enrich_result(r))
        except Exception as exc:
            logger.error("enrich_result unexpected error (site=%s): %s", r.get("site_id"), exc)
            r["rag_enriched"] = False
            r["rag_retrieved_count"] = 0
            enriched.append(r)
    return enriched
