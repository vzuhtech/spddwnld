import os
import re
import secrets
import shutil
from dataclasses import dataclass
from typing import Dict, List

from dotenv import load_dotenv
from telegram import InlineKeyboardButton, InlineKeyboardMarkup, Update
from telegram.constants import ChatAction
from telegram.ext import (Application, CallbackQueryHandler, CommandHandler,
                          ContextTypes, MessageHandler, filters)

from .downloader import VideoInfo, download_video, extract_video_info


URL_REGEX = re.compile(r"https?://\S+", re.IGNORECASE)


@dataclass
class RequestContext:
    url: str
    selectors: List[str]  # index -> selector
    labels: Dict[str, str]  # selector -> label


async def start(update: Update, context: ContextTypes.DEFAULT_TYPE) -> None:
    await update.message.reply_text(
        "Отправьте ссылку на видео, и я покажу превью и варианты скачивания.")


def _ensure_store(context: ContextTypes.DEFAULT_TYPE) -> Dict[str, RequestContext]:
    if "requests" not in context.application.bot_data:
        context.application.bot_data["requests"] = {}
    return context.application.bot_data["requests"]


async def _edit_message(query, text: str) -> None:
    msg = query.message
    try:
        if msg.photo:
            await query.edit_message_caption(caption=text)
        else:
            await query.edit_message_text(text=text)
    except Exception:
        # Fallback to sending a new message if editing fails (e.g., message too old)
        await msg.reply_text(text)


async def handle_url(update: Update, context: ContextTypes.DEFAULT_TYPE) -> None:
    text = update.message.text.strip()
    match = URL_REGEX.search(text)
    if not match:
        return
    url = match.group(0)

    await context.bot.send_chat_action(chat_id=update.effective_chat.id, action=ChatAction.TYPING)

    try:
        info: VideoInfo = await extract_video_info(url)
    except Exception as e:
        await update.message.reply_text(f"Ошибка: не удалось получить информацию о видео. {e}")
        return

    # Build buttons
    token = secrets.token_urlsafe(8)
    store = _ensure_store(context)
    selectors = [selector for selector, _ in info.format_rows]
    labels = {selector: label for selector, label in info.format_rows}
    store[token] = RequestContext(url=url, selectors=selectors, labels=labels)

    buttons = []
    for idx, selector in enumerate(selectors):
        label = labels.get(selector, f"Формат {idx}")
        # Keep callback data short: dl|token|<index in base36>
        cb = f"dl|{token}|{idx:x}"
        buttons.append([InlineKeyboardButton(text=label, callback_data=cb)])

    keyboard = InlineKeyboardMarkup(buttons)

    caption = info.title
    if info.thumbnail_url:
        await update.message.reply_photo(photo=info.thumbnail_url, caption=caption, reply_markup=keyboard)
    else:
        await update.message.reply_text(text=caption, reply_markup=keyboard)


async def on_download_click(update: Update, context: ContextTypes.DEFAULT_TYPE) -> None:
    query = update.callback_query
    await query.answer()

    data = query.data or ""
    if not data.startswith("dl|"):
        return
    try:
        _, token, idx_hex = data.split("|", 2)
        idx = int(idx_hex, 16)
    except Exception:
        return

    store = _ensure_store(context)
    req = store.get(token)
    if not req or not (0 <= idx < len(req.selectors)):
        await _edit_message(query, "Сессия устарела. Отправьте ссылку снова.")
        return

    selector = req.selectors[idx]
    label = req.labels.get(selector, "запрошенный формат")

    await _edit_message(query, f"Скачивание {label}…")

    try:
        await context.bot.send_chat_action(chat_id=update.effective_chat.id, action=ChatAction.UPLOAD_VIDEO)
        filepath, filename, ext = await download_video(req.url, selector)
    except Exception as e:
        await _edit_message(query, f"Не удалось скачать {label}: {e}")
        return

    # Telegram bot upload size safety check (approx 50 MB for bots)
    try:
        size_bytes = os.path.getsize(filepath)
    except OSError:
        size_bytes = 0

    max_bot_upload = 49 * 1024 * 1024
    if size_bytes and size_bytes > max_bot_upload:
        await _edit_message(
            query,
            (
                f"Файл {label} слишком большой для загрузки ботом (>{max_bot_upload//1024//1024}MB). "
                "Пожалуйста, выберите более низкое качество."
            ),
        )
        # Cleanup large file without uploading
        try:
            os.remove(filepath)
        except OSError:
            pass
        try:
            shutil.rmtree(os.path.dirname(filepath), ignore_errors=True)
        except Exception:
            pass
        return

    # Upload video/document
    try:
        if ext.lower() in {"mp4", "mov", "m4v"}:
            with open(filepath, "rb") as f:
                await query.message.reply_video(video=f, caption=filename)
        else:
            with open(filepath, "rb") as f:
                await query.message.reply_document(document=f, caption=filename)
    finally:
        # Cleanup temp files
        try:
            os.remove(filepath)
        except OSError:
            pass
        try:
            shutil.rmtree(os.path.dirname(filepath), ignore_errors=True)
        except Exception:
            pass

    await _edit_message(query, f"Готово: {label}")


def main() -> None:
    load_dotenv()
    token = os.getenv("BOT_TOKEN")
    if not token:
        raise RuntimeError("BOT_TOKEN не задан. Укажите его в .env")

    app = Application.builder().token(token).build()

    app.add_handler(CommandHandler("start", start))
    app.add_handler(MessageHandler(filters.TEXT & (~filters.COMMAND) & filters.Regex(URL_REGEX), handle_url))
    app.add_handler(CallbackQueryHandler(on_download_click, pattern=r"^dl\|"))

    print("Bot is running… Press Ctrl+C to stop.")
    app.run_polling(close_loop=False)


if __name__ == "__main__":
    main()