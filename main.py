import logging
import asyncio
import os
import random
from datetime import date, datetime
from telegram import Update, InlineKeyboardButton, InlineKeyboardMarkup, ReplyKeyboardMarkup, KeyboardButton
from telegram.ext import ApplicationBuilder, ContextTypes, CommandHandler, CallbackQueryHandler, MessageHandler, filters
from googleapiclient.discovery import build
import psycopg2
import requests
from dotenv import load_dotenv

load_dotenv()

# ==========================================
# 👇 CONFIGURATION (SECURE MODE) 👇
# ==========================================

BOT_TOKEN = os.getenv("BOT_TOKEN")
ADMIN_ID = int(os.getenv("ADMIN_ID"))
YOUTUBE_API_KEY = os.getenv("YOUTUBE_API_KEY")
DB_URI = os.getenv("DB_URI")
BKASH_NUMBER = os.getenv("BKASH_NUMBER")

BANNER_IMG = "https://cdn.pixabay.com/photo/2016/11/19/14/00/code-1839406_1280.jpg"

# ==========================================

logging.basicConfig(format='%(asctime)s - %(name)s - %(levelname)s - %(message)s', level=logging.INFO)

# --- DATABASE CONNECTION ---
def get_db_connection():
    try:
        conn = psycopg2.connect(DB_URI)
        return conn
    except Exception as e:
        print(f"DB Error: {e}")
        return None

# --- YOUTUBE API HELPERS ---
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
    except Exception as e:
        print(f"YT API Error: {e}")
        return None

def check_subscription(user_channel_id, target_channel_id):
    try:
        youtube = build('youtube', 'v3', developerKey=YOUTUBE_API_KEY)
        req = youtube.subscriptions().list(part="snippet", channelId=user_channel_id, forChannelId=target_channel_id)
        res = req.execute()
        return len(res.get("items", [])) > 0
    except:
        return False

# --- KEYBOARDS (MENUS) ---
def get_main_menu_keyboard():
    keyboard = [
        [KeyboardButton("🚀 Earn Points"), KeyboardButton("👤 My Profile")],
        [KeyboardButton("🎁 Daily Bonus"), KeyboardButton("🏆 Leaderboard")],
        [KeyboardButton("💎 Buy Points"), KeyboardButton("🤝 Refer & Earn")],
        [KeyboardButton("💸 Transfer"), KeyboardButton("🎟️ Redeem Code")],
        [KeyboardButton("📊 Server Stats"), KeyboardButton("🆘 Support")]
    ]
    return ReplyKeyboardMarkup(keyboard, resize_keyboard=True)

# --- START & REGISTRATION ---
async def start(update: Update, context: ContextTypes.DEFAULT_TYPE):
    user = update.effective_user
    args = context.args
    referrer_id = None
    if args:
        try:
            referrer_id = int(args[0])
            if referrer_id == user.id: referrer_id = None
        except: pass

    conn = get_db_connection()
    if not conn: return
    cur = conn.cursor()
    
    cur.execute("SELECT is_banned FROM users WHERE user_id = %s", (user.id,))
    res = cur.fetchone()
    
    if res:
        if res[0]: 
            await update.message.reply_text("⛔ **ACCOUNT BANNED**\nPlease contact admin.\n*আপনার অ্যাকাউন্টটি ব্যান করা হয়েছে।*")
        else:
            await update.message.reply_text("👋 **Welcome Back!**\nSelect an option from the menu.\n*মেইন মেনু থেকে কাজ শুরু করুন।*", reply_markup=get_main_menu_keyboard(), parse_mode='Markdown')
    else:
        # 👇 আপডেটেড নাম এখানে 👇
        welcome_text = (
            f"🎉 **WELCOME TO YOUTUBE GROWTH PRO**\n"
            "━━━━━━━━━━━━━━━━━━\n"
            f"Hello {user.first_name}, welcome to our premium community.\n"
            f"*আমাদের প্রফেশনাল কমিউনিটিতে আপনাকে স্বাগতম।*\n\n"
            "🎁 **Bonus:** `+75 Points`\n"
            "🚀 **Features:** Real Subs, Fast Growth.\n\n"
            "👇 **Send your YouTube Channel ID:**\n"
            "(Example: `UCxxxxxxxxxxxxxxx`)"
        )
        await update.message.reply_photo(photo=BANNER_IMG, caption=welcome_text, parse_mode='Markdown')
        context.user_data['waiting_for_channel'] = True
        if referrer_id: context.user_data['referrer_id'] = referrer_id
    
    cur.close()
    conn.close()

