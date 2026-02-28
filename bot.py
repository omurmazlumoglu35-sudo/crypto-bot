import asyncio, pandas as pd, requests, os, threading
from flask import Flask
from binance import AsyncClient, BinanceSocketManager

# --- MASTER CONFIG ---
SYMBOL, HTF, LTF = "BTCUSDT", "4h", "15m"
TOKEN, CHAT_ID = "8625084705:AAHzM6Sj54YG9eDjxQ6Q9nQ61tKHUyjWu04", "8731276912"

app = Flask(__name__)
@app.route('/')
def home(): return "Sovereign Sentience: Master Neural Node Active."

def telegram_send(msg):
    try: requests.post(f"https://api.telegram.org/bot{TOKEN}/sendMessage", 
                     json={"chat_id": CHAT_ID, "text": msg, "parse_mode": "Markdown"}, timeout=10)
    except: pass

class SovereignSentience:
    def __init__(self):
        self.client, self.cvd = None, 0.0
        self.price_history, self.htf_levels = [], {'h': 0, 'l': 0, 'atr': 0}
        self.cvd_buffer = []

    async def sync_market_intelligence(self):
        """HTF Likidite ve Volatilite Senkronizasyonu"""
        k = await self.client.get_klines(symbol=SYMBOL, interval=HTF, limit=100)
        df = pd.DataFrame(k).astype(float)
        self.htf_levels['h'] = df[2].iloc[-50:].max()
        self.htf_levels['l'] = df[3].iloc[-50:].min()
        self.htf_levels['atr'] = (df[2] - df[3]).tail(14).mean()

    def analyze_order_flow(self, current_price, side="SHORT"):
        """Delta Absorption ve Divergence Kontrolü"""
        if len(self.cvd_buffer) < 10: return False
        delta_vel = self.cvd_buffer[-1] - self.cvd_buffer[-5]
        if side == "SHORT":
            return delta_vel <= 0 
        return delta_vel >= 0 

    async def handle_market_data(self):
        bm = BinanceSocketManager(self.client)
        async with bm.kline_socket(SYMBOL, interval=LTF) as stream:
            while True:
                res = await stream.recv()
                k = res['k']
                if k['x']:
                    c, h, l, o = float(k['c']), float(k['h']), float(k['l']), float(k['o'])
                    # SFP, Wick Rejection ve Order Flow Onayı
                    if h > self.htf_levels['h'] and c < self.htf_levels['h'] and self.analyze_order_flow(h, "SHORT"):
                        self.fire_protocol("SHORT", c, h)
                    elif l < self.htf_levels['l'] and c > self.htf_levels['l'] and self.analyze_order_flow(l, "LONG"):
                        self.fire_protocol("LONG", c, l)
                    self.price_history.append((c, self.cvd))

    def fire_protocol(self, side, entry, extreme):
        """Dinamik Risk ve Trade Planı"""
        sl = extreme + (self.htf_levels['atr'] * 0.1) if side == "SHORT" else extreme - (self.htf_levels['atr'] * 0.1)
        risk = abs(entry - sl)
        tp = entry - (risk * 3) if side == "SHORT" else entry + (risk * 3)
        msg = (f"🦅 *SOVEREIGN {side} SETUP*\n\n"
               f"📍 Entry: `{entry:.2f}`\n"
               f"🛡️ SL: `{sl:.2f}`\n"
               f"🎯 TP (3R): `{tp:.2f}`\n\n"
               f"🧠 AI: Liquidity Grab + CVD Absorption Sync")
        telegram_send(msg)

    async def track_cvd(self):
        bm = BinanceSocketManager(self.client)
        async with bm.aggtrade_socket(SYMBOL) as stream:
            while True:
                m = await stream.recv()
                self.cvd += -float(m['q']) if m['m'] else float(m['q'])
                self.cvd_buffer.append(self.cvd)
                if len(self.cvd_buffer) > 50: self.cvd_buffer.pop(0)

    async def start(self):
        self.client = await AsyncClient.create(tld='com')
        await self.sync_market_intelligence()
        telegram_send("🛡️ *Sovereign Sentience Master AI* Aktif.\nNode: Frankfurt/EU Central.")
        await asyncio.gather(self.track_cvd(), self.handle_market_data())

if __name__ == "__main__":
    threading.Thread(target=lambda: app.run(host='0.0.0.0', port=int(os.environ.get("PORT", 8080))), daemon=True).start()
    asyncio.run(SovereignSentience().start())
