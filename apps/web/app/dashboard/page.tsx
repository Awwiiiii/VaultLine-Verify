"use client";
import Link from "next/link";
import { useEffect, useState } from "react";
import { request, type CasePage } from "@/lib/cases";
import { useDateDisplay } from "@/components/preferences";
import { Button } from "@/components/ui/button";
export default function Dashboard() {
 const [data,setData] = useState<CasePage|null>(null), [error,setError] = useState("");
 const date = useDateDisplay();
 useEffect(() => { let active=true; request<CasePage>("?limit=5&offset=0").then(d=>{if(active)setData(d);}).catch(()=>{if(active)setError("Unable to load overview. Check the backend connection in Settings.");}); return ()=>{active=false;}; }, []);
 return <><div className="flex flex-wrap justify-between gap-4"><div><h1 className="text-3xl font-semibold">Verification overview</h1><p className="mt-2 text-slate-600">Recorded evidence and cases requiring human review.</p></div><Button asChild><Link href="/cases">New verification</Link></Button></div>
 {error && <p role="alert" className="my-6 text-red-700">{error} <Link href="/settings" className="underline">Open Settings</Link></p>}
 {!data&&!error&&<p role="status" className="my-6">Loading overview…</p>}
 {data&&<><section className="my-6 rounded-xl border border-slate-200 bg-white p-6"><h2 className="text-sm text-slate-600">Total recorded cases</h2><p className="mt-2 text-3xl font-semibold">{data.total}</p><p className="mt-2 text-sm text-slate-600">Case workflow status is separate from verification outcomes. Every assessment requires human review.</p></section><section className="rounded-xl border border-slate-200 bg-white p-6"><h2 className="font-semibold">Recently created cases</h2><p className="mt-2 text-sm text-slate-600">Up to five newest cases. This is case creation activity, not a complete verification or audit feed.</p><ul className="mt-4 divide-y divide-slate-200">{data.items.map(c=><li key={c.id} className="py-4"><Link className="font-medium text-blue-700 underline" href={`/cases/${c.id}`}>{c.counterparty_name}</Link><p className="mt-1 break-all text-sm text-slate-600">{c.case_reference} · Workflow: {c.status} · Created {date(c.created_at)}</p></li>)}</ul>{data.total===0&&<p className="mt-4">No cases yet. Create a case and upload synthetic evidence to begin.</p>}<Link href="/cases" className="mt-4 inline-block text-blue-700 underline">View all cases</Link></section></>}
 </>;
}
