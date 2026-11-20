"use client";
import Link from "next/link";
import { useQuery } from "@tanstack/react-query";
import { ArrowUpRight, FolderGit2, Plus } from "lucide-react";
import { api } from "@/lib/api";
import type { Repository } from "@/lib/types";
import { date, label } from "@/lib/format";
import { Badge, EmptyState, ErrorState, Loading, PageHeading } from "@/components/ui";
export default function RepositoriesPage() {
  const query = useQuery({ queryKey: ["repositories"], queryFn: () => api<Repository[]>("/repositories") });
  return <><PageHeading eyebrow="REVIEWED SOURCES" title="Your repositories and snapshots." description="Sources from your review history, with their latest recorded state."><Link className="button" href="/app/new"><Plus size={16} aria-hidden /> Review a source</Link></PageHeading>
    <div className="notice"><FolderGit2 size={18} aria-hidden /><p>Sources are imported per review. They are not continuously synced or connected through a GitHub App.</p></div>
    {query.isPending ? <Loading /> : query.error ? <ErrorState error={query.error} retry={() => query.refetch()} /> : query.data.length ? <div className="repository-grid">{query.data.map(repo => <Link className="panel repository-card" key={repo.latest_review_id} href={`/app/review/${repo.latest_review_id}`}><div className="repository-icon"><FolderGit2 size={24} aria-hidden /><ArrowUpRight size={17} aria-hidden /></div><h2>{repo.name}</h2><p>{repo.source_url || "Local source snapshot"}</p><div className="repository-stats"><span>{label(repo.kind)} · {repo.review_count} reviews</span><strong>{repo.score ?? "—"}<small>/100</small></strong></div><div className="repository-bottom"><Badge value={repo.status} /><span>{date(repo.updated_at)}</span></div></Link>)}</div> : <EmptyState title="No sources reviewed yet" body="Upload source or import a GitHub repository to start building your review history." />}</>;
}
