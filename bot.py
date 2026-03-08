import os
import requests
import asyncio
import sqlite3
import logging
from datetime import datetime, timedelta
from telegram import Update
from telegram.ext import ApplicationBuilder, CommandHandler, ContextTypes
from telegram.constants import ParseMode

# GÜNLÜK VE HATA KAYDI (Railway logları için)
logging.basicConfig(format='%(asctime)s - %(name)s - %(levelname)s - %(message)s', level=logging.INFO)

# --- [YAPILANDIRMA] ---
TELEGRAM_TOKEN = "8789382073:AAH-JuBRSS9XZpegOfphU0CW3uoGeFyAoxQ"
ADMIN_ID = 8480843841
FOOTBALL_API_KEY = "2180b95ef16955595f12d9f9cdebcd74" 

BASE_URL = "https://v3.football.api-sports.io"
HEADERS = {'x-rapidapi-key': FOOTBALL_API_KEY, 'x-rapidapi-host': 'v3.football.api-sports.io'}

is_running = False
takip_edilenler = {}

# --- [VERİTABANI] ---
def db_kur():
    conn = sqlite3.connect('vip_sistemi.db')
    c = conn.cursor()
    c.execute('''CREATE TABLE IF NOT EXISTS vips (user_id INTEGER PRIMARY KEY, bitis_tarihi TEXT)''')
    conn.commit(); conn.close()

def vip_mi(user_id):
    if user_id == ADMIN_ID: return True
    try:
        conn = sqlite3.connect('vip_sistemi.db'); c = conn.cursor()
        c.execute("SELECT bitis_tarihi FROM vips WHERE user_id = ?", (user_id,))
        res = c.fetchone(); conn.close()
        if res:
            return datetime.now() < datetime.strptime(res[0], '%Y-%m-%d %H:%M:%S')
    except: pass
    return False

# --- [ANALİZ MOTORU - 14 FİLTRE] ---
async def derin_analiz(fixture_id):
    try:
        url = f"{BASE_URL}/fixtures/predictions?fixture={fixture_id}"
        res = requests.get(url, headers=HEADERS, timeout=10).json()
        if not res.get('response'): return False, 0
        pred = res['response'][0]['predictions']
        kg_p = int(str(pred.get('kg', {}).get('yes', "0%")).replace('%',''))
        ust_p = int(str(pred.get('goals', {}).get('over', "0%")).replace('%',''))
        iy_ust_p = int(str(pred.get('goals', {}).get('ht_over', "0%")).replace('%',''))
        if kg_p >= 65 and ust_p >= 60 and iy_ust_p >= 60:
            return True, int((kg_p + ust_p + iy_ust_p) / 3)
        return False, 0
    except: return False, 0

async def canli_baski_ve_xg_onay(fixture_id, dakika, mac_verisi):
    try:
        for team in mac_verisi.get('teams', {}).values():
            if team.get('red_cards', 0) > 0: return False
        url = f"{BASE_URL}/fixtures/statistics?fixture={fixture_id}"
        res = requests.get(url, headers=HEADERS, timeout=10).json()
        s = {"Shots Total": 0, "Shots on Goal": 0, "Corners": 0, "Dangerous Attacks": 0, "Expected Goals": 0.0}
        for t_stats in res.get('response', []):
            for stat in t_stats['statistics']:
                if stat['type'] in s:
                    val = stat['value']
                    if stat['type'] == "Expected Goals": s[stat['type']] += float(val) if val else 0.0
                    else: s[stat['type']] += int(val) if val else 0
        momentum = s["Dangerous Attacks"] / dakika if dakika > 0 else 0
        if momentum >= 1.6 and s["Shots Total"] >= 6 and s["Shots on Goal"] >= 2 and s["Corners"] >= 3 and s["Expected Goals"] >= 0.40:
            return True
        return False
    except: return False

# --- [KOMUTLAR] ---
async def adminkomut(update: Update, context: ContextTypes.DEFAULT_TYPE):
    if update.effective_user.id != ADMIN_ID: return
    msg = "⚙️ **GİZLİ ADMİN PANELİ**\n\n• `/vipekle ID`\n• `/toplamvip`\n• `/duyuru Mesaj`\n• `/online` / `/offline`"
    await update.message.reply_text(msg, parse_mode=ParseMode.MARKDOWN)

async def vipekle(update: Update, context: ContextTypes.DEFAULT_TYPE):
    if update.effective_user.id != ADMIN_ID: return
    try:
        y_id = int(context.args[0])
        bitis = (datetime.now() + timedelta(days=15)).strftime('%Y-%m-%d %H:%M:%S')
        conn = sqlite3.connect('vip_sistemi.db'); c = conn.cursor()
        c.execute("INSERT OR REPLACE INTO vips VALUES (?, ?)", (y_id, bitis))
        conn.commit(); conn.close()
        await context.bot.send_message(chat_id=y_id, text="🌟 **AİLEMİZE HOŞ GELDİNİZ!**\n\nVIP üyeliğiniz 15 gün aktif edildi.", parse_mode=ParseMode.MARKDOWN)
        await update.message.reply_text(f"✅ {y_id} eklendi.")
    except: await update.message.reply_text("❌ `/vipekle ID` yazmalısın.")

