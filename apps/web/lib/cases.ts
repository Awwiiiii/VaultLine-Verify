export type VerificationCase = { id: string; case_reference: string; counterparty_name: string; status: string; created_at: string; updated_at: string };
export type EvidenceDocument = { id: string; original_filename: string; document_type: string; content_type: string; file_size: number; sha256_checksum: string; upload_timestamp: string; processing_status: string };
export type CasePage = { items: VerificationCase[]; total: number; limit: number; offset: number };
export async function request<T>(path: string, init?: RequestInit): Promise<T> {
 const base = process.env.NEXT_PUBLIC_API_BASE_URL || "http://localhost:8000";
 const response = await fetch(`${base.replace(/\/$/, "")}/api/v1/cases${path}`, { ...init, cache: "no-store", signal: AbortSignal.timeout(60000) });
 if (!response.ok) { const body = await response.json().catch(() => null); throw new Error(typeof body?.detail === "string" ? body.detail : `Request failed (${response.status}). Check your input and try again.`); }
 return response.json() as Promise<T>;
}
