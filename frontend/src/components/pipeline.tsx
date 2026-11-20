"use client";
import { motion } from "motion/react";
import { Check, Circle, LoaderCircle, Minus, X, Shield, GitBranch, Activity, Blocks } from "lucide-react";
import { duration } from "@/lib/format";
import type { PipelineEvent } from "@/lib/types";

const stages = [{ id: "SCANNING", title: "Source", desc: "Snapshot indexed" }, { id: "PARSING", title: "Parse", desc: "Syntax and symbols" },
  { id: "STATIC_ANALYSIS", title: "Analyze", desc: "Deterministic rules" }, { id: "AI_ANALYSIS", title: "Specialists", desc: "Optional AI specialists" },
  { id: "VALIDATING", title: "Validate", desc: "Evidence checked" }, { id: "SYNTHESIZING", title: "Synthesize", desc: "Findings and score" }];
export function Pipeline({ events, status }: { events: PipelineEvent[]; status: string }) {
  const isTerminal = ["COMPLETED", "FAILED", "CANCELLED"].includes(status);
  return <section className="pipeline-panel" aria-label="Review execution"><div className="panel-heading"><h2>Execution trace</h2><span className="micro">{events.length} RECORDED EVENTS</span></div>
    <div className="pipeline-stages">{stages.map(stage => {
      const stageEvents = events.filter(e => e.stage === stage.id && !e.agent);
      const latest = stageEvents.at(-1);
      const state = latest?.state || "WAITING";
      const running = state === "RUNNING" && !isTerminal;
      const interrupted = state === "RUNNING" && isTerminal;
      return <motion.div layout className={`pipeline-stage ${running ? "running" : state.toLowerCase()}`} key={stage.id}>
        <span className="pipeline-node">{running ? <LoaderCircle className="spin" size={17} aria-hidden /> : state === "COMPLETED" ? <Check size={17} aria-hidden /> : state === "SKIPPED" ? <Minus size={17} aria-hidden /> : state === "FAILED" || interrupted ? <X size={17} aria-hidden /> : <Circle size={14} aria-hidden />}</span>
        <strong>{stage.title}</strong><small>{state === "SKIPPED" ? "Disabled" : interrupted ? "Interrupted" : running ? "Running" : state === "COMPLETED" ? "Complete" : state === "FAILED" ? "Failed" : "Waiting"}</small>
        <span>{latest?.duration_seconds ? duration(latest.duration_seconds) : stage.desc}</span></motion.div>;
    })}</div>
    <div className="agent-strip"><span className="micro">SPECIALISTS</span>{["SECURITY", "BUG", "PERFORMANCE", "MAINTAINABILITY"].map(agent => {
      const runs = events.filter(e => e.agent === agent);
      const last = runs.at(-1);
      const count = runs.filter(e => e.state === "COMPLETED").reduce((n, e) => n + e.findings, 0);
      const disabled = events.some(e => e.stage === "AI_ANALYSIS" && e.state === "SKIPPED");
      const Icon = agent === "SECURITY" ? Shield : agent === "BUG" ? GitBranch : agent === "PERFORMANCE" ? Activity : Blocks;
      return <div key={agent}><Icon size={14} aria-hidden /><span className={`agent-dot ${last?.state.toLowerCase() || ""}`} /><strong>{agent === "MAINTAINABILITY" ? "MAINT" : agent === "PERFORMANCE" ? "PERF" : agent === "SECURITY" ? "SEC" : "BUG"}</strong><span>{disabled ? "disabled" : last ? `${last.state === "RUNNING" && isTerminal ? "interrupted" : last.state.toLowerCase()} · ${count} findings` : isTerminal ? "not run" : "waiting"}</span></div>;
    })}</div>
    <details className="event-details"><summary>View event log</summary><ol>{events.map(e => <li key={e.sequence}><span>{new Date(e.created_at).toLocaleTimeString()}</span><strong>{e.label}</strong><span>{e.state.toLowerCase()}{e.findings ? ` · ${e.findings} findings` : ""}</span></li>)}</ol></details></section>;
}
