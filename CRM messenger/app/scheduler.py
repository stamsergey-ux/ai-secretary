"""Scheduled tasks: deadline reminders, overdue checks, weekly digest."""
from __future__ import annotations

import asyncio
from datetime import datetime, timedelta

from aiogram import Bot
from sqlalchemy import select, and_

from app.database import async_session, Task, Member


async def check_deadlines(bot: Bot):
    """Check tasks for approaching and passed deadlines. Run every hour."""
    now = datetime.utcnow()
    two_days = now + timedelta(days=2)
    today_end = now.replace(hour=23, minute=59, second=59)

    async with async_session() as session:
        # Tasks with deadline in 2 days (not yet notified today — simplified: always notify)
        result = await session.execute(
            select(Task, Member)
            .join(Member, Task.assignee_id == Member.id)
            .where(and_(
                Task.status.in_(["new", "in_progress"]),
                Task.deadline != None,
                Task.deadline <= two_days,
                Task.deadline > now,
            ))
        )
        approaching = result.all()

        for task, member in approaching:
            days_left = (task.deadline - now).days
            if days_left <= 0:
                msg = f"Сегодня срок по задаче #{task.id}: {task.title}"
            elif days_left == 1:
                msg = f"Завтра срок по задаче #{task.id}: {task.title}"
            else:
                msg = f"Через {days_left} дня срок по задаче #{task.id}: {task.title}"

            try:
                await bot.send_message(member.telegram_id, msg)
            except Exception:
                pass

        # Mark overdue tasks
        result = await session.execute(
            select(Task)
            .where(and_(
                Task.status.in_(["new", "in_progress"]),
                Task.deadline != None,
                Task.deadline < now,
            ))
        )
        overdue_tasks = result.scalars().all()

        for task in overdue_tasks:
            task.status = "overdue"

        if overdue_tasks:
            await session.commit()

            # Notify chairman about overdue tasks
            chairman_result = await session.execute(
                select(Member).where(Member.is_chairman == True)
            )
            chairmen = chairman_result.scalars().all()

            overdue_text = f"Просрочено задач: {len(overdue_tasks)}\n\n"
            for task in overdue_tasks[:10]:
                overdue_text += f"🔴 #{task.id} {task.title}\n"

            for ch in chairmen:
                try:
                    await bot.send_message(ch.telegram_id, overdue_text)
                except Exception:
                    pass


async def weekly_digest(bot: Bot, group_chat_id: int | None = None):
    """Send weekly digest of task progress."""
    async with async_session() as session:
        all_tasks = (await session.execute(select(Task))).scalars().all()

    now = datetime.utcnow()
    week_ago = now - timedelta(days=7)

    completed_this_week = [t for t in all_tasks if t.completed_at and t.completed_at > week_ago]
    overdue = [t for t in all_tasks if t.status == "overdue"]
    in_progress = [t for t in all_tasks if t.status == "in_progress"]
    new_tasks = [t for t in all_tasks if t.status == "new"]

    text = "ЕЖЕНЕДЕЛЬНЫЙ ДАЙДЖЕСТ\n\n"
    text += f"✅ Выполнено за неделю: {len(completed_this_week)}\n"
    text += f"🔵 В работе: {len(in_progress)}\n"
    text += f"⬜ Новые: {len(new_tasks)}\n"
    text += f"🔴 Просрочено: {len(overdue)}\n"

    if overdue:
        text += "\nПросроченные задачи:\n"
        for t in overdue[:10]:
            text += f"  - #{t.id} {t.title}\n"

    if group_chat_id:
        try:
            await bot.send_message(group_chat_id, text)
        except Exception:
            pass

    # Also send to chairmen
    async with async_session() as session:
        result = await session.execute(select(Member).where(Member.is_chairman == True))
        chairmen = result.scalars().all()

    for ch in chairmen:
        try:
            await bot.send_message(ch.telegram_id, text)
        except Exception:
            pass


async def run_scheduler(bot: Bot):
    """Main scheduler loop — runs deadline checks every hour."""
    while True:
        try:
            await check_deadlines(bot)
        except Exception as e:
            print(f"Scheduler error: {e}")
        await asyncio.sleep(3600)  # Check every hour
