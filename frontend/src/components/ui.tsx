import Link from "next/link";
import { AlertCircle, ArrowUpRight, FileCode2, LoaderCircle, ScanLine } from "lucide-react";
import { date, duration, label } from "@/lib/format";
import type { ReviewItem } from "@/lib/types";

export function Brand({ compact = false }: { compact?: boolean }) {
  return <Link href="/" className="brand" aria-label="AICR home"><span className="brand-mark"><ScanLine size={23} aria-hidden /></span>
    {!compact && <span>AICR<span className="brand-sub">CODE INTELLIGENCE</span></span>}</Link>;
}
export function Badge({ value, children }: { value: string; children?: React.ReactNode }) {
  return <span className={`badge badge-${value.toLowerCase()}`}><span className="badge-dot" />{children || label(value)}</span>;
}
export function Loading({ text = "Loading your workspace…" }: { text?: string }) {
  return <div className="state-box" role="status"><LoaderCircle className="spin" size={24} aria-hidden /><p>{text}</p></div>;
}
export function ErrorState({ error, retry }: { error: unknown; retry?: () => void }) {
  return <div className="error-state" role="alert"><AlertCircle size={21} aria-hidden /><div><strong>Something needs attention</strong>
    <p>{error instanceof Error ? error.message : "The request could not be completed."}</p>
    {retry && <button className="button secondary small" onClick={retry}>Try again</button>}</div></div>;
}
export function EmptyState({ title, body, action = true }: { title: string; body: string; action?: boolean }) {
  return <div className="empty-state"><span className="empty-icon"><FileCode2 size={27} aria-hidden /></span>
    <h3>{title}</h3><p>{body}</p>{action && <Link className="button" href="/app/new">Start a review <ArrowUpRight size={16} aria-hidden /></Link>}</div>;
}
export function PageHeading({ eyebrow, title, description, children }: { eyebrow?: string; title: string; description: string; children?: React.ReactNode }) {
  return <div className="page-heading"><div>{eyebrow && <p className="eyebrow">{eyebrow}</p>}<h1>{title}</h1><p>{description}</p></div>{children}</div>;
}
export function ReviewList({ reviews }: { reviews: ReviewItem[] }) {
  return <div className="review-list">{reviews.map(review => <Link className="review-row" key={review.id} href={`/app/review/${review.id}`}>
    <span className="file-symbol"><FileCode2 size={20} aria-hidden /></span><div className="review-name"><strong>{review.title}</strong>
      <span>{label(review.kind)} <span className="dot-separator">·</span> {date(review.created_at)}</span></div>
    <Badge value={review.status} /><span className="row-duration">{duration(review.summary?.duration_seconds)}</span>
    <span className="row-score">{review.score ?? "—"}<small>/100</small></span><ArrowUpRight className="row-arrow" size={16} aria-hidden />
  </Link>)}</div>;
}
