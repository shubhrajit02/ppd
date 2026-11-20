"use client";
import * as Dialog from "@radix-ui/react-dialog";
import { useQuery } from "@tanstack/react-query";
import { Check, Copy, Download, X } from "lucide-react";
import { useState } from "react";
import { api } from "@/lib/api";
import type { Finding, SuggestedFix } from "@/lib/types";
import { ErrorState, Loading } from "./ui";

export function PatchDialog({ reviewId, finding }: { reviewId: string; finding: Finding }) {
  const [open, setOpen] = useState(false);
  const [copied, setCopied] = useState(false);
  const [copyError, setCopyError] = useState("");
  const query = useQuery({ queryKey: ["patch", reviewId, finding.id], enabled: open,
    queryFn: () => api<SuggestedFix>(`/reviews/${reviewId}/fixes/${finding.id}`, { method: "POST" }) });
  async function copy() { try { await navigator.clipboard.writeText(query.data?.unified_diff || ""); setCopied(true); setCopyError(""); } catch { setCopyError("Clipboard is unavailable. Download the patch instead."); } }
  function download() { const url = URL.createObjectURL(new Blob([query.data?.unified_diff || ""], { type: "text/plain" })); const a = document.createElement("a"); a.href = url; a.download = `${finding.id}.patch`; a.click(); URL.revokeObjectURL(url); }
  return <Dialog.Root open={open} onOpenChange={setOpen}><Dialog.Trigger asChild><button className="button secondary small">View patch</button></Dialog.Trigger><Dialog.Portal><Dialog.Overlay className="dialog-overlay" /><Dialog.Content className="dialog-content"><div className="dialog-heading"><div><p className="eyebrow">SUGGESTED CHANGE</p><Dialog.Title>Inspect the patch</Dialog.Title></div><Dialog.Close asChild><button aria-label="Close patch" className="icon-button"><X size={20} aria-hidden /></button></Dialog.Close></div><Dialog.Description className="muted">{finding.file} · Review this suggestion before applying it. Your source has not been changed.</Dialog.Description>
    {query.isPending ? <Loading text="Loading validated patch…" /> : query.error ? <ErrorState error={query.error} retry={() => query.refetch()} /> : <><pre className="patch-code" tabIndex={0}>{query.data.unified_diff?.split("\n").map((line, i) => <span key={i} className={line.startsWith("+") ? "diff-add" : line.startsWith("-") ? "diff-remove" : line.startsWith("@@") ? "diff-hunk" : ""}>{line}{"\n"}</span>)}</pre><p>{query.data.explanation}</p><div className="dialog-actions"><button className="button secondary" onClick={download}><Download size={16} aria-hidden /> Download patch</button><button className="button" onClick={copy}>{copied ? <Check size={16} aria-hidden /> : <Copy size={16} aria-hidden />}{copied ? "Copied" : "Copy patch"}</button></div><p role="status" className="field-hint">{copyError || (copied ? "Patch copied to clipboard." : "")}</p></>}
  </Dialog.Content></Dialog.Portal></Dialog.Root>;
}
