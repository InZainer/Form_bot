import logging
import os
from dataclasses import dataclass, asdict

from aiogram import Bot, Dispatcher, F
from aiogram.enums import ParseMode
from aiogram.filters import CommandStart
from aiogram.fsm.context import FSMContext
from aiogram.fsm.state import State, StatesGroup
from aiogram.fsm.storage.memory import MemoryStorage
from aiogram.types import (
    CallbackQuery,
    InlineKeyboardButton,
    InlineKeyboardMarkup,
    Message,
)

# Импорт конфигурации
try:
    from config import BOT_TOKEN as CONFIG_BOT_TOKEN, ADMIN_ID as CONFIG_ADMIN_ID
except ImportError:
    CONFIG_BOT_TOKEN = "YOUR_BOT_TOKEN_HERE"
    CONFIG_ADMIN_ID = 0
    logging.warning("config.py не найден. Используйте переменные окружения или создайте config.py")


logging.basicConfig(
    level=logging.INFO,
    format="%(asctime)s - %(name)s - %(levelname)s - %(message)s",
)
logger = logging.getLogger(__name__)


# =============================
# CONFIG
# =============================
# Приоритет: переменные окружения > config.py

BOT_TOKEN = os.getenv("BOT_TOKEN", CONFIG_BOT_TOKEN)

try:
    ADMIN_ID = int(os.getenv("ADMIN_ID", str(CONFIG_ADMIN_ID)))
except ValueError:
    ADMIN_ID = CONFIG_ADMIN_ID

if BOT_TOKEN == "YOUR_BOT_TOKEN_HERE" or not BOT_TOKEN:
    logger.error(
        "BOT_TOKEN не установлен! "
        "Установите BOT_TOKEN в config.py или через переменную окружения BOT_TOKEN"
    )

if not ADMIN_ID:
    logger.error(
        "ADMIN_ID не установлен! "
        "Установите ADMIN_ID в config.py или через переменную окружения ADMIN_ID"
    )


# =============================
# DATA MODELS & STATES
# =============================


@dataclass
class Questionnaire:
    full_name: str | None = None
    phone: str | None = None
    contact_phone: str | None = None
    city: str | None = None
    address: str | None = None
    passport_photos: list[str] | None = None  # file_ids


class QuestionnaireStates(StatesGroup):
    waiting_full_name = State()
    waiting_phone = State()
    waiting_contact_phone = State()
    waiting_city = State()
    waiting_address = State()
    waiting_passport_photos = State()
    waiting_selfie = State()
    waiting_pickup_info = State()


# =============================
# HELPERS
# =============================


def build_admin_approval_keyboard(user_id: int) -> InlineKeyboardMarkup:
    return InlineKeyboardMarkup(
        inline_keyboard=[
            [
                InlineKeyboardButton(
                    text="✅ Одобрить",
                    callback_data=f"approve:{user_id}",
                ),
                InlineKeyboardButton(
                    text="❌ Отклонить",
                    callback_data=f"reject:{user_id}",
                ),
            ]
        ]
    )


def format_questionnaire_text(user: Message.from_user.__class__, q: Questionnaire) -> str:
    # user: actually aiogram.types.User, but we only need id / username / full_name
    lines = [
        "<b>Новая анкета продавца</b>",
        "",
        f"<b>Telegram ID:</b> <code>{user.id}</code>",
    ]
    if user.username:
        lines.append(f"<b>Username:</b> @{user.username}")
    if user.full_name:
        lines.append(f"<b>Telegram имя:</b> {user.full_name}")

    lines.extend(
        [
            "",
            f"<b>1. ФИО полностью:</b> {q.full_name}",
            f"<b>2. Основной номер телефона:</b> {q.phone}",
            f"<b>3. Доп. контактный телефон:</b> {q.contact_phone}",
            f"<b>4. Город:</b> {q.city}",
            f"<b>5. Адрес фактического проживания:</b> {q.address}",
        ]
    )

    disclaimer = (
        "\n\n<b>Дисклеймер:</b> анкета не собирает PIN-коды, пароли от ЛК, CVV, "
        "полные платёжные реквизиты и другую информацию, дающую доступ к счёту. "
        "Используйте данные только для связи и организации доставки."
    )

    lines.append(disclaimer)
    return "\n".join(lines)


