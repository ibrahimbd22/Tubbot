import logging
import asyncio
import os
import random
from datetime import date, datetime, timedelta
from telegram import Update, InlineKeyboardButton, InlineKeyboardMarkup, ReplyKeyboardMarkup, KeyboardButton
from telegram.ext import ApplicationBuilder, ContextTypes, CommandHandler, CallbackQueryHandler, MessageHandler, filters
from googleapiclient.discovery import build
import psycopg2
import requests
from dotenv import load_dotenv
from flask import Flask
from threading import Thread

# ==========================================
# 👇 RENDER KEEPER 👇
# ==========================================
app = Flask('')
@app.route('/')
def home(): return "YouTube Growth Pro is Running..."
def run(): app.run(host='0.0.0.0', port=8080)
def keep_alive():
    t = Thread(target=run)
    t.start()

# ==========================================
# 👇 CONFIGURATION 👇
# ==========================================
load_dotenv()

BOT_TOKEN = os.getenv("BOT_TOKEN")
ADMIN_ID = int(os.getenv("ADMIN_ID"))
YOUTUBE_API_KEY = os.getenv("YOUTUBE_API_KEY")
DB_URI = os.getenv("DB_URI")
BKASH_NUMBER = os.getenv("BKASH_NUMBER")

BANNER_IMG = "https://cdn.pixabay.com/photo/2016/11/19/14/00/code-1839406_1280.jpg"

logging.basicConfig(format='%(asctime)s - %(name)s - %(levelname)s - %(message)s', level=logging.INFO)

# --- DATABASE ---
def get_db_connection():
    try: return psycopg2.connect(DB_URI)
    except Exception as e: print(f"DB Error: {e}"); return None

# --- API HELPERS ---
def get_yt_channel_info(channel_id):
    try:
        youtube = build('youtube', 'v3', developerKey=YOUTUBE_API_KEY)
        req = youtube.channels().list(part="snippet,statistics", id=channel_id)
        res = req.execute()
        if "items" in res and len(res["items"]) > 0:
            item = res["items"][0]
            return {
                "title": item["snippet"]["title"],
                "thumbnail": item["snippet"]["thumbnails"]["high"]["url"],
                "subs": item["statistics"]["subscriberCount"]
            }
        return None
    except: return None

def check_subscription(user_channel_id, target_channel_id):
    try:
        youtube = build('youtube', 'v3', developerKey=YOUTUBE_API_KEY)
        req = youtube.subscriptions().list(part="snippet", channelId=user_channel_id, forChannelId=target_channel_id)
        res = req.execute()
        return len(res.get("items", [])) > 0
    except: return False

# --- KEYBOARDS ---
def get_persistent_menu():
    keyboard = [
        [KeyboardButton("🚀 Earn Points"), KeyboardButton("👤 My Profile")],
        [KeyboardButton("🎁 Daily Bonus"), KeyboardButton("🏆 Leaderboard")],
        [KeyboardButton("💎 Buy Points"), KeyboardButton("🤝 Refer & Earn")],
        [KeyboardButton("🎟️ Lottery (Win 1000)"), KeyboardButton("🚀 Boost Channel")],
        [KeyboardButton("💸 Transfer"), KeyboardButton("🆘 Support")]
    ]
    return ReplyKeyboardMarkup(keyboard, resize_keyboard=True)

def get_inline_home():
    return InlineKeyboardMarkup([
        [InlineKeyboardButton("🚀 Start Earning", callback_data='earn_mode'), InlineKeyboardButton("👤 Dashboard", callback_data='profile_mode')],
        [InlineKeyboardButton("💎 Premium Shop", callback_data='buy_mode'), InlineKeyboardButton("🎟️ Lottery", callback_data='lottery_info')],
        [InlineKeyboardButton("🏆 Top 10", callback_data='top_mode'), InlineKeyboardButton("🎁 Bonus", callback_data='bonus_action')]
    ])

