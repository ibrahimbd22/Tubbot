import logging
import asyncio
from telegram import Update, InlineKeyboardButton, InlineKeyboardMarkup
from telegram.ext import ApplicationBuilder, ContextTypes, CommandHandler, CallbackQueryHandler, MessageHandler, filters
from googleapiclient.discovery import build
import psycopg2
from datetime import datetime, timedelta

# ==========================================
# 👇 আপনার দেওয়া তথ্যগুলো বসানো হয়েছে 👇
# ==========================================

BOT_TOKEN = "8558760249:AAGETUnIesTK15Gd3AajClakNd7ZQ72fDRU"
ADMIN_ID = 5788504224
YOUTUBE_API_KEY = "AIzaSyCm-_pm6_XPQ6DN7v3GAf6dozFXuOyv0ek"
DB_URI = "postgresql://postgres.uqyphcmwfwwgxkwcfvhr:TubeBotPass2025@aws-1-ap-southeast-1.pooler.supabase.com:6543/postgres"
BKASH_NUMBER = "017XXXXXXXX"  # এখানে পরে আপনার বিকাশ নাম্বার বসিয়ে দিয়েন

# ==========================================

# লগিং সেটআপ
logging.basicConfig(
    format='%(asctime)s - %(name)s - %(levelname)s - %(message)s',
    level=logging.INFO
)

# ডাটাবেস কানেকশন ফাংশন
def get_db_connection():
    try:
        conn = psycopg2.connect(DB_URI)
        return conn
    except Exception as e:
        print(f"Database Connection Error: {e}")
        return None

# --- ইউটিউব হেল্পার ফাংশন ---
def check_youtube_sub(user_channel_id, target_channel_id):
    """চেক করে ইউজার সত্যি সাবস্ক্রাইব করেছে কি না"""
    try:
        youtube = build('youtube', 'v3', developerKey=YOUTUBE_API_KEY)
        request = youtube.subscriptions().list(
            part="snippet",
            channelId=user_channel_id,
            forChannelId=target_channel_id
        )
        response = request.execute()
        return len(response.get("items", [])) > 0
    except Exception as e:
        print(f"YT API Error: {e}")
        return False

# --- কমান্ড হ্যান্ডলার ---

async def start(update: Update, context: ContextTypes.DEFAULT_TYPE):
    user = update.effective_user
    args = context.args
    referrer_id = None
    
    # রেফারেল হ্যান্ডলিং
    if args:
        try:
            referrer_id = int(args[0])
            if referrer_id == user.id: referrer_id = None
        except:
            pass

    conn = get_db_connection()
    if not conn:
        await update.message.reply_text("⚠️ সার্ভার মেইনটেনেন্সে আছে। কিছুক্ষণ পর চেষ্টা করুন।")
        return

    cur = conn.cursor()
    
    # ইউজার আছে কি না চেক
    cur.execute("SELECT * FROM users WHERE user_id = %s", (user.id,))
    existing_user = cur.fetchone()
    
    if existing_user:
        await show_menu(update, context)
    else:
        # নতুন ইউজার হলে চ্যানেল আইডি চাইবে
        await update.message.reply_text(
            f"👋 স্বাগতম {user.first_name}!\n\n"
            "আমাদের কমিউনিটিতে জয়েন করতে আপনার **YouTube Channel ID** টি দিন।\n"
            "উদাহরণ: `UCxxxxxxxxxxxxxxx`\n\n"
            "(আপনার চ্যানেলে গিয়ে About সেকশন থেকে Share > Copy Link করে এখানে দিন)"
        )
        context.user_data['waiting_for_channel'] = True
        if referrer_id:
            context.user_data['referrer_id'] = referrer_id
            
    cur.close()
    conn.close()

async def handle_text(update: Update, context: ContextTypes.DEFAULT_TYPE):
    # চ্যানেল আইডি ইনপুট নেওয়া
    if context.user_data.get('waiting_for_channel'):
        channel_text = update.message.text.strip()
        
        # চ্যানেল আইডি বের করা (সিম্পল লজিক)
        channel_id = channel_text
        if "channel/" in channel_text:
            try:
                channel_id = channel_text.split("channel/")[-1].split("/")[0].split("?")[0]
            except:
                channel_id = channel_text

        user = update.effective_user
        referrer_id = context.user_data.get('referrer_id')
        
        conn = get_db_connection()
        if not conn: return
        cur = conn.cursor()
        
        try:
            # 1. সিস্টেম পুল থেকে ৭৫ পয়েন্ট কমানো
            cur.execute("UPDATE system_pool SET total_balance = total_balance - 75 WHERE id = 1")
            
            # 2. ইউজার তৈরি করা
            cur.execute(
                "INSERT INTO users (user_id, username, channel_id, balance, referrer_id) VALUES (%s, %s, %s, %s, %s)",
                (user.id, user.username, channel_id, 75, referrer_id)
            )
            
            # 3. রেফারার বোনাস (যদি থাকে)
            if referrer_id:
                cur.execute("UPDATE users SET balance = balance + 75 WHERE user_id = %s", (referrer_id,))
                cur.execute("UPDATE system_pool SET total_balance = total_balance - 75 WHERE id = 1")
                try:
                    await context.bot.send_message(referrer_id, "🎉 আপনি একজনকে রেফার করে ৭৫ পয়েন্ট পেয়েছেন!")
                except:
                    pass

            conn.commit()
            await update.message.reply_text(
                "✅ রেজিস্ট্রেশন সফল! আপনি ৭৫ পয়েন্ট বোনাস পেয়েছেন।",
            )
            await show_menu(update, context)
            
        except Exception as e:
            conn.rollback()
            await update.message.reply_text("⚠️ সমস্যা হয়েছে বা এই চ্যানেল/ইউজার ইতিমধ্যে নিবন্ধিত।")
            print(e)
        finally:
            cur.close()
            conn.close()
            context.user_data['waiting_for_channel'] = False
    else:
        await show_menu(update, context)

