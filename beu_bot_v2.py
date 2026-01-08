import logging
import requests
import io
import datetime
import time  # Added for retry delay
from telegram import Update, InlineKeyboardButton, InlineKeyboardMarkup, BotCommand
from telegram.ext import (
    ApplicationBuilder,
    ContextTypes,
    CommandHandler,
    CallbackQueryHandler,
    MessageHandler,
    filters,
    ConversationHandler,
    Application
)

# PDF Library (HTML to PDF)
from xhtml2pdf import pisa

# --- CONFIGURATION ---
# ⚠️ Replace with your Bot Token
BOT_TOKEN = "8541634623:AAETR1SvO0or9cXE85lQBL4y2ChvwGZX36o"

# ⚠️ Admin ID (Phool Babu)
ADMIN_ID = 6716560182

# API Base URL
BASE_URL = "https://www.beu-bih.ac.in/backend/v1/result/get-result"

# --- DEFAULT EXAM CONFIGURATION (Master List) ---
EXAM_CONFIG = {
    "2025_I": "Jan/2026",
    "2024_II": "Nov/2025",
    "2024_I": "May/2025",
    "2023_IV": "Dec/2025",
    "2023_III": "July/2025",
    "2023_II": "Dec/2024",
    "2023_I": "May/2024",
    "2022_VI": "Nov/2025",
    "2022_V": "July/2025",
    "2022_IV": "Dec/2024",
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

# --- HELPER: API RETRY LOGIC ---
def fetch_result_with_retry(params, max_retries=6):
    """
    Tries to fetch result from BEU server. 
    If server is down, it retries 'max_retries' times with a delay.
    """
    for attempt in range(1, max_retries + 1):
        try:
            response = requests.get(BASE_URL, params=params, timeout=10) # 10s timeout
            if response.status_code == 200:
                data = response.json()
                # Check if API returned valid data structure
                if data.get('status') == 200 and data.get('data'):
                    return data
        except requests.RequestException as e:
            print(f"⚠️ Attempt {attempt} failed: {e}")
        
        # If failed, wait 2 seconds before next try
        if attempt < max_retries:
            time.sleep(2)
            
    return None # Failed after all retries

# --- HELPER: GENERATE PDF MARKSHEET ---
def generate_pdf_in_memory(data, batch, sem, exam_held):
    """
    Creates a professional Marksheet PDF using HTML and CSS based on the PHP design.
    """
    
    name = data.get('name', 'N/A')
    reg_no = data.get('redg_no', 'N/A')
    college = data.get('college_name', 'N/A')
    college_code = data.get('college_code', '')
    course = data.get('course', 'B.Tech')
    course_code = data.get('course_code', '')
    father_name = data.get('father_name', 'N/A')
    mother_name = data.get('mother_name', 'N/A')
    cgpa = data.get('cgpa', 'N/A')
    
    publish_date = datetime.date.today().strftime("%d-%b-%Y")
    
    sgpa_list = data.get('sgpa', [])
    current_sgpa = "N/A"
    sem_map = {'I':0, 'II':1, 'III':2, 'IV':3, 'V':4, 'VI':5, 'VII':6, 'VIII':7}
    if sem in sem_map and sem_map[sem] < len(sgpa_list):
        val = sgpa_list[sem_map[sem]]
        current_sgpa = val if val else "Pending"
        
    fail_raw = data.get('fail_any', '')
    if fail_raw and "FAIL" in str(fail_raw):
        remarks_text = "FAIL"
        remarks_style = "color: red;"
    else:
        remarks_text = "PASS"
        remarks_style = "color: green;"

    theory_rows = ""
    if data.get('theorySubjects'):
        for sub in data['theorySubjects']:
            grade = sub.get('grade', '-')
            grade_style = "color: red;" if grade == 'F' else "color: black;"
            credit = sub.get('credit', '-')
            theory_rows += f"""
            <tr>
                <td style="text-align:center;">{sub.get('code', '')}</td>
                <td>{sub.get('name', '')}</td>
                <td style="text-align:center;">{sub.get('ese', '-')}</td>
                <td style="text-align:center;">{sub.get('ia', '-')}</td>
                <td style="text-align:center; font-weight:bold;">{sub.get('total', '-')}</td>
                <td style="text-align:center; font-weight:bold; {grade_style}">{grade}</td>
                <td style="text-align:center;">{credit}</td>
            </tr>
            """
    else:
        theory_rows = "<tr><td colspan='7' style='text-align:center;'>No Theory Subjects</td></tr>"

    practical_rows = ""
    if data.get('practicalSubjects'):
        for sub in data['practicalSubjects']:
            grade = sub.get('grade', '-')
            grade_style = "color: red;" if grade == 'F' else "color: black;"
            credit = sub.get('credit', '-')
            practical_rows += f"""
            <tr>
                <td style="text-align:center;">{sub.get('code', '')}</td>
                <td>{sub.get('name', '')}</td>
                <td style="text-align:center;">{sub.get('ese', '-')}</td>
                <td style="text-align:center;">{sub.get('ia', '-')}</td>
                <td style="text-align:center; font-weight:bold;">{sub.get('total', '-')}</td>
                <td style="text-align:center; font-weight:bold; {grade_style}">{grade}</td>
                <td style="text-align:center;">{credit}</td>
            </tr>
            """

    sem_romans = ['I', 'II', 'III', 'IV', 'V', 'VI', 'VII', 'VIII']
    history_header = ""
    history_data = ""
    for idx, rom in enumerate(sem_romans):
        history_header += f"<th style='width: 11%;'>{rom}</th>"
        val = "-"
        if idx < len(sgpa_list) and sgpa_list[idx] is not None:
             val = sgpa_list[idx]
        history_data += f"<td>{val}</td>"

    html_content = f"""
    <!DOCTYPE html>
    <html>
    <head>
        <style>
            @page {{ size: A4; margin: 1cm; }}
            body {{ font-family: 'Times New Roman', serif; font-size: 12px; color: #000; }}
            .univ-title {{ font-size: 22pt; font-weight: bold; text-transform: uppercase; text-align: center; }}
            .sub-title {{ font-size: 14pt; font-weight: bold; margin-top: 5px; color: #333; text-align: center; }}
            .exam-session {{ font-size: 11pt; margin-top: 5px; font-weight: bold; text-align: center; }}
            table {{ width: 100%; border-collapse: collapse; font-size: 10.5pt; margin-bottom: 15px; }}
            .marks-table th {{ background-color: #f0f0f0; font-weight: bold; text-transform: uppercase; font-size: 9pt; border: 1px solid #000; padding: 4px 6px; text-align: center; }}
            .marks-table td {{ border: 1px solid #000; padding: 4px 6px; vertical-align: middle; }}
            .info-table td {{ padding: 5px 2px; vertical-align: top; border: none; }}
            .summary-box {{ border: 1px solid #000; padding: 10px; margin-top: 10px; background-color: #fafafa; }}
            .header-container {{ text-align: center; margin-bottom: 20px; border-bottom: 1px solid #000; padding-bottom: 20px; }}
            .footer {{ text-align: center; margin-top: 30px; font-size: 9pt; color: #777; border-top: 1px solid #ccc; padding-top: 10px; }}
        </style>
    </head>
    <body>
        <div class="header-container">
            <div class="univ-title">Bihar Engineering University</div>
            <div class="sub-title">Patna, Bihar</div>
            <div style="margin-top:10px; font-size:12pt; font-weight:bold; text-transform: uppercase; text-align: center;">B.Tech {sem} Semester Examination</div>
            <div class="exam-session">Session: {exam_held}</div>
        </div>
        <table class="info-table">
            <tr><td style="width: 140px;"><strong>Registration No:</strong></td><td style="font-weight:bold; font-family:'Courier New', monospace; font-size: 12pt;">{reg_no}</td></tr>
            <tr><td><strong>Student Name:</strong></td><td style="font-weight:bold; text-transform:uppercase;">{name}</td></tr>
            <tr><td><strong>Father Name:</strong></td><td>{father_name}</td><td style="width: 120px;"><strong>Mother Name:</strong></td><td>{mother_name}</td></tr>
            <tr><td><strong>College Name:</strong></td><td colspan="3">{college_code} - {college}</td></tr>
            <tr><td><strong>Course Name:</strong></td><td colspan="3">{course_code} - {course}</td></tr>
        </table>
        <div style="font-weight:bold; margin-bottom:5px; text-decoration: underline;">THEORY</div>
        <table class="marks-table"><thead><tr><th style="width: 15%;">Subject Code</th><th style="text-align: left;">Subject Name</th><th style="width: 8%;">ESE</th><th style="width: 8%;">IA</th><th style="width: 8%;">Total</th><th style="width: 8%;">Grade</th><th style="width: 8%;">Credit</th></tr></thead><tbody>{theory_rows}</tbody></table>
        <div style="font-weight:bold; margin-bottom:5px; margin-top:15px; text-decoration: underline;">PRACTICAL</div>
        <table class="marks-table"><thead><tr><th style="width: 15%;">Subject Code</th><th style="text-align: left;">Subject Name</th><th style="width: 8%;">ESE</th><th style="width: 8%;">IA</th><th style="width: 8%;">Total</th><th style="width: 8%;">Grade</th><th style="width: 8%;">Credit</th></tr></thead><tbody>{practical_rows}</tbody></table>
        <div style="font-weight:bold; margin-bottom:5px; margin-top:15px; text-decoration: underline;">ACADEMIC PROGRESS</div>
        <table class="marks-table" style="text-align: center;"><thead><tr>{history_header}<th style="width: 12%; background-color: #333; color: white;">Cur. CGPA</th></tr></thead><tbody><tr>{history_data}<td style="font-weight: bold;">{cgpa}</td></tr></tbody></table>
        <div class="summary-box">
            <table style="width: 100%; border: none; margin: 0;">
                <tr style="border: none;">
                    <td style="border: none; text-align: left; width: 33%;"><strong>SGPA: </strong> <span style="font-size: 14pt; border: 2px solid #000; padding: 2px 8px; margin-left: 5px;">{current_sgpa}</span></td>
                    <td style="border: none; text-align: center; width: 33%;"><strong>CGPA: </strong> <span>{cgpa}</span></td>
                    <td style="border: none; text-align: right; width: 33%;"><strong>REMARKS: </strong> <span style="font-weight: bold; {remarks_style}">{remarks_text}</span></td>
                </tr>
            </table>
        </div>
        <div style="margin-top: 10px; font-size: 10pt;"><strong>Publish Date:</strong> {publish_date}</div>
        <div class="footer">Generated via BEU Result Bot | beuhub.site</div>
    </body>
    </html>
    """

    pdf_file = io.BytesIO()
    pisa_status = pisa.CreatePDF(io.BytesIO(html_content.encode("utf-8")), dest=pdf_file)
    if pisa_status.err: return None
    pdf_file.seek(0)
    return pdf_file

# --- HELPER: FORMAT RESULT TEXT ---
def format_marksheet_text(data, batch, sem, exam_held):
    name = data.get('name', 'N/A')
    reg_no = data.get('redg_no', 'N/A')
    college = data.get('college_name', 'N/A')
    
    sgpa_list = data.get('sgpa', [])
    current_sgpa = "N/A"
    sem_map = {'I':0, 'II':1, 'III':2, 'IV':3, 'V':4, 'VI':5, 'VII':6, 'VIII':7}
    if sem in sem_map and sem_map[sem] < len(sgpa_list):
        val = sgpa_list[sem_map[sem]]
        current_sgpa = val if val else "Pending"

    fail_raw = data.get('fail_any', '')
    if fail_raw and "FAIL" in str(fail_raw):
        status_icon = "🔴 FAIL"
        status_details = f"Backlog: {fail_raw.replace('FAIL:', '')}"
    else:
        status_icon = "🟢 PASS"
        status_details = "All Clear! Excellent Work. 🎉"

    msg = f"{HEADER_TEXT}\n"
    msg += f"🏛 **BEU OFFICIAL RESULT**\n"
    msg += f"📅 `Batch {batch} | Sem {sem} ({exam_held})`\n"
    msg += "━━━━━━━━━━━━━━━━━━\n"
    msg += f"👤 **{name}**\n"
    msg += f"🆔 `{reg_no}`\n"
    msg += f"🏫 _{college}_\n"
    msg += "━━━━━━━━━━━━━━━━━━\n"
    msg += "📝 **THEORY PAPERS**\n"
    
    if data.get('theorySubjects'):
        for sub in data['theorySubjects']:
            grade = sub['grade']
            grade_display = f"⚠️ {grade}" if grade == 'F' else f"✅ {grade}"
            msg += f"**• {sub['name']}** `({sub['code']})`\n"
            msg += f"   └ Marks: `{sub['total']}` (E:{sub['ese']}+I:{sub['ia']}) | Gd: {grade_display}\n"
    else:
        msg += "   _(No Theory Data Available)_\n"
    
    msg += "\n🛠 **PRACTICALS**\n"
    if data.get('practicalSubjects'):
        for sub in data['practicalSubjects']:
            msg += f"**• {sub['name']}**\n"
            msg += f"   └ Marks: `{sub['total']}` | Grade: {sub['grade']}\n"
            
    msg += "━━━━━━━━━━━━━━━━━━\n"
    msg += f"🔹 **SGPA:** `{current_sgpa}` | 🔸 **CGPA:** `{data.get('cgpa', 'N/A')}`\n"
    msg += f"🏁 **STATUS:** {status_icon}\n"
    msg += f"📢 {status_details}\n"
    msg += f"{FOOTER_TEXT}"
    return msg

# --- ADMIN COMMANDS ---
async def set_exam_date(update: Update, context: ContextTypes.DEFAULT_TYPE):
    user_id = update.effective_user.id
    if user_id != ADMIN_ID:
        await update.message.reply_text("⛔ **Access Denied.** Admin only.")
        return

    try:
        args = context.args
        if len(args) < 3:
            await update.message.reply_text("⚠️ Usage: `/set 2023 III July/2025`", parse_mode='Markdown')
            return

        batch = args[0]
        sem = args[1]
        exam_date = args[2] 
        EXAM_CONFIG[f"{batch}_{sem}"] = exam_date
        await update.message.reply_text(f"✅ Saved: `{batch}` | `{sem}` | `{exam_date}`", parse_mode='Markdown')
    except Exception as e:
        await update.message.reply_text(f"❌ Error: {str(e)}")

async def view_config(update: Update, context: ContextTypes.DEFAULT_TYPE):
    if update.effective_user.id != ADMIN_ID: return
    msg = "⚙️ **Active Configurations:**\n\n"
    for key, val in EXAM_CONFIG.items():
        b, s = key.split('_')
        msg += f"🔹 **{b} (Sem {s}):** `{val}`\n"
    await update.message.reply_text(msg, parse_mode='Markdown')

# --- HANDLERS ---

async def start(update: Update, context: ContextTypes.DEFAULT_TYPE):
    """Starts the bot or Resets the conversation."""
    user = update.effective_user.first_name
    
    # Clear any previous user data to ensure a fresh start
    context.user_data.clear()
    
    # Updated Welcome Message
    intro = (
        f"{HEADER_TEXT}\n"
        f"👋 **Hello {user}!**\n\n"
        "🎓 **Welcome to the BEU Result Portal.**\n\n"
        "🤖 **What this Bot can do:**\n"
        "✅ **Fetch Results:** Check any semester result instantly.\n"
        "✅ **PDF Downloads:** Get professional marksheet PDFs.\n"
        "✅ **Server Bypass:** Auto-retries if BEU site is down.\n"
        "✅ **Secure:** Your data is safe & private.\n\n"
        "👇 **Select your Batch Year to start:**"
    )
    keyboard = [
        [InlineKeyboardButton("2022", callback_data='2022'), InlineKeyboardButton("2023", callback_data='2023')],
        [InlineKeyboardButton("2024", callback_data='2024'), InlineKeyboardButton("2025", callback_data='2025')],
        [InlineKeyboardButton("2026", callback_data='2026')]
    ]
    reply_markup = InlineKeyboardMarkup(keyboard)
    
    # If called via CallbackQuery (e.g. Back button)
    if update.callback_query:
        await update.callback_query.message.reply_text(text=intro, reply_markup=reply_markup, parse_mode='Markdown')
    else:
        await update.message.reply_text(text=intro, reply_markup=reply_markup, parse_mode='Markdown')
        
    return BATCH

async def unknown_text(update: Update, context: ContextTypes.DEFAULT_TYPE):
    """Handles unnecessary text input and guides user to start."""
    await update.message.reply_text(
        "⚠️ **Invalid Input!**\n\n"
        "Please do not type unnecessary text.\n"
        "To start or check result, click here 👉 /start",
        parse_mode='Markdown'
    )

async def batch_handler(update: Update, context: ContextTypes.DEFAULT_TYPE):
    query = update.callback_query
    await query.answer()
    context.user_data['batch'] = query.data
    
    keyboard = [
        [InlineKeyboardButton("Sem I", callback_data='I'), InlineKeyboardButton("Sem II", callback_data='II')],
        [InlineKeyboardButton("Sem III", callback_data='III'), InlineKeyboardButton("Sem IV", callback_data='IV')],
        [InlineKeyboardButton("Sem V", callback_data='V'), InlineKeyboardButton("Sem VI", callback_data='VI')],
        [InlineKeyboardButton("Sem VII", callback_data='VII'), InlineKeyboardButton("Sem VIII", callback_data='VIII')]
    ]
    await query.edit_message_text(
        f"{HEADER_TEXT}\n✅ **Batch {query.data} Selected.**\n👇 Select **Semester**:", 
        reply_markup=InlineKeyboardMarkup(keyboard), 
        parse_mode='Markdown'
    )
    return SEMESTER

async def semester_handler(update: Update, context: ContextTypes.DEFAULT_TYPE):
    query = update.callback_query
    await query.answer()
    context.user_data['semester'] = query.data
    await query.edit_message_text(
        f"{HEADER_TEXT}\n✅ **Batch {context.user_data['batch']} | Sem {query.data}**\n\n"
        f"🔢 **Enter Registration Number:**\n_(e.g. 23101132025)_", 
        parse_mode='Markdown'
    )
    return REG_NO

async def get_result_handler(update: Update, context: ContextTypes.DEFAULT_TYPE):
    reg_no = update.message.text.strip()
    
    # Check if user accidentally typed a command or random text
    if not reg_no.isdigit():
        await update.message.reply_text(
            "❌ **Invalid Registration Number!**\n"
            "Please enter digits only (e.g., 23103132004).\n\n"
            "If you want to restart, type /start",
            parse_mode='Markdown'
        )
        return REG_NO

    batch = context.user_data.get('batch')
    sem = context.user_data.get('semester')
    context.user_data['reg_no'] = reg_no

    config_key = f"{batch}_{sem}"
    exam_held = EXAM_CONFIG.get(config_key)
    
    if not exam_held:
        await update.message.reply_text(f"⚠️ **Result Not Available Yet!**\nAdmin config missing for {batch}-{sem}.")
        return ConversationHandler.END

    status_msg = await update.message.reply_text("⏳ **Fetching Result...**")

    params = {"year": batch, "redg_no": reg_no, "semester": sem, "exam_held": exam_held}

    # USE RETRY LOGIC HERE
    data_json = fetch_result_with_retry(params)
    
    if data_json and data_json.get('data'):
        data = data_json['data']
        result_text = format_marksheet_text(data, batch, sem, exam_held)
        
        await context.bot.edit_message_text(
            chat_id=update.effective_chat.id, 
            message_id=status_msg.message_id, 
            text=result_text, 
            parse_mode='Markdown'
        )
        
        keyboard = [
            [InlineKeyboardButton("📥 Download PDF Marksheet", callback_data='NAV_PDF')],
            [InlineKeyboardButton("🔍 Check Another (Same Sem)", callback_data='NAV_SAME')],
            [InlineKeyboardButton("📂 Change Semester", callback_data='NAV_SEM')],
            [InlineKeyboardButton("🏠 Main Menu", callback_data='NAV_HOME')]
        ]
        await update.message.reply_text("👇 **Actions:**", reply_markup=InlineKeyboardMarkup(keyboard))
        return RESULT_MENU
    else:
        # Error handling if retry failed or data is empty
        await context.bot.edit_message_text(
            chat_id=update.effective_chat.id, 
            message_id=status_msg.message_id, 
            text=f"❌ **Result Not Found / Server Busy.**\nChecked Reg No: `{reg_no}`\n(Tried 6 times). Try again later.", 
            parse_mode='Markdown'
        )
        return ConversationHandler.END

async def result_menu_handler(update: Update, context: ContextTypes.DEFAULT_TYPE):
    query = update.callback_query
    await query.answer()
    choice = query.data
    
    if choice == 'NAV_PDF':
        await query.message.reply_text("⏳ **Generating PDF... Please wait.**")
        batch = context.user_data.get('batch')
        sem = context.user_data.get('semester')
        reg_no = context.user_data.get('reg_no')
        exam_held = EXAM_CONFIG.get(f"{batch}_{sem}")
        
        params = {"year": batch, "redg_no": reg_no, "semester": sem, "exam_held": exam_held}
        
        # USE RETRY LOGIC HERE TOO
        data_json = fetch_result_with_retry(params)
        
        if data_json and data_json.get('data'):
            pdf_file = generate_pdf_in_memory(data_json['data'], batch, sem, exam_held)
            if pdf_file:
                await context.bot.send_document(
                    chat_id=update.effective_chat.id,
                    document=pdf_file,
                    filename=f"BEU_Result_{reg_no}_{sem}.pdf",
                    caption=f"📄 **Official Marksheet**\nReg No: {reg_no}\n{FOOTER_TEXT}",
                    parse_mode='Markdown'
                )
            else:
                await query.message.reply_text("❌ Error creating PDF file.")
        else:
            await query.message.reply_text("❌ Error fetching data for PDF (Server Busy).")
        return RESULT_MENU

    elif choice == 'NAV_SAME':
        text = f"{HEADER_TEXT}\n🔄 **Check Another** (Batch {context.user_data.get('batch')} | Sem {context.user_data.get('semester')})\n🔢 **Enter Reg No:**"
        await query.edit_message_text(text=text, parse_mode='Markdown')
        return REG_NO
        
    elif choice == 'NAV_SEM':
        keyboard = [
            [InlineKeyboardButton("Sem I", callback_data='I'), InlineKeyboardButton("Sem II", callback_data='II')],
            [InlineKeyboardButton("Sem III", callback_data='III'), InlineKeyboardButton("Sem IV", callback_data='IV')],
            [InlineKeyboardButton("Sem V", callback_data='V'), InlineKeyboardButton("Sem VI", callback_data='VI')],
            [InlineKeyboardButton("Sem VII", callback_data='VII'), InlineKeyboardButton("Sem VIII", callback_data='VIII')]
        ]
        text = f"{HEADER_TEXT}\n📂 **Change Semester** (Batch {context.user_data.get('batch')})\n👇 Select Semester:"
        await query.edit_message_text(text=text, reply_markup=InlineKeyboardMarkup(keyboard), parse_mode='Markdown')
        return SEMESTER
        
    elif choice == 'NAV_HOME':
        return await start(update, context)

async def cancel(update: Update, context: ContextTypes.DEFAULT_TYPE):
    await update.message.reply_text("🚫 **Cancelled.** Type /start to restart.")
    return ConversationHandler.END

# --- POST INIT: SET COMMANDS ---
async def post_init(application: Application):
    """Sets the bot commands menu when bot starts."""
    await application.bot.set_my_commands([
        BotCommand("start", "Restart Bot / Check Result"),
        BotCommand("set", "for Admin),
        BotCommand("view_config", "Admin: View Config")
    ])

# --- MAIN ---
if __name__ == '__main__':
    try:
        from keep_alive import keep_alive
        keep_alive()
    except: pass

    print("🤖 BEU Premium Bot (PDF + Suggestions + Auto-Retry) Starting...")
    
    # Updated Builder to include post_init
    application = ApplicationBuilder().token(BOT_TOKEN).post_init(post_init).build()

    conv_handler = ConversationHandler(
        entry_points=[CommandHandler('start', start)],
        states={
            BATCH: [CallbackQueryHandler(batch_handler)],
            SEMESTER: [CallbackQueryHandler(semester_handler)],
            REG_NO: [MessageHandler(filters.TEXT & ~filters.COMMAND, get_result_handler)],
            RESULT_MENU: [CallbackQueryHandler(result_menu_handler)]
        },
        fallbacks=[
            CommandHandler('start', start), # Allows /start at any point
            CommandHandler('cancel', cancel),
            MessageHandler(filters.TEXT & ~filters.COMMAND, unknown_text) # Catches garbage text
        ]
    )

    application.add_handler(conv_handler)
    
    # Global handler for unknown text when not in conversation
    application.add_handler(MessageHandler(filters.TEXT & ~filters.COMMAND, unknown_text))
    
    # Admin Handlers
    application.add_handler(CommandHandler("set", set_exam_date))
    application.add_handler(CommandHandler("view_config", view_config))

    application.run_polling()
