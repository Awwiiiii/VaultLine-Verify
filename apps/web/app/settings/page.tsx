"use client";
import { useEffect, useState } from "react";
import { usePreferences } from "@/components/preferences";
import { Button } from "@/components/ui/button";
type Diagnostics = { backend: string; database: string; provider: { provider: string; model: string; configuration: string; availability: string; live_validation: string } | null };
export default function Settings() {
 const { preferences, update, storageAvailable, ready } = usePreferences();
 const [diagnostics,setDiagnostics] = useState<Diagnostics|null>(null), [pending,setPending] = useState(false);
 async function refresh() {
  setPending(true);
  const base=(process.env.NEXT_PUBLIC_API_BASE_URL || "http://localhost:8000").replace(/\/$/, "");
  const read=async(path:string)=>{const r=await fetch(base+path,{cache:"no-store",signal:AbortSignal.timeout(5000)});if(!r.ok)throw new Error();return r.json();};
  const [health,db,ai]=await Promise.allSettled([read("/health"),read("/ready"),read("/system/provider")]);
  setDiagnostics({backend:health.status==="fulfilled"&&health.value.status==="ok"?"Available":"Unavailable — check backend connection",database:db.status==="fulfilled"&&db.value.database==="reachable"?"Ready":"Not ready or unreachable",provider:ai.status==="fulfilled"?ai.value:null});
  setPending(false);
 }
 useEffect(()=>{const timer=setTimeout(()=>void refresh(),0);return ()=>clearTimeout(timer);},[]);
 return <><h1 className="text-3xl font-semibold">Settings</h1><p className="mt-2 text-slate-600">Local preferences and read-only system diagnostics.</p>
 <section className="my-6 space-y-5 rounded-xl border border-slate-200 bg-white p-6"><h2 className="font-semibold">Appearance and preferences</h2><p className="text-sm text-slate-600">Saved in this browser without an account. Date format applies to case activity and saved review timestamps.</p>
 <label className="block">Theme<select aria-label="Theme" disabled={!ready} className="ml-3 rounded border p-2" value={preferences.theme} onChange={e=>update({theme:e.target.value as "light"|"dark"})}><option value="light">Light</option><option value="dark">Dark</option></select></label>
 <label className="block">Default case-list page size<select disabled={!ready} className="ml-3 rounded border p-2" value={preferences.pageSize} onChange={e=>update({pageSize:Number(e.target.value)})}>{[10,20,50].map(n=><option key={n} value={n}>{n} cases</option>)}</select></label>
 <label className="block">Date display<select disabled={!ready} className="ml-3 rounded border p-2" value={preferences.dateFormat} onChange={e=>update({dateFormat:e.target.value as "local"|"iso"})}><option value="local">Browser locale and time zone</option><option value="iso">ISO date and UTC time</option></select></label>
 {!storageAvailable&&<p role="status">Browser storage is unavailable or invalid. Preferences apply to this session; persistence may be unavailable.</p>}</section>
 <section className="my-6 space-y-4 rounded-xl border border-slate-200 bg-white p-6"><h2 className="font-semibold">System diagnostics</h2><Button variant="outline" disabled={pending} onClick={refresh}>{pending?"Checking…":"Refresh diagnostics"}</Button>{pending&&<p role="status">Reading local service status…</p>}{diagnostics&&<dl className="space-y-3"><div><dt className="font-medium">Backend</dt><dd>{diagnostics.backend}</dd></div><div><dt className="font-medium">Database</dt><dd>{diagnostics.database}</dd></div><div><dt className="font-medium">AI provider</dt><dd>{diagnostics.provider?`${diagnostics.provider.provider} · ${diagnostics.provider.model}`:"Status unavailable — diagnostics endpoint unreachable"}</dd></div>{diagnostics.provider&&<><div><dt className="font-medium">Configuration</dt><dd>{diagnostics.provider.configuration}</dd></div><div><dt className="font-medium">Inference availability</dt><dd>{diagnostics.provider.availability} — configuration does not establish successful inference</dd></div></>}</dl>}
 <p className="text-sm text-slate-600">Live Meta inference: untested. Successful live inference has not been validated; account billing remains a known blocker. Unavailable means a local prerequisite is missing or requests are disabled. No external AI calls are made by these diagnostics. Test-only providers are not Meta output. Available inference requires separately validated live success and is never inferred from configuration.</p></section>
 <section className="rounded-xl border border-slate-200 bg-white p-6"><h2 className="font-semibold">Privacy and prototype limits</h2><p className="mt-3 text-sm leading-6 text-slate-600">Use synthetic data only. Authentication and access controls are not implemented. Uploaded evidence and saved review histories are stored by the backend; the isolated demo rolls back on exit. Production retention, secure deployment and access policies are not implemented. Preferences stay in browser storage. API credentials belong only in backend configuration and cannot be entered here. Starting an investigation can share minimized evidence with the configured provider only when backend sharing is approved.</p></section></>;
}
