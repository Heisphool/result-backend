import logging
import requests
from telegram import Update, InlineKeyboardButton, InlineKeyboardMarkup
from telegram.ext import (
    ApplicationBuilder,
    ContextTypes,
    CommandHandler,
    CallbackQueryHandler,
    MessageHandler,
    filters,
    ConversationHandler,
)

# --- CONFIGURATION ---
# ⚠️ Replace with your Bot Token
BOT_TOKEN = "8541634623:AAETR1SvO0or9cXE85lQBL4y2ChvwGZX36o"

# ⚠️ Updated Admin ID (Phool Babu)
ADMIN_ID = 6716560182

# API Base URL
BASE_URL = "https://www.beu-bih.ac.in/backend/v1/result/get-result"

# --- DEFAULT EXAM CONFIGURATION (Master List) ---
# Format: "BATCH_SEM": "Month/Year"
# Isme aap default values pehle se save kar sakte hain
EXAM_CONFIG = {
    "2023_III": "July/2025",
    "2023_II": "Dec/2024",
    "2023_I": "May/2024",
    "2022_V": "July/2025",
    "2022_IV": "Dec/2024",
}

# --- STATES ---
BATCH, SEMESTER, REG_NO = range(3)

# Logging
logging.basicConfig(
    format='%(asctime)s - %(name)s - %(levelname)s - %(message)s',
    level=logging.INFO
)

# --- HELPER: FORMAT RESULT (Marksheet Style) ---
def format_marksheet(data, batch, sem, exam_held):
    name = data.get('name', 'N/A')
    reg_no = data.get('redg_no', 'N/A')
    college = data.get('college_name', 'N/A')
    course = data.get('course', 'B.Tech')
    cgpa = data.get('cgpa', 'N/A')
    
    # SGPA logic
    sgpa_list = data.get('sgpa', [])
    # Assuming sem is roman 'III', convert to index if needed, or just fetch directly if logic allows
    # For now, let's try to grab the latest non-null SGPA or specific one if logic permits
    # Simple workaround: Just show "Current Sem SGPA" if available in array
    current_sgpa = "N/A"
    sem_map = {'I':0, 'II':1, 'III':2, 'IV':3, 'V':4, 'VI':5, 'VII':6, 'VIII':7}
    if sem in sem_map and sem_map[sem] < len(sgpa_list):
        val = sgpa_list[sem_map[sem]]
        current_sgpa = val if val else "Pending"

    # Fail Status
    fail_raw = data.get('fail_any', '')
    if fail_raw and "FAIL" in str(fail_raw):
        status_icon = "🔴 FAIL"
        status_text = f"Backlog: {fail_raw.replace('FAIL:', '')}"
    else:
        status_icon = "🟢 PASS"
        status_text = "All Clear! 🎉"

    # Header
    msg = f"🏛 **BIHAR ENGINEERING UNIVERSITY**\n"
    msg += f"🗓 `Batch {batch} | Sem {sem} ({exam_held})`\n"
    msg += "━━━━━━━━━━━━━━━━━━━━━━━━\n"
    
    # Student Details
    msg += f"👤 **{name}**\n"
    msg += f"🆔 `{reg_no}`\n"
    msg += f"🏫 {college}\n"
    msg += "━━━━━━━━━━━━━━━━━━━━━━━━\n"

    # Theory Subjects
    msg += "📝 **THEORY PAPERS**\n"
    if data.get('theorySubjects'):
        for sub in data['theorySubjects']:
            grade = sub['grade']
            # Make Grade Bold if Fail
            grade_display = f"**{grade}**" if grade == 'F' else f"{grade}"
            
            msg += f"**• {sub['name']}** `({sub['code']})`\n"
            msg += f"   ├─ Marks: `{sub['total']}` (Ext:{sub['ese']} + Int:{sub['ia']})\n"
            msg += f"   └─ Grade: {grade_display}\n"
    else:
        msg += "   (No Theory Data)\n"
    
    msg += "\n"

    # Practical Subjects
    msg += "🛠 **PRACTICAL / SESSIONAL**\n"
    if data.get('practicalSubjects'):
        for sub in data['practicalSubjects']:
            msg += f"**• {sub['name']}**\n"
            msg += f"   └─ Marks: `{sub['total']}` | Grade: {sub['grade']}\n"
    else:
        msg += "   (No Practical Data)\n"

    msg += "━━━━━━━━━━━━━━━━━━━━━━━━\n"
    
    # Footer Stats
    msg += f"📊 **PERFORMANCE REPORT**\n"
    msg += f"🔹 **SGPA:** `{current_sgpa}`  |  🔸 **CGPA:** `{cgpa}`\n"
    msg += f"🏁 **STATUS:** {status_icon}\n"
    if "FAIL" in status_icon:
        msg += f"⚠️ {status_text}\n"
    
    msg += "━━━━━━━━━━━━━━━━━━━━━━━━\n"
    msg += "🤖 *Generated via BEUHub Bot*"
    
    return msg

