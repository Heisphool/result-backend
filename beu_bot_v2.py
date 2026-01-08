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

# ⚠️ Admin ID (Phool Babu)
ADMIN_ID = 6716560182

# API Base URL
BASE_URL = "https://www.beu-bih.ac.in/backend/v1/result/get-result"

# --- DEFAULT EXAM CONFIGURATION (Master List) ---
# Admin can update this via /set command
EXAM_CONFIG = {
    "2023_III": "July/2025",
    "2023_II": "Dec/2024",
    "2023_I": "May/2024",
    "2022_V": "July/2025",
    "2022_VI": "Nov/2025",
    "2022_IV": "Dec/2024",
    "2024_I": "May/2025",
    "2024_II": "Nov/2025",
    # Add more defaults here
}

# --- STATES ---
BATCH, SEMESTER, REG_NO, RESULT_MENU = range(4)

# --- LOGGING ---
logging.basicConfig(
    format='%(asctime)s - %(name)s - %(levelname)s - %(message)s',
    level=logging.INFO
)

# --- HELPER: BRANDING ---
HEADER_TEXT = "🌐 **Visit: beuhub.site**\n━━━━━━━━━━━━━━━━━━"
FOOTER_TEXT = "━━━━━━━━━━━━━━━━━━\n🌐 **Powered by beuhub.site**"

# --- HELPER: FORMAT RESULT (PREMIUM STYLE) ---
def format_marksheet(data, batch, sem, exam_held):
    name = data.get('name', 'N/A')
    reg_no = data.get('redg_no', 'N/A')
    college = data.get('college_name', 'N/A')
    course = data.get('course', 'B.Tech')
    cgpa = data.get('cgpa', 'N/A')
    
    # Attempt to get current SGPA
    sgpa_list = data.get('sgpa', [])
    current_sgpa = "N/A"
    sem_map = {'I':0, 'II':1, 'III':2, 'IV':3, 'V':4, 'VI':5, 'VII':6, 'VIII':7}
    
    if sem in sem_map and sem_map[sem] < len(sgpa_list):
        val = sgpa_list[sem_map[sem]]
        current_sgpa = val if val else "Pending"

    # Fail Status Logic
    fail_raw = data.get('fail_any', '')
    if fail_raw and "FAIL" in str(fail_raw):
        status_icon = "🔴 FAIL"
        status_details = f"Backlog: {fail_raw.replace('FAIL:', '')}"
    else:
        status_icon = "🟢 PASS"
        status_details = "All Clear! Excellent Work. 🎉"

    # --- BUILDING THE MESSAGE ---
    msg = f"{HEADER_TEXT}\n"
    msg += f"🏛 **BEU OFFICIAL RESULT**\n"
    msg += f"📅 `Batch {batch} | Sem {sem} ({exam_held})`\n"
    msg += "━━━━━━━━━━━━━━━━━━\n"
    
    # Student Profile
    msg += f"👤 **{name}**\n"
    msg += f"🆔 `{reg_no}`\n"
    msg += f"🏫 _{college}_\n"
    msg += "━━━━━━━━━━━━━━━━━━\n"

    # Theory Papers
    msg += "📝 **THEORY PAPERS**\n"
    if data.get('theorySubjects'):
        for sub in data['theorySubjects']:
            grade = sub['grade']
            # Highlight Fail Grades
            grade_display = f"⚠️ {grade}" if grade == 'F' else f"✅ {grade}"
            
            msg += f"**• {sub['name']}** `({sub['code']})`\n"
            msg += f"   └ Marks: `{sub['total']}` (Ext:{sub['ese']} + Int:{sub['ia']}) | Gd: {grade_display}\n"
    else:
        msg += "   _(No Theory Data Available)_\n"
    
    msg += "\n"

    # Practical Papers
    msg += "🛠 **PRACTICALS**\n"
    if data.get('practicalSubjects'):
        for sub in data['practicalSubjects']:
            msg += f"**• {sub['name']}**\n"
            msg += f"   └ Marks: `{sub['total']}` | Grade: {sub['grade']}\n"
    else:
        msg += "   _(No Practical Data Available)_\n"

    msg += "━━━━━━━━━━━━━━━━━━\n"
    
    # Final Stats
    msg += f"📊 **PERFORMANCE SUMMARY**\n"
    msg += f"🔹 **SGPA:** `{current_sgpa}`\n"
    msg += f"🔸 **CGPA:** `{cgpa}`\n"
    msg += f"🏁 **STATUS:** {status_icon}\n"
    msg += f"📢 {status_details}\n"
    
    msg += f"{FOOTER_TEXT}"
    
    return msg

# --- ADMIN COMMANDS ---

async def set_exam_date(update: Update, context: ContextTypes.DEFAULT_TYPE):
    """Admin Command: /set 2023 III July/2025"""
    user_id = update.effective_user.id
    if user_id != ADMIN_ID:
        await update.message.reply_text("⛔ **Access Denied.** Admin only.")
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
        
        await update.message.reply_text(f"✅ **Configuration Saved!**\nBatch: `{batch}`\nSem: `{sem}`\nExam Date: `{exam_date}`", parse_mode='Markdown')

    except Exception as e:
        await update.message.reply_text(f"❌ Error: {str(e)}")