def get_profile_actions(is_enrolled):
    enroll_text = "🔕 Unenroll" if is_enrolled else "📌 Enroll Channel"
    enroll_data = "unenroll_action" if is_enrolled else "enroll_action"
    return InlineKeyboardMarkup([
        [InlineKeyboardButton("🎁 Claim Bonus", callback_data='bonus_action')],
        [InlineKeyboardButton(enroll_text, callback_data=enroll_data), InlineKeyboardButton("🚀 Boost (200 Pts)", callback_data='boost_action')],
        [InlineKeyboardButton("🔄 Transfer", callback_data='transfer_mode'), InlineKeyboardButton("🎟️ Coupon", callback_data='coupon_mode')],
        [InlineKeyboardButton("🚀 Earn Points", callback_data='earn_mode')]
    ])

# --- HANDLERS ---

async def start(update: Update, context: ContextTypes.DEFAULT_TYPE):
    user = update.effective_user
    conn = get_db_connection()
    if not conn: return
    cur = conn.cursor()
    cur.execute("SELECT is_banned FROM users WHERE user_id = %s", (user.id,))
    res = cur.fetchone()
    
    if res:
        if res[0]: await update.message.reply_text("⛔ **BANNED!** Contact Admin.")
        else: 
            txt = f"👋 **Welcome Back, {user.first_name}!**\nSelect an option below."
            await update.message.reply_photo(photo=BANNER_IMG, caption=txt, reply_markup=get_inline_home(), parse_mode='Markdown')
            await update.message.reply_text("👇 **Main Menu:**", reply_markup=get_persistent_menu())
    else:
        args = context.args
        ref_id = int(args[0]) if args and args[0].isdigit() and int(args[0]) != user.id else None
        welcome_text = (
            f"🎉 **WELCOME TO YOUTUBE GROWTH PRO**\n"
            "━━━━━━━━━━━━━━━━━━\n"
            f"Hello {user.first_name}, grow your channel organically.\n"
            f"*আমাদের প্রফেশনাল কমিউনিটিতে আপনাকে স্বাগতম।*\n\n"
            "🎁 **Bonus:** `+50 Points`\n"
            "🚀 **Features:** Real Subs, Fast Growth.\n\n"
            "👇 **Send your YouTube Channel ID:**\n"
            "(Example: `UCxxxxxxxxxxxxxxx`)"
        )
        await update.message.reply_photo(photo=BANNER_IMG, caption=welcome_text, parse_mode='Markdown')
        context.user_data['waiting_for_channel'] = True
        if ref_id: context.user_data['referrer_id'] = ref_id
    cur.close()
    conn.close()

async def handle_message(update: Update, context: ContextTypes.DEFAULT_TYPE):
    text = update.message.text
    user = update.effective_user
    
    if text == "🚀 Get Subscribers" or text == "🚀 Earn Points": await earn_points_logic(update, context)
    elif text == "👤 My Profile": await show_profile_logic(update, context)
    elif text == "🎁 Daily Bonus": await claim_bonus_logic(update, context)
    elif text == "🏆 Leaderboard": await show_leaderboard_logic(update, context)
    elif text == "💎 Buy Points": await buy_info_logic(update, context)
    elif text == "🤝 Refer & Earn": await refer_logic(update, context)
    elif text == "💸 Transfer": await update.message.reply_text("💸 **TRANSFER**\nUsage: `/transfer ID Amount`\n*Tax: 10%*")
    elif text == "🎟️ Redeem Code": 
        await update.message.reply_text("🎟️ **COUPON**\nEnter code:")
        context.user_data['awaiting_coupon'] = True
    elif text == "🎟️ Lottery (Win 1000)": await lottery_logic(update, context)
    elif text == "🚀 Boost Channel": await boost_channel_logic(update, context)
    elif text == "📊 Server Stats": await show_stats(update, context)
    elif text == "🆘 Support": await update.message.reply_text("📞 Admin: @YourAdminUsername")

    elif context.user_data.get('awaiting_coupon'):
        await process_coupon(update, context, text.strip())
        context.user_data['awaiting_coupon'] = False

    elif context.user_data.get('waiting_for_channel'):
        await process_registration(update, context, text)