async def handle_text_input(update: Update, context: ContextTypes.DEFAULT_TYPE):
    text = update.message.text
    user = update.effective_user
    
    if text == "🚀 Earn Points": await earn_points_menu(update, context)
    elif text == "👤 My Profile": await show_profile(update, context)
    elif text == "🎁 Daily Bonus": await claim_daily_bonus(update, context)
    elif text == "🏆 Leaderboard": await show_leaderboard(update, context)
    elif text == "💎 Buy Points": await buy_points_info(update, context)
    elif text == "🤝 Refer & Earn": await refer_info(update, context)
    elif text == "💸 Transfer": await transfer_info(update, context)
    elif text == "🎟️ Redeem Code": 
        await update.message.reply_text("🎟️ **REDEEM COUPON**\nEnter your coupon code below:\n*আপনার কুপন কোডটি নিচে লিখুন:*", parse_mode='Markdown')
        context.user_data['waiting_for_coupon'] = True
    elif text == "📊 Server Stats": await show_server_stats(update, context)
    elif text == "🆘 Support": await update.message.reply_text("📞 **SUPPORT CENTER**\nContact Admin: @YourAdminUsername\n*যেকোনো সমস্যায় অ্যাডমিনকে মেসেজ দিন।*", parse_mode='Markdown')
    
    elif context.user_data.get('waiting_for_coupon'):
        await process_coupon(update, context, text.strip())
        context.user_data['waiting_for_coupon'] = False
        
    elif context.user_data.get('waiting_for_channel'):
        channel_id = text
        if "channel/" in text:
            try: channel_id = text.split("channel/")[-1].split("/")[0].split("?")[0]
            except: channel_id = text
        
        yt_info = get_yt_channel_info(channel_id)
        if not yt_info:
            await update.message.reply_text("❌ **Invalid Channel ID!**\nPlease send a valid public channel ID.\n*সঠিক আইডি দিন অথবা আপনার চ্যানেল পাবলিক আছে কি না দেখুন।*")
            return

        conn = get_db_connection()
        cur = conn.cursor()
        try:
            cur.execute("UPDATE system_pool SET total_balance = total_balance - 75 WHERE id = 1")
            cur.execute(
                "INSERT INTO users (user_id, username, channel_id, channel_title, pfp_url, balance, total_earned, referrer_id) VALUES (%s, %s, %s, %s, %s, %s, %s, %s)",
                (user.id, user.username, channel_id, yt_info['title'], yt_info['thumbnail'], 75, 75, context.user_data.get('referrer_id'))
            )
            ref_id = context.user_data.get('referrer_id')
            if ref_id:
                cur.execute("UPDATE users SET balance = balance + 75, total_earned = total_earned + 75 WHERE user_id = %s", (ref_id,))
                cur.execute("UPDATE system_pool SET total_balance = total_balance - 75 WHERE id = 1")
                try: await context.bot.send_message(ref_id, "🎉 **Referral Bonus:** You got 75 Points!\n*বন্ধু জয়েন করায় ৭৫ পয়েন্ট পেয়েছেন!*")
                except: pass
            
            conn.commit()
            await update.message.reply_text("✅ **Registration Successful!**\n75 Points Added.\n*রেজিস্ট্রেশন সফল! ৭৫ পয়েন্ট যোগ হয়েছে।*", reply_markup=get_main_menu_keyboard(), parse_mode='Markdown')
        except:
            conn.rollback()
            await update.message.reply_text("⚠️ **Already Registered!**\n*আপনি ইতিমধ্যে রেজিস্টার্ড।*")
        finally:
            cur.close()
            conn.close()
            context.user_data['waiting_for_channel'] = False

