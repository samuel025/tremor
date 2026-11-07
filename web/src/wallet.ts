// Browsers have no Node `Buffer`, which the wallet libraries expect; provide it before they load.
import { Buffer } from "buffer";
(globalThis as unknown as { Buffer: typeof Buffer }).Buffer = Buffer;
(globalThis as unknown as { global: unknown }).global = globalThis;

// NEAR wallet connection (testnet only) through wallet-selector. Logging in creates a key limited to the Tremor contract, so the
// page can only ever call Tremor methods; it never gets a full-access key.
import { actionCreators, setupWalletSelector, type WalletSelector } from "@near-wallet-selector/core";
import { setupModal } from "@near-wallet-selector/modal-ui";
import "@near-wallet-selector/modal-ui/styles.css";
import { setupMeteorWallet } from "@near-wallet-selector/meteor-wallet";

let selector: WalletSelector | null = null, modal: ReturnType<typeof setupModal> | null = null, contract = "";
export const accountId = (): string | null => selector?.store.getState().accounts.find((a) => a.active)?.accountId ?? null;

export async function initWallet(contractId: string, onChange: (account: string | null) => void) {
  contract = contractId;
  selector = await setupWalletSelector({ network: "testnet", modules: [setupMeteorWallet()] });
  modal = setupModal(selector, { contractId });
  selector.store.observable.subscribe(() => onChange(accountId()));
  onChange(accountId());
}
export const connectWallet = () => modal?.show();
export async function disconnectWallet() { if (!selector) return; const w = await selector.wallet(); await w.signOut(); }

/** Sign and send one Tremor method call. deposit is in yoctoNEAR (a string). */
export async function send(methodName: string, args: object, deposit = "0") {
  if (!selector) throw new Error("wallet not ready");
  const w = await selector.wallet();
  return w.signAndSendTransaction({ receiverId: contract, actions: [actionCreators.functionCall(methodName, args, 100_000_000_000_000n, BigInt(deposit))] });
}