async def earn_points_logic(update: Update, context: ContextTypes.DEFAULT_TYPE):
    user = update.effective_user
    conn = get_db_connection()
    cur = conn.cursor()
    
    target, t_uid, priority = None, 0, False
    
    # 1. Admin Priority
    cur.execute("SELECT channel_id FROM priority_channels")
    for (pcid,) in cur.fetchall():
        cur.execute("SELECT 1 FROM subscriptions WHERE subscriber_id=%s AND target_channel_id=%s", (user.id, pcid))
        if not cur.fetchone():
            cur.execute("SELECT 1 FROM skipped_tasks WHERE user_id=%s AND channel_id=%s", (user.id, pcid))
            if not cur.fetchone():
                cur.execute("SELECT channel_id FROM users WHERE user_id=%s", (user.id,))
                my = cur.fetchone()
                if not my or my[0] != pcid:
                    target, priority = pcid, True
                    break
    
    # 2. Boosted Channels (Paid 200)
    if not target:
        cur.execute("SELECT channel_id, user_id FROM boosted_channels WHERE expires_at > NOW() ORDER BY expires_at ASC")
        for bcid, buid in cur.fetchall():
            cur.execute("SELECT 1 FROM subscriptions WHERE subscriber_id=%s AND target_channel_id=%s", (user.id, bcid))
            if not cur.fetchone():
                cur.execute("SELECT 1 FROM skipped_tasks WHERE user_id=%s AND channel_id=%s", (user.id, bcid))
                if not cur.fetchone():
                    if buid != user.id:
                        target, t_uid, priority = bcid, buid, True # Considered Priority
                        break

    # 3. Regular
    if not target:
        cur.execute("""SELECT user_id, channel_id FROM users 
                       WHERE user_id != %s AND balance >= 15 AND is_enrolled = TRUE
                       AND channel_id NOT IN (SELECT target_channel_id FROM subscriptions WHERE subscriber_id = %s)
                       AND channel_id NOT IN (SELECT channel_id FROM skipped_tasks WHERE user_id = %s)
                       ORDER BY RANDOM() LIMIT 1""", (user.id, user.id, user.id))
        reg = cur.fetchone()
        if reg: t_uid, target = reg

    cur.close()
    conn.close()

    if target:
        yt = get_yt_channel_info(target)
        title = yt['title'] if yt else "Channel"
        thumb = yt['thumbnail'] if yt else BANNER_IMG
        context.user_data.update({'t_uid': t_uid, 't_cid': target, 'prio': priority})
        
        cap = (f"📋 **NEW TASK**\n━━━━━━━━━━━━━━━━\nSubscribe to earn **10 Points**.\n"
               f"📺 **{title}**\n🎁 Reward: 10 Pts\n⚠️ *Don't unsubscribe (-30 Pts).*")
        
        kb = [[InlineKeyboardButton("📺 Subscribe Now ↗️", url=f"https://www.youtube.com/channel/{target}")],
              [InlineKeyboardButton("✅ Verify", callback_data='verify')],
              [InlineKeyboardButton("⏭️ Skip (-1)", callback_data='skip'), InlineKeyboardButton("🚩 Report", callback_data='report')]]
        
        if update.callback_query:
            await update.callback_query.message.reply_photo(photo=thumb, caption=cap, reply_markup=InlineKeyboardMarkup(kb), parse_mode='Markdown')
        else:
            await update.message.reply_photo(photo=thumb, caption=cap, reply_markup=InlineKeyboardMarkup(kb), parse_mode='Markdown')
    else:
        msg = "❌ **No Tasks!**\nPlease try again later."
        if update.callback_query: await update.callback_query.message.reply_text(msg)
        else: await update.message.reply_text(msg)

async def show_profile_logic(update: Update, context: ContextTypes.DEFAULT_TYPE):
    user = update.effective_user
    conn = get_db_connection()
    cur = conn.cursor()
    cur.execute("SELECT balance, channel_id, warnings, total_earned, total_spent, gained_subs, channel_title, pfp_url, streak_count, is_enrolled FROM users WHERE user_id = %s", (user.id,))
    res = cur.fetchone()
    cur.close()
    conn.close()

    if res:
        bal, cid, warn, earn, spent, gained, title, pfp, streak, enrolled = res
        yt = get_yt_channel_info(cid)
        subs = yt['subs'] if yt else "N/A"
        rank = "VIP" if spent > 2000 else "Free"
        
        cap = (f"👤 **MY DASHBOARD**\n━━━━━━━━━━━━━━━━\n📛 {title}\n🆔 `{user.id}` | 💎 {rank}\n━━━━━━━━━━━━━━━━\n"
               f"📊 **STATS:** Live: `{subs}` | Bot: `{gained}`\n🔥 **Streak:** {streak} Days\n"
               f"💰 **WALLET:** Bal: `{bal}` | Earned: `{earn}`\n"
               f"⚠️ **Status:** Active ({warn}/3)")
        
        if update.callback_query:
            await update.callback_query.message.reply_photo(photo=pfp or BANNER_IMG, caption=cap, reply_markup=get_profile_actions(enrolled), parse_mode='Markdown')
        else:
            await update.message.reply_photo(photo=pfp or BANNER_IMG, caption=cap, reply_markup=get_profile_actions(enrolled), parse_mode='Markdown')

