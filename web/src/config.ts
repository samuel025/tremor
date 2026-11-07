// Testnet only. The contract id can be overridden at build time: VITE_CONTRACT=name.testnet npm run build
export const CONTRACT: string = (import.meta.env.VITE_CONTRACT as string | undefined) ?? "tremor.rounds-indep-5928.testnet";
// Free public testnet RPCs, no key. The official one rate-limits (HTTP 429, which browsers report as a CORS error), so it is the fallback.
export const RPCS = ["https://test.rpc.fastnear.com", "https://rpc.testnet.near.org"];
export const EXPLORER = "https://testnet.nearblocks.io/address/";
export const USGS = "https://earthquake.usgs.gov/fdsnws/event/1/query";
export const POLL_MS = 15000;
