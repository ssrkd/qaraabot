from telegram import Update, ReplyKeyboardMarkup, ReplyKeyboardRemove, Chat
from telegram.ext import Application, CommandHandler, MessageHandler, ContextTypes, filters
from supabase import create_client
from datetime import datetime, timedelta
import pytz

# --- Supabase ---
SUPABASE_URL = "https://jghlvdgtowjattktkejw.supabase.co"
SUPABASE_KEY = "eyJhbGciOiJIUzI1NiIsInR5cCI6IkpXVCJ9.eyJpc3MiOiJzdXBhYmFzZSIsInJlZiI6ImpnaGx2ZGd0b3dqYXR0a3RrZWp3Iiwicm9sZSI6ImFub24iLCJpYXQiOjE3NTkxNTc2NzYsImV4cCI6MjA3NDczMzY3Nn0.IxceNDdpFHPPkOwjlk644C1fji4wAhQr2dR8FmEKVas"
supabase = create_client(SUPABASE_URL, SUPABASE_KEY)

# --- Telegram ---
BOT_TOKEN = "8458767187:AAHV6sl14LzVt1Bnk49LvoR6QYg7MAvbYhA"

# --- Админы и сотрудники ---
OWNER_IDS = [996317285]
SELLER_IDS = [6924074231]

# --- Группа ---
GROUP_ID = -1003107339633
GROUP_NAME = None

# --- Временные состояния ---
waiting_for_message = {}           # Для /zov
report_sessions = {}               # {user_id: {"messages": [], "active": True}}
waiting_reports_selection = {}     # {user_id: True} для выбора периода в /reports
waiting_for_new_seller_id = {}     # {admin_id: True}
waiting_for_remove_seller = {}     # {admin_id: True}

# --- Вспомогательные функции ---
def format_datetime_astro(dt_str):
    dt = datetime.fromisoformat(dt_str)
    dt = dt.astimezone(pytz.timezone("Asia/Almaty"))
    return dt.strftime("%d.%m.%Y %H:%M:%S")

def format_user(user):
    return f"{user.id} (@{user.username})" if user.username else f"{user.id} ({user.full_name})"

def astana_now():
    return datetime.now(pytz.timezone("Asia/Almaty"))

# --- Команды ---
async def start(update: Update, context: ContextTypes.DEFAULT_TYPE):
    user = update.effective_user
    user_id = user.id
    first_name = user.first_name

    if user_id in OWNER_IDS:
        await update.message.reply_text("Добро пожаловать 👑 У вас админ-доступ. Команды: /help")
    elif user_id in SELLER_IDS:
        await update.message.reply_text(f"{first_name}, вы зарегистрированы как сотрудник 🧑‍💼.\nДоступная команда: /report")
    else:
        await update.message.reply_text(f"{first_name}, у вас нет доступа.")

async def help_command(update: Update, context: ContextTypes.DEFAULT_TYPE):
    user_id = update.effective_user.id
    if user_id in OWNER_IDS:
        await update.message.reply_text(
            "📋 Доступные команды:\n"
            "/zov — отправить сообщение в группу\n"
            "/status — состояние бота\n"
            # "/staff — список сотрудников\n"
            "/reports — просмотреть отчёты\n"
            "/add_seller — добавить продавца\n"
            "/remove_seller — удалить продавца\n"
            "/list_sellers — просмотреть продавцов"
        )
    elif user_id in SELLER_IDS:
        await update.message.reply_text("📋 Доступные команды:\n/report — сдать отчёт")
    else:
        await update.message.reply_text("⛔ У вас нет доступа.")

