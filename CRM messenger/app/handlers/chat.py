"""AI chat handler — free-form conversation about meetings and tasks."""
from __future__ import annotations

import json
from datetime import datetime

from aiogram import Router, F
from aiogram.types import Message, BufferedInputFile
from sqlalchemy import select

from app.database import async_session, Task, Member, Meeting
from app.ai_service import chat_with_context, generate_agenda
from app.rag import search_relevant_chunks
from app.gantt import generate_gantt_pdf
from app.utils import is_chairman

router = Router()


async def _get_tasks_summary(user_id: int | None = None) -> str:
    """Get a summary of current tasks, optionally filtered by user."""
    async with async_session() as session:
        query = (
            select(Task, Member)
            .outerjoin(Member, Task.assignee_id == Member.id)
            .where(Task.status.in_(["new", "in_progress", "overdue"]))
            .order_by(Task.deadline.asc())
        )
        result = await session.execute(query)
        rows = result.all()

    if not rows:
        return "No open tasks."

    lines = []
    for task, member in rows:
        name = member.name if member else "unassigned"
        deadline = task.deadline.strftime("%d.%m.%Y") if task.deadline else "no deadline"
        lines.append(f"#{task.id} [{task.status}] {task.title} -> {name}, deadline: {deadline}")

    return "\n".join(lines)


async def _get_all_tasks_for_gantt(assignee_filter: str | None = None) -> list[dict]:
    """Get tasks formatted for Gantt chart."""
    async with async_session() as session:
        query = (
            select(Task, Member)
            .outerjoin(Member, Task.assignee_id == Member.id)
            .order_by(Task.deadline.asc())
        )
        result = await session.execute(query)
        rows = result.all()

    tasks = []
    for task, member in rows:
        name = member.name if member else "?"
        if assignee_filter and assignee_filter.lower() not in name.lower():
            continue
        tasks.append({
            "id": task.id,
            "title": task.title,
            "assignee": name,
            "deadline": task.deadline or datetime.now(),
            "created_at": task.created_at or datetime.now(),
            "status": task.status,
        })
    return tasks


async def _build_agenda() -> str:
    """Build agenda using all available context."""
    async with async_session() as session:
        # Recent meetings
        result = await session.execute(
            select(Meeting).where(Meeting.is_confirmed == True)
            .order_by(Meeting.date.desc()).limit(5)
        )
        meetings = result.scalars().all()

        # Open tasks
        result = await session.execute(
            select(Task, Member)
            .outerjoin(Member, Task.assignee_id == Member.id)
            .where(Task.status.in_(["new", "in_progress"]))
            .order_by(Task.deadline.asc())
        )
        open_rows = result.all()

        # Overdue tasks
        result = await session.execute(
            select(Task, Member)
            .outerjoin(Member, Task.assignee_id == Member.id)
            .where(Task.status == "overdue")
        )
        overdue_rows = result.all()

    meetings_ctx = ""
    agenda_items = ""
    for m in meetings:
        meetings_ctx += f"\n[{m.date.strftime('%d.%m.%Y')}] {m.title}\n{m.summary[:500]}\n"
        if m.agenda_items_next:
            try:
                items = json.loads(m.agenda_items_next)
                for item in items:
                    agenda_items += f"- {item.get('topic', '?')} (presenter: {item.get('presenter', '?')})\n"
            except json.JSONDecodeError:
                pass

    open_tasks_text = "\n".join(
        f"#{t.id} {t.title} -> {m.name if m else '?'}, deadline: {t.deadline}" for t, m in open_rows
    ) or "None"

    overdue_text = "\n".join(
        f"#{t.id} {t.title} -> {m.name if m else '?'}, deadline: {t.deadline}" for t, m in overdue_rows
    ) or "None"

    return await generate_agenda(meetings_ctx, open_tasks_text, overdue_text, agenda_items or "None")


