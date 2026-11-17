import asyncio
import os
import sqlite3
from pathlib import Path
from typing import Optional

from aiogram import Bot, Dispatcher, F
from aiogram.filters import Command
from aiogram.fsm.context import FSMContext
from aiogram.fsm.state import State, StatesGroup
from aiogram.types import InlineKeyboardButton, InlineKeyboardMarkup, Message

BOT_TOKEN = os.getenv("BOT_TOKEN", "")
ADMIN_IDS = {
    int(item.strip())
    for item in os.getenv("ADMIN_IDS", "").split(",")
    if item.strip()
}
DATABASE_PATH = Path("movies.db")


class AddMovieForm(StatesGroup):
    waiting_for_title = State()
    waiting_for_description = State()
    waiting_for_poster_url = State()
    waiting_for_code = State()


def init_db() -> None:
    conn = sqlite3.connect(DATABASE_PATH)
    conn.execute(
        """
        CREATE TABLE IF NOT EXISTS movies (
            id INTEGER PRIMARY KEY AUTOINCREMENT,
            title TEXT NOT NULL,
            description TEXT NOT NULL DEFAULT '',
            poster_url TEXT NOT NULL DEFAULT '',
            code TEXT NOT NULL UNIQUE,
            created_by INTEGER NOT NULL
        )
        """
    )
    conn.commit()
    conn.close()


def is_admin(user_id: int) -> bool:
    return user_id in ADMIN_IDS


def add_movie(title: str, description: str, poster_url: str, code: str, created_by: int) -> bool:
    conn = sqlite3.connect(DATABASE_PATH)
    try:
        conn.execute(
            "INSERT INTO movies (title, description, poster_url, code, created_by) VALUES (?, ?, ?, ?, ?)",
            (title.strip(), description.strip(), poster_url.strip(), code.strip(), created_by),
        )
        conn.commit()
        return True
    except sqlite3.IntegrityError:
        return False
    finally:
        conn.close()


def get_movie_by_code(code: str) -> Optional[dict]:
    conn = sqlite3.connect(DATABASE_PATH)
    conn.row_factory = sqlite3.Row
    row = conn.execute(
        "SELECT title, description, poster_url, code FROM movies WHERE LOWER(code) = LOWER(?) LIMIT 1",
        (code.strip(),),
    ).fetchone()
    conn.close()
    if row is None:
        return None
    return dict(row)


def get_all_movies() -> list[dict]:
    conn = sqlite3.connect(DATABASE_PATH)
    conn.row_factory = sqlite3.Row
    rows = conn.execute(
        "SELECT title, description, poster_url, code FROM movies ORDER BY id DESC"
    ).fetchall()
    conn.close()
    return [dict(row) for row in rows]


async def send_movie_info(message: Message, movie: dict) -> None:
    title = movie["title"]
    description = movie["description"] or "Tavsif mavjud emas."
    poster_url = movie["poster_url"]
    code = movie["code"]

    text = (
        f"🎬 <b>{title}</b>\n\n"
        f"📌 Kod: <code>{code}</code>\n\n"
        f"📝 {description}"
    )

    if poster_url:
        await message.answer_photo(photo=poster_url, caption=text, parse_mode="HTML")
    else:
        await message.answer(text, parse_mode="HTML")


async def start_handler(message: Message) -> None:
    text = (
        "👋 Salom! Kino qidirish botiga xush kelibsiz.\n\n"
        "• /search <kod> — kinoni kod bo‘yicha qidirish\n"
        "• /admin — admin panel\n"
        "• /help — yordam"
    )
    await message.answer(text)


async def help_handler(message: Message) -> None:
    await start_handler(message)


async def admin_panel(message: Message) -> None:
    if not is_admin(message.from_user.id):
        await message.answer("❌ Siz admin emassiz.")
        return

    keyboard = InlineKeyboardMarkup(
        inline_keyboard=[
            [InlineKeyboardButton(text="➕ Kino qo‘shish", callback_data="admin_add_movie")],
            [InlineKeyboardButton(text="📋 Barcha kinolar", callback_data="admin_list_movies")],
        ]
    )
    await message.answer("🛠 Admin panel", reply_markup=keyboard)


