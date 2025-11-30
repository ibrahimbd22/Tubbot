import logging
import asyncio
from telegram import Update, InlineKeyboardButton, InlineKeyboardMarkup
from telegram.ext import ApplicationBuilder, ContextTypes, CommandHandler, CallbackQueryHandler, MessageHandler, filters
from googleapiclient.discovery import build
import psycopg2
from datetime import datetime, timedelta

# ==========================================
# ЁЯСЗ ржЖржкржирж╛рж░ рждржерзНржпржЧрзБрж▓рзЛ ржПржЦрж╛ржирзЗ ржмрж╕рж╛ржи (рж╕рж╛ржмржзрж╛ржирзЗ) ЁЯСЗ
# ==========================================

BOT_TOKEN = "8558760249:AAGETUnIesTK15Gd3AajClakNd7ZQ72fDRU"
ADMIN_ID = 5788504224  # ржЖржкржирж╛рж░ ржЯрзЗрж▓рж┐ржЧрзНрж░рж╛ржо ржЖржЗржбрж┐ (рж╕ржВржЦрзНржпрж╛)
YOUTUBE_API_KEY = "AIzaSyCm-_pm6_XPQ6DN7v3GAf6dozFXuOyv0ek"
DB_URI = "postgresql://postgres:01836204769@db.uqyphcmwfwwgxkwcfvhr.supabase.co:5432/postgres" # postgresql://...
BKASH_NUMBER = "01881251107" # ржЖржкржирж╛рж░ ржмрж┐ржХрж╛рж╢ ржирж╛ржорзНржмрж╛рж░

# ==========================================

# рж▓ржЧрж┐ржВ рж╕рзЗржЯржЖржк
logging.basicConfig(
    format='%(asctime)s - %(name)s - %(levelname)s - %(message)s',
    level=logging.INFO
)

# ржбрж╛ржЯрж╛ржмрзЗрж╕ ржХрж╛ржирзЗржХрж╢ржи ржлрж╛ржВрж╢ржи
def get_db_connection():
    return psycopg2.connect(DB_URI)

# --- ржЗржЙржЯрж┐ржЙржм рж╣рзЗрж▓рзНржкрж╛рж░ ржлрж╛ржВрж╢ржи ---
def check_youtube_sub(user_channel_id, target_channel_id):
    """ржЪрзЗржХ ржХрж░рзЗ ржЗржЙржЬрж╛рж░ рж╕рждрзНржпрж┐ рж╕рж╛ржмрж╕рзНржХрзНрж░рж╛ржЗржм ржХрж░рзЗржЫрзЗ ржХрж┐ ржирж╛"""
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

# --- ржХржорж╛ржирзНржб рж╣рзНржпрж╛ржирзНржбрж▓рж╛рж░ ---

async def start(update: Update, context: ContextTypes.DEFAULT_TYPE):
    user = update.effective_user
    args = context.args
    referrer_id = None
    
    # рж░рзЗржлрж╛рж░рзЗрж▓ рж╣рзНржпрж╛ржирзНржбрж▓рж┐ржВ
    if args:
        try:
            referrer_id = int(args[0])
            if referrer_id == user.id: referrer_id = None
        except:
            pass

    conn = get_db_connection()
    cur = conn.cursor()
    
    # ржЗржЙржЬрж╛рж░ ржЖржЫрзЗ ржХрж┐ ржирж╛ ржЪрзЗржХ
    cur.execute("SELECT * FROM users WHERE user_id = %s", (user.id,))
    existing_user = cur.fetchone()
    
    if existing_user:
        await show_menu(update, context)
    else:
        # ржирждрзБржи ржЗржЙржЬрж╛рж░ рж╣рж▓рзЗ ржЪрзНржпрж╛ржирзЗрж▓ ржЖржЗржбрж┐ ржЪрж╛ржЗржмрзЗ
        await update.message.reply_text(
            f"ЁЯСЛ рж╕рзНржмрж╛ржЧрждржо {user.first_name}!\n\n"
            "ржЖржорж╛ржжрзЗрж░ ржХржорж┐ржЙржирж┐ржЯрж┐рждрзЗ ржЬрзЯрзЗржи ржХрж░рждрзЗ ржЖржкржирж╛рж░ **YouTube Channel ID** ржЯрж┐ ржжрж┐ржиред\n"
            "ржЙржжрж╛рж╣рж░ржг: `UCxxxxxxxxxxxxxxx`\n\n"
            "(ржЪрзНржпрж╛ржирзЗрж▓ рж▓рж┐ржВржХ ржжрж┐рж▓рзЗржУ рж╣ржмрзЗ, рждржмрзЗ ржЖржЗржбрж┐ ржжрж┐рж▓рзЗ ржнрж╛рж▓рзЛ рж╣рзЯ)"
        )
        context.user_data['waiting_for_channel'] = True
        if referrer_id:
            context.user_data['referrer_id'] = referrer_id
            
    cur.close()
    conn.close()

