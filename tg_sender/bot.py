import asyncio
import logging
import os
import sys
from enum import StrEnum
from pathlib import Path

from aiogram import Bot, Dispatcher, F, Router
from aiogram.client.default import DefaultBotProperties
from aiogram.enums import ParseMode
from aiogram.filters import Command, CommandStart
from aiogram.fsm.context import FSMContext
from aiogram.fsm.state import State, StatesGroup
from aiogram.types import (
    KeyboardButton,
    Message,
    ReplyKeyboardMarkup,
    ReplyKeyboardRemove,
)
from dotenv import load_dotenv
from telethon import TelegramClient

from tg_sender.file_storage import LocalFileStorage

load_dotenv()
api_id = int(os.environ["API_ID"])
api_hash = os.environ["API_HASH"]
TOKEN = os.environ["TOKEN"]

form_router = Router()


class ButtonTexts(StrEnum):
    NEW_MAILING = "Новая рассылка"
    YES = "Да"
    NO = "Нет"
    SEND = "Отправить"
    CANCEL = "Отмена"


class Form(StatesGroup):
    start = State()
    should_use_same_list = State()
    enter_list_of_users = State()
    enter_message = State()
    ask_confirmation = State()


@form_router.message(CommandStart())
async def command_start(message: Message, state: FSMContext) -> None:
    await message.answer(
        "Привет, я бот для рассылки сообщений.",
        reply_markup=ReplyKeyboardMarkup(
            keyboard=[
                [KeyboardButton(text=ButtonTexts.NEW_MAILING.value)],
            ],
            resize_keyboard=True,
        ),
    )
    await state.set_state(Form.start)


async def ask_for_list(message: Message) -> None:
    await message.answer(
        "Введите список пользователей для рассылки, каждый пользователь с новой строки",
        reply_markup=ReplyKeyboardRemove(),
    )


async def ask_for_message(message: Message) -> None:
    await message.answer(
        "Введите сообщение для рассылки", reply_markup=ReplyKeyboardRemove()
    )


@form_router.message(Form.start)
async def handle_start(message: Message, state: FSMContext) -> None:
    if message.text is None or message.text.casefold() not in [
        ButtonTexts.NEW_MAILING.value.lower(),
    ]:
        await message.answer(
            "Не получилось распознать команду, возврат в начало.",
        )
        await command_start(message, state)
        return
    prev_list: list[str] | None = await state.get_value(key="list_of_users")
    if not prev_list:
        await message.answer(
            "Я не нашел списка из прошлой рассылки. Поэтому придется ввести с нуля",
            reply_markup=ReplyKeyboardRemove(),
        )
        await ask_for_list(message)
        await state.set_state(Form.enter_list_of_users)
        return
    await message.answer(
        f"Список с прошлой рассылки: {'\n'.join(prev_list)}.\nХотите использовать тот же список пользователей?",
        reply_markup=ReplyKeyboardMarkup(
            keyboard=[
                [
                    KeyboardButton(text=ButtonTexts.YES.value),
                    KeyboardButton(text=ButtonTexts.NO.value),
                ],
            ],
            resize_keyboard=True,
        ),
    )
    await state.set_state(Form.should_use_same_list)


@form_router.message(Form.should_use_same_list)
async def handle_should_use_same_list_yes(message: Message, state: FSMContext) -> None:
    allowed_cmds = [ButtonTexts.YES.value.lower(), ButtonTexts.NO.value.lower()]
    if message.text is None or message.text.casefold() not in allowed_cmds:
        await message.answer(
            f"Не получилось распознать ответ, допустимые ответы: {', '.join(allowed_cmds)}.",
        )
        return
    elif message.text.casefold() == ButtonTexts.YES.value.lower():
        await message.answer(
            "Окей, использую тот же лист", reply_markup=ReplyKeyboardRemove()
        )
        await ask_for_message(message)
        await state.set_state(Form.enter_message)
        return
    else:
        await ask_for_list(message)
        await state.set_state(Form.enter_list_of_users)


