"""Task management handlers — view, complete, comment."""

import json
from datetime import datetime

from aiogram import Router, F
from aiogram.types import Message, CallbackQuery, InlineKeyboardMarkup, InlineKeyboardButton
from sqlalchemy import select

from app.database import async_session, Task, Member, Meeting, TaskComment

router = Router()


def _task_keyboard(task_id: int, status: str) -> InlineKeyboardMarkup:
    buttons = []
    if status != "done":
        buttons.append([
            InlineKeyboardButton(text="Выполнено", callback_data=f"task_done:{task_id}"),
            InlineKeyboardButton(text="В работе", callback_data=f"task_progress:{task_id}"),
        ])
    buttons.append([
        InlineKeyboardButton(text="Комментировать", callback_data=f"task_comment:{task_id}"),
    ])
    return InlineKeyboardMarkup(inline_keyboard=buttons)


def _format_task(task: Task, assignee_name: str = "?") -> str:
    status_icon = {
        "new": "⬜",
        "in_progress": "🔵",
        "done": "✅",
        "overdue": "🔴",
    }.get(task.status, "⬜")

    priority_icon = {
        "high": "!!!",
        "medium": "",
        "low": "",
    }.get(task.priority, "")

    deadline_str = task.deadline.strftime("%d.%m.%Y") if task.deadline else "без срока"

    text = f"{status_icon} {priority_icon} #{task.id} {task.title}\n"
    text += f"   Ответственный: {assignee_name}\n"
    text += f"   Срок: {deadline_str}\n"
    text += f"   Статус: {task.status}\n"

    if task.context_quote:
        quote = task.context_quote[:150]
        if len(task.context_quote) > 150:
            quote += "..."
        text += f'   Контекст: "{quote}"\n'

    return text


@router.callback_query(F.data == "my_tasks")
async def cb_my_tasks(callback: CallbackQuery):
    """Show user's personal tasks."""
    user_id = callback.from_user.id

    async with async_session() as session:
        member = (await session.execute(
            select(Member).where(Member.telegram_id == user_id)
        )).scalar_one_or_none()

        if not member:
            await callback.message.answer("Ты ещё не зарегистрирован. Нажми /start")
            await callback.answer()
            return

        result = await session.execute(
            select(Task).where(
                Task.assignee_id == member.id,
                Task.status.in_(["new", "in_progress", "overdue"])
            ).order_by(Task.deadline.asc())
        )
        tasks = result.scalars().all()

    if not tasks:
        await callback.message.answer("У тебя нет открытых задач!")
        await callback.answer()
        return

    text = f"Твои открытые задачи ({len(tasks)}):\n\n"
    for task in tasks:
        text += _format_task(task, member.name) + "\n"

    # Send with keyboard for first task
    if tasks:
        await callback.message.answer(text, reply_markup=_task_keyboard(tasks[0].id, tasks[0].status))
    else:
        await callback.message.answer(text)
    await callback.answer()


@router.callback_query(F.data == "all_tasks")
async def cb_all_tasks(callback: CallbackQuery):
    """Show all open tasks."""
    async with async_session() as session:
        result = await session.execute(
            select(Task, Member)
            .outerjoin(Member, Task.assignee_id == Member.id)
            .where(Task.status.in_(["new", "in_progress", "overdue"]))
            .order_by(Task.deadline.asc())
        )
        rows = result.all()

    if not rows:
        await callback.message.answer("Нет открытых задач!")
        await callback.answer()
        return

    text = f"Все открытые задачи ({len(rows)}):\n\n"
    for task, member in rows:
        name = member.name if member else "не назначено"
        text += _format_task(task, name) + "\n"

    if len(text) > 4000:
        text = text[:4000] + "\n\n... (список обрезан)"

    await callback.message.answer(text)
    await callback.answer()


@router.callback_query(F.data.startswith("task_done:"))
async def cb_task_done(callback: CallbackQuery):
    """Mark task as done."""
    task_id = int(callback.data.split(":")[1])

    async with async_session() as session:
        task = await session.get(Task, task_id)
        if not task:
            await callback.answer("Задача не найдена.")
            return

        task.status = "done"
        task.completed_at = datetime.utcnow()
        await session.commit()

    await callback.message.answer(f"Задача #{task_id} отмечена как выполненная!")
    await callback.answer("Выполнено!")


@router.callback_query(F.data.startswith("task_progress:"))
async def cb_task_progress(callback: CallbackQuery):
    """Mark task as in progress."""
    task_id = int(callback.data.split(":")[1])

    async with async_session() as session:
        task = await session.get(Task, task_id)
        if not task:
            await callback.answer("Задача не найдена.")
            return

        task.status = "in_progress"
        await session.commit()

    await callback.message.answer(f"Задача #{task_id} переведена в работу.")
    await callback.answer("В работе!")


@router.callback_query(F.data == "last_protocol")
async def cb_last_protocol(callback: CallbackQuery):
    """Show last confirmed meeting protocol."""
    async with async_session() as session:
        result = await session.execute(
            select(Meeting)
            .where(Meeting.is_confirmed == True)
            .order_by(Meeting.date.desc())
            .limit(1)
        )
        meeting = result.scalar_one_or_none()

    if not meeting:
        await callback.message.answer("Пока нет сохранённых протоколов.")
        await callback.answer()
        return

    text = f"ПРОТОКОЛ: {meeting.title}\n"
    text += f"Дата: {meeting.date.strftime('%d.%m.%Y')}\n"
    text += f"Участники: {meeting.participants}\n\n"
    text += f"{meeting.summary}\n"

    if meeting.decisions:
        try:
            decisions = json.loads(meeting.decisions)
            if decisions:
                text += f"\nРЕШЕНИЯ:\n"
                for d in decisions:
                    text += f"  - {d['text']}\n"
        except (json.JSONDecodeError, KeyError):
            pass

    if len(text) > 4000:
        text = text[:4000] + "\n\n... (протокол обрезан)"

    await callback.message.answer(text)
    await callback.answer()