# =============================
# HANDLERS
# =============================


async def cmd_start(message: Message, state: FSMContext) -> None:
    await state.clear()
    text = (
        "Здравствуйте!\n\n"
        "Я бот для заполнения анкеты продавца.\n\n"
        "⚠️ <b>Важно:</b> Никому не отправляйте PIN-коды, пароли от личного кабинета, "
        "CVV-коды и вообще любые данные для входа в банк.\n\n"
        "Давайте начнём с анкеты.\n\n"
        "<b>1.</b> Пришлите, пожалуйста, ваше <b>ФИО полностью</b>."
    )
    await message.answer(text, parse_mode=ParseMode.HTML)
    await state.set_state(QuestionnaireStates.waiting_full_name)


async def process_full_name(message: Message, state: FSMContext) -> None:
    full_name = message.text.strip()
    await state.update_data(questionnaire=asdict(Questionnaire(full_name=full_name)))

    await message.answer(
        "<b>2.</b> Укажите ваш <b>основной номер телефона</b> для связи.",
        parse_mode=ParseMode.HTML,
    )
    await state.set_state(QuestionnaireStates.waiting_phone)


async def process_phone(message: Message, state: FSMContext) -> None:
    phone = message.text.strip()
    data = await state.get_data()
    q_dict = data.get("questionnaire", {})
    q_dict["phone"] = phone
    await state.update_data(questionnaire=q_dict)

    await message.answer(
        "<b>3.</b> Укажите <b>дополнительный контактный телефон</b> (если есть). "
        "Если нет — напишите «нет».",
        parse_mode=ParseMode.HTML,
    )
    await state.set_state(QuestionnaireStates.waiting_contact_phone)


async def process_contact_phone(message: Message, state: FSMContext) -> None:
    contact_phone = message.text.strip()
    if contact_phone.lower() in {"нет", "no", "-"}:
        contact_phone = "нет"

    data = await state.get_data()
    q_dict = data.get("questionnaire", {})
    q_dict["contact_phone"] = contact_phone
    await state.update_data(questionnaire=q_dict)

    await message.answer(
        "<b>4.</b> Укажите ваш <b>город</b> фактического проживания.",
        parse_mode=ParseMode.HTML,
    )
    await state.set_state(QuestionnaireStates.waiting_city)


async def process_city(message: Message, state: FSMContext) -> None:
    city = message.text.strip()
    data = await state.get_data()
    q_dict = data.get("questionnaire", {})
    q_dict["city"] = city
    await state.update_data(questionnaire=q_dict)

    await message.answer(
        "<b>5.</b> Укажите <b>полный адрес фактического проживания</b> "
        "(улица, дом, подъезд, этаж, квартира).",
        parse_mode=ParseMode.HTML,
    )
    await state.set_state(QuestionnaireStates.waiting_address)


async def process_address(message: Message, state: FSMContext) -> None:
    address = message.text.strip()
    data = await state.get_data()
    q_dict = data.get("questionnaire", {})
    q_dict["address"] = address
    await state.update_data(questionnaire=q_dict)

    await message.answer(
        "<b>6.</b> Пришлите <b>фото паспорта</b> (страница с фото и пропиской) "
        "в хорошем качестве. Можно несколькими фото.",
        parse_mode=ParseMode.HTML,
    )
    await state.set_state(QuestionnaireStates.waiting_passport_photos)


