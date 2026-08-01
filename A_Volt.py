"""
Telegram-бот для публикации постов в канал 𝙑𝙤𝙡𝙩 𝙃𝙪𝙗⚡︎

Бот пошагово запрашивает у администратора:
  1. Название игры
  2. Функции (список, каждая с новой строки)
  3. Ключ (State)
  4. Loadstring (скрипт, который будет копироваться по кнопке)
  5. Фото для поста

После этого показывает предпросмотр и по кнопке "Опубликовать"
отправляет готовый пост (фото с подписью) в канал. Loadstring нигде
не отображается в тексте — он "спрятан" за инлайн-кнопкой
"Скопировать loadstring", которая копирует его в буфер обмена
пользователя (нативная функция Telegram Bot API — copy_text у
инлайн-кнопки).

Установка зависимостей:
    pip install -r requirements.txt

Запуск:
    python bot.py

Токен, id канала и id админов уже прописаны ниже. При желании их
можно переопределить переменными окружения BOT_TOKEN / CHANNEL_ID /
ADMIN_IDS, не трогая код.
"""

import logging
import os

from telegram import (
    Update,
    InlineKeyboardButton,
    InlineKeyboardMarkup,
    CopyTextButton,
)
from telegram.constants import ParseMode
from telegram.ext import (
    Application,
    CommandHandler,
    MessageHandler,
    CallbackQueryHandler,
    ConversationHandler,
    ContextTypes,
    filters,
)

# ---------------------------------------------------------------------------
# Настройки. Значения по умолчанию — ваши; при необходимости их можно
# переопределить переменными окружения BOT_TOKEN / CHANNEL_ID / ADMIN_IDS,
# не редактируя код (например, если этот файл когда-нибудь попадёт в
# публичный репозиторий — тогда токен из кода стоит убрать и заменить).
# ---------------------------------------------------------------------------

BOT_TOKEN = os.environ.get("BOT_TOKEN", "8869115380:AAGkhtzy32ItvcSTL2E2R9J8sWg85tMxcAg")

# Числовой chat_id канала. Для супергрупп/каналов Telegram он всегда
# отрицательный и с префиксом -100, поэтому верный вариант — -1003390585756.
CHANNEL_ID = os.environ.get("CHANNEL_ID", "-1003390585756")

# ID администраторов, которым разрешено пользоваться ботом (через запятую)
ADMIN_IDS = {
    int(x) for x in os.environ.get("ADMIN_IDS", "7891780046,5051719818,1154566620").split(",") if x.strip().isdigit()
}

logging.basicConfig(
    format="%(asctime)s - %(name)s - %(levelname)s - %(message)s",
    level=logging.INFO,
)
logger = logging.getLogger(__name__)

# Состояния диалога
GAME, FUNCTIONS, KEY, LOADSTRING, PHOTO, PREVIEW = range(6)


# ---------------------------------------------------------------------------
# "Грим" для текста: латинские буквы и цифры превращаются в стилизованный
# unicode-шрифт (тот же стиль, что и в названии канала 𝙑𝙤𝙡𝙩 𝙃𝙪𝙗),
# кириллица и все прочие символы остаются как есть, эмодзи не добавляются.
# ---------------------------------------------------------------------------

def stylize(text: str) -> str:
    result = []
    for ch in text:
        if "A" <= ch <= "Z":
            result.append(chr(0x1D63C + (ord(ch) - ord("A"))))
        elif "a" <= ch <= "z":
            result.append(chr(0x1D656 + (ord(ch) - ord("a"))))
        elif "0" <= ch <= "9":
            result.append(chr(0x1D7EC + (ord(ch) - ord("0"))))
        else:
            result.append(ch)
    return "".join(result)


def build_post_text(game: str, functions: list[str], key: str) -> str:
    functions_block = "\n".join(f"• {stylize(f)}" for f in functions)
    return (
        f"<b>Игра:</b> {stylize(game)}\n\n"
        f"<b>Функции:</b>\n{functions_block}\n\n"
        f"<b>Ключ:</b> {stylize(key)}"
    )


def copy_keyboard(loadstring: str) -> InlineKeyboardMarkup:
    return InlineKeyboardMarkup(
        [[InlineKeyboardButton("Скопировать скрипт", copy_text=CopyTextButton(text=loadstring))]]
    )


# ---------------------------------------------------------------------------
# Проверка доступа
# ---------------------------------------------------------------------------

def is_admin(update: Update) -> bool:
    if not ADMIN_IDS:
        # Если список админов не задан — доступ не ограничен (только для теста).
        return True
    return update.effective_user.id in ADMIN_IDS


# ---------------------------------------------------------------------------
# Хендлеры диалога
# ---------------------------------------------------------------------------

async def start(update: Update, context: ContextTypes.DEFAULT_TYPE) -> None:
    await update.message.reply_text(
        "Привет. Команда /post запускает создание нового поста "
        "\n\nОтменить создание поста в любой момент - /cancel.А еще пошел нахуй"
    )