# --- FEATURE FUNCTIONS ---

async def show_profile(update: Update, context: ContextTypes.DEFAULT_TYPE):
    user = update.effective_user
    conn = get_db_connection()
    cur = conn.cursor()
    cur.execute("SELECT balance, channel_id, warnings, total_earned, total_spent, gained_subs, channel_title, pfp_url FROM users WHERE user_id = %s", (user.id,))
    res = cur.fetchone()
    cur.close()
    conn.close()

    if res:
        balance, cid, warns, earned, spent, gained, c_title, pfp = res
        yt_info = get_yt_channel_info(cid)
        sub_count = yt_info['subs'] if yt_info else "N/A"
        display_pfp = pfp if pfp else BANNER_IMG
        
        status = "✅ Active" if warns < 3 else "⚠️ At Risk"
        membership = "VIP Member" if spent > 2000 else "Free Member"
        
        caption = (
            f"👤 **MY PROFILE**\n"
            f"━━━━━━━━━━━━━━━━━━\n"
            f"📛 **Name:** {c_title}\n"
            f"🆔 **ID:** `{user.id}`\n"
            f"💎 **Rank:** {membership}\n"
            f"━━━━━━━━━━━━━━━━━━\n"
            f"📊 **STATISTICS**\n"
            f"🔴 **Live Subs:** `{sub_count}`\n"
            f"🚀 **Bot Gained:** `{gained}`\n"
            f"━━━━━━━━━━━━━━━━━━\n"
            f"💰 **WALLET**\n"
            f"💳 **Balance:** `{balance}` Pts\n"
            f"📈 **Lifetime:** Earned `{earned}` | Spent `{spent}`\n"
            f"━━━━━━━━━━━━━━━━━━\n"
            f"⚠️ **Status:** {status} ({warns}/3)"
        )
        await update.message.reply_photo(photo=display_pfp, caption=caption, parse_mode='Markdown')

