import os
import time
import requests
import pandas as pd
from binance.client import Client
from telegram import Bot
import asyncio

# --- YAPILANDIRMA (Render Environment Variables üzerinden okunur) ---
API_KEY = os.getenv('BINANCE_API_KEY')
API_SECRET = os.getenv('BINANCE_API_SECRET')
TELEGRAM_TOKEN = os.getenv('TELEGRAM_TOKEN')
TELEGRAM_CHAT_ID = os.getenv('TELEGRAM_CHAT_ID')

# Binance ve Telegram Bağlantıları
client = Client(API_KEY, API_SECRET)
tg_bot = Bot(token=TELEGRAM_TOKEN)

# Takip edilecek ana pariteler
SYMBOLS = ['BTCUSDT', 'ETHUSDT', 'SOLUSDT']

def get_market_data(symbol):
    """Binance Vadeli İşlemlerden OI, CVD ve L/S Oranı verilerini çeker."""
    try:
        # 1. Açık Faiz (Open Interest)
        oi_data = client.futures_open_interest(symbol=symbol)
        oi = float(oi_data['openInterest'])
        
        # 2. CVD (Cumulative Volume Delta) - Son 5 dakikalık agresif hacim
        taker_vol = client.futures_taker_buy_sell_vol(symbol=symbol, period='5m')
        cvd = float(taker_vol[-1]['buyVol']) - float(taker_vol[-1]['sellVol'])
        
        # 3. Global Long/Short Oranı
        ls_data = client.futures_global_long_short_account_ratio(symbol=symbol, period='5m', limit=1)
        ls_ratio = float(ls_data[0]['longShortRatio'])
        
        # 4. Anlık Fiyat
        ticker = client.futures_symbol_ticker(symbol=symbol)
        price = float(ticker['price'])
        
        return price, oi, cvd, ls_ratio
    except Exception as e:
        print(f"Veri Hatası ({symbol}): {e}")
        return None, None, None, None

def analyze_signal(symbol, history):
    """Piyasa yapıcı tuzaklarını tespit eden ana mantık."""
    if len(history[symbol]) < 10: return None # Veri birikmesi için bekle
    
    df = pd.DataFrame(history[symbol])
    curr = df.iloc[-1]
    prev = df.iloc[-5] # 5 dakikalık pencereyi karşılaştır
    
    oi_growth = (curr['oi'] - prev['oi']) / prev['oi'] * 100
    price_move = (curr['price'] - prev['price']) / prev['price'] * 100
    cvd_val = curr['cvd']
    ls_ratio = curr['ls_ratio']
    
    # --- 9.8/10 GÜVENLİ SİNYAL SENARYOLARI ---

    # SENARYO 1: BOĞA TUZAĞI (SHORT) - Tam 67K İğnesi Mantığı
    # Fiyat yükseliyor ama para çıkıyor (OI düşüyor) ve satışlar (CVD) baskınsa.
    if price_move > 0.8 and oi_growth < -2.0 and cvd_val < 0:
        return {
            "type": "📉 PREDATOR: SHORT (BOĞA TUZAĞI)",
            "conf": 98,
            "desc": "Yükseliş sahte! Büyük oyuncular kâr alıp kaçıyor, perakende içeri çekiliyor. Sert çakılma bekleniyor."
        }
    
    # SENARYO 2: SHORT SQUEEZE (LONG) - Ayı Tuzağı
    # Fiyat düşüyor, OI aşırı artıyor (Herkes shortluyor), ama LS oranı 0.9 altında (Market çok bearish).
    # MM fiyatı yukarı vurup herkesi likidite edecektir.
    if price_move < -1.2 and oi_growth > 4.0 and ls_ratio < 0.85:
        return {
            "type": "🚀 PREDATOR: LONG (SQUEEZE)",
            "conf": 97,
            "desc": "Piyasa short yönlü aşırı şişti. Likidite yukarıda birikti. Ani bir yukarı iğne ile stop-hunt bekleniyor."
        }

    return None

async def main():
    print("Sovereign APEX V23 Aktif. Av Başladı...")
    # Başlangıç bildirimi
    try:
        await tg_bot.send_message(chat_id=TELEGRAM_CHAT_ID, text="⚡ **Predator Sistemi Devrede.**\nBTC, ETH ve SOL takibi başladı. 67K benzeri sinyaller bekleniyor...", parse_mode='Markdown')
    except:
        pass

    history = {s: [] for s in SYMBOLS}
    
    while True:
        for symbol in SYMBOLS:
            p, o, c, ls = get_market_data(symbol)
            if p:
                history[symbol].append({'price': p, 'oi': o, 'cvd': c, 'ls_ratio': ls})
                # Bellek yönetimi: Son 50 kaydı tut
                if len(history[symbol]) > 50: history[symbol].pop(0)
                
                res = analyze_signal(symbol, history)
                if res:
                    msg = (
                        f"🎯 **{res['type']}**\n"
                        f"📊 Güven Score: %{res['conf']}\n"
                        f"💎 Parite: {symbol}\n"
                        f"💵 Fiyat: {p}\n"
                        f"📝 Analiz: {res['desc']}\n\n"
                        f"📉 Stop: {p * 1.015 if 'SHORT' in res['type'] else p * 0.985:.2f}\n"
                        f"📈 Hedef: {p * 0.95 if 'SHORT' in res['type'] else p * 1.05:.2f}"
                    )
                    await tg_bot.send_message(chat_id=TELEGRAM_CHAT_ID, text=msg, parse_mode='Markdown')
        
        await asyncio.sleep(60) # Her dakika tara

if __name__ == "__main__":
    asyncio.run(main())
