# Wallet Tracker Bot (Telegram)

Bot Telegram buat tracking wallet **EVM** (Ethereum, Base, Arbitrum, Optimism, BSC, Polygon) dan **Solana**. Polling otomatis, kirim notif tiap ada transaksi baru.

## Fitur
- Multi-chain EVM lewat satu API key Etherscan V2
- Solana lewat JSON-RPC (Helius / public RPC)
- Simpan wallet per-chat di SQLite
- Notif IN/OUT + link explorer (Etherscan / Solscan)
- Polling tiap N detik (default 60)

## Setup

```bash
cd wallet-tracker-bot
python -m venv .venv && source .venv/bin/activate
pip install -r requirements.txt
cp .env.example .env   # isi token & API key
python bot.py
```

### Yang dibutuhin
1. **Bot token** — bikin bot di [@BotFather](https://t.me/BotFather)
2. **Etherscan API key** — gratis di https://etherscan.io/myapikey (1 key untuk semua chain EVM via V2 API)
3. **Solana RPC** — disarankan [Helius](https://helius.dev) gratis, atau public RPC `https://api.mainnet-beta.solana.com`

## Perintah

| Perintah | Fungsi |
|---|---|
| `/start` | info bot |
| `/add <address> [label]` | tambah wallet (auto-detect EVM/Solana) |
| `/list` | lihat wallet |
| `/remove <address>` | hapus wallet |
| `/check` | cek transaksi manual sekarang |
| `/balance <address>` | saldo native semua chain EVM / SOL |
| `/token <address> <contract> [chain]` | saldo token (smart contract) di wallet |

Gak perlu sebut nama chain — cukup tempel address. Address EVM otomatis dipantau di **semua chain** (`eth`, `base`, `arb`, `op`, `bsc`, `polygon`). Address Solana auto-terdeteksi.

Contoh:
```
/add 0xd8dA6BF26964aF9D7eEd9e03E53415D37aA96045 vitalik
/add 5tzFkiKscXHK5ZXCGbXZxdw7gTjjD1mBwuoFbhUvuAi9 sol-wallet
/balance 0xd8dA6BF26964aF9D7eEd9e03E53415D37aA96045
/token 0xd8dA6BF26964aF9D7eEd9e03E53415D37aA96045 0xA0b86991c6218b36c1d19D4a2e9Eb0cE3606eB48 eth
```

## Catatan
- Saat pertama di-add, bot catat waktunya. Notif cuma muncul buat transaksi **setelah** wallet ditambahkan.
- Tiap address EVM di-scan di semua chain tiap polling, jadi awasi rate limit Etherscan (free tier 5 req/detik). Kurangi `CHAINS` di `chains/evm.py` kalau perlu.
- Bot nge-track transaksi native **dan** token: ERC-20 (EVM, via Etherscan `tokentx`) + SPL (Solana, via `getTransaction` pre/postTokenBalances). Notif IN/OUT lengkap dengan jumlah & symbol/mint.
- Hati-hati rate limit kalau pakai public Solana RPC; pakai Helius lebih stabil.
- Buat deploy 24/7: jalankan di VPS pakai `systemd`, `screen`, atau Docker.

## Struktur
```
wallet-tracker-bot/
├── bot.py            # main bot + polling
├── storage.py        # SQLite
├── chains/
│   ├── evm.py        # Etherscan V2 multichain
│   └── solana.py     # Solana RPC
├── requirements.txt
├── .env.example
└── README.md
```