async def callback_handler(update: Update, context: ContextTypes.DEFAULT_TYPE):
    q = update.callback_query
    await q.answer()
    data, user = q.data, q.from_user
    
    if data == 'earn_mode': await earn_points_logic(update, context)
    elif data == 'profile_mode': await show_profile_logic(update, context)
    elif data == 'bonus_action': await claim_bonus_logic(update, context)
    elif data == 'top_mode': await show_leaderboard_logic(update, context)
    elif data == 'buy_mode': await buy_info_logic(update, context)
    elif data == 'refer_mode': await refer_logic(update, context)
    elif data == 'lottery_info': await lottery_logic(update, context)
    elif data == 'boost_action': await boost_channel_logic(update, context)
    
    elif data == 'skip':
        cid = context.user_data.get('t_cid')
        conn = get_db_connection()
        cur = conn.cursor()
        cur.execute("INSERT INTO skipped_tasks VALUES (%s, %s) ON CONFLICT DO NOTHING", (user.id, cid))
        cur.execute("UPDATE users SET balance = balance - 1 WHERE user_id = %s", (user.id,))
        conn.commit()
        conn.close()
        await q.message.delete()
        await q.message.reply_text("⏭️ **Skipped!** 1 Point deducted.")
        await earn_points_logic(update, context)

    elif data == 'verify':
        uid, cid, prio = context.user_data.get('t_uid'), context.user_data.get('t_cid'), context.user_data.get('prio')
        conn = get_db_connection()
        cur = conn.cursor()
        cur.execute("SELECT channel_id FROM users WHERE user_id = %s", (user.id,))
        my = cur.fetchone()
        
        if my and check_subscription(my[0], cid):
            try:
                cur.execute("UPDATE users SET balance = balance + 10, total_earned = total_earned + 10 WHERE user_id = %s", (user.id,))
                if not prio and uid != 0:
                    cur.execute("UPDATE users SET balance = balance - 15, total_spent = total_spent + 15, gained_subs = gained_subs + 1 WHERE user_id = %s", (uid,))
                    cur.execute("UPDATE system_pool SET total_balance = total_balance + 5 WHERE id = 1")
                cur.execute("INSERT INTO subscriptions (subscriber_id, target_channel_id, target_user_id) VALUES (%s, %s, %s)", (user.id, cid, uid))
                conn.commit()
                await q.message.delete()
                await q.message.reply_text("🎉 **Success!** +10 Points.", reply_markup=InlineKeyboardMarkup([[InlineKeyboardButton("🚀 Next Task", callback_data='earn_mode')]]))
            except: 
                await q.message.reply_text("⚠️ Error.")
        else:
            await q.message.reply_text("❌ **Failed!** Not subscribed.")
        conn.close()

    elif data == 'buy_lottery_ticket':
        conn = get_db_connection()
        cur = conn.cursor()
        cur.execute("SELECT balance FROM users WHERE user_id=%s", (user.id,))
        bal = cur.fetchone()[0]
        
        if bal >= 100:
            cur.execute("UPDATE users SET balance = balance - 100 WHERE user_id=%s", (user.id,))
            cur.execute("INSERT INTO lottery_tickets (user_id) VALUES (%s)", (user.id,))
            cur.execute("SELECT COUNT(DISTINCT user_id) FROM lottery_tickets")
            count = cur.fetchone()[0]
            
            msg = f"🎟️ **Ticket Purchased!** (-100 Pts)\nTotal Participants: {count}/12"
            
            # LOTTERY DRAW LOGIC
            if count >= 12:
                cur.execute("SELECT user_id FROM lottery_tickets ORDER BY RANDOM() LIMIT 1")
                winner = cur.fetchone()[0]
                cur.execute("UPDATE users SET balance = balance + 1000 WHERE user_id=%s", (winner,))
                cur.execute("DELETE FROM lottery_tickets") # Reset
                cur.execute("UPDATE system_pool SET total_balance = total_balance + 200 WHERE id = 1") # System Profit
                try: await context.bot.send_message(winner, "🎉 **CONGRATS!** You won the 1000 Pts Lottery!")
                except: pass
                msg += "\n🔥 **DRAW COMPLETED!** Winner selected."
            
            conn.commit()
            await q.edit_message_text(msg)
        else:
            await q.answer("❌ Low Balance! Need 100 Pts.", show_alert=True)
        conn.close()

    elif data == 'confirm_boost':
        conn = get_db_connection()
        cur = conn.cursor()
        cur.execute("SELECT balance, channel_id FROM users WHERE user_id=%s", (user.id,))
        res = cur.fetchone()
        
        if res and res[0] >= 200:
            exp = datetime.now() + timedelta(hours=1)
            cur.execute("UPDATE users SET balance = balance - 200 WHERE user_id=%s", (user.id,))
            cur.execute("INSERT INTO boosted_channels (channel_id, user_id, expires_at) VALUES (%s, %s, %s) ON CONFLICT (channel_id) DO UPDATE SET expires_at = %s", (res[1], user.id, exp, exp))
            conn.commit()
            await q.edit_message_text("🚀 **BOOSTED!**\nYour channel is #1 for 1 Hour.")
        else:
            await q.answer("❌ Low Balance! Need 200 Pts.", show_alert=True)
        conn.close()

    elif data in ['enroll_action', 'unenroll_action']:
        new_status = True if data == 'enroll_action' else False
        conn = get_db_connection()
        cur = conn.cursor()
        cur.execute("UPDATE users SET is_enrolled = %s WHERE user_id = %s", (new_status, user.id))
        conn.commit()
        conn.close()
        state = "✅ Enrolled" if new_status else "🔕 Unenrolled"
        await q.message.reply_text(f"{state} successfully!")
        await show_profile_logic(update, context)

