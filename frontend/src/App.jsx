import { useState, useEffect, useRef, useCallback } from "react";
import ReactFlow, { Background, useNodesState, useEdgesState, ReactFlowProvider, Handle, Position, useReactFlow } from "reactflow";
import "reactflow/dist/style.css";
import { SCENARIOS, SITE_META } from "./data/scenarios.js";
import { TOPOLOGIES } from "./data/topologies.js";

const BACKEND_URL = "https://noc-triage-v3-production.up.railway.app";

// Maps scenario ID to site IDs for API calls
const SCENARIO_SITES = {
  "SCN-001": ["SITE-ATX-001"],
  "SCN-002": ["SITE-ATX-002"],
  "SCN-003": ["SITE-ATX-003", "SITE-ATX-004"],
  "SCN-004": ["SITE-ATX-004"],
};

// ─── CONSTANTS ────────────────────────────────────────────────────────────────
const C = {
  // Page zones
  bg:          "#dde3ea",      // site view / page bg - medium slate
  alarmBg:     "#e2ddd8",      // alarm view content bg - medium warm
  surface:     "#edf0f4",      // triage / cards - medium cool
  surface2:    "#e4e9ef",      // topology bg / secondary surfaces

  // Nav hierarchy
  topbar:      "#0f172a",      // deep navy - top bar
  submenu:     "#1e293b",      // slate - submenu

  // Terminal zones
  terminal:    "#0d1117",      // alarm feed bg - near black
  terminalDim: "#8b949e",      // terminal dim text
  terminalGreen:"#3fb950",     // terminal green
  terminalAmber:"#d29922",     // terminal amber
  agentBg:     "#161b26",      // agent log bg - dark navy-charcoal
  agentBorder: "#30363d",      // agent panel borders

  // Borders & text
  border:      "#c8d0da",      // medium content borders
  borderStrong:"#adb8c5",      // stronger borders
  text:        "#0f172a",      // primary text
  dim:         "#475569",      // secondary text
  gray:        "#94a3b8",      // muted

  // Semantic colors
  cyan:        "#0284c7",
  red:         "#dc2626",
  orange:      "#ea580c",
  yellow:      "#ca8a04",
  blue:        "#2563eb",
  green:       "#16a34a",
  purple:      "#7c3aed",
};

const PRIORITY_COLOR = { P1: C.red, P2: C.orange, P3: C.yellow, P4: C.blue, P5: C.green };
const SEV_COLOR      = { critical: C.red, major: C.orange, minor: C.yellow, warning: C.purple, info: C.gray };
const ALARM_STATUS_COLOR = { OPEN: C.red, "IN PROGRESS": C.orange, RESOLVED: C.green, CLEARED: C.gray };

// ─── SHARED UI ATOMS ──────────────────────────────────────────────────────────
function Badge({ label, color, small }) {
  return (
    <span style={{
      background: color + "22", color,
      border: "1px solid " + (color) + "55",
      borderRadius: "2px",
      padding: small ? "1px 5px" : "2px 7px",
      fontSize: small ? "11px" : "13px",
      fontWeight: 700, letterSpacing: "0.08em", whiteSpace: "nowrap",
    }}>{label}</span>
  );
}

function Dot({ color, pulse }) {
  return (
    <span style={{ position: "relative", display: "inline-flex", alignItems: "center" }}>
      {pulse && <span style={{
        position: "absolute", width: 8, height: 8, borderRadius: "50%",
        background: color, opacity: 0.4, animation: "ping 1.2s ease-out infinite",
      }} />}
      <span style={{ width: 8, height: 8, borderRadius: "50%", background: color, display: "inline-block" }} />
    </span>
  );
}

function PanelHeader({ title, right, phase }) {
  return (
    <div style={{
      padding: "10px 16px", borderBottom: "1px solid " + (C.border),
      color: C.cyan, fontWeight: 700, fontSize: "12px", letterSpacing: "0.08em",
      display: "flex", alignItems: "center", justifyContent: "space-between", flexShrink: 0,
    }}>
      <span className={phase ? "cursor" : ""}>{title}</span>
      {right}
    </div>
  );
}

function PriorAlarmBanner({ alarms }) {
  if (!alarms || alarms.length === 0) return null;
  const [elapsed, setElapsed] = useState(0);
  useEffect(() => {
    const t = setInterval(() => setElapsed(e => e + 1), 1000);
    return () => clearInterval(t);
  }, []);
  const mins = Math.floor(elapsed / 60);
  const secs = elapsed % 60;
  const worst = alarms.reduce((a, b) =>
    ["P1","P2","P3","P4","P5"].indexOf(a.priority) < ["P1","P2","P3","P4","P5"].indexOf(b.priority) ? a : b
  );
  const pColor = PRIORITY_COLOR[worst.priority];
  return (
    <div style={{
      background: "#fff8ed",
      borderBottom: "1px solid #f59e0b",
      borderLeft: "4px solid #f59e0b",
      padding: "8px 16px",
      display: "flex", alignItems: "center", gap: "10px",
      flexShrink: 0, flexWrap: "wrap",
      boxShadow: "0 2px 6px rgba(245,158,11,0.15)",
    }}>
      <span style={{ fontSize: "16px" }}>WARNING</span>
      <div style={{ flex: 1 }}>
        <div style={{ fontWeight: 700, fontSize: "12px", color: "#92400e", letterSpacing: "0.04em" }}>
          PRIOR UNRESOLVED ALARM AT THIS SITE
        </div>
        <div style={{ fontSize: "11px", color: "#b45309", marginTop: 2 }}>
          {alarms.map(a => (
            <span key={a.id} style={{ marginRight: 12 }}>
              <span style={{
                background: pColor + "22", color: pColor,
                border: "1px solid " + (pColor) + "55",
                borderRadius: "2px", padding: "1px 5px",
                fontSize: "10px", fontWeight: 700, marginRight: 5,
              }}>{a.priority}</span>
              {a.alarmName} - {a.equipmentId}
            </span>
          ))}
        </div>
      </div>
      <div style={{
        background: "#fef3c7", border: "1px solid #f59e0b",
        borderRadius: "3px", padding: "3px 10px",
        color: "#92400e", fontSize: "11px", fontWeight: 700,
        flexShrink: 0,
      }}>
        OPEN {mins}m {String(secs).padStart(2,"0")}s
      </div>
      <div style={{
        fontSize: "10px", color: "#b45309", flexShrink: 0,
        fontStyle: "italic",
      }}>
        AI triage considers existing alarm state
      </div>
    </div>
  );
}

function IdlePlaceholder({ message }) {
  return (
    <div style={{
      display: "flex", alignItems: "center", justifyContent: "center",
      height: "100%", color: C.gray, fontSize: "13px", textAlign: "center", padding: "24px",
    }}>
      <div><div style={{ fontSize: "22px", marginBottom: "8px", opacity: 0.2 }}>o</div>{message}</div>
    </div>
  );
}

function TabBtn({ label, active, onClick, badge, badgeColor }) {
  return (
    <button onClick={onClick} style={{
      background: active ? C.cyan + "22" : "transparent",
      border: "none",
      borderBottom: "3px solid " + (active ? "#38bdf8" : "transparent"),
      borderTop: "3px solid transparent",
      color: active ? "#38bdf8" : "#94a3b8", fontFamily: "inherit", fontSize: "13px",
      fontWeight: active ? 700 : 400, padding: "0 18px", cursor: "pointer",
      letterSpacing: active ? "0.06em" : "0.04em",
      display: "flex", alignItems: "center", gap: "7px",
      transition: "all 0.15s", whiteSpace: "nowrap", height: "100%",
      boxShadow: active ? "inset 0 -2px 0 " + (C.cyan) : "none",
    }}>
      {active && <span style={{ fontSize: "8px", opacity: 0.8 }}>o</span>}
      {label}
      {badge && <Badge label={badge} color={badgeColor || C.cyan} small />}
    </button>
  );
}

// Navy-themed tab for top bar
function NavTabBtn({ label, active, onClick, badge }) {
  return (
    <button onClick={onClick} style={{
      background: active ? "#ffffff18" : "transparent",
      border: "none", borderBottom: "2px solid " + (active ? "#38bdf8" : "transparent"),
      color: active ? "#e2e8f0" : "#64748b", fontFamily: "inherit", fontSize: "13px",
      fontWeight: active ? 700 : 400, padding: "0 18px", cursor: "pointer",
      letterSpacing: "0.08em", display: "flex", alignItems: "center", gap: "7px",
      transition: "all 0.15s", whiteSpace: "nowrap", height: "100%",
    }}>
      {label}
      {badge && (
        <span style={{
          background: "#ef444433", color: "#f87171", border: "1px solid #ef444455",
          borderRadius: "2px", padding: "1px 5px", fontSize: "9px", fontWeight: 700,
        }}>{badge}</span>
      )}
    </button>
  );
}

