"""
Telegram Wallet Tracker Bot — support EVM (semua chain) + Solana.

Cara pakai:
  /start                       -> info bot
  /add <address> [label]       -> tambah wallet (auto-detect EVM/Solana)
                                  EVM otomatis ke-track di SEMUA chain.
  /list                        -> lihat wallet yang di-track
  /remove <address>            -> hapus wallet
  /check                       -> cek transaksi manual sekarang
  /balance <address>           -> saldo native (semua chain EVM) / SOL
  /token <address> <contract> [chain]
                               -> saldo token (smart contract) di sebuah wallet

Bot otomatis polling tiap POLL_INTERVAL detik dan kirim notif kalau ada tx baru.
"""
from __future__ import annotations
import os
import json
import logging
import aiohttp
from dotenv import load_dotenv
from telegram import Update
from telegram.constants import ParseMode
from telegram.ext import (
    Application, CommandHandler, ContextTypes,
)

import storage
from chains import evm, solana

load_dotenv()

TOKEN = os.environ["TELEGRAM_BOT_TOKEN"]
ETHERSCAN_KEY = os.environ.get("ETHERSCAN_API_KEY", "")
SOLANA_RPC = os.environ.get("SOLANA_RPC_URL", "https://api.mainnet-beta.solana.com")
POLL_INTERVAL = int(os.environ.get("POLL_INTERVAL", "60"))

logging.basicConfig(
    format="%(asctime)s - %(name)s - %(levelname)s - %(message)s",
    level=logging.INFO,
)
log = logging.getLogger("wallet-tracker")


# ---------- command handlers ----------

async def start(update: Update, ctx: ContextTypes.DEFAULT_TYPE):
    await update.message.reply_text(
        "👋 *Wallet Tracker Bot*\n\n"
        "Tempel address-nya aja, aku auto-detect EVM atau Solana. "
        "Address EVM otomatis dipantau di *semua chain* (eth, base, arb, op, bsc, polygon).\n\n"
        "*Perintah:*\n"
        "`/add <address> [label]` — tambah wallet\n"
        "`/list` — lihat wallet\n"
        "`/remove <address>` — hapus wallet\n"
        "`/check` — cek transaksi manual\n"
        "`/balance <address>` — saldo native semua chain / SOL\n"
        "`/token <address> <contract> [chain]` — saldo token (smart contract)\n\n"
        "Contoh:\n"
        "`/add 0xd8dA6BF26964aF9D7eEd9e03E53415D37aA96045 vitalik`\n"
        "`/add 5tzFkiKscXHK5ZXCGbXZxdw7gTjjD1mBwuoFbhUvuAi9 sol-wallet`\n"
        "`/token 0xd8dA...6045 0xA0b8...eB48 eth`",
        parse_mode=ParseMode.MARKDOWN,
    )


async def add(update: Update, ctx: ContextTypes.DEFAULT_TYPE):
    args = ctx.args
    if not args:
        await update.message.reply_text("Format: /add <address> [label]")
        return

    address = args[0]
    label = " ".join(args[1:]) if len(args) > 1 else None
    chat_id = update.effective_chat.id

    if evm.is_evm_address(address):
        chain = "evm"                         # multichain: scan semua CHAINS
        kind_msg = "EVM (semua chain)"
    elif solana.is_solana_address(address):
        chain = "solana"
        kind_msg = "Solana"
    else:
        await update.message.reply_text(
            "⚠️ Address tidak dikenali. Tempel address EVM (0x...) atau Solana."
        )
        return

    wallet_id = storage.add_wallet(chat_id, chain, address, label)
    if wallet_id:
        tag = f" ({label})" if label else ""
        await update.message.reply_text(
            f"✅ Tracking {kind_msg}: `{address}`{tag}\n"
            f"Mulai dari sekarang — transaksi sebelum ini diabaikan.",
            parse_mode=ParseMode.MARKDOWN)
    else:
        await update.message.reply_text("ℹ️ Wallet itu sudah ada di list.")


async def remove(update: Update, ctx: ContextTypes.DEFAULT_TYPE):
    if not ctx.args:
        await update.message.reply_text("Format: /remove <address>")
        return
    n = storage.remove_wallet(update.effective_chat.id, ctx.args[0])
    await update.message.reply_text("🗑️ Dihapus." if n else "Tidak ketemu wallet itu.")


