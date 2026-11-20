"use client";
import * as Dialog from "@radix-ui/react-dialog";
import { useEffect, useRef, useState } from "react";
import { usePathname, useRouter } from "next/navigation";
import { Command, Search, X } from "lucide-react";
import { AnimatePresence, motion } from "motion/react";
import { enter } from "@/lib/motion";

export function CommandPalette() {
  const [open, setOpen] = useState(false);
  const [search, setSearch] = useState("");
  const router = useRouter();
  const path = usePathname();
  const list = useRef<HTMLDivElement>(null);
  useEffect(() => {
    const key = (e: KeyboardEvent) => { if ((e.metaKey || e.ctrlKey) && e.key.toLowerCase() === "k") { e.preventDefault(); setOpen(value => !value); } };
    window.addEventListener("keydown", key); return () => window.removeEventListener("keydown", key);
  }, []);
  const commands = [
    { name: "New review", route: "/app/new" }, { name: "Open repositories", route: "/app/repositories" },
    { name: "Open history", route: "/app/history" }, { name: "Settings", route: "/app/settings" }, { name: "Overview", route: "/app" },
    ...(path.startsWith("/app/review/") ? [{ name: "Go to next finding", action: "next" }, { name: "Filter Critical", action: "critical" }, { name: "Filter Security", action: "security" }, { name: "Reset filters", action: "reset" }, { name: "Toggle file panel", action: "files" }, { name: "Toggle findings panel", action: "findings" }] : []),
  ].filter(c => c.name.toLowerCase().includes(search.toLowerCase()));
  function run(c: typeof commands[number]) { setOpen(false); setSearch(""); if (c.route) router.push(c.route); else window.dispatchEvent(new CustomEvent("aicr-command", { detail: c.action })); }
  return <Dialog.Root open={open} onOpenChange={value => { setOpen(value); if (!value) setSearch(""); }}><Dialog.Trigger asChild><button className="command-trigger" aria-label="Open command palette"><Command size={14} aria-hidden /><span>Commands</span><kbd>Ctrl K</kbd></button></Dialog.Trigger><AnimatePresence>{open && <Dialog.Portal forceMount><Dialog.Overlay asChild><motion.div className="dialog-overlay" {...enter} /></Dialog.Overlay><Dialog.Content asChild><motion.div className="dialog-content command-dialog" {...enter}><div className="dialog-heading"><Dialog.Title>Command palette</Dialog.Title><Dialog.Close asChild><button className="icon-button" aria-label="Close commands"><X size={18} aria-hidden /></button></Dialog.Close></div><Dialog.Description className="field-hint">Navigate with Tab or arrow keys. Enter runs a command.</Dialog.Description><label className="command-search"><Search size={18} aria-hidden /><span className="sr-only">Search commands</span><input autoComplete="off" value={search} onChange={e => setSearch(e.target.value)} onKeyDown={e => { if (e.key === "ArrowDown") { e.preventDefault(); list.current?.querySelector("button")?.focus(); } if (e.key === "Enter" && commands[0]) run(commands[0]); }} placeholder="What would you like to do?" /></label><div ref={list} className="command-results" onKeyDown={e => { if (!["ArrowDown", "ArrowUp", "Home", "End"].includes(e.key)) return; e.preventDefault(); const buttons = Array.from(list.current?.querySelectorAll("button") || []); const index = buttons.indexOf(document.activeElement as HTMLButtonElement); const next = e.key === "Home" ? 0 : e.key === "End" ? buttons.length - 1 : (index + (e.key === "ArrowDown" ? 1 : -1) + buttons.length) % buttons.length; buttons[next]?.focus(); }}>{commands.map(c => <button key={c.name} onClick={() => run(c)}>{c.name}<span aria-hidden>↵</span></button>)}{!commands.length && <p className="empty-command">No matching commands.</p>}</div></motion.div></Dialog.Content></Dialog.Portal>}</AnimatePresence></Dialog.Root>;
}
