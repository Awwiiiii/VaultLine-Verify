"use client";
import { useDateDisplay } from "@/components/preferences";

import { useState } from "react";
import { Button } from "@/components/ui/button";
import { request } from "@/lib/cases";

type Statement = { kind: string; text: string; evidence_refs: string[] };
type Summary = { id: string; provider: string; model: string; status: string; created_at: string; error: string | null };
type Entry = { id: string; kind: string; text: string; document_ids: string[]; claim_ids: string[]; case_ids: string[]; provenance: unknown[] };
type Report = Summary & { output: { executive_summary: Statement[]; key_findings: Statement[]; supporting_evidence_references: string[]; unresolved_questions: Statement[]; recommended_next_verification_steps: Statement[]; limitations: Statement[] } | null; evidence_snapshot: { entries?: Entry[]; verification_run_id?: string | null; verification_created_at?: string | null; captured_at?: string } };
type History = { items: Summary[]; total: number };

export function InvestigationPanel({ caseId }: { caseId: string }) {
 const date = useDateDisplay();
  const [history, setHistory] = useState<History | null>(null);
  const [report, setReport] = useState<Report | null>(null);
  const [pending, setPending] = useState(false);
  const [error, setError] = useState("");
  const [offset, setOffset] = useState(0);

  async function execute(action: "start" | "history" | "get", id?: string, page = offset) {
    setPending(true);
    setError("");
    try {
      if (action !== "history") {
        const result = await request<Report>(`/${caseId}/investigations${action === "get" ? `/${id}` : ""}`, { method: action === "start" ? "POST" : "GET" });
        setReport(result);
        if (action === "start") page = 0;
      }
      setHistory(await request<History>(`/${caseId}/investigations?limit=20&offset=${page}`));
      setOffset(page);
    } catch (e) {
      setError(e instanceof Error ? e.message : "Investigation unavailable. Review deterministic findings.");
    } finally {
      setPending(false);
    }
  }
  const sections: [string, Statement[]][] = report?.output ? [
    ["Executive summary", report.output.executive_summary],
    ["Key findings", report.output.key_findings],
    ["Unresolved questions", report.output.unresolved_questions],
    ["Recommended next verification steps", report.output.recommended_next_verification_steps],
    ["Limitations", report.output.limitations],
  ] : [];

  return <section aria-labelledby="investigation-title" className="my-6 space-y-4 rounded-xl border border-slate-200 bg-white p-6">
    <h2 id="investigation-title" className="font-semibold">AI Investigation</h2>
    <p className="text-sm text-slate-600">AI-generated interpretations of saved findings. No loan decision, fraud determination, or verification of legal rights. External financing is unverified. Start only when this evidence is approved for sharing with the configured provider.</p>
    <p className="text-sm text-slate-600">Run deterministic verification first. Each investigation preserves its evidence snapshot; later changes require a new investigation.</p>
    <div className="flex flex-wrap gap-3">
      <Button disabled={pending} onClick={() => execute("start")}>Start investigation</Button>
      <Button variant="outline" disabled={pending} onClick={() => execute("history")}>Load history</Button>
    </div>
    {pending && <p role="status">Loading investigation…</p>}
    {error && <p role="alert" className="text-red-700">{error}</p>}
    {history && <div className="space-y-3">
      <label>Saved investigation<select className="ml-2 max-w-full rounded border p-2" value={history.items.some(r => r.id === report?.id) ? report?.id : ""} disabled={pending} onChange={e => { if (e.target.value) execute("get", e.target.value); }}>
        <option value="">Select a saved report</option>{history.items.map(r => <option key={r.id} value={r.id}>{date(r.created_at)} · {r.status} · {r.id.slice(0, 8)}</option>)}
      </select></label>
      <div className="flex gap-3"><Button variant="outline" disabled={pending || offset === 0} onClick={() => execute("history", undefined, Math.max(0, offset - 20))}>Newer</Button><Button variant="outline" disabled={pending || offset + 20 >= history.total} onClick={() => execute("history", undefined, offset + 20)}>Older</Button><span>{history.total} saved investigations</span></div>
    </div>}
    {report && <article className="space-y-4 border-t pt-4">
      <p className="text-sm">{report.provider} · {report.model} · {report.status} · {date(report.created_at)}</p>
      {report.provider === "mock" && <p className="font-semibold text-amber-800">TEST ONLY — deterministic mock investigation; no Meta response.</p>}
      {report.error && <p role="alert" className="text-red-700">{report.error}</p>}
      {report.status === "pending" && <p>This request may still be running or may have been interrupted. Reload history before starting another investigation.</p>}
      {report.evidence_snapshot.verification_run_id && <p className="text-xs">Saved verification: {report.evidence_snapshot.verification_run_id} · {report.evidence_snapshot.verification_created_at}</p>}
      {sections.map(([title, statements]) => <div key={title}><h3 className="font-medium">{title}</h3><ul className="space-y-2">{statements.map((s, i) => <li key={i} className="text-sm"><span className="font-medium">{s.kind === "ai_interpretation" ? "AI-generated interpretation" : s.kind === "observed_fact" ? "Source observation — unverified" : s.kind.replaceAll("_", " ")}:</span> {s.text}<p className="text-xs text-slate-500">Evidence: {s.evidence_refs.join(", ")}</p></li>)}</ul></div>)}
      <details><summary>Supporting evidence and provenance</summary><p className="text-xs">Cited references: {report.output?.supporting_evidence_references.join(", ")}</p>{report.evidence_snapshot.entries?.map(e => <div key={e.id} className="my-2 border p-3 text-xs"><h4>{e.id} · {e.kind}</h4><p>{e.text}</p><p className="break-all">Cases: {e.case_ids.join(", ")} · Documents: {e.document_ids.join(", ")} · Claims: {e.claim_ids.join(", ")}</p>{e.provenance.length > 0 && <pre className="overflow-auto">{JSON.stringify(e.provenance, null, 2)}</pre>}</div>)}</details>
    </article>}
  </section>;
}
