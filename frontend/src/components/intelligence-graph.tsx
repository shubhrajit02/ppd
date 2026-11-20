"use client";
import dynamic from "next/dynamic";
import { useEffect, useRef, useState } from "react";
import { useReducedMotion } from "motion/react";
import { GitBranch, Pause, Play } from "lucide-react";
import type { PipelineEvent } from "@/lib/types";

const Scene = dynamic(() => import("./graph-scene"), { ssr: false, loading: () => <StaticGraph /> });
export const graphNodes = [
  { x: 0, y: 0, label: "Repository", color: "#c2ee85", kind: "core" },
  { x: -2, y: 1.2, label: "Files", color: "#98bce8", kind: "file" },
  { x: -2, y: -1.2, label: "Symbols", color: "#98bce8", kind: "symbol" },
  { x: 0.1, y: 2.2, label: "Security", color: "#e8ad9c", kind: "agent" },
  { x: 2.3, y: 1.1, label: "Bug & logic", color: "#d0b4ec", kind: "agent" },
  { x: 2.3, y: -1.1, label: "Performance", color: "#e6c785", kind: "agent" },
  { x: 0.1, y: -2.2, label: "Maintainability", color: "#98bce8", kind: "agent" },
  { x: 3.7, y: 0, label: "Validated", color: "#c2ee85", kind: "result" },
];
export const graphEdges = [[0, 1], [1, 2], [2, 0], [0, 3], [0, 4], [0, 5], [0, 6], [3, 7], [4, 7], [5, 7], [6, 7]];
export function StaticGraph() {
  return <svg className="static-graph" viewBox="0 0 640 400" role="img" aria-label="Pipeline schematic: repository, files and symbols connect to four specialists and validated findings">
    {graphEdges.map(([a, b]) => <path key={`${a}-${b}`} d={`M ${260 + graphNodes[a].x * 65} ${190 - graphNodes[a].y * 60} L ${260 + graphNodes[b].x * 65} ${190 - graphNodes[b].y * 60}`} stroke="#435149" fill="none" />)}
    {graphNodes.map(n => <g key={n.label} transform={`translate(${260 + n.x * 65},${190 - n.y * 60})`}><circle r={n.kind === "core" ? 25 : 10} fill="#1b2421" stroke={n.color} strokeWidth="1.5" /><circle r="3" fill={n.color} /><text y={n.kind === "core" ? 46 : 28} textAnchor="middle" fill="#cad4cc" fontSize="12">{n.label}</text></g>)}
  </svg>;
}
export function IntelligenceGraph({ events = [], status = "ILLUSTRATION" }: { events?: PipelineEvent[]; status?: string }) {
  const reduced = useReducedMotion();
  const root = useRef<HTMLDivElement>(null);
  const [eligible, setEligible] = useState(false);
  const [visible, setVisible] = useState(false);
  const [paused, setPaused] = useState(false);
  useEffect(() => {
    const mq = matchMedia("(min-width: 801px) and (pointer: fine)");
    const sync = () => setEligible(mq.matches && navigator.hardwareConcurrency >= 4);
    sync(); mq.addEventListener("change", sync);
    let onScreen = false;
    const update = () => setVisible(onScreen && !document.hidden);
    const observer = new IntersectionObserver(([entry]) => { onScreen = entry.isIntersecting; update(); });
    if (root.current) observer.observe(root.current);
    document.addEventListener("visibilitychange", update);
    return () => { observer.disconnect(); mq.removeEventListener("change", sync); document.removeEventListener("visibilitychange", update); };
  }, []);
  const latest = events.filter(e => !e.agent).at(-1);
  const illustrated = status === "ILLUSTRATION";
  const active = illustrated || !["COMPLETED", "FAILED", "CANCELLED"].includes(status);
  return <div className="intelligence-graph" ref={root} data-testid="intelligence-graph">
    <div className="graph-heading"><span><GitBranch size={15} aria-hidden /> CODE INTELLIGENCE GRAPH</span>{eligible && !reduced && <button className="icon-button" aria-label={paused ? "Resume graph motion" : "Pause graph motion"} onClick={() => setPaused(!paused)}>{paused ? <Play size={15} /> : <Pause size={15} />}</button>}</div>
    <div className="graph-viewport">{eligible && !reduced && visible ? <Scene moving={!paused && active} sequence={latest?.sequence ?? 0} stage={latest?.stage || "SCANNING"} /> : <StaticGraph />}</div>
    <div className="graph-caption"><span className="micro">{illustrated ? "PIPELINE SCHEMATIC / NOT A LIVE REVIEW" : "PIPELINE SCHEMATIC / LIVE EXECUTION"}</span><p>{illustrated ? "Source → syntax → specialist review → grounded evidence" : `${latest?.label || "Queued"} · ${latest?.completed ?? 0}/${latest?.total ?? 0} work units · ${latest?.findings ?? 0} stage findings`}</p></div>
  </div>;
}