async def handle_text(update: Update, context: ContextTypes.DEFAULT_TYPE):
    # ржЪрзНржпрж╛ржирзЗрж▓ ржЖржЗржбрж┐ ржЗржиржкрзБржЯ ржирзЗржУрзЯрж╛
    if context.user_data.get('waiting_for_channel'):
        channel_text = update.message.text.strip()
        
        # ржЪрзНржпрж╛ржирзЗрж▓ ржЖржЗржбрж┐ ржмрзЗрж░ ржХрж░рж╛ (рж╕рж┐ржорзНржкрж▓ рж▓ржЬрж┐ржХ)
        if "channel/" in channel_text:
            channel_id = channel_text.split("channel/")[-1].split("/")[0]
        else:
            channel_id = channel_text

        user = update.effective_user
        referrer_id = context.user_data.get('referrer_id')
        
        conn = get_db_connection()
        cur = conn.cursor()
        
        try:
            # 1. рж╕рж┐рж╕рзНржЯрзЗржо ржкрзБрж▓ ржерзЗржХрзЗ рзнрзл ржкрзЯрзЗржирзНржЯ ржХржорж╛ржирзЛ
            cur.execute("UPDATE system_pool SET total_balance = total_balance - 75 WHERE id = 1")
            
            # 2. ржЗржЙржЬрж╛рж░ рждрзИрж░рж┐ ржХрж░рж╛
            cur.execute(
                "INSERT INTO users (user_id, username, channel_id, balance, referrer_id) VALUES (%s, %s, %s, %s, %s)",
                (user.id, user.username, channel_id, 75, referrer_id)
            )
            
            # 3. рж░рзЗржлрж╛рж░рж╛рж░ ржмрзЛржирж╛рж╕ (ржпржжрж┐ ржерж╛ржХрзЗ)
            if referrer_id:
                cur.execute("UPDATE users SET balance = balance + 75 WHERE user_id = %s", (referrer_id,))
                cur.execute("UPDATE system_pool SET total_balance = total_balance - 75 WHERE id = 1")
                try:
                    await context.bot.send_message(referrer_id, "ЁЯОЙ ржЖржкржирж┐ ржПржХржЬржиржХрзЗ рж░рзЗржлрж╛рж░ ржХрж░рзЗ рзнрзл ржкрзЯрзЗржирзНржЯ ржкрзЗрзЯрзЗржЫрзЗржи!")
                except:
                    pass

            conn.commit()
            await update.message.reply_text(
                "тЬЕ рж░рзЗржЬрж┐рж╕рзНржЯрзНрж░рзЗрж╢ржи рж╕ржлрж▓! ржЖржкржирж┐ рзнрзл ржкрзЯрзЗржирзНржЯ ржмрзЛржирж╛рж╕ ржкрзЗрзЯрзЗржЫрзЗржиред",
            )
            await show_menu(update, context)
            
        except Exception as e:
            conn.rollback()
            await update.message.reply_text("тЪая╕П рж╕ржорж╕рзНржпрж╛ рж╣рзЯрзЗржЫрзЗ ржмрж╛ ржПржЗ ржЪрзНржпрж╛ржирзЗрж▓ ржЗрждрж┐ржоржзрзНржпрзЗ ржирж┐ржмржирзНржзрж┐рждред")
            print(e)
        finally:
            cur.close()
            conn.close()
            context.user_data['waiting_for_channel'] = False
    else:
        await show_menu(update, context)

async def show_menu(update: Update, context: ContextTypes.DEFAULT_TYPE):
    keyboard = [
        [InlineKeyboardButton("ЁЯТ░ Earn Points (ржХрж╛ржЬ ржХрж░рзБржи)", callback_data='earn')],
        [InlineKeyboardButton("ЁЯСд My Profile", callback_data='profile'),
         InlineKeyboardButton("ЁЯТ│ Buy Points", callback_data='buy')],
        [InlineKeyboardButton("ЁЯФЧ Refer & Earn", callback_data='refer')]
    ]
    reply_markup = InlineKeyboardMarkup(keyboard)
    msg_text = "ЁЯПа **Main Menu**\nржЖржкржирж╛рж░ ржЕржкрж╢ржи ржмрзЗржЫрзЗ ржирж┐ржи:"
    
    if update.callback_query:
        await update.callback_query.edit_message_text(msg_text, reply_markup=reply_markup, parse_mode='Markdown')
    else:
        await update.message.reply_text(msg_text, reply_markup=reply_markup, parse_mode='Markdown')

