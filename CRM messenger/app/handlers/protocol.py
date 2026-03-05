"""Protocol upload and AI analysis handlers."""
from __future__ import annotations

import json
import io
from datetime import datetime

from aiogram import Router, F, Bot
from aiogram.types import Message, CallbackQuery, InlineKeyboardMarkup, InlineKeyboardButton
from sqlalchemy import select

from app.database import async_session, Meeting, Task, Member
from app.ai_service import analyze_transcript
from app.rag import store_meeting_chunks
from app.utils import is_chairman

router = Router()

# Temporary storage for pending reviews: {chairman_telegram_id: {meeting_data}}
_pending_reviews: dict[int, dict] = {}


async def _get_members_list() -> str:
    """Get comma-separated list of known member names."""
    async with async_session() as session:
        result = await session.execute(select(Member))
        members = result.scalars().all()
    if not members:
        return "No members registered yet"
    names = []
    for m in members:
        parts = [m.display_name, m.first_name, m.username]
        name = next((p for p in parts if p), f"ID:{m.telegram_id}")
        names.append(name)
    return ", ".join(names)


async def _extract_text_from_file(message: Message, bot: Bot) -> str | None:
    """Extract text from uploaded file (txt or pdf)."""
    doc = message.document
    if not doc:
        return None

    file = await bot.download(doc)
    content = file.read()

    if doc.file_name and doc.file_name.endswith(".pdf"):
        try:
            from PyPDF2 import PdfReader
            reader = PdfReader(io.BytesIO(content))
            text = ""
            for page in reader.pages:
                text += page.extract_text() or ""
            return text
        except Exception as e:
            return None
    else:
        try:
            return content.decode("utf-8")
        except UnicodeDecodeError:
            return content.decode("latin-1", errors="ignore")


def _review_keyboard() -> InlineKeyboardMarkup:
    return InlineKeyboardMarkup(inline_keyboard=[
        [
            InlineKeyboardButton(text="Подтвердить", callback_data="confirm_protocol"),
            InlineKeyboardButton(text="Отклонить", callback_data="reject_protocol"),
        ]
    ])


@router.message(F.document)
async def handle_document(message: Message, bot: Bot):
    """Handle uploaded document (transcript from Plaud)."""
    if not is_chairman(message.from_user.username):
        await message.answer("Загрузка протоколов доступна только Председателю.")
        return

    await message.answer("Получил файл, обрабатываю...")

    text = await _extract_text_from_file(message, bot)
    if not text or len(text.strip()) < 50:
        await message.answer("Не удалось извлечь текст из файла. Попробуй отправить как текстовое сообщение.")
        return

    await _process_transcript(message, text)


@router.message(F.text & F.text.len() > 500)
async def handle_long_text(message: Message):
    """Handle long text messages as potential transcripts (only from chairman)."""
    if not is_chairman(message.from_user.username):
        return  # Will fall through to AI chat handler
    # Only treat as transcript if it looks like a meeting transcript
    text_lower = message.text.lower()
    transcript_markers = ["совещание", "встреча", "протокол", "участники", "тема:", "следующие шаги"]
    if any(marker in text_lower for marker in transcript_markers):
        await message.answer("Похоже на протокол совещания. Обрабатываю...")
        await _process_transcript(message, message.text)
    # If not a transcript, let it fall through to AI chat


async def _process_transcript(message: Message, transcript: str):
    """Process transcript through AI and present for review."""
    members_list = await _get_members_list()

    await message.answer("Анализирую транскрипт через AI... Это может занять до минуты.")

    analysis = await analyze_transcript(transcript, members_list)

    if "error" in analysis:
        await message.answer(f"Ошибка анализа: {analysis['error']}\n\nПопробуй ещё раз.")
        return

    # Store for review
    _pending_reviews[message.from_user.id] = {
        "transcript": transcript,
        "analysis": analysis,
    }

    # Format review message
    tasks = analysis.get("tasks", [])
    decisions = analysis.get("decisions", [])
    open_q = analysis.get("open_questions", [])
    agenda = analysis.get("agenda_next", [])

    title = analysis.get("title", "Без названия")
    date = analysis.get("date", "дата не определена")
    summary = analysis.get("summary", "")

    review_text = f"ПРОТОКОЛ: {title}\nДата: {date}\n\n"
    review_text += f"КРАТКОЕ СОДЕРЖАНИЕ:\n{summary}\n\n"

    if tasks:
        review_text += f"ЗАДАЧИ ({len(tasks)}):\n"
        for i, t in enumerate(tasks, 1):
            assignee = t.get("assignee_name", "?")
            deadline = t.get("deadline", "без срока")
            priority = t.get("priority", "medium")
            p_icon = {"high": "!!!", "medium": "", "low": ""}.get(priority, "")
            review_text += f"  {i}. {p_icon} {t['title']}\n     -> {assignee}, до {deadline}\n"
        review_text += "\n"

    if decisions:
        review_text += f"РЕШЕНИЯ ({len(decisions)}):\n"
        for d in decisions:
            review_text += f"  - {d['text']}\n"
        review_text += "\n"

    if open_q:
        review_text += f"ОТКРЫТЫЕ ВОПРОСЫ ({len(open_q)}):\n"
        for q in open_q:
            review_text += f"  - {q['text']}\n"
        review_text += "\n"

    if agenda:
        review_text += f"НА СЛЕДУЮЩЕЕ СОВЕЩАНИЕ ({len(agenda)}):\n"
        for a in agenda:
            presenter = a.get("presenter", "?")
            mins = a.get("estimated_minutes", "?")
            review_text += f"  - [{mins} мин] {presenter}: {a['topic']}\n"

    # Telegram message limit is 4096 chars
    if len(review_text) > 4000:
        chunks = [review_text[i:i+4000] for i in range(0, len(review_text), 4000)]
        for chunk in chunks[:-1]:
            await message.answer(chunk)
        await message.answer(chunks[-1], reply_markup=_review_keyboard())
    else:
        await message.answer(review_text, reply_markup=_review_keyboard())


