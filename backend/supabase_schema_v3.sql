-- ============================================================
-- NOC Triage Agent v3 — Supabase Schema
-- Run this ONCE in the Supabase SQL editor before using the API.
--
-- Tables:
--   canonical_alarms  — normalized alarm records (one row per alarm)
--   site_events       — aggregated site events (one row per site+zone group)
--   triage_results    — correlation output (one row per site event)
-- ============================================================

-- ── canonical_alarms ──────────────────────────────────────────────────
-- Stores every alarm after OEM normalization.
-- Multiple alarms belong to one site_event (linked by run_id + site_id + zone_id).

create table if not exists canonical_alarms (
    id                      bigserial primary key,
    run_id                  uuid not null,           -- groups all rows from one /triage call
    raw_alarm_ref           text not null,           -- original alarm_id from the OEM
    site_id                 text not null,
    zone_id                 text not null,
    site_name               text,
    alarm_name              text,
    alarm_code              text,
    alarm_category          text,                    -- TDD_SYNC_LOST | ELEMENT_OFFLINE | etc.
    source_equipment_type   text,                    -- REMOTE | OPTICAL_MODULE | MAIN_HUB | EXPANSION_HUB | POI
    source_equipment_id     text,
    parent_equipment_id     text,
    severity                text,                    -- critical | major | minor | warning | info
    das_oem                 text,                    -- stratum | orion
    alarm_timestamp         timestamptz,
    created_at              timestamptz default now()
);

create index if not exists idx_canonical_alarms_run_id    on canonical_alarms (run_id);
create index if not exists idx_canonical_alarms_site      on canonical_alarms (site_id, zone_id);
create index if not exists idx_canonical_alarms_category  on canonical_alarms (alarm_category);
create index if not exists idx_canonical_alarms_severity  on canonical_alarms (severity);


-- ── site_events ───────────────────────────────────────────────────────
-- One row per site+zone aggregation produced by the ingestion agent.

create table if not exists site_events (
    id                          bigserial primary key,
    run_id                      uuid not null,
    site_id                     text not null,
    zone_id                     text not null,
    site_name                   text,
    alarm_count                 integer not null default 0,
    dominant_severity           text,                -- critical | major | minor | warning | info
    alarm_category              text,                -- dominant category across all alarms in event
    aggregated                  boolean not null default false,
    stray_alarm                 boolean not null default false,
    das_oems                    text[],              -- e.g. {stratum} or {orion} or {stratum,orion}
    aggregation_window_start    timestamptz,
    aggregation_window_end      timestamptz,
    normalization_applied       boolean not null default true,
    created_at                  timestamptz default now()
);

create index if not exists idx_site_events_run_id   on site_events (run_id);
create index if not exists idx_site_events_site      on site_events (site_id, zone_id);
create index if not exists idx_site_events_priority  on site_events (dominant_severity);
create index if not exists idx_site_events_category  on site_events (alarm_category);


-- ── triage_results ────────────────────────────────────────────────────
-- One row per site event: the full correlation + triage output.

create table if not exists triage_results (
    id                      bigserial primary key,
    run_id                  uuid not null,
    site_id                 text not null,
    zone_id                 text not null,
    site_name               text,
    alarm_count             integer not null default 0,
    dominant_severity       text,
    alarm_category          text,
    cascade_type            text,                    -- OPTICAL_CASCADE | SYNC_CASCADE | POWER_CASCADE | HUB_CASCADE | STRAY
    root_cause_node         text,                    -- equipment ID of the root cause
    root_cause_type         text,                    -- canonical equipment type of root cause
    probable_root_cause     text,                    -- human-readable root cause narrative
    affected_equipment      text[],                  -- ordered list of affected equipment IDs
    affected_carriers       text[],
    affected_bands          text[],
    service_impact          text,                    -- service impact narrative
    triage_priority         text,                    -- P1 | P2 | P3 | P4 | P5
    recommended_action      text,
    correlated_alarm_refs   text[],                  -- raw_alarm_ref of all correlated alarms
    stray_alarm             boolean not null default false,
    aggregated              boolean not null default false,
    aggregation_window_start timestamptz,
    aggregation_window_end   timestamptz,
    das_oems                text[],
    created_at              timestamptz default now()
);

create index if not exists idx_triage_results_run_id    on triage_results (run_id);
create index if not exists idx_triage_results_site       on triage_results (site_id, zone_id);
create index if not exists idx_triage_results_priority   on triage_results (triage_priority);
create index if not exists idx_triage_results_cascade    on triage_results (cascade_type);
create index if not exists idx_triage_results_created    on triage_results (created_at desc);


-- ============================================================
-- Verification queries (run after inserting test data)
-- ============================================================

-- Count results by triage priority:
-- select triage_priority, count(*) from triage_results group by triage_priority order by triage_priority;

-- Most recent triage runs:
-- select run_id, site_id, zone_id, triage_priority, cascade_type, created_at
-- from triage_results order by created_at desc limit 20;

-- Alarms per severity in last run:
-- select severity, count(*) from canonical_alarms
-- where run_id = '<run_id>' group by severity order by severity;