# --- ADMIN COMMANDS ---

async def set_exam_date(update: Update, context: ContextTypes.DEFAULT_TYPE):
    """
    Admin Command: /set 2023 III July/2025
    """
    user_id = update.effective_user.id
    if user_id != ADMIN_ID:
        await update.message.reply_text("⛔ **Admin Access Only.**\nYou are not authorized.")
        return

    try:
        args = context.args
        if len(args) < 3:
            await update.message.reply_text(
                "⚠️ **Usage:** `/set <Batch> <Sem> <Month/Year>`\n"
                "Example: `/set 2023 III July/2025`", 
                parse_mode='Markdown'
            )
            return

        batch = args[0]
        sem = args[1]
        exam_date = args[2] 
        
        key = f"{batch}_{sem}"
        EXAM_CONFIG[key] = exam_date
        
        await update.message.reply_text(f"✅ **Config Saved!**\nBatch: `{batch}`\nSem: `{sem}`\nExam: `{exam_date}`", parse_mode='Markdown')

    except Exception as e:
        await update.message.reply_text(f"❌ Error: {str(e)}")

async def view_config(update: Update, context: ContextTypes.DEFAULT_TYPE):
    """Shows all saved Exam Configurations."""
    user_id = update.effective_user.id
    if user_id != ADMIN_ID:
        await update.message.reply_text("⛔ Not Authorized.")
        return

    msg = "⚙️ **Active Exam Configurations:**\n\n"
    if not EXAM_CONFIG:
        msg += "❌ No configurations set. Use /set command."
    else:
        for key, val in EXAM_CONFIG.items():
            b, s = key.split('_')
            msg += f"🔹 **{b} (Sem {s}):** `{val}`\n"
    
    await update.message.reply_text(msg, parse_mode='Markdown')

# --- USER FLOW COMMANDS ---

async def start(update: Update, context: ContextTypes.DEFAULT_TYPE):
    """Starts the bot."""
    user = update.effective_user.first_name
    await update.message.reply_text(
        f"👋 **Namaste {user}!**\n\n"
        "🎓 **BEU Result Portal** me aapka swagat hai.\n"
        "Yahan aap apna official marksheet check kar sakte hain.\n\n"
        "👇 **Shuru karne ke liye apna Batch select karein:**",
        parse_mode='Markdown'
    )
    
    # Batch Buttons
    keyboard = [
        [InlineKeyboardButton("2021", callback_data='2021'), InlineKeyboardButton("2022", callback_data='2022')],
        [InlineKeyboardButton("2023", callback_data='2023'), InlineKeyboardButton("2024", callback_data='2024')],
        [InlineKeyboardButton("2025", callback_data='2025')]
    ]
    reply_markup = InlineKeyboardMarkup(keyboard)
    await update.message.reply_text("🔹 **Select Batch Year:**", reply_markup=reply_markup)
    return BATCH

async def batch_handler(update: Update, context: ContextTypes.DEFAULT_TYPE):
    query = update.callback_query
    await query.answer()
    
    batch = query.data
    context.user_data['batch'] = batch
    
    await query.edit_message_text(f"✅ **Batch {batch}** Selected.\n👇 Ab apna **Semester** select karein:")
    
    # Semester Buttons
    keyboard = [
        [InlineKeyboardButton("Sem I", callback_data='I'), InlineKeyboardButton("Sem II", callback_data='II')],
        [InlineKeyboardButton("Sem III", callback_data='III'), InlineKeyboardButton("Sem IV", callback_data='IV')],
        [InlineKeyboardButton("Sem V", callback_data='V'), InlineKeyboardButton("Sem VI", callback_data='VI')],
        [InlineKeyboardButton("Sem VII", callback_data='VII'), InlineKeyboardButton("Sem VIII", callback_data='VIII')]
    ]
    reply_markup = InlineKeyboardMarkup(keyboard)
    await query.message.reply_text("🔹 **Select Semester:**", reply_markup=reply_markup)
    return SEMESTER

