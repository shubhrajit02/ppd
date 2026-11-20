"use client";
import { motion } from "motion/react";
import type { Report } from "@/lib/types";
import { label } from "@/lib/format";

export function Score({ report }: { report: Report }) {
  const { score } = report;
  return <details className="score-explanation"><summary aria-label={`Review score ${score.value}. Why this score?`}><motion.strong key={score.value} initial={{ opacity: 0 }} animate={{ opacity: 1 }}>{score.value}</motion.strong><span>REVIEW SCORE<small>Why this score?</small></span></summary><div className="score-popover"><h2>Why {score.value}?</h2><p>{score.formula}</p><p className="field-hint">A heuristic review score, not a safety certification. Categories below show actual penalty points, not separate AI ratings.</p><div className="score-categories">{["SECURITY", "BUG", "PERFORMANCE", "MAINTAINABILITY"].map(category => { const ids = new Set(report.findings.filter(f => f.category === category).map(f => f.id)); const penalty = score.penalties.filter(p => ids.has(p.finding_id)).reduce((sum, p) => sum + p.points, 0); return <div key={category}><span>{label(category)}</span><strong>−{Math.round(penalty * 100) / 100}</strong></div>; })}</div><ul>{score.penalties.map(p => <li key={p.finding_id}>{report.findings.find(f => f.id === p.finding_id)?.title}: −{p.points}<small>{p.explanation}</small></li>)}</ul>{!score.penalties.length && <p>No penalties from the analyzed scope.</p>}</div></details>;
}
