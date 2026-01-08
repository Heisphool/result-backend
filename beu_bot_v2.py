import logging
import requests
import os
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

# --- IMPORT KEEP_ALIVE ---
# This requires a file named keep_alive.py in the same folder
try:
    from keep_alive import keep_alive
except ImportError:
    # Fallback if file doesn't exist (e.g. running locally without it)
    def keep_alive():
        print("Keep alive module not found. Skipping web server.")

# --- CONFIGURATION ---
# Your Specific Bot Token
BOT_TOKEN = "8541634623:AAETR1SvO0or9cXE85lQBL4y2ChvwGZX36o"

# API Config
BASE_URL = "https://www.beu-bih.ac.in/backend/v1/result/get-result"
# Default values
DEFAULT_YEAR = "2023"
DEFAULT_EXAM_HELD = "July/2025"

# States for Conversation
SEMESTER, REG_NO = range(2)

# Semester Mapping for SGPA list index (Sem I -> Index 0)
SEM_MAP = {
    'I': 0, 'II': 1, 'III': 2, 'IV': 3, 
    'V': 4, 'VI': 5, 'VII': 6, 'VIII': 7
}

# Logging Setup
logging.basicConfig(
    format='%(asctime)s - %(name)s - %(levelname)s - %(message)s',
    level=logging.INFO
)

async def start(update: Update, context: ContextTypes.DEFAULT_TYPE):
    """Starts the conversation and asks for Semester."""
    user = update.effective_user.first_name
    await update.message.reply_text(
        f"👋 **Namaste {user}!**\n\n"
        "Welcome to the **BEU Result Bot**.\n"
        "I can fetch your full marksheet directly.\n\n"
        "👇 **Please select your Semester:**",
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
    
    await update.message.reply_text("Choose your semester:", reply_markup=reply_markup)
    return SEMESTER

async def semester_handler(update: Update, context: ContextTypes.DEFAULT_TYPE):
    """Saves the semester and asks for Registration Number."""
    query = update.callback_query
    await query.answer() 
    
    selected_semester = query.data
    context.user_data['semester'] = selected_semester
    
    await query.edit_message_text(
        f"✅ **Semester {selected_semester}** selected.\n\n"
        "🔢 Now, please enter your **Registration Number** (e.g., 23103132004):",
        parse_mode='Markdown'
    )
    return REG_NO

async def get_result_handler(update: Update, context: ContextTypes.DEFAULT_TYPE):
    """Fetches result from API and shows it."""
    reg_no = update.message.text.strip()
    semester = context.user_data.get('semester')
    
    # Validate Reg No
    if not reg_no.isdigit():
        await update.message.reply_text("❌ Invalid Registration Number. Please enter numbers only.")
        return REG_NO

    status_msg = await update.message.reply_text("⏳ **Fetching Result from BEU Server...**", parse_mode='Markdown')

    # API Parameters
    params = {
        "year": DEFAULT_YEAR,
        "redg_no": reg_no,
        "semester": semester,
        "exam_held": DEFAULT_EXAM_HELD
    }

    try:
        # Requesting data
        response = requests.get(BASE_URL, params=params)
        
        if response.status_code == 200:
            result_json = response.json()
            
            # Check if API returned success and data exists
            if result_json.get('status') != 200 or not result_json.get('data'):
                await context.bot.edit_message_text(
                    chat_id=update.effective_chat.id,
                    message_id=status_msg.message_id,
                    text="❌ **Result Not Found**\nPlease check your Registration Number or Semester."
                )
                return ConversationHandler.END

            # Parsing Data
            data = result_json['data']
            
            # Personal Info
            name = data.get('name', 'N/A')
            father = data.get('father_name', 'N/A')
            mother = data.get('mother_name', 'N/A')
            college = data.get('college_name', 'N/A')
            course = data.get('course', 'N/A')
            
            # Marks & Status
            sgpa_list = data.get('sgpa', [])
            current_sgpa = "N/A"
            sem_index = SEM_MAP.get(semester, -1)
            
            if sem_index != -1 and sgpa_list and sem_index < len(sgpa_list):
                 current_sgpa = sgpa_list[sem_index] if sgpa_list[sem_index] is not None else "Pending"
            
            cgpa = data.get('cgpa', 'N/A')
            
            # Fail logic: "fail_any": "FAIL:100310" or null/empty
            fail_status = data.get('fail_any')
            if fail_status and "FAIL" in str(fail_status):
                 final_status = f"🔴 {fail_status}"
            else:
                 final_status = "🟢 PASS"

            # Constructing the Message
            msg = f"🏛 **BEU RESULT: {semester} ({data.get('exam_held', DEFAULT_EXAM_HELD)})**\n"
            msg += "━━━━━━━━━━━━━━━━━━\n"
            msg += f"👤 **Name:** `{name}`\n"
            msg += f"👨‍👩‍👦 **Parents:** {father} / {mother}\n"
            msg += f"🆔 **Reg No:** `{reg_no}`\n"
            msg += f"🏫 **College:** {college}\n"
            msg += f"🎓 **Course:** {course}\n"
            msg += "━━━━━━━━━━━━━━━━━━\n"
            
            # Theory Subjects
            msg += "\n📝 **THEORY SUBJECTS:**\n"
            if data.get('theorySubjects'):
                for sub in data['theorySubjects']:
                    msg += f"• **{sub['name']}**\n"
                    msg += f"   └ Marks: {sub['total']} (ESE:{sub['ese']} + IA:{sub['ia']}) | Gd: {sub['grade']}\n"
            else:
                msg += "No Theory Subjects.\n"

            # Practical Subjects
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

    # Ask to check another result
    keyboard = [[InlineKeyboardButton("🔍 Check Another Result", callback_data='restart')]]
    reply_markup = InlineKeyboardMarkup(keyboard)
    await update.message.reply_text("Do you want to check another student?", reply_markup=reply_markup)
    
    return ConversationHandler.END

async def cancel(update: Update, context: ContextTypes.DEFAULT_TYPE):
    """Cancels the operation."""
    await update.message.reply_text("🚫 Operation Cancelled. Type /start to try again.")
    return ConversationHandler.END

async def restart(update: Update, context: ContextTypes.DEFAULT_TYPE):
    """Restart handler for the button."""
    query = update.callback_query
    await query.answer()
    await start(update, context) 
    return SEMESTER

# --- MAIN EXECUTION ---
if __name__ == '__main__':
    print("🤖 BEU Result Bot is starting...")
    
    # 1. Start the 'Keep Alive' web server (for Render)
    keep_alive()
    
    # 2. Build the Bot Application
    application = ApplicationBuilder().token(BOT_TOKEN).build()

    # 3. Setup Conversation Handler
    conv_handler = ConversationHandler(
        entry_points=[CommandHandler('start', start)],
        states={
            SEMESTER: [CallbackQueryHandler(semester_handler)],
            REG_NO: [MessageHandler(filters.TEXT & ~filters.COMMAND, get_result_handler)],
        },
        fallbacks=[CommandHandler('cancel', cancel)]
    )

    # 4. Add Handlers
    application.add_handler(conv_handler)
    application.add_handler(CallbackQueryHandler(restart, pattern='^restart$'))

    # 5. Run the Bot
    application.run_polling()
  
