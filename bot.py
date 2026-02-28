import asyncio, logging, time, requests, os, pandas as pd
from binance import AsyncClient, BinanceSocketManager
from flask import Flask
from threading import Thread

# --- AYARLAR ---
SYMBOL, HTF, LTF = "BTCUSDT", "4h", "15m"
TG_TOKEN = "8625084705:AAHzM6Sj54YG9eDjxQ6Q9nQ61tKHUyjWu04"
TG_CHAT_ID = "8731276912"

app = Flask('')
@app.route('/')
def home(): return "Bot Aktif!"

def run_web():
    app.run(host='0.0.0.0', port=int(os.environ.get("PORT", 8080)))

class SovereignIronclad:
    def __init__(self):
        self.client = None
        self.htf_high = 0.0

    def send_tg(self, msg):
        url = f"https://api.telegram.org/bot{TG_TOKEN}/sendMessage"
        try: requests.post(url, data={"chat_id": TG_CHAT_ID, "text": msg, "parse_mode": "Markdown"}, timeout=10)
        except: pass

    async def sync_htf(self):
        try:
            k = await self.client.get_klines(symbol=SYMBOL, interval=HTF, limit=100)
            self.htf_high = float(pd.DataFrame(k)[2].iloc[-48:].max())
            logging.info(f"🏛️ Baglanti Basarili! HTF High: {self.htf_high}")
            self.send_tg("🚀 Bot Render'da Baslatildi!")
        except Exception as e: logging.error(f"Hata: {e}")

    async def run(self):
        self.client = await AsyncClient.create()
        await self.sync_htf()
        bm = BinanceSocketManager(self.client)
        async with bm.kline_socket(SYMBOL, interval=LTF) as stream:
            while True:
                res = await stream.recv()
                if res['k']['x']: logging.info("Mum kapandi, taraniyor...")

if __name__ == "__main__":
    logging.basicConfig(level=logging.INFO)
    Thread(target=run_web).start()
    asyncio.run(SovereignIronclad().run())
