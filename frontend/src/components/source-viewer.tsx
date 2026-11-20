"use client";
import { useEffect, useMemo, useState } from "react";
import Prism from "prismjs";
import "prismjs/components/prism-python";
import "prismjs/components/prism-typescript";
import "prismjs/components/prism-jsx";
import "prismjs/components/prism-tsx";
import {
  AlertCircle,
  AlertTriangle,
  Check,
  CheckCircle2,
  ChevronLeft,
  ChevronRight,
  Copy,
  FileCode2,
  Info,
  Sparkles,
} from "lucide-react";
import type { Finding, FindingState, SourceFile } from "@/lib/types";
import { PatchDialog } from "./patch-dialog";

type Piece = { text: string; types: string[] };

function tokensByLine(source: string, language: string): Piece[][] {
  const grammar = Prism.languages[language === "tsx" ? "tsx" : language] || Prism.languages.javascript;
  const rows: Piece[][] = [[]];
  function visit(token: string | Prism.Token | (string | Prism.Token)[], types: string[] = []) {
    if (Array.isArray(token)) { token.forEach(t => visit(t, types)); return; }
    if (typeof token !== "string") { visit(token.content, [...types, token.type]); return; }
    token.split("\n").forEach((text, i) => { if (i) rows.push([]); rows[rows.length - 1].push({ text, types }); });
  }
  visit(Prism.tokenize(source, grammar));
  return rows;
}

function resolveFix(finding: Finding, lineText: string, language: string): {
  original: string;
  replacement: string;
  explanation: string;
} {
  if (finding.suggested_fix) {
    return {
      original: finding.suggested_fix.original || lineText,
      replacement: finding.suggested_fix.replacement,
      explanation: finding.suggested_fix.explanation || finding.recommendation,
    };
  }

  const trimmed = lineText.trim();

  // Smart resolution for Python code
  if (language === "python" || finding.file.endsWith(".py")) {
    const cTypeMatch = trimmed.match(/^(int|float|double|char|bool|long|short|void)\s+([^;]+);?$/i);
    if (cTypeMatch) {
      const vars = cTypeMatch[2].split(",").map(v => v.trim()).filter(Boolean);
      return {
        original: lineText,
        replacement: `# In Python, variables are created on assignment (e.g. ${vars.map(v => `${v} = 0`).join(", ")})`,
        explanation: "Python variables do not use static type declarations. Variables are initialized upon assignment.",
      };
    }

    if (/^[a-zA-Z_]\w*\s*\d+\s*;?$/.test(trimmed)) {
      const varName = trimmed.match(/^[a-zA-Z_]\w*/)?.[0] || "";
      const num = trimmed.match(/\d+/)?.[0] || "";
      return {
        original: lineText,
        replacement: `${varName} = ${num}`,
        explanation: `Assign variable directly: '${varName} = ${num}'.`,
      };
    }

    if (trimmed.endsWith(";")) {
      return {
        original: lineText,
        replacement: lineText.replace(/;+\s*$/, ""),
        explanation: "Remove trailing semicolon (optional in Python).",
      };
    }
  }

  return {
    original: lineText || finding.code_snippet,
    replacement: "",
    explanation: finding.recommendation || "Review the issue details and apply the recommended changes.",
  };
}

export interface SourceViewerProps {
  file: SourceFile;
  selectedLine: number;
  findings: Finding[];
  reviewId?: string;
  selectedFindingId?: string;
  onSelectFinding?: (finding: Finding) => void;
  onTriage?: (findingId: string, state: FindingState) => void;
  findingStates?: Record<string, FindingState>;
}