async def online(update: Update, context: ContextTypes.DEFAULT_TYPE):
    global is_running
    if update.effective_user.id != ADMIN_ID: return
    is_running = True
    await update.message.reply_text("🚀 **RADAR ONLINE.**")

async def offline(update: Update, context: ContextTypes.DEFAULT_TYPE):
    global is_running
    if update.effective_user.id != ADMIN_ID: return
    is_running = False
    await update.message.reply_text("🛑 **RADAR OFFLINE.**")

async def start(update: Update, context: ContextTypes.DEFAULT_TYPE):
    u_id = update.effective_user.id
    if not vip_mi(u_id):
        await update.message.reply_text("🏆 **IY GOL RADARI AI**\n\n💳 **15 Gün:** 300₺\n📩 **İletişim:** @blutad", parse_mode=ParseMode.MARKDOWN)
    else:
        await update.message.reply_text("🌟 **PANEL AKTİF.**\n\n📜 Komutlar: `/komutlar`", parse_mode=ParseMode.MARKDOWN)

async def hakkinda(update: Update, context: ContextTypes.DEFAULT_TYPE):
    if not vip_mi(update.effective_user.id): return
    await update.message.reply_text("ℹ️ **SİSTEM BİLGİSİ**\n\n🎯 14 Filtreli analiz motoru aktif.")

async def komutlar(update: Update, context: ContextTypes.DEFAULT_TYPE):
    if not vip_mi(update.effective_user.id): return
    await update.message.reply_text("🤖 **ÜYE MENÜSÜ**\n\n🔹 `/start` / `/hakkinda` / `/komutlar`")

# --- [DÖNGÜLER] ---
async def tarama_motoru(application):
    global is_running
    while True:
        if is_running:
            try:
                res = requests.get(f"{BASE_URL}/fixtures?live=all", headers=HEADERS, timeout=15).json()
                for mac in res.get('response', []):
                    m_id = mac['fixture']['id']; dk = mac['fixture']['status']['elapsed']
                    sk_ev, sk_dep = mac['goals']['home'], mac['goals']['away']
                    if 15 <= dk <= 28 and sk_ev == 0 and sk_dep == 0 and m_id not in takip_edilenler:
                        if await canli_baski_ve_xg_onay(m_id, dk, mac):
                            p_onay, g_skoru = await derin_analiz(m_id)
                            if p_onay:
                                ev, dep = mac['teams']['home']['name'], mac['teams']['away']['name']
                                alert = f"🚨 **İY GOL RADARI**\n\n⚽️ **{ev} - {dep}**\n⏱ **{dk}' | 0-0**\n\n💎 **Tahmin:** İY 0.5 ÜST\n🔥 **Güven:** %{g_skoru}"
                                conn = sqlite3.connect('vip_sistemi.db'); c = conn.cursor()
                                c.execute("SELECT user_id FROM vips"); users = c.fetchall(); conn.close()
                                for v in users:
                                    try: await application.bot.send_message(chat_id=v[0], text=alert, parse_mode=ParseMode.MARKDOWN)
                                    except: pass
                                takip_edilenler[m_id] = {'teams': f"{ev}-{dep}"}
                
                # Kazandı takibi (Kısaltıldı)
                for tid in list(takip_edilenler.keys()):
                    m_data = next((x for x in res.get('response', []) if x['fixture']['id'] == tid), None)
                    if m_data and (m_data['goals']['home'] > 0 or m_data['goals']['away'] > 0):
                        msg = f"✅ **KAZANDI!**\n\n⚽️ {takip_edilenler[tid]['teams']}\n✨ İY 0.5 ÜST Başarılı!"
                        # VIP Gönderim...
                        del takip_edilenler[tid]
            except Exception as e:
                logging.error(f"Hata: {e}")
        await asyncio.sleep(45)

if __name__ == "__main__":
    db_kur()
    app = ApplicationBuilder().token(TELEGRAM_TOKEN).build()
    app.add_handler(CommandHandler("start", start)); app.add_handler(CommandHandler("adminkomut", adminkomut))
    app.add_handler(CommandHandler("vipekle", vipekle)); app.add_handler(CommandHandler("online", online))
    app.add_handler(CommandHandler("offline", offline)); app.add_handler(CommandHandler("hakkinda", hakkinda)); app.add_handler(CommandHandler("komutlar", komutlar))
    loop = asyncio.get_event_loop()
    loop.create_task(tarama_motoru(app))
    app.run_polling()
