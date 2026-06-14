"""Polling transaksi Solana lewat JSON-RPC (getSignaturesForAddress)."""
from __future__ import annotations
import aiohttp

# Base58 alphabet (tanpa 0, O, I, l)
_B58 = "123456789ABCDEFGHJKLMNPQRSTUVWXYZabcdefghijkmnopqrstuvwxyz"


def is_solana_address(addr: str) -> bool:
    if not (32 <= len(addr) <= 44):
        return False
    return all(ch in _B58 for ch in addr)


async def fetch_latest_signatures(session: aiohttp.ClientSession, rpc_url: str,
                                  address: str, limit: int = 5):
    payload = {
        "jsonrpc": "2.0",
        "id": 1,
        "method": "getSignaturesForAddress",
        "params": [address, {"limit": limit}],
    }
    async with session.post(rpc_url, json=payload, timeout=30) as resp:
        data = await resp.json()
    return data.get("result", []) or []


def format_sig(sig: dict, address: str) -> str:
    status = "❌ failed" if sig.get("err") else "✅ ok"
    short = f"{address[:6]}...{address[-6:]}"
    return (
        f"🌀 Solana tx ({status})\n"
        f"👛 {short}\n"
        f"🔗 https://solscan.io/tx/{sig['signature']}"
    )


async def fetch_transaction(session: aiohttp.ClientSession, rpc_url: str, signature: str):
    """Ambil detail transaksi (buat deteksi perpindahan token SPL & SOL)."""
    payload = {
        "jsonrpc": "2.0",
        "id": 1,
        "method": "getTransaction",
        "params": [
            signature,
            {"encoding": "jsonParsed", "maxSupportedTransactionVersion": 0},
        ],
    }
    async with session.post(rpc_url, json=payload, timeout=30) as resp:
        data = await resp.json()
    return data.get("result")


def extract_token_changes(tx: dict, owner: str) -> list[str]:
    """Hitung delta saldo SPL token milik `owner` dari pre/postTokenBalances."""
    if not tx:
        return []
    meta = tx.get("meta") or {}
    pre = {b["accountIndex"]: b for b in (meta.get("preTokenBalances") or [])}
    post = {b["accountIndex"]: b for b in (meta.get("postTokenBalances") or [])}
    lines = []
    for idx, pb in post.items():
        if pb.get("owner") != owner:
            continue
        pre_amt = float((pre.get(idx, {}).get("uiTokenAmount") or {}).get("uiAmount") or 0)
        post_amt = float((pb.get("uiTokenAmount") or {}).get("uiAmount") or 0)
        delta = post_amt - pre_amt
        if abs(delta) < 1e-9:
            continue
        mint = pb.get("mint", "?")
        direction = "📥 IN" if delta > 0 else "📤 OUT"
        lines.append(f"{direction}  {abs(delta):,.4f}  (mint {mint[:6]}...{mint[-4:]})")
    return lines


def format_token_change(signature: str, owner: str, changes: list[str]) -> str:
    short = f"{owner[:6]}...{owner[-6:]}"
    body = "\n".join(changes)
    return (
        f"🌀 Solana token transfer\n"
        f"👛 {short}\n"
        f"{body}\n"
        f"🔗 https://solscan.io/tx/{signature}"
    )


async def fetch_balance(session: aiohttp.ClientSession, rpc_url: str, address: str) -> float:
    """Saldo SOL (dalam satuan SOL, bukan lamports)."""
    payload = {"jsonrpc": "2.0", "id": 1, "method": "getBalance", "params": [address]}
    async with session.post(rpc_url, json=payload, timeout=30) as resp:
        data = await resp.json()
    lamports = ((data.get("result") or {}).get("value")) or 0
    return lamports / 1e9


async def fetch_token_balance(session: aiohttp.ClientSession, rpc_url: str,
                              owner: str, mint: str) -> float:
    """Saldo SPL token (smart contract / mint) untuk sebuah owner."""
    payload = {
        "jsonrpc": "2.0", "id": 1,
        "method": "getTokenAccountsByOwner",
        "params": [
            owner,
            {"mint": mint},
            {"encoding": "jsonParsed"},
        ],
    }
    async with session.post(rpc_url, json=payload, timeout=30) as resp:
        data = await resp.json()
    accounts = ((data.get("result") or {}).get("value")) or []
    total = 0.0
    for acc in accounts:
        info = acc["account"]["data"]["parsed"]["info"]["tokenAmount"]
        total += float(info.get("uiAmount") or 0)
    return total