async def status(update: Update, context: ContextTypes.DEFAULT_TYPE):
    if update.effective_user.id not in OWNER_IDS:
        return

    global GROUP_NAME
    if GROUP_NAME is None:
        try:
            chat: Chat = await context.bot.get_chat(GROUP_ID)
            GROUP_NAME = chat.title
        except:
            GROUP_NAME = "❓ Неизвестно"

    admin_list = [f"- {format_user(await context.bot.get_chat(uid))}" for uid in OWNER_IDS]
    staff_list = [f"- {format_user(await context.bot.get_chat(uid))}" for uid in SELLER_IDS]

    await update.message.reply_text(
        f"🤖 Бот работает\n"
        f"📌 Подключён к группе: {GROUP_NAME}\n"
        f"👑 Админы:\n" + "\n".join(admin_list) + "\n"
        f"🧑‍💼 Сотрудники:\n" + ("\n".join(staff_list) if staff_list else "Нет сотрудников")
    )

async def staff(update: Update, context: ContextTypes.DEFAULT_TYPE):
    if update.effective_user.id not in OWNER_IDS:
        return
    staff_list = [f"- {format_user(await context.bot.get_chat(uid))}" for uid in SELLER_IDS]
    await update.message.reply_text("🧑‍💼 Сотрудники:\n" + ("\n".join(staff_list) if staff_list else "❌ Сотрудников нет."))

# --- ZOV ---
async def zov(update: Update, context: ContextTypes.DEFAULT_TYPE):
    user_id = update.effective_user.id
    if user_id in OWNER_IDS:
        waiting_for_message[user_id] = True
        await update.message.reply_text("✍️ Отправьте сообщение, и я перешлю его в группу.")
    else:
        await update.message.reply_text("⛔ У вас нет доступа.")

# --- Report ---
async def report(update: Update, context: ContextTypes.DEFAULT_TYPE):
    user_id = update.effective_user.id
    if user_id in SELLER_IDS:
        report_sessions[user_id] = {"messages": [], "active": True}
        await update.message.reply_text("✍️ Напишите или прикрепите отчёт (текст, фото, файл).")
    else:
        await update.message.reply_text("⛔ У вас нет доступа.")

# --- Reports ---
async def reports(update: Update, context: ContextTypes.DEFAULT_TYPE):
    user_id = update.effective_user.id
    if user_id not in OWNER_IDS:
        return
    keyboard = [["Сегодня", "Вчера"], ["Неделя", "Месяц"], ["Год", "Всё"]]
    reply_markup = ReplyKeyboardMarkup(keyboard, one_time_keyboard=True, resize_keyboard=True)
    await update.message.reply_text("Выберите период:", reply_markup=reply_markup)
    waiting_reports_selection[user_id] = True

async def handle_reports_selection(update: Update, context: ContextTypes.DEFAULT_TYPE):
    user_id = update.effective_user.id
    if not waiting_reports_selection.get(user_id):
        return

    period = update.message.text.lower()
    now = datetime.now(pytz.timezone("Asia/Almaty"))
    start_date = None

    if period == "сегодня":
        start_date = datetime(now.year, now.month, now.day, tzinfo=now.tzinfo)
    elif period == "вчера":
        start_date = datetime(now.year, now.month, now.day, tzinfo=now.tzinfo) - timedelta(days=1)
    elif period == "неделя":
        start_date = now - timedelta(days=7)
    elif period == "месяц":
        start_date = now - timedelta(days=30)
    elif period == "год":
        start_date = now - timedelta(days=365)
    elif period == "всё":
        start_date = datetime(1970, 1, 1, tzinfo=now.tzinfo)
    else:
        await update.message.reply_text("❌ Неизвестный период", reply_markup=ReplyKeyboardRemove())
        waiting_reports_selection[user_id] = False
        return

    res = supabase.table("reports").select("*").gte("date", start_date.isoformat()).execute()
    data = res.data

    if not data:
        await update.message.reply_text("📭 Нет отчётов за этот период.", reply_markup=ReplyKeyboardRemove())
    else:
        text_lines = []
        for r in data:
            line = f"{format_datetime_astro(r['date'])} - {r['user_id']} (@{r['username']}) - {r['type']}"
            if r["type"] == "text":
                line += f"\n{r['content']}"
            text_lines.append(line)
        await update.message.reply_text("\n\n".join(text_lines), reply_markup=ReplyKeyboardRemove())

    waiting_reports_selection[user_id] = False

