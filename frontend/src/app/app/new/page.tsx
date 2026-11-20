import { NewReview } from "@/components/new-review";
import type { SourceKind } from "@/lib/types";
export default async function NewPage({ searchParams }: { searchParams: Promise<{ mode?: string }> }) {
  const { mode } = await searchParams;
  const allowed = ["files", "code", "diff", "github", "pr", "demo"];
  return <NewReview initialMode={allowed.includes(mode || "") ? mode as SourceKind : "files"} />;
}