# --- LOGIC HELPERS ---
async def process_registration(update, context, channel_id):
    user = update.effective_user
    yt = get_yt_channel_info(channel_id.split('/')[-1])
    
    if not yt:
        await update.message.reply_text("❌ **Invalid ID!** Public channel required.")
        return

    conn = get_db_connection()
    cur = conn.cursor()
    try:
        cur.execute("UPDATE system_pool SET total_balance = total_balance - 50 WHERE id = 1")
        cur.execute("INSERT INTO users (user_id, username, channel_id, channel_title, pfp_url, balance, total_earned, referrer_id) VALUES (%s, %s, %s, %s, %s, %s, %s, %s)",
            (user.id, user.username, channel_id, yt['title'], yt['thumbnail'], 50, 50, context.user_data.get('referrer_id')))
        
        ref = context.user_data.get('referrer_id')
        if ref:
            cur.execute("UPDATE users SET balance = balance + 50, total_earned = total_earned + 50 WHERE user_id = %s", (ref,))
            try: await context.bot.send_message(ref, "🎉 **Referral Bonus:** +50 Pts!")
            except: pass
        
        conn.commit()
        await update.message.reply_text("✅ **Registered!** +50 Points.", reply_markup=get_persistent_menu())
    except:
        conn.rollback()
        await update.message.reply_text("⚠️ Already Registered.")
    finally:
        cur.close()
        conn.close()