// ─── ALARM CARD ───────────────────────────────────────────────────────────────
function AlarmCard({ alarm, visible, compact }) {
  const sevColor = SEV_COLOR[alarm.severity] || C.gray;
  const oemColor = alarm.oem === "stratum" ? C.cyan : C.orange;
  return (
    <div style={{
      background: C.bg, border: "1px solid " + (C.border),
      borderLeft: "3px solid " + (sevColor), borderRadius: "3px",
      padding: compact ? "6px 8px" : "8px 10px", marginBottom: "5px",
      opacity: visible ? 1 : 0, transform: visible ? "translateY(0)" : "translateY(-6px)",
      transition: "all 0.3s ease",
    }}>
      <div style={{ display: "flex", alignItems: "center", gap: "5px", marginBottom: compact ? 2 : 4, flexWrap: "wrap" }}>
        <Badge label={alarm.severity.toUpperCase()} color={sevColor} small />
        <Badge label={alarm.oem === "stratum" ? "STRATUM" : "ORION"} color={oemColor} small />
        <span style={{ color: C.gray, fontSize: "9px", marginLeft: "auto" }}>{alarm.timestamp}</span>
      </div>
      <div style={{ color: C.text, fontWeight: 700, fontSize: "13px", marginBottom: 2 }}>{alarm.alarmName}</div>
      <div style={{ color: C.dim, fontSize: "10px" }}>
        {alarm.equipmentId}
        {alarm.equipmentType && <span style={{ color: C.gray }}> [{alarm.equipmentType}]</span>}
        {alarm.parentId && <span style={{ color: C.gray }}> {"<-"} {alarm.parentId}</span>}
      </div>
      {!compact && alarm.siteId && (
        <div style={{ color: C.gray, fontSize: "9px", marginTop: 2 }}>{alarm.siteId}</div>
      )}
    </div>
  );
}

// ─── TERMINAL ALARM CARD (alarm feed) ───────────────────────────────────────
function TerminalAlarmCard({ alarm, visible }) {
  const sevColor = alarm.severity === "critical" ? "#f85149"
    : alarm.severity === "major" ? "#d29922"
    : alarm.severity === "minor" ? "#8b949e"
    : "#8b949e";
  const oemColor = alarm.oem === "stratum" ? "#58a6ff" : "#ffa657";
  const prefix = alarm.severity === "critical" ? "CRIT"
    : alarm.severity === "major" ? "MAJR" : "MINR";

  return (
    <div style={{
      borderLeft: "2px solid " + (sevColor),
      padding: "6px 8px", marginBottom: "4px",
      opacity: visible ? 1 : 0,
      transform: visible ? "translateX(0)" : "translateX(-8px)",
      transition: "all 0.3s ease",
      background: "#0d1117",
    }}>
      <div style={{ display: "flex", gap: 6, marginBottom: 2, alignItems: "center" }}>
        <span style={{ color: sevColor, fontSize: "9px", fontWeight: 700, minWidth: 28 }}>{prefix}</span>
        <span style={{ color: oemColor, fontSize: "9px" }}>[{alarm.oem === "stratum" ? "STR" : "ORN"}]</span>
        <span style={{ color: "#8b949e", fontSize: "9px", marginLeft: "auto" }}>{alarm.timestamp}</span>
      </div>
      <div style={{ color: "#e6edf3", fontSize: "12px", fontWeight: 700, marginBottom: 1 }}>{alarm.alarmName}</div>
      <div style={{ color: "#8b949e", fontSize: "9px" }}>
        {alarm.equipmentId}
        {alarm.equipmentType && <span> [{alarm.equipmentType}]</span>}
        {alarm.siteId && <span style={{ color: "#484f58" }}> - {alarm.siteId.replace("SITE-","")}</span>}
      </div>
    </div>
  );
}

// ─── ACTIVE ALARM ROW (site view) ─────────────────────────────────────────────
function ActiveAlarmRow({ alarm, onResolve }) {
  const [elapsed, setElapsed] = useState(0);
  useEffect(() => {
    const t = setInterval(() => setElapsed(e => e + 1), 1000);
    return () => clearInterval(t);
  }, []);

  const sevColor = SEV_COLOR[alarm.severity] || C.gray;
  const statusColor = ALARM_STATUS_COLOR[alarm.status] || C.gray;
  const mins = Math.floor(elapsed / 60);
  const secs = elapsed % 60;

  return (
    <div style={{
      background: C.bg, border: "1px solid " + (C.border),
      borderLeft: "3px solid " + (sevColor), borderRadius: "3px",
      padding: "10px 12px", marginBottom: "6px",
      display: "flex", alignItems: "flex-start", gap: "10px",
    }}>
      <div style={{ flex: 1 }}>
        <div style={{ display: "flex", gap: "5px", marginBottom: 4, flexWrap: "wrap", alignItems: "center" }}>
          <Badge label={alarm.severity.toUpperCase()} color={sevColor} small />
          <Badge label={alarm.status} color={statusColor} small />
          <Badge label={alarm.priority} color={PRIORITY_COLOR[alarm.priority]} small />
          <span style={{ color: C.gray, fontSize: "9px", marginLeft: "auto" }}>
            {mins}m {String(secs).padStart(2, "0")}s ago
          </span>
        </div>
        <div style={{ color: C.text, fontWeight: 700, fontSize: "13px", marginBottom: 2 }}>{alarm.alarmName}</div>
        <div style={{ color: C.dim, fontSize: "10px" }}>
          {alarm.equipmentId} - {alarm.cascadeType}
          {alarm.priorAlarms && alarm.priorAlarms.length > 0 && (
            <span style={{ color: C.yellow, marginLeft: 8 }}>
              WARNING {alarm.priorAlarms.length} prior open alarm{alarm.priorAlarms.length > 1 ? "s" : ""} at site
            </span>
          )}
        </div>
        {alarm.ticketId && (
          <div style={{ color: C.gray, fontSize: "9px", marginTop: 3 }}>
            ServiceNow - {alarm.ticketId}
          </div>
        )}
      </div>
      {alarm.status !== "RESOLVED" && (
        <button onClick={() => onResolve(alarm.id)} style={{
          background: "transparent", border: "1px solid " + (C.border),
          borderRadius: "2px", color: C.dim, fontFamily: "inherit",
          fontSize: "9px", padding: "3px 8px", cursor: "pointer",
          letterSpacing: "0.06em", flexShrink: 0,
        }}>RESOLVE</button>
      )}
    </div>
  );
}

// ─── LOG LINE ─────────────────────────────────────────────────────────────────
function LogLine({ line, dim }) {
  return (
    <div style={{
      fontSize: "12px", lineHeight: "1.8",
      opacity: dim ? 0.4 : 1, transition: "opacity 0.3s",
      display: "flex", gap: "6px", marginBottom: "1px",
    }}>
      {line.ts && <span style={{ color: C.gray, flexShrink: 0, minWidth: 52 }}>{line.ts}</span>}
      <span style={{ color: line.color || C.dim }}>{line.text}</span>
    </div>
  );
}

// ─── AGGREGATION SUMMARY ──────────────────────────────────────────────────────
function AggregationSummary({ sites }) {
  if (!sites || sites.length === 0) return null;
  return (
    <div style={{ background: C.bg, border: "1px solid " + (C.border), borderRadius: "3px", marginTop: 10 }}>
      <div style={{ padding: "6px 10px", borderBottom: "1px solid " + (C.border),
        color: C.cyan, fontSize: "9px", fontWeight: 700, letterSpacing: "0.1em" }}>
        AGGREGATION RESULT
      </div>
      {sites.map(s => (
        <div key={s.siteId} style={{
          padding: "7px 10px", borderBottom: "1px solid " + (C.border) + "22",
          display: "flex", alignItems: "center", gap: "8px", flexWrap: "wrap",
        }}>
          <span style={{ color: C.dim, fontSize: "10px", minWidth: 90 }}>{s.siteId.replace("SITE-", "")}</span>
          <span style={{ color: C.text, fontSize: "10px" }}>{s.alarmCount} alarm{s.alarmCount !== 1 ? "s" : ""}</span>
          <span style={{ marginLeft: "auto", display: "flex", gap: 5 }}>
            <Badge label={s.aggregated ? "AGGREGATED" : "STRAY"} color={s.aggregated ? C.green : C.yellow} small />
            <Badge label={s.priority} color={PRIORITY_COLOR[s.priority]} small />
          </span>
        </div>
      ))}
    </div>
  );
}

