# Jalanin di Termux (Android)

Bisa banget. Bot ini full Python, gak butuh GUI, jadi cocok jalan di Termux.

## 1. Install Termux
Pakai versi dari **F-Droid** (yang di Play Store udah usang):
https://f-droid.org/packages/com.termux/

## 2. Setup paket dasar
```bash
pkg update && pkg upgrade -y
pkg install -y python git clang rust binutils
```
> `clang` + `rust` dibutuhin karena `aiohttp` & beberapa dependency di-compile dari source di Android.

## 3. Clone repo
```bash
git clone https://github.com/Limit99/wallet-tracker-bot.git
cd wallet-tracker-bot
```

## 4. Install dependency
```bash
pip install --upgrade pip wheel
pip install -r requirements.txt
```
Kalau `aiohttp` gagal build, coba:
```bash
MATHLIB=m pip install aiohttp
```

## 5. Isi konfigurasi
```bash
cp .env.example .env
nano .env      # isi TELEGRAM_BOT_TOKEN, ETHERSCAN_API_KEY, SOLANA_RPC_URL
```
Simpan di nano: `Ctrl+O` lalu `Enter`, keluar `Ctrl+X`.

## 6. Jalanin
```bash
python bot.py
```
Chat bot lo di Telegram, ketik `/start`.

---

## Biar gak mati saat layar terkunci
Android suka bunuh proses background. Pakai wake lock:
```bash
pkg install -y termux-api
termux-wake-lock
```
Aktifin juga: Settings Android → Battery → cari Termux → set **Unrestricted / No restriction**.

## Biar jalan terus walau Termux ketutup
Pakai `tmux`:
```bash
pkg install -y tmux
tmux new -s bot
python bot.py
# detach: tekan Ctrl+B lalu D
# balik lagi: tmux attach -t bot
```

## Update kode nanti
```bash
cd wallet-tracker-bot
git pull
pip install -r requirements.txt
```

## Catatan
- Pakai **Helius RPC** buat Solana, public RPC sering kena rate limit di koneksi HP.
- `wallets.db` (data wallet) bakal kebuat otomatis di folder repo. Jangan di-`git push`.
- Kalau HP-nya hemat baterai agresif (Xiaomi/Oppo/Vivo/Samsung), wajib matiin battery optimization buat Termux, kalau gak bot bakal ke-kill.