# --- Управление сотрудниками ---
async def add_seller_start(update: Update, context: ContextTypes.DEFAULT_TYPE):
    user_id = update.effective_user.id
    if user_id not in OWNER_IDS:
        await update.message.reply_text("⛔ У вас нет доступа.")
        return
    waiting_for_new_seller_id[user_id] = True
    await update.message.reply_text("✍️ Напишите ID нового продавца:")

async def remove_seller_start(update: Update, context: ContextTypes.DEFAULT_TYPE):
    user_id = update.effective_user.id
    if user_id not in OWNER_IDS:
        await update.message.reply_text("⛔ У вас нет доступа.")
        return
    if not SELLER_IDS:
        await update.message.reply_text("❌ Нет сотрудников для удаления.")
        return

    # Создаём кнопки для каждого продавца
    keyboard = [[f"{uid} (@{(await context.bot.get_chat(uid)).username})" if (await context.bot.get_chat(uid)).username else f"{uid}"] for uid in SELLER_IDS]
    reply_markup = ReplyKeyboardMarkup(keyboard, one_time_keyboard=True, resize_keyboard=True)
    waiting_for_remove_seller[user_id] = True
    await update.message.reply_text("Выберите продавца для удаления:", reply_markup=reply_markup)

async def list_sellers(update: Update, context: ContextTypes.DEFAULT_TYPE):
    user_id = update.effective_user.id
    if user_id not in OWNER_IDS:
        await update.message.reply_text("⛔ У вас нет доступа.")
        return
    if not SELLER_IDS:
        await update.message.reply_text("❌ Нет сотрудников.")
        return
    text_lines = []
    for uid in SELLER_IDS:
        try:
            user = await context.bot.get_chat(uid)
            text_lines.append(f"- {format_user(user)}")
        except:
            text_lines.append(f"- {uid} (не удалось получить данные)")
    await update.message.reply_text("🧑‍💼 Список сотрудников:\n" + "\n".join(text_lines))