async def semester_handler(update: Update, context: ContextTypes.DEFAULT_TYPE):
    query = update.callback_query
    await query.answer()
    
    sem = query.data
    context.user_data['semester'] = sem
    
    await query.edit_message_text(
        f"✅ **Semester {sem}** Selected.\n\n"
        f"🔢 Please type your **Registration Number**:\n"
        f"(Example: `23103132004`)",
        parse_mode='Markdown'
    )
    return REG_NO

async def get_result_handler(update: Update, context: ContextTypes.DEFAULT_TYPE):
    reg_no = update.message.text.strip()
    batch = context.user_data.get('batch')
    sem = context.user_data.get('semester')
    
    if not reg_no.isdigit():
        await update.message.reply_text("❌ **Invalid Input!**\nSirf numbers enter karein (e.g. 23103132004).")
        return REG_NO

    # Check Config
    config_key = f"{batch}_{sem}"
    exam_held = EXAM_CONFIG.get(config_key)
    
    if not exam_held:
        await update.message.reply_text(
            f"⚠️ **Data Not Found!**\n"
            f"Admin ne abhi **Batch {batch} - Sem {sem}** ka date set nahi kiya hai.\n"
            f"Please contact Admin (@PhoolBabu) to update settings."
        )
        return ConversationHandler.END

    status_msg = await update.message.reply_text(f"⏳ **Connecting to BEU Server...**\nFetching result for Reg: {reg_no}", parse_mode='Markdown')

    # API Call
    params = {
        "year": batch,
        "redg_no": reg_no,
        "semester": sem,
        "exam_held": exam_held
    }

    try:
        response = requests.get(BASE_URL, params=params)
        data = response.json()
        
        # Check Success
        if response.status_code == 200 and data.get('status') == 200 and data.get('data'):
            # Generate Premium Marksheet
            result_text = format_marksheet(data['data'], batch, sem, exam_held)
            
            await context.bot.edit_message_text(
                chat_id=update.effective_chat.id, 
                message_id=status_msg.message_id, 
                text=result_text, 
                parse_mode='Markdown'
            )
        else:
            await context.bot.edit_message_text(
                chat_id=update.effective_chat.id, 
                message_id=status_msg.message_id, 
                text="❌ **Result Not Found.**\nPlease check Reg No or try again later."
            )

    except Exception as e:
        await context.bot.edit_message_text(
            chat_id=update.effective_chat.id, 
            message_id=status_msg.message_id, 
            text=f"❌ **Server Error:** {str(e)}"
        )
    
    # Restart Button
    keyboard = [[InlineKeyboardButton("🔄 Check Another Result", callback_data='restart')]]
    reply_markup = InlineKeyboardMarkup(keyboard)
    await update.message.reply_text("Check another student?", reply_markup=reply_markup)

    return ConversationHandler.END

async def cancel(update: Update, context: ContextTypes.DEFAULT_TYPE):
    await update.message.reply_text("🚫 **Cancelled.** /start to restart.")
    return ConversationHandler.END

async def restart(update: Update, context: ContextTypes.DEFAULT_TYPE):
    query = update.callback_query
    await query.answer()
    await start(update, context) 
    return BATCH

# --- MAIN ---
if __name__ == '__main__':
    # 1. Render Keep-Alive Logic
    try:
        from keep_alive import keep_alive
        keep_alive()
        print("✅ Web Server Started (Render Mode)")
    except ImportError:
        print("⚠️ keep_alive.py not found. Running in Local Mode.")

    # 2. Bot Builder
    print("🤖 Bot is Starting...")
    application = ApplicationBuilder().token(BOT_TOKEN).build()

    # 3. Handlers
    conv_handler = ConversationHandler(
        entry_points=[CommandHandler('start', start)],
        states={
            BATCH: [CallbackQueryHandler(batch_handler)],
            SEMESTER: [CallbackQueryHandler(semester_handler)],
            REG_NO: [MessageHandler(filters.TEXT & ~filters.COMMAND, get_result_handler)],
        },
        fallbacks=[CommandHandler('cancel', cancel)]
    )

    application.add_handler(conv_handler)
    application.add_handler(CallbackQueryHandler(restart, pattern='^restart$'))
    
    # Admin Handlers
    application.add_handler(CommandHandler("set", set_exam_date))
    application.add_handler(CommandHandler("view_config", view_config))

    # 4. Run
    application.run_polling()