// ─── TRIAGE RESULT CARD ───────────────────────────────────────────────────────
function TriageResultCard({ triage, siteName, siteId, onOverride, overridden }) {
  if (!triage) return null;
  const pColor = PRIORITY_COLOR[overridden?.priority || triage.priority];
  return (
    <div style={{
      background: "#ffffff", border: "1px solid " + (C.borderStrong),
      borderTop: "4px solid " + (pColor), borderRadius: "4px", overflow: "hidden",
      boxShadow: "0 2px 12px rgba(0,0,0,0.10), 0 0 0 1px rgba(2,132,199,0.08)",
    }}>
      <div style={{
          padding: "10px 14px", borderBottom: "1px solid " + (C.border),
          display: "flex", alignItems: "center", gap: 10, flexWrap: "wrap",
          position: "sticky", top: 0, background: "#ffffff",
          zIndex: 10,
          boxShadow: "0 2px 8px rgba(0,0,0,0.08)",
        }}>
        <span style={{ fontSize: "28px", fontWeight: 900, color: pColor, lineHeight: 1 }}>
          {overridden?.priority || triage.priority}
        </span>
        <div>
          <div style={{ color: C.text, fontWeight: 700, fontSize: "14px" }}>{siteName}</div>
          <div style={{ color: C.gray, fontSize: "9px" }}>{siteId}</div>
        </div>
        <div style={{ marginLeft: "auto", display: "flex", gap: 5, flexWrap: "wrap" }}>
          <Badge label={triage.cascadeType} color={C.cyan} small />
          {triage.stray && <Badge label="STRAY" color={C.yellow} small />}
          {overridden && <Badge label="OVERRIDDEN" color={C.purple} small />}
        </div>
      </div>

      <div style={{ padding: "10px 14px", borderBottom: "1px solid " + (C.border) }}>
        <div style={{ color: C.gray, fontSize: "10px", letterSpacing: "0.1em", marginBottom: 4 }}>ROOT CAUSE</div>
        <div style={{ display: "flex", alignItems: "center", gap: 6, marginBottom: 4 }}>
          <Badge label={triage.rootCauseType} color={C.red} small />
          <span style={{ color: C.red, fontWeight: 800, fontSize: "16px", letterSpacing: "0.02em" }}>{triage.rootCauseId}</span>
        </div>
        <div style={{ color: C.dim, fontSize: "12px", lineHeight: "1.6" }}>{triage.probableCause}</div>
      </div>

      <div style={{ padding: "10px 14px", borderBottom: "1px solid " + (C.border) }}>
        <div style={{ color: C.gray, fontSize: "10px", letterSpacing: "0.1em", marginBottom: 6 }}>BLAST RADIUS</div>
        <div style={{ marginBottom: 6 }}>
          <div style={{ color: C.gray, fontSize: "9px", marginBottom: 3 }}>AFFECTED EQUIPMENT</div>
          <div style={{ display: "flex", flexWrap: "wrap", gap: 3 }}>
            {triage.blastRadius.affectedEquipment.map(eq => (
              <span key={eq} style={{
                background: C.red + "18", color: C.orange,
                border: "1px solid " + (C.red) + "33", borderRadius: "2px",
                padding: "1px 5px", fontSize: "9px",
              }}>{eq}</span>
            ))}
          </div>
        </div>
        <div style={{ marginBottom: 6 }}>
          <div style={{ color: C.gray, fontSize: "9px", marginBottom: 3 }}>CARRIERS / BANDS</div>
          <div style={{ display: "flex", flexWrap: "wrap", gap: 3 }}>
            {triage.blastRadius.affectedCarriers.map(c => <Badge key={c} label={c} color={C.blue} small />)}
            {triage.blastRadius.affectedBands.map(b => <Badge key={b} label={b} color={C.cyan} small />)}
          </div>
        </div>
        <div style={{ color: C.dim, fontSize: "12px", lineHeight: "1.6" }}>{triage.blastRadius.serviceImpact}</div>
      </div>

      <div style={{ padding: "10px 14px", borderBottom: "1px solid " + (C.border) }}>
        <div style={{ color: C.gray, fontSize: "10px", letterSpacing: "0.1em", marginBottom: 4 }}>RECOMMENDED ACTION</div>
        <div style={{ color: C.dim, fontSize: "12px", lineHeight: "1.7" }}>{triage.recommendedAction}</div>
      </div>

      <div style={{ padding: "8px 14px", display: "flex", alignItems: "center", gap: 8, flexWrap: "wrap" }}>
        <span style={{
          background: C.green + "22", color: C.green,
          border: "1px solid " + (C.green) + "44", borderRadius: "2px",
          padding: "4px 10px", fontSize: "11px", fontWeight: 700, letterSpacing: "0.06em",
        }}>v TICKET CREATED - {triage.ticketId}</span>
        <button onClick={() => onOverride && onOverride(siteId, triage)} style={{
          marginLeft: "auto", background: overridden ? C.purple + "18" : "transparent",
          border: "1px solid " + (overridden ? C.purple : C.border),
          borderRadius: "2px", color: overridden ? C.purple : C.gray,
          fontFamily: "inherit", fontSize: "9px", padding: "3px 10px",
          cursor: "pointer", letterSpacing: "0.06em", transition: "all 0.15s",
        }}>
          {overridden ? "v OVERRIDE ACTIVE" : "OVERRIDE"}
        </button>
      </div>
    </div>
  );
}

// ─── TOPOLOGY MAP ─────────────────────────────────────────────────────────────
const NODE_BASE = {
  width: 86, height: 34, display: "flex", alignItems: "center", justifyContent: "center",
  fontSize: "11px", fontWeight: 700, fontFamily: "'JetBrains Mono', monospace",
  borderRadius: "3px", border: "1px solid", letterSpacing: "0.04em", cursor: "default",
  position: "relative",
};
const handleStyle = { background: "transparent", border: "none", width: 6, height: 6 };
function NodeBox({ data, healthyColor }) {
  const isFault    = data.status === "fault";
  const isImpacted = data.status === "impacted";
  const c = isFault ? C.red : isImpacted ? C.orange : healthyColor;
  const cls = isFault ? "node-fault" : isImpacted ? "node-impacted" : "";
  return (
    <div className={cls} style={{
      ...NODE_BASE,
      background: isFault ? C.red + "22" : isImpacted ? C.orange + "18" : c + "14",
      borderColor: c, color: c,
      borderWidth: isFault || isImpacted ? "2px" : "1px",
    }}>
      <Handle type="target" position={Position.Top} style={handleStyle} />
      {data.label}
      <Handle type="source" position={Position.Bottom} style={handleStyle} />
    </div>
  );
}
function PoiNode({ data }) {
  const isFault    = data.status === "fault";
  const isImpacted = data.status === "impacted";
  const c = isFault ? C.red : isImpacted ? C.orange : C.blue;
  const cls = isFault ? "node-fault" : isImpacted ? "node-impacted" : "";
  const carrierColor = data.carrier === "Vertex" ? "#0284c7"
    : data.carrier === "PeakCell" ? "#7c3aed"
    : data.carrier === "Meridian" ? "#16a34a"
    : C.gray;
  return (
    <div style={{ display: "flex", flexDirection: "column", alignItems: "center", gap: 4 }}>
      {data.carrier && (
        <div style={{
          fontSize: "10px", fontWeight: 700, letterSpacing: "0.05em",
          color: carrierColor, lineHeight: 1, textAlign: "center",
          whiteSpace: "nowrap",
        }}>
          {data.carrier} · {data.band}
        </div>
      )}
      <div className={cls} style={{
        ...NODE_BASE,
        background: isFault ? C.red + "22" : isImpacted ? C.orange + "18" : C.blue + "14",
        borderColor: c, color: c,
        borderWidth: isFault || isImpacted ? "2px" : "1px",
      }}>
        <Handle type="target" position={Position.Top} style={handleStyle} />
        {data.label}
        <Handle type="source" position={Position.Bottom} style={handleStyle} />
      </div>
    </div>
  );
}
function HubNode({ data }) { return <NodeBox data={data} healthyColor={C.cyan} />; }
function ExpNode({ data }) { return <NodeBox data={data} healthyColor={C.purple} />; }
function RemNode({ data }) { return <NodeBox data={data} healthyColor={C.green} />; }
const NODE_TYPES = { poi: PoiNode, hub: HubNode, expansion: ExpNode, remote: RemNode };

// Inner component that can call useReactFlow (must be inside ReactFlowProvider)
function TopologyInner({ siteId, rootCauseId, blastRadius, containerSize }) {
  const topo = TOPOLOGIES[siteId];
  const affected = new Set(blastRadius || []);
  const { fitView } = useReactFlow();

  const computeNodes = useCallback(() =>
    (topo?.nodes || []).map(n => {
      let status = "healthy";
      if (n.id === rootCauseId) status = "fault";
      else if (affected.has(n.id)) status = "impacted";
      return { ...n, data: { ...n.data, status } };
    }), [siteId, rootCauseId, blastRadius]);

  const computeEdges = useCallback(() =>
    (topo?.edges || []).map(e => ({
      ...e,
      style: { stroke: "#6b7280", strokeWidth: 1.5 },
      type: "default",
    })), [siteId]);

  const [nodes, setNodes, onNodesChange] = useNodesState(computeNodes());
  const [edges, setEdges, onEdgesChange] = useEdgesState(computeEdges());

  useEffect(() => { setNodes(computeNodes()); }, [siteId, rootCauseId, blastRadius]);
  useEffect(() => { setEdges(computeEdges()); }, [siteId]);

  // Re-fit whenever container size is known or site changes
  useEffect(() => {
    if (containerSize.w > 0 && containerSize.h > 0) {
      setTimeout(() => fitView({ padding: 0.28, duration: 200 }), 50);
    }
  }, [siteId, containerSize.w, containerSize.h]);

  return (
    <ReactFlow
      key={siteId}
      nodes={nodes}
      edges={edges}
      onNodesChange={onNodesChange}
      onEdgesChange={onEdgesChange}
      nodeTypes={NODE_TYPES}
      fitView
      fitViewOptions={{ padding: 0.28 }}
      minZoom={0.1}
      maxZoom={3}
      nodesDraggable={false}
      nodesConnectable={false}
      elementsSelectable={false}
      panOnDrag
      zoomOnScroll
      style={{ width: containerSize.w, height: containerSize.h, background: C.bg }}
      proOptions={{ hideAttribution: true }}
    >
      <Background color="#c8d0da" gap={20} size={0.5} />
    </ReactFlow>
  );
}

