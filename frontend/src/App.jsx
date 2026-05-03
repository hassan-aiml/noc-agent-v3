import React, { useState, useEffect, useCallback } from 'react';
import FlowContainer from './FlowContainer';
import TriageTerminal from './TriageTerminal';

const API = process.env.REACT_APP_API_URL || 'http://localhost:8000';

const SCENARIOS = [
  { id: 'single_ru',       label: '① Single RU Failure',       description: 'RU-01 — VSWR High',        color: '#ff832b' },
  { id: 'hub_failure',     label: '② Food Court Hub Failure',   description: 'EH-01: All 5 RUs Offline', color: '#fa4d56' },
  { id: 'poi_signal_loss', label: '③ Meridian n41 Signal Loss', description: 'Sector-wide DL Power Low',  color: '#33b1ff' },
];

export default function App() {
  const [topology, setTopology]               = useState(null);
  const [incidents, setIncidents]             = useState([]);
  const [primaryIncident, setPrimaryIncident] = useState(null);
  const [triageBrief, setTriageBrief]         = useState('');
  const [loading, setLoading]                 = useState(false);
  const [activeScenario, setActiveScenario]   = useState(null);
  const [error, setError]                     = useState('');

  useEffect(() => {
    fetch(`${API}/topology`)
      .then(r => r.json())
      .then(setTopology)
      .catch(() => setError('Backend not reachable — start FastAPI on port 8000'));
  }, []);

  const runScenario = useCallback(async (scenarioId) => {
    setLoading(true);
    setActiveScenario(scenarioId);
    setTriageBrief('');
    setIncidents([]);
    setPrimaryIncident(null);
    setError('');
    try {
      const res = await fetch(`${API}/simulate`, {
        method: 'POST',
        headers: { 'Content-Type': 'application/json' },
        body: JSON.stringify({ scenario: scenarioId }),
      });
      const data = await res.json();
      setIncidents(data.incidents || []);
      setPrimaryIncident(data.primary_incident || null);
      setTriageBrief(data.triage_brief || '');
    } catch (e) {
      console.error('Simulation error:', e);
      setError('Simulation failed. Is the backend running?');
    } finally {
      setLoading(false);
    }
  }, []);

  const resetAll = () => {
    setIncidents([]);
    setPrimaryIncident(null);
    setTriageBrief('');
    setActiveScenario(null);
    setError('');
  };

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
      `}</style>

      {/* Top Bar */}
      <div style={{
        display: 'flex',
        alignItems: 'center',
        padding: '12px 24px',
        background: '#1c1c1c',
        borderBottom: '1px solid #393939',
        gap: 16,
        flexShrink: 0,
      }}>
        <div style={{ display: 'flex', alignItems: 'center', gap: 12 }}>
          <span style={{ fontSize: 22 }}>🛰️</span>
          <div>
            <div style={{ color: '#33b1ff', fontWeight: 700, fontSize: 15, letterSpacing: 3 }}>NOC TRIAGE AGENT</div>
            <div style={{ color: '#6f6f6f', fontSize: 11, letterSpacing: 2 }}>DIGITAL TWIN · PHASE 2</div>
          </div>
        </div>
        <div style={{ flex: 1 }} />
        <div style={{ display: 'flex', gap: 24, fontSize: 11, color: '#6f6f6f' }}>
          <span>SITE: <span style={{ color: '#f4f4f4' }}>NORTHPARK MALL</span></span>
          <span>NODES: <span style={{ color: '#42be65' }}>{topology ? Object.keys(topology.nodes || {}).length : '—'}</span></span>
          {activeScenario && (
            <span>SCENARIO: <span style={{ color: '#ff832b' }}>
              {SCENARIOS.find(s => s.id === activeScenario)?.id.toUpperCase()}
            </span></span>
          )}
        </div>
        {error && (
          <div style={{ background: '#2a0e0e', border: '0.5px solid #fa4d56', color: '#ff8389', padding: '5px 12px', borderRadius: 0, fontSize: 11 }}>
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
          <div style={{ color: '#6f6f6f', fontSize: 11, letterSpacing: 2, marginBottom: 12 }}>SIMULATE FAULT</div>

          {SCENARIOS.map(sc => (
            <button
              key={sc.id}
              className={`scenario-btn ${activeScenario === sc.id ? 'active' : ''}`}
              onClick={() => runScenario(sc.id)}
            >
              <div style={{ color: sc.color, fontWeight: 700, marginBottom: 4 }}>{sc.label}</div>
              <div style={{ color: '#6f6f6f', fontSize: 10 }}>{sc.description}</div>
            </button>
          ))}

          <div style={{ flex: 1 }} />
          <button className="reset-btn" onClick={resetAll}>↺ Reset</button>

          {/* Legend — 3 items only */}
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
