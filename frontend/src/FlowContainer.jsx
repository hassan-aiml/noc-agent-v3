import React, { useMemo } from 'react';
import ReactFlow, {
  Background,
  Controls,
  Handle,
  Position,
} from 'reactflow';
import 'reactflow/dist/style.css';

/* ── Status palette — Carbon IBM ────────────────────── */
const STATUS = {
  healthy:     { border: '#42be65', glow: '0 0 10px #42be6544', bg: '#0a1a0e' },
  fault:       { border: '#fa4d56', glow: '0 0 16px #fa4d56, 0 0 32px #fa4d5655', bg: '#1e0808' },
  impacted:    { border: '#ff832b', glow: '0 0 10px #ff832b44', bg: '#1e1208' },
  poi_healthy: { border: '#33b1ff', glow: '0 0 10px #33b1ff44', bg: '#081a28' },
  poi_fault:   { border: '#fa4d56', glow: '0 0 16px #fa4d56, 0 0 32px #fa4d5655', bg: '#1e0808' },
};

/* ── SVG Icons ───────────────────────────────────────── */
const IconCoreRouter = ({ color }) => (
  <svg width="32" height="32" viewBox="0 0 32 32" fill="none">
    <rect x="4" y="10" width="24" height="12" rx="2" stroke={color} strokeWidth="1.5" fill="none"/>
    <circle cx="9" cy="16" r="2" fill={color} opacity="0.8"/>
    <circle cx="16" cy="16" r="2" fill={color} opacity="0.8"/>
    <circle cx="23" cy="16" r="2" fill={color} opacity="0.8"/>
    <line x1="16" y1="4" x2="16" y2="10" stroke={color} strokeWidth="1.5"/>
    <line x1="10" y1="4" x2="10" y2="7" stroke={color} strokeWidth="1.2"/>
    <line x1="22" y1="4" x2="22" y2="7" stroke={color} strokeWidth="1.2"/>
    <line x1="16" y1="22" x2="16" y2="28" stroke={color} strokeWidth="1.5"/>
    <line x1="8" y1="25" x2="8" y2="28" stroke={color} strokeWidth="1.2"/>
    <line x1="24" y1="25" x2="24" y2="28" stroke={color} strokeWidth="1.2"/>
  </svg>
);

const IconDistSwitch = ({ color }) => (
  <svg width="28" height="28" viewBox="0 0 28 28" fill="none">
    <rect x="3" y="8" width="22" height="12" rx="2" stroke={color} strokeWidth="1.5" fill="none"/>
    <line x1="8" y1="8" x2="8" y2="20" stroke={color} strokeWidth="0.8" opacity="0.4"/>
    <line x1="14" y1="8" x2="14" y2="20" stroke={color} strokeWidth="0.8" opacity="0.4"/>
    <line x1="20" y1="8" x2="20" y2="20" stroke={color} strokeWidth="0.8" opacity="0.4"/>
    <circle cx="8"  cy="14" r="1.5" fill={color} opacity="0.9"/>
    <circle cx="14" cy="14" r="1.5" fill={color} opacity="0.9"/>
    <circle cx="20" cy="14" r="1.5" fill={color} opacity="0.9"/>
    <line x1="8"  y1="20" x2="8"  y2="24" stroke={color} strokeWidth="1.2"/>
    <line x1="14" y1="20" x2="14" y2="24" stroke={color} strokeWidth="1.2"/>
    <line x1="20" y1="20" x2="20" y2="24" stroke={color} strokeWidth="1.2"/>
  </svg>
);

const IconRadioHead = ({ color }) => (
  <svg width="26" height="26" viewBox="0 0 26 26" fill="none">
    <rect x="8" y="10" width="10" height="12" rx="1.5" stroke={color} strokeWidth="1.5" fill="none"/>
    <line x1="13" y1="4" x2="13" y2="10" stroke={color} strokeWidth="1.5"/>
    <line x1="9"  y1="6" x2="13" y2="4"  stroke={color} strokeWidth="1.2"/>
    <line x1="17" y1="6" x2="13" y2="4"  stroke={color} strokeWidth="1.2"/>
    <rect x="10" y="13" width="6" height="3" rx="0.5" fill={color} opacity="0.4"/>
    <circle cx="13" cy="19" r="1" fill={color} opacity="0.7"/>
  </svg>
);

