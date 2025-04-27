import asyncio
import logging
from typing import Optional

from telegram import Update, constants
from telegram.ext import ContextTypes

from models.tracking import TrackingInfo
from services.storage import StorageService
from services.scraper import CloudflareBlockedError, ScraperService
from services.notifier import NotificationService
from utils.helpers import parse_course_arg

class CommandHandlers:
    """Handlers for bot commands."""
    
    def __init__(
        self, storage: StorageService, scraper: ScraperService, 
        notifier: NotificationService
    ):
        self.storage = storage
        self.scraper = scraper
        self.notifier = notifier
    
    async def start(self, update: Update, _: ContextTypes.DEFAULT_TYPE) -> None:
        """Handle /start command."""
        chat_id = update.effective_chat.id
        
        if chat_id not in self.storage.subscriptions:
            self.storage.get(chat_id)  # Creates default prefs
            
            await update.message.reply_text(
                "Welcome! 🤖 I can help you track DLSU course slots.\n"
                "1. Set your ID: `/setid <YOUR_ID_NUMBER>`\n"
                "2. Add courses: `/addcourse <COURSE_CODE>` (e.g., `/addcourse CSOPESY`)\n"
                "   Or specific sections: `/addcourse <COURSE_CODE>:<CLASS_NBR>` (e.g., `/addcourse CSOPESY:1234`)\n"
                "Use /help for all commands.",
                parse_mode=constants.ParseMode.MARKDOWN
            )
            logging.info("User %d subscribed", chat_id)
        else:
            await update.message.reply_text(
                "You are already subscribed. Use /help to see commands. 👍"
            )
    
    async def stop(self, update: Update, _: ContextTypes.DEFAULT_TYPE) -> None:
        """Handle /stop command."""
        chat_id = update.effective_chat.id
        if self.storage.delete(chat_id):
            await update.message.reply_text(
                "Unsubscribed successfully. I will no longer send you updates. Bye! 👋"
            )
            logging.info("User %d unsubscribed", chat_id)
        else:
            await update.message.reply_text("You were not subscribed. 🙅")
    
    async def help(self, update: Update, _: ContextTypes.DEFAULT_TYPE) -> None:
        """Handle /help command."""
        await update.message.reply_markdown(
            "*DLSU Course Monitor Bot Commands* 📋\n\n"
            "`/start` - Subscribe to the bot & see welcome message 👋\n"
            "`/stop` - Unsubscribe from the bot 🚫\n"
            "`/setid <ID_NUMBER>` - Set your 8-digit student ID (required for checking courses) 🔖\n"
            "`/addcourse <COURSE>` - Track all sections of a course (e.g., `/addcourse LBYCPA1`) ➕\n"
            "`/addcourse <COURSE>:<CLASS_NBR>` - Track a specific section (e.g., `/addcourse CSOPESY:1234`) 🔎\n"
            "`/removecourse <COURSE or COURSE:CLASS_NBR>` - Stop tracking a course or section ➖\n"
            "`/course <COURSE>` - Show current status of all sections for a course *now* 📊\n"
            "`/course <COURSE>:<CLASS_NBR>` - Show current status of a specific section *now* 🔍\n"
            "`/check` - Manually trigger an update check for all your tracked items *now* 🔄\n"
            "`/prefs` - Show your current settings (ID, tracked courses/sections) ⚙️"
        )
    
    async def setid(self, update: Update, ctx: ContextTypes.DEFAULT_TYPE) -> None:
        """Handle /setid command."""
        chat_id = update.effective_chat.id
        if not ctx.args:
            await update.message.reply_text(
                "Please provide your 8-digit student ID.\nUsage: `/setid <ID_NUMBER>` 🔐",
                parse_mode=constants.ParseMode.MARKDOWN,
            )
            return

        student_id = ctx.args[0].strip()
        if not (student_id.isdigit() and len(student_id) == 8):
            await update.message.reply_text(
                "Invalid ID format. Please provide an 8-digit number. ❌"
            )
            return

        prefs = self.storage.get(chat_id)
        prefs.id_no = student_id
        self.storage.update(chat_id, prefs)

        await update.message.reply_text(
            f"Student ID set to {student_id}. You can now add courses to track. ✅"
        )
        logging.info("User %d set ID to %s", chat_id, student_id)
    
    async def prefs(self, update: Update, _: ContextTypes.DEFAULT_TYPE) -> None:
        """Handle /prefs command."""
        chat_id = update.effective_chat.id
        prefs = self.storage.subscriptions.get(chat_id)

        if not prefs:
            await update.message.reply_text("You are not subscribed. Use /start first. 👋")
            return

        id_no = prefs.id_no or "Not set"
        courses = prefs.courses
        sections_dict = prefs.sections

        lines = [f"*Your Settings* ⚙️"]
        lines.append(f"👤 Student ID: `{id_no}`")

        if courses:
            lines.append(f"📚 Tracking all sections of: {', '.join(sorted(courses))}")
        else:
            lines.append("📚 Tracking all sections of: None")

        if sections_dict:
            section_lines = []
            for course, numbers in sorted(sections_dict.items()):
                if numbers:
                    section_lines.append(
                        f"  - {course}: {', '.join(map(str, sorted(numbers)))}"
                    )
            if section_lines:
                lines.append("🔎 Tracking specific sections:")
                lines.extend(section_lines)
            else:
                lines.append("🔎 Tracking specific sections: None")
        else:
            lines.append("🔎 Tracking specific sections: None")

        await update.message.reply_markdown("\n".join(lines))
    
    async def addcourse(self, update: Update, ctx: ContextTypes.DEFAULT_TYPE) -> None:
        """Handle /addcourse command."""
        chat_id = update.effective_chat.id
        if not ctx.args:
            await update.message.reply_text(
                "Please specify what to track.\n"
                "Usage:\n"
                "  `/addcourse <COURSE>` (e.g., `/addcourse CSOPESY`)\n"
                "  `/addcourse <COURSE>:<CLASS>` (e.g., `/addcourse CSOPESY:1234`)",
                parse_mode=constants.ParseMode.MARKDOWN,
            )
            return

        prefs = self.storage.get(chat_id)

        try:
            course, class_number = parse_course_arg(ctx.args[0])
        except ValueError as exc:
            await update.message.reply_text(f"Invalid format: {exc} ❌")
            return

        if class_number is None:
            if course in prefs.courses:
                await update.message.reply_text(
                    f"You are already tracking all sections of {course}. 🔄"
                )
            else:
                prefs.courses.append(course)
                prefs.courses.sort()
                self.storage.update(chat_id, prefs)
                await update.message.reply_text(
                    f"OK. Added {course} to your tracked courses. I'll notify you of any changes. ✅"
                )
                logging.info("User %d added tracking for course %s", chat_id, course)
        else:
            course_specific_sections = prefs.sections.setdefault(course, [])

            if class_number in course_specific_sections:
                await update.message.reply_text(
                    f"You are already tracking section {class_number} of {course}. 🔄"
                )
            else:
                course_specific_sections.append(class_number)
                course_specific_sections.sort()
                self.storage.update(chat_id, prefs)
                await update.message.reply_text(
                    f"OK. Added section {class_number} of {course} to your tracked sections. ✅"
                )
                logging.info(
                    "User %d added tracking for %s:%d", chat_id, course, class_number
                )
    
    async def removecourse(self, update: Update, ctx: ContextTypes.DEFAULT_TYPE) -> None:
        """Handle /removecourse command."""
        chat_id = update.effective_chat.id
        if not ctx.args:
            await update.message.reply_text(
                "Please specify what to stop tracking.\n"
                "Usage:\n"
                "  `/removecourse <COURSE>`\n"
                "  `/removecourse <COURSE>:<CLASS>`",
                parse_mode=constants.ParseMode.MARKDOWN,
            )
            return

        prefs = self.storage.subscriptions.get(chat_id)
        if not prefs:
            await update.message.reply_text("You are not subscribed. Use /start first. 👋")
            return

        try:
            course, class_number = parse_course_arg(ctx.args[0])
        except ValueError as exc:
            await update.message.reply_text(f"Invalid format: {exc} ❌")
            return

        removed = False

        if class_number is None:
            if course in prefs.courses:
                prefs.courses.remove(course)
                prefs.previous_data.pop(course, None)
                await update.message.reply_text(
                    f"Stopped tracking all sections of {course}. ✅"
                )
                logging.info("User %d removed tracking for course %s", chat_id, course)
                removed = True
            else:
                await update.message.reply_text(
                    f"You were not tracking all sections of {course}. 🙅"
                )
        else:
            course_specific_sections = prefs.sections.get(course, [])

            if class_number in course_specific_sections:
                course_specific_sections.remove(class_number)
                if not course_specific_sections:
                    prefs.sections.pop(course, None)
                if course not in prefs.sections:
                    prefs.previous_data.pop(f"{course}:sections", None)

                await update.message.reply_text(
                    f"Stopped tracking section {class_number} of {course}. ✅"
                )
                logging.info(
                    "User %d removed tracking for %s:%d", chat_id, course, class_number
                )
                removed = True
            else:
                await update.message.reply_text(
                    f"You were not tracking section {class_number} of {course}. 🙅"
                )

        if removed:
            self.storage.update(chat_id, prefs)
    
    async def course(self, update: Update, ctx: ContextTypes.DEFAULT_TYPE) -> None:
        """Handle /course command - show current status."""
        chat_id = update.effective_chat.id
        if not ctx.args:
            await update.message.reply_text(
                "Usage:\n"
                "  `/course <COURSE>` (e.g., `/course CSOPESY`)\n"
                "  `/course <COURSE>:<CLASS>` (e.g., `/course CSOPESY:1234`)",
                parse_mode=constants.ParseMode.MARKDOWN
            )
            return

        prefs = self.storage.subscriptions.get(chat_id)
        if not prefs:
            await update.message.reply_text("You need to subscribe first. Use /start. 👋")
            return

        student_id = prefs.id_no
        if not student_id:
            await update.message.reply_text(
                "Please set your student ID first using `/setid <ID_NUMBER>`. 🔖",
                parse_mode=constants.ParseMode.MARKDOWN,
            )
            return

        try:
            course, class_number = parse_course_arg(ctx.args[0])
        except ValueError as exc:
            await update.message.reply_text(f"Invalid format: {exc} ❌")
            return

        course_display = course
        if class_number:
            course_display = f"{course}:{class_number}"
            
        await update.message.reply_text(f"Fetching current status for {course_display}... 🔄")
        
        tracking_info = TrackingInfo(
            chat_id=chat_id, 
            student_id=student_id, 
            course=course, 
            track_all=(class_number is None),
            class_numbers=[class_number] if class_number else []
        )
        
        try:
            await self.notifier.send_course_status(ctx, tracking_info, update=update)
        except CloudflareBlockedError:
            # Already handled in send_course_status
            pass
    
    async def check(self, update: Update, ctx: ContextTypes.DEFAULT_TYPE) -> None:
        """Handle /check command - force update check."""
        chat_id = update.effective_chat.id
        prefs = self.storage.subscriptions.get(chat_id)

        if not prefs:
            await update.message.reply_text("You need to subscribe first. Use /start. 👋")
            return

        student_id = prefs.id_no
        if not student_id:
            await update.message.reply_text(
                "Please set your student ID first using `/setid <ID_NUMBER>`. 🔖",
                parse_mode=constants.ParseMode.MARKDOWN,
            )
            return

        courses_to_check = prefs.courses
        sections_to_check = prefs.sections

        if not courses_to_check and not sections_to_check:
            await update.message.reply_text(
                "You are not tracking any courses or sections yet. Use /addcourse to add some. ➕"
            )
            return

        await update.message.reply_text("Checking status for your tracked items now... 🔄")

        cloudflare_blocked = False

        for course in courses_to_check:
            tracking_info = TrackingInfo(
                chat_id=chat_id, student_id=student_id, course=course, track_all=True
            )
            try:
                await self.notifier.send_course_status(ctx, tracking_info, update=update)
            except CloudflareBlockedError:
                cloudflare_blocked = True
                break
            await asyncio.sleep(0.5)

        if not cloudflare_blocked:
            for course, class_numbers in sections_to_check.items():
                if class_numbers:
                    tracking_info = TrackingInfo(
                        chat_id=chat_id,
                        student_id=student_id,
                        course=course,
                        track_all=False,
                        class_numbers=class_numbers,
                    )
                    try:
                        await self.notifier.send_course_status(ctx, tracking_info, update=update)
                    except CloudflareBlockedError:
                        cloudflare_blocked = True
                        break
                    await asyncio.sleep(0.5)

        if not cloudflare_blocked:
            await update.message.reply_text("Finished checking all tracked items. ✅")

    async def cache_stats(self, update: Update, _: ContextTypes.DEFAULT_TYPE) -> None:
        """Handle /cache command - show cache statistics."""
        chat_id = update.effective_chat.id
        
        stats = self.scraper.cache.get_stats()
        
        await update.message.reply_markdown(
            "*Cache Statistics* 📊\n\n"
            f"Total cached courses: {stats['total_entries']}\n"
            f"Valid cache entries: {stats['valid_entries']}\n"
            f"Expired entries: {stats['expired_entries']}\n\n"
            f"Cache hit rate: {stats['hit_rate']}\n"
            f"Cache hits: {stats['hits']}\n"
            f"Cache misses: {stats['misses']}\n\n"
            f"Cache TTL: 60\n"
            f"Cache enabled: True\n"
        )

