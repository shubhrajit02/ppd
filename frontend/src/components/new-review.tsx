"use client";
import { useMutation, useQuery } from "@tanstack/react-query";
import { useRouter } from "next/navigation";
import { useRef, useState } from "react";
import { z } from "zod";
import { ArrowRight, Braces, Check, FileCode2, FileDiff, FlaskConical, FolderUp, GitBranch, Github, Info, LoaderCircle, ShieldCheck, Upload, X } from "lucide-react";
import { api, createReview } from "@/lib/api";
import type { CreateReview, Providers, SourceKind, UploadedFile } from "@/lib/types";
import { ErrorState, PageHeading } from "./ui";
import { usePreferences } from "@/lib/preferences";

const modes = [{ id: "files", name: "Files", icon: FolderUp }, { id: "github", name: "Repository", icon: Github },
  { id: "pr", name: "Pull request", icon: GitBranch }, { id: "diff", name: "Paste diff", icon: FileDiff },
  { id: "code", name: "Paste code", icon: Braces }, { id: "demo", name: "Demo", icon: FlaskConical }] as const;
const sourceSchema = z.object({ path: z.string().min(1).max(240).regex(/\.(py|js|jsx|mjs|cjs|ts|tsx)$/i, "Use a supported source extension"), content: z.string().min(1, "Paste the source code") });

