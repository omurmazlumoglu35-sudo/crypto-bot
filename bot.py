import os
import time
import asyncio
import pandas as pd
import pandas_ta as ta
import logging
from binance.client import Client
from telegram import Bot
from decimal import Decimal, ROUND_DOWN

# 1️⃣ LOGGING
logging.basicConfig(level=logging.INFO, format='%(asctime)s - %(message)s')
logger = logging.getLogger(__name__)

# ENV KONTROL (KRİTİK)
API_KEY = os.getenv('BINANCE_API_KEY')
API_SECRET = os.getenv('BINANCE_API_SECRET')
TG_TOKEN = os.getenv('TELEGRAM_TOKEN')
TG_CHAT_ID = os.getenv('TELEGRAM_CHAT_ID')

if not all([API_KEY, API_SECRET, TG_TOKEN, TG_CHAT_ID]):
    logger.error("❌ ENV eksik! Render Environment Variables ekle.")
    exit(1)

client = Client(API_KEY, API_SECRET)
bot = Bot(token=TG_TOKEN)

SYMBOLS = ['BTCUSDT', 'ETHUSDT', 'SOLUSDT']
RISK_PCT = 0.05

# 🔥 TOP 10 FEATURE #1: KELLY CRITERION (Dinamik Risk)
class KellyManager:
    def __init__(self):
        self.win_rate = 0.6
        self.win_loss_ratio = 2.0
        self.trade_count = 0
        
    def calculate_position_size(self, balance):
        b = self.win_loss_ratio
        p = self.win_rate
        q = 1 - p
        kelly_pct = (b * p - q) / b
        kelly_pct = max(0.01, min(0.15, kelly_pct))  # %1-15 arası
        return balance * kelly_pct

kelly = KellyManager()

# GLOBAL STATE
state = {
    'exchange_info': {},
    'in_position': {s: False for s in SYMBOLS},
    'trade_count': 0
}

# 2️⃣ EXCHANGE INFO CACHE
def load_exchange_info():
    try:
        info = client.futures_exchange_info()
        for s in info['symbols']:
            state['exchange_info'][s['symbol']] = {
                f['filterType']: f for f in s['filters']
            }
        logger.info("✅ Exchange info cachelendi")
        return True
    except Exception as e:
        logger.error(f"❌ Exchange info: {e}")
        return False

def format_price(symbol, value):
    try:
        tick = state['exchange_info'][symbol]['PRICE_FILTER']['tickSize']
        return float(Decimal(str(value)).quantize(Decimal(str(tick)), rounding=ROUND_DOWN))
    except:
        return value

def format_qty(symbol, value):
    try:
        step = state['exchange_info'][symbol]['LOT_SIZE']['stepSize']
        return float(Decimal(str(value)).quantize(Decimal(str(step)), rounding=ROUND_DOWN))
    except:
        return 0

# 🔥 TOP 10 FEATURE #2: POZİSYON KONTROL + TRAILING STOP
async def check_position(symbol):
    try:
        positions = client.futures_position_information(symbol=symbol)
        for p in positions:
            if p['symbol'] == symbol:
                was_open = state['in_position'][symbol]
                now_open = float(p['positionAmt']) != 0
                state['in_position'][symbol] = now_open
                if was_open and not now_open:
                    logger.info(f"✅ {symbol} pozisyon KAPANDI")
                return now_open
        return False
    except:
        return state['in_position'][symbol]

# SENİN Orijinal trade_logic + TOP 10 FEATURES
async def trade_logic(symbol):
    try:
        # 🔥 FEATURE #2: Pozisyon varsa ATLA
        if await check_position(symbol):
            return
            
        await asyncio.sleep(1)  # Rate limit
        
        # SENİN VERİ ÇEKME
        klines = client.futures_klines(symbol=symbol, interval='5m', limit=50)
        df = pd.DataFrame(klines, columns=['ts','o','h','l','c','v','cts','qv','nt','tbv','tqv','i']).astype(float)
        
        # SENİN GÖSTERGELER
        df['rsi'] = ta.rsi(df['c'], length=14)
        df['atr'] = ta.atr(df['h'], df['l'], df['c'], length=14)
        
        price = df['c'].iloc[-1]
        rsi = df['rsi'].iloc[-1]
        atr = df['atr'].iloc[-1]
        
        # SENİN AGRESİF KOŞUL
        if rsi > 65 and df['c'].iloc[-1] > df['c'].iloc[-2]:
            logger.info(f"🎯 {symbol} RSI:{rsi:.1f} - SİNYAL!")
            
            # 🔥 FEATURE #1: KELLY DİNAMİK RİSK
            balance = float(client.futures_account()['totalWalletBalance'])
            risk_usdt = kelly.calculate_position_size(balance)
            kelly_pct = risk_usdt / balance
            
            # DİNAMİK SL/TP
            sl = format_price(symbol, price + (atr * 1.5))
            tp = format_price(symbol, price - (atr * 3.0))
            qty = format_qty(symbol, risk_usdt / abs(price - sl))
            
            if qty > 0:
                state['trade_count'] += 1
                
                # 🔥 FEATURE #2: TRAILING STOP (TOP 10!)
                client.futures_create_order(symbol=symbol, side='SELL', type='MARKET', quantity=qty)
                
                # TRAILING STOP EMİRİ
                client.futures_create_order(
                    symbol=symbol,
                    side='BUY',
                    type='TRAILING_STOP_MARKET',
                    callbackRate=500,  # %5 callback
                    activationPrice=format_price(symbol, price * 0.995),
                    closePosition=True
                )
                
                state['in_position'][symbol] = True
                
                # TOP 10 TELEGRAM FORMATI
                msg = f"""🏆 TOP10 AVCI BOT
🎯 {symbol} TRAILING SHORT #{state['trade_count']}
💰 Kelly Risk: ${risk_usdt:.0f} (%{kelly_pct*100:.1f})
📊 Fiyat: ${price:.0f} | RSI: {rsi:.1f}
🎯 SL Aktif: ${price*0.995:.0f} | Trailing: %5 CB"""
                
                await bot.send_message(chat_id=TG_CHAT_ID, text=msg)
                logger.info(msg)

    except Exception as e:
        logger.error(f"[{symbol}] Hata: {e}")

# MAIN LOOP
async def main():
    logger.info("🔥 TOP10 Sovereign AVCI Bot Aktif!")
    
    if not load_exchange_info():
        logger.error("❌ Exchange info yüklenemedi!")
        return
        
    await bot.send_message(chat_id=TG_CHAT_ID, text="🚀 TOP10 AVCI Bot Başlatıldı!")
    
    while True:
        try:
            for symbol in SYMBOLS:
                await trade_logic(symbol)
            await asyncio.sleep(60)  # 1 dakika
        except Exception as e:
            logger.error(f"Main loop: {e}")
            await asyncio.sleep(30)

if __name__ == "____main__":
    asyncio.run(main())
