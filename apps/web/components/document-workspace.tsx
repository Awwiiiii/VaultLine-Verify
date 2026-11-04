"use client";

import { useRef, useState } from "react";
import { Button } from "@/components/ui/button";
import { ExtractionPanel } from "@/components/extraction-panel";
import { useDateDisplay } from "@/components/preferences";
import { request, type EvidenceDocument } from "@/lib/cases";

const statusLabels: Record<string, string> = {
  uploaded: "Uploaded — not extracted",
  processing: "Extraction processing",
  extracted: "Extracted successfully — document observations only",
  needs_review: "Extraction incomplete — review validation findings",
  failed: "Extraction failed — inspect saved findings or retry",
};

type Props = {
  caseId: string;
  documents: EvidenceDocument[];
  onUploaded: (document: EvidenceDocument) => void;
  onStatus: (id: string, status: string) => void;
  refresh: () => Promise<void>;
};

export function DocumentWorkspace(props: Props) {
  const [refreshing, setRefreshing] = useState(false);
  const [error, setError] = useState("");
  async function refresh() {
    setRefreshing(true); setError("");
    try { await props.refresh(); }
    catch { setError("Unable to refresh documents. Check the connection before uploading again."); }
    finally { setRefreshing(false); }
  }
  return <section id="evidence-documents" aria-labelledby="evidence-title" className="my-6 space-y-4">
    <h2 id="evidence-title" className="text-xl font-semibold">Evidence documents</h2>
    <p className="text-sm text-slate-600">Upload the invoice and supporting purchase order into this case, then extract their financial fields. PDF or UTF-8 CSV, up to 10 MiB. Supported extraction uses field/value CSV or labeled text PDF; no OCR. Uploading does not verify financial contents. All saved documents remain visible.</p>
    <Button variant="outline" disabled={refreshing} onClick={refresh}>{refreshing ? "Refreshing…" : "Refresh documents"}</Button>
    {error && <p role="alert" className="text-red-700">{error}</p>}
    <div className="grid grid-cols-1 items-start gap-6 xl:grid-cols-2">
      <DocumentArea {...props} kind="invoice" title="Invoice" />
      <DocumentArea {...props} kind="purchase_order" title="Purchase order" />
    </div>
  </section>;
}

function DocumentArea({ caseId, documents, onUploaded, onStatus, refresh, kind, title }: Props & { kind: "invoice" | "purchase_order"; title: string }) {
  const date = useDateDisplay();
  const [file, setFile] = useState<File | null>(null);
  const [pending, setPending] = useState(false);
  const [success, setSuccess] = useState("");
  const [error, setError] = useState("");
  const submitting = useRef(false);
  const input = useRef<HTMLInputElement>(null);
  const associated = documents.filter(document => document.document_type === kind);

  async function upload(event: React.FormEvent<HTMLFormElement>) {
    event.preventDefault();
    if (submitting.current || !file) return;
    if (!/\.(pdf|csv)$/i.test(file.name) || file.size === 0 || file.size > 10 * 1024 * 1024) {
      setError("Select a non-empty PDF or CSV file no larger than 10 MiB."); return;
    }
    submitting.current = true; setPending(true); setError(""); setSuccess("");
    try {
      const body = new FormData();
      body.append("document_type", kind); body.append("file", file);
      const saved = await request<EvidenceDocument>(`/${caseId}/documents`, { method: "POST", body });
      onUploaded(saved);
      setSuccess(`Upload successful: ${saved.original_filename}. Saved to this case; extraction has not yet been performed.`);
      setFile(null);
      if (input.current) input.current.value = "";
    } catch (error) {
      setError(`Upload failed or confirmation unavailable. ${error instanceof Error ? error.message : "Check the API connection."} Refresh documents before retrying: the server may have saved the file even if confirmation was lost.`);
    } finally { submitting.current = false; setPending(false); }
  }

  return <section aria-label={`${title} documents`} className="min-w-0 space-y-4 rounded-xl border border-slate-200 bg-white p-5">
    <h3 className="text-lg font-semibold">{title}</h3>
    <form onSubmit={upload} aria-busy={pending} className="space-y-3">
      <label className="block text-sm">{title} file<input ref={input} aria-label={`${title} file`} disabled={pending} type="file" accept=".pdf,.csv" className="mt-2 block w-full" onChange={event => { setFile(event.target.files?.[0] ?? null); setError(""); setSuccess(""); }} /></label>
      <p className="text-sm text-slate-600">{file ? `File selected: ${file.name} · ${file.size.toLocaleString()} bytes` : "No file selected"}</p>
      {file && associated.some(document => document.original_filename === file.name && document.file_size === file.size) && <p className="text-sm text-amber-800">A saved document has this filename and size. Check the history before uploading another copy.</p>}
      <Button disabled={pending || !file} type="submit">{pending ? `Uploading ${title.toLowerCase()}…` : `Upload ${title.toLowerCase()}`}</Button>
      {pending && <div role="status"><progress aria-label={`${title} upload in progress`} className="w-full" /><p>Uploading and awaiting backend persistence confirmation…</p></div>}
      {success && <p role="status" className="text-sm">{success}</p>}
      {error && <p role="alert" className="text-sm text-red-700">{error}</p>}
    </form>
    <p className="text-sm text-slate-600">{associated.length} saved {title.toLowerCase()} document(s)</p>
    {associated.length === 0 && <p className="text-sm">No {title.toLowerCase()} uploaded. Missing evidence remains visible in verification.</p>}
    <ul className="space-y-4">{associated.map(document => <li key={document.id} className="border-t border-slate-200 pt-4 text-sm">
      <h4 className="break-all font-semibold">{document.original_filename}</h4>
      <p>{title} · {document.file_size.toLocaleString()} bytes · {document.content_type}</p>
      <p>{date(document.upload_timestamp)}</p>
      <p className="my-2 font-medium">{statusLabels[document.processing_status] ?? `Recorded status: ${document.processing_status}`}</p>
      <details><summary>Document identity and checksum</summary><p className="break-all">ID: {document.id}</p><p className="break-all font-mono text-xs">SHA-256: {document.sha256_checksum}</p></details>
      <ExtractionPanel caseId={caseId} documentId={document.id} onStatus={status => { onStatus(document.id, status); }} onRefresh={refresh} />
    </li>)}</ul>
  </section>;
}
