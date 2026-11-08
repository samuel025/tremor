// Copies committed data into public/ so the site is fully static: the catalog (for the map and replay), the simulation series and summary.
import { cpSync, mkdirSync, readdirSync } from "node:fs";
const root = new URL("../../", import.meta.url).pathname;
mkdirSync("public/sim", { recursive: true }); mkdirSync("public/fixtures", { recursive: true }); cpSync(root + "fixtures/testnet-demo.json", "public/fixtures/testnet-demo.json"); mkdirSync("public/data", { recursive: true });
cpSync(root + "deployments.json", "public/deployments.json");
cpSync(root + "results/results.json", "public/results.json");
cpSync(root + "data/usgs_60d.csv", "public/data/usgs_60d.csv");
for (const f of readdirSync(root + "results/sim")) if (/\.(csv|json|md)$/.test(f)) cpSync(root + "results/sim/" + f, "public/sim/" + f);
console.log("synced data and simulation results");