async def show_menu(update: Update, context: ContextTypes.DEFAULT_TYPE):
    keyboard = [
        [InlineKeyboardButton("💰 Earn Points (কাজ করুন)", callback_data='earn')],
        [InlineKeyboardButton("👤 My Profile", callback_data='profile'),
         InlineKeyboardButton("💳 Buy Points", callback_data='buy')],
        [InlineKeyboardButton("🔗 Refer & Earn", callback_data='refer')]
    ]
    reply_markup = InlineKeyboardMarkup(keyboard)
    msg_text = "🏠 **Main Menu**\nআপনার অপশন বেছে নিন:"
    
    if update.callback_query:
        await update.callback_query.edit_message_text(msg_text, reply_markup=reply_markup, parse_mode='Markdown')
    else:
        await update.message.reply_text(msg_text, reply_markup=reply_markup, parse_mode='Markdown')

# --- বাটন হ্যান্ডলার (সব অ্যাকশন এখানে) ---

async def button_callback(update: Update, context: ContextTypes.DEFAULT_TYPE):
    query = update.callback_query
    await query.answer()
    user = query.from_user
    data = query.data
    
    conn = get_db_connection()
    if not conn:
        await query.message.reply_text("Database Error")
        return
    cur = conn.cursor()

    if data == 'profile':
        cur.execute("SELECT balance, channel_id, warnings FROM users WHERE user_id = %s", (user.id,))
        res = cur.fetchone()
        if res:
            text = (
                f"👤 **আপনার প্রোফাইল**\n\n"
                f"💰 ব্যালেন্স: **{res[0]}** পয়েন্ট\n"
                f"📺 চ্যানেল আইডি: `{res[1]}`\n"
                f"⚠️ ওয়ার্নিং: {res[2]}/3\n"
            )
            back_btn = [[InlineKeyboardButton("🔙 Back", callback_data='menu')]]
            await query.edit_message_text(text, parse_mode='Markdown', reply_markup=InlineKeyboardMarkup(back_btn))

    elif data == 'menu':
        await show_menu(update, context)

    elif data == 'refer':
        link = f"https://t.me/{context.bot.username}?start={user.id}"
        text = (
            "🤝 **রেফারেল প্রোগ্রাম**\n\n"
            "বন্ধুদের ইনভাইট করুন এবং দুজনেই জিতুন!\n"
            "🎁 আপনি পাবেন: **৭৫ পয়েন্ট**\n"
            "🎁 বন্ধু পাবে: **৭৫ পয়েন্ট**\n\n"
            f"আপনার লিংক:\n`{link}`"
        )
        back_btn = [[InlineKeyboardButton("🔙 Back", callback_data='menu')]]
        await query.edit_message_text(text, parse_mode='Markdown', reply_markup=InlineKeyboardMarkup(back_btn))

    elif data == 'buy':
        text = (
            "💎 **পয়েন্ট কিনুন (১ টাকা = ৩ পয়েন্ট)**\n\n"
            "• Starter: ১০০ টাকায় ৩৫০ পয়েন্ট\n"
            "• Pro: ৫০০ টাকায় ২০০০ পয়েন্ট\n"
            "• VIP: ১০০০ টাকায় ৪৫০০ পয়েন্ট\n\n"
            f"বিকাশ (Send Money): `{BKASH_NUMBER}`\n\n"
            "টাকা পাঠিয়ে অ্যাডমিনকে স্ক্রিনশট বা TrxID দিন।"
        )
        back_btn = [[InlineKeyboardButton("🔙 Back", callback_data='menu')]]
        await query.edit_message_text(text, parse_mode='Markdown', reply_markup=InlineKeyboardMarkup(back_btn))

    elif data == 'earn':
        # টাস্ক খোঁজা: এমন ইউজার যার ব্যালেন্স ১৫+ এবং আমি তাকে সাবস্ক্রাইব করিনি
        cur.execute(
            """
            SELECT user_id, channel_id FROM users 
            WHERE user_id != %s AND balance >= 15 
            ORDER BY RANDOM() LIMIT 1
            """,
            (user.id,)
        )
        target = cur.fetchone()
        
        if target:
            target_uid, target_cid = target
            context.user_data['task_target_uid'] = target_uid
            context.user_data['task_target_cid'] = target_cid
            
            kb = [
                [InlineKeyboardButton("📺 Subscribe Channel", url=f"https://www.youtube.com/channel/{target_cid}")],
                [InlineKeyboardButton("✅ Verify Task", callback_data='verify_task')],
                [InlineKeyboardButton("🔙 Back", callback_data='menu')]
            ]
            await query.edit_message_text(
                f"👇 এই চ্যানেলটি সাবস্ক্রাইব করুন এবং ১০ পয়েন্ট জিতুন!\nID: `{target_cid}`",
                reply_markup=InlineKeyboardMarkup(kb),
                parse_mode='Markdown'
            )
        else:
            await query.edit_message_text("❌ বর্তমানে কোনো কাজ নেই। কিছুক্ষণ পর চেষ্টা করুন।", 
                                          reply_markup=InlineKeyboardMarkup([[InlineKeyboardButton("🔙 Back", callback_data='menu')]]))

    elif data == 'verify_task':
        target_uid = context.user_data.get('task_target_uid')
        target_cid = context.user_data.get('task_target_cid')
        
        if not target_cid:
            await query.edit_message_text("Error. Try again.")
            cur.close()
            conn.close()
            return

        # আমার চ্যানেল আইডি বের করা
        cur.execute("SELECT channel_id FROM users WHERE user_id = %s", (user.id,))
        res = cur.fetchone()
        
        if not res:
            await query.edit_message_text("User not found.")
            cur.close()
            conn.close()
            return
            
        my_cid = res[0]

        # API কল করে চেক করা
        is_subscribed = check_youtube_sub(my_cid, target_cid)

        if is_subscribed:
            try:
                # ১. চ্যানেল মালিকের থেকে ১৫ কাটা
                cur.execute("UPDATE users SET balance = balance - 15 WHERE user_id = %s", (target_uid,))
                # ২. আর্নারকে ১০ দেওয়া
                cur.execute("UPDATE users SET balance = balance + 10 WHERE user_id = %s", (user.id,))
                # ৩. সিস্টেমে ৫ ফেরত (Recycle)
                cur.execute("UPDATE system_pool SET total_balance = total_balance + 5 WHERE id = 1")
                
                # ৪. সাবস্ক্রিপশন রেকর্ড সেভ (বিচারের জন্য)
                cur.execute(
                    "INSERT INTO subscriptions (subscriber_id, target_channel_id, target_user_id) VALUES (%s, %s, %s)",
                    (user.id, target_cid, target_uid)
                )
                
                conn.commit()
                await query.edit_message_text("✅ অভিনন্দন! টাস্ক কমপ্লিট। ১০ পয়েন্ট যোগ হয়েছে।", 
                                              reply_markup=InlineKeyboardMarkup([[InlineKeyboardButton("More Task", callback_data='earn')]]))
            except Exception as e:
                conn.rollback()
                print(e)
                await query.edit_message_text("Error processing points.")
        else:
            await query.edit_message_text(
                "❌ সাবস্ক্রিপশন পাওয়া যায়নি।\n"
                "দয়া করে নিশ্চিত করুন আপনি সাবস্ক্রাইব করেছেন এবং আপনার 'Subscriptions' প্রাইভেসি 'Public' করা আছে।",
                reply_markup=InlineKeyboardMarkup([[InlineKeyboardButton("Try Again", callback_data='earn')]])
            )

    cur.close()
    conn.close()