async def process_passport_photos(message: Message, state: FSMContext) -> None:
    if not message.photo:
        await message.answer(
            "Пожалуйста, отправьте именно <b>фото</b> паспорта.",
            parse_mode=ParseMode.HTML,
        )
        return

    data = await state.get_data()
    q_dict = data.get("questionnaire", {})

    photos: list[str] = q_dict.get("passport_photos") or []
    file_id = message.photo[-1].file_id  # best quality
    photos.append(file_id)
    q_dict["passport_photos"] = photos
    await state.update_data(questionnaire=q_dict)

    await message.answer(
        "Фото паспорта сохранено.\n\n"
        "Если нужно, отправьте ещё фото. Когда закончите, напишите «готово».",
        parse_mode=ParseMode.HTML,
    )


async def finish_passport_photos(message: Message, state: FSMContext) -> None:
    data = await state.get_data()
    q_dict = data.get("questionnaire", {})
    photos = q_dict.get("passport_photos") or []

    if not photos:
        await message.answer(
            "У вас пока нет сохранённых фото паспорта. "
            "Пожалуйста, отправьте хотя бы одно фото.",
            parse_mode=ParseMode.HTML,
        )
        return

    # Отправляем анкету админу
    if ADMIN_ID:
        q = Questionnaire(**q_dict)
        text = format_questionnaire_text(message.from_user, q)
        try:
            await message.bot.send_message(
                chat_id=ADMIN_ID,
                text=text,
                parse_mode=ParseMode.HTML,
                reply_markup=build_admin_approval_keyboard(message.from_user.id),
            )
            # Отправляем фото отдельными сообщениями
            for file_id in photos:
                await message.bot.send_photo(
                    chat_id=ADMIN_ID,
                    photo=file_id,
                    caption=f"Паспорт, пользователь {message.from_user.id}",
                )
        except Exception as e:
            logger.exception("Failed to send questionnaire to admin: %s", e)

    await message.answer(
        "Спасибо! Анкета отправлена на проверку.\n\n"
        "<b>Анкета на проверке, ожидайте.</b>",
        parse_mode=ParseMode.HTML,
    )

    await state.set_state(QuestionnaireStates.waiting_selfie)

    await message.answer(
        "Теперь пришлите, пожалуйста, "
        "<b>селфи или видеосообщение</b> с материалом и паспортом "
        "в хорошем качестве.",
        parse_mode=ParseMode.HTML,
    )


async def process_selfie(message: Message, state: FSMContext) -> None:
    if not (message.photo or message.video or message.video_note):
        await message.answer(
            "Пожалуйста, отправьте фото или видео.",
            parse_mode=ParseMode.HTML,
        )
        return

    # Можно при желании переслать админу сразу
    if ADMIN_ID:
        try:
            if message.photo:
                await message.bot.send_photo(
                    chat_id=ADMIN_ID,
                    photo=message.photo[-1].file_id,
                    caption=f"Селфи/материал от пользователя {message.from_user.id}",
                )
            elif message.video:
                await message.bot.send_video(
                    chat_id=ADMIN_ID,
                    video=message.video.file_id,
                    caption=f"Видео от пользователя {message.from_user.id}",
                )
            elif message.video_note:
                await message.bot.send_video_note(
                    chat_id=ADMIN_ID,
                    video_note=message.video_note.file_id,
                )
        except Exception as e:
            logger.exception("Failed to forward selfie/video to admin: %s", e)

    await message.answer(
        "Спасибо! Материалы получены.\n\n"
        "<b>Анкета на проверке, пожалуйста, ожидайте решения администратора.</b>",
        parse_mode=ParseMode.HTML,
    )


# ===== ADMIN CALLBACKS =====


