"use client";
import { useSyncExternalStore } from "react";
const key = "aicr-preferences";
const defaults = '{"includeAI":false,"includeInfo":true}';
type Preferences = { includeAI: boolean; includeInfo: boolean };
function subscribe(callback: () => void) { window.addEventListener("storage", callback); window.addEventListener(key, callback); return () => { window.removeEventListener("storage", callback); window.removeEventListener(key, callback); }; }
function snapshot() { try { return localStorage.getItem(key) || defaults; } catch { return defaults; } }
export function usePreferences(): [Preferences, (next: Preferences) => void] {
  const value = useSyncExternalStore(subscribe, snapshot, () => defaults);
  let preferences: Preferences;
  try { const parsed = JSON.parse(value); preferences = { includeAI: parsed.includeAI === true, includeInfo: parsed.includeInfo !== false }; }
  catch { preferences = JSON.parse(defaults); }
  function save(next: Preferences) { localStorage.setItem(key, JSON.stringify(next)); window.dispatchEvent(new Event(key)); }
  return [preferences, save];
}