export function NewReview({ initialMode = "files" }: { initialMode?: SourceKind }) {
  const router = useRouter();
  const [mode, setMode] = useState<SourceKind>(initialMode);
  const [title, setTitle] = useState(initialMode === "demo" ? "Sample project" : "");
  const [files, setFiles] = useState<UploadedFile[]>([]);
  const [filename, setFilename] = useState("src/main.py");
  const [code, setCode] = useState("");
  const [diff, setDiff] = useState("");
  const [url, setUrl] = useState("");
  const [ref, setRef] = useState("");
  const [prNumber, setPrNumber] = useState("");
  const [preferences] = usePreferences();
  const [aiOverride, setUseAI] = useState<boolean | null>(null);
  const useAI = aiOverride ?? preferences.includeAI;
  const [error, setError] = useState<Error | null>(null);
  const [reading, setReading] = useState(false);
  const errorRef = useRef<HTMLDivElement>(null);
  const providers = useQuery({ queryKey: ["providers"], queryFn: () => api<Providers>("/config/providers") });
  const demo = useQuery({ queryKey: ["demo"], queryFn: () => api<UploadedFile[]>("/demo"), enabled: mode === "demo" });
  const mutation = useMutation({ mutationFn: createReview, onSuccess: job => router.push(`/app/review/${job.id}`) });

  async function readFiles(selected: FileList | null) {
    if (!selected) return;
    setError(null); setReading(true);
    try {
      const entries = Array.from(selected);
      if (entries.length > (providers.data?.max_files || 100) || entries.reduce((n, f) => n + f.size, 0) > (providers.data?.max_source_bytes || 2_000_000)) throw new Error("Choose at most 100 source files, up to 2 MB combined.");
      if (entries.some(f => f.size > 500_000)) throw new Error("Each source file must be smaller than 500 KB.");
      const uploaded = await Promise.all(entries.map(async f => ({ path: f.webkitRelativePath || f.name, content: new TextDecoder("utf-8", { fatal: true }).decode(await f.arrayBuffer()) })));
      for (const f of uploaded) if (!/\.(py|js|jsx|mjs|cjs|ts|tsx)$/i.test(f.path)) throw new Error(`Unsupported file: ${f.path}. Select Python, JavaScript or TypeScript source.`);
      setFiles(uploaded);
      if (!title) setTitle(entries.length === 1 ? entries[0].name : "Source review");
    } catch (e) { setError(e instanceof Error ? e : new Error("Could not read selected files")); }
    finally { setReading(false); }
  }
  function submit(event: React.FormEvent) {
    event.preventDefault(); setError(null); mutation.reset();
    try {
      const payload: CreateReview = { kind: mode, title: title.trim() || (mode === "demo" ? "Sample project" : "Untitled review"), use_ai: useAI && !!providers.data?.ai_available };
      if (mode === "files") { if (!files.length) throw new Error("Choose at least one source file."); payload.files = files; }
      if (mode === "code" || mode === "diff") {
        const parsed = sourceSchema.safeParse({ path: filename, content: code });
        if (!parsed.success) throw new Error(parsed.error.issues[0].message);
        payload.files = [parsed.data];
      }
      if (mode === "diff") { if (!diff.trim()) throw new Error("Paste a unified diff and its complete post-change source."); payload.diff = diff; }
      if (mode === "github" || mode === "pr") {
        if (!/^https:\/\/github\.com\/[\w.-]+\/[\w.-]+(?:\/pull\/\d+)?\/?$/.test(url)) throw new Error("Enter a GitHub repository or pull request URL, starting with https://github.com/.");
        payload.url = url;
        if (mode === "github" && ref.trim()) payload.ref = ref.trim();
        if (mode === "pr" && prNumber) payload.pr_number = Number(prNumber);
        if (!title.trim()) payload.title = url.replace("https://github.com/", "");
      }
      mutation.mutate(payload);
    } catch (e) { setError(e instanceof Error ? e : new Error("Check your review input")); requestAnimationFrame(() => errorRef.current?.focus()); }
  }
  const busy = mutation.isPending || reading;
  return <><PageHeading eyebrow="NEW REVIEW" title="Bring your code into focus." description="Choose a source. Set the scope. Let the evidence lead." />
    <div className="new-review-grid"><form className="panel review-form" onSubmit={submit}>
      <div className="form-section"><div className="section-number">01</div><div className="section-title"><h2>Choose your source</h2><p>Source is analyzed as data. It is never executed.</p></div></div>
      <div className="source-tabs" role="group" aria-label="Review source">{modes.map(({ id, name, icon: Icon }) => <button type="button" key={id} aria-pressed={mode === id} disabled={busy} className={mode === id ? "selected" : ""} onClick={() => { setMode(id); setError(null); mutation.reset(); }}><Icon size={18} aria-hidden /><span>{name}</span></button>)}</div>
      {(error || mutation.error) && <div ref={errorRef} tabIndex={-1}><ErrorState error={error || mutation.error} /></div>}
      <label className="field">Review name <input value={title} onChange={e => setTitle(e.target.value)} maxLength={120} placeholder={mode === "demo" ? "Sample project" : "e.g. Authentication service"} /></label>
      {mode === "files" && <><label className={`upload-zone ${reading ? "reading" : ""}`}><input type="file" multiple accept=".py,.js,.jsx,.mjs,.cjs,.ts,.tsx" onChange={e => readFiles(e.target.files)} disabled={busy} aria-label="Choose source files" /><Upload size={27} aria-hidden /><strong>{reading ? "Reading selected files…" : "Choose source files"}</strong><span>Python, JavaScript and TypeScript · Up to 2 MB combined</span><span className="button secondary small">Browse files</span></label>
        {files.length > 0 && <div className="selected-files">{files.map(f => <div key={f.path}><FileCode2 size={15} aria-hidden /><span>{f.path}</span><button type="button" className="icon-button" aria-label={`Remove ${f.path}`} onClick={() => setFiles(files.filter(x => x.path !== f.path))}><X size={14} aria-hidden /></button></div>)}<p>{files.length} files selected</p></div>}
        <p className="field-hint">Only selected file contents are uploaded. The browser does not grant access to the rest of your computer.</p></>}
      {(mode === "github" || mode === "pr") && <><label className="field">{mode === "pr" ? "Pull request or repository URL" : "Repository URL"}<input type="url" placeholder={mode === "pr" ? "https://github.com/owner/repo/pull/42" : "https://github.com/owner/repo"} value={url} onChange={e => setUrl(e.target.value)} /></label>
        {mode === "github" ? <label className="field">Branch or commit <span className="optional">optional</span><input value={ref} onChange={e => setRef(e.target.value)} placeholder="Default branch" /></label> : <label className="field">PR number <span className="optional">if using a repository URL</span><input type="number" min={1} value={prNumber} onChange={e => setPrNumber(e.target.value)} placeholder="42" /></label>}
        <div className="notice"><Info size={17} aria-hidden /><p>Read-only GitHub import. Public repositories work without a token, within GitHub rate limits. Private access uses credentials configured on the server.</p></div></>}
      {(mode === "code" || mode === "diff") && <><label className="field">File path<input value={filename} onChange={e => setFilename(e.target.value)} placeholder="src/main.py" /></label>
        {mode === "diff" && <label className="field">Unified diff<textarea className="code-input" rows={7} value={diff} onChange={e => setDiff(e.target.value)} spellCheck={false} placeholder={'--- a/src/main.py\n+++ b/src/main.py\n@@ -1 +1 @@\n-value = 1\n+value = eval(source)'} /></label>}
        <label className="field">{mode === "diff" ? "Complete post-change source" : "Source code"}<textarea className="code-input" rows={12} value={code} onChange={e => setCode(e.target.value)} spellCheck={false} placeholder={mode === "diff" ? "Paste the full resulting file so line numbers and AST evidence can be verified." : "Paste the code you want to review…"} /></label>
        {mode === "diff" && <p className="field-hint">This mode reviews one file. Complete post-change source is required; the engine will not invent context from an incomplete patch.</p>}</>}
      {mode === "demo" && <div className="demo-preview"><div className="demo-title"><FlaskConical size={20} aria-hidden /><strong>A small project. Real analysis.</strong><span className="micro">EXPLICIT DEMO</span></div><p>Intentionally unsafe source lets you explore findings, evidence and a suggested patch. The same engine analyzes your own code.</p>
        {demo.isPending ? <p role="status">Loading sample source…</p> : demo.error ? <ErrorState error={demo.error} retry={() => demo.refetch()} /> : demo.data?.map(f => <div className="demo-file" key={f.path}><FileCode2 size={16} aria-hidden /><span>{f.path}</span><span>{f.content.split("\n").length} lines</span></div>)}</div>}
      <div className="form-divider" /><div className="form-section"><div className="section-number">02</div><div className="section-title"><h2>Review mode</h2><p>Deterministic checks are always included.</p></div></div>
      <label className="check-field"><input type="checkbox" checked={useAI} onChange={e => setUseAI(e.target.checked)} disabled={!providers.data?.ai_available || busy} /><span><strong>Include AI specialists</strong><small>{providers.data?.ai_available ? `Use ${providers.data.model} for additional reasoning.` : "Optional. Configure a model in server settings to enable."}</small></span></label>
      <div className="form-footer"><span><ShieldCheck size={15} aria-hidden /> No automatic source changes</span><button className="button" disabled={busy || (mode === "demo" && !demo.data)} type="submit">{mutation.isPending ? <><LoaderCircle size={16} className="spin" aria-hidden /> Starting…</> : <>Start review <ArrowRight size={17} aria-hidden /></>}</button></div></form>
      <aside className="review-guide"><p className="eyebrow">FROM SOURCE TO SIGNAL</p><h2>A review you can follow.</h2><ol><li><span>1</span><div><strong>Understand the structure</strong><p>Parse source and identify functions, symbols and changed lines.</p></div></li><li><span>2</span><div><strong>Surface potential issues</strong><p>Run security, logic and maintainability rules. Add AI specialists if configured.</p></div></li><li><span>3</span><div><strong>Ground the findings</strong><p>Check locations and evidence. Keep unverifiable claims separate.</p></div></li><li><span>4</span><div><strong>Make your decision</strong><p>Inspect the score, navigate source and review suggested patches.</p></div></li></ol><div className="guide-note"><Check size={17} aria-hidden /><p>No paid API is required.<br />Deterministic analysis runs instantly.</p></div></aside></div></>;
}
