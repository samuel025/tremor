// Testnet only. The contract ids live in deployments.json (copied next to the page at build time).
// Free public testnet RPCs, no key. The official one rate-limits (HTTP 429, which browsers report as a CORS error), so it is the fallback.
export const RPCS = ["https://test.rpc.fastnear.com", "https://rpc.testnet.near.org"];
export const EXPLORER = "https://testnet.nearblocks.io/address/";
export const USGS = "https://earthquake.usgs.gov/fdsnws/event/1/query";
export const POLL_MS = 15000;