async def earn_points_menu(update: Update, context: ContextTypes.DEFAULT_TYPE):
    user = update.effective_user
    conn = get_db_connection()
    cur = conn.cursor()
    
    target_channel = None
    target_uid = 0 # 0 = Priority/Admin Channel
    is_priority = False

    # 1. Check Priority Channels
    cur.execute("SELECT channel_id FROM priority_channels ORDER BY added_at DESC")
    priority_list = cur.fetchall()
    
    for p_channel in priority_list:
        pcid = p_channel[0]
        cur.execute("SELECT 1 FROM subscriptions WHERE subscriber_id = %s AND target_channel_id = %s", (user.id, pcid))
        is_subbed = cur.fetchone()
        cur.execute("SELECT 1 FROM skipped_tasks WHERE user_id = %s AND channel_id = %s", (user.id, pcid))
        is_skipped = cur.fetchone()
        
        cur.execute("SELECT channel_id FROM users WHERE user_id = %s", (user.id,))
        my_cid_res = cur.fetchone()
        my_cid = my_cid_res[0] if my_cid_res else ""

        if not is_subbed and not is_skipped and pcid != my_cid:
            target_channel = pcid
            is_priority = True
            break
    
    # 2. Check Regular Channels
    if not target_channel:
        cur.execute(
            """
            SELECT user_id, channel_id FROM users 
            WHERE user_id != %s 
            AND balance >= 15 
            AND channel_id NOT IN (SELECT target_channel_id FROM subscriptions WHERE subscriber_id = %s)
            AND channel_id NOT IN (SELECT channel_id FROM skipped_tasks WHERE user_id = %s)
            ORDER BY RANDOM() LIMIT 1
            """,
            (user.id, user.id, user.id)
        )
        regular = cur.fetchone()
        if regular:
            target_uid, target_channel = regular

    cur.close()
    conn.close()

    if target_channel:
        yt_info = get_yt_channel_info(target_channel)
        title = yt_info['title'] if yt_info else "YouTube Channel"
        thumb = yt_info['thumbnail'] if yt_info else BANNER_IMG
        
        context.user_data['task_target_uid'] = target_uid
        context.user_data['task_target_cid'] = target_channel
        context.user_data['is_priority'] = is_priority

        caption = (
            f"📋 **NEW TASK AVAILABLE**\n"
            f"━━━━━━━━━━━━━━━━━━\n"
            f"Subscribe to this channel to earn 10 Points.\n"
            f"*পয়েন্ট পেতে নিচের চ্যানেলটি সাবস্ক্রাইব করুন।*\n\n"
            f"📺 **Channel:** {title}\n"
            f"🎁 **Reward:** 10 Points\n"
            f"━━━━━━━━━━━━━━━━━━\n"
            f"⚠️ *Note: Unsubscribing later will cost 30 Points.*"
        )
        kb = [
            [InlineKeyboardButton("📺 Subscribe Now ↗️", url=f"https://www.youtube.com/channel/{target_channel}")],
            [InlineKeyboardButton("✅ Verify & Claim", callback_data='verify_task')],
            [InlineKeyboardButton("⏭️ Skip (-1 Pt)", callback_data='skip_task'), InlineKeyboardButton("🚩 Report", callback_data='report_task')]
        ]
        
        await update.message.reply_photo(photo=thumb, caption=caption, reply_markup=InlineKeyboardMarkup(kb), parse_mode='Markdown')
    else:
        await update.message.reply_text("❌ **No Tasks Available!**\nPlease try again later.\n*বর্তমানে কোনো চ্যানেল পাওয়া যাচ্ছে না।*")

async def button_handler(update: Update, context: ContextTypes.DEFAULT_TYPE):
    query = update.callback_query
    await query.answer()
    data = query.data
    user = query.from_user

    if data == 'skip_task':
        cid = context.user_data.get('task_target_cid')
        if cid:
            conn = get_db_connection()
            cur = conn.cursor()
            cur.execute("INSERT INTO skipped_tasks (user_id, channel_id) VALUES (%s, %s) ON CONFLICT DO NOTHING", (user.id, cid))
            cur.execute("UPDATE users SET balance = balance - 1 WHERE user_id = %s", (user.id,))
            conn.commit()
            cur.close()
            conn.close()
            await query.edit_message_caption("⏭️ **Task Skipped!** (1 Point deducted)")
    
    elif data == 'report_task':
        cid = context.user_data.get('task_target_cid')
        await context.bot.send_message(ADMIN_ID, f"🚨 **REPORT:**\nUser {user.id} reported Channel {cid}")
        await query.edit_message_caption("🚩 **Reported!** Thanks for helping us.\n*রিপোর্ট করার জন্য ধন্যবাদ।*")

    elif data == 'verify_task':
        target_uid = context.user_data.get('task_target_uid')
        target_cid = context.user_data.get('task_target_cid')
        is_priority = context.user_data.get('is_priority')
        
        if not target_cid: return

        conn = get_db_connection()
        cur = conn.cursor()
        cur.execute("SELECT channel_id FROM users WHERE user_id = %s", (user.id,))
        my_res = cur.fetchone()
        if not my_res: return
        my_cid = my_res[0]

        is_subbed = check_subscription(my_cid, target_cid)

        if is_subbed:
            try:
                # 1. Earner Gets 10
                cur.execute("UPDATE users SET balance = balance + 10, total_earned = total_earned + 10 WHERE user_id = %s", (user.id,))
                
                # 2. Spender Loses 15 (Except Priority)
                if not is_priority and target_uid != 0:
                    cur.execute("UPDATE users SET balance = balance - 15, total_spent = total_spent + 15, gained_subs = gained_subs + 1 WHERE user_id = %s", (target_uid,))
                    cur.execute("UPDATE system_pool SET total_balance = total_balance + 5 WHERE id = 1") 
                
                # 3. Log
                cur.execute("INSERT INTO subscriptions (subscriber_id, target_channel_id, target_user_id) VALUES (%s, %s, %s)", (user.id, target_cid, target_uid))
                
                conn.commit()
                await query.edit_message_caption("🎉 **Success!** 10 Points Added.")
            except Exception as e:
                conn.rollback()
                print(e)
        else:
            await query.message.reply_text("❌ **Verification Failed!**\nDid you subscribe? Is your subscription list public?\n*সাবস্ক্রাইব করা হয়নি বা লিস্ট পাবলিক নয়।*")
        cur.close()
        conn.close()

