"use client";
import Link from "next/link";
import { useEffect, useState } from "react";
import { motion } from "motion/react";
import { useMutation, useQuery, useQueryClient } from "@tanstack/react-query";
import { ArrowLeft, ChevronLeft, ChevronRight, Download, FileCode2, ShieldCheck } from "lucide-react";
import { api, getReview } from "@/lib/api";
import type { Finding, FindingState, PipelineEvent, SourceFile } from "@/lib/types";
import { severities, terminal } from "@/lib/types";
import { duration, label } from "@/lib/format";
import { Badge, EmptyState, ErrorState, Loading } from "./ui";
import { Pipeline } from "./pipeline";
import { SourceViewer } from "./source-viewer";
import { PatchDialog } from "./patch-dialog";
import { IntelligenceGraph } from "./intelligence-graph";
import { Score } from "./score";
import { usePreferences } from "@/lib/preferences";

export function ReviewWorkspace({ id }: { id: string }) {
  const client = useQueryClient();
  const [preferences] = usePreferences();
  const review = useQuery({ queryKey: ["review", id], queryFn: ({ signal }) => getReview(id, signal), refetchInterval: q => !q.state.data || !terminal.has(q.state.data.status) ? 700 : false });
  const active = !review.data || !terminal.has(review.data.status);
  const events = useQuery({ queryKey: ["events", id], queryFn: () => api<PipelineEvent[]>(`/reviews/${id}/events`), refetchInterval: active ? 700 : false, enabled: !!review.data });
  const sources = useQuery({ queryKey: ["sources", id], queryFn: () => api<SourceFile[]>(`/reviews/${id}/files`), enabled: !!review.data?.sources_available });
  useEffect(() => { if (!active) { client.invalidateQueries({ queryKey: ["events", id] }); client.invalidateQueries({ queryKey: ["dashboard"] }); client.invalidateQueries({ queryKey: ["reviews"] }); } }, [active, client, id]);
  const cancel = useMutation({ mutationFn: () => api(`/reviews/${id}/cancel`, { method: "POST" }), onSuccess: () => client.invalidateQueries({ queryKey: ["review", id] }) });
  const triage = useMutation({ mutationFn: ({ finding, state }: { finding: string; state: FindingState }) => api(`/reviews/${id}/findings/${finding}`, { method: "PATCH", body: JSON.stringify({ state }) }), onSuccess: () => { client.invalidateQueries({ queryKey: ["review", id] }); client.invalidateQueries({ queryKey: ["dashboard"] }); } });
  const [selectedId, setSelectedId] = useState("");
  const [activePath, setActivePath] = useState("");
  const [fileFilter, setFileFilter] = useState("");
  const [severity, setSeverity] = useState("");
  const [category, setCategory] = useState("");
  const [state, setState] = useState("");
  const [mobileView, setMobileView] = useState("findings");
  const [filesHidden, setFilesHidden] = useState(false);
  const [findingsHidden, setFindingsHidden] = useState(false);
  const [fileSearch, setFileSearch] = useState("");
  function reset() { setFileFilter(""); setCategory(""); setSeverity(""); setState(""); setActivePath(""); setSelectedId(""); }
  useEffect(() => {
    const command = (event: Event) => {
      const action = (event as CustomEvent<string>).detail;
      if (action === "critical") { setSeverity("CRITICAL"); setActivePath(""); setMobileView("findings"); }
      if (action === "security") { setCategory("SECURITY"); setActivePath(""); setMobileView("findings"); }
      if (action === "reset") reset();
      if (action === "files") { setFilesHidden(v => !v); setMobileView("files"); }
      if (action === "findings") { setFindingsHidden(v => !v); setMobileView("findings"); }
      if (action === "next") document.querySelector<HTMLButtonElement>('[aria-label="Next finding"]')?.click();
    };
    window.addEventListener("aicr-command", command); return () => window.removeEventListener("aicr-command", command);
  }, []);
  if (review.isPending) return <Loading text="Opening review…" />;
  if (review.error) return <ErrorState error={review.error} retry={() => review.refetch()} />;
  const job = review.data, report = job.report;
  const allFindings = report?.findings || [];
  const filtered = allFindings.filter(f => (preferences.includeInfo || f.severity !== "INFO" || severity === "INFO") && (!severity || f.severity === severity) && (!category || f.category === category) && (!fileFilter || f.file === fileFilter) && (!state || (job.finding_states[f.id] || "OPEN") === state));
  const selected = filtered.find(f => f.id === selectedId) || filtered[0];
  const source = sources.data?.find(f => f.path === (activePath || selected?.file)) || sources.data?.[0];
  const selectedLine = selected && selected.file === source?.path ? selected.lines.start : 0;
  function select(f: Finding) { setSelectedId(f.id); setActivePath(f.file); setFindingsHidden(false); }
  function exportReport() { if (!report) return; const url = URL.createObjectURL(new Blob([JSON.stringify(report, null, 2)], { type: "application/json" })); const a = document.createElement("a"); a.href = url; a.download = `aicr-${id}.json`; a.click(); URL.revokeObjectURL(url); }
  const selectedIndex = selected ? filtered.indexOf(selected) : -1;
  return <>
    <div className="review-header"><div><Link href="/app/history" className="back-link"><ArrowLeft size={14} aria-hidden /> Reviews</Link><h1>{job.title}</h1><div className="review-meta"><span>{label(job.kind)}</span><span>·</span><span>{report ? `${report.summary.files_reviewed} files` : "Preparing source"}</span><span>·</span><span>{duration(report?.summary.duration_seconds)}</span>{job.source_url && <a href={job.source_url} target="_blank" rel="noreferrer">View on GitHub</a>}</div></div><div className="review-header-right"><Badge value={job.status} />{report && <Score report={report} />}{active ? <button className="button secondary small" disabled={cancel.isPending || job.cancel_requested} onClick={() => cancel.mutate()}>{job.cancel_requested ? "Cancelling…" : "Cancel review"}</button> : report && <button className="icon-button export-button" onClick={exportReport} aria-label="Export JSON report"><Download size={18} aria-hidden /></button>}</div></div>
    {(cancel.error || triage.error) && <ErrorState error={cancel.error || triage.error} />}{triage.isSuccess && <p role="status" className="triage-status">Decision saved. Original report preserved.</p>}{job.error && <ErrorState error={new Error(job.error)} />}
    {job.status === "CANCELLED" && <div className="notice"><p>Review cancelled. <Link href="/app/new">Start another review</Link>.</p></div>}
    {active && <motion.div initial={{ opacity: 0 }} animate={{ opacity: 1 }} className="analysis-graph"><p role="status">{job.cancel_requested ? "Stopping after the current operation…" : events.data?.at(-1)?.label || "Review queued"}</p><IntelligenceGraph events={events.data || []} status={job.status} /><p>Progress and history are saved. You can leave this page.</p></motion.div>}
    {report && <>
      <div className="review-filterbar"><div><strong>Findings</strong><span className="count-pill">{filtered.length}</span></div><div className="filter-controls">
        <label className="sr-only" htmlFor="severity-filter">Severity filter</label><select id="severity-filter" value={severity} onChange={e => { setSeverity(e.target.value); setActivePath(""); setSelectedId(""); }}><option value="">All severities</option>{severities.map(s => <option key={s}>{s}</option>)}</select>
        <label className="sr-only" htmlFor="category-filter">Category filter</label><select id="category-filter" value={category} onChange={e => { setCategory(e.target.value); setActivePath(""); setSelectedId(""); }}><option value="">All categories</option>{Array.from(new Set(allFindings.map(f => f.category))).sort().map(c => <option key={c}>{c}</option>)}</select>
        <label className="sr-only" htmlFor="state-filter">Finding state</label><select id="state-filter" value={state} onChange={e => { setState(e.target.value); setActivePath(""); setSelectedId(""); }}><option value="">All states</option><option>OPEN</option><option>RESOLVED</option><option>IGNORED</option></select><button className="text-button" onClick={reset}>Reset</button>
      </div></div>
      <div className="workspace-tools"><div className="mobile-views" role="group" aria-label="Workspace view">{["code", "findings", "files"].map(view => <button key={view} aria-pressed={mobileView === view} onClick={() => setMobileView(view)}>{label(view)}</button>)}</div><div className="panel-controls"><button className="text-button" aria-pressed={!filesHidden} onClick={() => setFilesHidden(!filesHidden)}>{filesHidden ? "Show" : "Hide"} files</button><button className="text-button" aria-pressed={!findingsHidden} onClick={() => setFindingsHidden(!findingsHidden)}>{findingsHidden ? "Show" : "Hide"} findings</button></div><span className="field-hint">Ctrl / ⌘ K · Commands</span></div>
      <div className={`review-columns mobile-${mobileView} ${filesHidden ? "files-hidden" : ""} ${findingsHidden ? "findings-hidden" : ""}`}>
        <aside className="file-tree" aria-label="Review files"><div className="tree-heading"><strong>FILES</strong><span>{sources.data?.length ?? report.summary.files_reviewed}</span></div><label className="file-search"><span className="sr-only">Search files</span><input placeholder="Find a file…" value={fileSearch} onChange={e => setFileSearch(e.target.value)} /></label><button className={`all-files ${!fileFilter ? "selected" : ""}`} onClick={() => { setFileFilter(""); setActivePath(""); }}>All findings <span>{allFindings.length}</span></button>
          {sources.data?.filter(f => f.path.toLowerCase().includes(fileSearch.toLowerCase())).map(file => <button key={file.path} title={file.path} className={`file-tree-item ${source?.path === file.path ? "selected" : ""}`} onClick={() => { setActivePath(file.path); setFileFilter(file.path); setSelectedId(""); setMobileView("code"); }}><FileCode2 size={15} aria-hidden /><span>{file.path}</span>{file.changed_lines !== null && <i aria-label="Changed file">M</i>}<small>{allFindings.filter(f => f.file === file.path).length}</small></button>)}
          {!sources.data && <p className="field-hint">{job.sources_available ? "Loading source…" : "Source retention has expired."}</p>}<div className="tree-note"><ShieldCheck size={15} aria-hidden /><span>Immutable snapshot<br />No source edits</span></div>
        </aside>
        {sources.error ? <ErrorState error={sources.error} retry={() => sources.refetch()} /> : source ? <SourceViewer key={source.path} file={source} selectedLine={selectedLine} findings={allFindings.filter(f => f.file === source.path)} reviewId={id} selectedFindingId={selected?.id} onSelectFinding={select} onTriage={(finding, state) => triage.mutate({ finding, state })} findingStates={job.finding_states} /> : <div className="source-panel"><EmptyState title={job.sources_available ? "Source loading" : "Source snapshot unavailable"} body="Reports retain finding evidence. Full source snapshots expire after the configured retention period." action={false} /></div>}
        <aside className="findings-panel" aria-label="Review findings"><div className="findings-heading"><span>{filtered.length} {filtered.length === 1 ? "finding" : "findings"}</span><div><button className="icon-button" aria-label="Previous finding" disabled={selectedIndex <= 0} onClick={() => select(filtered[selectedIndex - 1])}><ChevronLeft size={17} aria-hidden /></button><button className="icon-button" aria-label="Next finding" disabled={selectedIndex < 0 || selectedIndex >= filtered.length - 1} onClick={() => select(filtered[selectedIndex + 1])}><ChevronRight size={17} aria-hidden /></button></div></div>
          <div className="findings-scroll">{!filtered.length ? <EmptyState title="No findings in this view" body="Try another file or reset the filters. A clear result is not proof that source is defect-free." action={false} /> : filtered.map(f => <motion.article layout="position" className={`finding-card ${selected?.id === f.id ? "selected" : ""}`} key={f.id}><button className="finding-select" aria-expanded={selected?.id === f.id} onClick={() => select(f)}><div><Badge value={f.severity} /><span className="finding-category">{label(f.category)}</span></div><h3>{f.title}</h3><span className="finding-location">{f.file}:{f.lines.start}</span></button>
            {selected?.id === f.id && <motion.div initial={{ opacity: 0 }} animate={{ opacity: 1 }} className="finding-body"><button className="text-button jump-code" onClick={() => { setMobileView("code"); requestAnimationFrame(() => document.querySelector<HTMLElement>(".source-panel")?.focus()); }}>Jump to code →</button><p>{f.description}</p><span className="micro">EVIDENCE</span><pre className="evidence-code">{f.code_snippet}</pre><span className="micro">RECOMMENDATION</span><p>{f.recommendation}</p><div className="confidence-row"><span>Confidence</span><strong>{Math.round(f.confidence * 100)}%</strong></div><div className="confidence-track"><span style={{ width: `${f.confidence * 100}%` }} /></div><div className="finding-trust"><ShieldCheck size={13} aria-hidden />{label(f.validation)} · {f.source === "static" ? "deterministic rule" : "AI suggestion"}</div><div className="finding-actions">{f.suggested_fix && <PatchDialog reviewId={id} finding={f} />}<label className="sr-only" htmlFor={`state-${f.id}`}>Decision for {f.title}</label><select id={`state-${f.id}`} disabled={triage.isPending} value={job.finding_states[f.id] || "OPEN"} onChange={e => triage.mutate({ finding: f.id, state: e.target.value as FindingState })}><option value="OPEN">Open</option><option value="RESOLVED">Resolved</option><option value="IGNORED">Ignored</option></select></div><details className="explain-details"><summary>Explain this finding</summary><p>Analyzer: {f.analyzer}. Rule: {f.rule_id}.</p>{f.validation_notes.map((note, i) => <p key={i}>{note}</p>)}<p>Score penalty: {report.score.penalties.find(p => p.finding_id === f.id)?.points ?? 0} points.</p><p className="mono-small">{report.score.penalties.find(p => p.finding_id === f.id)?.explanation}</p></details></motion.div>}
          </motion.article>)}</div>
        </aside>
      </div>
      {!!report.warnings.length && <details className="review-warnings"><summary>{report.warnings.length} review notes</summary><ul>{report.warnings.map((warning, i) => <li key={i}>{warning}</li>)}</ul></details>}
    </>}
    {events.error ? <ErrorState error={events.error} retry={() => events.refetch()} /> : <details className="execution-disclosure" open={active || undefined}><summary>Agent execution & timeline</summary><Pipeline events={events.data || []} status={job.status} /></details>}
    {report && <div className="score-note"><span>SCORING METHOD</span><p>{report.score.formula}. Severity, confidence and validation determine each penalty. Resolving a finding records your decision without changing the original report.</p></div>}
  </>;
}