async def view_config(update: Update, context: ContextTypes.DEFAULT_TYPE):
    """Shows all saved Exam Configurations."""
    user_id = update.effective_user.id
    if user_id != ADMIN_ID:
        return

    msg = "⚙️ **Active Exam Configurations:**\n\n"
    if not EXAM_CONFIG:
        msg += "❌ No configurations set. Use /set command."
    else:
        for key, val in EXAM_CONFIG.items():
            b, s = key.split('_')
            msg += f"🔹 **Batch {b} (Sem {s}):** `{val}`\n"
    
    await update.message.reply_text(msg, parse_mode='Markdown')

# --- USER FLOW HANDLERS ---

async def start(update: Update, context: ContextTypes.DEFAULT_TYPE):
    """Starts the bot."""
    user = update.effective_user.first_name
    
    # Intro Message
    intro = (
        f"{HEADER_TEXT}\n"
        f"👋 **Hello {user}!**\n\n"
        "🎓 **Welcome to the BEU Result Portal.**\n"
        "Get your official results instantly with a verified mark sheet.\n\n"
        "👇 **Please select your Batch Year to begin:**"
    )
    
    # Batch Buttons
    keyboard = [
        [InlineKeyboardButton("2022", callback_data='2022')],
        [InlineKeyboardButton("2023", callback_data='2023'), InlineKeyboardButton("2024", callback_data='2024')],
        [InlineKeyboardButton("2025", callback_data='2025')]
    ]
    reply_markup = InlineKeyboardMarkup(keyboard)
    
    if update.callback_query:
        await update.callback_query.edit_message_text(text=intro, reply_markup=reply_markup, parse_mode='Markdown')
    else:
        await update.message.reply_text(text=intro, reply_markup=reply_markup, parse_mode='Markdown')
        
    return BATCH

async def batch_handler(update: Update, context: ContextTypes.DEFAULT_TYPE):
    query = update.callback_query
    await query.answer()
    
    batch = query.data
    context.user_data['batch'] = batch
    
    text = (
        f"{HEADER_TEXT}\n"
        f"✅ **Batch {batch} Selected.**\n"
        f"👇 Now, please select your **Semester**:"
    )
    
    # Semester Buttons
    keyboard = [
        [InlineKeyboardButton("Sem I", callback_data='I'), InlineKeyboardButton("Sem II", callback_data='II')],
        [InlineKeyboardButton("Sem III", callback_data='III'), InlineKeyboardButton("Sem IV", callback_data='IV')],
        [InlineKeyboardButton("Sem V", callback_data='V'), InlineKeyboardButton("Sem VI", callback_data='VI')],
        [InlineKeyboardButton("Sem VII", callback_data='VII'), InlineKeyboardButton("Sem VIII", callback_data='VIII')]
    ]
    reply_markup = InlineKeyboardMarkup(keyboard)
    await query.edit_message_text(text=text, reply_markup=reply_markup, parse_mode='Markdown')
    return SEMESTER

async def semester_handler(update: Update, context: ContextTypes.DEFAULT_TYPE):
    query = update.callback_query
    await query.answer()
    
    sem = query.data
    context.user_data['semester'] = sem
    
    text = (
        f"{HEADER_TEXT}\n"
        f"✅ **Batch {context.user_data['batch']} | Semester {sem}**\n\n"
        f"🔢 **Enter Registration Number:**\n"
        f"_(Example: 23103132004)_"
    )
    
    await query.edit_message_text(text=text, parse_mode='Markdown')
    return REG_NO

