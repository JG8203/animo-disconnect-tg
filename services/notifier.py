import asyncio
import logging
from typing import List, Optional

from telegram import Update, constants
from telegram.ext import ContextTypes

from models.tracking import TrackingInfo
from services.scraper import CloudflareBlockedError, ScraperService
import bot.formatter as formatter

class NotificationService:
    """Service for sending notifications to users."""
    
    def __init__(self, scraper: ScraperService):
        self.scraper = scraper
        
    async def send_long_message(
        self, ctx: ContextTypes.DEFAULT_TYPE, chat_id: int, 
        text_lines: List[str], title: str = ""
    ) -> None:
        """Sends potentially long messages by splitting them into chunks."""
        msg_limit = constants.MessageLimit.MAX_TEXT_LENGTH
        chunks: List[str] = []
        current_chunk = ""

        for line in text_lines:
            line_with_separators = ("\n\n" if current_chunk else "") + line
            if len(current_chunk) + len(line_with_separators) > msg_limit:
                chunks.append(current_chunk.strip())
                current_chunk = line
            else:
                current_chunk += line_with_separators

        if current_chunk:
            chunks.append(current_chunk.strip())

        for idx, chunk in enumerate(chunks, 1):
            header = (
                f"*{title}* (part {idx}/{len(chunks)})\n\n"
                if len(chunks) > 1 and title
                else ""
            )
            full_message = header + chunk
            try:
                await ctx.bot.send_message(
                    chat_id,
                    full_message,
                    parse_mode=constants.ParseMode.MARKDOWN,
                    disable_web_page_preview=True,
                )
            except Exception as e:
                logging.error(
                    "Failed to send message chunk %d/%d to chat %d: %s",
                    idx, len(chunks), chat_id, e
                )
                if idx == 1:
                    await ctx.bot.send_message(
                        chat_id,
                        f"❌ Error sending status update for {title}. Please try again later.",
                    )
                break
            await asyncio.sleep(0.5)
            
    async def notify_cloudflare_block(
        self, ctx: ContextTypes.DEFAULT_TYPE, chat_id: int, 
        update: Optional[Update] = None
    ) -> None:
        """Notify user about Cloudflare block."""
        msg = (
            "❌ The course checker is temporarily blocked by Cloudflare.\n"
            "Please visit the enrollment site and solve the Cloudflare CAPTCHA/checkbox to unblock access.\n"
            "After checking the Cloudflare checkbox, I'll be able to continue monitoring. I'll keep trying in the background."
        )
        try:
            if update and update.message:
                await update.message.reply_text(msg)
            else:
                await ctx.bot.send_message(chat_id, msg)
        except Exception as e:
            logging.error(
                "Failed to send Cloudflare block notification to chat %d: %s", chat_id, e
            )
        logging.warning("Cloudflare block detected for chat %d", chat_id)
            
    async def send_course_status(
        self, ctx: ContextTypes.DEFAULT_TYPE,
        tracking_info: TrackingInfo,
        update: Optional[Update] = None,
    ) -> None:
        """Fetches and sends the current status of a course/sections to the user."""
        try:
            sections = await self.scraper.fetch_and_filter_data(
                tracking_info.course,
                tracking_info.student_id,
                tracking_info.class_numbers if not tracking_info.track_all else None
            )
        except CloudflareBlockedError:
            await self.notify_cloudflare_block(ctx, tracking_info.chat_id, update=update)
            raise

        if sections is None:
            await ctx.bot.send_message(
                tracking_info.chat_id,
                f"❌ Error fetching data for {tracking_info.course}. Could not check status.",
            )
            return

        if not tracking_info.track_all:
            found_numbers = {s["classNbr"] for s in sections if "classNbr" in s}
            not_found = set(tracking_info.class_numbers) - found_numbers
            if not_found:
                await ctx.bot.send_message(
                    tracking_info.chat_id,
                    f"❌ Note: Section(s) {', '.join(map(str, sorted(not_found)))} "
                    f"for {tracking_info.course} were not found in the latest data.",
                )

        if not sections:
            msg = f"No sections found matching your criteria for {tracking_info.course}. 🤷‍♂️"
            if not tracking_info.track_all:
                msg += f" (Sections: {', '.join(map(str, tracking_info.class_numbers))})"
            await ctx.bot.send_message(tracking_info.chat_id, msg)
            return

        suffix = (
            ""
            if tracking_info.track_all
            else f" (Sections: {', '.join(map(str, tracking_info.class_numbers))})"
        )
        text_lines = formatter.compose_status_lines(tracking_info.course, sections, suffix)
        await self.send_long_message(
            ctx, tracking_info.chat_id, text_lines, 
            title=f"{tracking_info.course}{suffix}"
        )
        
    async def process_course_updates(
        self, ctx: ContextTypes.DEFAULT_TYPE,
        tracking_info: TrackingInfo,
        previous_data: dict,
    ) -> Optional[List[dict]]:
        """
        Fetches, diffs, and notifies user only if there are changes.
        
        Returns:
            The current sections data if successful, None otherwise
        """
        data_key = tracking_info.get_data_key()
        previous_sections = previous_data.get(data_key, [])

        try:
            current_sections = await self.scraper.fetch_and_filter_data(
                tracking_info.course,
                tracking_info.student_id,
                tracking_info.class_numbers if not tracking_info.track_all else None
            )
        except CloudflareBlockedError:
            logging.warning(
                "Cloudflare block during background update for %s user %d",
                data_key, tracking_info.chat_id
            )
            return None
        except Exception as e:
            logging.error(
                "Failed background fetch for %s user %d: %s",
                data_key, tracking_info.chat_id, e
            )
            return None

        if current_sections is None:
            return None

        changes = formatter.diff_courses(previous_sections, current_sections)

        if any(changes.values()):
            logging.info("Changes detected for %s user %d", data_key, tracking_info.chat_id)
            
            suffix = "" if tracking_info.track_all else \
                f" (Sections: {', '.join(map(str, tracking_info.class_numbers))})"
                
            lines = formatter.compose_update_lines(tracking_info.course, changes, suffix)

            await self.send_long_message(
                ctx, tracking_info.chat_id, lines, 
                title=f"Updates for {tracking_info.course}{suffix}"
            )

        return current_sections
