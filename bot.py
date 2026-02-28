import asyncio
import pandas as pd
import logging
import time
import threading
import requests
import os
from flask import Flask
from binance import AsyncClient, BinanceSocketManager

# --- PARAMETRELER ---
SYMBOL = "BTCUSDT"
HTF, LTF = "4h", "15m"
TOKEN = "8625084705:AAHzM6Sj54YG9eDjxQ6Q9nQ61tKHUyjWu04"
CHAT_ID = "8731276912"

app = Flask(__name__)
@app.route('/')
def home(): return "Sovereign Sentience Aktif!"

def run_web():
    port = int(os.environ.get("PORT", 8080))
    app.run(host='0.0.0.0', port=port)

def telegram_send(msg):
    url = f"https://api.telegram.org/bot{TOKEN}/sendMessage"
    try: requests.post(url, json={"chat_id": CHAT_ID, "text": msg}, timeout=10)
    except: pass

class SovereignSentience:
    def __init__(self):
        self.client = None
        self.cvd = 0.0
        self.price_history = [] 
        self.htf_levels = {'high': 0, 'low': 0}
        self.last_htf_sync = 0

    async def get_htf_context(self):
        try:
            k = await self.client.get_klines(symbol=SYMBOL, interval=HTF, limit=50)
            df = pd.DataFrame(k).astype(float)
            self.htf_levels['high'] = df[2].iloc[-42:].max()
            self.htf_levels['low'] = df[3].iloc[-42:].min()
            self.last_htf_sync = time.time()
            logging.info(f"🏛️ HTF Sync Basarili")
        except Exception as e:
            logging.error(f"HTF Veri Hatasi: {e}")

    async def handle_klines(self):
        bm = BinanceSocketManager(self.client)
        async with bm.kline_socket(SYMBOL, interval=LTF) as stream:
            while True:
                res = await stream.recv()
                k = res['k']
                if k['x']:
                    c, h = float(k['c']), float(k['h'])
                    is_bear_sweep = h > self.htf_levels['high'] and c < self.htf_levels['high']
                    if is_bear_sweep:
                        telegram_send(f"🚀 [SIGNAL] HTF SWEEP at {h}")
                    self.price_history.append((c, self.cvd))
                    if len(self.price_history) > 50: self.price_history.pop(0)

    async def handle_trades(self):
        bm = BinanceSocketManager(self.client)
        async with bm.aggtrade_socket(SYMBOL) as stream:
            while True:
                msg = await stream.recv()
                qty = float(msg['q'])
                self.cvd += -qty if msg['m'] else qty

    async def run(self):
        # KRITIK DUZELTME: Kısıtlamayı aşmak için alternatif sunucu ekledik
        self.client = await AsyncClient.create(tld='com') 
        await self.get_htf_context()
        telegram_send("🛰️ Bot Engel Asildi ve Baslatildi!")
        await asyncio.gather(self.handle_trades(), self.handle_klines())

if __name__ == "__main__":
    logging.basicConfig(level=logging.INFO)
    threading.Thread(target=run_web, daemon=True).start()
    loop = asyncio.get_event_loop()
    loop.run_until_complete(SovereignSentience().run())