function TopologyMap({ siteId, rootCauseId, blastRadius }) {
  const topo = TOPOLOGIES[siteId];
  const wrapRef = useRef(null);
  const [containerSize, setContainerSize] = useState({ w: 0, h: 0 });

  useEffect(() => {
    const el = wrapRef.current;
    if (!el) return;
    const measure = () => {
      const r = el.getBoundingClientRect();
      if (r.width > 10 && r.height > 10) {
        setContainerSize({ w: Math.floor(r.width), h: Math.floor(r.height) });
      }
    };
    measure();
    const ro = new ResizeObserver(measure);
    ro.observe(el);
    return () => ro.disconnect();
  }, []);

  if (!topo) return <IdlePlaceholder message="No topology data" />;

  return (
    <div ref={wrapRef} style={{ width: "100%", height: "100%", minHeight: "200px", position: "relative" }}>
      <ReactFlowProvider>
        <TopologyInner
          siteId={siteId}
          rootCauseId={rootCauseId}
          blastRadius={blastRadius}
          containerSize={containerSize}
        />
      </ReactFlowProvider>
    </div>
  );
}

// ─── SITE ANALYSIS PANEL (reused in both views) ───────────────────────────────
function SiteAnalysisPanel({ siteId, logLines, aggData, triageResult, phase, onOverride, overrides, siteAlarms, onResolve }) {
  const logRef = useRef(null);
  const triageRef = useRef(null);
  useEffect(() => {
    if (logRef.current) logRef.current.scrollTop = logRef.current.scrollHeight;
  }, [logLines]);
  useEffect(() => {
    if (triageRef.current) triageRef.current.scrollTop = 0;
  }, [triageResult]);

  const filteredLog = logLines.filter(l => l.siteId === null || l.siteId === siteId);
  const meta = SITE_META[siteId];
  const overridden = overrides?.[siteId];

  const middleTitle =
    ["normalizing", "aggregating"].includes(phase) ? "INGESTION AGENT - NORMALIZING" :
    phase === "correlating" ? "CORRELATION ENGINE - ANALYZING" :
    phase === "complete"    ? "CORRELATION ENGINE - ANALYZING" :
    "AGENT ACTIVITY";

  const isAnimating = ["normalizing", "correlating"].includes(phase);

  const [agentCollapsed, setAgentCollapsed] = useState(false);

  return (
    <div style={{ display: "flex", flex: 1, overflow: "hidden", height: "100%", minHeight: 0 }}>

      {/* Middle panel - alarms on top, agent log below, same dark column */}
      <div style={{
        width: agentCollapsed ? "36px" : "34%",
        minWidth: agentCollapsed ? "36px" : "220px",
        borderRight: "1px solid " + C.agentBorder,
        borderTop: "3px solid #30363d",
        display: "flex", flexDirection: "column", overflow: "hidden",
        transition: "width 0.2s ease, min-width 0.2s ease",
        flexShrink: 0, background: C.agentBg,
      }}>

        {/* Active alarms - top section of middle panel */}
        {!agentCollapsed && siteAlarms && siteAlarms.length > 0 && (
          <div style={{
            flexShrink: 0,
            maxHeight: "66%",
            display: "flex",
            flexDirection: "column",
            borderBottom: "2px solid #30363d",
          }}>
            <div style={{
              padding: "8px 10px", borderBottom: "1px solid #30363d",
              display: "flex", alignItems: "center", justifyContent: "space-between",
              flexShrink: 0,
            }}>
              <span style={{ color: "#58a6ff", fontWeight: 700, fontSize: "11px", letterSpacing: "0.1em" }}>
                ACTIVE ALARMS
              </span>
              <span style={{ color: "#8b949e", fontSize: "10px" }}>
                {siteAlarms.filter(a => a.status !== "RESOLVED").length} open
              </span>
            </div>
            <div style={{ flex: 1, overflowY: "auto", padding: "6px 10px", scrollbarWidth: "thin", scrollbarColor: "#30363d transparent" }}>
              {siteAlarms.map(alarm => (
                <ActiveAlarmRow key={alarm.id} alarm={alarm} onResolve={onResolve} />
              ))}
            </div>
          </div>
        )}

        {/* Correlation engine / agent log header */}
        <div style={{
          padding: "8px 10px", borderBottom: "1px solid " + C.agentBorder,
          display: "flex", alignItems: "center", gap: 6, flexShrink: 0,
          background: C.agentBg,
        }}>
          {!agentCollapsed && (
            <span className={isAnimating ? "cursor" : ""} style={{
              color: "#58a6ff", fontWeight: 700, fontSize: "11px",
              letterSpacing: "0.1em", flex: 1,
            }}>{middleTitle}</span>
          )}
          {!agentCollapsed && phase !== "idle" && phase !== "alarms_firing" && (
            <Badge
              label={phase === "complete" ? "DONE" : "RUNNING"}
              color={phase === "complete" ? C.green : C.cyan}
              small
            />
          )}
          <button onClick={() => setAgentCollapsed(v => !v)} style={{
            background: "transparent", border: "1px solid #30363d",
            borderRadius: "2px", color: "#8b949e", cursor: "pointer",
            fontSize: "10px", padding: "2px 5px", lineHeight: 1,
            marginLeft: agentCollapsed ? "auto" : 0, flexShrink: 0,
          }} title={agentCollapsed ? "Expand agent log" : "Collapse agent log"}>
            {agentCollapsed ? "+" : "-"}
          </button>
        </div>

        {/* Agent log body */}
        {!agentCollapsed ? (
          <div ref={logRef} style={{
            flex: 1, overflowY: "auto", padding: "12px",
            scrollbarWidth: "thin", scrollbarColor: C.agentBorder + " transparent",
            background: C.agentBg,
          }}>
            {filteredLog.length === 0
              ? <IdlePlaceholder message="Run a scenario to see agent activity" />
              : filteredLog.map((line, i, arr) => (
                  <LogLine key={line.id} line={line} dim={i < arr.length - 14} />
                ))
            }
            {aggData && (
              <AggregationSummary sites={
                aggData.multiSite
                  ? aggData.sites.filter(s => s.siteId === siteId)
                  : aggData.sites
              } />
            )}
          </div>
        ) : (
          <div style={{ flex: 1, display: "flex", flexDirection: "column", alignItems: "center", paddingTop: 12, gap: 6, background: C.agentBg }}>
            <span style={{
              color: "#484f58", fontSize: "8px", letterSpacing: "0.1em",
              writingMode: "vertical-rl", transform: "rotate(180deg)",
            }}>AGENT LOG</span>
          </div>
        )}
      </div>


      {/* Triage + topology - clean white decision zone */}
      <div style={{ flex: 1, display: "flex", flexDirection: "column", overflow: "hidden", minHeight: 0, background: "#eef4fb", borderLeft: "none", borderTop: "3px solid " + C.cyan, boxShadow: "inset 0 0 40px #0284c708" }}>
        <div ref={triageRef} style={{
          overflowY: "auto", padding: "12px",
          borderBottom: "1px solid " + (C.border),
          flexShrink: 0, maxHeight: "58%",
          scrollbarWidth: "thin", scrollbarColor: (C.border) + " transparent",
        }}>
          {triageResult
            ? <TriageResultCard
                triage={triageResult}
                siteName={meta?.name}
                siteId={siteId}
                onOverride={onOverride}
                overridden={overridden}
              />
            : <IdlePlaceholder message={
                phase === "idle" ? "Run a scenario to see triage" :
                phase === "complete" ? "No triage result for this site" :
                "Analyzing..."
              } />
          }
        </div>
        <div style={{ flex: 1, display: "flex", flexDirection: "column", minHeight: 0, overflow: "hidden" }}>
          <div style={{
            padding: "5px 14px", borderBottom: "1px solid " + (C.border),
            color: C.gray, fontSize: "10px", letterSpacing: "0.08em",
            flexShrink: 0, display: "flex", alignItems: "center",
          }}>
            SITE TOPOLOGY - {siteId} - {TOPOLOGIES[siteId]?.nodes.length || 0} nodes
          </div>
          <div style={{ flex: 1, minHeight: 0, overflow: "hidden" }}>
            <TopologyMap
              siteId={siteId}
              rootCauseId={triageResult?.rootCauseId}
              blastRadius={triageResult?.blastRadius?.affectedEquipment}
            />
          </div>
          <div style={{
            padding: "6px 14px", borderTop: "1px solid " + (C.border),
            display: "flex", alignItems: "center", flexWrap: "wrap",
            gap: "14px", flexShrink: 0, background: C.surface2,
          }}>
            {[
              { color: C.blue,   label: "POI"       },
              { color: C.cyan,   label: "Main Hub"   },
              { color: C.purple, label: "Exp. Hub"   },
              { color: C.green,  label: "Remote"     },
              { color: C.red,    label: "Root Cause" },
              { color: C.orange, label: "Impacted"   },
              { color: "#0284c7", label: "Vertex"    },
              { color: "#7c3aed", label: "PeakCell"  },
              { color: "#16a34a", label: "Meridian"  },
            ].map(({ color, label }) => (
              <div key={label} style={{ display: "flex", alignItems: "center", gap: "5px" }}>
                <div style={{
                  width: 11, height: 11, borderRadius: "2px",
                  background: color + "22", border: "2px solid " + (color),
                  flexShrink: 0,
                }} />
                <span style={{ color: C.dim, fontSize: "11px" }}>{label}</span>
              </div>
            ))}
          </div>
        </div>
      </div>
    </div>
  );
}

