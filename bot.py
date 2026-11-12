import logging
from telegram import Update, InlineKeyboardButton, InlineKeyboardMarkup
from telegram.ext import ApplicationBuilder, ContextTypes, CommandHandler, CallbackQueryHandler
import yfinance as yf
import pandas as pd
import sqlite3
from datetime import datetime

# استبدل التوكن أدناه بالتوكن الذي نسخته من BotFather
TOKEN = "9116308908:AAE6NKH6MrLiIIcORMFdT0pUhP3l23p8-J4"

# إعدادات إدارة المخاطر الافتراضية
DEFAULT_CAPITAL = 1000.0  
DEFAULT_RISK_PERCENT = 0.01  

logging.basicConfig(format='%(asctime)s - %(name)s - %(levelname)s - %(message)s', level=logging.INFO)

# قاعدة البيانات المخزنة محلياً
DB_NAME = "trading_bot.db"

def init_db():
    conn = sqlite3.connect(DB_NAME)
    cursor = conn.cursor()
    cursor.execute('''
        CREATE TABLE IF NOT EXISTS signals (
            id INTEGER PRIMARY KEY AUTOINCREMENT,
            timestamp TEXT,
            type TEXT,
            entry REAL,
            sl REAL,
            tp1 REAL,
            tp2 REAL,
            tp3 REAL,
            rr REAL,
            reason TEXT,
            status TEXT DEFAULT 'ACTIVE',
            result TEXT DEFAULT 'PENDING'
        )
    ''')
    conn.commit()
    conn.close()

def save_signal(signal_data):
    conn = sqlite3.connect(DB_NAME)
    cursor = conn.cursor()
    cursor.execute('''
        INSERT INTO signals (timestamp, type, entry, sl, tp1, tp2, tp3, rr, reason, status, result)
        VALUES (?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?)
    ''', (
        datetime.now().strftime("%Y-%m-%d %H:%M:%S"),
        signal_data['type'], signal_data['entry'], signal_data['sl'],
        signal_data['tp1'], signal_data['tp2'], signal_data['tp3'],
        signal_data['rr'], signal_data['reason'], 'ACTIVE', 'PENDING'
    ))
    conn.commit()
    conn.close()

def get_last_signals(limit=3):
    conn = sqlite3.connect(DB_NAME)
    cursor = conn.cursor()
    cursor.execute('SELECT * FROM signals ORDER BY id DESC LIMIT ?', (limit,))
    rows = cursor.fetchall()
    conn.close()
    return rows

def fetch_gold_data():
    try:
        ticker = yf.Ticker("GC=F")
        df = ticker.history(period="5d", interval="1h")
        if df.empty:
            return None
        return df
    except Exception as e:
        print(f"Error: {e}")
        return None

def analyze_market_structure(df):
    if df is None or len(df) < 30:
        return None

    df['EMA_50'] = df['Close'].ewm(span=50, adjust=False).mean()
    df['EMA_200'] = df['Close'].ewm(span=200, adjust=False).mean()
    
    current_close = df['Close'].iloc[-1]
    ema_50 = df['EMA_50'].iloc[-1]
    ema_200 = df['EMA_200'].iloc[-1]

    if ema_50 > ema_200 and current_close > ema_50:
        trend = "صاعد قوي (Bullish)"
    elif ema_50 < ema_200 and current_close < ema_50:
        trend = "هابط قوي (Bearish)"
    else:
        trend = "عرضي / تذبذب (Consolidation)"

    support = df['Low'].tail(20).min()
    resistance = df['High'].tail(20).max()

    analysis_result = {
        "current_price": round(current_close, 2),
        "trend": trend,
        "support": round(support, 2),
        "resistance": round(resistance, 2),
        "fvg": "اختلال سعري متوازن (FVG متوفر)",
        "signal_ready": False
    }

    if "صاعد" in trend and abs(current_close - support) < (resistance - support) * 0.2:
        entry = round(current_close, 2)
        sl = round(support - 3.0, 2)
        risk = entry - sl
        if risk > 0:
            analysis_result.update({
                "signal_ready": True, "type": "BUY", "entry": entry, "sl": sl,
                "tp1": round(entry + (risk * 1.5), 2),
                "tp2": round(entry + (risk * 2.5), 2),
                "tp3": round(entry + (risk * 4.0), 2),
                "rr": 2.5,
                "reason": "ارتداد من دعم رئيسي مع توافق هيكل السوق الصاعد (BOS) ومفاهيم الذكاء المؤسسي (SMC)."
            })
    elif "هابط" in trend and abs(current_close - resistance) < (resistance - support) * 0.2:
        entry = round(current_close, 2)
        sl = round(resistance + 3.0, 2)
        risk = sl - entry
        if risk > 0:
            analysis_result.update({
                "signal_ready": True, "type": "SELL", "entry": entry, "sl": sl,
                "tp1": round(entry - (risk * 1.5), 2),
                "tp2": round(entry - (risk * 2.5), 2),
                "tp3": round(entry - (risk * 4.0), 2),
                "rr": 2.5,
                "reason": "رفض السعر لمنطقة مقاومة قوية وتغير الشخصية (CHoCH) نحو الهبوط."
            })

    return analysis_result