@router.message(F.text)
async def handle_text_message(message: Message):
    """Handle all text messages as AI chat (catch-all handler, must be registered last)."""
    text = message.text.strip().lower()

    # Quick command detection
    if text in ("мои задачи", "мои задачи?", "какие у меня задачи", "какие у меня задачи?"):
        return await _show_my_tasks(message)

    if text in ("гант", "ганта", "гант-таблица", "экспорт задач", "диаграмма ганта"):
        return await _send_gantt(message)

    if text in ("адженда", "повестка", "подготовь адженду", "подготовь повестку"):
        return await _send_agenda(message)

    if text in ("дашборд", "dashboard", "статус"):
        return await _send_dashboard(message)

    # For everything else — AI chat with RAG
    await _ai_chat(message)


async def _show_my_tasks(message: Message):
    user_id = message.from_user.id

    async with async_session() as session:
        member = (await session.execute(
            select(Member).where(Member.telegram_id == user_id)
        )).scalar_one_or_none()

        if not member:
            await message.answer("Ты ещё не зарегистрирован. Нажми /start")
            return

        result = await session.execute(
            select(Task).where(
                Task.assignee_id == member.id,
                Task.status.in_(["new", "in_progress", "overdue"])
            ).order_by(Task.deadline.asc())
        )
        tasks = result.scalars().all()

    if not tasks:
        await message.answer("У тебя нет открытых задач!")
        return

    text = f"Твои открытые задачи ({len(tasks)}):\n\n"
    for t in tasks:
        status_icon = {"new": "⬜", "in_progress": "🔵", "overdue": "🔴"}.get(t.status, "⬜")
        deadline = t.deadline.strftime("%d.%m.%Y") if t.deadline else "без срока"
        text += f"{status_icon} #{t.id} {t.title}\n   Срок: {deadline}\n\n"

    await message.answer(text)


async def _send_gantt(message: Message, assignee_filter: str | None = None):
    if not is_chairman(message.from_user.username):
        await message.answer("Экспорт диаграммы Ганта доступен Председателю.")
        return

    await message.answer("Генерирую диаграмму Ганта...")
    tasks = await _get_all_tasks_for_gantt(assignee_filter)

    if not tasks:
        await message.answer("Нет задач для отображения.")
        return

    pdf_buf = generate_gantt_pdf(tasks)
    doc = BufferedInputFile(
        pdf_buf.read(),
        filename=f"gantt_{datetime.now().strftime('%Y%m%d')}.pdf"
    )
    await message.answer_document(doc, caption="Диаграмма Ганта — Совет Директоров")


async def _send_agenda(message: Message):
    if not is_chairman(message.from_user.username):
        await message.answer("Генерация адженды доступна Председателю.")
        return

    await message.answer("Готовлю адженду следующего совещания...")
    agenda_text = await _build_agenda()
    await message.answer(agenda_text)


async def _send_dashboard(message: Message):
    async with async_session() as session:
        # Count tasks by status
        all_tasks = (await session.execute(select(Task))).scalars().all()

    total = len(all_tasks)
    new = sum(1 for t in all_tasks if t.status == "new")
    in_progress = sum(1 for t in all_tasks if t.status == "in_progress")
    done = sum(1 for t in all_tasks if t.status == "done")
    overdue = sum(1 for t in all_tasks if t.status == "overdue")

    # Count overdue (deadline passed but not done)
    now = datetime.utcnow()
    actually_overdue = sum(
        1 for t in all_tasks
        if t.deadline and t.deadline < now and t.status not in ("done",)
    )

    text = f"ДАШБОРД\n\n"
    text += f"Всего задач: {total}\n"
    text += f"⬜ Новые: {new}\n"
    text += f"🔵 В работе: {in_progress}\n"
    text += f"✅ Выполнено: {done}\n"
    text += f"🔴 Просрочено: {actually_overdue}\n"

    await message.answer(text)


async def _ai_chat(message: Message):
    """Handle free-form AI chat with RAG context."""
    user = message.from_user
    user_name = user.first_name or user.username or "Пользователь"

    # Search relevant meeting chunks
    chunks = await search_relevant_chunks(message.text, limit=5)
    tasks_summary = await _get_tasks_summary()

    await message.answer("Думаю...")

    response = await chat_with_context(
        user_message=message.text,
        user_name=user_name,
        context_chunks=chunks,
        tasks_summary=tasks_summary,
    )

    # Split long responses
    if len(response) > 4000:
        parts = [response[i:i+4000] for i in range(0, len(response), 4000)]
        for part in parts:
            await message.answer(part)
    else:
        await message.answer(response)