export function SourceViewer({
  file,
  selectedLine,
  findings,
  reviewId,
  selectedFindingId,
  onSelectFinding,
  onTriage,
  findingStates,
}: SourceViewerProps) {
  const [mode, setMode] = useState<"source" | "diff">("source");
  const [copiedId, setCopiedId] = useState<string | null>(null);
  const lines = useMemo(() => file.content.split(/\r?\n/), [file.content]);
  const [start, setStart] = useState(Math.max(0, selectedLine - 80));
  const end = Math.min(lines.length, start + 300);
  const visible = useMemo(
    () => tokensByLine(lines.slice(start, end).join("\n"), file.language),
    [file.language, lines, start, end]
  );

  useEffect(() => {
    if (selectedLine > 0 && (selectedLine <= start || selectedLine > end)) {
      setStart(Math.max(0, selectedLine - 80));
    }
  }, [selectedLine, start, end]);

  useEffect(() => {
    if (mode === "source" && selectedLine > 0) {
      document.getElementById(`source-line-${selectedLine}`)?.scrollIntoView({ block: "nearest" });
    }
  }, [selectedLine, mode]);

  async function copyCorrection(id: string, text: string) {
    try {
      await navigator.clipboard.writeText(text);
      setCopiedId(id);
      setTimeout(() => setCopiedId(null), 2000);
    } catch {
      // ignore clipboard error
    }
  }

  return (
    <section className="source-panel" tabIndex={-1} aria-label="Source viewer">
      <div className="source-toolbar">
        <div>
          <FileCode2 size={16} aria-hidden />
          <strong>{file.path.split("/").at(-1)}</strong>
          <span className="micro">{file.language}</span>
          {findings.length > 0 && (
            <span className="source-finding-count" title={`${findings.length} findings in this file`}>
              {findings.length} {findings.length === 1 ? "issue" : "issues"}
            </span>
          )}
        </div>
        <div className="segmented" role="group" aria-label="Source view mode">
          <button aria-pressed={mode === "source"} onClick={() => setMode("source")}>
            Source
          </button>
          <button aria-pressed={mode === "diff"} disabled={!file.patch} onClick={() => setMode("diff")}>
            Diff
          </button>
        </div>
      </div>
      <div className="source-path">
        <span>{file.path}</span>
        <span>{lines.length} lines · Read only</span>
      </div>

      {mode === "diff" ? (
        <div className="diff-view" tabIndex={0} aria-label="Unified source diff">
          <pre>
            {file.patch?.split("\n").map((line, i) => (
              <span
                key={i}
                className={
                  line.startsWith("+")
                    ? "diff-add"
                    : line.startsWith("-")
                    ? "diff-remove"
                    : line.startsWith("@@")
                    ? "diff-hunk"
                    : ""
                }
              >
                {line || " "}
                {"\n"}
              </span>
            ))}
          </pre>
        </div>
      ) : (
        <div className="source-scroll" tabIndex={0} aria-label={`${file.path} source code`}>
          <table className="code-table">
            <tbody>
              {visible.map((pieces, index) => {
                const n = start + index + 1;
                const lineFindings = findings.filter(f => f.lines.start <= n && f.lines.end >= n);
                const inlineFindings = findings.filter(
                  f => f.lines.end === n || (f.lines.start === n && f.lines.end < n)
                );
                const changed = file.changed_lines?.some(r => n >= r.start && n <= r.end);
                const hasFinding = lineFindings.length > 0;
                const primaryIssue = lineFindings[0];
                const primarySeverity = primaryIssue ? primaryIssue.severity.toLowerCase() : "";

                return (
                  <tr key={`line-group-${n}`} className="code-line-group">
                    <td colSpan={3} className="code-line-group-cell">
                      <div
                        id={`source-line-${n}`}
                        data-testid={`source-line-${n}`}
                        data-selected={n === selectedLine}
                        className={`source-code-row ${n === selectedLine ? "selected-line" : ""} ${
                          changed ? "changed-line" : ""
                        } ${hasFinding ? `has-finding finding-${primarySeverity}` : ""}`}
                      >
                        <div className="line-gutter">
                          {hasFinding && (
                            <button
                              type="button"
                              className={`line-marker-badge severity-badge-${primarySeverity}`}
                              title={`${primaryIssue.severity}: ${primaryIssue.title}`}
                              onClick={() => onSelectFinding?.(primaryIssue)}
                            >
                              {primaryIssue.severity === "CRITICAL" || primaryIssue.severity === "HIGH" ? (
                                <AlertCircle size={10} aria-hidden />
                              ) : primaryIssue.severity === "MEDIUM" ? (
                                <AlertTriangle size={10} aria-hidden />
                              ) : (
                                <Info size={10} aria-hidden />
                              )}
                            </button>
                          )}
                        </div>
                        <div className={`line-number ${hasFinding ? `num-${primarySeverity}` : ""}`}>{n}</div>
                        <div className="line-code">
                          <code>
                            {pieces.map((piece, i) => (
                              <span key={i} className={piece.types.map(t => `token ${t}`).join(" ")}>
                                {piece.text}
                              </span>
                            ))}
                          </code>
                        </div>
                      </div>

                      {/* Inline Error & Correction Callouts */}
                      {inlineFindings.map(f => {
                        const fix = resolveFix(f, lines[f.lines.start - 1] || "", file.language);
                        const isSelected = selectedFindingId === f.id;
                        const fSeverity = f.severity.toLowerCase();

                        return (
                          <div
                            key={`inline-finding-${f.id}`}
                            id={`inline-finding-${f.id}`}
                            data-testid={`inline-finding-${f.id}`}
                            className={`inline-finding-card severity-${fSeverity} ${
                              isSelected ? "selected-finding-card" : ""
                            }`}
                            onClick={() => onSelectFinding?.(f)}
                          >
                            {/* Card Header: Error Badges & Controls */}
                            <div className="inline-card-header">
                              <div className="inline-card-meta">
                                <span className={`badge badge-${fSeverity}`}>
                                  <span className="badge-dot" />
                                  {f.severity}
                                </span>
                                <span className="inline-category-badge">{f.category}</span>
                                <code className="inline-rule-badge">{f.rule_id}</code>
                                <span className="inline-line-ref">
                                  Line {f.lines.start}
                                  {f.lines.end !== f.lines.start ? `–${f.lines.end}` : ""}
                                </span>
                              </div>
                              <div className="inline-card-actions" onClick={e => e.stopPropagation()}>
                                {f.suggested_fix && reviewId && (
                                  <PatchDialog reviewId={reviewId} finding={f} />
                                )}
                                {onTriage && (
                                  <select
                                    className="inline-triage-select"
                                    aria-label={`State for ${f.title}`}
                                    value={findingStates?.[f.id] || "OPEN"}
                                    onChange={e => onTriage(f.id, e.target.value as FindingState)}
                                  >
                                    <option value="OPEN">Open</option>
                                    <option value="RESOLVED">Resolved</option>
                                    <option value="IGNORED">Ignored</option>
                                  </select>
                                )}
                              </div>
                            </div>

                            {/* Error Details */}
                            <div className="inline-error-body">
                              <div className="inline-error-title-row">
                                <AlertCircle size={15} className={`severity-icon-${fSeverity}`} aria-hidden />
                                <strong className="inline-error-title">{f.title}</strong>
                              </div>
                              <p className="inline-error-desc">{f.description}</p>
                            </div>

                            {/* Correction Section */}
                            <div className="inline-correction-section">
                              <div className="inline-correction-top">
                                <div className="inline-correction-label">
                                  <Sparkles size={13} aria-hidden />
                                  <strong>Correction & Suggested Fix</strong>
                                </div>
                                {fix.replacement && (
                                  <button
                                    type="button"
                                    className="inline-copy-fix-btn"
                                    onClick={e => {
                                      e.stopPropagation();
                                      copyCorrection(f.id, fix.replacement);
                                    }}
                                    title="Copy correction to clipboard"
                                  >
                                    {copiedId === f.id ? <Check size={12} /> : <Copy size={12} />}
                                    <span>{copiedId === f.id ? "Copied" : "Copy fix"}</span>
                                  </button>
                                )}
                              </div>

                              {fix.explanation && (
                                <p className="inline-fix-explanation">{fix.explanation}</p>
                              )}

                              {/* Diff: Current Error vs Correction */}
                              <div className="inline-diff-display">
                                {fix.original && (
                                  <div className="diff-line diff-remove">
                                    <span className="diff-marker" aria-hidden>-</span>
                                    <code className="diff-text">{fix.original.replace(/\r?\n$/, "")}</code>
                                    <span className="diff-tag remove-tag">Current Error</span>
                                  </div>
                                )}
                                {fix.replacement ? (
                                  <div className="diff-line diff-add">
                                    <span className="diff-marker" aria-hidden>+</span>
                                    <code className="diff-text">{fix.replacement.replace(/\r?\n$/, "")}</code>
                                    <span className="diff-tag add-tag">Correction</span>
                                  </div>
                                ) : (
                                  <div className="diff-line diff-remove-note">
                                    <span className="diff-marker" aria-hidden>—</span>
                                    <span className="diff-text-muted">Remove this statement</span>
                                    <span className="diff-tag add-tag">Correction</span>
                                  </div>
                                )}
                              </div>

                              {f.recommendation && f.recommendation !== fix.explanation && (
                                <p className="inline-extra-recommendation">
                                  <strong>Recommendation:</strong> {f.recommendation}
                                </p>
                              )}
                            </div>
                          </div>
                        );
                      })}
                    </td>
                  </tr>
                );
              })}
            </tbody>
          </table>
        </div>
      )}
      <div className="source-footer">
        <span>
          {mode === "source"
            ? `Lines ${start + 1}–${end} of ${lines.length}`
            : "Unified diff · new-side review scope"}
        </span>
        {mode === "source" && lines.length > 300 && (
          <div>
            <button
              className="icon-button"
              aria-label="Previous source lines"
              disabled={start === 0}
              onClick={() => setStart(Math.max(0, start - 300))}
            >
              <ChevronLeft size={16} aria-hidden />
            </button>
            <button
              className="icon-button"
              aria-label="Next source lines"
              disabled={end === lines.length}
              onClick={() => setStart(start + 300)}
            >
              <ChevronRight size={16} aria-hidden />
            </button>
          </div>
        )}
        <span>UTF-8</span>
      </div>
    </section>
  );
}