// ─── SCENARIO RUNNER HOOK ─────────────────────────────────────────────────────
function useScenarioRunner() {
  const [phase, setPhase]           = useState("idle");
  const [alarms, setAlarms]         = useState([]);
  const [visibleAlarms, setVisible] = useState(new Set());
  const [logLines, setLogLines]     = useState([]);
  const [aggData, setAggData]       = useState(null);
  const [triageResults, setTriage]  = useState({});
  const [activeScenario, setActiveScenario] = useState(null);
  const timers = useRef([]);
  const runId  = useRef(0);

  const clearTimers = () => { timers.current.forEach(clearTimeout); timers.current = []; };

  const addLog = useCallback((text, color, ts, delay, siteId = null) => {
    timers.current.push(setTimeout(() => {
      setLogLines(prev => [...prev, { text, color, ts, siteId, id: Date.now() + Math.random() }]);
    }, delay));
  }, []);

  const run = useCallback(async (scenarioId) => {
    clearTimers();
    const scn = SCENARIOS.find(s => s.id === scenarioId);
    if (!scn) return;

    setPhase("idle");
    setAlarms([]);
    setVisible(new Set());
    setLogLines([]);
    setAggData(null);
    setTriage({});
    setActiveScenario(scn);

    const siteIds = SCENARIO_SITES[scenarioId] || (scn.site ? [scn.site] : scn.sites || []);
    const thisRunId = ++runId.current;

    let apiResults = [];
    let useFallback = false;

    try {
      const responses = await Promise.all(
        siteIds.map(siteId =>
          fetch(BACKEND_URL + "/triage/simulate", {
            method: "POST",
            headers: { "Content-Type": "application/json" },
            body: JSON.stringify({ scenario: scenarioId, site_id: siteId }),
          }).then(r => r.ok ? r.json() : Promise.reject(r.status))
        )
      );
      apiResults = responses;
    } catch (e) {
      console.warn("API call failed, falling back to hardcoded data:", e);
      useFallback = true;
    }

    if (runId.current !== thisRunId) return;

    // Build alarm list — from API or fallback
    let al;
    if (!useFallback && apiResults.length > 0) {
      // Flatten alarms from all site_events across all API responses
      const rawAlarms = apiResults.flatMap(data =>
        (data.site_events || []).flatMap(ev =>
          (ev.alarm_list || []).map(a => ({
            alarmId:       a.raw_alarm_ref || a.alarm_id || (a.source_equipment_id + "-" + Date.now()),
            oem:           (a.das_oem || "stratum").toLowerCase(),
            siteId:        ev.site_id,
            equipmentId:   a.source_equipment_id,
            equipmentType: a.source_equipment_type,
            alarmName:     a.alarm_name,
            severity:      a.severity,
            timestamp:     a.timestamp ? a.timestamp.slice(11, 19) : "",
          }))
        )
      );
      // Sort by timestamp
      al = rawAlarms.sort((a, b) => (a.timestamp > b.timestamp ? 1 : -1));
    } else {
      al = scn.rawAlarms || [];
    }

    let t = 200;

    // Phase 1: Alarm stream
    setPhase("alarms_firing");
    al.forEach((alarm, i) => {
      timers.current.push(setTimeout(() => {
        setAlarms(prev => [...prev, alarm]);
        setVisible(prev => new Set([...prev, alarm.alarmId]));
      }, t + i * 380));
    });
    t += al.length * 380 + 300;

    // Phase 2: Normalization log
    timers.current.push(setTimeout(() => setPhase("normalizing"), t));
    t += 200;
    addLog("-> Ingestion agent started", C.cyan, al[0]?.timestamp || "", t, null); t += 260;

    if (!useFallback && apiResults.length > 0) {
      apiResults.forEach(data => {
        (data.site_events || []).forEach(ev => {
          const sid = ev.site_id;
          (ev.field_mappings_resolved || []).forEach(fm => {
            const left  = fm.oem_field || "";
            const mid   = fm.oem_value ? " (" + fm.oem_value + ")" : "";
            const right = fm.canonical_field || fm.canonical_value || "";
            addLog("  norm: " + left + mid + " -> " + right, C.green, "", t, sid); t += 190;
          });
          (ev.severity_gaps_resolved || []).forEach(sg => {
            addLog("  gap:  " + (sg.oem || "") + " '" + (sg.arrived_as || "") + "' -> " + (sg.canonical_severity || "minor"), C.yellow, "", t, sid); t += 190;
          });
        });
      });
    } else {
      al.forEach(alarm => {
        const sid = alarm.siteId;
        addLog("  recv: " + alarm.alarmId + " [" + (alarm.oem||"").toUpperCase() + "]", C.dim, alarm.timestamp, t, sid); t += 190;
        const norm = (scn.normalization || []).find(n => {
          if (n.site && n.site !== alarm.siteId) return false;
          return n.oemValue === alarm.equipmentType || n.oemField === "fault_description";
        });
        if (norm?.canonicalField) { addLog("  norm: fault_description -> alarm_name", C.yellow, alarm.timestamp, t, sid); t += 190; }
        if (norm?.canonicalValue) { addLog("  norm: " + norm.oemValue + " -> " + norm.canonicalValue, C.green, alarm.timestamp, t, sid); t += 190; }
      });
    }

    // Phase 3: Aggregation
    timers.current.push(setTimeout(() => setPhase("aggregating"), t));
    addLog("------------------------------", C.border, "", t, null); t += 180;
    addLog("-> Aggregating within 15-min window", C.cyan, "", t, null); t += 260;

    if (!useFallback && apiResults.length > 0) {
      const aggSites = apiResults.flatMap(data =>
        (data.site_events || []).map(ev => {
          const result = (data.results || []).find(r => r.site_id === ev.site_id) || {};
          addLog("  " + ev.site_id.replace("SITE-","") + " - " + (ev.alarm_count || 0) + " alarm(s) -> " + (ev.aggregated ? "AGGREGATED" : ev.stray_alarm ? "STRAY" : "SINGLE"),
            ev.aggregated ? C.green : C.yellow, "", t, ev.site_id); t += 260;
          return {
            siteId:     ev.site_id,
            alarmCount: ev.alarm_count || 0,
            aggregated: ev.aggregated || false,
            priority:   result.triage_priority || "P3",
          };
        })
      );
      const isMulti = aggSites.length > 1;
      timers.current.push(setTimeout(() => setAggData({ multiSite: isMulti, sites: aggSites }), t));
    } else {
      // Fallback aggregation
      if (scn.multiSite) {
        const groups = {};
        al.forEach(a => { if (!groups[a.siteId]) groups[a.siteId] = []; groups[a.siteId].push(a); });
        Object.entries(groups).forEach(([sid, alms]) => {
          const agg = scn.aggregation?.sites?.[sid];
          addLog("  " + sid.replace("SITE-","") + " - " + alms.length + " alarm(s) -> " + (agg?.aggregated ? "AGGREGATED" : "STRAY"),
            agg?.aggregated ? C.green : C.yellow, "", t, sid); t += 260;
        });
        const aggSites = Object.entries(scn.aggregation?.sites || {}).map(([siteId, a]) => ({
          siteId, alarmCount: a.alarmCount, aggregated: a.aggregated,
          priority: scn.triage?.[siteId]?.priority || "P3",
        }));
        timers.current.push(setTimeout(() => setAggData({ multiSite: true, sites: aggSites }), t));
      } else {
        const agg = scn.aggregation || {};
        addLog("  " + ((scn.site||"").replace("SITE-","")) + " - " + (agg.alarmCount||0) + " alarm(s) -> " + (agg.aggregated ? "AGGREGATED" : "SINGLE"),
          agg.aggregated ? C.green : C.yellow, "", t, scn.site); t += 260;
        timers.current.push(setTimeout(() => setAggData({
          multiSite: false,
          sites: [{ siteId: scn.site, alarmCount: agg.alarmCount, aggregated: agg.aggregated, priority: scn.triage?.priority }],
        }), t));
      }
    }
    t += 160;

    // Phase 4: Correlation
    timers.current.push(setTimeout(() => setPhase("correlating"), t));
    addLog("------------------------------", C.border, "", t, null); t += 180;
    addLog("-> Correlation engine analyzing", C.cyan, "", t, null); t += 360;

    if (!useFallback && apiResults.length > 0) {
      apiResults.forEach(data => {
        (data.results || []).forEach(r => {
          const sid = r.site_id;
          addLog("  [" + (sid||"").replace("SITE-","") + "] cascade: " + (r.cascade_type||""), C.dim, "", t, sid); t += 260;
          addLog("  [" + (sid||"").replace("SITE-","") + "] root:    " + (r.root_cause_node||"") + " [" + (r.root_cause_type||"") + "]", C.red, "", t, sid); t += 260;
          addLog("  [" + (sid||"").replace("SITE-","") + "] blast:   " + ((r.blast_radius?.affected_equipment||[]).length) + " equipment", C.orange, "", t, sid); t += 260;
          addLog("  [" + (sid||"").replace("SITE-","") + "] priority -> " + (r.triage_priority||""), PRIORITY_COLOR[r.triage_priority] || C.gray, "", t, sid); t += 260;
        });
      });
    } else {
      if (scn.multiSite) {
        Object.entries(scn.triage || {}).forEach(([sid, tr]) => {
          addLog("  [" + sid.replace("SITE-","") + "] cascade: " + tr.cascadeType, C.dim, "", t, sid); t += 260;
          addLog("  [" + sid.replace("SITE-","") + "] root:    " + tr.rootCauseId + " [" + tr.rootCauseType + "]", C.red, "", t, sid); t += 260;
          addLog("  [" + sid.replace("SITE-","") + "] priority -> " + tr.priority, PRIORITY_COLOR[tr.priority], "", t, sid); t += 260;
        });
      } else {
        const tr = scn.triage || {};
        addLog("  cascade:  " + tr.cascadeType, C.dim, "", t, scn.site); t += 300;
        addLog("  root:     " + tr.rootCauseId + " [" + tr.rootCauseType + "]", C.red, "", t, scn.site); t += 300;
        addLog("  priority -> " + tr.priority, PRIORITY_COLOR[tr.priority], "", t, scn.site); t += 300;
      }
    }

    // Phase 5: Complete
    timers.current.push(setTimeout(() => {
      if (runId.current !== thisRunId) return;
      setPhase("complete");

      if (!useFallback && apiResults.length > 0) {
        const triageMap = {};
        apiResults.forEach(data => {
          (data.results || []).forEach(r => {
            const sid = r.site_id;
            if (!sid) return;
            triageMap[sid] = {
              priority:       r.triage_priority,
              cascadeType:    r.cascade_type,
              rootCauseId:    r.root_cause_node,
              rootCauseType:  r.root_cause_type,
              probableCause:  r.probable_root_cause,
              recommendedAction: r.recommended_action,
              stray:          r.is_stray || false,
              ticketId:       r.servicenow_ticket_id || ("INC-" + Math.floor(Math.random()*9000000+1000000)),
              blastRadius: {
                affectedEquipment: r.blast_radius?.affected_equipment || [],
                affectedCarriers:  r.blast_radius?.affected_carriers  || [],
                affectedBands:     r.blast_radius?.affected_bands      || [],
                serviceImpact:     r.blast_radius?.service_impact      || "",
              },
            };
          });
        });
        setTriage(triageMap);
      } else {
        if (scn.multiSite) {
          const results = {};
          Object.entries(scn.triage || {}).forEach(([sid, tr]) => { results[sid] = tr; });
          setTriage(results);
        } else {
          setTriage({ [scn.site]: scn.triage });
        }
      }
    }, t));
  }, [addLog]);

  useEffect(() => () => clearTimers(), []);

  return { phase, alarms, visibleAlarms, logLines, aggData, triageResults, activeScenario, run };
}

