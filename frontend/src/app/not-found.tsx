import Link from "next/link";
export default function NotFound() { return <main className="empty-state"><p className="eyebrow">404 / NOT FOUND</p><h1>This page isn’t here.</h1><Link className="button" href="/app">Return to workspace</Link></main>; }