# --- Обработка всех сообщений ---
async def handle_all_messages(update: Update, context):
    user = update.effective_user
    user_id = user.id
    message = update.message

    # --- Добавление нового продавца ---
    if waiting_for_new_seller_id.get(user_id):
        text = message.text
        if not text.isdigit():
            await update.message.reply_text("❌ ID должен быть числом. Попробуйте ещё раз.")
            return
        new_id = int(text)
        if new_id in SELLER_IDS:
            await update.message.reply_text(f"⚠ Пользователь {new_id} уже сотрудник.")
        else:
            SELLER_IDS.append(new_id)
            await update.message.reply_text(f"✅ Пользователь {new_id} добавлен как сотрудник.")
        waiting_for_new_seller_id[user_id] = False
        return

    # --- Удаление продавца ---
    if waiting_for_remove_seller.get(user_id):
        uid_str = message.text.split(" ")[0]
        if not uid_str.isdigit():
            await update.message.reply_text("❌ Ошибка, выберите продавца из кнопок.", reply_markup=ReplyKeyboardRemove())
            return
        uid = int(uid_str)
        if uid in SELLER_IDS:
            SELLER_IDS.remove(uid)
            await update.message.reply_text(f"✅ Пользователь {uid} удалён из сотрудников.", reply_markup=ReplyKeyboardRemove())
        else:
            await update.message.reply_text("⚠ Пользователь не найден.", reply_markup=ReplyKeyboardRemove())
        waiting_for_remove_seller[user_id] = False
        return

    # --- ZOV ---
    if waiting_for_message.get(user_id):
        if message.text:
            await context.bot.send_message(chat_id=GROUP_ID, text=message.text)
        elif message.photo:
            await context.bot.send_photo(chat_id=GROUP_ID, photo=message.photo[-1].file_id, caption=message.caption or "")
        elif message.document:
            await context.bot.send_document(chat_id=GROUP_ID, document=message.document.file_id, caption=message.caption or "")
        waiting_for_message[user_id] = False
        await message.reply_text("✅ Сообщение отправлено в группу.")
        return

    # --- Выбор периода отчёта ---
    if waiting_reports_selection.get(user_id):
        await handle_reports_selection(update, context)
        return

    # --- Report ---
    if report_sessions.get(user_id):
        session = report_sessions[user_id]

        if session["active"] == True:
            session["messages"].append(message)
            keyboard = [["Да", "Нет"]]
            reply_markup = ReplyKeyboardMarkup(keyboard, one_time_keyboard=True, resize_keyboard=True)
            await message.reply_text("Хотите добавить ещё?", reply_markup=reply_markup)
            session["active"] = "waiting_confirm"
            return

        elif session["active"] == "waiting_confirm":
            if message.text and message.text.lower() == "да":
                session["active"] = True
                await message.reply_text("✍️ Напишите или прикрепите ещё сообщение.", reply_markup=ReplyKeyboardRemove())
                return
            elif message.text and message.text.lower() == "нет":
                for msg in session["messages"]:
                    data = {
                        "user_id": user.id,
                        "username": user.username or "",
                        "date": astana_now().isoformat(),
                        "type": "text",
                        "content": msg.text or "",
                        "file_id": None
                    }
                    if msg.photo:
                        data["type"] = "photo"
                        data["file_id"] = msg.photo[-1].file_id
                        data["content"] = msg.caption or ""
                    elif msg.document:
                        data["type"] = "document"
                        data["file_id"] = msg.document.file_id
                        data["content"] = msg.caption or ""
                    elif msg.video:
                        data["type"] = "video"
                        data["file_id"] = msg.video.file_id
                        data["content"] = msg.caption or ""

                    supabase.table("reports").insert(data).execute()

                    # Отправляем админу
                    if data["type"] == "text":
                        await context.bot.send_message(
                            chat_id=OWNER_IDS[0],
                            text=f"📩 Отчёт от {format_user(user)}:\n\n{data['content']}"
                        )
                    elif data["type"] == "photo":
                        await context.bot.send_photo(
                            chat_id=OWNER_IDS[0],
                            photo=data["file_id"],
                            caption=data["content"] or f"📩 Отчёт от {format_user(user)}"
                        )
                    elif data["type"] == "document":
                        await context.bot.send_document(
                            chat_id=OWNER_IDS[0],
                            document=data["file_id"],
                            caption=data["content"] or f"📩 Отчёт от {format_user(user)}"
                        )
                    elif data["type"] == "video":
                        await context.bot.send_video(
                            chat_id=OWNER_IDS[0],
                            video=data["file_id"],
                            caption=data["content"] or f"📩 Отчёт от {format_user(user)}"
                        )

                await message.reply_text("✅ Отчёт отправлен администратору.", reply_markup=ReplyKeyboardRemove())
                del report_sessions[user_id]
                return

# --- Запуск бота ---
app = Application.builder().token(BOT_TOKEN).build()

# --- Хэндлеры команд ---
app.add_handler(CommandHandler("start", start))
app.add_handler(CommandHandler("help", help_command))
app.add_handler(CommandHandler("status", status))
app.add_handler(CommandHandler("staff", staff))
app.add_handler(CommandHandler("zov", zov))
app.add_handler(CommandHandler("report", report))
app.add_handler(CommandHandler("reports", reports))
app.add_handler(CommandHandler("add_seller", add_seller_start))
app.add_handler(CommandHandler("remove_seller", remove_seller_start))
app.add_handler(CommandHandler("list_sellers", list_sellers))

# --- Хэндлер всех сообщений ---
app.add_handler(MessageHandler(filters.ALL & ~filters.COMMAND, handle_all_messages))

print("Бот запущен...")
app.run_polling()