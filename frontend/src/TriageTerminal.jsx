import React, { useEffect, useRef, useState } from 'react';

const CURSOR_CHAR = '█';

export default function TriageTerminal({ brief, loading, incident }) {
  const [displayed, setDisplayed] = useState('');
  const [done, setDone] = useState(false);
  const timerRef = useRef(null);
  const idxRef = useRef(0);
  const scrollRef = useRef(null);

  useEffect(() => {
    clearInterval(timerRef.current);
    setDisplayed('');
    setDone(false);
    idxRef.current = 0;
    if (!brief) return;

    timerRef.current = setInterval(() => {
      idxRef.current += 1;
      setDisplayed(brief.slice(0, idxRef.current));
      if (idxRef.current >= brief.length) {
        clearInterval(timerRef.current);
        setDone(true);
      }
    }, 18);

    return () => clearInterval(timerRef.current);
  }, [brief]);

  // Auto-scroll as text streams in
  useEffect(() => {
    if (scrollRef.current) {
      scrollRef.current.scrollTop = scrollRef.current.scrollHeight;
    }
  }, [displayed]);

  const severityMap   = { 'P1': 5, 'P2': 4, 'P3': 3, 'P4': 2, 'P5': 1 };
  const severityColor = (s) => {
    if (s === 'P1') return '#fa4d56';
    if (s === 'P2') return '#ff832b';
    if (s === 'P3') return '#f1c21b';
    if (s === 'P4') return '#42be65';
    if (s === 'P5') return '#33b1ff';
    return '#6f6f6f';
  };
  const severityBar = (s) => {
    const filled = severityMap[s] || 0;
    const color  = severityColor(s);
    return (
      <span>
        {'■'.repeat(filled)}
        <span style={{ opacity: 0.2 }}>{'■'.repeat(5 - filled)}</span>
        {' '}{s}
      </span>
    );
  };

  return (
    <div style={{
      display: 'flex',
      flexDirection: 'column',
      height: '100%',
      background: '#0d0d0d',
      fontFamily: "'JetBrains Mono', 'Courier New', monospace",
      fontSize: 12,
      color: '#f4f4f4',
      boxSizing: 'border-box',
    }}>

      {/* Fixed terminal header */}
      <div style={{
        padding: '10px 20px 8px',
        borderBottom: '1px solid #393939',
        display: 'flex',
        alignItems: 'center',
        gap: 8,
        flexShrink: 0,
        background: '#0d0d0d',
      }}>
        <span style={{ color: '#ff5f57', fontSize: 11 }}>●</span>
        <span style={{ color: '#febc2e', fontSize: 11 }}>●</span>
        <span style={{ color: '#28c840', fontSize: 11 }}>●</span>
        <span style={{ color: '#33b1ff', marginLeft: 10, letterSpacing: 2, fontSize: 12, fontWeight: 700 }}>NOC TRIAGE TERMINAL</span>
      </div>

      {/* Scrollable content */}
      <div
        ref={scrollRef}
        style={{
          flex: 1,
          overflowY: 'auto',
          padding: '12px 20px 16px',
          scrollbarWidth: 'thin',
          scrollbarColor: '#33b1ff44 #1c1c1c',
        }}
      >
        {/* Incident metadata */}
        {incident && (
          <div style={{ marginBottom: 14, lineHeight: 2 }}>
            <div><span style={{ color: '#33b1ff' }}>INCIDENT   </span><span style={{ color: '#f4f4f4' }}>{incident.incident_id}</span></div>
            <div><span style={{ color: '#33b1ff' }}>TITLE      </span><span style={{ color: '#f4f4f4' }}>{incident.title}</span></div>
            <div>
              <span style={{ color: '#33b1ff' }}>SEVERITY   </span>
              <span style={{ color: severityColor(incident.severity), fontWeight: 700 }}>
                {severityBar(incident.severity)}
              </span>
            </div>
            <div><span style={{ color: '#33b1ff' }}>SCOPE      </span><span style={{ color: '#f4f4f4' }}>{incident.scope_label}</span></div>
            <div><span style={{ color: '#33b1ff' }}>ROOT CAUSE </span><span style={{ color: '#f1c21b' }}>{incident.root_cause_node} ({incident.root_cause_type})</span></div>
            <div>
              <span style={{ color: '#33b1ff' }}>ZONE       </span>
              <span style={{ color: incident.is_critical_zone ? '#fa4d56' : '#42be65' }}>
                {incident.is_critical_zone ? '⚠ CRITICAL' : 'Standard'}
              </span>
            </div>
            <div style={{ marginTop: 4, color: '#6f6f6f', fontSize: 11 }}>
              AFFECTED: {incident.affected_nodes?.join(', ')}
            </div>
            <div style={{ borderBottom: '1px solid #393939', marginTop: 10, marginBottom: 10 }} />
          </div>
        )}

        {/* AI Brief */}
        <div style={{ marginBottom: 6 }}>
          <span style={{ color: '#33b1ff', fontWeight: 700 }}>AI BRIEF   </span>
          {loading && <span style={{ color: '#ff832b' }}>⟳ Generating triage brief...</span>}
        </div>
        {!loading && brief && (
          <div style={{ color: '#c6e9ff', lineHeight: 1.8, whiteSpace: 'pre-wrap' }}>
            {displayed}{!done ? <span style={{ opacity: 0.7 }}>{CURSOR_CHAR}</span> : ''}
          </div>
        )}
        {!loading && !brief && (
          <div style={{ color: '#393939', fontStyle: 'italic' }}>
            — Select a scenario to run triage —
          </div>
        )}

        {/* Sparing advice */}
        {incident?.sparing_advice && done && (
          <div style={{
            marginTop: 14,
            padding: '10px 12px',
            background: '#0a1a10',
            borderLeft: '2px solid #42be65',
            borderTop: '0.5px solid #393939',
            borderRight: '0.5px solid #393939',
            borderBottom: '0.5px solid #393939',
            color: '#42be65',
            fontSize: 11,
            lineHeight: 1.7,
          }}>
            <span style={{ color: '#42be65', fontWeight: 700 }}>SPARING NOTE  </span>
            {incident.sparing_advice}
          </div>
        )}
      </div>
    </div>
  );
}
