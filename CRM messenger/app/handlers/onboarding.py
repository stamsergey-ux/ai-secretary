"""Onboarding and /start, /help handlers."""

from aiogram import Router, F
from aiogram.filters import CommandStart, Command
from aiogram.types import Message, InlineKeyboardMarkup, InlineKeyboardButton, CallbackQuery
from sqlalchemy import select

from app.database import async_session, Member
from app.utils import is_chairman

router = Router()

MEMBER_INTRO = """Привет, {name}! Я — AI-секретарь Совета Директоров.

Я веду протоколы совещаний, слежу за задачами и помогаю ничего не забыть. Вот что я умею:

━━━━━━━━━━━━━━━━━━━━━━━━━

ПРОТОКОЛЫ
Все совещания сохраняются у меня. Спроси:
- "Что обсуждали на последнем совещании?"
- "Что решили по бюджету в феврале?"
- "Покажи протокол от 4 марта"

ТВОИ ЗАДАЧИ
Я отслеживаю задачи, которые тебе назначены:
- "Какие у меня задачи?" — список твоих задач
- "Что у меня просрочено?" — то, что требует внимания
- Нажми [Выполнено] под задачей, чтобы закрыть её

ВСЕ ЗАДАЧИ
Ты видишь задачи всей команды:
- "Какие задачи у Алексея?"
- "Кто работает над логистикой?"
- "Что просрочено по всей команде?"

НАПОМИНАНИЯ
Я сам напомню тебе:
- За 2 дня до дедлайна
- В день дедлайна
- Если задача просрочена

СВОБОДНЫЙ ФОРМАТ
Не нужно запоминать команды. Просто пиши мне как человеку — я пойму.

━━━━━━━━━━━━━━━━━━━━━━━━━"""

CHAIRMAN_EXTRA = """
━━━━━━━━━━━━━━━━━━━━━━━━━

УПРАВЛЕНИЕ (только для Председателя)

- Отправь мне файл из Plaud — я разберу протокол
- "Создай задачу для Екатерины: ... до 15 марта"
- "Подготовь адженду" — соберу повестку следующего совещания
- "Экспорт задач" или "Гант" — PDF с диаграммой Ганта
- "Дашборд" — общая картина по задачам

━━━━━━━━━━━━━━━━━━━━━━━━━"""


def _main_keyboard() -> InlineKeyboardMarkup:
    return InlineKeyboardMarkup(inline_keyboard=[
        [
            InlineKeyboardButton(text="Мои задачи", callback_data="my_tasks"),
            InlineKeyboardButton(text="Последний протокол", callback_data="last_protocol"),
        ],
        [
            InlineKeyboardButton(text="Что умеет бот?", callback_data="help"),
        ]
    ])


@router.message(CommandStart())
async def cmd_start(message: Message):
    """Handle /start — register user and show onboarding."""
    user = message.from_user
    chairman = is_chairman(user.username)

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
            )
            session.add(member)
            await session.commit()

    name = user.first_name or user.username or "коллега"
    text = MEMBER_INTRO.format(name=name)
    if chairman:
        text += CHAIRMAN_EXTRA

    await message.answer(text, reply_markup=_main_keyboard())


@router.message(Command("help"))
async def cmd_help(message: Message):
    user = message.from_user
    name = user.first_name or user.username or "коллега"
    text = MEMBER_INTRO.format(name=name)
    if is_chairman(user.username):
        text += CHAIRMAN_EXTRA
    await message.answer(text, reply_markup=_main_keyboard())


@router.callback_query(F.data == "help")
async def cb_help(callback: CallbackQuery):
    user = callback.from_user
    name = user.first_name or user.username or "коллега"
    text = MEMBER_INTRO.format(name=name)
    if is_chairman(user.username):
        text += CHAIRMAN_EXTRA
    await callback.message.answer(text, reply_markup=_main_keyboard())
    await callback.answer()
