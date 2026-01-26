import logging
import asyncio
import uuid
import random
from datetime import datetime, timedelta

from aiogram import Bot, Dispatcher, types
from aiogram.filters import Command, CommandStart
from aiogram.types import InlineKeyboardButton, InlineKeyboardMarkup
from aiogram.fsm.context import FSMContext
from aiogram.fsm.state import State, StatesGroup
from aiogram.fsm.storage.memory import MemoryStorage


TOKEN = "8494851583:AAEToTqoFhlVQL9rNRGfwUqGWU30UcSDHg4"
BOT_USERNAME = "karkarychmeetbot"

logging.basicConfig(level=logging.INFO)

storage = MemoryStorage()
bot = Bot(token=TOKEN)
dp = Dispatcher(storage=storage)


class InviteStates(StatesGroup):
    waiting_for_place = State()
    waiting_for_time = State()
    waiting_for_description = State()


invites = {}


def format_invite(code, invite):
    responses = invite.get("responses", {})
    yes = sum(1 for r in responses.values() if r == "yes")
    maybe = sum(1 for r in responses.values() if r == "maybe")
    no = sum(1 for r in responses.values() if r == "no")

    desc = invite.get("desc", "")
    return (
        f"💌 Приглашение от {invite['from_name']}\n"
        f"📍 Место: {invite['place']}\n"
        f"🕒 Время: {invite['time']}\n"
        f"📝 {desc}\n\n"
        f"📊 Ответы:\n💖 Да: {yes}\n🤔 Подумаю: {maybe}\n🙈 Нет: {no}\n\n"
        f"🔗 Ссылка: https://t.me/{BOT_USERNAME}?start=invite_{code}"
    )


def invite_keyboard(code):
    return InlineKeyboardMarkup(inline_keyboard=[[
        InlineKeyboardButton(text="💖 Да", callback_data=f"yes_{code}"),
        InlineKeyboardButton(text="🤔 Подумаю", callback_data=f"maybe_{code}"),
        InlineKeyboardButton(text="🙈 Нет", callback_data=f"no_{code}")
    ]])


def owner_invite_keyboard(code):
    return InlineKeyboardMarkup(inline_keyboard=[[
        InlineKeyboardButton(text="❌ Отменить", callback_data=f"cancel_{code}"),
    ]])


@dp.message(CommandStart())
async def start(message: types.Message, state: FSMContext):
    args = message.text.split(maxsplit=1)[1] if len(message.text.split()) > 1 else ""

    if args.startswith("invite_"):
        code = args.replace("invite_", "")
        invite = invites.get(code)

        if not invite:
            await message.answer("😔 Это приглашение недоступно.")
            return

        # если владелец открыл ссылку
        if message.from_user.id == invite["from_id"]:
            await message.answer(
                "Это твоё приглашение 👇\n\n" + format_invite(code, invite),
                reply_markup=owner_invite_keyboard(code)
            )
            return

        await message.answer(
            f"💌 {invite['from_name']} приглашает тебя на свидание\n\n"
            f"📍 {invite['place']}\n"
            f"🕒 {invite['time']}\n"
            f"📝 {invite.get('desc','')}\n\n"
            f"Ты согласна?",
            reply_markup=invite_keyboard(code)
        )
        return

    await message.answer(
        "Привет! 💌\n"
        "Напиши /create чтобы создать приглашение\n"
        "Или /myinvites чтобы посмотреть свои приглашения"
    )


@dp.message(Command("create"))
async def create_invite(message: types.Message, state: FSMContext):
    await message.answer("📍 Куда пригласить? Напиши место")
    await state.set_state(InviteStates.waiting_for_place)


@dp.message(InviteStates.waiting_for_place)
async def get_place(message: types.Message, state: FSMContext):
    places = ["Парк", "Кафе", "Кино", "Мадагаскар", "Картинг", "Мастер-класс", "Сюрприз 🎁"]
    place = random.choice(places) if message.text.lower() == "/random" else message.text
    await state.update_data(place=place)
    await message.answer("🕒 Когда?")
    await state.set_state(InviteStates.waiting_for_time)


@dp.message(InviteStates.waiting_for_time)
async def get_time(message: types.Message, state: FSMContext):
    await state.update_data(time=message.text)
    await message.answer("📝 Описание или 'нет'")
    await state.set_state(InviteStates.waiting_for_description)


@dp.message(InviteStates.waiting_for_description)
async def get_desc(message: types.Message, state: FSMContext):
    data = await state.get_data()
    desc = "" if message.text.lower() == "нет" else message.text
    code = str(uuid.uuid4())[:8]

    invites[code] = {
        "from_id": message.from_user.id,
        "from_name": message.from_user.first_name,
        "place": data["place"],
        "time": data["time"],
        "desc": desc,
        "responses": {},
        "created_at": datetime.utcnow()
    }

    await message.answer(
        "💌 Приглашение создано!\n\n"
        f"{format_invite(code, invites[code])}"
    )
    await state.clear()


@dp.message(Command("myinvites"))
async def my_invites(message: types.Message):
    my_list = [(code, inv) for code, inv in invites.items() if inv["from_id"] == message.from_user.id]

    if not my_list:
        await message.answer("У тебя пока нет приглашений. Напиши /create ✅")
        return

    for code, invite in my_list:
        await message.answer(format_invite(code, invite), reply_markup=owner_invite_keyboard(code))


@dp.callback_query(lambda c: c.data.startswith(("yes_", "maybe_", "no_")))
async def answer(callback: types.CallbackQuery):
    action, code = callback.data.split("_", 1)
    invite = invites.get(code)

    if not invite:
        await callback.answer("Недействительно", show_alert=True)
        return

    # нельзя отвечать самому себе
    if callback.from_user.id == invite["from_id"]:
        await callback.answer("Это твоё приглашение 🙂", show_alert=True)
        return

    invite["responses"][callback.from_user.id] = action

    text_action = {"yes": "💖 Да", "maybe": "🤔 Подумаю", "no": "🙈 Нет"}[action]

    await bot.send_message(
        invite["from_id"],
        f"📩 Ответ на приглашение:\n"
        f"👤 {callback.from_user.first_name}\n"
        f"✅ Ответ: {text_action}\n\n"
        f"{format_invite(code, invite)}"
    )

    await callback.answer("Готово ✅")


@dp.callback_query(lambda c: c.data.startswith("cancel_"))
async def cancel_invite(callback: types.CallbackQuery):
    code = callback.data.replace("cancel_", "")
    invite = invites.get(code)

    if not invite:
        await callback.answer("Уже недоступно", show_alert=True)
        return

    if callback.from_user.id != invite["from_id"]:
        await callback.answer("Это не твоё приглашение", show_alert=True)
        return

    del invites[code]
    await callback.message.edit_text("❌ Приглашение отменено.")
    await callback.answer("Отменено ✅")


async def cleanup_old_invites():
    while True:
        now = datetime.utcnow()
        for code in list(invites.keys()):
            invite = invites[code]
            if now - invite["created_at"] > timedelta(days=1):
                del invites[code]
        await asyncio.sleep(3600)


async def main():
    asyncio.create_task(cleanup_old_invites())
    await dp.start_polling(bot)


if __name__ == "__main__":
    asyncio.run(main())
