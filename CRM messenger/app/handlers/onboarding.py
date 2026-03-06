"""Onboarding and /start, /help handlers."""

from aiogram import Router, F
from aiogram.filters import CommandStart, Command
from aiogram.types import (
    Message, InlineKeyboardMarkup, InlineKeyboardButton, CallbackQuery,
    ReplyKeyboardMarkup, KeyboardButton,
)
from sqlalchemy import select

from app.database import async_session, Member
from app.utils import is_chairman, is_stakeholder

router = Router()

MEMBER_INTRO = """🤖 <b>AI-секретарь Совета Директоров</b>

Привет, <b>{name}</b>! Я помогаю вести протоколы, отслеживать задачи и готовить совещания.

📋 <b>ПРОТОКОЛЫ</b>
Все совещания сохраняются у меня. Спроси:
· <i>«Что обсуждали на последнем совещании?»</i>
· <i>«Что решили по бюджету в феврале?»</i>

✅ <b>ТВОИ ЗАДАЧИ</b>
Я отслеживаю задачи, назначенные тебе:
· <i>«Какие у меня задачи?»</i>
· <i>«Что у меня просрочено?»</i>
· Нажми <b>[Выполнено]</b> чтобы закрыть задачу

🔔 <b>НАПОМИНАНИЯ</b>
· ⏳ За 2 дня до дедлайна
· ⚡ В день дедлайна
· 🚨 Если задача просрочена

🎙 <b>ГОЛОСОВЫЕ</b>
Отправь голосовое — распознаю речь и выполню команду. Можно диктовать задачи, вопросы, отчёты.

📅 <b>СОВЕЩАНИЯ</b>
· За 48ч — сбор статусов по задачам
· За 24ч — рассылка повестки (адженды)
· <i>«Добавь в адженду: обсудить бюджет»</i>

💬 <b>СВОБОДНЫЙ ЧАТ</b>
Не нужно запоминать команды — просто пиши мне как человеку."""

CHAIRMAN_EXTRA = """

🔑 <b>УПРАВЛЕНИЕ</b>
· Отправь файл из Plaud — разберу протокол
· <i>«Создай задачу для Екатерины: ... до 15 марта»</i>
· <i>«Подготовь адженду»</i> — повестка совещания
· <i>«Гант»</i> — PDF-диаграмма задач
· <i>«Дашборд»</i> — общая картина

📊 <b>АНАЛИТИКА</b>
· <i>«Аналитика»</i> — статистика задач
· Выполнение по участникам
· Просрочки и динамика

📅 <b>ПЛАНИРОВАНИЕ</b>
· <i>«Назначь совещание 15.03.2026 Итоги Q1»</i>
· Авто-сбор статусов за 48ч
· Авто-рассылка адженды за 24ч
· Все участники получат повестку"""

STAKEHOLDER_INTRO = """💎 <b>АКЦИОНЕР</b>

Привет, <b>{name}</b>! Я ваш AI-секретарь Совета Директоров.

📋 <b>ПРОТОКОЛЫ И ЗАДАЧИ</b>
· Все протоколы совещаний
· Статус по всем задачам
· Спрашивай в свободной форме

💎 <b>ПОСТАНОВКА ЗАДАЧ</b>
Нажми <b>[💎 Поставить задачу]</b> и продиктуй или напиши: что нужно сделать, кто ответственный, срок. Секретарь покажет карточку для подтверждения.

💎 <b>МОИ ПОРУЧЕНИЯ</b>
Нажми <b>[💎 Мои поручения]</b> — увидишь все поставленные тобой задачи и их текущий статус."""



def _main_keyboard(is_admin: bool = False) -> InlineKeyboardMarkup:
    buttons = [
        [
            InlineKeyboardButton(text="📋 Мои задачи", callback_data="my_tasks"),
            InlineKeyboardButton(text="📝 Протокол", callback_data="last_protocol"),
        ],
    ]
    if is_admin:
        buttons.append([
            InlineKeyboardButton(text="📊 Дашборд", callback_data="dashboard_cb"),
            InlineKeyboardButton(text="👥 Все задачи", callback_data="all_tasks"),
        ])
    buttons.append([
        InlineKeyboardButton(text="❓ Что умеет бот?", callback_data="help"),
    ])
    return InlineKeyboardMarkup(inline_keyboard=buttons)


def _persistent_keyboard(is_admin: bool = False) -> ReplyKeyboardMarkup:
    """Persistent reply keyboard — always visible at the bottom of the chat."""
    buttons = [
        [KeyboardButton(text="📋 Мои задачи"), KeyboardButton(text="📝 Протокол")],
    ]
    if is_admin:
        buttons.append(
            [KeyboardButton(text="⚙️ Расширенные функции")]
        )
    buttons.append(
        [KeyboardButton(text="🔄 Перезапустить бот"), KeyboardButton(text="❓ Помощь")]
    )
    return ReplyKeyboardMarkup(keyboard=buttons, resize_keyboard=True)




def _stakeholder_keyboard() -> ReplyKeyboardMarkup:
    """Persistent keyboard for stakeholder/shareholder."""
    buttons = [
        [KeyboardButton(text="💎 Поставить задачу"), KeyboardButton(text="💎 Мои поручения")],
        [KeyboardButton(text="📋 Мои задачи"), KeyboardButton(text="📝 Протокол")],
        [KeyboardButton(text="🔄 Перезапустить бот"), KeyboardButton(text="❓ Помощь")],
    ]
    return ReplyKeyboardMarkup(keyboard=buttons, resize_keyboard=True)
@router.message(CommandStart())
async def cmd_start(message: Message):
    """Handle /start — register user and show onboarding."""
    user = message.from_user
    chairman = is_chairman(user.username)
    stakeholder = is_stakeholder(user.username)

    async with async_session() as session:
        existing = await session.execute(
            select(Member).where(Member.telegram_id == user.id)
        )
        member = existing.scalar_one_or_none()

        if not member:
            member = Member(
                telegram_id=user.id,
                username=user.username,
                first_name=user.first_name,
                last_name=user.last_name,
                is_chairman=chairman,
                is_stakeholder=stakeholder,
            )
            session.add(member)
            await session.commit()
        elif stakeholder and not member.is_stakeholder:
            member.is_stakeholder = True
            await session.commit()

    name = user.first_name or user.username or "коллега"

    if stakeholder:
        text = STAKEHOLDER_INTRO.format(name=name)
        keyboard = _stakeholder_keyboard()
    else:
        text = MEMBER_INTRO.format(name=name)
        if chairman:
            text += CHAIRMAN_EXTRA
        keyboard = _persistent_keyboard(chairman)

    await message.answer(text, parse_mode="HTML", reply_markup=keyboard)


@router.message(Command("help"))
async def cmd_help(message: Message):
    user = message.from_user
    name = user.first_name or user.username or "коллега"
    chairman = is_chairman(user.username)
    text = MEMBER_INTRO.format(name=name)
    if chairman:
        text += CHAIRMAN_EXTRA
    await message.answer(text, parse_mode="HTML", reply_markup=_main_keyboard(chairman))


@router.callback_query(F.data == "help")
async def cb_help(callback: CallbackQuery):
    user = callback.from_user
    name = user.first_name or user.username or "коллега"
    chairman = is_chairman(user.username)
    text = MEMBER_INTRO.format(name=name)
    if chairman:
        text += CHAIRMAN_EXTRA
    await callback.message.answer(text, parse_mode="HTML", reply_markup=_main_keyboard(chairman))
    await callback.answer()