// ─── ALARM VIEW ───────────────────────────────────────────────────────────────
function AlarmView({ runner, sessionAlarms, onOverride, overrides }) {
  const { phase, alarms, visibleAlarms, logLines, aggData, triageResults, activeScenario, run } = runner;
  const [feedCollapsed, setFeedCollapsed] = useState(false);
  const [activeSite, setActiveSite] = useState(null);

  const affectedSites = activeScenario
    ? activeScenario.multiSite ? activeScenario.sites : [activeScenario.site]
    : [];

  // Auto-select P1 site on complete, collapse feed
  useEffect(() => {
    if (phase === "complete" && Object.keys(triageResults).length > 0) {
      const p1 = Object.entries(triageResults).find(([, tr]) => tr.priority === "P1");
      setActiveSite(p1 ? p1[0] : Object.keys(triageResults)[0]);
      setFeedCollapsed(true);
    }
  }, [phase, triageResults]);

  // Reset on new scenario — fires as soon as activeScenario changes
  useEffect(() => {
    if (activeScenario) {
      setFeedCollapsed(false);
      setActiveSite(null);
    }
  }, [activeScenario]);

  // Pick first site while running
  useEffect(() => {
    if (affectedSites.length > 0 && !activeSite) setActiveSite(affectedSites[0]);
  }, [affectedSites.length]);

  const currentScenarioId = activeScenario?.id;
  const priorOpen = activeSite
    ? sessionAlarms.filter(a =>
        a.siteId === activeSite &&
        a.status !== "RESOLVED" &&
        a.scenarioId !== currentScenarioId
      )
    : [];

  return (
    <div style={{ display: "flex", flex: 1, overflow: "hidden", background: C.alarmBg }}>

      {/* Collapsible alarm feed - dark terminal */}
      <div style={{
        width: feedCollapsed ? "40px" : "22%",
        minWidth: feedCollapsed ? "40px" : "190px",
        borderRight: "1px solid #30363d",
        background: C.terminal,
        display: "flex", flexDirection: "column", overflow: "hidden",
        transition: "width 0.25s ease, min-width 0.25s ease",
        flexShrink: 0,
      }}>
        {/* Feed header */}
        <div style={{
          padding: "9px 10px", borderBottom: "1px solid #30363d",
          display: "flex", alignItems: "center", gap: 6, flexShrink: 0,
          background: "#161b22",
        }}>
          {!feedCollapsed && (
            <span style={{ color: C.terminalGreen, fontWeight: 700, fontSize: "10px", letterSpacing: "0.12em", flex: 1 }}>
              ALARM FEED
            </span>
          )}
          {!feedCollapsed && alarms.length > 0 && (
            <span style={{ color: "#f87171", fontSize: "10px", fontWeight: 700 }}>{alarms.length}</span>
          )}
          <button onClick={() => setFeedCollapsed(v => !v)} style={{
            background: "transparent", border: "1px solid #30363d",
            borderRadius: "2px", color: "#8b949e", cursor: "pointer",
            fontSize: "10px", padding: "2px 5px", lineHeight: 1,
            marginLeft: feedCollapsed ? "auto" : 0,
          }} title={feedCollapsed ? "Expand alarm feed" : "Collapse alarm feed"}>
            {feedCollapsed ? "+" : "-"}
          </button>
        </div>

        {/* Feed body */}
        {!feedCollapsed ? (
          <div style={{
            flex: 1, overflowY: "auto", padding: "10px",
            scrollbarWidth: "thin", scrollbarColor: "#30363d transparent",
          }}>
            {alarms.length === 0
              ? <div style={{ color: "#8b949e", fontSize: "11px", padding: "20px 8px", textAlign: "center" }}>
                  <div style={{ fontSize: "20px", marginBottom: 6, opacity: 0.3 }}>o</div>
                  Waiting for alarms...
                </div>
              : alarms.map(alarm => (
                  <TerminalAlarmCard key={alarm.alarmId} alarm={alarm}
                    visible={visibleAlarms.has(alarm.alarmId)} />
                ))
            }
          </div>
        ) : (
          <div style={{ flex: 1, display: "flex", flexDirection: "column", alignItems: "center", paddingTop: 14, gap: 8 }}>
            {alarms.length > 0 && (
              <>
                <span style={{ color: "#f87171", fontSize: "11px", fontWeight: 700 }}>{alarms.length}</span>
                <span style={{
                  color: "#8b949e", fontSize: "8px", letterSpacing: "0.1em",
                  writingMode: "vertical-rl", transform: "rotate(180deg)",
                }}>ALARMS</span>
              </>
            )}
          </div>
        )}
      </div>
      {/* Right area */}
      <div style={{ flex: 1, display: "flex", flexDirection: "column", overflow: "hidden" }}>

        {/* Affected site tabs */}
        <div style={{
          borderBottom: "1px solid #30363d", background: C.submenu,
          display: "flex", alignItems: "stretch", flexShrink: 0, height: 40, flexWrap: "nowrap",
          overflowX: "auto",
        }}>
          {affectedSites.length === 0 ? (
            <span style={{ color: C.gray, fontSize: "10px", padding: "0 16px", display: "flex", alignItems: "center" }}>
              Select a scenario above to begin
            </span>
          ) : (
            <>
              {affectedSites.map(sid => {
                const tr = triageResults[sid];
                const meta = SITE_META[sid];
                return (
                  <TabBtn
                    key={sid}
                    label={meta?.shortId + " - " + meta?.name.replace("Austin ", "")}
                    active={activeSite === sid}
                    onClick={() => setActiveSite(sid)}
                    badge={tr?.priority || (phase !== "idle" ? "..." : null)}
                    badgeColor={tr ? PRIORITY_COLOR[tr.priority] : C.gray}
                  />
                );
              })}
              {priorOpen.length > 0 && (
                <span style={{
                  marginLeft: "auto", padding: "0 14px",
                  display: "flex", alignItems: "center", gap: 6, whiteSpace: "nowrap",
                }}>
                  <span style={{
                    background: "#fff3cd",
                    border: "1px solid #f59e0b",
                    borderRadius: "3px",
                    padding: "3px 10px",
                    color: "#92400e",
                    fontSize: "11px",
                    fontWeight: 700,
                    letterSpacing: "0.04em",
                    display: "flex", alignItems: "center", gap: 5,
                    boxShadow: "0 0 0 2px #f59e0b55",
                  }}>
                    <span style={{ fontSize: "13px" }}>WARNING</span>
                    {priorOpen.length} PRIOR UNRESOLVED ALARM{priorOpen.length > 1 ? "S" : ""} AT THIS SITE
                  </span>
                </span>
              )}
            </>
          )}
        </div>

        {/* Site analysis or idle */}
        {activeSite
          ? <SiteAnalysisPanel
              siteId={activeSite}
              logLines={logLines}
              aggData={aggData}
              triageResult={triageResults[activeSite]}
              phase={phase}
              onOverride={onOverride}
              overrides={overrides}
            />
          : <IdlePlaceholder message="Select a scenario from the submenu above" />
        }
      </div>
    </div>
  );
}

