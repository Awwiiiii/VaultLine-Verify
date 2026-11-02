"use client";

import { useEffect, useState } from "react";
import { Button } from "@/components/ui/button";
import { request } from "@/lib/cases";

type Outcome = "passed" | "discrepancy" | "insufficient_evidence" | "not_applicable";
type Source = {
  document_id: string;
  case_id: string;
  field_name: string;
  value: string | null;
  provenance: { original_value: string; source_location: Record<string, string | number>; extraction_method: string; validation_status: string }[];
};
type Finding = {
  rule_id: string;
  outcome: Outcome;
  mandatory: boolean;
  document_ids: string[];
  actual_values: Record<string, string | null>;
  expected_values: Record<string, string | null>;
  source_evidence: Source[];
  explanation: string;
};
type RunSummary = { id: string; case_id: string; rule_set_version: string; outcome: Outcome; created_at: string; tolerances: Record<string, string> };
type Run = RunSummary & { findings: Finding[] };
type History = { items: RunSummary[]; total: number; limit: number; offset: number };
const labels: Record<Outcome, string> = {
  passed: "Passed document checks",
  discrepancy: "Discrepancy — investigate",
  insufficient_evidence: "Insufficient evidence",
  not_applicable: "Not applicable",
};
const colors: Record<Outcome, string> = {
  passed: "bg-emerald-50 text-emerald-800",
  discrepancy: "bg-amber-50 text-amber-900",
  insufficient_evidence: "bg-slate-100 text-slate-700",
  not_applicable: "bg-slate-100 text-slate-600",
};

export function VerificationPanel({ caseId }: { caseId: string }) {
  const [history, setHistory] = useState<History | null>(null);
  const [offset, setOffset] = useState(0);
  const [run, setRun] = useState<Run | null>(null);
  const [pending, setPending] = useState(false);
  const [error, setError] = useState("");
  const [revision, setRevision] = useState(0);

  useEffect(() => {
    let active = true;
    request<History>(`/${caseId}/verifications?limit=20&offset=${offset}`)
      .then(data => { if (active) setHistory(data); })
      .catch(() => { if (active) setError("Unable to load verification history. Check the API connection."); });
    return () => { active = false; };
  }, [caseId, offset, revision]);

  async function execute(runId?: string) {
    setPending(true);
    setError("");
    try {
      const result = await request<Run>(runId ? `/${caseId}/verifications/${runId}` : `/${caseId}/verify`, { method: runId ? "GET" : "POST" });
      setRun(result);
      if (!runId) { setOffset(0); setRevision(value => value + 1); }
    } catch (error) {
      setError(error instanceof Error ? error.message : "Verification request failed");
    } finally {
      setPending(false);
    }
  }

  return <section aria-labelledby="verification-title" className="my-6 space-y-5 rounded-xl border border-slate-200 bg-white p-6">
    <div className="flex flex-wrap items-center justify-between gap-4">
      <div><h2 id="verification-title" className="font-semibold">Cross-document verification</h2><p className="mt-1 text-sm text-slate-500">Deterministic checks against extracted supporting evidence.</p></div>
      <Button disabled={pending} onClick={() => execute()}>{pending ? "Loading verification…" : "Run verification"}</Button>
    </div>
    <p className="text-sm text-slate-600">Inspect every finding, including conditional checks with insufficient evidence. Results do not establish ownership, enforceability, delivery, acceptance, or absence of fraud. No lending decision is made.</p>
    {pending && <p role="status" className="text-sm">Comparing evidence or retrieving a saved run…</p>}
    {error && <p role="alert" className="text-sm text-red-700">{error}</p>}
    {!history && !error && <p role="status" className="text-sm">Loading history…</p>}
    {history?.total === 0 && <p className="text-sm text-slate-500">No verification runs yet. Extract invoices and supporting purchase orders, then run checks.</p>}
    {history && history.total > 0 && <div className="flex flex-wrap items-center gap-3">
      <label className="text-sm">Historical run<select aria-label="Select a historical verification run" className="ml-2 max-w-full rounded border border-slate-300 p-2" disabled={pending} value={history.items.some(item => item.id === run?.id) ? run?.id : ""} onChange={event => { if (event.target.value) execute(event.target.value); }}>
        <option value="">Select a saved run</option>{history.items.map(item => <option key={item.id} value={item.id}>{new Date(item.created_at).toLocaleString()} — {labels[item.outcome]} — {item.id.slice(0,8)}</option>)}
      </select></label>
      <Button variant="outline" disabled={pending || offset === 0} onClick={() => setOffset(Math.max(0, offset - 20))}>Newer</Button>
      <Button variant="outline" disabled={pending || offset + 20 >= history.total} onClick={() => setOffset(offset + 20)}>Older</Button>
      <span className="text-xs text-slate-500">{history.total} saved runs</span>
    </div>}
    {run && <div className="space-y-4">
      <div className="space-y-2 border-t border-slate-100 pt-5"><span className={`inline-block rounded px-3 py-1 text-sm font-medium ${colors[run.outcome]}`}>{labels[run.outcome]}</span><p className="text-xs text-slate-500">{new Date(run.created_at).toLocaleString()} · {run.rule_set_version} · Run {run.id}</p><p className="text-xs text-slate-500">Absolute tolerances: {Object.entries(run.tolerances).map(([key,value]) => `${key.replaceAll("_", " ")}: ${value}`).join(" · ")}</p></div>
      {run.findings.map((finding, index) => <article key={index} className="rounded-lg border border-slate-200 p-4">
        <div className="flex flex-wrap items-center justify-between gap-2"><h3 className="text-sm font-semibold">{finding.rule_id.replaceAll("_", " ")}</h3><span className={`rounded px-2 py-1 text-xs ${colors[finding.outcome]}`}>{labels[finding.outcome]}</span></div>
        <p className="mt-2 text-sm text-slate-600">{finding.explanation}</p><p className="mt-1 text-xs text-slate-500">{finding.mandatory ? "Mandatory check" : "Conditional check"}</p>
        <div className="mt-4 grid gap-4 text-xs sm:grid-cols-2">{[["Actual values", finding.actual_values], ["Expected / supporting values", finding.expected_values]].map(([title, values]) => <div key={String(title)}><h4 className="font-medium">{String(title)}</h4><dl className="mt-1 space-y-2">{Object.entries(values).map(([key,value]) => <div key={key}><dt className="break-all text-slate-500">{key}</dt><dd className="font-medium">{value ?? "Missing / unresolved"}</dd></div>)}</dl>{Object.keys(values).length === 0 && <p className="text-slate-500">No supporting value available.</p>}</div>)}</div>
        <details className="mt-4 text-xs"><summary className="cursor-pointer font-medium">Source documents and field provenance</summary>
          <p className="mt-2 break-all text-slate-500">Documents: {finding.document_ids.join(", ") || "No document available"}</p>
          {finding.source_evidence.map((source, sourceIndex) => <div key={sourceIndex} className="mt-3 border-t border-slate-100 pt-2"><p className="break-all">Case {source.case_id} · Document {source.document_id}</p><p className="font-medium">{source.field_name}: {source.value ?? "Missing / unresolved"}</p>{source.provenance.length === 0 ? <p className="text-slate-500">No source field provenance available.</p> : source.provenance.map((item, i) => <p key={i} className="whitespace-pre-wrap text-slate-500">Original: {item.original_value} · {Object.entries(item.source_location).map(([key,value]) => `${key}: ${value}`).join(", ") || "Location unavailable"} · {item.extraction_method} · {item.validation_status}</p>)}</div>)}
        </details>
      </article>)}
    </div>}
  </section>;
}
