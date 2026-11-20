"use client";
import Link from "next/link";
import { useQuery } from "@tanstack/react-query";
import { ArrowRight, ArrowUpRight, Braces, CheckCheck, Files, Plus, ShieldAlert } from "lucide-react";
import { api } from "@/lib/api";
import type { Dashboard } from "@/lib/types";
import { severities } from "@/lib/types";
import { label } from "@/lib/format";
import { EmptyState, ErrorState, Loading, PageHeading, ReviewList } from "@/components/ui";

export default function DashboardPage() {
  const query = useQuery({ queryKey: ["dashboard"], queryFn: () => api<Dashboard>("/dashboard"), refetchInterval: 5000 });
  if (query.isPending) return <Loading />;
  if (query.error) return <ErrorState error={query.error} retry={() => query.refetch()} />;
  const data = query.data;
  const total = Object.values(data.severity_distribution).reduce((a, b) => a + b, 0);
  const categories = Object.entries(data.categories).sort((a, b) => b[1] - a[1]).slice(0, 5);
  const metrics = [{ title: "Total reviews", value: data.review_count, note: `${data.completed_count} completed`, icon: CheckCheck },
    { title: "Average score", value: data.average_score ?? "—", note: "Across completed reviews", icon: Braces },
    { title: "Needs attention", value: data.open_high + data.open_critical, note: "Open high + critical findings", icon: ShieldAlert },
    { title: "Files reviewed", value: data.files_reviewed, note: "Across your review history", icon: Files }];
  return <><PageHeading eyebrow="WORKSPACE OVERVIEW" title="A clearer view of your code." description="Your reviews, signals, and next decisions in one place."><Link href="/app/new" className="button"><Plus size={17} aria-hidden /> New review</Link></PageHeading>
    <section className="metric-grid" aria-label="Review metrics">{metrics.map(({ title, value, note, icon: Icon }) => <div className="metric" key={title}><div><span>{title}</span><Icon size={17} aria-hidden /></div><strong>{value}{title === "Average score" && <small>/100</small>}</strong><p>{note}</p></div>)}</section>
    {data.review_count === 0 && <div className="welcome-strip"><div><span className="eyebrow">READY WHEN YOU ARE</span><h2>Start with a question. Leave with evidence.</h2><p>Review your own source, or explore the workspace with an explicit sample.</p></div><Link href="/app/new?mode=demo" className="button secondary">Run sample review <ArrowRight size={16} aria-hidden /></Link></div>}
    <div className="dashboard-grid"><section className="panel recent-panel"><div className="panel-heading"><h2>Recent reviews</h2><Link className="text-link" href="/app/history">View all <ArrowUpRight size={14} aria-hidden /></Link></div>
      {data.recent.length ? <ReviewList reviews={data.recent} /> : <EmptyState title="Your review history starts here" body="Completed and in-progress reviews will appear here. There are no generated metrics or seeded results." />}</section>
      <section className="panel"><div className="panel-heading"><h2>Open findings</h2><span className="micro">BY SEVERITY</span></div><div className="severity-summary"><strong>{total}</strong><span>findings to review</span></div><div className="bar-stack" aria-hidden>{severities.map(s => <span key={s} className={`severity-bg-${s.toLowerCase()}`} style={{ flex: data.severity_distribution[s] || 0 }} />)}</div><div className="severity-legend">{severities.map(s => <div key={s}><span><i className={`severity-bg-${s.toLowerCase()}`} />{label(s)}</span><strong>{data.severity_distribution[s]}</strong></div>)}</div></section>
      <section className="panel"><div className="panel-heading"><h2>Repository health</h2><Link className="text-link" href="/app/repositories">All sources <ArrowUpRight size={14} aria-hidden /></Link></div>
        {data.repositories.length ? data.repositories.slice(0, 4).map(repo => <Link className="source-row" href={`/app/review/${repo.latest_review_id}`} key={repo.latest_review_id}><div><strong>{repo.name}</strong><span>{repo.review_count} {repo.review_count === 1 ? "review" : "reviews"} · {label(repo.kind)}</span></div><span className="source-score">{repo.score ?? "—"}<small>/100</small></span></Link>) : <p className="panel-empty">Reviewed sources will appear here with their latest score.</p>}</section>
      <section className="panel"><div className="panel-heading"><h2>Common categories</h2><span className="micro">OPEN FINDINGS</span></div>{categories.length ? <div className="category-bars">{categories.map(([name, count]) => <div key={name}><div><span>{label(name)}</span><span>{count}</span></div><div className="bar-track"><span style={{ width: `${count / categories[0][1] * 100}%` }} /></div></div>)}</div> : <p className="panel-empty">Issue categories will be summarized after your first review.</p>}</section></div>
    <p className="footnote">Scores describe findings in the reviewed scope. They do not certify code as safe.</p></>;
}
