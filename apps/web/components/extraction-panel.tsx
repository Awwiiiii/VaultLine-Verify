"use client";

import { useRef, useState } from "react";
import { Button } from "@/components/ui/button";
import { request } from "@/lib/cases";

type Provenance = {
  field_name: string;
  original_value: string;
  normalized_value: string | null;
  source_location: Record<string, string | number>;
  extraction_method: string;
  validation_status: string;
};
type Extraction = {
  status: string;
  error: string | null;
  result: {
    fields: Record<string, string | null>;
    line_items: Record<string, string | null>[];
    findings: { field: string; code: string; message: string }[];
    provenance: Provenance[];
  };
};

export function ExtractionPanel({ caseId, documentId, onStatus, onRefresh }: { caseId: string; documentId: string; onStatus: (status: string) => void; onRefresh?: () => Promise<void> }) {
  const submitting = useRef(false);
  const [refreshWarning, setRefreshWarning] = useState("");
  const [data, setData] = useState<Extraction | null>(null);
  const [pending, setPending] = useState(false);
  const [error, setError] = useState("");

  async function load(extract: boolean) {
    if (submitting.current) return;
    submitting.current = true;
    setRefreshWarning("");
    setPending(true);
    setError("");
    try {
      const action = extract ? "extract" : "extraction";
      const result = await request<Extraction>(`/${caseId}/documents/${documentId}/${action}`, { method: extract ? "POST" : "GET" });
      setData(result);
      onStatus(result.status);
      if (onRefresh) { try { await onRefresh(); } catch { setRefreshWarning("Extraction result received, but document details could not refresh. Use Refresh documents."); } }
    } catch (error) {
      setError(error instanceof Error ? error.message : "Extraction request failed");
    } finally {
      submitting.current = false;
      setPending(false);
    }
  }

  return <div className="mt-4 space-y-4">
    <div className="flex flex-wrap gap-3">
      <Button disabled={pending} onClick={() => load(true)}>{pending ? "Processing…" : data?.status === "failed" ? "Retry extraction" : "Extract financial fields"}</Button>
      <Button variant="outline" disabled={pending} onClick={() => load(false)}>View saved extraction</Button>
    </div>
    {pending && <p role="status">Reading and normalizing document fields…</p>}
    {refreshWarning && <p role="status">{refreshWarning}</p>}
    {error && <p role="alert" className="text-red-700">{error}</p>}
    {data && <p role="status">{data.status === "extracted" ? "Extraction successful." : data.status === "failed" ? "Extraction failed. Review the saved error and retry after checking the document." : data.status === "needs_review" ? "Extraction incomplete. Review unresolved fields and validation findings." : `Recorded extraction status: ${data.status}`}</p>}
    {data && <section aria-label="Document extraction" className="space-y-4 rounded-lg bg-slate-50 p-4">
      <h4 className="font-semibold">Extraction: {data.status.replaceAll("_", " ")}</h4>
      <p className="text-slate-600">Extracted values are document observations, not verified financial claims. No OCR or AI is used.</p>
      {data.error && <p role="alert" className="text-red-700">{data.error}</p>}
      <dl className="grid gap-3 sm:grid-cols-2">{Object.entries(data.result.fields).map(([key, value]) => <div key={key}><dt className="text-slate-500">{key.replaceAll("_", " ")}</dt><dd className="break-words font-medium">{value ?? "Unresolved"}</dd></div>)}</dl>
      {data.result.line_items.length > 0 && <div><h5 className="font-medium">Line items</h5>{data.result.line_items.map((item, i) => <dl key={i} className="mt-2 flex flex-wrap gap-4 border-t border-slate-200 pt-2">{Object.entries(item).map(([key, value]) => <div key={key}><dt className="text-slate-500">{key}</dt><dd>{value ?? "Unresolved"}</dd></div>)}</dl>)}</div>}
      <div><h5 className="font-medium">Validation findings</h5>{data.result.findings.length === 0 ? <p>No validation findings recorded. This does not establish financial verification.</p> : <ul className="list-inside list-disc">{data.result.findings.map((finding, i) => <li key={i}>{finding.field}: {finding.message}{finding.code === "unsupported_field" && " Check the uploaded document type and schema; extraction does not change document types."}</li>)}</ul>}</div>
      <details><summary className="cursor-pointer font-medium">Field provenance and original values</summary><div className="overflow-x-auto"><table className="mt-3 w-full text-left text-xs"><caption className="sr-only">Field-level source evidence</caption><thead><tr>{["Field", "Original", "Normalized", "Source", "Method", "Validation"].map(label => <th key={label} scope="col" className="p-2">{label}</th>)}</tr></thead><tbody>{data.result.provenance.map((field, i) => <tr key={i} className="border-t border-slate-200"><td className="p-2">{field.field_name}</td><td className="whitespace-pre-wrap p-2">{field.original_value}</td><td className="p-2">{field.normalized_value ?? "Unresolved"}</td><td className="p-2">{Object.entries(field.source_location).map(([key,value]) => `${key}: ${value}`).join(", ")}</td><td className="p-2">{field.extraction_method}</td><td className="p-2">{field.validation_status}</td></tr>)}</tbody></table></div></details>
    </section>}
  </div>;
}
