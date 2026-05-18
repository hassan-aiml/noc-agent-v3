"""
seed_vector_store.py
NOC Triage Agent v3 — Seed noc_kb_chunks with ground truth scenario patterns.

Usage:
  cd backend && python seed_vector_store.py

What this does:
  1. Reads 4 ground truth scenarios from tests/ground_truth/scenarios.yaml
  2. Builds a text chunk per scenario (pattern fingerprint + resolution notes)
  3. Embeds each chunk with Voyage AI voyage-3 (1024-dim)
  4. Upserts into noc_kb_chunks in Supabase (matches match_noc_chunks RPC schema)
  5. Optionally chunks NOC KB runbook files from noc_kb/

Requirements:
  - VOYAGE_API_KEY, SUPABASE_URL, SUPABASE_SERVICE_KEY set in .env or environment
  - noc_kb_chunks table must exist (run supabase_setup.sql first)
"""

from __future__ import annotations

import os
import sys
import textwrap
from pathlib import Path

# Load .env before anything else
from dotenv import load_dotenv
_BACKEND = Path(__file__).resolve().parent
load_dotenv(_BACKEND / ".env")

import yaml

VOYAGE_API_KEY       = os.environ.get("VOYAGE_API_KEY", "")
SUPABASE_URL         = os.environ.get("SUPABASE_URL", "")
SUPABASE_SERVICE_KEY = (
    os.environ.get("SUPABASE_SERVICE_KEY")
    or os.environ.get("SUPABASE_KEY", "")
)
VOYAGE_MODEL = "voyage-3"

_SCENARIOS_YAML = _BACKEND / "tests" / "ground_truth" / "scenarios.yaml"
_NOC_KB_DIR     = _BACKEND / "noc_kb"


# ── Chunk builders ─────────────────────────────────────────────────────


def _chunks_from_scenario(scn: dict) -> list[dict]:
    """
    Build one or two text chunks from a ground truth scenario.
    Multi-site scenarios (SCN-003) produce one chunk per site sub-key.
    """
    chunks: list[dict] = []

    def _make_chunk(alarm_id: str, alarm_name: str, section: str, content: str) -> dict:
        return {
            "alarm_id":   alarm_id,
            "alarm_name": alarm_name,
            "section":    section,
            "content":    content.strip(),
        }

    scn_id   = scn.get("id", "")
    scn_name = scn.get("name", "")

    # Detect multi-site scenario (SCN-003 has no top-level site_id; has site_atx_XXX sub-keys)
    # Only look for sub-keys when there is no top-level site_id to avoid matching expected_output.
    if scn.get("site_id"):
        site_keys = []
    else:
        site_keys = [
            k for k in scn
            if isinstance(scn[k], dict)
            and "site_id" in scn[k]
            and "oem" in scn[k]  # site config blocks have oem, topology, etc.
        ]

    if site_keys:
        # Multi-site: build one chunk per site
        for sk in site_keys:
            site_data = scn[sk]
            site_id   = site_data.get("site_id", sk)
            oem       = site_data.get("oem", "unknown")
            # expected output is a list; find entry for this site
            expected_list = scn.get("expected_output", [])
            expected = next(
                (e for e in expected_list if e.get("site_id") == site_id), {}
            )
            content = _build_chunk_text(scn_id, scn_name, oem, site_data, expected)
            chunks.append(_make_chunk(
                alarm_id   = f"{scn_id}-{site_id}",
                alarm_name = scn_name,
                section    = site_id,
                content    = content,
            ))
    else:
        # Single-site scenario
        oem      = scn.get("oem", "unknown")
        expected = scn.get("expected_output", {})
        content  = _build_chunk_text(scn_id, scn_name, oem, scn, expected)
        chunks.append(_make_chunk(
            alarm_id   = scn_id,
            alarm_name = scn_name,
            section    = "pattern_and_resolution",
            content    = content,
        ))

    return chunks


def _build_chunk_text(
    scn_id: str,
    scn_name: str,
    oem: str,
    site_data: dict,
    expected: dict,
) -> str:
    """Build the canonical text content for a knowledge base chunk."""
    br = expected.get("blast_radius", {})
    cascade   = expected.get("cascade_type", "UNKNOWN")
    root_type = expected.get("root_cause_type", "UNKNOWN")
    alarm_cat = expected.get("alarm_category", "UNKNOWN")
    severity  = expected.get("dominant_severity", "info")
    affected  = br.get("affected_equipment", [])
    carriers  = br.get("affected_carriers", [])
    bands     = br.get("affected_bands", [])
    impact    = br.get("service_impact", "")
    probable  = expected.get("probable_root_cause", "")
    priority  = expected.get("triage_priority", "P3")
    stray     = expected.get("stray_alarm", False)

    # Query fingerprint line (same format as _build_query_text in rag_pipeline.py)
    oems_str = oem
    equip_count = len(affected)
    fingerprint = (
        f"cascade={cascade} root_type={root_type} "
        f"alarm_category={alarm_cat} equip_count={equip_count} "
        f"oem={oems_str} severity={severity}"
    )

    return textwrap.dedent(f"""\
        SCENARIO: {scn_id} — {scn_name}
        OEM: {oem}
        FINGERPRINT: {fingerprint}
        PRIORITY: {priority}
        STRAY: {stray}

        PATTERN:
        Alarm category: {alarm_cat}
        Cascade type: {cascade}
        Root cause type: {root_type}
        Dominant severity: {severity}
        Affected equipment ({equip_count}): {', '.join(affected) or 'n/a'}
        Affected carriers: {', '.join(carriers) or 'n/a'}
        Affected bands: {', '.join(bands) or 'n/a'}

        PROBABLE ROOT CAUSE:
        {probable}

        SERVICE IMPACT:
        {impact}
    """)