async def list_cmd(update: Update, ctx: ContextTypes.DEFAULT_TYPE):
    rows = storage.list_wallets(update.effective_chat.id)
    if not rows:
        await update.message.reply_text("Belum ada wallet. Tambah dengan /add")
        return
    lines = []
    for r in rows:
        tag = f" — {r['label']}" if r["label"] else ""
        kind = "EVM" if r["chain"].startswith("evm") else "SOL"
        lines.append(f"• [{kind}] `{r['address'][:10]}...{r['address'][-6:]}`{tag}")
    await update.message.reply_text("*Wallet di-track:*\n" + "\n".join(lines),
                                    parse_mode=ParseMode.MARKDOWN)


async def check_cmd(update: Update, ctx: ContextTypes.DEFAULT_TYPE):
    await update.message.reply_text("🔍 Cek manual...")
    await poll_wallets(ctx.application, only_chat=update.effective_chat.id)
    await update.message.reply_text("Selesai.")


async def balance_cmd(update: Update, ctx: ContextTypes.DEFAULT_TYPE):
    if not ctx.args:
        await update.message.reply_text("Format: /balance <address>")
        return
    address = ctx.args[0]
    await update.message.reply_text("💰 Ambil saldo...")
    async with aiohttp.ClientSession() as session:
        if evm.is_evm_address(address):
            lines = [f"💰 *Saldo native* `{address[:8]}...{address[-6:]}`"]
            for ckey, cid in evm.CHAINS.items():
                try:
                    bal = await evm.fetch_native_balance(session, address, ETHERSCAN_KEY, cid)
                except Exception:  # noqa: BLE001
                    continue
                if bal > 0:
                    lines.append(f"• {ckey.upper()}: {bal:.6f} {evm.NATIVE_SYMBOL[ckey]}")
            if len(lines) == 1:
                lines.append("_Tidak ada saldo native di chain manapun._")
            await update.message.reply_text("\n".join(lines), parse_mode=ParseMode.MARKDOWN)
        elif solana.is_solana_address(address):
            bal = await solana.fetch_balance(session, SOLANA_RPC, address)
            await update.message.reply_text(
                f"💰 `{address[:6]}...{address[-6:]}`\n• SOL: {bal:.6f}",
                parse_mode=ParseMode.MARKDOWN)
        else:
            await update.message.reply_text("⚠️ Address tidak dikenali.")


async def token_cmd(update: Update, ctx: ContextTypes.DEFAULT_TYPE):
    args = ctx.args
    if len(args) < 2:
        await update.message.reply_text(
            "Format: /token <address> <contract> [chain]\n"
            "chain (EVM): eth, base, arb, op, bsc, polygon (default eth)")
        return
    address, contract = args[0], args[1]
    chain_arg = args[2].lower() if len(args) > 2 else "eth"
    await update.message.reply_text("🪙 Ambil saldo token...")
    async with aiohttp.ClientSession() as session:
        if evm.is_evm_address(address):
            cid = evm.CHAINS.get(chain_arg, 1)
            try:
                bal = await evm.fetch_token_balance(session, address, contract, ETHERSCAN_KEY, cid)
            except Exception as e:  # noqa: BLE001
                await update.message.reply_text(f"⚠️ Gagal: {e}")
                return
            await update.message.reply_text(
                f"🪙 Token `{contract[:8]}...{contract[-6:]}` @ {chain_arg.upper()}\n"
                f"👛 `{address[:8]}...{address[-6:]}`\n"
                f"Saldo: {bal:,.6f}",
                parse_mode=ParseMode.MARKDOWN)
        elif solana.is_solana_address(address):
            try:
                bal = await solana.fetch_token_balance(session, SOLANA_RPC, address, contract)
            except Exception as e:  # noqa: BLE001
                await update.message.reply_text(f"⚠️ Gagal: {e}")
                return
            await update.message.reply_text(
                f"🪙 Mint `{contract[:6]}...{contract[-4:]}`\n"
                f"👛 `{address[:6]}...{address[-6:]}`\n"
                f"Saldo: {bal:,.6f}",
                parse_mode=ParseMode.MARKDOWN)
        else:
            await update.message.reply_text("⚠️ Address tidak dikenali.")


# ---------- polling logic ----------

async def poll_wallets(app: Application, only_chat: int | None = None):
    rows = storage.all_wallets()
    if not rows:
        return
    async with aiohttp.ClientSession() as session:
        for r in rows:
            if only_chat is not None and r["chat_id"] != only_chat:
                continue
            try:
                await _check_one(session, app, r)
            except Exception as e:  # noqa: BLE001
                log.warning("Gagal cek wallet %s: %s", r["address"], e)


