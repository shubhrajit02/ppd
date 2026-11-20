import { z } from "zod";

export const severities = ["CRITICAL", "HIGH", "MEDIUM", "LOW", "INFO"] as const;
export const terminal = new Set(["COMPLETED", "FAILED", "CANCELLED"]);
export type Severity = (typeof severities)[number];
export type FindingState = "OPEN" | "RESOLVED" | "IGNORED";
export const lineSchema = z.object({ start: z.number(), end: z.number() });
export const fixSchema = z.object({ lines: lineSchema, original: z.string(), replacement: z.string(),
  explanation: z.string(), unified_diff: z.string().nullable() });
export const findingSchema = z.object({ id: z.string(), rule_id: z.string(),
  category: z.string(), severity: z.enum(severities), confidence: z.number(),
  title: z.string(), description: z.string(), file: z.string(), lines: lineSchema,
  symbol: z.string().nullable(), code_snippet: z.string(), evidence: z.array(z.string()),
  recommendation: z.string(), suggested_fix: fixSchema.nullable(), source: z.enum(["static", "ai"]),
  analyzer: z.string(), validation: z.string(), validation_notes: z.array(z.string()) });
export type Finding = z.infer<typeof findingSchema>;
export type SuggestedFix = z.infer<typeof fixSchema>;
export const summarySchema = z.object({ files_reviewed: z.number(), findings_count: z.number(),
  rejected_count: z.number(), duration_seconds: z.number(), severity_counts: z.record(z.string(), z.number()) });
export const reportSchema = z.object({ schema_version: z.string(), root: z.string(), mode: z.string(),
  findings: z.array(findingSchema), rejected_findings: z.array(findingSchema),
  score: z.object({ value: z.number(), formula: z.string(), penalties: z.array(z.object({
    finding_id: z.string(), points: z.number(), explanation: z.string() })) }),
  summary: summarySchema, warnings: z.array(z.string()), ai_status: z.string() });
export const reviewItemSchema = z.object({ id: z.string(), title: z.string(), kind: z.string(),
  source_url: z.string().nullable(), status: z.string(), created_at: z.string(), updated_at: z.string(),
  error: z.string().nullable(), score: z.number().nullable(), summary: summarySchema.nullable(),
  cancel_requested: z.boolean() });
export const detailSchema = reviewItemSchema.extend({ report: reportSchema.nullable(),
  finding_states: z.record(z.string(), z.enum(["OPEN", "RESOLVED", "IGNORED"])), sources_available: z.boolean() });
export type ReviewItem = z.infer<typeof reviewItemSchema>;
export type ReviewDetail = z.infer<typeof detailSchema>;
export type Report = z.infer<typeof reportSchema>;
export type SourceFile = { path: string; content: string; language: string;
  changed_lines: { start: number; end: number }[] | null; patch: string | null; before: string | null };
export type PipelineEvent = { sequence: number; created_at: string; stage: string;
  label: string; state: string; completed: number; total: number; findings: number;
  duration_seconds: number; agent: string | null };
export type Repository = { name: string; source_url: string | null; kind: string;
  latest_review_id: string; score: number | null; status: string; updated_at: string; review_count: number };
export type Dashboard = { review_count: number; completed_count: number; average_score: number | null;
  files_reviewed: number; open_critical: number; open_high: number;
  severity_distribution: Record<string, number>; categories: Record<string, number>;
  repositories: Repository[]; recent: ReviewItem[] };
export type Providers = { selected: string; model: string; ai_available: boolean; providers: string[];
  github_authenticated: boolean; max_files: number; max_source_bytes: number; source_retention_hours: number };
export type UploadedFile = { path: string; content: string };
export type SourceKind = "files" | "demo" | "code" | "diff" | "github" | "pr";
export type CreateReview = { kind: SourceKind; title: string; files?: UploadedFile[]; diff?: string;
  url?: string; ref?: string; pr_number?: number; use_ai: boolean };
