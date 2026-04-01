"""
APScheduler-based scheduler for event reminders, auto-completion,
recurring event creation, and review prompts.
"""
import logging
from datetime import datetime, timedelta

from aiogram import Bot
from apscheduler.schedulers.asyncio import AsyncIOScheduler

import database as db

logger = logging.getLogger(__name__)

scheduler = AsyncIOScheduler()


def setup_scheduler(bot: Bot) -> AsyncIOScheduler:
    """Set up and return the scheduler with all jobs."""

    # Every 10 minutes: mark completed events
    scheduler.add_job(
        _job_mark_completed,
        "interval",
        minutes=10,
        args=[bot],
        id="mark_completed",
        replace_existing=True,
    )

    # Every 15 minutes: check for 24h reminders
    scheduler.add_job(
        _job_send_reminders,
        "interval",
        minutes=15,
        args=[bot, 24],
        id="reminder_24h",
        replace_existing=True,
    )

    # Every 15 minutes: check for 2h reminders
    scheduler.add_job(
        _job_send_reminders,
        "interval",
        minutes=15,
        args=[bot, 2],
        id="reminder_2h",
        replace_existing=True,
    )

    # Every 30 minutes: create next occurrences for recurring events
    scheduler.add_job(
        _job_create_recurring,
        "interval",
        minutes=30,
        args=[bot],
        id="recurring_events",
        replace_existing=True,
    )

    # Every hour: prompt reviews for recently completed events
    scheduler.add_job(
        _job_prompt_reviews,
        "interval",
        hours=1,
        args=[bot],
        id="prompt_reviews",
        replace_existing=True,
    )

    scheduler.start()
    logger.info("Scheduler started with all jobs")
    return scheduler


async def _job_mark_completed(bot: Bot) -> None:
    """Mark past events as completed."""
    try:
        completed_ids = await db.mark_completed_events()
        if completed_ids:
            logger.info("Marked events as completed: %s", completed_ids)
    except Exception:
        logger.exception("Error in mark_completed job")


async def _job_send_reminders(bot: Bot, hours_before: int) -> None:
    """Send reminders for events happening in `hours_before` hours."""
    try:
        events = await db.get_events_for_reminder(hours_before)
        for event in events:
            user_ids = await db.get_event_registered_user_ids(event["id"])
            if hours_before == 24:
                time_text = "через 24 часа"
                emoji = "🔔"
            else:
                time_text = "через 2 часа"
                emoji = "⏰"

            text = (
                f"{emoji} <b>Напоминание!</b>\n\n"
                f"Событие <b>{event['title']}</b> начнётся {time_text}!\n\n"
                f"📅 {event['date']}  🕐 {event['time']}\n"
                f"📍 {event['location']}"
            )

            sent = 0
            for uid in user_ids:
                try:
                    await bot.send_message(uid, text)
                    sent += 1
                except Exception:
                    logger.warning("Failed to send reminder to user %s", uid)

            logger.info(
                "Sent %dh reminder for event %s to %d/%d users",
                hours_before, event["id"], sent, len(user_ids),
            )
    except Exception:
        logger.exception("Error in send_reminders job (hours=%s)", hours_before)


async def _job_create_recurring(bot: Bot) -> None:
    """Create next occurrences for completed recurring events."""
    try:
        events = await db.get_recurring_completed_events()
        for event in events:
            # Skip if already has a future occurrence
            if await db.has_next_occurrence(event["id"]):
                continue

            recurrence = event.get("recurrence_type")
            if not recurrence:
                continue

            # Calculate next date
            try:
                current_date = datetime.strptime(event["date"], "%Y-%m-%d")
            except ValueError:
                continue

            if recurrence == "weekly":
                next_date = current_date + timedelta(weeks=1)
            elif recurrence == "biweekly":
                next_date = current_date + timedelta(weeks=2)
            elif recurrence == "monthly":
                # Add ~30 days, adjusting for month boundaries
                month = current_date.month + 1
                year = current_date.year
                if month > 12:
                    month = 1
                    year += 1
                day = min(current_date.day, 28)  # Safe day
                next_date = current_date.replace(year=year, month=month, day=day)
            else:
                continue

            parent_id = event.get("recurrence_parent_id") or event["id"]

            new_id = await db.create_event(
                title=event["title"],
                description=event["description"],
                event_date=next_date.strftime("%Y-%m-%d"),
                event_time=event["time"],
                location=event["location"],
                max_participants=event["max_participants"],
                photo_id=event.get("photo_id"),
                category_id=event.get("category_id"),
                recurrence_type=recurrence,
                recurrence_parent_id=parent_id,
            )

            # Copy ticket types from parent event
            ticket_types = await db.get_ticket_types(event["id"])
            for tt in ticket_types:
                await db.create_ticket_type(
                    event_id=new_id,
                    name=tt["name"],
                    price=tt["price"],
                    max_count=tt["max_count"],
                )

            logger.info(
                "Created recurring event %s (from %s), date=%s",
                new_id, event["id"], next_date.strftime("%Y-%m-%d"),
            )
    except Exception:
        logger.exception("Error in create_recurring job")


async def _job_prompt_reviews(bot: Bot) -> None:
    """Prompt users of recently completed events to leave reviews."""
    try:
        events = await db.get_completed_events_needing_review()
        for event in events:
            user_ids = await db.get_all_registered_user_ids(event["id"])
            for uid in user_ids:
                # Check if user already left a review
                existing = await db.get_user_review(event["id"], uid)
                if existing:
                    continue
                try:
                    await bot.send_message(
                        uid,
                        f"⭐ <b>Как вам событие?</b>\n\n"
                        f"Событие <b>{event['title']}</b> завершилось.\n"
                        f"Оставьте отзыв! Используйте команду:\n"
                        f"<code>/review {event['id']}</code>\n\n"
                        f"Оцените от 1 до 5 звёзд и напишите комментарий.",
                    )
                except Exception:
                    pass  # User may have blocked the bot
    except Exception:
        logger.exception("Error in prompt_reviews job")
