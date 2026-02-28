import asyncio, pandas as pd, requests, os, threading, numpy as np
from flask import Flask
from binance import AsyncClient, BinanceSocketManager

# --- SOVEREIGN SENTIENCE ALPHA CONFIG ---
SYMBOL, HTF, LTF = "BTCUSDT", "4h", "15m"
TOKEN, CHAT_ID = "8625084705:AAHzM6Sj54YG9eDjxQ6Q9nQ61tKHUyjWu04", "8731276912"

app = Flask(__name__)
@app.route('/')
def home(): return "Sovereign Sentience: Neural Execution Node Online."

def telegram_send(msg):
    try: requests.post(f"https://api.telegram.org/bot{TOKEN}/sendMessage", 
                     json={"chat_id": CHAT_ID, "text": msg, "parse_mode": "Markdown"}, timeout=10)
    except: pass

class SovereignSentience:
    def __init__(self):
        self.client, self.cvd = None, 0.0
        self.price_history = [] 
        self.htf_levels = {'h': 0, 'l': 0, 'atr': 0}
        self.cvd_buffer = []

    async def sync_intelligence(self):
        """Likidite Havuzlarını ve Piyasa Volatilitesini Senkronize Eder"""
        k = await self.client.get_klines(symbol=SYMBOL, interval=HTF, limit=100)
        df = pd.DataFrame(k).astype(float)
        self.htf_levels['h'] = df[2].iloc[-50:].max()
        self.htf_levels['l'] = df[3].iloc[-50:].min()
        # ATR bazlı dinamik volatilite ölçümü
        self.htf_levels['atr'] = (df[2] - df[3]).tail(14).mean()

    def analyze_order_flow(self, current_price, side="SHORT"):
        """Delta Divergence & Absorption Analizi"""
        if len(self.cvd_buffer) < 10: return False
        
        delta_velocity = self.cvd_buffer[-1] - self.cvd_buffer[-5]
        price_velocity = current_price - self.price_history[-5][0] if self.price_history else 0
        
        if side == "SHORT":
            # Fiyat yükseliyor ama agresif alıcılar (Delta) azalıyor veya negatif: ABSORPTION!
            return price_velocity > 0 and delta_velocity <= 0
        else:
            # Fiyat düşüyor ama agresif satıcılar azalıyor: ACCUMULATION!
            return price_velocity < 0 and delta_velocity >= 0

    async def handle_klines(self):
        bm = BinanceSocketManager(self.client)
        async with bm.kline_socket(SYMBOL, interval=LTF) as stream:
            while True:
                res = await stream.recv()
                k = res['k']
                if k['x']: # Mum kapandığında 5 AI Motoru karar verir
                    c, h, l, o = float(k['c']), float(k['h']), float(k['l']), float(k['o'])
                    
                    # 1. Kontrol: Liquidity Sweep (SFP)
                    is_bear_sweep = h > self.htf_levels['h'] and c < self.htf_levels['h']
                    is_bull_sweep = l < self.htf_levels['l'] and c > self.htf_levels['l']
                    
                    # 2. Kontrol: Order Flow Rejection (CVD Divergence)
                    if is_bear_sweep and self.analyze_order_flow(h, "SHORT"):
                        self.execute_protocol("SHORT", c, h)
                    
                    elif is_bull_sweep and self.analyze_order_flow(l, "LONG"):
                        self.execute_protocol("LONG", c, l)
                    
                    self.price_history.append((c, self.cvd))
                    if len(self.price_history) > 100: self.price_history.pop(0)

    def execute_protocol(self, side, entry, extreme):
        """Profesyonel Risk Yönetimi & Trade Setup Üretimi"""
        # Dinamik Stop: ATR'nin %20'si kadar tampon
        sl_buffer = self.htf_levels['atr'] * 0.2
        sl = extreme + sl_buffer if side == "SHORT" else extreme - sl_buffer
        
        risk = abs(entry - sl)
        tp1, tp2 = (entry - risk * 2, entry - risk * 4) if side == "SHORT" else (entry + risk * 2, entry + risk * 4)
        
        msg = (f"🦅 *SOVEREIGN {side} EXECUTION*\n\n"
               f"💎 *Entry:* `{entry:.2f}`\n"
               f"🛡️ *Dynamic Stop:* `{sl:.2f}`\n"
               f"🎯 *TP 1 (2R):* `{tp1:.2f}`\n"
               f"🔥 *TP 2 (4R):* `{tp2:.2f}`\n\n"
               f"🧠 *AI Confluence:* SFP + CVD Absorption + ATR Volatility Sync")
        telegram_send(msg)

    async def track_cvd(self):
        bm = BinanceSocketManager(self.client)
        async with bm.aggtrade_socket(SYMBOL) as stream:
            while True:
                m = await stream.recv()
                self.cvd += -float(m['q']) if m['m'] else float(m['q'])
                self.cvd_buffer.append(self.cvd)
                if len(self.cvd_buffer) > 50: self.cvd_buffer.pop(0)

    async def run(self):
        self.client = await AsyncClient.create(tld='com')
        await self.sync_intelligence()
        telegram_send("⚔️ *Sovereign Sentience: Neural Node* Online.\nLocation: Frankfurt/EU.")
        await asyncio.gather(self.track_cvd(), self.handle_klines())

if __name__ == "__main__":
    threading.Thread(target=lambda: app.run(host='0.0.0.0', port=int(os.environ.get("PORT", 8080))), daemon=True).start()
    asyncio.run(SovereignSentience().run())
