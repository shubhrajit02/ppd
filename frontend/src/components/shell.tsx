"use client";
import Link from "next/link";
import { usePathname } from "next/navigation";
import { useQuery } from "@tanstack/react-query";
import { ArrowUpRight, FolderGit2, History, LayoutDashboard, Plus, Settings2 } from "lucide-react";
import { api } from "@/lib/api";
import { Brand } from "./ui";
import { CommandPalette } from "./command-palette";
import { motion } from "motion/react";
import { API_URL } from "@/lib/api";

const links = [
  { href: "/app", label: "Overview", icon: LayoutDashboard },
  { href: "/app/new", label: "New review", icon: Plus },
  { href: "/app/repositories", label: "Repositories", icon: FolderGit2 },
  { href: "/app/history", label: "History", icon: History },
  { href: "/app/settings", label: "Settings", icon: Settings2 },
];
export function Shell({ children }: { children: React.ReactNode }) {
  const path = usePathname();
  const health = useQuery({ queryKey: ["health"], queryFn: () => api<{ status: string }>("/health"), refetchInterval: 15000 });
  const title = links.find(link => link.href === path)?.label || "Review workspace";
  return <div className="app-shell"><a className="skip-link" href="#main">Skip to content</a>
    <aside className="sidebar"><Brand /><div className="workspace-label"><span className="workspace-initial">W</span><span>Workspace<small>Active environment</small></span></div>
      <p className="nav-caption">WORKSPACE</p><nav aria-label="Main navigation">{links.map(({ href, label, icon: Icon }) =>
        <Link key={href} href={href} aria-label={label} className={`nav-link ${path === href ? "active" : ""}`} aria-current={path === href ? "page" : undefined}>
          {path === href && <motion.span className="nav-indicator" layoutId="sidebar-selection" />}<Icon size={18} aria-hidden /><span>{label}</span>{href === "/app/new" && <kbd>+</kbd>}</Link>)}</nav>
      <div className="sidebar-bottom"><div className="engine-status"><span className={`status-led ${health.data ? "online" : ""}`} />
        <span>{health.isPending ? "Connecting to engine" : health.data ? "Engine online" : "Engine unavailable"}</span></div>
        <p>One engine. Every interface.</p><a href={`${API_URL.replace(/\/api$/, "")}/docs`} target="_blank" rel="noreferrer">API reference <ArrowUpRight size={13} aria-hidden /></a></div>
    </aside><div className="app-main"><header className="topbar"><div><span className="muted">Workspace</span><span className="slash">/</span><span>{title}</span></div>
      <div className="topbar-actions"><CommandPalette /></div></header>
      <main id="main" className={path.startsWith("/app/review/") ? "workspace-main" : "page-content"}>{children}</main>
    </div></div>;
}
