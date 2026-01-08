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
# ⚠️ Replace this with your actual Bot Token from BotFather
BOT_TOKEN = "8541634623:AAETR1SvO0or9cXE85lQBL4y2ChvwGZX36o" 

# API Config
BASE_URL = "https://www.beu-bih.ac.in/backend/v1/result/get-result"
# Default values (You can change these based on current exam cycle)
DEFAULT_YEAR = "2023"
DEFAULT_EXAM_HELD = "July/2025"

# States
SEMESTER, REG_NO = range(2)

# Semester Mapping for SGPA list index (Sem I -> Index 0)
SEM_MAP = {
    'I': 0, 'II': 1, 'III': 2, 'IV': 3, 
    'V': 4, 'VI': 5, 'VII': 6, 'VIII': 7
}

# Logging
logging.basicConfig(
    format='%(asctime)s - %(name)s - %(levelname)s - %(message)s',
    level=logging.INFO
)

async def start(update: Update, context: ContextTypes.DEFAULT_TYPE):
    """Starts the bot."""
    user_name = update.effective_user.first_name
    await update.message.reply_text(
        f"👋 **Namaste {user_name}!**\n\n"
        "Welcome to the **BEU Result Portal**.\n"
        "I can fetch your full marksheet directly.\n\n"
        "👇 **Select your Semester:**",
        parse_mode='Markdown'
    )
    
    # Semester Buttons
    keyboard = [
        [InlineKeyboardButton("Sem I", callback_data='I'), InlineKeyboardButton("Sem II", callback_data='II')],
        [InlineKeyboardButton("Sem III", callback_data='III'), InlineKeyboardButton("Sem IV", callback_data='IV')],
        [InlineKeyboardButton("Sem V", callback_data='V'), InlineKeyboardButton("Sem VI", callback_data='VI')],
        [InlineKeyboardButton("Sem VII", callback_data='VII'), InlineKeyboardButton("Sem VIII", callback_data='VIII')]
    ]
    reply_markup = InlineKeyboardMarkup(keyboard)
    await update.message.reply_text("Choose Semester:", reply_markup=reply_markup)
    return SEMESTER

async def semester_handler(update: Update, context: ContextTypes.DEFAULT_TYPE):
    """Handles semester selection."""
    query = update.callback_query
    await query.answer()
    
    selected_semester = query.data
    context.user_data['semester'] = selected_semester
    
    await query.edit_message_text(
        f"✅ **Semester {selected_semester}** selected.\n\n"
        "🔢 Please enter your **Registration Number** (e.g., 23103132004):",
        parse_mode='Markdown'
    )
    return REG_NO