# --- ржмрж╛ржЯржи рж╣рзНржпрж╛ржирзНржбрж▓рж╛рж░ (рж╕ржм ржЕрзНржпрж╛ржХрж╢ржи ржПржЦрж╛ржирзЗ) ---

async def button_callback(update: Update, context: ContextTypes.DEFAULT_TYPE):
    query = update.callback_query
    await query.answer()
    user = query.from_user
    data = query.data
    
    conn = get_db_connection()
    cur = conn.cursor()

    if data == 'profile':
        cur.execute("SELECT balance, channel_id, warnings FROM users WHERE user_id = %s", (user.id,))
        res = cur.fetchone()
        if res:
            text = (
                f"ЁЯСд **ржЖржкржирж╛рж░ ржкрзНрж░рзЛржлрж╛ржЗрж▓**\n\n"
                f"ЁЯТ░ ржмрзНржпрж╛рж▓рзЗржирзНрж╕: **{res[0]}** ржкрзЯрзЗржирзНржЯ\n"
                f"ЁЯУ║ ржЪрзНржпрж╛ржирзЗрж▓ ржЖржЗржбрж┐: `{res[1]}`\n"
                f"тЪая╕П ржУрзЯрж╛рж░рзНржирж┐ржВ: {res[2]}/3\n"
            )
            back_btn = [[InlineKeyboardButton("ЁЯФЩ Back", callback_data='menu')]]
            await query.edit_message_text(text, parse_mode='Markdown', reply_markup=InlineKeyboardMarkup(back_btn))

    elif data == 'menu':
        await show_menu(update, context)

    elif data == 'refer':
        link = f"https://t.me/{context.bot.username}?start={user.id}"
        text = (
            "ЁЯдЭ **рж░рзЗржлрж╛рж░рзЗрж▓ ржкрзНрж░рзЛржЧрзНрж░рж╛ржо**\n\n"
            "ржмржирзНржзрзБржжрзЗрж░ ржЗржиржнрж╛ржЗржЯ ржХрж░рзБржи ржПржмржВ ржжрзБржЬржирзЗржЗ ржЬрж┐рждрзБржи!\n"
            "ЁЯОБ ржЖржкржирж┐ ржкрж╛ржмрзЗржи: **рзнрзл ржкрзЯрзЗржирзНржЯ**\n"
            "ЁЯОБ ржмржирзНржзрзБ ржкрж╛ржмрзЗ: **рзнрзл ржкрзЯрзЗржирзНржЯ**\n\n"
            f"ржЖржкржирж╛рж░ рж▓рж┐ржВржХ:\n`{link}`"
        )
        back_btn = [[InlineKeyboardButton("ЁЯФЩ Back", callback_data='menu')]]
        await query.edit_message_text(text, parse_mode='Markdown', reply_markup=InlineKeyboardMarkup(back_btn))

    elif data == 'buy':
        text = (
            "ЁЯТО **ржкрзЯрзЗржирзНржЯ ржХрж┐ржирзБржи (рзз ржЯрж╛ржХрж╛ = рзй ржкрзЯрзЗржирзНржЯ)**\n\n"
            "тАв Starter: рззрзжрзж ржЯрж╛ржХрж╛рзЯ рзйрзлрзж ржкрзЯрзЗржирзНржЯ\n"
            "тАв Pro: рзлрзжрзж ржЯрж╛ржХрж╛рзЯ рзирзжрзжрзж ржкрзЯрзЗржирзНржЯ\n"
            "тАв VIP: рззрзжрзжрзж ржЯрж╛ржХрж╛рзЯ рзкрзлрзжрзж ржкрзЯрзЗржирзНржЯ\n\n"
            f"ржмрж┐ржХрж╛рж╢ (Send Money): `{BKASH_NUMBER}`\n\n"
            "ржЯрж╛ржХрж╛ ржкрж╛ржарж┐рзЯрзЗ ржЕрзНржпрж╛ржбржорж┐ржиржХрзЗ рж╕рзНржХрзНрж░рж┐ржирж╢ржЯ ржмрж╛ TrxID ржжрж┐ржиред"
        )
        back_btn = [[InlineKeyboardButton("ЁЯФЩ Back", callback_data='menu')]]
        await query.edit_message_text(text, parse_mode='Markdown', reply_markup=InlineKeyboardMarkup(back_btn))

    elif data == 'earn':
        # ржЯрж╛рж╕рзНржХ ржЦрзЛржБржЬрж╛: ржПржоржи ржЗржЙржЬрж╛рж░ ржпрж╛рж░ ржмрзНржпрж╛рж▓рзЗржирзНрж╕ рззрзл+ ржПржмржВ ржЖржорж┐ рждрж╛ржХрзЗ рж╕рж╛ржмрж╕рзНржХрзНрж░рж╛ржЗржм ржХрж░рж┐ржирж┐
        # (ржПржЦрж╛ржирзЗ рж╕рж┐ржорзНржкрж▓ рж▓ржЬрж┐ржХ ржмрзНржпржмрж╣рж╛рж░ ржХрж░рж╛ рж╣рзЯрзЗржЫрзЗ, ржкрзНрж░рзЛржбрж╛ржХрж╢ржирзЗ ржЖрж░ржУ ржЕрзНржпрж╛ржбржнрж╛ржирзНрж╕ржб ржХрзБрзЯрзЗрж░рж┐ рж▓рж╛ржЧржмрзЗ)
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
                [InlineKeyboardButton("ЁЯУ║ Subscribe Channel", url=f"https://www.youtube.com/channel/{target_cid}")],
                [InlineKeyboardButton("тЬЕ Verify Task", callback_data='verify_task')],
                [InlineKeyboardButton("ЁЯФЩ Back", callback_data='menu')]
            ]
            await query.edit_message_text(
                f"ЁЯСЗ ржПржЗ ржЪрзНржпрж╛ржирзЗрж▓ржЯрж┐ рж╕рж╛ржмрж╕рзНржХрзНрж░рж╛ржЗржм ржХрж░рзБржи ржПржмржВ рззрзж ржкрзЯрзЗржирзНржЯ ржЬрж┐рждрзБржи!\nID: `{target_cid}`",
                reply_markup=InlineKeyboardMarkup(kb),
                parse_mode='Markdown'
            )
        else:
            await query.edit_message_text("тЭМ ржмрж░рзНрждржорж╛ржирзЗ ржХрзЛржирзЛ ржХрж╛ржЬ ржирзЗржЗред ржХрж┐ржЫрзБржХрзНрж╖ржг ржкрж░ ржЪрзЗрж╖рзНржЯрж╛ ржХрж░рзБржиред", 
                                          reply_markup=InlineKeyboardMarkup([[InlineKeyboardButton("ЁЯФЩ Back", callback_data='menu')]]))

    elif data == 'verify_task':
        target_uid = context.user_data.get('task_target_uid')
        target_cid = context.user_data.get('task_target_cid')
        
        if not target_cid:
            await query.edit_message_text("Error. Try again.")
            return

        # ржЖржорж╛рж░ ржЪрзНржпрж╛ржирзЗрж▓ ржЖржЗржбрж┐ ржмрзЗрж░ ржХрж░рж╛
        cur.execute("SELECT channel_id FROM users WHERE user_id = %s", (user.id,))
        my_cid = cur.fetchone()[0]

        # API ржХрж▓ ржХрж░рзЗ ржЪрзЗржХ ржХрж░рж╛
        is_subscribed = check_youtube_sub(my_cid, target_cid)

        if is_subscribed:
            try:
                # рзз. ржЪрзНржпрж╛ржирзЗрж▓ ржорж╛рж▓рж┐ржХрзЗрж░ ржерзЗржХрзЗ рззрзл ржХрж╛ржЯрж╛
                cur.execute("UPDATE users SET balance = balance - 15 WHERE user_id = %s", (target_uid,))
                # рзи. ржЖрж░рзНржирж╛рж░ржХрзЗ рззрзж ржжрзЗржУрзЯрж╛
                cur.execute("UPDATE users SET balance = balance + 10 WHERE user_id = %s", (user.id,))
                # рзй. рж╕рж┐рж╕рзНржЯрзЗржорзЗ рзл ржлрзЗрж░ржд (Recycle)
                cur.execute("UPDATE system_pool SET total_balance = total_balance + 5 WHERE id = 1")
                
                # рзк. рж╕рж╛ржмрж╕рзНржХрзНрж░рж┐ржкрж╢ржи рж░рзЗржХрж░рзНржб рж╕рзЗржн (ржмрж┐ржЪрж╛рж░рзЗрж░ ржЬржирзНржп)
                cur.execute(
                    "INSERT INTO subscriptions (subscriber_id, target_channel_id, target_user_id) VALUES (%s, %s, %s)",
                    (user.id, target_cid, target_uid)
                )
                
                conn.commit()
                await query.edit_message_text("тЬЕ ржЕржнрж┐ржиржирзНржжржи! ржЯрж╛рж╕рзНржХ ржХржоржкрзНрж▓рж┐ржЯред рззрзж ржкрзЯрзЗржирзНржЯ ржпрзЛржЧ рж╣рзЯрзЗржЫрзЗред", 
                                              reply_markup=InlineKeyboardMarkup([[InlineKeyboardButton("More Task", callback_data='earn')]]))
            except Exception as e:
                conn.rollback()
                print(e)
                await query.edit_message_text("Error processing points.")
        else:
            await query.edit_message_text(
                "тЭМ рж╕рж╛ржмрж╕рзНржХрзНрж░рж┐ржкрж╢ржи ржкрж╛ржУрзЯрж╛ ржпрж╛рзЯржирж┐ред\n"
                "ржжрзЯрж╛ ржХрж░рзЗ ржирж┐рж╢рзНржЪрж┐ржд ржХрж░рзБржи ржЖржкржирж┐ рж╕рж╛ржмрж╕рзНржХрзНрж░рж╛ржЗржм ржХрж░рзЗржЫрзЗржи ржПржмржВ ржЖржкржирж╛рж░ 'Subscriptions' ржкрзНрж░рж╛ржЗржнрзЗрж╕рж┐ 'Public' ржХрж░рж╛ ржЖржЫрзЗред",
                reply_markup=InlineKeyboardMarkup([[InlineKeyboardButton("Try Again", callback_data='earn')]])
            )

    cur.close()
    conn.close()