@form_router.message(Form.enter_list_of_users)
async def handle_enter_list_of_users(message: Message, state: FSMContext) -> None:
    if message.text is None or (list_of_users := message.text.splitlines()) is []:
        await message.answer(
            "Не могу распознать список пользователей. Попробуйте еще раз.",
            reply_markup=ReplyKeyboardRemove(),
        )
        return
    await state.set_data({**(await state.get_data()), "list_of_users": list_of_users})
    await message.answer(
        f"Распознал список пользователей:{list_of_users}",
        reply_markup=ReplyKeyboardRemove(),
    )
    await ask_for_message(message)
    await state.set_state(Form.enter_message)


@form_router.message(Form.enter_message)
async def handle_enter_message(message: Message, state: FSMContext) -> None:
    if message.text is None:
        await message.answer(
            "Не могу распознать сообщение. Попробуйте еще раз.",
            reply_markup=ReplyKeyboardRemove(),
        )
        return
    await state.set_data({**(await state.get_data()), "message": message.text})
    await message.answer(
        f"Распознал сообщение:\n\n{message.text}", reply_markup=ReplyKeyboardRemove()
    )
    await message.answer(
        "Подтвердите отправку сообщения",
        reply_markup=ReplyKeyboardMarkup(
            keyboard=[
                [
                    KeyboardButton(text=ButtonTexts.SEND.value),
                    KeyboardButton(text=ButtonTexts.CANCEL.value),
                ],
            ],
            resize_keyboard=True,
        ),
    )
    await state.set_state(Form.ask_confirmation)


@form_router.message(Form.ask_confirmation)
async def handle_ask_confirmation(message: Message, state: FSMContext) -> None:
    allowed_cmds = [ButtonTexts.SEND.value.lower(), ButtonTexts.CANCEL.value.lower()]
    if message.text is None or message.text.casefold() not in allowed_cmds:
        await message.answer(
            f"Не получилось распознать ответ, допустимые ответы: {', '.join(allowed_cmds)}.",
        )
        return
    if not (source_user := message.from_user):
        await message.answer("Не могу определить ваш user ID, возврат в начало")
        await command_start(message, state)
        return
    elif message.text.casefold() == ButtonTexts.SEND.value.lower():
        await message.answer("Отправляю сообщение", reply_markup=ReplyKeyboardRemove())
        data = await state.get_data()
        list_of_users = data["list_of_users"]
        text = data["message"]
        async with TelegramClient(str(source_user.id), api_id, api_hash) as client:
            for dest_user in list_of_users:
                await message.answer(f"Отправляю сообщение пользователю {dest_user}")
                await client.send_message(dest_user, text)
                await asyncio.sleep(0.05)
        await message.answer("Рассылка завершена", reply_markup=ReplyKeyboardRemove())
        await state.set_state(Form.start)
        return
    else:
        await message.answer("Рассылка отменена", reply_markup=ReplyKeyboardRemove())
        await state.set_state(Form.start)
        return


@form_router.message(Command("cancel"))
@form_router.message(F.text.casefold() == ButtonTexts.CANCEL.value.lower())
async def cancel_handler(message: Message, state: FSMContext) -> None:
    await message.answer("Возврат в начало", reply_markup=ReplyKeyboardRemove())
    await command_start(message, state)


unk_router = Router()


@unk_router.message()
async def unknown_message_handler(message: Message, state: FSMContext) -> None:
    await message.answer("Возврат в начало")
    await command_start(message, state)


async def main():
    bot = Bot(token=TOKEN, default=DefaultBotProperties(parse_mode=ParseMode.HTML))
    dp = Dispatcher(storage=LocalFileStorage(Path("storage.pkl")))
    dp.include_router(form_router)
    dp.include_router(unk_router)
    # Start event dispatching
    await dp.start_polling(bot)


if __name__ == "__main__":
    logging.basicConfig(level=logging.INFO, stream=sys.stdout)
    asyncio.run(main())