async def get_result_handler(update: Update, context: ContextTypes.DEFAULT_TYPE):
    """Fetches and displays the detailed result."""
    reg_no = update.message.text.strip()
    semester = context.user_data.get('semester')
    
    if not reg_no.isdigit():
        await update.message.reply_text("❌ Invalid Registration Number. Please enter digits only.")
        return REG_NO

    status_msg = await update.message.reply_text("⏳ **Fetching Result from BEU Server...**", parse_mode='Markdown')

    # Prepare API Request
    params = {
        "year": DEFAULT_YEAR,
        "redg_no": reg_no,
        "semester": semester,
        "exam_held": DEFAULT_EXAM_HELD
    }

    try:
        response = requests.get(BASE_URL, params=params)
        
        if response.status_code == 200:
            result_json = response.json()
            
            # --- VALIDATION ---
            if result_json.get('status') != 200 or not result_json.get('data'):
                await context.bot.edit_message_text(
                    chat_id=update.effective_chat.id,
                    message_id=status_msg.message_id,
                    text="❌ **Result Not Found**\nPlease check your Registration Number or Semester."
                )
                return ConversationHandler.END

            # --- DATA PARSING ---
            data = result_json['data']
            
            # Personal Info
            name = data.get('name', 'N/A')
            father = data.get('father_name', 'N/A')
            mother = data.get('mother_name', 'N/A')
            college = data.get('college_name', 'N/A')
            course = data.get('course', 'N/A')
            
            # Result Info
            sgpa_list = data.get('sgpa', [])
            current_sgpa = "N/A"
            # Extract specific SGPA for this semester if available
            sem_index = SEM_MAP.get(semester, -1)
            if sem_index != -1 and sem_index < len(sgpa_list):
                current_sgpa = sgpa_list[sem_index] if sgpa_list[sem_index] else "Pending"
            
            cgpa = data.get('cgpa', 'N/A')
            fail_status = data.get('fail_any', 'PASS')
            if fail_status and "FAIL" in fail_status:
                final_status = f"🔴 {fail_status}" # Red circle for fail
            else:
                final_status = "🟢 PASS" # Green circle for pass

            # --- MESSAGE CONSTRUCTION ---
            msg = f"🏛 **BEU RESULT: {semester} ({data.get('exam_held')})**\n"
            msg += "━━━━━━━━━━━━━━━━━━\n"
            msg += f"👤 **Name:** `{name}`\n"
            msg += f"👨‍👩‍👦 **Parents:** {father} / {mother}\n"
            msg += f"🆔 **Reg No:** `{reg_no}`\n"
            msg += f"🏫 **College:** {college}\n"
            msg += f"🎓 **Course:** {course}\n"
            msg += "━━━━━━━━━━━━━━━━━━\n"
            
            # Theory Subjects Loop
            msg += "\n📝 **THEORY SUBJECTS:**\n"
            if data.get('theorySubjects'):
                for sub in data['theorySubjects']:
                    # Format: Name (Code): Total [Grade]
                    msg += f"• **{sub['name']}**\n"
                    msg += f"   └ Marks: {sub['total']} (ESE:{sub['ese']} + IA:{sub['ia']}) | Gd: {sub['grade']}\n"
            else:
                msg += "No Theory Subjects.\n"

            # Practical Subjects Loop
            msg += "\n🛠 **PRACTICAL / SESSIONAL:**\n"
            if data.get('practicalSubjects'):
                for sub in data['practicalSubjects']:
                    msg += f"• **{sub['name']}**\n"
                    msg += f"   └ Marks: {sub['total']} (ESE:{sub['ese']} + IA:{sub['ia']}) | Gd: {sub['grade']}\n"
            else:
                msg += "No Practical Subjects.\n"

            msg += "━━━━━━━━━━━━━━━━━━\n"
            msg += f"📊 **SGPA (Sem {semester}):** {current_sgpa}\n"
            msg += f"📈 **CGPA:** {cgpa}\n"
            msg += f"🏁 **RESULT:** {final_status}\n"
            msg += "━━━━━━━━━━━━━━━━━━\n"
            msg += "🤖 Generated by BEUHub Bot"

            # Send the big message
            await context.bot.edit_message_text(
                chat_id=update.effective_chat.id,
                message_id=status_msg.message_id,
                text=msg,
                parse_mode='Markdown'
            )

        else:
            await context.bot.edit_message_text(
                chat_id=update.effective_chat.id,
                message_id=status_msg.message_id,
                text=f"❌ **Server Error:** API responded with code {response.status_code}"
            )

    except Exception as e:
        await context.bot.edit_message_text(
            chat_id=update.effective_chat.id,
            message_id=status_msg.message_id,
            text=f"❌ **Error:** {str(e)}"
        )

    # Ask to check again
    keyboard = [[InlineKeyboardButton("🔍 Check Another Result", callback_data='restart')]]
    reply_markup = InlineKeyboardMarkup(keyboard)
    await update.message.reply_text("Check another student?", reply_markup=reply_markup)
    
    return ConversationHandler.END

async def cancel(update: Update, context: ContextTypes.DEFAULT_TYPE):
    """Cancels the conversation."""
    await update.message.reply_text("🚫 Operation Cancelled. Type /start to restart.")
    return ConversationHandler.END

async def restart(update: Update, context: ContextTypes.DEFAULT_TYPE):
    """Restart handler."""
    query = update.callback_query
    await query.answer()
    await start(update, context)
    return SEMESTER

# --- MAIN ---
if __name__ == '__main__':
    print("🤖 BEU Result Bot is Running...")
    application = ApplicationBuilder().token(BOT_TOKEN).build()

    conv_handler = ConversationHandler(
        entry_points=[CommandHandler('start', start)],
        states={
            SEMESTER: [CallbackQueryHandler(semester_handler)],
            REG_NO: [MessageHandler(filters.TEXT & ~filters.COMMAND, get_result_handler)],
        },
        fallbacks=[CommandHandler('cancel', cancel)]
    )

    application.add_handler(conv_handler)
    application.add_handler(CallbackQueryHandler(restart, pattern='^restart$'))

    application.run_polling()