def _chunks_from_kb_file(path: Path) -> list[dict]:
    """
    Parse a NOC KB runbook file (YAML frontmatter + markdown body) into chunks.
    Each ## section becomes its own chunk.
    """
    text = path.read_text(encoding="utf-8")
    chunks: list[dict] = []

    # Split YAML frontmatter from markdown body
    if text.startswith("---"):
        parts = text.split("---", 2)
        if len(parts) >= 3:
            try:
                fm = yaml.safe_load(parts[1]) or {}
            except yaml.YAMLError:
                fm = {}
            body = parts[2]
        else:
            fm, body = {}, text
    else:
        fm, body = {}, text

    alarm_id   = fm.get("alarm_id", path.stem)
    alarm_name = fm.get("alarm_name", path.stem)

    # Split body into sections by ## headings
    sections: list[tuple[str, str]] = []
    current_title, current_lines = "overview", []
    for line in body.splitlines():
        if line.startswith("## "):
            if current_lines:
                sections.append((current_title, "\n".join(current_lines).strip()))
            current_title = line[3:].strip().lower().replace(" ", "_")
            current_lines = []
        else:
            current_lines.append(line)
    if current_lines:
        sections.append((current_title, "\n".join(current_lines).strip()))

    for title, content in sections:
        if not content:
            continue
        chunks.append({
            "alarm_id":   alarm_id,
            "alarm_name": alarm_name,
            "section":    title,
            "content":    content,
        })

    return chunks


# ── Embedding + upsert ─────────────────────────────────────────────────


def _embed_batch(texts: list[str]) -> list[list[float]] | None:
    if not VOYAGE_API_KEY:
        print("  ERROR: VOYAGE_API_KEY not set.")
        return None
    try:
        import voyageai
        vo = voyageai.Client(api_key=VOYAGE_API_KEY)
        resp = vo.embed(texts, model=VOYAGE_MODEL)
        return resp.embeddings
    except Exception as exc:
        print(f"  ERROR: Voyage AI embed failed: {exc}")
        return None


def _upsert_chunks(chunks: list[dict], embeddings: list[list[float]]) -> int:
    """Upsert chunks into noc_kb_chunks. Returns number of rows inserted."""
    if not (SUPABASE_URL and SUPABASE_SERVICE_KEY):
        print("  ERROR: SUPABASE_URL or SUPABASE_SERVICE_KEY not set.")
        return 0
    try:
        from supabase import create_client
        sb = create_client(SUPABASE_URL, SUPABASE_SERVICE_KEY)

        rows = []
        for chunk, emb in zip(chunks, embeddings):
            rows.append({
                "alarm_id":   chunk["alarm_id"],
                "alarm_name": chunk["alarm_name"],
                "section":    chunk["section"],
                "content":    chunk["content"],
                "embedding":  emb,
            })

        # upsert on (alarm_id, section) — assumes unique constraint in schema
        sb.table("noc_kb_chunks").upsert(
            rows, on_conflict="alarm_id,section"
        ).execute()
        return len(rows)
    except Exception as exc:
        print(f"  ERROR: Supabase upsert failed: {exc}")
        print("  Hint: make sure noc_kb_chunks table exists (run supabase_setup.sql first).")
        return 0


# ── Main ───────────────────────────────────────────────────────────────


def main() -> None:
    print("=" * 60)
    print("NOC KB Vector Store Seeder")
    print("=" * 60)

    # ── 1. Build chunks from ground truth scenarios ────────────────────
    print("\n[1/4] Loading ground truth scenarios …")
    with open(_SCENARIOS_YAML, "r") as f:
        data = yaml.safe_load(f)
    scenarios = data.get("scenarios", [])

    scenario_chunks: list[dict] = []
    for scn in scenarios:
        new_chunks = _chunks_from_scenario(scn)
        scenario_chunks.extend(new_chunks)
        for c in new_chunks:
            print(f"  + {c['alarm_id']} / {c['section']}")

    print(f"  → {len(scenario_chunks)} scenario chunks")

    # ── 2. Build chunks from NOC KB runbook files ──────────────────────
    print("\n[2/4] Loading NOC KB runbook files …")
    kb_chunks: list[dict] = []
    if _NOC_KB_DIR.exists():
        for md_file in sorted(_NOC_KB_DIR.rglob("*.md")):
            file_chunks = _chunks_from_kb_file(md_file)
            kb_chunks.extend(file_chunks)
            print(f"  + {md_file.relative_to(_BACKEND)} → {len(file_chunks)} chunks")
    else:
        print(f"  noc_kb/ not found at {_NOC_KB_DIR} — skipping")

    print(f"  → {len(kb_chunks)} KB chunks")

    all_chunks = scenario_chunks + kb_chunks
    if not all_chunks:
        print("\nNo chunks to embed — exiting.")
        return

    # ── 3. Embed ───────────────────────────────────────────────────────
    print(f"\n[3/4] Embedding {len(all_chunks)} chunks with Voyage AI {VOYAGE_MODEL} …")
    texts = [c["content"] for c in all_chunks]
    embeddings = _embed_batch(texts)
    if embeddings is None:
        print("  Embedding failed — aborting.")
        sys.exit(1)
    print(f"  → {len(embeddings)} embeddings (dim={len(embeddings[0])})")

    # ── 4. Upsert to Supabase ──────────────────────────────────────────
    print("\n[4/4] Upserting to Supabase noc_kb_chunks …")
    inserted = _upsert_chunks(all_chunks, embeddings)
    if inserted:
        print(f"  → {inserted} rows upserted successfully.")
    else:
        print("  → 0 rows upserted (check errors above).")

    print("\nDone.")


if __name__ == "__main__":
    main()