async def admin_approve_callback(callback: CallbackQuery, state: FSMContext, bot: Bot) -> None:
    if callback.from_user.id != ADMIN_ID:
        await callback.answer("Недостаточно прав.", show_alert=True)
        return

    _, user_id_str = callback.data.split(":", maxsplit=1)
    user_id = int(user_id_str)

    await callback.answer("Анкета одобрена.")

    # Сообщение продавцу
    await bot.send_message(
        chat_id=user_id,
        text=(
            "Ваша анкета <b>одобрена</b> ✅\n\n"
            "Укажите, пожалуйста, <b>адрес</b>, откуда удобнее всего отправить материал, "
            "и <b>в какое время</b> это будет удобно сделать."
        ),
        parse_mode=ParseMode.HTML,
    )

    # Установим состояние этому пользователю
    # В этом простом примере мы используем MemoryStorage, поэтому создадим отдельный FSMContext
    user_state = FSMContext(
        storage=callback.message.bot.dispatcher.storage,  # type: ignore[attr-defined]
        key=(
            callback.message.chat.id,
            user_id,
        ),
    )
    await user_state.set_state(QuestionnaireStates.waiting_pickup_info)


async def admin_reject_callback(callback: CallbackQuery, bot: Bot) -> None:
    if callback.from_user.id != ADMIN_ID:
        await callback.answer("Недостаточно прав.", show_alert=True)
        return

    _, user_id_str = callback.data.split(":", maxsplit=1)
    user_id = int(user_id_str)

    await callback.answer("Анкета отклонена.")

    await bot.send_message(
        chat_id=user_id,
        text="К сожалению, ваша анкета отклонена. "
        "Для уточнений свяжитесь с администратором.",
    )


async def process_pickup_info(message: Message, state: FSMContext) -> None:
    pickup_info = message.text.strip()

    # Отправляем админу
    if ADMIN_ID:
        try:
            await message.bot.send_message(
                chat_id=ADMIN_ID,
                text=(
                    "<b>Адрес и время отправки материала от продавца</b>\n\n"
                    f"<b>Пользователь:</b> <code>{message.from_user.id}</code>\n"
                    f"<b>Информация:</b> {pickup_info}"
                ),
                parse_mode=ParseMode.HTML,
            )
        except Exception as e:
            logger.exception("Failed to send pickup info to admin: %s", e)

    await message.answer(
        "Спасибо! Информация передана администратору. "
        "Ожидайте дальнейшие инструкции.\n\n"
        "💸 Оплата происходит строго после проверки карты и личного кабинета.",
        parse_mode=ParseMode.HTML,
    )

    await state.clear()


# =============================
# APP SETUP
# =============================


def setup_handlers(dp: Dispatcher) -> None:
    dp.message.register(cmd_start, CommandStart())

    dp.message.register(process_full_name, QuestionnaireStates.waiting_full_name)
    dp.message.register(process_phone, QuestionnaireStates.waiting_phone)
    dp.message.register(
        process_contact_phone,
        QuestionnaireStates.waiting_contact_phone,
    )
    dp.message.register(process_city, QuestionnaireStates.waiting_city)
    dp.message.register(process_address, QuestionnaireStates.waiting_address)

    dp.message.register(
        process_passport_photos,
        QuestionnaireStates.waiting_passport_photos,
        F.photo,
    )
    dp.message.register(
        finish_passport_photos,
        QuestionnaireStates.waiting_passport_photos,
        F.text.casefold() == "готово",
    )

    dp.message.register(
        process_selfie,
        QuestionnaireStates.waiting_selfie,
    )

    dp.callback_query.register(
        admin_approve_callback,
        F.data.startswith("approve:"),
    )
    dp.callback_query.register(
        admin_reject_callback,
        F.data.startswith("reject:"),
    )

    dp.message.register(
        process_pickup_info,
        QuestionnaireStates.waiting_pickup_info,
    )


async def main() -> None:
    bot = Bot(BOT_TOKEN, parse_mode=ParseMode.HTML)
    storage = MemoryStorage()
    dp = Dispatcher(storage=storage)

    # Save dispatcher on bot object for later access (hack for admin callbacks)
    bot.dispatcher = dp  # type: ignore[attr-defined]

    setup_handlers(dp)

    logger.info("Bot started")
    await dp.start_polling(bot)


if __name__ == "__main__":
    import asyncio

    asyncio.run(main())