async def claim_bonus_logic(update, context):
    user = update.effective_user
    conn = get_db_connection()
    cur = conn.cursor()
    
    # Check if user did 3 tasks today
    cur.execute("SELECT COUNT(*) FROM subscriptions WHERE subscriber_id=%s AND DATE(created_at) = CURRENT_DATE", (user.id,))
    tasks_today = cur.fetchone()[0]
    
    if tasks_today < 3:
        await update.message.reply_text(f"🔒 **Locked!**\nComplete 3 tasks today to unlock.\nDone: {tasks_today}/3")
        conn.close()
        return

    cur.execute("SELECT daily_bonus_date, streak_count FROM users WHERE user_id = %s", (user.id,))
    res = cur.fetchone()
    today = date.today()
    last, streak = res[0], res[1]
    
    if last == today:
        msg = "⚠️ **Already Claimed!**"
    else:
        if last == today - timedelta(days=1): streak += 1
        else: streak = 1
            
        bonus = 15
        extra = 50 if streak == 7 else 0
        if streak > 7: streak = 1 # Reset after 7 days loop
            
        total = bonus + extra
        cur.execute("UPDATE users SET balance = balance + %s, daily_bonus_date = %s, streak_count = %s WHERE user_id = %s", (total, today, streak, user.id))
        conn.commit()
        msg = f"🎁 **Daily Bonus:** +{bonus} Pts\n🔥 **Streak:** {streak}/7"
        if extra: msg += f"\n✨ **BIG BONUS:** +{extra} Pts!"
        
    conn.close()
    if update.callback_query: await update.callback_query.message.reply_text(msg)
    else: await update.message.reply_text(msg)

async def lottery_logic(update, context):
    conn = get_db_connection()
    cur = conn.cursor()
    cur.execute("SELECT COUNT(DISTINCT user_id) FROM lottery_tickets")
    count = cur.fetchone()[0]
    conn.close()
    
    msg = (f"🎟️ **LOTTERY (Win 1000 Pts)**\n━━━━━━━━━━━━━━━━\n"
           f"💰 Ticket Cost: **100 Pts**\n👥 Participants: **{count}/12**\n"
           f"⚡ Winner gets 1000 Pts instantly when 12 people join!")
    
    kb = InlineKeyboardMarkup([[InlineKeyboardButton("🎟️ Buy Ticket (-100)", callback_data='buy_lottery_ticket')]])
    
    if update.callback_query: await update.callback_query.message.reply_text(msg, reply_markup=kb, parse_mode='Markdown')
    else: await update.message.reply_text(msg, reply_markup=kb, parse_mode='Markdown')

async def boost_channel_logic(update, context):
    msg = ("🚀 **BOOST CHANNEL**\n━━━━━━━━━━━━━━━━\n"
           "Get #1 Priority for 1 Hour.\n"
           "💰 **Cost:** 200 Points\n"
           "⚡ *Effective immediately.*")
    kb = InlineKeyboardMarkup([[InlineKeyboardButton("⚡ Confirm Boost (-200)", callback_data='confirm_boost')]])
    if update.callback_query: await update.callback_query.message.reply_text(msg, reply_markup=kb, parse_mode='Markdown')
    else: await update.message.reply_text(msg, reply_markup=kb, parse_mode='Markdown')

async def show_leaderboard_logic(update, context):
    conn = get_db_connection()
    cur = conn.cursor()
    cur.execute("SELECT channel_title, total_earned FROM users ORDER BY total_earned DESC LIMIT 10")
    txt = "🏆 **TOP 10**\n" + "\n".join([f"{i+1}. {r[0]} - {r[1]}" for i, r in enumerate(cur.fetchall())])
    conn.close()
    if update.callback_query: await update.callback_query.message.reply_text(txt)
    else: await update.message.reply_text(txt)

async def buy_info_logic(update, context):
    txt = f"💎 **BUY POINTS**\n100Tk = 350Pts\n500Tk = 2000Pts\n\nSend to `{BKASH_NUMBER}` & msg Admin."
    if update.callback_query: await update.callback_query.message.reply_text(txt, parse_mode='Markdown')
    else: await update.message.reply_text(txt, parse_mode='Markdown')

async def refer_logic(update, context):
    link = f"https://t.me/{context.bot.username}?start={update.effective_user.id}"
    txt = f"🤝 **INVITE**\n`{link}`\n🎁 Both get 50 Pts!"
    if update.callback_query: await update.callback_query.message.reply_text(txt, parse_mode='Markdown')
    else: await update.message.reply_text(txt, parse_mode='Markdown')

async def show_stats(update, context):
    conn = get_db_connection()
    cur = conn.cursor()
    cur.execute("SELECT COUNT(*), SUM(balance) FROM users")
    res = cur.fetchone()
    conn.close()
    await update.message.reply_text(f"📊 Users: {res[0]} | Points: {res[1]}")

