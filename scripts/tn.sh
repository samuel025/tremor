#!/usr/bin/env bash
# Tiny testnet helper (testnet only). Usage: source scripts/tn.sh; call <signer> <method> '<json>' [deposit]; view <method> '<json>'
export HOME="$(cd "$(dirname "${BASH_SOURCE[0]}")/.." && pwd)/.state/home"
P=$(cat "$HOME/../parent_account"); C=tremor.$P
call(){ near contract call-function as-transaction $C "$2" json-args "$3" prepaid-gas '100 Tgas' attached-deposit "${4:-0 NEAR}" sign-as "$1.$P" network-config testnet sign-with-legacy-keychain send 2>&1; }
view(){ near contract call-function as-read-only $C "$1" json-args "${2:-{\}}" network-config testnet now 2>&1 | grep -v -E "^\s*$|CLI|self-update|re-run|near contract|Here is" ; }