# --- এডমিন কমান্ড (পয়েন্ট দেওয়ার জন্য) ---
async def admin_add_points(update: Update, context: ContextTypes.DEFAULT_TYPE):
    user = update.effective_user
    if user.id != ADMIN_ID: return

    try:
        # ব্যবহার: /add user_id amount
        target_id = int(context.args[0])
        amount = int(context.args[1])
        
        conn = get_db_connection()
        if not conn: return
        cur = conn.cursor()
        
        # সিস্টেম পুল থেকে পয়েন্ট নিয়ে ইউজারকে দেওয়া
        cur.execute("UPDATE users SET balance = balance + %s WHERE user_id = %s", (amount, target_id))
        cur.execute("UPDATE system_pool SET total_balance = total_balance - %s WHERE id = 1", (amount,))
        conn.commit()
        conn.close()
        
        await update.message.reply_text(f"✅ সফল! {target_id}-কে {amount} পয়েন্ট দেওয়া হয়েছে।")
        await context.bot.send_message(target_id, f"🎉 অভিনন্দন! অ্যাডমিন আপনাকে {amount} পয়েন্ট পাঠিয়েছে।")
        
    except Exception as e:
        await update.message.reply_text("ব্যবহার: /add <user_id> <amount>")

# --- রান বডি ---
if __name__ == '__main__':
    app = ApplicationBuilder().token(BOT_TOKEN).build()
    
    app.add_handler(CommandHandler("start", start))
    app.add_handler(CommandHandler("add", admin_add_points)) 
    app.add_handler(MessageHandler(filters.TEXT & (~filters.COMMAND), handle_text))
    app.add_handler(CallbackQueryHandler(button_callback))
    
    print("Bot is running...")
    app.run_polling()