async def post_start(update: Update, context: ContextTypes.DEFAULT_TYPE) -> int:
    if not is_admin(update):
        await update.message.reply_text("У вас нет доступа к этому боту.")
        return ConversationHandler.END

    context.user_data.clear()
    await update.message.reply_text("Введите название игры:")
    return GAME


async def get_game(update: Update, context: ContextTypes.DEFAULT_TYPE) -> int:
    context.user_data["game"] = update.message.text.strip()
    await update.message.reply_text(
        "Теперь отправьте функции одним сообщением - каждая новая функция с новой строки."
    )
    return FUNCTIONS


async def get_functions(update: Update, context: ContextTypes.DEFAULT_TYPE) -> int:
    lines = [line.strip() for line in update.message.text.splitlines() if line.strip()]
    if not lines:
        await update.message.reply_text("Нужна хотя бы одна функция. Отправьте ещё раз:")
        return FUNCTIONS
    context.user_data["functions"] = lines
    await update.message.reply_text("Введите ключ:")
    return KEY


async def get_key(update: Update, context: ContextTypes.DEFAULT_TYPE) -> int:
    context.user_data["key"] = update.message.text.strip()
    await update.message.reply_text(
        "Введите скрипт - этот скрипт будет копироваться по кнопке "
        ""
    )
    return LOADSTRING


async def get_loadstring(update: Update, context: ContextTypes.DEFAULT_TYPE) -> int:
    context.user_data["loadstring"] = update.message.text.strip()
    await update.message.reply_text("Теперь отправьте скриншот:")
    return PHOTO


async def get_photo(update: Update, context: ContextTypes.DEFAULT_TYPE) -> int:
    if not update.message.photo:
        await update.message.reply_text("Нужно отправить именно фото. Попробуйте ещё раз:")
        return PHOTO

    # Берём вариант с наилучшим качеством (последний в списке).
    context.user_data["photo_file_id"] = update.message.photo[-1].file_id

    text = build_post_text(
        context.user_data["game"],
        context.user_data["functions"],
        context.user_data["key"],
    )

    keyboard = InlineKeyboardMarkup(
        [
            [InlineKeyboardButton(
                "Скопировать скрипт",
                copy_text=CopyTextButton(text=context.user_data["loadstring"]),
            )],
            [
                InlineKeyboardButton("Опубликовать", callback_data="publish"),
                InlineKeyboardButton("Отмена", callback_data="cancel"),
            ],
            [InlineKeyboardButton("Начать заново", callback_data="restart")],
        ]
    )

    await update.message.reply_photo(
        photo=context.user_data["photo_file_id"],
        caption=text,
        parse_mode=ParseMode.HTML,
        reply_markup=keyboard,
    )
    return PREVIEW


async def preview_callback(update: Update, context: ContextTypes.DEFAULT_TYPE) -> int:
    query = update.callback_query
    await query.answer()

    if query.data == "publish":
        text = build_post_text(
            context.user_data["game"],
            context.user_data["functions"],
            context.user_data["key"],
        )
        try:
            await context.bot.send_photo(
                chat_id=CHANNEL_ID,
                photo=context.user_data["photo_file_id"],
                caption=text,
                parse_mode=ParseMode.HTML,
                reply_markup=copy_keyboard(context.user_data["loadstring"]),
            )
        except Exception as exc:  # noqa: BLE001
            logger.exception("Не удалось опубликовать пост")
            await query.message.reply_text(f"Ошибка публикации: {exc}")
            return ConversationHandler.END

        await query.message.reply_text("Пост опубликован в канал.")
        context.user_data.clear()
        return ConversationHandler.END

    if query.data == "cancel":
        await query.message.reply_text("Публикация отменена.")
        context.user_data.clear()
        return ConversationHandler.END

    if query.data == "restart":
        context.user_data.clear()
        await query.message.reply_text("Начинаем заново.\n\nВведите название игры:")
        return GAME

    return PREVIEW


async def cancel(update: Update, context: ContextTypes.DEFAULT_TYPE) -> int:
    context.user_data.clear()
    await update.message.reply_text("Публикация отменена.")
    return ConversationHandler.END


def main() -> None:
    application = Application.builder().token(BOT_TOKEN).build()

    conv_handler = ConversationHandler(
        entry_points=[CommandHandler("post", post_start)],
        states={
            GAME: [MessageHandler(filters.TEXT & ~filters.COMMAND, get_game)],
            FUNCTIONS: [MessageHandler(filters.TEXT & ~filters.COMMAND, get_functions)],
            KEY: [MessageHandler(filters.TEXT & ~filters.COMMAND, get_key)],
            LOADSTRING: [MessageHandler(filters.TEXT & ~filters.COMMAND, get_loadstring)],
            PHOTO: [MessageHandler(filters.PHOTO, get_photo)],
            PREVIEW: [CallbackQueryHandler(preview_callback)],
        },
        fallbacks=[CommandHandler("cancel", cancel)],
    )

    application.add_handler(CommandHandler("start", start))
    application.add_handler(conv_handler)

    application.run_polling()


if __name__ == "__main__":
    main()

