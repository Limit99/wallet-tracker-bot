"""Polling transaksi EVM lewat Etherscan V2 multichain API.

Satu API key Etherscan bisa dipakai untuk semua chain EVM yang didukung
(Ethereum, Base, Arbitrum, Optimism, BSC, Polygon, dll) cuma dengan
ganti parameter chainid.
"""
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


def is_evm_address(addr: str) -> bool:
    return addr.startswith("0x") and len(addr) == 42


async def fetch_latest_txs(session: aiohttp.ClientSession, address: str,
                           api_key: str, chainid: int = 1, limit: int = 5):
    """Ambil transaksi normal terbaru untuk sebuah address EVM."""
    params = {
        "chainid": chainid,
        "module": "account",
        "action": "txlist",
        "address": address,
        "startblock": 0,
        "endblock": 99999999,
        "page": 1,
        "offset": limit,
        "sort": "desc",
        "apikey": api_key,
    }
    async with session.get(BASE_URL, params=params, timeout=30) as resp:
        data = await resp.json()
    if data.get("status") != "1" or not isinstance(data.get("result"), list):
        return []
    return data["result"]


def format_tx(tx: dict, address: str, explorer: str = "https://etherscan.io") -> str:
    address = address.lower()
    direction = "📤 OUT" if tx["from"].lower() == address else "📥 IN"
    value_eth = int(tx.get("value", "0")) / 1e18
    counterpart = tx["to"] if direction.endswith("OUT") else tx["from"]
    short = f"{counterpart[:8]}...{counterpart[-6:]}" if counterpart else "contract"
    return (
        f"{direction}  {value_eth:.6f} (native)\n"
        f"↔️ {short}\n"
        f"🔗 {explorer}/tx/{tx['hash']}"
    )


async def fetch_latest_token_txs(session: aiohttp.ClientSession, address: str,
                                 api_key: str, chainid: int = 1, limit: int = 5):
    """Ambil transfer ERC-20 terbaru untuk sebuah address EVM."""
    params = {
        "chainid": chainid,
        "module": "account",
        "action": "tokentx",
        "address": address,
        "startblock": 0,
        "endblock": 99999999,
        "page": 1,
        "offset": limit,
        "sort": "desc",
        "apikey": api_key,
    }
    async with session.get(BASE_URL, params=params, timeout=30) as resp:
        data = await resp.json()
    if data.get("status") != "1" or not isinstance(data.get("result"), list):
        return []
    return data["result"]


def format_token_tx(tx: dict, address: str, explorer: str = "https://etherscan.io") -> str:
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