@router.callback_query(F.data == "confirm_protocol")
async def confirm_protocol(callback: CallbackQuery):
    """Chairman confirms the analyzed protocol."""
    user_id = callback.from_user.id
    review = _pending_reviews.pop(user_id, None)

    if not review:
        await callback.answer("Нет протокола для подтверждения.")
        return

    analysis = review["analysis"]
    transcript = review["transcript"]

    async with async_session() as session:
        # Save meeting
        meeting_date_str = analysis.get("date")
        meeting_date = datetime.now()
        if meeting_date_str:
            try:
                meeting_date = datetime.fromisoformat(meeting_date_str)
            except ValueError:
                pass

        meeting = Meeting(
            date=meeting_date,
            title=analysis.get("title", ""),
            raw_transcript=transcript,
            summary=analysis.get("summary", ""),
            participants=", ".join(analysis.get("participants", [])),
            decisions=json.dumps(analysis.get("decisions", []), ensure_ascii=False),
            open_questions=json.dumps(analysis.get("open_questions", []), ensure_ascii=False),
            agenda_items_next=json.dumps(analysis.get("agenda_next", []), ensure_ascii=False),
            is_confirmed=True,
        )
        session.add(meeting)
        await session.flush()

        # Save tasks
        tasks_created = 0
        for t in analysis.get("tasks", []):
            assignee = None
            assignee_name = t.get("assignee_name")
            if assignee_name:
                result = await session.execute(
                    select(Member).where(
                        (Member.first_name == assignee_name) |
                        (Member.display_name == assignee_name) |
                        (Member.username == assignee_name)
                    )
                )
                assignee = result.scalar_one_or_none()

            deadline = None
            if t.get("deadline"):
                try:
                    deadline = datetime.fromisoformat(t["deadline"])
                except ValueError:
                    pass

            task = Task(
                meeting_id=meeting.id,
                assignee_id=assignee.id if assignee else None,
                title=t["title"],
                description=t.get("title", ""),
                context_quote=t.get("context_quote"),
                priority=t.get("priority", "medium"),
                status="new",
                deadline=deadline,
            )
            session.add(task)
            tasks_created += 1

        await session.commit()

        # Store chunks for RAG
        full_text = f"Совещание: {analysis.get('title', '')}\nДата: {analysis.get('date', '')}\n\n{transcript}"
        if analysis.get("summary"):
            full_text += f"\n\nКраткое содержание:\n{analysis['summary']}"
        await store_meeting_chunks(meeting.id, full_text)

    await callback.message.answer(
        f"Протокол сохранён. Создано задач: {tasks_created}.\n\n"
        f"Уведомления отправлены участникам."
    )
    await callback.answer("Подтверждено!")

    # Notify assignees
    await _notify_assignees(callback.bot, meeting.id)


@router.callback_query(F.data == "reject_protocol")
async def reject_protocol(callback: CallbackQuery):
    """Chairman rejects the analyzed protocol."""
    _pending_reviews.pop(callback.from_user.id, None)
    await callback.message.answer("Протокол отклонён. Можешь отправить файл заново.")
    await callback.answer("Отклонено")


async def _notify_assignees(bot: Bot, meeting_id: int):
    """Send personal task notifications to each assignee."""
    async with async_session() as session:
        meeting = await session.get(Meeting, meeting_id)
        result = await session.execute(
            select(Task, Member)
            .join(Member, Task.assignee_id == Member.id)
            .where(Task.meeting_id == meeting_id)
        )
        rows = result.all()

    # Group tasks by assignee
    by_assignee: dict[int, list] = {}
    for task, member in rows:
        if member.telegram_id not in by_assignee:
            by_assignee[member.telegram_id] = {"name": member.name, "tasks": []}
        by_assignee[member.telegram_id]["tasks"].append(task)

    for tg_id, data in by_assignee.items():
        text = f"Новые задачи с совещания \"{meeting.title}\":\n\n"
        for task in data["tasks"]:
            deadline_str = task.deadline.strftime("%d.%m.%Y") if task.deadline else "без срока"
            p_icon = {"high": "!!!", "medium": "", "low": ""}.get(task.priority, "")
            text += f"{p_icon} #{task.id} {task.title}\n   Срок: {deadline_str}\n\n"

        keyboard = InlineKeyboardMarkup(inline_keyboard=[
            [InlineKeyboardButton(text="Мои задачи", callback_data="my_tasks")]
        ])

        try:
            await bot.send_message(tg_id, text, reply_markup=keyboard)
        except Exception:
            pass  # User hasn't started the bot yet