async def process_coupon(update, context, code):
    user = update.effective_user
    conn = get_db_connection()
    cur = conn.cursor()
    cur.execute("SELECT amount, usage_limit, used_count FROM coupons WHERE code=%s", (code,))
    c = cur.fetchone()
    if c and c[2] < c[1]:
        cur.execute("SELECT 1 FROM coupon_usage WHERE user_id=%s AND code=%s", (user.id, code))
        if not cur.fetchone():
            cur.execute("UPDATE users SET balance=balance+%s WHERE user_id=%s", (c[0], user.id))
            cur.execute("UPDATE coupons SET used_count=used_count+1 WHERE code=%s", (code,))
            cur.execute("INSERT INTO coupon_usage VALUES (%s, %s)", (user.id, code))
            conn.commit()
            await update.message.reply_text(f"🎉 +{c[0]} Points!")
        else: await update.message.reply_text("⚠️ Used!")
    else: await update.message.reply_text("❌ Invalid/Expired.")
    conn.close()

# --- ADMIN COMMANDS ---
async def admin_cmds(update: Update, context: ContextTypes.DEFAULT_TYPE):
    if update.effective_user.id != ADMIN_ID: return
    cmd, args = update.message.text.split()[0], context.args
    conn = get_db_connection()
    cur = conn.cursor()
    try:
        if cmd == "/add_priority":
            cur.execute("INSERT INTO priority_channels VALUES (%s) ON CONFLICT DO NOTHING", (args[0],))
            await update.message.reply_text("✅ Priority Added")
        elif cmd == "/create_coupon":
            cur.execute("INSERT INTO coupons VALUES (%s, %s, %s)", (args[0], int(args[1]), int(args[2])))
            await update.message.reply_text("✅ Coupon Created")
        elif cmd == "/add":
            cur.execute("UPDATE users SET balance = balance + %s WHERE user_id = %s", (int(args[1]), int(args[0])))
            await update.message.reply_text("✅ Points Added")
        elif cmd == "/broadcast":
            cur.execute("SELECT user_id FROM users")
            for u in cur.fetchall():
                try: await context.bot.send_message(u[0], f"📢 **NOTICE**\n{' '.join(args)}", parse_mode='Markdown')
                except: pass
            await update.message.reply_text("✅ Sent")
        conn.commit()
    except Exception as e: await update.message.reply_text(f"Error: {e}")
    conn.close()

async def user_transfer(update: Update, context: ContextTypes.DEFAULT_TYPE):
    try:
        sender, target, amt = update.effective_user.id, int(context.args[0]), int(context.args[1])
        if amt < 10: return
        conn = get_db_connection()
        cur = conn.cursor()
        cur.execute("SELECT balance FROM users WHERE user_id = %s", (sender,))
        res = cur.fetchone()
        if res and res[0] >= amt:
            tax = int(amt * 0.1)
            cur.execute("UPDATE users SET balance = balance - %s WHERE user_id = %s", (amt, sender))
            cur.execute("UPDATE users SET balance = balance + %s WHERE user_id = %s", (amt-tax, target))
            cur.execute("UPDATE system_pool SET total_balance = total_balance + %s WHERE id = 1", (tax,))
            conn.commit()
            await update.message.reply_text(f"✅ Sent {amt-tax} Pts to {target} (Tax: {tax})")
        else: await update.message.reply_text("❌ Low Balance")
        conn.close()
    except: await update.message.reply_text("Use: /transfer ID AMOUNT")

# --- MAIN ---
if __name__ == '__main__':
    keep_alive()
    app = ApplicationBuilder().token(BOT_TOKEN).build()
    
    # Handlers
    app.add_handler(CommandHandler("start", start))
    app.add_handler(CommandHandler("transfer", user_transfer))
    for c in ["add_priority", "create_coupon", "add", "broadcast"]:
        app.add_handler(CommandHandler(c.strip("/"), admin_cmds))
        
    app.add_handler(MessageHandler(filters.TEXT & (~filters.COMMAND), handle_message))
    app.add_handler(CallbackQueryHandler(callback_handler))
    
    print("YouTube Growth Pro is Live...")
    app.run_polling()
