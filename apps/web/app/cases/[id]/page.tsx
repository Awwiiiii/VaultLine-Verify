"use client";
import { DocumentWorkspace } from "@/components/document-workspace";
import { useParams } from "next/navigation";
import { useEffect, useState } from "react";
import Link from "next/link";
import { RiskPanel } from "@/components/risk-panel";
import { InvestigationPanel } from "@/components/investigation-panel";
import { ClaimsPanel } from "@/components/claims-panel";
import { VerificationPanel } from "@/components/verification-panel";
import { request, type VerificationCase, type EvidenceDocument } from "@/lib/cases";
export default function Detail(){const {id}=useParams<{id:string}>();return <CaseDetail key={id} id={id}/>;}
function CaseDetail({id}:{id:string}){const [record,setRecord]=useState<VerificationCase|null>(null),[docs,setDocs]=useState<EvidenceDocument[]>([]),[error,setError]=useState("");
useEffect(()=>{let active=true;Promise.all([request<VerificationCase>(`/${id}`),request<EvidenceDocument[]>(`/${id}/documents`)]).then(([c,d])=>{if(active){setRecord(c);setDocs(d);}}).catch(()=>{if(active)setError("Unable to load case. Check the case ID and API connection.");});return()=>{active=false;};},[id]);
async function refreshDocuments(){setDocs(await request<EvidenceDocument[]>(`/${id}/documents`));}
return <><Link href="/cases" className="text-sm text-blue-700 underline">Back to cases</Link>{error&&<p role="alert" className="my-4 text-red-700">{error}</p>}{!record&&!error&&<p role="status">Loading case…</p>}{record&&<><h1 className="mt-5 text-3xl font-semibold">{record.counterparty_name}</h1><p className="mt-2 text-sm text-slate-500">{record.case_reference} · {record.status}</p><nav aria-label="Case sections" className="my-5 flex flex-wrap gap-4 text-sm text-blue-700 underline"><a href="#evidence-documents">Evidence and extraction</a><a href="#verification-title">Verification</a><a href="#risk-title">Risk assessment</a><a href="#investigation-title">Investigation and history</a></nav><p className="my-4 text-sm text-slate-600">1. Upload invoice · 2. Upload supporting purchase order · 3. Extract financial fields · 4. Run verification · 5. Review discrepancies and evidence · 6. Assess risk · 7. Investigate with AI when authorized. Verification remains available with missing evidence.</p><DocumentWorkspace caseId={id} documents={docs} refresh={refreshDocuments} onUploaded={document=>setDocs(current=>[document,...current.filter(item=>item.id!==document.id)])} onStatus={(documentId,status)=>setDocs(current=>current.map(document=>document.id===documentId?{...document,processing_status:status}:document))}/><VerificationPanel caseId={id}/><div className="[&_label]:min-w-0 [&_select]:w-full"><ClaimsPanel caseId={id} documents={docs}/></div><RiskPanel caseId={id}/><InvestigationPanel caseId={id}/></>}</>;}
