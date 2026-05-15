import React, { useState, useEffect, useCallback, useRef } from 'react';
import FlowContainer from './FlowContainer';
import TriageTerminal from './TriageTerminal';

const API = process.env.REACT_APP_API_URL || 'http://localhost:8000';

const SITES = [
  { id: 'SITE-ATX-001', name: 'Austin Domain Tower',   shortName: 'ATX-001', oem: 'STRATUM' },
  { id: 'SITE-ATX-002', name: 'Austin Midtown Plaza',  shortName: 'ATX-002', oem: 'ORION'   },
  { id: 'SITE-ATX-003', name: 'Austin Rainey Street',  shortName: 'ATX-003', oem: 'STRATUM' },
  { id: 'SITE-ATX-004', name: 'Austin South Congress', shortName: 'ATX-004', oem: 'ORION'   },
];

const SITE_SCENARIOS = {
  'SITE-ATX-001': { id: 'SCN-001', label: 'Optical Link Cascade',          color: '#33b1ff' },
  'SITE-ATX-002': { id: 'SCN-002', label: 'Sync Loss + Normalization',     color: '#f1c21b' },
  'SITE-ATX-003': { id: 'SCN-003', label: 'Power Failure — Multi-carrier', color: '#fa4d56' },
  'SITE-ATX-004': { id: 'SCN-004', label: 'POI Signal Loss — Meridian B4', color: '#be95ff' },
};

const SEV_COLOR = {
  critical: '#fa4d56',
  major:    '#ff832b',
  minor:    '#f1c21b',
  warning:  '#a8a8a8',
  info:     '#6f6f6f',
};

const PRIO_COLOR = { P1: '#fa4d56', P2: '#ff832b', P3: '#f1c21b', P4: '#42be65', P5: '#6f6f6f' };

function OemBadge({ oem }) {
  const isStratum = oem === 'STRATUM' || oem === 'stratum';
  return (
    <span style={{
      background: isStratum ? '#0d3d3d' : '#0d2d4a',
      color: isStratum ? '#3ddbd9' : '#33b1ff',
      fontSize: 9,
      padding: '2px 5px',
      fontFamily: "'JetBrains Mono', monospace",
      letterSpacing: 0.5,
    }}>
      {String(oem).toUpperCase()}
    </span>
  );
}

function SevBadge({ sev }) {
  const col = SEV_COLOR[sev] || '#6f6f6f';
  return (
    <span style={{
      background: col + '22',
      border: `1px solid ${col}`,
      color: col,
      fontSize: 9,
      padding: '1px 5px',
      letterSpacing: 0.5,
      minWidth: 52,
      display: 'inline-block',
      textAlign: 'center',
    }}>
      {String(sev).toUpperCase()}
    </span>
  );
}

