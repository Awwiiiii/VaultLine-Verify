export type VerificationCase = { id: string; case_reference: string; counterparty_name: string; status: string; created_at: string; updated_at: string };
export type EvidenceDocument = { id: string; original_filename: string; document_type: string; content_type: string; file_size: number; sha256_checksum: string; upload_timestamp: string; processing_status: string };
export type CasePage = { items: VerificationCase[]; total: number; limit: number; offset: number };
export const API_BASE_URL = (process.env.NEXT_PUBLIC_API_BASE_URL || "http://localhost:8000").replace(/\/$/, "");
export async function request<T>(path: string, init?: RequestInit): Promise<T> {
 const base = API_BASE_URL;
 const response = await fetch(`${base.replace(/\/$/, "")}/api/v1/cases${path}`, { ...init, cache: "no-store", signal: init?.signal ? AbortSignal.any([init.signal, AbortSignal.timeout(60000)]) : AbortSignal.timeout(60000) });
 if (!response.ok) { const body = await response.json().catch(() => null); throw new Error(typeof body?.detail === "string" ? body.detail : `Request failed (${response.status}). Check your input and try again.`); }
 return response.json() as Promise<T>;
}


export async function loadCases(limit: number, offset: number, signal: AbortSignal): Promise<CasePage> {
 const value = await request<unknown>(`?limit=${limit}&offset=${offset}`, { signal });
 if (!value || typeof value !== "object") throw new Error("Invalid cases response");
 const page = value as Partial<CasePage>;
 if (!Array.isArray(page.items) || page.items.length > 100 ||
     !Number.isInteger(page.total) || (page.total ?? -1) < 0 ||
     page.limit !== limit || page.offset !== offset ||
     !page.items.every(item => item && typeof item === "object" &&
       ["id", "case_reference", "counterparty_name", "status", "created_at", "updated_at"].every(key => typeof (item as Record<string, unknown>)[key] === "string"))) {
   throw new Error("Invalid cases response");
 }
 return page as CasePage;
}