# --- OTHER HANDLERS ---
async def claim_daily_bonus(update: Update, context: ContextTypes.DEFAULT_TYPE):
    user = update.effective_user
    conn = get_db_connection()
    cur = conn.cursor()
    cur.execute("SELECT daily_bonus_date FROM users WHERE user_id = %s", (user.id,))
    res = cur.fetchone()
    today = date.today()
    if res and res[0] == today:
        await update.message.reply_text("⚠️ **Already Claimed!**\nCome back tomorrow.\n*আজকের বোনাস আপনি নিয়ে ফেলেছেন।*")
    else:
        bonus = 20
        cur.execute("UPDATE users SET balance = balance + %s, total_earned = total_earned + %s, daily_bonus_date = %s WHERE user_id = %s", (bonus, bonus, today, user.id))
        cur.execute("UPDATE system_pool SET total_balance = total_balance - %s WHERE id = 1", (bonus,))
        conn.commit()
        await update.message.reply_text(f"🎁 **Daily Bonus!**\n{bonus} Points Added.\n*{bonus} পয়েন্ট যোগ হয়েছে।*")
    cur.close()
    conn.close()

async def show_leaderboard(update: Update, context: ContextTypes.DEFAULT_TYPE):
    conn = get_db_connection()
    cur = conn.cursor()
    cur.execute("SELECT channel_title, total_earned FROM users ORDER BY total_earned DESC LIMIT 10")
    leaders = cur.fetchall()
    cur.close()
    conn.close()
    text = "🏆 **TOP 10 EARNERS**\n━━━━━━━━━━━━━━━━━━\n"
    for idx, (name, score) in enumerate(leaders, 1):
        medal = "🥇" if idx==1 else "🥈" if idx==2 else "🥉" if idx==3 else f"{idx}."
        text += f"{medal} {name or 'Unknown'} - {score} Pts\n"
    await update.message.reply_text(text, parse_mode='Markdown')

async def buy_points_info(update: Update, context: ContextTypes.DEFAULT_TYPE):
    text = (
        "💎 **PREMIUM STORE**\n"
        "Buy points to grow faster:\n"
        "*দ্রুত সাবস্ক্রাইবার পেতে পয়েন্ট কিনুন:*\n\n"
        "📦 **Starter:** 100 Tk = 350 Points\n"
        "📦 **Pro:** 500 Tk = 2000 Points\n"
        "📦 **VIP:** 1000 Tk = 4500 Points\n\n"
        f"💳 **bKash:** `{BKASH_NUMBER}`\n"
        "Send money and send screenshot to Admin."
    )
    await update.message.reply_text(text, parse_mode='Markdown')

async def transfer_info(update: Update, context: ContextTypes.DEFAULT_TYPE):
    await update.message.reply_text("💸 **TRANSFER**\nUse command:\n`/transfer [User_ID] [Amount]`\n\nExample: `/transfer 12345 100`\nTax: 10%", parse_mode='Markdown')

async def refer_info(update: Update, context: ContextTypes.DEFAULT_TYPE):
    link = f"https://t.me/{context.bot.username}?start={update.effective_user.id}"
    await update.message.reply_text(f"🤝 **REFER & EARN**\n\n🔗 **Your Link:**\n`{link}`\n\n🎁 Bonus: Both get 75 Points!", parse_mode='Markdown')

