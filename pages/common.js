// Shared client-side config/helpers for dashboard.html and detail.html
// (REV-053). Loaded via same-origin <script src="common.js"> before each
// page's own inline <script>, so plain global `const`/`function` declarations
// here are visible there (classic scripts, not modules -- load order is the
// only contract).

// Publishable (anon) key is client-safe by design: RLS scopes it to
// read-only call_log + watchlist (dashboard also needs the watchlist SELECT
// policy, #16).
const SUPABASE_URL = "https://ikghqdtlbwifwnooytmm.supabase.co";
const SUPABASE_PUBLISHABLE_KEY = "sb_publishable_1CNiVwpI_NV7MzOvi_XucA_nQ47FKjG";

const VERDICT = {
  Buy:  {bg:"var(--buy-bg)",  text:"var(--buy-text)"},
  Sell: {bg:"var(--sell-bg)", text:"var(--sell-text)"},
  Hold: {bg:"var(--hold-bg)", text:"var(--hold-text)"},
};

const esc = s => String(s ?? "").replace(/[&<>"]/g, c =>
  ({"&":"&amp;","<":"&lt;",">":"&gt;",'"':"&quot;"}[c]));

// Currency: ONE shape shared by both pages (REV-053 -- previously dashboard
// keyed by market and detail keyed by currency code, independently). Keyed
// by ISO currency code, with a market -> code lookup for call sites that
// only have a market. No FX: native-currency display only (UI-handoff v3).
const CUR = {USD:"$", CAD:"CA$", INR:"₹"};
const MKT_CUR_CODE = {US:"USD", TSX:"CAD", NSE:"INR"};
const curSymByCode = c => CUR[c] || (c ? c + " " : "");
const curSymByMarket = m => curSymByCode(MKT_CUR_CODE[m]);

// FR23 dual-timezone display helpers: device tz primary + IST secondary in
// brackets, deduped when the device is already IST.
const _TZSHORT = {EST:"ET",EDT:"ET",CST:"CT",CDT:"CT",MST:"MT",MDT:"MT",PST:"PT",PDT:"PT"};
function tzLabel(iso, tz){
  const p = new Intl.DateTimeFormat("en-US",{timeZone:tz,timeZoneName:"short"})
    .formatToParts(new Date(iso)).find(x => x.type === "timeZoneName");
  const raw = p ? p.value : "";
  return _TZSHORT[raw] || raw;   // "EST"->"ET"; leaves e.g. "GMT+5:30" as-is
}
function clockIn(iso, tz, withDate){
  const opt = withDate
    ? {timeZone:tz, month:"short", day:"numeric", hour:"numeric", minute:"2-digit"}
    : {timeZone:tz, hour:"numeric", minute:"2-digit"};
  return new Date(iso).toLocaleString("en-US", opt);
}