async def callback_admin_add_movie(callback_query) -> None:
    if not is_admin(callback_query.from_user.id):
        await callback_query.answer("Siz admin emassiz.", show_alert=True)
        return

    await callback_query.message.answer("🎬 Kino nomini yuboring:")
    await callback_query.message.answer("Masalan: Oppenheimer")
    await callback_query.message.edit_reply_markup(reply_markup=None)
    await callback_query.bot.set_state(
        callback_query.from_user.id,
        callback_query.message.chat.id,
        AddMovieForm.waiting_for_title,
    )
    await callback_query.answer()


async def callback_admin_list_movies(callback_query) -> None:
    if not is_admin(callback_query.from_user.id):
        await callback_query.answer("Siz admin emassiz.", show_alert=True)
        return

    movies = get_all_movies()
    if not movies:
        await callback_query.message.answer("📭 Hozircha kino yo‘q.")
        await callback_query.answer()
        return

    text = "📚 Barcha kinolar:\n\n"
    for movie in movies:
        text += f"• <b>{movie['title']}</b> — <code>{movie['code']}</code>\n"
    await callback_query.message.answer(text, parse_mode="HTML")
    await callback_query.answer()


async def process_title(message: Message, state: FSMContext) -> None:
    title = message.text.strip()
    if not title:
        await message.answer("❌ Noto‘g‘ri nom. Qayta yuboring:")
        return

    await state.update_data(title=title)
    await message.answer("📝 Kinoning qisqacha tasvirini yuboring:")
    await state.set_state(AddMovieForm.waiting_for_description)


async def process_description(message: Message, state: FSMContext) -> None:
    description = message.text.strip() or "Tavsif mavjud emas."
    await state.update_data(description=description)
    await message.answer("🖼 Poster URL yuboring. Agar bo‘lmasa: /skip")
    await state.set_state(AddMovieForm.waiting_for_poster_url)


async def process_poster_url(message: Message, state: FSMContext) -> None:
    poster_url = message.text.strip()
    if poster_url.lower() in ["/skip", "skip", "no", "none", "-"]:
        poster_url = ""
    await state.update_data(poster_url=poster_url)
    await message.answer("🔐 Kinoga kod kiriting:\nMasalan: 12345")
    await state.set_state(AddMovieForm.waiting_for_code)


async def process_code(message: Message, state: FSMContext) -> None:
    code = message.text.strip()
    if not code:
        await message.answer("❌ Kod kiritilmadi. Qayta kiriting:")
        return

    data = await state.get_data()
    saved = add_movie(
        title=data["title"],
        description=data["description"],
        poster_url=data.get("poster_url", ""),
        code=code,
        created_by=message.from_user.id,
    )

    if not saved:
        await message.answer("⚠️ Bu kod allaqachon ishlatilgan. Boshqa kod tanlang:")
        return

    await message.answer(f"✅ Kino muvaffaqiyatli qo‘shildi.\nKod: <code>{code}</code>", parse_mode="HTML")
    await state.clear()


async def search_movie(message: Message) -> None:
    args = message.text.split(maxsplit=1)
    if len(args) < 2:
        await message.answer("🔎 Kodni yozing. Misol: /search 12345")
        return

    code = args[1].strip()
    movie = get_movie_by_code(code)
    if movie is None:
        await message.answer(f"❌ <code>{code}</code> kodi bo‘yicha kino topilmadi.", parse_mode="HTML")
        return

    await send_movie_info(message, movie)


async def main() -> None:
    if not BOT_TOKEN:
        raise RuntimeError("BOT_TOKEN environment variable is required.")

    init_db()
    bot = Bot(token=BOT_TOKEN)
    dp = Dispatcher()

    dp.message.register(start_handler, Command("start"))
    dp.message.register(help_handler, Command("help"))
    dp.message.register(admin_panel, Command("admin"))
    dp.message.register(search_movie, Command("search"))

    dp.callback_query.register(callback_admin_add_movie, F.data == "admin_add_movie")
    dp.callback_query.register(callback_admin_list_movies, F.data == "admin_list_movies")

    dp.message.register(process_title, AddMovieForm.waiting_for_title)
    dp.message.register(process_description, AddMovieForm.waiting_for_description)
    dp.message.register(process_poster_url, AddMovieForm.waiting_for_poster_url)
    dp.message.register(process_code, AddMovieForm.waiting_for_code)

    await dp.start_polling(bot)


if __name__ == "__main__":
    asyncio.run(main())
