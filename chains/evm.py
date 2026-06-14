"""Polling transaksi & cek balance EVM lewat Etherscan V2 multichain API.

Satu API key Etherscan dipakai untuk semua chain EVM cukup dengan ganti
parameter chainid. Tidak perlu sebut nama chain saat add address — bot
otomatis scan semua chain di bawah ini.
"""
from __future__ import annotations
import aiohttp

BASE_URL = "https://api.etherscan.io/v2/api"

# chainid Etherscan V2. Tambah sesuai kebutuhan.
CHAINS = {
    "eth": 1,
    "base": 8453,
    "arb": 42161,
    "op": 10,
    "bsc": 56,
    "polygon": 137,
}

EXPLORERS = {
    "eth": "https://etherscan.io",
    "base": "https://basescan.org",
    "arb": "https://arbiscan.io",
    "op": "https://optimistic.etherscan.io",
    "bsc": "https://bscscan.com",
    "polygon": "https://polygonscan.com",
}

NATIVE_SYMBOL = {
    "eth": "ETH", "base": "ETH", "arb": "ETH",
    "op": "ETH", "bsc": "BNB", "polygon": "POL",
}


def is_evm_address(addr: str) -> bool:
    return addr.startswith("0x") and len(addr) == 42


async def _get(session: aiohttp.ClientSession, params: dict):
    async with session.get(BASE_URL, params=params, timeout=30) as resp:
        return await resp.json()


# ---------- transaksi ----------

async def fetch_latest_txs(session, address, api_key, chainid=1, limit=5):
    """Transaksi native terbaru untuk sebuah address EVM."""
    data = await _get(session, {
        "chainid": chainid, "module": "account", "action": "txlist",
        "address": address, "startblock": 0, "endblock": 99999999,
        "page": 1, "offset": limit, "sort": "desc", "apikey": api_key,
    })
    if data.get("status") != "1" or not isinstance(data.get("result"), list):
        return []
    return data["result"]


async def fetch_latest_token_txs(session, address, api_key, chainid=1, limit=5):
    """Transfer ERC-20 terbaru untuk sebuah address EVM."""
    data = await _get(session, {
        "chainid": chainid, "module": "account", "action": "tokentx",
        "address": address, "startblock": 0, "endblock": 99999999,
        "page": 1, "offset": limit, "sort": "desc", "apikey": api_key,
    })
    if data.get("status") != "1" or not isinstance(data.get("result"), list):
        return []
    return data["result"]


# ---------- balance ----------

async def fetch_native_balance(session, address, api_key, chainid=1) -> float:
    """Saldo native (ETH/BNB/POL) dalam satuan utuh."""
    data = await _get(session, {
        "chainid": chainid, "module": "account", "action": "balance",
        "address": address, "tag": "latest", "apikey": api_key,
    })
    if data.get("status") != "1":
        return 0.0
    return int(data["result"]) / 1e18


async def fetch_token_balance(session, address, contract, api_key, chainid=1) -> float:
    """Saldo ERC-20 (smart contract) untuk sebuah wallet, dalam satuan utuh."""
    data = await _get(session, {
        "chainid": chainid, "module": "account", "action": "tokenbalance",
        "contractaddress": contract, "address": address, "tag": "latest",
        "apikey": api_key,
    })
    if data.get("status") != "1":
        return 0.0
    decimals = await fetch_token_decimals(session, contract, api_key, chainid)
    return int(data["result"]) / (10 ** decimals)


async def fetch_token_decimals(session, contract, api_key, chainid=1) -> int:
    """Ambil decimals token via eth_call decimals() (free-tier friendly)."""
    data = await _get(session, {
        "chainid": chainid, "module": "proxy", "action": "eth_call",
        "to": contract, "data": "0x313ce567", "tag": "latest", "apikey": api_key,
    })
    result = data.get("result")
    if not result or result == "0x":
        return 18
    try:
        return int(result, 16)
    except ValueError:
        return 18


# ---------- formatting ----------

def format_tx(tx: dict, address: str, explorer: str, symbol: str = "ETH") -> str:
    address = address.lower()
    direction = "📤 OUT" if tx["from"].lower() == address else "📥 IN"
    value = int(tx.get("value", "0")) / 1e18
    counterpart = tx["to"] if direction.endswith("OUT") else tx["from"]
    short = f"{counterpart[:8]}...{counterpart[-6:]}" if counterpart else "contract"
    return (
        f"{direction}  {value:.6f} {symbol}\n"
        f"↔️ {short}\n"
        f"🔗 {explorer}/tx/{tx['hash']}"
    )


def format_token_tx(tx: dict, address: str, explorer: str) -> str:
    address = address.lower()
    direction = "📤 OUT" if tx["from"].lower() == address else "📥 IN"
    try:
        decimals = int(tx.get("tokenDecimal", "18") or "18")
        amount = int(tx.get("value", "0")) / (10 ** decimals)
    except (ValueError, ZeroDivisionError):
        amount = 0
    symbol = tx.get("tokenSymbol", "?")
    counterpart = tx["to"] if direction.endswith("OUT") else tx["from"]
    short = f"{counterpart[:8]}...{counterpart[-6:]}" if counterpart else "contract"
    return (
        f"{direction}  {amount:,.4f} {symbol} (token)\n"
        f"↔️ {short}\n"
        f"🔗 {explorer}/tx/{tx['hash']}"
    )