async def get_result_handler(update: Update, context: ContextTypes.DEFAULT_TYPE):
    reg_no = update.message.text.strip()
    batch = context.user_data.get('batch')
    sem = context.user_data.get('semester')
    
    # Validation
    if not reg_no.isdigit():
        await update.message.reply_text("❌ **Invalid Input!**\nPlease enter digits only (e.g., 23103132004).")
        return REG_NO

    # Check Configuration
    config_key = f"{batch}_{sem}"
    exam_held = EXAM_CONFIG.get(config_key)
    
    if not exam_held:
        error_msg = (
            f"{HEADER_TEXT}\n"
            f"⚠️ **Result Not Available Yet!**\n"
            f"Exam Date not configured for **Batch {batch} - Sem {sem}**.\n"
            f"Please contact Admin to update settings.\n"
            f"{FOOTER_TEXT}"
        )
        await update.message.reply_text(error_msg, parse_mode='Markdown')
        return ConversationHandler.END

    status_msg = await update.message.reply_text(f"⏳ **Fetching Result...**\nConnecting to BEU Server...", parse_mode='Markdown')

    # API Request
    params = {
        "year": batch,
        "redg_no": reg_no,
        "semester": sem,
        "exam_held": exam_held
    }

    try:
        response = requests.get(BASE_URL, params=params)
        data = response.json()
        
        # Check API Success
        if response.status_code == 200 and data.get('status') == 200 and data.get('data'):
            # Generate Premium Marksheet
            result_text = format_marksheet(data['data'], batch, sem, exam_held)
            
            # Send Result
            await context.bot.edit_message_text(
                chat_id=update.effective_chat.id, 
                message_id=status_msg.message_id, 
                text=result_text, 
                parse_mode='Markdown'
            )
            
            # --- SMART NAVIGATION MENU ---
            nav_text = (
                "👇 **What would you like to do next?**\n"
                "Select an option below:"
            )
            
            keyboard = [
                [InlineKeyboardButton("🔍 Check Another (Same Sem)", callback_data='NAV_SAME')],
                [InlineKeyboardButton("📂 Change Semester", callback_data='NAV_SEM')],
                [InlineKeyboardButton("🏠 Main Menu / Change Batch", callback_data='NAV_HOME')]
            ]
            reply_markup = InlineKeyboardMarkup(keyboard)
            
            await update.message.reply_text(text=nav_text, reply_markup=reply_markup)
            
            # Transition to Menu State
            return RESULT_MENU
            
        else:
            await context.bot.edit_message_text(
                chat_id=update.effective_chat.id, 
                message_id=status_msg.message_id, 
                text=f"❌ **Result Not Found.**\nNo record found for Reg No: `{reg_no}` in this semester.\n\n{FOOTER_TEXT}",
                parse_mode='Markdown'
            )
            return ConversationHandler.END

    except Exception as e:
        await context.bot.edit_message_text(
            chat_id=update.effective_chat.id, 
            message_id=status_msg.message_id, 
            text=f"❌ **Server Error:** {str(e)}\nPlease try again later.",
            parse_mode='Markdown'
        )
        return ConversationHandler.END

# --- RESULT MENU HANDLER ---
async def result_menu_handler(update: Update, context: ContextTypes.DEFAULT_TYPE):
    """Handles the navigation buttons after result is shown."""
    query = update.callback_query
    await query.answer()
    
    choice = query.data
    
    if choice == 'NAV_SAME':
        # User wants to check same Batch/Sem -> Ask Reg No
        batch = context.user_data.get('batch')
        sem = context.user_data.get('semester')
        text = (
            f"{HEADER_TEXT}\n"
            f"🔄 **Check Another Result**\n"
            f"Batch: {batch} | Sem: {sem}\n\n"
            f"🔢 **Enter Registration Number:**"
        )
        await query.edit_message_text(text=text, parse_mode='Markdown')
        return REG_NO
        
    elif choice == 'NAV_SEM':
        # User wants to change Semester (Keep Batch)
        text = (
            f"{HEADER_TEXT}\n"
            f"📂 **Change Semester** (Batch: {context.user_data.get('batch')})\n"
            f"👇 Select new Semester:"
        )
        keyboard = [
            [InlineKeyboardButton("Sem I", callback_data='I'), InlineKeyboardButton("Sem II", callback_data='II')],
            [InlineKeyboardButton("Sem III", callback_data='III'), InlineKeyboardButton("Sem IV", callback_data='IV')],
            [InlineKeyboardButton("Sem V", callback_data='V'), InlineKeyboardButton("Sem VI", callback_data='VI')],
            [InlineKeyboardButton("Sem VII", callback_data='VII'), InlineKeyboardButton("Sem VIII", callback_data='VIII')]
        ]
        reply_markup = InlineKeyboardMarkup(keyboard)
        await query.edit_message_text(text=text, reply_markup=reply_markup, parse_mode='Markdown')
        return SEMESTER
        
    elif choice == 'NAV_HOME':
        # Go back to start
        return await start(update, context)

async def cancel(update: Update, context: ContextTypes.DEFAULT_TYPE):
    await update.message.reply_text("🚫 **Operation Cancelled.** Type /start to restart.")
    return ConversationHandler.END

# --- MAIN EXECUTION ---
if __name__ == '__main__':
    # 1. Start Keep-Alive (For Render)
    try:
        from keep_alive import keep_alive
        keep_alive()
        print("✅ Web Server Started (Render Mode)")
    except ImportError:
        print("⚠️ keep_alive.py not found. Running in Local Mode.")

    print("🤖 BEU Premium Bot Starting...")
    application = ApplicationBuilder().token(BOT_TOKEN).build()

    # 2. Conversation Handler
    conv_handler = ConversationHandler(
        entry_points=[CommandHandler('start', start)],
        states={
            BATCH: [CallbackQueryHandler(batch_handler)],
            SEMESTER: [CallbackQueryHandler(semester_handler)],
            REG_NO: [MessageHandler(filters.TEXT & ~filters.COMMAND, get_result_handler)],
            RESULT_MENU: [CallbackQueryHandler(result_menu_handler)]
        },
        fallbacks=[CommandHandler('cancel', cancel)]
    )

    application.add_handler(conv_handler)
    
    # 3. Admin Handlers
    application.add_handler(CommandHandler("set", set_exam_date))
    application.add_handler(CommandHandler("view_config", view_config))

    # 4. Run
    application.run_polling()
