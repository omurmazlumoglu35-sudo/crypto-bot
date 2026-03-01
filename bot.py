import os, asyncio, numpy as np, threading
from binance import AsyncClient, BinanceSocketManager
from telegram import Bot
from flask import Flask

# --- RENDER KEEPALIVE ENGINE ---
# Render'ın "Port bindi" hatası verip botu kapatmasını engeller.
app = Flask(__name__)

@app.route('/')
def health_check():
    return "Sovereign Apex is Online", 200

def run_web_server():
    # Render'ın verdiği portu (10000) otomatik yakalar
    port = int(os.environ.get("PORT", 10000))
    app.run(host="0.0.0.0", port=port)

# Web sunucusunu ayrı bir kolda (Thread) başlat
threading.Thread(target=run_web_server, daemon=True).start()

# --- BOT AYARLARI ---
WATCHLIST = ['BTCUSDT', 'SOLUSDT', 'ETHUSDT']
LEVERAGE = 20
RISK_PER_TRADE_PCT = 0.02
FUNDING_THRESHOLD = 0.00025
OI_Z_SCORE_THRESHOLD = 2.0 
BREAKEVEN_TRIGGER = 1.5
RISK_REWARD = 2.5

class SovereignApexFinal:
    def __init__(self):
        self.bot = Bot(token=os.getenv('TELEGRAM_BOT_TOKEN'))
        self.chat_id = os.getenv('TELEGRAM_CHAT_ID')
        self.client = None
        self.state = {s: {
            'm1_klines': [], 'm5_klines': [], 'm15_klines': [],
            'oi_history': [], 'current_cvd': 0, 'cvd_history': [],
            'funding': 0, 'active_trade': False, 'entry_price': 0, 'sl_order_id': None
        } for s in WATCHLIST}

    # (Buraya daha önceki V20 fonksiyonlarını ekle: get_oi_z_score, execute_apex_short, process_logic, sync_data)
    # Kodun geri kalan tüm mantığı V20 ile aynı kalmalı.

    async def launch(self):
        while True:
            try:
                # API Kontrol
                api_key = os.getenv('BINANCE_API_KEY')
                api_secret = os.getenv('BINANCE_API_SECRET')
                
                if not api_key:
                    print("❌ HATA: BINANCE_API_KEY eksik!")
                    await asyncio.sleep(60)
                    continue

                self.client = await AsyncClient.create(api_key, api_secret)
                
                # Initial Data Fill
                for s in WATCHLIST:
                    for tf, key in [('1m', 'm1_klines'), ('5m', 'm5_klines'), ('15m', 'm15_klines')]:
                        k = await self.client.futures_historical_klines(s, tf, '200m ago UTC')
                        self.state[s][key] = [{'h':float(i[2]), 'l':float(i[3]), 'c':float(i[4]), 'o':float(i[1])} for i in k]
                    
                    # OI Z-Score için başlangıç verisi
                    oi_init = await self.client.futures_open_interest(symbol=s)
                    self.state[s]['oi_history'] = [float(oi_init['openInterest'])] * 20

                asyncio.create_task(self.sync_data())
                
                bsm = BinanceSocketManager(self.client)
                streams = [f"{s.lower()}@kline_{tf}" for s in WATCHLIST for tf in ['1m', '5m', '15m']] + \
                          [f"{s.lower()}@aggTrade" for s in WATCHLIST]
                
                async with bsm.multiplex_socket(streams) as ms:
                    print("🦅 Sovereign APEX: Frankfurt Borsasına Bağlanıldı. Pusu Başladı.")
                    await self.bot.send_message(self.chat_id, "🚀 Bot Başarıyla Başlatıldı. 7/24 Gözlem Aktif.")
                    while True:
                        res = await ms.recv()
                        await self.process_socket(res) # Bu fonksiyonu V20'den al
            except Exception as e:
                print(f"⚠️ Reconnect hatası: {e}")
                await asyncio.sleep(5)
            finally:
                if self.client: await self.client.close_connection()

if __name__ == "__main__":
    asyncio.run(SovereignApexFinal().launch())