const IconPOI = ({ color }) => (
  <svg width="26" height="26" viewBox="0 0 26 26" fill="none">
    <circle cx="13" cy="13" r="9" stroke={color} strokeWidth="1.5" fill="none"/>
    <circle cx="13" cy="13" r="5" stroke={color} strokeWidth="1" fill="none" opacity="0.5"/>
    <circle cx="13" cy="13" r="2" fill={color} opacity="0.8"/>
    <line x1="13" y1="4"  x2="13" y2="7"  stroke={color} strokeWidth="1.5"/>
    <line x1="22" y1="13" x2="19" y2="13" stroke={color} strokeWidth="1.5"/>
  </svg>
);

/* ── Node shell ──────────────────────────────────────── */
function NodeShell({ label, sublabel, icon, status, pulse }) {
  const s = STATUS[status] || STATUS.healthy;
  return (
    <div style={{
      background: s.bg,
      border: `1.5px solid ${s.border}`,
      boxShadow: s.glow,
      borderRadius: 2,
      padding: '8px 12px',
      minWidth: 100,
      textAlign: 'center',
      fontFamily: "'JetBrains Mono', monospace",
      animation: pulse ? 'pulseFault 1.2s ease-in-out infinite' : 'none',
    }}>
      <div style={{ display: 'flex', justifyContent: 'center', marginBottom: 4 }}>{icon}</div>
      <div style={{ color: s.border, fontWeight: 700, fontSize: 11, letterSpacing: 0.5 }}>{label}</div>
      {sublabel && <div style={{ color: '#525252', fontSize: 9, marginTop: 2 }}>{sublabel}</div>}
    </div>
  );
}

/* ── Custom node types ───────────────────────────────── */
function MainHubNode({ data }) {
  const s = STATUS[data.status] || STATUS.healthy;
  return (
    <>
      <Handle type="target" position={Position.Top} style={{ opacity: 0 }} />
      <NodeShell label={data.label} sublabel="Core Hub" status={data.status} icon={<IconCoreRouter color={s.border} />} />
      <Handle type="source" position={Position.Bottom} />
    </>
  );
}

function ExpansionHubNode({ data }) {
  const s = STATUS[data.status] || STATUS.healthy;
  return (
    <>
      <Handle type="target" position={Position.Top} />
      <NodeShell label={data.label} sublabel={data.location + (data.is_critical ? ' ⚠' : '')}
        status={data.status} pulse={data.status === 'fault'} icon={<IconDistSwitch color={s.border} />} />
      <Handle type="source" position={Position.Bottom} />
    </>
  );
}

function RemoteUnitNode({ data }) {
  const s = STATUS[data.status] || STATUS.healthy;
  return (
    <>
      <Handle type="target" position={Position.Top} />
      <NodeShell label={data.label} sublabel="Radio Head" status={data.status}
        pulse={data.status === 'fault'} icon={<IconRadioHead color={s.border} />} />
    </>
  );
}

function PoiNode({ data }) {
  const s = STATUS[data.poiStatus] || STATUS.poi_healthy;
  return (
    <>
      <NodeShell label={data.label} sublabel={data.carrier_name + ' · ' + data.band}
        status={data.poiStatus} pulse={data.poiStatus === 'poi_fault'} icon={<IconPOI color={s.border} />} />
      <Handle type="source" position={Position.Bottom} />
    </>
  );
}

const nodeTypes = { mainHub: MainHubNode, expansionHub: ExpansionHubNode, remoteUnit: RemoteUnitNode, poi: PoiNode };