# --- ржПржбржорж┐ржи ржХржорж╛ржирзНржб (ржкрзЯрзЗржирзНржЯ ржжрзЗржУрзЯрж╛рж░ ржЬржирзНржп) ---
async def admin_add_points(update: Update, context: ContextTypes.DEFAULT_TYPE):
    user = update.effective_user
    if user.id != ADMIN_ID: return

    try:
        # ржмрзНржпржмрж╣рж╛рж░: /add user_id amount
        target_id = int(context.args[0])
        amount = int(context.args[1])
        
        conn = get_db_connection()
        cur = conn.cursor()
        
        # рж╕рж┐рж╕рзНржЯрзЗржо ржкрзБрж▓ ржерзЗржХрзЗ ржкрзЯрзЗржирзНржЯ ржирж┐рзЯрзЗ ржЗржЙржЬрж╛рж░ржХрзЗ ржжрзЗржУрзЯрж╛
        cur.execute("UPDATE users SET balance = balance + %s WHERE user_id = %s", (amount, target_id))
        cur.execute("UPDATE system_pool SET total_balance = total_balance - %s WHERE id = 1", (amount,))
        conn.commit()
        conn.close()
        
        await update.message.reply_text(f"тЬЕ рж╕ржлрж▓! {target_id}-ржХрзЗ {amount} ржкрзЯрзЗржирзНржЯ ржжрзЗржУрзЯрж╛ рж╣рзЯрзЗржЫрзЗред")
        await context.bot.send_message(target_id, f"ЁЯОЙ ржЕржнрж┐ржиржирзНржжржи! ржЕрзНржпрж╛ржбржорж┐ржи ржЖржкржирж╛ржХрзЗ {amount} ржкрзЯрзЗржирзНржЯ ржкрж╛ржарж┐рзЯрзЗржЫрзЗред")
        
    except Exception as e:
        await update.message.reply_text("ржмрзНржпржмрж╣рж╛рж░: /add <user_id> <amount>")

# --- рж░рж╛ржи ржмржбрж┐ ---
if __name__ == '__main__':
    app = ApplicationBuilder().token(BOT_TOKEN).build()
    
    app.add_handler(CommandHandler("start", start))
    app.add_handler(CommandHandler("add", admin_add_points)) # рж╢рзБржзрзБ ржПржбржорж┐ржирзЗрж░ ржЬржирзНржп
    app.add_handler(MessageHandler(filters.TEXT & (~filters.COMMAND), handle_text))
    app.add_handler(CallbackQueryHandler(button_callback))
    
    print("Bot is running...")
    app.run_polling()