import { describe, it, expect, vi } from "vitest";
import { render, screen, fireEvent } from "@testing-library/react";
import { EmptyState, ErrorState, Loading } from "@/components/ui";
import { Pipeline } from "@/components/pipeline";
import { SourceViewer } from "@/components/source-viewer";
import type { PipelineEvent } from "@/lib/types";

describe("honest application states", () => {
  it("announces loading and offers a working retry", () => {
    const retry = vi.fn(); render(<><Loading text="Fetching source" /><ErrorState error={new Error("Engine offline")} retry={retry} /></>);
    expect(screen.getByRole("status")).toHaveTextContent("Fetching source");
    expect(screen.getByRole("alert")).toHaveTextContent("Engine offline"); fireEvent.click(screen.getByText("Try again")); expect(retry).toHaveBeenCalledOnce();
  });
  it("empty state starts a real review", () => { render(<EmptyState title="No reviews yet" body="Review your source" />); expect(screen.getByRole("link")).toHaveAttribute("href", "/app/new"); });
  it("does not animate disabled specialists as completed", () => {
    const event = { sequence: 1, created_at: "2026-01-01T00:00:00Z", stage: "AI_ANALYSIS", label: "Local AI disabled", state: "SKIPPED", completed: 0, total: 0, findings: 0, duration_seconds: 0, agent: null } satisfies PipelineEvent;
    render(<Pipeline events={[event]} status="COMPLETED" />); expect(screen.getAllByText("disabled")).toHaveLength(4); expect(screen.getByText("Disabled")).toBeInTheDocument(); expect(screen.queryByText("Running")).not.toBeInTheDocument();
  });
  it("shows actual source and diff, rendering injected markup as text", () => {
    Element.prototype.scrollIntoView = vi.fn();
    render(<SourceViewer file={{ path: "sample.ts", content: 'const x = "<script>alert(1)</script>";', language: "typescript", patch: "+debugger;", before: "", changed_lines: [{ start: 1, end: 1 }] }} selectedLine={1} findings={[]} />);
    expect(screen.getByTestId("source-line-1")).toHaveAttribute("data-selected", "true"); expect(document.querySelector("script")).toBeNull(); fireEvent.click(screen.getByRole("button", { name: "Diff" })); expect(screen.getByLabelText("Unified source diff")).toHaveTextContent("+debugger;");
  });
  it("shows error and correction inline on the affected code lines", () => {
    Element.prototype.scrollIntoView = vi.fn();
    const finding = {
      id: "f-123",
      rule_id: "syntax-error",
      category: "BUG",
      severity: "HIGH" as const,
      confidence: 0.95,
      title: "Source contains a syntax error",
      description: "The parser could not parse this region.",
      file: "src/main.py",
      lines: { start: 1, end: 1 },
      symbol: null,
      code_snippet: "int a,b;",
      evidence: ["src/main.py:1-1", "int a,b;"],
      recommendation: "Correct the syntax and run the language compiler or interpreter.",
      suggested_fix: {
        lines: { start: 1, end: 1 },
        original: "int a,b;\n",
        replacement: "# In Python, variables are created on assignment\n",
        explanation: "Remove C-style type declaration.",
        unified_diff: null,
      },
      source: "static" as const,
      analyzer: "builtin-ast",
      validation: "VERIFIED",
      validation_notes: [],
    };
    render(
      <SourceViewer
        file={{
          path: "src/main.py",
          content: "int a,b;\na=4;\n",
          language: "python",
          patch: null,
          before: null,
          changed_lines: null,
        }}
        selectedLine={1}
        findings={[finding]}
      />
    );
    // Line 1 is marked as has-finding
    expect(screen.getByTestId("source-line-1")).toHaveClass("has-finding");
    // Inline finding card is rendered
    expect(screen.getByTestId("inline-finding-f-123")).toBeInTheDocument();
    // Error is shown in lines
    expect(screen.getByText("Source contains a syntax error")).toBeInTheDocument();
    expect(screen.getByText("The parser could not parse this region.")).toBeInTheDocument();
    // Correction is shown in lines
    expect(screen.getByText("Correction & Suggested Fix")).toBeInTheDocument();
    expect(screen.getByText("Remove C-style type declaration.")).toBeInTheDocument();
    expect(screen.getByText("# In Python, variables are created on assignment")).toBeInTheDocument();
  });
});
