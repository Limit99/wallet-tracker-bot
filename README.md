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
| `/add <chain> <address> [label]` | tambah wallet |
| `/list` | lihat wallet |
| `/remove <address>` | hapus wallet |
| `/check` | cek manual sekarang |

Chain valid: `eth`, `base`, `arb`, `op`, `bsc`, `polygon`, `sol`

Contoh:
```
/add eth 0xd8dA6BF26964aF9D7eEd9e03E53415D37aA96045 vitalik
/add sol 5tzFkiKscXHK5ZXCGbXZxdw7gTjjD1mBwuoFbhUvuAi9 usdc
```

## Catatan
- Saat pertama di-add, bot ambil baseline (gak spam histori lama). Notif mulai dari tx berikutnya.
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