def _evm_key(kind: str, tx: dict) -> str:
    return f"{kind}:{tx['hash']}:{tx.get('contractAddress','')}:{tx.get('value','')}"


async def _check_evm_chain(session, app, r, ckey, chainid, last_marker, added_at):
    """Cek 1 chain EVM untuk sebuah wallet. Return marker terbaru (atau last_marker)."""
    address = r["address"]
    native = await evm.fetch_latest_txs(session, address, ETHERSCAN_KEY, chainid)
    tokens = await evm.fetch_latest_token_txs(session, address, ETHERSCAN_KEY, chainid)

    events = [("native", tx) for tx in native] + [("token", tx) for tx in tokens]
    events.sort(key=lambda e: int(e[1].get("timeStamp", "0")), reverse=True)
    if not events:
        return last_marker

    newest = _evm_key(*events[0])
    explorer = evm.EXPLORERS[ckey]
    symbol = evm.NATIVE_SYMBOL[ckey]

    fresh = []
    for ev in events:
        if last_marker and _evm_key(*ev) == last_marker:
            break
        if int(ev[1].get("timeStamp", "0")) > added_at:
            fresh.append(ev)

    for kind, tx in reversed(fresh):
        body = (evm.format_token_tx(tx, address, explorer) if kind == "token"
                else evm.format_tx(tx, address, explorer, symbol))
        msg = f"{_label(r)}⛓️ {ckey.upper()}\n{body}"
        await app.bot.send_message(r["chat_id"], msg, disable_web_page_preview=True)
    return newest


async def _check_one(session, app, r):
    chain = r["chain"]
    address = r["address"]
    last_seen = r["last_seen"]
    added_at = r["added_at"] or 0

    if chain.startswith("evm"):
        # last_seen disimpan sebagai JSON dict per-chain: {"eth": marker, ...}
        try:
            seen = json.loads(last_seen) if last_seen else {}
        except (ValueError, TypeError):
            seen = {}
        if not isinstance(seen, dict):
            seen = {}

        # legacy: row lama "evm:eth" cuma scan chain itu; row baru "evm" scan semua
        if ":" in chain:
            chains = {chain.split(":", 1)[1]: evm.CHAINS[chain.split(":", 1)[1]]}
        else:
            chains = evm.CHAINS

        for ckey, cid in chains.items():
            try:
                seen[ckey] = await _check_evm_chain(
                    session, app, r, ckey, cid, seen.get(ckey), added_at)
            except Exception as e:  # noqa: BLE001
                log.warning("EVM %s %s gagal: %s", ckey, address, e)
        storage.set_last_seen(r["id"], json.dumps(seen))

    elif chain == "solana":
        sigs = await solana.fetch_latest_signatures(session, SOLANA_RPC, address)
        if not sigs:
            return
        newest = sigs[0]["signature"]
        fresh = []
        for s in sigs:
            if last_seen and s["signature"] == last_seen:
                break
            if (s.get("blockTime") or 0) > added_at:
                fresh.append(s)
        for s in reversed(fresh):
            detail = await solana.fetch_transaction(session, SOLANA_RPC, s["signature"])
            changes = solana.extract_token_changes(detail, address)
            if changes:
                msg = _label(r) + solana.format_token_change(s["signature"], address, changes)
            else:
                msg = _label(r) + solana.format_sig(s, address)
            await app.bot.send_message(r["chat_id"], msg, disable_web_page_preview=True)
        storage.set_last_seen(r["id"], newest)


def _label(r) -> str:
    return f"🔔 *{r['label']}*\n" if r["label"] else "🔔 Transaksi baru\n"


async def poll_job(ctx: ContextTypes.DEFAULT_TYPE):
    await poll_wallets(ctx.application)


# ---------- bootstrap ----------

def main():
    storage.init_db()
    app = Application.builder().token(TOKEN).build()

    app.add_handler(CommandHandler("start", start))
    app.add_handler(CommandHandler("help", start))
    app.add_handler(CommandHandler("add", add))
    app.add_handler(CommandHandler("remove", remove))
    app.add_handler(CommandHandler("list", list_cmd))
    app.add_handler(CommandHandler("check", check_cmd))
    app.add_handler(CommandHandler("balance", balance_cmd))
    app.add_handler(CommandHandler("token", token_cmd))

    app.job_queue.run_repeating(poll_job, interval=POLL_INTERVAL, first=10)

    log.info("Bot jalan. Polling tiap %ss", POLL_INTERVAL)
    app.run_polling(allowed_updates=Update.ALL_TYPES)


if __name__ == "__main__":
    main()
