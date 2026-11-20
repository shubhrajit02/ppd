import Link from "next/link";
import { ArrowRight, ArrowUpRight, ShieldCheck, Terminal } from "lucide-react";
import { IntelligenceGraph } from "@/components/intelligence-graph";
import { Brand } from "@/components/ui";

export default function Home() {
  return <main className="landing"><header className="landing-nav"><Brand /><nav aria-label="Product navigation"><a href="#how-it-works">How it works</a><Link href="/app/history">Review history</Link><Link href="/app" className="button secondary small">Open workspace <ArrowUpRight size={15} aria-hidden /></Link></nav></header>
    <section className="hero"><div className="hero-copy"><span className="eyebrow"><span className="status-led online" /> AI CODE INTELLIGENCE</span>
      <h1>Understand the code.<br /><span>Review with evidence.</span></h1><p>AST-grounded reviews for security, bugs, performance and maintainability. One local engine. Evidence you can inspect.</p>
      <div className="hero-actions"><Link className="button" href="/app/new">Review repository <ArrowRight size={18} aria-hidden /></Link><Link href="/app/new?mode=demo" className="text-link">Try a sample review <ArrowUpRight size={16} aria-hidden /></Link></div>
      <div className="hero-command"><span>$</span><code>aicr review .</code><small>FREE · FAST · INSPECTABLE</small></div><div className="hero-notes"><span><ShieldCheck size={16} aria-hidden /> No API key required</span><span><Terminal size={16} aria-hidden /> CLI + web, one engine</span></div></div>
      <IntelligenceGraph /></section>
    <section id="how-it-works" className="landing-features"><div><span className="feature-number">01 / SOURCE</span><h2>Your code. Your scope.</h2><p>Upload files, paste code, or inspect a GitHub repository or pull request. Every review starts with a clear source snapshot.</p></div><div><span className="feature-number">02 / EVIDENCE</span><h2>Reasoning you can inspect.</h2><p>Deterministic checks run locally. Optional local AI adds specialist reasoning, checked against actual source evidence.</p></div><div><span className="feature-number">03 / DECISION</span><h2>You stay in the loop.</h2><p>Navigate findings, inspect suggested patches, and track decisions. No automatic code changes. No opaque AI scores.</p></div></section>
    <footer className="landing-footer"><span>AICR / Built for the review before the merge.</span><Link href="/app/settings">Configuration <ArrowUpRight size={13} aria-hidden /></Link></footer></main>;
}