async def show_server_stats(update: Update, context: ContextTypes.DEFAULT_TYPE):
    conn = get_db_connection()
    cur = conn.cursor()
    cur.execute("SELECT COUNT(*), SUM(balance) FROM users")
    res = cur.fetchone()
    cur.close()
    conn.close()
    await update.message.reply_text(f"📊 **STATS:** Users: {res[0]} | Points: {res[1]}")

async def process_coupon(update: Update, context: ContextTypes.DEFAULT_TYPE, code: str):
    user = update.effective_user
    conn = get_db_connection()
    cur = conn.cursor()
    cur.execute("SELECT amount, usage_limit, used_count FROM coupons WHERE code = %s", (code,))
    c = cur.fetchone()
    if c:
        cur.execute("SELECT 1 FROM coupon_usage WHERE user_id = %s AND code = %s", (user.id, code))
        if cur.fetchone(): await update.message.reply_text("⚠️ Used!")
        elif c[2] >= c[1]: await update.message.reply_text("⚠️ Limit reached!")
        else:
            cur.execute("UPDATE users SET balance = balance + %s WHERE user_id = %s", (c[0], user.id))
            cur.execute("UPDATE coupons SET used_count = used_count + 1 WHERE code = %s", (code,))
            cur.execute("INSERT INTO coupon_usage VALUES (%s, %s)", (user.id, code))
            conn.commit()
            await update.message.reply_text(f"🎉 **Redeemed!** +{c[0]} Points.")
    else: await update.message.reply_text("❌ Invalid Code.")
    conn.close()

# --- ADMIN COMMANDS ---
async def admin_cmds(update: Update, context: ContextTypes.DEFAULT_TYPE):
    if update.effective_user.id != ADMIN_ID: return
    cmd = update.message.text.split()[0]
    args = context.args
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
            msg = " ".join(args)
            cur.execute("SELECT user_id FROM users")
            for u in cur.fetchall():
                try: await context.bot.send_message(u[0], f"📢 **NOTICE**\n{msg}", parse_mode='Markdown')
                except: pass
            await update.message.reply_text("✅ Broadcast Sent")
        conn.commit()
    except Exception as e: await update.message.reply_text(f"Error: {e}")
    conn.close()

async def user_transfer(update: Update, context: ContextTypes.DEFAULT_TYPE):
    try:
        sender, target, amt = update.effective_user.id, int(context.args[0]), int(context.args[1])
        if amt < 10: 
            await update.message.reply_text("❌ Minimum 10 Points.")
            return
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

if __name__ == '__main__':
    app = ApplicationBuilder().token(BOT_TOKEN).build()
    
    # 1. Menu & Feature Commands
    app.add_handler(CommandHandler("start", start))
    app.add_handler(CommandHandler("earn", earn_points_menu))
    app.add_handler(CommandHandler("profile", show_profile))
    app.add_handler(CommandHandler("bonus", claim_daily_bonus))
    app.add_handler(CommandHandler("top", show_leaderboard))
    app.add_handler(CommandHandler("buy", buy_points_info))
    app.add_handler(CommandHandler("refer", refer_info))
    app.add_handler(CommandHandler("transfer", user_transfer))
    app.add_handler(CommandHandler("stats", show_server_stats))
    
    # 2. Support
    app.add_handler(CommandHandler("support", lambda u,c: u.message.reply_text("📞 Admin: @YourAdminUsername")))
    
    # 3. Admin Commands
    for acmd in ["add_priority", "create_coupon", "add", "broadcast"]:
        app.add_handler(CommandHandler(acmd.strip("/"), admin_cmds))

    # 4. Text & Button Handlers
    app.add_handler(MessageHandler(filters.TEXT & (~filters.COMMAND), handle_text_input))
    app.add_handler(CallbackQueryHandler(button_handler))
    
    print("YouTube Growth Pro is Live...")
    app.run_polling()