export default function App() {
  const [activeSite, setActiveSite]           = useState('SITE-ATX-001');
  const [topology, setTopology]               = useState(null);
  const [incidents, setIncidents]             = useState([]);
  const [primaryIncident, setPrimaryIncident] = useState(null);
  const [triageBrief, setTriageBrief]         = useState('');
  const [loading, setLoading]                 = useState(false);
  const [activeScenario, setActiveScenario]   = useState(null);
  const [error, setError]                     = useState('');
  const [ingestionMeta, setIngestionMeta]     = useState(null);
  const [siteAlarmStatus, setSiteAlarmStatus] = useState({
    'SITE-ATX-001': false,
    'SITE-ATX-002': false,
    'SITE-ATX-003': false,
    'SITE-ATX-004': false,
  });

  // Pipeline animation state
  const [allAlarms, setAllAlarms]           = useState([]);   // flat alarm list from site_events
  const [visibleCount, setVisibleCount]     = useState(0);    // how many alarms shown in Panel 1
  const [siteEvents, setSiteEvents]         = useState([]);   // for Panel 2
  const [triageResults, setTriageResults]   = useState([]);   // for Panel 3 detail
  const [phase, setPhase]                   = useState('idle'); // idle|streaming|normalizing|done
  const timerRefs = useRef([]);

  // Fetch topology on site change
  useEffect(() => {
    setTopology(null);
    setIncidents([]);
    setPrimaryIncident(null);
    setTriageBrief('');
    setActiveScenario(null);
    setIngestionMeta(null);
    setError('');
    resetPipeline();

    fetch(`${API}/triage/topology?site_id=${activeSite}`)
      .then(r => {
        if (!r.ok) throw new Error(`HTTP ${r.status}`);
        return r.json();
      })
      .then(setTopology)
      .catch(() => setError('Backend not reachable — start FastAPI on port 8000'));
  }, [activeSite]); // eslint-disable-line react-hooks/exhaustive-deps

  function resetPipeline() {
    timerRefs.current.forEach(clearTimeout);
    timerRefs.current = [];
    setPhase('idle');
    setAllAlarms([]);
    setVisibleCount(0);
    setSiteEvents([]);
    setTriageResults([]);
  }

  // Drive the streaming animation
  useEffect(() => {
    if (phase !== 'streaming' || allAlarms.length === 0) return;

    timerRefs.current.forEach(clearTimeout);
    timerRefs.current = [];

    const timers = [];
    allAlarms.forEach((_, i) => {
      timers.push(setTimeout(() => setVisibleCount(i + 1), i * 300));
    });
    // After all alarms shown, reveal Panel 2
    timers.push(setTimeout(() => setPhase('normalizing'), allAlarms.length * 300 + 200));
    // After short pause, reveal Panel 3
    timers.push(setTimeout(() => setPhase('done'), allAlarms.length * 300 + 800));

    timerRefs.current = timers;
    return () => timers.forEach(clearTimeout);
  }, [phase, allAlarms]);

  const runScenario = useCallback(async () => {
    const scn = SITE_SCENARIOS[activeSite];
    if (!scn) return;

    resetPipeline();
    setLoading(true);
    setActiveScenario(scn.id);
    setIncidents([]);
    setPrimaryIncident(null);
    setTriageBrief('');
    setIngestionMeta(null);
    setError('');

    try {
      const res = await fetch(`${API}/triage/simulate`, {
        method: 'POST',
        headers: { 'Content-Type': 'application/json' },
        body: JSON.stringify({ scenario: scn.id, site_id: activeSite }),
      });
      if (!res.ok) {
        const errData = await res.json().catch(() => ({}));
        throw new Error(errData.detail || `HTTP ${res.status}`);
      }
      const data = await res.json();

      setIncidents(data.incidents || []);
      setPrimaryIncident(data.primary_incident || null);
      setTriageBrief(data.triage_brief || '');
      setIngestionMeta(data.ingestion_meta || null);
      setSiteAlarmStatus(prev => ({ ...prev, [activeSite]: true }));

      const events = data.site_events || [];
      setSiteEvents(events);
      setTriageResults(data.results || []);

      // Build flat alarm list for Panel 1 animation
      const flat = events.flatMap(ev => ev.alarm_list || []);
      setAllAlarms(flat);
      setVisibleCount(0);
      setPhase('streaming');
    } catch (e) {
      setError(`Simulation failed: ${e.message}`);
    } finally {
      setLoading(false);
    }
  }, [activeSite]);

  const resetAll = () => {
    resetPipeline();
    setIncidents([]);
    setPrimaryIncident(null);
    setTriageBrief('');
    setActiveScenario(null);
    setError('');
    setIngestionMeta(null);
    setSiteAlarmStatus({
      'SITE-ATX-001': false,
      'SITE-ATX-002': false,
      'SITE-ATX-003': false,
      'SITE-ATX-004': false,
    });
  };

  const currentSite = SITES.find(s => s.id === activeSite);
  const currentScn  = SITE_SCENARIOS[activeSite];

  // Flatten first site_event's normalization data for Panel 2
  const firstEvent      = siteEvents[0] || null;
  const fieldMappings   = firstEvent?.field_mappings_resolved || [];
  const severityGaps    = firstEvent?.severity_gaps_resolved || [];
  const aggWindow       = firstEvent
    ? `${firstEvent.aggregation_window_start?.slice(11, 19) || ''} → ${firstEvent.aggregation_window_end?.slice(11, 19) || ''}`
    : '';

  // Primary triage result for Panel 3 detail
  const primaryResult = triageResults.length > 0
    ? triageResults.reduce((a, b) =>
        (parseInt(a.triage_priority?.[1] || 9) <= parseInt(b.triage_priority?.[1] || 9) ? a : b)
      )
    : null;

  return (
    <div style={{
      display: 'flex',
      flexDirection: 'column',
      height: '100vh',
      background: '#161616',
      color: '#f4f4f4',
      fontFamily: "'JetBrains Mono', monospace",
    }}>
      <style>{`
        @import url('https://fonts.googleapis.com/css2?family=JetBrains+Mono:wght@400;700&display=swap');
        * { box-sizing: border-box; margin: 0; padding: 0; }
        body { background: #161616; }
        ::-webkit-scrollbar { width: 5px; }
        ::-webkit-scrollbar-track { background: #1c1c1c; }
        ::-webkit-scrollbar-thumb { background: #33b1ff44; border-radius: 3px; }
        .site-btn {
          background: transparent;
          border: none;
          border-bottom: 2px solid transparent;
          color: #6f6f6f;
          padding: 6px 14px;
          cursor: pointer;
          font-family: 'JetBrains Mono', monospace;
          font-size: 11px;
          display: flex;
          align-items: center;
          gap: 7px;
          transition: all 0.15s;
          height: 100%;
        }
        .site-btn:hover { color: #c6c6c6; }
        .site-btn.active { color: #f4f4f4; border-bottom-color: #33b1ff; }
        .run-btn {
          background: #0f3a5a;
          border: 1px solid #33b1ff;
          color: #33b1ff;
          padding: 7px 16px;
          cursor: pointer;
          font-family: 'JetBrains Mono', monospace;
          font-size: 11px;
          font-weight: 700;
          letter-spacing: 1px;
          transition: all 0.15s;
        }
        .run-btn:hover:not(:disabled) { background: #1a4a6a; }
        .run-btn:disabled { opacity: 0.4; cursor: not-allowed; }
        .reset-btn {
          background: transparent;
          border: 1px solid #393939;
          color: #a8a8a8;
          padding: 7px 12px;
          cursor: pointer;
          font-family: 'JetBrains Mono', monospace;
          font-size: 11px;
          transition: all 0.15s;
        }
        .reset-btn:hover { border-color: #6f6f6f; color: #f4f4f4; }
        .alarm-row {
          padding: 7px 10px;
          border-bottom: 1px solid #1c1c1c;
          animation: fadeIn 0.25s ease-in;
        }
        @keyframes fadeIn { from { opacity: 0; transform: translateY(4px); } to { opacity: 1; transform: none; } }
        .panel-label {
          font-size: 9px;
          letter-spacing: 2px;
          color: #525252;
          padding: 6px 12px;
          background: #1a1a1a;
          border-bottom: 1px solid #2a2a2a;
          text-transform: uppercase;
        }
      `}</style>

      {/* ── Top Bar ── */}
      <div style={{
        display: 'flex',
        alignItems: 'center',
        padding: '0 20px',
        background: '#1c1c1c',
        borderBottom: '1px solid #393939',
        gap: 0,
        flexShrink: 0,
        height: 52,
      }}>
        {/* Logo */}
        <div style={{ display: 'flex', alignItems: 'center', gap: 10, paddingRight: 20, borderRight: '1px solid #393939', height: '100%' }}>
          <span style={{ fontSize: 20 }}>🛰️</span>
          <div>
            <div style={{ color: '#33b1ff', fontWeight: 700, fontSize: 13, letterSpacing: 3 }}>NOC TRIAGE AGENT</div>
            <div style={{ color: '#6f6f6f', fontSize: 10, letterSpacing: 2 }}>DIGITAL TWIN · PHASE 3</div>
          </div>
        </div>

        {/* Site selector */}
        <div style={{ display: 'flex', alignItems: 'stretch', height: '100%', borderRight: '1px solid #393939' }}>
          {SITES.map(site => (
            <button
              key={site.id}
              className={`site-btn ${activeSite === site.id ? 'active' : ''}`}
              onClick={() => setActiveSite(site.id)}
            >
              <span style={{
                width: 7, height: 7, borderRadius: '50%',
                background: siteAlarmStatus[site.id] ? '#fa4d56' : '#42be65',
                display: 'inline-block', flexShrink: 0,
              }} />
              {site.shortName}
              <OemBadge oem={site.oem} />
            </button>
          ))}
        </div>

        {/* Scenario label */}
        {currentScn && (
          <div style={{ paddingLeft: 16, fontSize: 11, color: currentScn.color }}>
            {currentScn.label}
          </div>
        )}

        <div style={{ flex: 1 }} />

        {/* Active scenario indicator */}
        {activeScenario && (
          <span style={{ fontSize: 10, color: '#ff832b', marginRight: 16 }}>
            {activeScenario} {phase === 'streaming' ? '▶ STREAMING' : phase === 'normalizing' ? '▶ NORMALIZING' : phase === 'done' ? '✓ DONE' : ''}
          </span>
        )}

        {/* Error banner */}
        {error && (
          <div style={{ background: '#2a0e0e', border: '0.5px solid #fa4d56', color: '#ff8389', padding: '4px 10px', fontSize: 10, marginRight: 12 }}>
            ⚠ {error}
          </div>
        )}

        {/* Buttons */}
        <div style={{ display: 'flex', gap: 8 }}>
          <button
            className="run-btn"
            onClick={runScenario}
            disabled={loading || !currentScn}
          >
            {loading ? '▶ RUNNING...' : '▶ RUN SCENARIO'}
          </button>
          <button className="reset-btn" onClick={resetAll}>↺ RESET</button>
        </div>
      </div>

      {/* ── 3-Panel Main Layout ── */}
      <div style={{ display: 'flex', flex: 1, overflow: 'hidden' }}>

        {/* ── Panel 1: Raw Alarm Feed (25%) ── */}
        <div style={{
          width: '25%',
          borderRight: '1px solid #2a2a2a',
          display: 'flex',
          flexDirection: 'column',
          overflow: 'hidden',
          background: '#141414',
        }}>
          <div className="panel-label">
            RAW ALARM FEED
            {allAlarms.length > 0 && (
              <span style={{ color: '#33b1ff', marginLeft: 8 }}>
                {visibleCount}/{allAlarms.length}
              </span>
            )}
          </div>

          <div style={{ flex: 1, overflowY: 'auto' }}>
            {allAlarms.length === 0 && phase === 'idle' ? (
              <div style={{ padding: 16, color: '#393939', fontSize: 11, textAlign: 'center', marginTop: 40 }}>
                No alarms — run a scenario
              </div>
            ) : (
              allAlarms.slice(0, visibleCount).map((alarm, i) => (
                <div key={alarm.raw_alarm_ref || i} className="alarm-row">
                  <div style={{ display: 'flex', alignItems: 'center', gap: 6, marginBottom: 4 }}>
                    <SevBadge sev={alarm.severity} />
                    <span style={{ color: '#a8a8a8', fontSize: 9 }}>
                      {alarm.das_oem?.toUpperCase()}
                    </span>
                  </div>
                  <div style={{ fontSize: 11, color: '#f4f4f4', marginBottom: 2 }}>
                    <span style={{ color: '#33b1ff' }}>{alarm.source_equipment_id}</span>
                    <span style={{ color: '#525252', fontSize: 9 }}> [{alarm.source_equipment_type}]</span>
                  </div>
                  <div style={{ fontSize: 10, color: '#a8a8a8', marginBottom: 2 }}>
                    {alarm.alarm_name}
                  </div>
                  <div style={{ fontSize: 9, color: '#525252' }}>
                    {alarm.timestamp?.slice(11, 19) || ''}
                  </div>
                </div>
              ))
            )}
          </div>
        </div>

        {/* ── Panel 2: Ingestion Agent (35%) ── */}
        <div style={{
          width: '35%',
          borderRight: '1px solid #2a2a2a',
          display: 'flex',
          flexDirection: 'column',
          overflow: 'hidden',
          background: '#131313',
          opacity: (phase === 'normalizing' || phase === 'done') ? 1 : 0.25,
          transition: 'opacity 0.4s ease',
        }}>
          <div className="panel-label">
            INGESTION AGENT
            {firstEvent && (
              <span style={{ color: '#a8a8a8', marginLeft: 8 }}>
                <OemBadge oem={(firstEvent.das_oems || [])[0] || 'stratum'} />
              </span>
            )}
          </div>

          <div style={{ flex: 1, overflowY: 'auto', padding: '12px 14px' }}>
            {(phase !== 'normalizing' && phase !== 'done') ? (
              <div style={{ color: '#393939', fontSize: 11, textAlign: 'center', marginTop: 40 }}>
                Waiting for alarms...
              </div>
            ) : (
              <>
                {/* Field Mappings */}
                {fieldMappings.length > 0 && (
                  <div style={{ marginBottom: 14 }}>
                    <div style={{ color: '#525252', fontSize: 9, letterSpacing: 2, marginBottom: 8 }}>
                      FIELD MAPPINGS
                    </div>
                    {fieldMappings.map((fm, i) => {
                      const left  = fm.oem_field || '';
                      const mid   = fm.oem_value ? ` (${fm.oem_value})` : '';
                      const right = fm.canonical_field || fm.canonical_value || '';
                      return (
                        <div key={i} style={{ fontSize: 10, color: '#a8a8a8', marginBottom: 4, paddingLeft: 8 }}>
                          <span style={{ color: '#ff832b' }}>{left}{mid}</span>
                          <span style={{ color: '#525252', margin: '0 6px' }}>→</span>
                          <span style={{ color: '#42be65' }}>{right}</span>
                        </div>
                      );
                    })}
                  </div>
                )}

                {/* Severity Gaps */}
                {severityGaps.length > 0 && (
                  <div style={{ marginBottom: 14 }}>
                    <div style={{ color: '#525252', fontSize: 9, letterSpacing: 2, marginBottom: 8 }}>
                      SEVERITY GAPS
                    </div>
                    {severityGaps.map((sg, i) => (
                      <div key={i} style={{ fontSize: 10, color: '#a8a8a8', marginBottom: 6, paddingLeft: 8 }}>
                        <div>
                          <span style={{ color: '#f1c21b' }}>{sg.alarm_id}</span>
                          <span style={{ color: '#525252' }}> arrived_as </span>
                          <span style={{ color: '#ff832b' }}>{sg.arrived_as}</span>
                          <span style={{ color: '#525252' }}> → </span>
                          <span style={{ color: '#42be65' }}>{sg.canonical_severity}</span>
                        </div>
                        {sg.note && (
                          <div style={{ color: '#393939', fontSize: 9, marginTop: 2 }}>{sg.note}</div>
                        )}
                      </div>
                    ))}
                  </div>
                )}

                {/* Aggregation results per site event */}
                <div style={{ color: '#525252', fontSize: 9, letterSpacing: 2, marginBottom: 8 }}>
                  AGGREGATION OUTPUT
                </div>
                {siteEvents.map((ev, i) => {
                  const isAgg  = ev.aggregated;
                  const isStray = ev.stray_alarm;
                  const badge  = isAgg ? 'AGGREGATED' : isStray ? 'STRAY' : 'SINGLE';
                  const bColor = isAgg ? '#42be65' : isStray ? '#f1c21b' : '#a8a8a8';
                  return (
                    <div key={i} style={{
                      background: '#1a1a1a',
                      border: '1px solid #2a2a2a',
                      padding: '10px 12px',
                      marginBottom: 8,
                    }}>
                      <div style={{ display: 'flex', justifyContent: 'space-between', marginBottom: 6 }}>
                        <span style={{ color: '#f4f4f4', fontSize: 11 }}>
                          {ev.site_id} · {ev.zone_id}
                        </span>
                        <span style={{
                          fontSize: 9, padding: '1px 6px',
                          border: `1px solid ${bColor}`,
                          color: bColor,
                        }}>
                          {badge}
                        </span>
                      </div>
                      <div style={{ fontSize: 10, color: '#a8a8a8' }}>
                        <span style={{ color: SEV_COLOR[ev.dominant_severity] || '#6f6f6f' }}>
                          {ev.dominant_severity?.toUpperCase()}
                        </span>
                        <span style={{ color: '#525252', margin: '0 8px' }}>·</span>
                        {ev.alarm_count} alarm{ev.alarm_count !== 1 ? 's' : ''}
                        <span style={{ color: '#525252', margin: '0 8px' }}>·</span>
                        {ev.alarm_category}
                      </div>
                      {aggWindow && (
                        <div style={{ fontSize: 9, color: '#525252', marginTop: 4 }}>
                          window: {aggWindow}
                        </div>
                      )}
                    </div>
                  );
                })}
              </>
            )}
          </div>
        </div>

        {/* ── Panel 3: Triage Result (40%) ── */}
        <div style={{
          width: '40%',
          display: 'flex',
          flexDirection: 'column',
          overflow: 'hidden',
          background: '#121212',
          opacity: phase === 'done' ? 1 : 0.15,
          transition: 'opacity 0.5s ease',
        }}>
          <div className="panel-label">
            TRIAGE RESULT
            {primaryResult && (
              <span style={{ marginLeft: 8 }}>
                <span style={{
                  color: PRIO_COLOR[primaryResult.triage_priority] || '#6f6f6f',
                  fontWeight: 700,
                }}>
                  {primaryResult.triage_priority}
                </span>
                <span style={{ color: '#393939' }}> · </span>
                <span style={{ color: '#525252' }}>{primaryResult.cascade_type}</span>
              </span>
            )}
          </div>

          <div style={{ flex: 1, overflowY: 'auto', display: 'flex', flexDirection: 'column' }}>
            {phase !== 'done' ? (
              <div style={{ padding: 16, color: '#393939', fontSize: 11, textAlign: 'center', marginTop: 40 }}>
                Awaiting correlation output...
              </div>
            ) : primaryResult ? (
              <>
                {/* Priority badge + root cause header */}
                <div style={{ padding: '14px 16px', borderBottom: '1px solid #1c1c1c' }}>
                  <div style={{ display: 'flex', alignItems: 'center', gap: 12, marginBottom: 10 }}>
                    <div style={{
                      fontSize: 28, fontWeight: 700, letterSpacing: 2,
                      color: PRIO_COLOR[primaryResult.triage_priority] || '#6f6f6f',
                      background: (PRIO_COLOR[primaryResult.triage_priority] || '#6f6f6f') + '18',
                      border: `2px solid ${PRIO_COLOR[primaryResult.triage_priority] || '#6f6f6f'}`,
                      padding: '4px 14px',
                    }}>
                      {primaryResult.triage_priority}
                    </div>
                    <div>
                      <div style={{ color: '#33b1ff', fontSize: 12, fontWeight: 700 }}>
                        {primaryResult.cascade_type?.replace(/_/g, ' ')}
                      </div>
                      <div style={{ color: '#6f6f6f', fontSize: 10 }}>
                        Root cause: <span style={{ color: '#f4f4f4' }}>{primaryResult.root_cause_node}</span>
                        <span style={{ color: '#525252' }}> [{primaryResult.root_cause_type}]</span>
                      </div>
                    </div>
                  </div>

                  {/* Probable root cause */}
                  <div style={{ fontSize: 11, color: '#a8a8a8', lineHeight: 1.6 }}>
                    {primaryResult.probable_root_cause}
                  </div>
                </div>

                {/* Blast radius */}
                {primaryResult.blast_radius && (
                  <div style={{ padding: '10px 16px', borderBottom: '1px solid #1c1c1c' }}>
                    <div style={{ color: '#525252', fontSize: 9, letterSpacing: 2, marginBottom: 8 }}>BLAST RADIUS</div>
                    <div style={{ fontSize: 10, color: '#a8a8a8', marginBottom: 4 }}>
                      <span style={{ color: '#525252' }}>Equipment: </span>
                      {(primaryResult.blast_radius.affected_equipment || []).join(', ')}
                    </div>
                    <div style={{ fontSize: 10, color: '#a8a8a8', marginBottom: 4 }}>
                      <span style={{ color: '#525252' }}>Carriers: </span>
                      {(primaryResult.blast_radius.affected_carriers || []).join(', ')}
                    </div>
                    <div style={{ fontSize: 10, color: '#a8a8a8', marginBottom: 4 }}>
                      <span style={{ color: '#525252' }}>Bands: </span>
                      {(primaryResult.blast_radius.affected_bands || []).join(', ')}
                    </div>
                    <div style={{ fontSize: 10, color: '#ff832b', marginTop: 6 }}>
                      {primaryResult.blast_radius.service_impact}
                    </div>
                  </div>
                )}

                {/* Recommended action */}
                {primaryResult.recommended_action && (
                  <div style={{ padding: '10px 16px', borderBottom: '1px solid #1c1c1c' }}>
                    <div style={{ color: '#525252', fontSize: 9, letterSpacing: 2, marginBottom: 6 }}>RECOMMENDED ACTION</div>
                    <div style={{ fontSize: 10, color: '#a8a8a8', lineHeight: 1.6 }}>
                      {primaryResult.recommended_action}
                    </div>
                  </div>
                )}

                {/* Mini topology — FlowContainer */}
                {topology && incidents.length > 0 && (
                  <div style={{ flex: 1, minHeight: 180, borderTop: '1px solid #1c1c1c', overflow: 'hidden' }}>
                    <div style={{ color: '#525252', fontSize: 9, letterSpacing: 2, padding: '6px 12px', background: '#1a1a1a' }}>
                      TOPOLOGY
                    </div>
                    <div style={{ height: 'calc(100% - 28px)' }}>
                      <FlowContainer topology={topology} incidents={incidents} />
                    </div>
                  </div>
                )}
              </>
            ) : (
              <div style={{ padding: 16, color: '#525252', fontSize: 11, textAlign: 'center', marginTop: 40 }}>
                No triage result available.
              </div>
            )}
          </div>
        </div>

      </div>
    </div>
  );
}
