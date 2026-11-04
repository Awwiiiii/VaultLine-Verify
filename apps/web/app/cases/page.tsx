"use client";
import { usePreferences } from "@/components/preferences";
import Link from "next/link";
import { useEffect, useState } from "react";
import { Button } from "@/components/ui/button";
import { API_BASE_URL, loadCases, request, type CasePage } from "@/lib/cases";

export default function Cases() {
  const { preferences } = usePreferences();
  const pageSize = preferences.pageSize;
  const [data, setData] = useState<CasePage | null>(null);
  const [error, setError] = useState("");
  const [createError, setCreateError] = useState("");
  const [offset, setOffset] = useState(0);
  const [pending, setPending] = useState(false);
  const [loading, setLoading] = useState(true);
  const [attempt, setAttempt] = useState(0);

  useEffect(() => {
    let active = true;
    const controller = new AbortController();
    // Fetch with defaults immediately; saved preferences may replace this request after hydration.
    // eslint-disable-next-line react-hooks/set-state-in-effect -- start a new cancellable request
    setLoading(true);
    setError("");
    const signal = AbortSignal.any([controller.signal, AbortSignal.timeout(10000)]);
    loadCases(pageSize, offset, signal)
      .then(result => { if (active) setData(result); })
      .catch(() => {
        if (active) setError("Unable to load cases. Check the backend URL, connection and allowed frontend origin, then retry.");
      })
      .finally(() => { if (active) setLoading(false); });
    return () => { active = false; controller.abort(); };
  }, [offset, pageSize, attempt]);

  async function create(event: React.FormEvent<HTMLFormElement>) {
    event.preventDefault();
    const form = event.currentTarget;
    setPending(true); setCreateError("");
    try {
      await request("", { method: "POST", headers: { "Content-Type": "application/json" }, body: JSON.stringify({ counterparty_name: new FormData(form).get("counterparty_name") }) });
      form.reset(); setOffset(0); setAttempt(value => value + 1);
    } catch (error) { setCreateError(error instanceof Error ? error.message : "Unable to create case"); }
    finally { setPending(false); }
  }

  return <>
    <h1 className="text-3xl font-semibold">Verification cases</h1>
    <p className="mt-2 text-slate-500">Create a case and preserve its supporting evidence.</p>
    <noscript>JavaScript is required to load cases. Enable it and reload this page.</noscript>
    <form onSubmit={create} className="my-6 flex flex-wrap items-end gap-4 rounded-xl border border-slate-200 bg-white p-5">
      <label className="text-sm">Counterparty name<input name="counterparty_name" required maxLength={200} className="mt-2 block rounded border border-slate-300 p-2" /></label>
      <Button disabled={pending}>{pending ? "Creating…" : "New verification"}</Button>
    </form>
    {createError && <p role="alert" className="my-4 text-red-700">{createError}</p>}
    {error && <div role="alert" className="my-4 space-y-3 text-red-700"><p>{error}</p><p className="break-all text-sm">API base URL: {API_BASE_URL}</p><Button variant="outline" onClick={() => setAttempt(value => value + 1)}>Retry loading cases</Button></div>}
    <section aria-busy={loading} className="overflow-x-auto rounded-xl border border-slate-200 bg-white">
      <table className="w-full text-left text-sm"><caption className="sr-only">Verification cases</caption><thead><tr>{["Reference", "Counterparty", "Status"].map(label => <th key={label} className="p-4">{label}</th>)}</tr></thead>
        <tbody>{!loading && !error && data?.items.map(record => <tr key={record.id} className="border-t border-slate-100"><td className="p-4"><Link className="text-blue-700 underline" href={`/cases/${record.id}`}>{record.case_reference}</Link></td><td className="p-4">{record.counterparty_name}</td><td className="p-4">{record.status}</td></tr>)}</tbody>
      </table>
      {loading && <p role="status" className="p-6">Loading cases…</p>}
      {!loading && !error && data?.items.length === 0 && <p className="p-6">No cases found. Create a verification case to add synthetic evidence.</p>}
    </section>
    <div className="mt-4 flex items-center gap-4">
      <Button variant="outline" disabled={loading || !!error || offset === 0} onClick={() => setOffset(Math.max(0, offset - pageSize))}>Previous</Button>
      <span className="text-sm">{data && !loading && !error ? `${data.total} cases` : "Case count unavailable"}</span>
      <Button variant="outline" disabled={loading || !!error || !data || offset + pageSize >= data.total} onClick={() => setOffset(offset + pageSize)}>Next</Button>
    </div>
  </>;
}
