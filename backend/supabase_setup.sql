-- ============================================================
-- NOC Knowledge Base — Supabase Setup
-- Run this ONCE in the Supabase SQL editor before ingesting.
-- ============================================================

-- 1. Enable pgvector
create extension if not exists vector;

-- 2. Create the chunks table
drop table if exists noc_kb_chunks;

create table noc_kb_chunks (
    id            bigserial primary key,
    alarm_id      text,          -- e.g. INT-001, EXT-002, OPS-003
    category      text,          -- internal | external | ops_guide | metadata
    subcategory   text,          -- remote_unit | poi_signal | rf_performance | etc.
    severity      text,          -- critical | major | minor
    alarm_name    text,          -- human-readable alarm name
    tags          text[],        -- array of keyword tags for debugging
    section       text,          -- which section of the runbook this chunk came from
    chunk_index   integer,       -- 0-based index if a section was split further
    content       text not null, -- the actual text the LLM will read
    token_count   integer,       -- tokens in this chunk
    source_file   text,          -- original filename for traceability
    embedding     vector(1024)   -- voyage-3 produces 1024-dim vectors
);

-- 3. Vector similarity index (IVFFlat — fast approximate search)
--    lists = 50 is appropriate for ~200 chunks; increase to 100 for >1000 chunks
create index on noc_kb_chunks using ivfflat (embedding vector_cosine_ops)
  with (lists = 50);

-- 4. Metadata filter indexes
create index on noc_kb_chunks (category);
create index on noc_kb_chunks (severity);
create index on noc_kb_chunks (alarm_id);
create index on noc_kb_chunks (subcategory);

-- ============================================================
-- 5. Retrieval function
--    Called by the RAG agent with an embedded query vector.
--    Supports optional metadata pre-filtering before vector search
--    (filter by category and/or severity).
--
--    Example calls from Python:
--      supabase.rpc("match_noc_chunks", {
--          "query_embedding": [...],
--          "match_count": 5,
--          "filter_category": "internal",
--          "filter_severity": null
--      })
-- ============================================================

create or replace function match_noc_chunks (
    query_embedding vector(1024),
    match_count     int     default 5,
    filter_category text    default null,
    filter_severity text    default null
)
returns table (
    id          bigint,
    alarm_id    text,
    category    text,
    subcategory text,
    severity    text,
    alarm_name  text,
    section     text,
    content     text,
    similarity  float
)
language sql stable
as $$
    select
        id,
        alarm_id,
        category,
        subcategory,
        severity,
        alarm_name,
        section,
        content,
        1 - (embedding <=> query_embedding) as similarity
    from noc_kb_chunks
    where
        (filter_category is null or category = filter_category)
        and (filter_severity is null or severity = filter_severity)
    order by embedding <=> query_embedding
    limit match_count;
$$;

-- ============================================================
-- 6. Handy verification queries (run after ingestion)
-- ============================================================

-- Count chunks by category:
-- select category, count(*) from noc_kb_chunks group by category order by category;

-- Count chunks by alarm_id:
-- select alarm_id, alarm_name, count(*) as chunks
-- from noc_kb_chunks group by alarm_id, alarm_name order by alarm_id;

-- Check token distribution:
-- select min(token_count), max(token_count), avg(token_count)::int
-- from noc_kb_chunks;