// ─── SITE VIEW ────────────────────────────────────────────────────────────────
// ─── SITE VIEW ────────────────────────────────────────────────────────────────
function SiteTriageOrIdle({ siteTriage, selectedSite, onOverride, overrides, siteAlarms, onResolve }) {
  if (!siteTriage) {
    return <IdlePlaceholder message="No triage data for this site - run a scenario from Alarm View" />;
  }
  const tr = siteTriage;
  const syntheticLog = [
    { id: "s0", text: "-> Triage result loaded from session", color: C.cyan, ts: "", siteId: selectedSite },
    { id: "s1", text: "  cascade:  " + tr.cascadeType, color: C.dim, ts: "", siteId: selectedSite },
    { id: "s2", text: "  root:     " + tr.rootCauseId + " [" + tr.rootCauseType + "]", color: C.red, ts: "", siteId: selectedSite },
    { id: "s3", text: "  blast:    " + tr.blastRadius.affectedEquipment.length + " equipment", color: C.orange, ts: "", siteId: selectedSite },
    { id: "s4", text: "  carriers: " + tr.blastRadius.affectedCarriers.join(", "), color: C.blue, ts: "", siteId: selectedSite },
    { id: "s5", text: "  bands:    " + tr.blastRadius.affectedBands.join(", "), color: C.cyan, ts: "", siteId: selectedSite },
    { id: "s6", text: "------------------------------", color: C.gray, ts: "", siteId: selectedSite },
    { id: "s7", text: "  priority -> " + tr.priority, color: PRIORITY_COLOR[tr.priority], ts: "", siteId: selectedSite },
    { id: "s8", text: "  ticket:   " + tr.ticketId, color: C.green, ts: "", siteId: selectedSite },
    { id: "s9", text: "  impact:   " + tr.blastRadius.serviceImpact, color: C.dim, ts: "", siteId: selectedSite },
  ];
  return (
    <SiteAnalysisPanel
      siteId={selectedSite}
      logLines={syntheticLog}
      aggData={null}
      triageResult={siteTriage}
      phase="complete"
      onOverride={onOverride}
      overrides={overrides}
      siteAlarms={siteAlarms}
      onResolve={onResolve}
    />
  );
}

function SiteView({ sessionAlarms, allTriageResults, onResolve, onOverride, overrides }) {
  const [selectedSite, setSelectedSite] = useState(null);

  const getSiteHealth = (siteId) => {
    const open = sessionAlarms.filter(a => a.siteId === siteId && a.status !== "RESOLVED");
    if (open.some(a => a.priority === "P1")) return "critical";
    if (open.some(a => ["P2", "P3"].includes(a.priority))) return "degraded";
    return "healthy";
  };
  const hColor = (h) => h === "critical" ? C.red : h === "degraded" ? C.orange : C.green;

  const siteAlarms = selectedSite
    ? sessionAlarms.filter(a => a.siteId === selectedSite)
    : [];
  const siteTriage = selectedSite ? allTriageResults[selectedSite] : null;

  return (
    <div style={{ display: "flex", flex: 1, overflow: "hidden", height: "100%", minHeight: 0 }}>

      {/* Left panel */}
      <div style={{
        width: "280px",
        borderRight: "1px solid " + C.borderStrong,
        display: "flex",
        flexDirection: "column",
        background: C.surface2,
        flexShrink: 0,
      }}>
        <PanelHeader title="ALL SITES" />
        <div style={{ overflowY: "auto", padding: "10px", flexShrink: 0 }}>
          {Object.values(SITE_META).map(meta => {
            const h = getSiteHealth(meta.id);
            const hc = hColor(h);
            const openCount = sessionAlarms.filter(a => a.siteId === meta.id && a.status !== "RESOLVED").length;
            const tr = allTriageResults[meta.id];
            const selected = selectedSite === meta.id;
            const cardBorder = "1px solid " + (selected ? C.cyan : C.border);
            const cardBorderLeft = "4px solid " + (selected ? C.cyan : hc);
            const cardShadow = selected ? "0 0 0 2px " + C.cyan + "33" : "none";
            return (
              <div key={meta.id} onClick={() => setSelectedSite(meta.id)} style={{
                background: selected ? C.cyan + "28" : C.surface,
                border: cardBorder,
                borderLeft: cardBorderLeft,
                borderRadius: "3px",
                padding: "10px 12px",
                marginBottom: "6px",
                cursor: "pointer",
                transition: "all 0.15s",
                boxShadow: cardShadow,
              }}>
                <div style={{ display: "flex", alignItems: "center", gap: 6, marginBottom: 4, flexWrap: "wrap" }}>
                  <Dot color={hc} pulse={h !== "healthy"} />
                  <span style={{ color: selected ? C.cyan : C.text, fontWeight: 700, fontSize: "12px", letterSpacing: selected ? "0.04em" : "normal" }}>
                    {selected ? "+ " : ""}{meta.shortId}
                  </span>
                  <Badge label={meta.oem} color={meta.oem === "STRATUM" ? C.cyan : C.orange} small />
                  {tr && openCount > 0 && <Badge label={tr.priority} color={PRIORITY_COLOR[tr.priority]} small />}
                </div>
                <div style={{ color: C.gray, fontSize: "10px", marginBottom: 3 }}>
                  {meta.name.replace("Austin ", "")}
                </div>
                <div style={{ color: openCount > 0 ? C.orange : C.gray, fontSize: "11px" }}>
                  {openCount > 0 ? (openCount + " open alarm" + (openCount > 1 ? "s" : "")) : "No active alarms"}
                </div>
              </div>
            );
          })}
        </div>


      </div>

      {/* Site detail */}
      <div style={{ flex: 1, display: "flex", flexDirection: "column", overflow: "hidden" }}>
        {!selectedSite ? (
          <IdlePlaceholder message="Select a site from the list to view triage and topology" />
        ) : (
          <SiteTriageOrIdle
            siteTriage={siteTriage}
            selectedSite={selectedSite}
            onOverride={onOverride}
            overrides={overrides}
            siteAlarms={siteAlarms}
            onResolve={onResolve}
          />
        )}
      </div>
    </div>
  );
}

