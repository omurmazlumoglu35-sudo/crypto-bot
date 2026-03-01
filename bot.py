import os, asyncio, numpy as np, threading
from binance import AsyncClient, BinanceSocketManager
from telegram import Bot
from flask import Flask

# --- RENDER KEEPALIVE ENGINE ---
app = Flask(__name__)

@app.route('/')
def health_check():
    return "Sovereign Apex is Online", 200

def run_web_server():
    port = int(os.environ.get("PORT", 10000))
    app.run(host="0.0.0.0", port=port)

# Web sunucusunu ayrı bir kolda başlat (Render'ı açık tutar)
threading.Thread(target=run_web_server, daemon=True).start()

# --- APEX STRATEGY SETTINGS ---
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

    def get_oi_z_score(self, symbol):
        if len(self.state[symbol]['oi_history']) < 20: return 0
        ois = np.array(self.state[symbol]['oi_history'][-20:])
        return (ois[-1] - np.mean(ois)) / (np.std(ois) + 1e-9)

    async def manage_position(self, symbol):
        while self.state[symbol]['active_trade']:
            try:
                ticker = await self.client.futures_symbol_ticker(symbol=symbol)
                current_price = float(ticker['price'])
                entry = self.state[symbol]['entry_price']
                profit_pct = (entry - current_price) / entry * 100
                
                # ATR bazlı Breakeven kontrolü
                if len(self.state[symbol]['m1_klines']) > 14:
                    atr = np.mean([k['h'] - k['l'] for k in self.state[symbol]['m1_klines'][-14:]])
                    if profit_pct > (BREAKEVEN_TRIGGER * (atr/entry)*100):
                        if self.state[symbol]['sl_order_id']:
                            await self.client.futures_cancel_order(symbol=symbol, orderId=self.state[symbol]['sl_order_id'])
                            new_sl = await self.client.futures_create_order(
                                symbol=symbol, side='BUY', type='STOP_MARKET', 
                                stopPrice=round(entry * 0.9995, 4), closePosition='true'
                            )
                            self.state[symbol]['sl_order_id'] = new_sl['orderId']
                            await self.bot.send_message(self.chat_id, f"🛡️ {symbol}: Breakeven Koruması Aktif.")
                            break
            except: pass
            await asyncio.sleep(20)

    async def execute_apex_short(self, symbol, h, c, atr):
        if self.state[symbol]['active_trade']: return
        try:
            balance = await self.client.futures_account_balance()
            usdt = next(float(b['balance']) for b in balance if b['asset'] == 'USDT')
            sl_price = round(h + (atr * 0.15), 2 if 'BTC' in symbol else 4)
            qty = round((usdt * RISK_PER_TRADE_PCT / (abs(sl_price - c) / c)) / c, 3 if 'BTC' in symbol else 1)
            
            if qty > 0:
                await self.client.futures_change_leverage(symbol=symbol, leverage=LEVERAGE)
                order = await self.client.futures_create_order(symbol=symbol, side='SELL', type='MARKET', quantity=qty)
                entry = float(order['avgPrice'])
                tp_price = round(entry - (abs(sl_price - entry) * RISK_REWARD), 2 if 'BTC' in symbol else 4)
                
                sl_order = await self.client.futures_create_order(symbol=symbol, side='BUY', type='STOP_MARKET', stopPrice=sl_price, closePosition='true')
                await self.client.futures_create_order(symbol=symbol, side='BUY', type='TAKE_PROFIT_MARKET', stopPrice=tp_price, closePosition='true')
                
                self.state[symbol].update({'active_trade': True, 'entry_price': entry, 'sl_order_id': sl_order['orderId']})
                asyncio.create_task(self.manage_position(symbol))
                await self.bot.send_message(self.chat_id, f"⚔️ APEX SHORT EXECUTED: {symbol}\nEntry: {entry}\nSL: {sl_price} | TP: {tp_price}")
        except Exception as e:
            print(f"Execution Error: {e}")

    async def process_logic(self, symbol):
        s = self.state[symbol]
        if len(s['m1_klines']) < 20 or len(s['m15_klines']) < 5: return
        m1, m15 = s['m1_klines'][-1], s['m15_klines'][-1]
        
        # M15 Rejection (Üst iğne)
        m15_rejection = (m15['h'] - max(m15['o'], m15['c'])) > (max(m15['o'], m15['c']) - min(m15['o'], m15['c']))
        
        if m15_rejection:
            # M1 SFP (Önceki tepenin süpürülmesi)
            prev_high = max([k['h'] for k in s['m1_klines'][-20:-1]])
            atr_m1 = np.mean([k['h'] - k['l'] for k in s['m1_klines'][-14:]])
            
            if m1['h'] > prev_high and m1['c'] < prev_high:
                # OI Spike (Z-Score) & Funding Check
                if self.get_oi_z_score(symbol) > OI_Z_SCORE_THRESHOLD and s['funding'] >= FUNDING_THRESHOLD:
                    # CVD Divergence (Fiyat çıkarken satış baskısı)
                    if len(s['cvd_history']) > 5 and s['cvd_history'][-1] < s['cvd_history'][-5]:
                        await self.execute_apex_short(symbol, m1['h'], m1['c'], atr_m1)

    async def sync_data(self):
        while True:
            for s in WATCHLIST:
                try:
                    oi = await self.client.futures_open_interest(symbol=s)
                    self.state[s]['oi_history'].append(float(oi['openInterest']))
                    if len(self.state[s]['oi_history']) > 60: self.state[s]['oi_history'].pop(0)
                    f = await self.client.futures_funding_rate(symbol=s, limit=1)
                    self.state[s]['funding'] = float(f[0]['fundingRate'])
                except: pass
            await asyncio.sleep(30)

    async def launch(self):
        while True:
            try:
                self.client = await AsyncClient.create(os.getenv('BINANCE_API_KEY'), os.getenv('BINANCE_API_SECRET'))
                for s in WATCHLIST:
                    # Başlangıç verilerini doldur
                    for tf, key in [('1m', 'm1_klines'), ('5m', 'm5_klines'), ('15m', 'm15_klines')]:
                        k = await self.client.futures_historical_klines(s, tf, '100m ago UTC')
                        self.state[s][key] = [{'h':float(i[2]), 'l':float(i[3]), 'c':float(i[4]), 'o':float(i[1])} for i in k]
                    oi_init = await self.client.futures_open_interest(symbol=s)
                    self.state[s]['oi_history'] = [float(oi_init['openInterest'])] * 20
                
                asyncio.create_task(self.sync_data())
                bsm = BinanceSocketManager(self.client)
                streams = [f"{s.lower()}@kline_{tf}" for s in WATCHLIST for tf in ['1m', '5m', '15m']] + [f"{s.lower()}@aggTrade" for s in WATCHLIST]
                
                async with bsm.multiplex_socket(streams) as ms:
                    print("🦅 Sovereign APEX: Aktif. Frankfurt Hattı Kuruldu.")
                    await self.bot.send_message(self.chat_id, "🚀 Sovereign APEX V20 Online. Pusu Başladı.")
                    while True:
                        res = await ms.recv()
                        stream, data = res['stream'], res['data']
                        symbol = stream.split('@')[0].upper()
                        
                        if 'kline' in stream and data['k']['x']:
                            tf = stream.split('_')[1]
                            self.state[symbol][f"{tf}_klines"].append({'h':float(data['k']['h']), 'l':float(data['k']['l']), 'c':float(data['k']['c']), 'o':float(data['k']['o'])})
                            if len(self.state[symbol][f"{tf}_klines"]) > 100: self.state[symbol][f"{tf}_klines"].pop(0)
                            if tf == '1m': await self.process_logic(symbol)
                            
                        elif 'aggTrade' in stream:
                            self.state[symbol]['current_cvd'] += (-float(data['q']) if data['m'] else float(data['q']))
                            # CVD history her dakika başında kline_1m içinde güncellenir.
                            if '1m' in stream and data['k']['x']:
                                self.state[symbol]['cvd_history'].append(self.state[symbol]['current_cvd'])
                                self.state[symbol]['current_cvd'] = 0
                                if len(self.state[symbol]['cvd_history']) > 50: self.state[symbol]['cvd_history'].pop(0)

            except Exception as e:
                print(f"⚠️ Bağlantı Hatası: {e}")
                await asyncio.sleep(10)
            finally:
                if self.client: await self.client.close_connection()

if __name__ == "__main__":
    asyncio.run(SovereignApexFinal().launch())