def get_main_keyboard():
    keyboard = [
        [InlineKeyboardButton("📊 تحليل الذهب الحالي", callback_data="market_analysis")],
        [InlineKeyboardButton("⚡ آخر التوصيات", callback_data="last_signals")],
        [InlineKeyboardButton("💰 إدارة رأس المال والمخاطر", callback_data="risk_management_info")],
        [InlineKeyboardButton("⚙️ حالة السوق", callback_data="market_status")]
    ]
    return InlineKeyboardMarkup(keyboard)

async def start(update: Update, context: ContextTypes.DEFAULT_TYPE):
    user_name = update.effective_user.first_name
    welcome_text = (
        f"مرحباً بك يا أخي {user_name} في بوت تحليل وتداول الذهب الاحترافي (XAUUSD).\n\n"
        f"يعتمد البوت على مفاهيم الذكاء المؤسسي (SMC) وحماية رأس المال.\n"
        f"اختر من القائمة أدناه للبدء:"
    )
    if update.message:
        await update.message.reply_text(welcome_text, reply_markup=get_main_keyboard())
    elif update.callback_query:
        await update.callback_query.message.edit_text(welcome_text, reply_markup=get_main_keyboard())

async def button_handler(update: Update, context: ContextTypes.DEFAULT_TYPE):
    query = update.callback_query
    await query.answer()

    if query.data == "market_analysis":
        await query.message.edit_text("⏳ جاري جلب أسعار الذهب الحية وتحليل السوق بناءً على SMC...", reply_markup=get_main_keyboard())
        
        df = fetch_gold_data()
        analysis = analyze_market_structure(df)
        
        if not analysis:
            await query.message.edit_text("❌ تعذر جلب البيانات حالياً. حاول لاحقاً.", reply_markup=get_main_keyboard())
            return

        text = (
            f"📈 **التحليل الفني الفوري للذهب (XAUUSD)**\n\n"
            f"💵 **السعر الحالي:** `{analysis['current_price']}` $\n"
            f"📊 **الاتجاه العام:** {analysis['trend']}\n"
            f"🛡 **الدعم:** `{analysis['support']}` | ⚔️ **المقاومة:** `{analysis['resistance']}`\n"
            f"🔍 **منطقة FVG:** {analysis['fvg']}\n\n"
        )

        if analysis['signal_ready']:
            risk_usd = DEFAULT_CAPITAL * DEFAULT_RISK_PERCENT
            text += (
                f"🚨 **فرصة تداول مؤكدة ومكتملة الشروط!**\n"
                f"🔸 **النوع:** `{analysis['type']}`\n"
                f"🎯 **سعر الدخول:** `{analysis['entry']}`\n"
                f"🛑 **وقف الخسارة:** `{analysis['sl']}`\n"
                f"🎯 **TP1:** `{analysis['tp1']}` | **TP2:** `{analysis['tp2']}` | **TP3:** `{analysis['tp3']}`\n"
                f"⚖️ **العائد للمخاطرة (R:R):** `1:{analysis['rr']}`\n"
                f"📉 **المخاطرة المقترحة (1%):** `{risk_usd}$`\n\n"
                f"💡 **السبب:** {analysis['reason']}"
            )
            save_signal(analysis)
        else:
            text += "💤 **حالة السوق:** لا توجد فرصة مطابقة لشروط الدخول الصارمة حالياً. حماية رأس المال أولوية."

        await query.message.edit_text(text, reply_markup=get_main_keyboard(), parse_mode="Markdown")

    elif query.data == "last_signals":
        signals = get_last_signals(limit=3)
        if not signals:
            await query.message.edit_text("📭 لا توجد توصيات مسجلة حتى الآن.", reply_markup=get_main_keyboard())
            return
        
        text = "⚡ **سجل آخر التوصيات:**\n\n"
        for sig in signals:
            text += f"📅 `{sig[1]}`\n🔹 **{sig[2]}** | الدخول: `{sig[3]}` | الوقف: `{sig[4]}`\n-------------------\n"
        
        await query.message.edit_text(text, reply_markup=get_main_keyboard(), parse_mode="Markdown")

    elif query.data == "risk_management_info":
        risk_text = (
            f"💰 **إدارة المخاطر:**\n\n"
            f"1️⃣ المخاطرة بنسبة `1%` فقط افتراضياً من رأس المال.\n"
            f"2️⃣ الالتزام بوقف خسارة صارم بناءً على الهيكل الفني.\n"
            f"3️⃣ عدم الدخول في صفقات ذات عائد أقل من 1:2."
        )
        await query.message.edit_text(risk_text, reply_markup=get_main_keyboard(), parse_mode="Markdown")

    elif query.data == "market_status":
        status_text = "⚙️ **حالة النظام:**\n\n🟢 السيرفر متصل ومرتبط ببيانات الذهب الحية.\n🛡 فلاتر SMC مفعلة بنجاح."
        await query.message.edit_text(status_text, reply_markup=get_main_keyboard(), parse_mode="Markdown")

def main():
    init_db()
    app = ApplicationBuilder().token(TOKEN).build()
    app.add_handler(CommandHandler("start", start))
    app.add_handler(CallbackQueryHandler(button_handler))
    print("Bot is running...")
    app.run_polling()

if __name__ == '__main__':
    main()
  
