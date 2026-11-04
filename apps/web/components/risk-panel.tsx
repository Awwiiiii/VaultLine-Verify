"use client";
import { useDateDisplay } from "@/components/preferences";

import { useState } from "react";
import { Button } from "@/components/ui/button";
import { request } from "@/lib/cases";

type Indicator = { id: string; category: string; title: string; explanation: string; source_refs: string[] };
type Source = { id: string; kind: string; payload: Record<string, unknown> };
type Assessment = {
  assessed_at: string; case_id: string; rule_version: string;
  assessment_status: "review_findings_present" | "insufficient_evidence" | "no_recorded_discrepancy";
  human_review_required: true; review_requirement: string; scope: string;
  indicators: Indicator[]; sources: Source[];
  input_snapshot: { freshness: string; verification: { id: string; created_at: string } | null };
};
const labels = {
  review_findings_present: "Findings require human review",
  insufficient_evidence: "Insufficient evidence for complete recorded checks",
  no_recorded_discrepancy: "No discrepancy found in the recorded checks",
};
const categories: Record<string, string> = {
  discrepancy: "Document discrepancy",
  potential_claim_conflict: "Potential claim conflict",
  aggregate_claim_excess: "Recorded aggregate claim excess",
  duplicate_assertions: "Duplicate registry assertions",
  insufficient_evidence: "Insufficient evidence",
  unchecked_comparison: "Comparison not performed",
  no_recorded_claim_conflict: "Recorded dataset limitation",
  unknown_external_financing: "Unknown external financing",
};

export function RiskPanel({ caseId }: { caseId: string }) {
 const date = useDateDisplay();
  const [assessment, setAssessment] = useState<Assessment | null>(null);
  const [pending, setPending] = useState(false);
  const [error, setError] = useState("");
  async function load() {
    setPending(true);
    setError("");
    try {
      setAssessment(await request<Assessment>(`/${caseId}/risk-assessment`));
    } catch (e) {
      setAssessment(null);
      setError(e instanceof Error ? e.message : "Unable to assess recorded evidence.");
    } finally { setPending(false); }
  }
  return <section aria-labelledby="risk-title" className="my-6 space-y-4 rounded-xl border border-slate-200 bg-white p-6">
    <h2 id="risk-title" className="font-semibold">Evidence-based risk assessment</h2>
    <p className="text-sm text-slate-600">Deterministic review indicators, not a credit-risk prediction or default probability. Human review is always required. No loan approval or rejection is made.</p>
    <p className="text-sm text-slate-600">Recorded claims do not prove financing or ownership. Missing evidence does not establish fraud. External financing remains unknown. Refresh after verification, extraction or claim changes; the displayed assessment is a point-in-time view.</p>
    <Button disabled={pending} onClick={load}>{pending ? "Assessing evidence…" : "Assess recorded evidence"}</Button>
    {error && <p role="alert" className="text-red-700">{error}</p>}
    {assessment && <div className="space-y-4">
      <h3 className="font-semibold">{labels[assessment.assessment_status]}</h3>
      <p className="font-medium">{assessment.review_requirement}</p>
      <p className="text-xs text-slate-500">{date(assessment.assessed_at)} · {assessment.rule_version} · Verification coverage: {assessment.input_snapshot.freshness}</p>
      {assessment.input_snapshot.verification && <p className="break-all text-xs">Saved verification {assessment.input_snapshot.verification.id} · {assessment.input_snapshot.verification.created_at}</p>}
      <p className="text-sm">{assessment.scope}</p>
      {assessment.indicators.map(indicator => <article key={indicator.id} className="space-y-2 rounded border border-slate-200 p-4">
        <p className="text-xs font-medium text-slate-500">{categories[indicator.category] ?? indicator.category}</p>
        <h4 className="font-medium">{indicator.title}</h4><p className="text-sm">{indicator.explanation}</p>
        <details><summary className="cursor-pointer text-sm">Supporting deterministic findings and provenance</summary>
          {indicator.source_refs.map(ref => {
            const source = assessment.sources.find(s => s.id === ref);
            return <div key={ref} className="mt-2 border-t pt-2 text-xs"><p className="break-all">{ref} · {source?.kind}</p><pre className="overflow-auto whitespace-pre-wrap">{JSON.stringify(source?.payload, null, 2)}</pre></div>;
          })}
        </details>
      </article>)}
    </div>}
  </section>;
}
