"use client";
import { useEffect, useState } from "react";
import { getHealth } from "@/lib/api";
export function Status() { const [status, setStatus] = useState("Checking backend…"); useEffect(() => { let active = true; getHealth().then(() => { if(active) setStatus("Backend connected"); }).catch(() => { if(active) setStatus("Backend unavailable — check API configuration"); }); return () => { active = false; }; }, []); return <span role="status" className="text-sm text-slate-600">{status}</span>; }
