import React, { useState, useEffect, useCallback } from 'react';
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
  'SITE-ATX-001': [{ id: 'SCN-001', label: 'Optical Link Cascade',          description: 'OM-1 — 5 alarms · Stratum',    color: '#33b1ff' }],
  'SITE-ATX-002': [{ id: 'SCN-002', label: 'Sync Loss + Normalization',     description: 'MH-01 — 4 alarms · Orion',     color: '#f1c21b' }],
  'SITE-ATX-003': [{ id: 'SCN-003', label: 'Power Failure — Multi-carrier', description: 'MU-01 — 5 alarms · Stratum',   color: '#fa4d56' }],
  'SITE-ATX-004': [{ id: 'SCN-003', label: 'Stray Alarm Detection',         description: 'RAU-03 — 1 alarm · Orion',     color: '#42be65' }],
};

function OemBadge({ oem }) {
  const isStratum = oem === 'STRATUM';
  return (
    <span style={{
      background: isStratum ? '#0d3d3d' : '#0d2d4a',
      color: isStratum ? '#3ddbd9' : '#33b1ff',
      fontSize: 9,
      padding: '2px 5px',
      fontFamily: "'JetBrains Mono', monospace",
      letterSpacing: 0.5,
    }}>
      {oem}
    </span>
  );
}

