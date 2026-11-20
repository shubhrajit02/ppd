"use client";
import { useState } from "react";
import { useMutation, useQuery, useQueryClient } from "@tanstack/react-query";
import * as Dialog from "@radix-ui/react-dialog";
import { ChevronLeft, ChevronRight, Search, Trash2, X } from "lucide-react";
import { api, getReviews } from "@/lib/api";
import { terminal } from "@/lib/types";
import { EmptyState, ErrorState, Loading, PageHeading, ReviewList } from "@/components/ui";

export default function HistoryPage() {
  const [offset, setOffset] = useState(0);
  const [search, setSearch] = useState("");
  const [deleting, setDeleting] = useState<string | null>(null);
  const client = useQueryClient();
  const query = useQuery({ queryKey: ["history", offset], queryFn: ({ signal }) => getReviews(offset, signal), refetchInterval: 5000 });
  const remove = useMutation({ mutationFn: (id: string) => api(`/reviews/${id}`, { method: "DELETE" }), onSuccess: () => { client.invalidateQueries(); setDeleting(null); } });
  return <><PageHeading eyebrow="REVIEW HISTORY" title="Every review, in context." description="Revisit results, track decisions, and pick up where you left off." />
    <div className="history-tools"><label className="search-field"><Search size={17} aria-hidden /><input aria-label="Search reviews on this page" value={search} onChange={e => setSearch(e.target.value)} placeholder="Search this page…" /></label><span className="micro">SAVED LOCALLY · SQLITE</span></div>
    {query.isPending ? <Loading /> : query.error ? <ErrorState error={query.error} retry={() => query.refetch()} /> : <section className="panel"><div className="panel-heading"><h2>Reviews</h2><span className="muted">{query.data.length} on this page</span></div>{query.data.length ? query.data.filter(r => r.title.toLowerCase().includes(search.toLowerCase())).map(review => <div className="history-row" key={review.id}><ReviewList reviews={[review]} /><button className="icon-button" title="Delete review" aria-label={`Delete ${review.title}`} disabled={!terminal.has(review.status)} onClick={() => { remove.reset(); setDeleting(review.id); }}><Trash2 size={16} aria-hidden /></button></div>) : <EmptyState title="No reviews yet" body="Your completed and in-progress reviews will be saved here automatically." />}
      {query.data.length > 0 && !query.data.some(r => r.title.toLowerCase().includes(search.toLowerCase())) && <EmptyState title="No matching reviews on this page" body="Try another search or browse a different page." action={false} />}</section>}
    <div className="pagination"><button className="button secondary small" disabled={offset === 0} onClick={() => setOffset(Math.max(0, offset - 50))}><ChevronLeft size={16} aria-hidden /> Previous</button><span>Page {offset / 50 + 1}</span><button className="button secondary small" disabled={!query.data || query.data.length < 50} onClick={() => setOffset(offset + 50)}>Next <ChevronRight size={16} aria-hidden /></button></div>
    <Dialog.Root open={!!deleting} onOpenChange={open => { if (!open) setDeleting(null); }}><Dialog.Portal><Dialog.Overlay className="dialog-overlay" /><Dialog.Content className="dialog-content compact-dialog"><div className="dialog-heading"><Dialog.Title>Delete this review?</Dialog.Title><Dialog.Close asChild><button className="icon-button" aria-label="Close delete dialog"><X size={19} aria-hidden /></button></Dialog.Close></div><Dialog.Description>This removes the stored report, decisions, source snapshot and event history. Your original source files are not affected.</Dialog.Description>{remove.error && <ErrorState error={remove.error} />}<div className="dialog-actions"><Dialog.Close asChild><button className="button secondary">Keep review</button></Dialog.Close><button className="button danger" disabled={remove.isPending} onClick={() => deleting && remove.mutate(deleting)}>{remove.isPending ? "Deleting…" : "Delete review"}</button></div></Dialog.Content></Dialog.Portal></Dialog.Root></>;
}
