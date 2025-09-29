import os
from telegram import Update
from telegram.ext import ApplicationBuilder, CommandHandler, ContextTypes

# Получаем токен из переменных окружения
BOT_TOKEN = "8458767187:AAHV6sl14LzVt1Bnk49LvoR6QYg7MAvbYhA"

# Команда /start
async def start(update: Update, context: ContextTypes.DEFAULT_TYPE):
    await update.message.reply_text(f"Привет, {update.effective_user.first_name}! Бот работает ✅")

# Создание приложения
app = ApplicationBuilder().token(BOT_TOKEN).build()
app.add_handler(CommandHandler("start", start))

print("Бот запущен...")
# Запуск polling
app.run_polling()