export default function App() {
  const [activeSite, setActiveSite]             = useState('SITE-ATX-001');
  const [topology, setTopology]                 = useState(null);
  const [incidents, setIncidents]               = useState([]);
  const [primaryIncident, setPrimaryIncident]   = useState(null);
  const [triageBrief, setTriageBrief]           = useState('');
  const [loading, setLoading]                   = useState(false);
  const [activeScenario, setActiveScenario]     = useState(null);
  const [error, setError]                       = useState('');
  const [ingestionMeta, setIngestionMeta]       = useState(null);
  const [siteAlarmStatus, setSiteAlarmStatus]   = useState({
    'SITE-ATX-001': false,
    'SITE-ATX-002': false,
    'SITE-ATX-003': false,
    'SITE-ATX-004': false,
  });
  const [ingestionExpanded, setIngestionExpanded] = useState(false);

  // Fetch topology whenever activeSite changes
  useEffect(() => {
    setTopology(null);
    setIncidents([]);
    setPrimaryIncident(null);
    setTriageBrief('');
    setActiveScenario(null);
    setIngestionMeta(null);
    setError('');

    fetch(`${API}/triage/topology?site_id=${activeSite}`)
      .then(r => {
        if (!r.ok) throw new Error(`HTTP ${r.status}`);
        return r.json();
      })
      .then(setTopology)
      .catch(() => setError('Backend not reachable — start FastAPI on port 8000'));
  }, [activeSite]);

  const runScenario = useCallback(async (scenarioId) => {
    setLoading(true);
    setActiveScenario(scenarioId);
    setTriageBrief('');
    setIncidents([]);
    setPrimaryIncident(null);
    setIngestionMeta(null);
    setError('');
    try {
      const res = await fetch(`${API}/triage/simulate`, {
        method: 'POST',
        headers: { 'Content-Type': 'application/json' },
        body: JSON.stringify({ scenario: scenarioId, site_id: activeSite }),
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
    } catch (e) {
      console.error('Simulation error:', e);
      setError(`Simulation failed: ${e.message}`);
    } finally {
      setLoading(false);
    }
  }, [activeSite]);

  const resetAll = () => {
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
  const currentScenarios = SITE_SCENARIOS[activeSite] || [];

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
        ::-webkit-scrollbar { width: 6px; }
        ::-webkit-scrollbar-track { background: #1c1c1c; }
        ::-webkit-scrollbar-thumb { background: #33b1ff44; border-radius: 3px; }
        .scenario-btn {
          background: #262626;
          border: 0.5px solid #393939;
          color: #f4f4f4;
          padding: 12px 14px;
          border-radius: 0px;
          cursor: pointer;
          text-align: left;
          transition: all 0.2s;
          font-family: 'JetBrains Mono', monospace;
          font-size: 12px;
          width: 100%;
          margin-bottom: 1px;
        }
        .scenario-btn:hover { border-color: #33b1ff; background: #1a2a35; }
        .scenario-btn.active { border-left: 2px solid #fa4d56; background: #2a1515; }
        .reset-btn {
          background: transparent;
          border: 0.5px solid #393939;
          color: #33b1ff;
          padding: 9px 12px;
          border-radius: 0px;
          cursor: pointer;
          font-family: 'JetBrains Mono', monospace;
          font-size: 12px;
          width: 100%;
          transition: all 0.2s;
        }
        .reset-btn:hover { border-color: #33b1ff; background: #1a2a35; }
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
        }
        .site-btn:hover { color: #c6c6c6; }
        .site-btn.active { color: #f4f4f4; border-bottom-color: #33b1ff; }
      `}</style>

      {/* Top Bar */}
      <div style={{
        display: 'flex',
        alignItems: 'center',
        padding: '0 24px',
        background: '#1c1c1c',
        borderBottom: '1px solid #393939',
        gap: 0,
        flexShrink: 0,
        height: 52,
      }}>
        {/* Logo + title */}
        <div style={{ display: 'flex', alignItems: 'center', gap: 12, paddingRight: 24, borderRight: '1px solid #393939', height: '100%' }}>
          <span style={{ fontSize: 22 }}>🛰️</span>
          <div>
            <div style={{ color: '#33b1ff', fontWeight: 700, fontSize: 15, letterSpacing: 3 }}>NOC TRIAGE AGENT</div>
            <div style={{ color: '#6f6f6f', fontSize: 11, letterSpacing: 2 }}>DIGITAL TWIN · PHASE 3</div>
          </div>
        </div>

        {/* Site selector buttons */}
        <div style={{ display: 'flex', alignItems: 'stretch', height: '100%' }}>
          {SITES.map(site => (
            <button
              key={site.id}
              className={`site-btn ${activeSite === site.id ? 'active' : ''}`}
              onClick={() => setActiveSite(site.id)}
            >
              {/* Health dot */}
              <span style={{
                width: 8,
                height: 8,
                borderRadius: '50%',
                background: siteAlarmStatus[site.id] ? '#fa4d56' : '#42be65',
                display: 'inline-block',
                flexShrink: 0,
              }} />
              {site.shortName}
              <OemBadge oem={site.oem} />
            </button>
          ))}
        </div>

        <div style={{ flex: 1 }} />

        {/* NODES + SCENARIO indicator */}
        <div style={{ display: 'flex', gap: 24, fontSize: 11, color: '#6f6f6f' }}>
          <span>NODES: <span style={{ color: '#42be65' }}>{topology ? Object.keys(topology.nodes || {}).length : '—'}</span></span>
          {activeScenario && (
            <span>SCENARIO: <span style={{ color: '#ff832b' }}>
              {activeScenario}
            </span></span>
          )}
        </div>

        {/* Error banner */}
        {error && (
          <div style={{ background: '#2a0e0e', border: '0.5px solid #fa4d56', color: '#ff8389', padding: '5px 12px', borderRadius: 0, fontSize: 11, marginLeft: 16 }}>
            ⚠ {error}
          </div>
        )}
      </div>

      {/* Main Layout */}
      <div style={{ display: 'flex', flex: 1, overflow: 'hidden' }}>

        {/* Sidebar */}
        <div style={{
          width: 230,
          background: '#1c1c1c',
          borderRight: '1px solid #393939',
          padding: 18,
          display: 'flex',
          flexDirection: 'column',
          gap: 4,
          overflowY: 'auto',
          flexShrink: 0,
        }}>
          <div style={{ color: '#6f6f6f', fontSize: 11, letterSpacing: 2, marginBottom: 12 }}>SCENARIOS</div>

          {currentScenarios.map(sc => (
            <button
              key={sc.id + sc.label}
              className={`scenario-btn ${activeScenario === sc.id ? 'active' : ''}`}
              onClick={() => runScenario(sc.id)}
            >
              <div style={{ color: sc.color, fontWeight: 700, marginBottom: 4 }}>{sc.label}</div>
              <div style={{ color: '#6f6f6f', fontSize: 10 }}>{sc.description}</div>
            </button>
          ))}

          <div style={{ flex: 1 }} />

          <button className="reset-btn" onClick={resetAll}>↺ Reset</button>

          {/* INGESTION AGENT panel */}
          {ingestionMeta && (
            <div style={{ marginTop: 10 }}>
              {/* Panel header */}
              <div
                style={{
                  cursor: 'pointer',
                  padding: '8px 10px',
                  background: '#1a1a1a',
                  border: '0.5px solid #393939',
                  display: 'flex',
                  alignItems: 'center',
                  justifyContent: 'space-between',
                  userSelect: 'none',
                }}
                onClick={() => setIngestionExpanded(prev => !prev)}
              >
                <span style={{ fontSize: 10, letterSpacing: 1.5, color: '#a8a8a8' }}>
                  INGESTION AGENT {ingestionExpanded ? '▼' : '▶'}
                </span>
                {currentSite && <OemBadge oem={currentSite.oem} />}
              </div>

              {/* Panel body */}
              {ingestionExpanded && (
                <div style={{
                  padding: '8px 10px',
                  background: '#131313',
                  border: '0.5px solid #393939',
                  borderTop: 'none',
                }}>
                  {/* Field Mappings */}
                  {ingestionMeta.field_mappings && ingestionMeta.field_mappings.length > 0 && (
                    <div style={{ marginBottom: 8 }}>
                      <div style={{ color: '#6f6f6f', fontSize: 9, letterSpacing: 1.5, marginBottom: 5 }}>FIELD MAPPINGS</div>
                      {ingestionMeta.field_mappings.map((fm, i) => {
                        const left = fm.oem_field || '';
                        const right = fm.canonical_field || fm.canonical_value || '';
                        const mid = fm.oem_value ? ` (${fm.oem_value})` : '';
                        return (
                          <div key={i} style={{ color: '#a8a8a8', fontSize: 10, fontFamily: "'JetBrains Mono', monospace", marginBottom: 3 }}>
                            {left}{mid} <span style={{ color: '#33b1ff' }}>→</span> {right}
                          </div>
                        );
                      })}
                    </div>
                  )}

                  {/* Severity Gaps */}
                  {ingestionMeta.severity_gaps && ingestionMeta.severity_gaps.length > 0 && (
                    <div>
                      <div style={{ color: '#6f6f6f', fontSize: 9, letterSpacing: 1.5, marginBottom: 5 }}>SEVERITY GAPS</div>
                      {ingestionMeta.severity_gaps.map((sg, i) => (
                        <div key={i} style={{ color: '#a8a8a8', fontSize: 10, fontFamily: "'JetBrains Mono', monospace", marginBottom: 4 }}>
                          <div>arrived_as: <span style={{ color: '#f1c21b' }}>{sg.arrived_as}</span></div>
                          {sg.note && <div style={{ color: '#525252', fontSize: 9, marginTop: 2 }}>{sg.note}</div>}
                        </div>
                      ))}
                    </div>
                  )}

                  {/* OEM tag if no mappings or gaps */}
                  {(!ingestionMeta.field_mappings || ingestionMeta.field_mappings.length === 0) &&
                   (!ingestionMeta.severity_gaps || ingestionMeta.severity_gaps.length === 0) && (
                    <div style={{ color: '#525252', fontSize: 10 }}>
                      {ingestionMeta.oem && ingestionMeta.oem.length > 0
                        ? `OEM: ${ingestionMeta.oem.join(', ')}`
                        : 'No normalization data.'}
                    </div>
                  )}
                </div>
              )}
            </div>
          )}

          {/* Legend */}
          <div style={{ marginTop: 18, borderTop: '1px solid #393939', paddingTop: 14 }}>
            <div style={{ color: '#6f6f6f', fontSize: 10, letterSpacing: 2, marginBottom: 10 }}>LEGEND</div>
            {[
              { color: '#42be65', label: 'Healthy' },
              { color: '#fa4d56', label: 'Root Fault' },
              { color: '#ff832b', label: 'Impacted' },
              { color: '#33b1ff', label: 'POI/Source' },
            ].map(item => (
              <div key={item.label} style={{ display: 'flex', alignItems: 'center', gap: 9, marginBottom: 6, fontSize: 11 }}>
                <div style={{ width: 10, height: 10, borderRadius: 0, background: item.color + '33', border: `1px solid ${item.color}` }} />
                <span style={{ color: '#a8a8a8' }}>{item.label}</span>
              </div>
            ))}
          </div>

          {/* Incident list */}
          {incidents.length > 0 && (
            <div style={{ marginTop: 14, borderTop: '1px solid #393939', paddingTop: 14 }}>
              <div style={{ color: '#6f6f6f', fontSize: 10, letterSpacing: 2, marginBottom: 10 }}>INCIDENTS ({incidents.length})</div>
              {incidents.map(inc => (
                <div key={inc.incident_id} style={{
                  background: '#262626',
                  borderLeft: `2px solid ${inc.severity === 'P1' ? '#fa4d56' : inc.severity === 'P2' ? '#ff832b' : '#42be65'}`,
                  borderTop: '0.5px solid #393939',
                  borderRight: '0.5px solid #393939',
                  borderBottom: '0.5px solid #393939',
                  padding: '7px 10px',
                  marginBottom: 4,
                  fontSize: 11,
                }}>
                  <div style={{ color: inc.severity === 'P1' ? '#fa4d56' : inc.severity === 'P2' ? '#ff832b' : '#42be65', fontWeight: 700, fontSize: 10 }}>
                    {'■'.repeat({'P1':5,'P2':4,'P3':3,'P4':2,'P5':1}[inc.severity]||0)}{'□'.repeat(5-({'P1':5,'P2':4,'P3':3,'P4':2,'P5':1}[inc.severity]||0))} {inc.severity} · {inc.scope_label}
                  </div>
                  <div style={{ color: '#a8a8a8', marginTop: 3 }}>{inc.root_cause_node}</div>
                </div>
              ))}
            </div>
          )}
        </div>

        {/* Center column — 55/45 split */}
        <div style={{ flex: 1, display: 'flex', flexDirection: 'column', overflow: 'hidden' }}>

          {/* Topology — 55% */}
          <div style={{ flex: '0 0 55%', minHeight: 0, overflow: 'hidden' }}>
            {topology
              ? <FlowContainer topology={topology} incidents={incidents} />
              : (
                <div style={{ display: 'flex', alignItems: 'center', justifyContent: 'center', height: '100%', color: '#6f6f6f' }}>
                  {error ? error : 'Loading topology...'}
                </div>
              )
            }
          </div>

          {/* Terminal — 45%, scrollable */}
          <div style={{ flex: '0 0 45%', borderTop: '1px solid #393939', overflow: 'hidden', display: 'flex', flexDirection: 'column' }}>
            <TriageTerminal brief={triageBrief} loading={loading} incident={primaryIncident} />
          </div>

        </div>
      </div>
    </div>
  );
}
