import { RPCS } from "./config";
import { DEP } from "./deployment";

export interface Params {
  s0: string; min_mag_x10: number; base_ppm: number; max_event_ppm: number; cooldown_s: number; week_cap_ppm: number; month_cap_ppm: number;
  bond: string; window_s: number; vote_s: number; slash_pct: number; quorum_ppm: number; max_age_s: number; tap_amount: string; relief_accounts: string[];
}
export interface State {
  supply: string; initial_supply: string; minted_7d: string; minted_30d: string; week_left: string; month_left: string; open_events: number; tap_pool: string; log_len: number; now_s: number;
}
export interface Ev {
  event_id: string; mag_x10: number; origin_s: number; reporter: string; reported_at: number; status: "waiting" | "challenged" | "counted" | "rejected";
  challenger: string | null; challenged_at: number; window_ends: number; vote_ends: number | null; real_locked: string; not_real_locked: string;
  minted: string; clipped: boolean; pot: string;
}

async function rpc<T>(method: string, params: unknown): Promise<T> {
  let last: unknown = new Error("no RPC");
  for (const url of RPCS) {
    try {
      const r = await fetch(url, { method: "POST", headers: { "Content-Type": "application/json" }, body: JSON.stringify({ jsonrpc: "2.0", id: 1, method, params }) });
      if (!r.ok) throw new Error(`${url} answered ${r.status}`);
      const j = await r.json();
      if (j.error || j.result?.error) throw new Error(JSON.stringify(j.error ?? j.result.error));
      return j.result as T;
    } catch (e) { last = e; }
  }
  throw last;
}

export async function view<T>(method: string, args: object = {}): Promise<T> {
  const res = await rpc<{ result: number[] }>("query", {
    request_type: "call_function", finality: "final", account_id: DEP.contract, method_name: method,
    args_base64: btoa(JSON.stringify(args)),
  });
  return JSON.parse(new TextDecoder().decode(new Uint8Array(res.result))) as T;
}

export async function accessKeyCount(): Promise<number> {
  const r = await rpc<{ keys: unknown[] }>("query", { request_type: "view_access_key_list", finality: "final", account_id: DEP.contract });
  return r.keys.length;
}

export async function listEvents(): Promise<Ev[]> {
  const out: Ev[] = [];
  for (;;) {
    const page = await view<Ev[]>("list_events", { from: out.length, limit: 100 });
    out.push(...page);
    if (page.length < 100) return out;
  }
}

export async function registered(account: string): Promise<boolean> { return (await view<unknown>("storage_balance_of", { account_id: account })) !== null; }