export default function App() {
  const [view, setView]               = useState("alarm");
  const [sessionAlarms, setSessionAlarms] = useState([]);
  const [overrides, setOverrides]     = useState({});
  const [allTriageResults, setAllTriageResults] = useState({});

  const runner = useScenarioRunner();
  const { phase, triageResults, activeScenario } = runner;

  // Persist triage results across scenarios
  useEffect(() => {
    if (phase === "complete" && Object.keys(triageResults).length > 0) {
      setAllTriageResults(prev => ({ ...prev, ...triageResults }));
    }
  }, [phase, triageResults]);

  // Push completed scenario into session alarms
  useEffect(() => {
    if (phase !== "complete" || !activeScenario) return;
    const sites = activeScenario.multiSite ? activeScenario.sites : [activeScenario.site];
    const newAlarms = [];

    sites.forEach(siteId => {
      const tr = activeScenario.multiSite ? activeScenario.triage[siteId] : activeScenario.triage;
      if (!tr) return;
      const priorOpen = sessionAlarms.filter(a => a.siteId === siteId && a.status !== "RESOLVED");
      newAlarms.push({
        id: (activeScenario.id) + "-" + siteId + "-" + Date.now(),
        siteId,
        alarmName: tr.stray
          ? "Stray Alarm - " + tr.cascadeType
          : tr.cascadeType.replace(/_/g, " ") + " EVENT",
        severity: tr.priority === "P1" ? "critical" : tr.priority === "P2" ? "major" : "minor",
        priority: tr.priority,
        status: "OPEN",
        cascadeType: tr.cascadeType,
        equipmentId: tr.rootCauseId,
        ticketId: tr.ticketId,
        scenarioId: activeScenario.id,
        priorAlarms: priorOpen,
        createdAt: Date.now(),
      });
    });

    if (newAlarms.length > 0) setSessionAlarms(prev => [...prev, ...newAlarms]);
  }, [phase]);

  const handleResolve = useCallback((alarmId) => {
    setSessionAlarms(prev => prev.map(a => a.id === alarmId ? { ...a, status: "RESOLVED" } : a));
  }, []);

  const handleOverride = useCallback((siteId, triage) => {
    setOverrides(prev => {
      if (prev[siteId]) {
        const { [siteId]: _, ...rest } = prev;
        return rest;
      }
      const levels = ["P5", "P4", "P3", "P2", "P1"];
      const bumped = levels[Math.max(0, levels.indexOf(triage.priority) - 1)];
      return { ...prev, [siteId]: { priority: bumped, reason: "Manual override by NOC engineer" } };
    });
  }, []);

  const totalActive = sessionAlarms.filter(a => a.status !== "RESOLVED").length;

  const getSiteHealth = (siteId) => {
    const open = sessionAlarms.filter(a => a.siteId === siteId && a.status !== "RESOLVED");
    if (open.some(a => a.priority === "P1")) return "critical";
    if (open.some(a => ["P2", "P3"].includes(a.priority))) return "degraded";
    return "healthy";
  };
  const hColor = (h) => h === "critical" ? C.red : h === "degraded" ? C.orange : C.green;

  return (
    <div style={{
      fontFamily: "'JetBrains Mono', 'Fira Code', 'Courier New', monospace",
      background: C.bg, color: C.text,
      height: "100vh", display: "flex", flexDirection: "column", fontSize: "15px",
    }}>
      <style>{"\n        @import url('https://fonts.googleapis.com/css2?family=JetBrains+Mono:wght@400;700;800&display=swap');\n        * { box-sizing: border-box; }\n        ::-webkit-scrollbar { width: 5px; height: 5px; }\n        ::-webkit-scrollbar-track { background: " + C.surface2 + "; }\n        ::-webkit-scrollbar-thumb { background: " + C.border + "; border-radius: 3px; }\n        @keyframes ping { 0% { transform: scale(1); opacity: 0.4; } 100% { transform: scale(2.4); opacity: 0; } }\n        @keyframes blink { 0%,100% { opacity: 1; } 50% { opacity: 0; } }\n        @keyframes glow-red { 0%,100% { box-shadow: 0 0 4px 2px #d9302566; } 50% { box-shadow: 0 0 12px 5px #d9302599; } }\n        @keyframes glow-orange { 0%,100% { box-shadow: 0 0 4px 2px #e8650a55; } 50% { box-shadow: 0 0 10px 4px #e8650a88; } }\n        .cursor::after { content: '|'; animation: blink 1s step-end infinite; color: " + C.cyan + "; }\n        .node-fault { animation: glow-red 1.4s ease-in-out infinite; }\n        .node-impacted { animation: glow-orange 1.8s ease-in-out infinite; }\n      "}</style>

      {/* TOP BAR - deep navy */}
      <div style={{
        background: C.topbar, borderBottom: "1px solid #1e293b",
        display: "flex", alignItems: "stretch", flexShrink: 0, height: 48, padding: "0 4px 0 20px",
      }}>
        <div style={{ display: "flex", alignItems: "center", paddingRight: 20, flexShrink: 0, gap: 8 }}>
          <div style={{
            width: 7, height: 7, borderRadius: "50%", background: C.cyan,
            boxShadow: "0 0 8px " + (C.cyan),
          }} />
          <span style={{ color: "#e2e8f0", fontWeight: 700, fontSize: "13px", letterSpacing: "0.1em", whiteSpace: "nowrap" }}>
            NOC TRIAGE AGENT
          </span>
          <span style={{
            background: C.cyan + "33", color: C.cyan, border: "1px solid " + (C.cyan) + "55",
            borderRadius: "3px", padding: "1px 6px", fontSize: "9px", fontWeight: 700, letterSpacing: "0.1em",
          }}>PHASE 3</span>
        </div>
        <div style={{ width: 1, background: "#334155", margin: "10px 4px", flexShrink: 0 }} />

        <NavTabBtn label="ALARM VIEW" active={view === "alarm"} onClick={() => setView("alarm")} />
        <NavTabBtn
          label="SITE VIEW" active={view === "site"} onClick={() => setView("site")}
          badge={totalActive > 0 ? String(totalActive) : null}
        />

        <div style={{ width: 1, background: "#334155", margin: "10px 12px", flexShrink: 0 }} />
        <div style={{ display: "flex", alignItems: "center", gap: 6, padding: "0 8px" }}>
          <span style={{ color: "#64748b", fontSize: "10px", letterSpacing: "0.06em" }}>ACTIVE</span>
          <span style={{
            color: totalActive > 0 ? "#f87171" : "#64748b",
            fontWeight: 800, fontSize: "15px", minWidth: 20,
          }}>{totalActive}</span>
          <span style={{ color: "#64748b", fontSize: "10px", letterSpacing: "0.06em" }}>ALARMS</span>
        </div>

        {/* Site health pills */}
        <div style={{ marginLeft: "auto", display: "flex", alignItems: "center", gap: 12, padding: "0 16px" }}>
          {Object.values(SITE_META).map(meta => {
            const h = getSiteHealth(meta.id);
            return (
              <div key={meta.id} style={{ display: "flex", alignItems: "center", gap: 5 }}>
                <Dot color={hColor(h)} pulse={h !== "healthy"} />
                <span style={{ color: "#94a3b8", fontSize: "10px", letterSpacing: "0.04em" }}>{meta.shortId}</span>
              </div>
            );
          })}
        </div>
      </div>

      {/* SUBMENU - slate */}
      <div style={{
        background: C.submenu, borderBottom: "1px solid #0f172a",
        padding: "8px 20px", display: "flex", alignItems: "center", gap: 8,
        flexShrink: 0, minHeight: 44, flexWrap: "wrap",
      }}>
        {view === "alarm" ? (
          <>
            <span style={{ color: "#64748b", fontSize: "9px", letterSpacing: "0.12em", marginRight: 4 }}>SCENARIOS</span>
            {SCENARIOS.map(scn => (
              <button key={scn.id} onClick={() => runner.run(scn.id)} style={{
                background: runner.activeScenario?.id === scn.id && runner.phase !== "idle"
                  ? "#38bdf822" : "#ffffff0a",
                border: "1px solid " + (runner.activeScenario?.id === scn.id && runner.phase !== "idle" ? "#38bdf8" : "#334155"),
                borderRadius: "2px",
                color: runner.activeScenario?.id === scn.id && runner.phase !== "idle" ? "#38bdf8" : "#94a3b8",
                fontFamily: "inherit", fontSize: "10px", padding: "4px 10px",
                cursor: "pointer", letterSpacing: "0.06em", transition: "all 0.15s",
              }}>{scn.id}: {scn.label}</button>
            ))}
          </>
        ) : (
          <>
            <span style={{ color: "#64748b", fontSize: "9px", letterSpacing: "0.12em", marginRight: 4 }}>SITES</span>
            {Object.values(SITE_META).map(meta => {
              const h = getSiteHealth(meta.id);
              const openCount = sessionAlarms.filter(a => a.siteId === meta.id && a.status !== "RESOLVED").length;
              return (
                <div key={meta.id} style={{
                  display: "flex", alignItems: "center", gap: 5,
                  background: "#ffffff0a", border: "1px solid #334155", borderRadius: "2px",
                  padding: "4px 10px", fontSize: "10px",
                }}>
                  <Dot color={hColor(h)} pulse={h !== "healthy"} />
                  <span style={{ color: "#94a3b8" }}>{meta.shortId}</span>
                  <Badge label={meta.oem} color={meta.oem === "STRATUM" ? C.cyan : C.orange} small />
                  {openCount > 0 && <Badge label={String(openCount)} color={C.red} small />}
                </div>
              );
            })}
          </>
        )}
      </div>

      {/* MAIN CONTENT */}
      <div style={{ flex: 1, display: "flex", overflow: "hidden" }}>
        {view === "alarm"
          ? <AlarmView
              runner={runner}
              sessionAlarms={sessionAlarms}
              onOverride={handleOverride}
              overrides={overrides}
            />
          : <SiteView
              sessionAlarms={sessionAlarms}
              allTriageResults={allTriageResults}
              onResolve={handleResolve}
              onOverride={handleOverride}
              overrides={overrides}
            />
        }
      </div>
    </div>
  );
}