/* ── Graph builder ───────────────────────────────────── */
function buildGraph(topology, incidents) {
  if (!topology) return { nodes: [], edges: [] };

  const faultNodes    = new Set();
  const impactedNodes = new Set();
  const hasPOIFault   = incidents.some(inc => inc.root_cause_type === 'poi');

  incidents.forEach(inc => {
    if (inc.root_cause_type === 'poi') {
      faultNodes.add(inc.root_cause_node);
      if (topology.sites[0]) {
        const mh = topology.sites[0].main_hub;
        impactedNodes.add(mh.id);
        mh.expansion_hubs.forEach(eh => {
          impactedNodes.add(eh.id);
          eh.remotes.forEach(r => impactedNodes.add(r));
        });
      }
    } else if (!hasPOIFault) {
      if (inc.root_cause_type === 'expansion_hub' || inc.root_cause_type === 'main_hub') {
        faultNodes.add(inc.root_cause_node);
        inc.affected_nodes.forEach(n => impactedNodes.add(n));
      } else {
        inc.affected_nodes.forEach(n => faultNodes.add(n));
      }
    }
  });

  const rfNodes = [];
  const rfEdges = [];
  const site    = topology.sites[0];
  if (!site) return { nodes: [], edges: [] };

  const pois       = topology.pois || [];
  const totalWidth = (pois.length - 1) * 160;
  const poiStartX  = 400 - totalWidth / 2;

  pois.forEach((poi, i) => {
    const isFault   = faultNodes.has(poi.id);
    const poiStatus = isFault ? 'poi_fault' : 'poi_healthy';
    rfNodes.push({
      id: poi.id, type: 'poi',
      position: { x: poiStartX + i * 160, y: 0 },
      data: { label: poi.id, carrier_name: poi.carrier_name || poi.carrier, band: poi.band, poiStatus },
    });
    rfEdges.push({
      id: `e-${poi.id}-MH-01`, source: poi.id, target: 'MH-01',
      animated: !isFault,
      style: { stroke: isFault ? '#fa4d56' : '#33b1ff', strokeWidth: 2 },
    });
  });

  const mhStatus = faultNodes.has('MH-01') ? 'fault' : impactedNodes.has('MH-01') ? 'impacted' : 'healthy';
  rfNodes.push({ id: 'MH-01', type: 'mainHub', position: { x: 370, y: 150 }, data: { label: 'MH-01', status: mhStatus } });

  const ehs = site.main_hub?.expansion_hubs || [];
  ehs.forEach((eh, ei) => {
    const ehStatus = faultNodes.has(eh.id) ? 'fault' : impactedNodes.has(eh.id) ? 'impacted' : 'healthy';
    rfNodes.push({
      id: eh.id, type: 'expansionHub',
      position: { x: 120 + ei * 500, y: 310 },
      data: { label: eh.id, location: eh.location, is_critical: eh.is_critical, status: ehStatus },
    });
    rfEdges.push({
      id: `e-MH01-${eh.id}`, source: 'MH-01', target: eh.id,
      animated: ehStatus === 'healthy',
      style: { stroke: ehStatus === 'fault' ? '#fa4d56' : ehStatus === 'impacted' ? '#ff832b' : '#42be65', strokeWidth: 2 },
    });

    eh.remotes.forEach((ruId, ri) => {
      const ruStatus = faultNodes.has(ruId) ? 'fault' : impactedNodes.has(ruId) ? 'impacted' : 'healthy';
      const xOffset  = (ri - (eh.remotes.length - 1) / 2) * 120;
      rfNodes.push({
        id: ruId, type: 'remoteUnit',
        position: { x: 120 + ei * 500 + xOffset, y: 470 },
        data: { label: ruId, status: ruStatus },
      });
      rfEdges.push({
        id: `e-${eh.id}-${ruId}`, source: eh.id, target: ruId,
        animated: ruStatus === 'healthy',
        style: { stroke: ruStatus === 'fault' ? '#fa4d56' : ruStatus === 'impacted' ? '#ff832b' : '#42be65', strokeWidth: 1.5 },
      });
    });
  });

  return { nodes: rfNodes, edges: rfEdges };
}

/* ── Main export ─────────────────────────────────────── */
export default function FlowContainer({ topology, incidents }) {
  const derived = useMemo(() => buildGraph(topology, incidents), [topology, incidents]);

  return (
    <div style={{ width: '100%', height: '100%', background: '#161616' }}>
      <style>{`
        @keyframes pulseFault {
          0%, 100% { box-shadow: 0 0 8px #fa4d56; }
          50%       { box-shadow: 0 0 24px #fa4d56, 0 0 44px #fa4d5644; }
        }
      `}</style>
      <ReactFlow
        nodes={derived.nodes}
        edges={derived.edges}
        nodeTypes={nodeTypes}
        fitView
        fitViewOptions={{ padding: 0.12 }}
        proOptions={{ hideAttribution: true }}
      >
        <Background color="#222222" gap={28} size={1} />
        <Controls style={{ background: '#1c1c1c', border: '1px solid #393939', borderRadius: 2 }} />
      </ReactFlow>
    </div>
  );
}
