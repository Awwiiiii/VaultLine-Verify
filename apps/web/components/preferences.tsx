"use client";
import { createContext, useContext, useEffect, useState } from "react";
type Preferences = { theme: "light" | "dark"; pageSize: number; dateFormat: "local" | "iso" };
const defaults: Preferences = { theme: "light", pageSize: 20, dateFormat: "local" };
const Context = createContext({ preferences: defaults, update: (_: Partial<Preferences>) => {}, storageAvailable: true, ready: false });
export function PreferencesProvider({ children }: { children: React.ReactNode }) {
  const [preferences, setPreferences] = useState(defaults);
  const [storageAvailable, setStorageAvailable] = useState(true);
  const [ready, setReady] = useState(false);
  useEffect(() => {
    // Hydrate browser-only preferences after server rendering.
    try {
      const value = JSON.parse(localStorage.getItem("vaultline-preferences") || "{}");
      // eslint-disable-next-line react-hooks/set-state-in-effect -- browser-only hydration
      setPreferences({ theme: value?.theme === "dark" ? "dark" : "light", pageSize: [10,20,50].includes(value?.pageSize) ? value.pageSize : 20, dateFormat: value?.dateFormat === "iso" ? "iso" : "local" });
    } catch { setStorageAvailable(false); }
    setReady(true);
  }, []);
  useEffect(() => { document.documentElement.dataset.theme = preferences.theme; }, [preferences.theme]);
  function update(change: Partial<Preferences>) {
    const next = { ...preferences, ...change };
    setPreferences(next);
    try { localStorage.setItem("vaultline-preferences", JSON.stringify(next)); setStorageAvailable(true); } catch { setStorageAvailable(false); }
  }
  return <Context.Provider value={{ preferences, update, storageAvailable, ready }}>{children}</Context.Provider>;
}
export const usePreferences = () => useContext(Context);
export function useDateDisplay() {
  const { preferences } = usePreferences();
  return (value: string) => preferences.dateFormat === "iso" ? new Date(value).toISOString().replace("T", " ").replace(".000Z", " UTC") : new Date(value).toLocaleString();
}
