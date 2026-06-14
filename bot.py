"""
Telegram Wallet Tracker Bot — support EVM + Solana.

Cara pakai:
  /start                          -> info bot
  /add <chain> <address> [label]  -> tambah wallet
       chain EVM: eth | base | arb | op | bsc | polygon
       chain Solana: sol
  /list                           -> lihat wallet yang di-track
  /remove <address>               -> hapus wallet
  /check                          -> cek manual sekarang

Bot otomatis polling tiap POLL_INTERVAL detik dan kirim notif kalau ada tx baru.
"""
import os
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
        "Aku pantau wallet EVM & Solana dan kabarin kalau ada transaksi baru.\n\n"
        "*Perintah:*\n"
        "`/add <chain> <address> [label]`\n"
        "  chain EVM: eth, base, arb, op, bsc, polygon\n"
        "  chain Solana: sol\n"
        "`/list` — lihat wallet\n"
        "`/remove <address>` — hapus wallet\n"
        "`/check` — cek manual sekarang\n\n"
        "Contoh:\n"
        "`/add eth 0xd8dA6BF26964aF9D7eEd9e03E53415D37aA96045 vitalik`\n"
        "`/add sol 5tzFkiKscXHK5ZXCGbXZxdw7gTjjD1mBwuoFbhUvuAi9 usdc`",
        parse_mode=ParseMode.MARKDOWN,
    )


async def add(update: Update, ctx: ContextTypes.DEFAULT_TYPE):
    args = ctx.args
    if len(args) < 2:
        await update.message.reply_text("Format: /add <chain> <address> [label]")
        return

    chain_arg = args[0].lower()
    address = args[1]
    label = " ".join(args[2:]) if len(args) > 2 else None
    chat_id = update.effective_chat.id

    if chain_arg == "sol":
        if not solana.is_solana_address(address):
            await update.message.reply_text("⚠️ Address Solana tidak valid.")
            return
        chain = "solana"
    elif chain_arg in evm.CHAINS:
        if not evm.is_evm_address(address):
            await update.message.reply_text("⚠️ Address EVM tidak valid (harus 0x...).")
            return
        chain = f"evm:{chain_arg}"
    else:
        await update.message.reply_text(
            "⚠️ Chain tidak dikenal. Pilih: eth, base, arb, op, bsc, polygon, sol"
        )
        return

    ok = storage.add_wallet(chat_id, chain, address, label)
    if ok:
        tag = f" ({label})" if label else ""
        await update.message.reply_text(f"✅ Tracking {chain_arg}: `{address}`{tag}",
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
        lines.append(f"• `{r['chain']}` {r['address'][:10]}...{r['address'][-6:]}{tag}")
    await update.message.reply_text("*Wallet di-track:*\n" + "\n".join(lines),
                                    parse_mode=ParseMode.MARKDOWN)


async def check_cmd(update: Update, ctx: ContextTypes.DEFAULT_TYPE):
    await update.message.reply_text("🔍 Cek manual...")
    await poll_wallets(ctx.application, only_chat=update.effective_chat.id)
    await update.message.reply_text("Selesai.")


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


async def _check_one(session, app, r):
    chain = r["chain"]
    address = r["address"]
    last_seen = r["last_seen"]

    if chain.startswith("evm:"):
        chain_key = chain.split(":", 1)[1]
        chainid = evm.CHAINS[chain_key]
        native = await evm.fetch_latest_txs(session, address, ETHERSCAN_KEY, chainid)
        tokens = await evm.fetch_latest_token_txs(session, address, ETHERSCAN_KEY, chainid)

        # gabung native + token jadi satu timeline, urut terbaru dulu
        events = []
        for tx in native:
            events.append(("native", tx))
        for tx in tokens:
            events.append(("token", tx))
        events.sort(key=lambda e: int(e[1].get("blockNumber", "0")), reverse=True)
        if not events:
            return

        def _key(ev):
            kind, tx = ev
            return f"{kind}:{tx['hash']}:{tx.get('contractAddress','')}:{tx.get('value','')}"

        newest = _key(events[0])
        if last_seen is None:
            storage.set_last_seen(r["id"], newest)  # baseline, jangan spam histori
            return
        fresh = []
        for ev in events:
            if _key(ev) == last_seen:
                break
            fresh.append(ev)
        for kind, tx in reversed(fresh):
            if kind == "token":
                body = evm.format_token_tx(tx, address)
            else:
                body = evm.format_tx(tx, address)
            await app.bot.send_message(r["chat_id"], _label(r) + body,
                                       disable_web_page_preview=True)
        storage.set_last_seen(r["id"], newest)

    elif chain == "solana":
        sigs = await solana.fetch_latest_signatures(session, SOLANA_RPC, address)
        if not sigs:
            return
        newest = sigs[0]["signature"]
        if last_seen is None:
            storage.set_last_seen(r["id"], newest)
            return
        fresh = []
        for s in sigs:
            if s["signature"] == last_seen:
                break
            fresh.append(s)
        for s in reversed(fresh):
            # coba ambil detail token transfer; fallback ke notif generic
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

    app.job_queue.run_repeating(poll_job, interval=POLL_INTERVAL, first=10)

    log.info("Bot jalan. Polling tiap %ss", POLL_INTERVAL)
    app.run_polling(allowed_updates=Update.ALL_TYPES)


if __name__ == "__main__":
    main()
