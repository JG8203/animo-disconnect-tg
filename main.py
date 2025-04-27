import logging
import sys
from telegram.ext import Application, CommandHandler

import config
from services.storage import StorageService
from services.cache import CacheService
from services.scraper import ScraperService
from services.notifier import NotificationService
from bot.commands import CommandHandlers
from bot.scheduler import UpdateScheduler

def setup_logging():
    """Configure logging."""
    logging.basicConfig(
        format="%(asctime)s - %(name)s - %(levelname)s - %(message)s",
        level=logging.INFO,
        stream=sys.stdout,
    )
    
    logging.getLogger("httpx").setLevel(logging.WARNING)
    logging.getLogger("httpcore").setLevel(logging.WARNING)
    logging.getLogger("telegram.ext").setLevel(logging.INFO)
    logging.getLogger("telegram.bot").setLevel(logging.INFO)

def main():
    """Main entry point for the bot."""
    setup_logging()
    
    storage_service = StorageService()
    cache_service = CacheService(max_age_seconds=config.CACHE_TTL_SECONDS)
    scraper_service = ScraperService(cache_service)
    notification_service = NotificationService(scraper_service)
    
    storage_service.load()
    
    command_handlers = CommandHandlers(storage_service, scraper_service, notification_service)
    
    update_scheduler = UpdateScheduler(storage_service, notification_service)
    
    app = Application.builder().token(config.BOT_TOKEN).build()
    
    handlers = [
        CommandHandler("start", command_handlers.start),
        CommandHandler("stop", command_handlers.stop),
        CommandHandler("help", command_handlers.help),
        CommandHandler("setid", command_handlers.setid),
        CommandHandler("prefs", command_handlers.prefs),
        CommandHandler("addcourse", command_handlers.addcourse),
        CommandHandler("removecourse", command_handlers.removecourse),
        CommandHandler("course", command_handlers.course),
        CommandHandler("check", command_handlers.check),
        CommandHandler("cache", command_handlers.cache_stats),
    ]
    app.add_handlers(handlers)
    
    app.job_queue.run_repeating(
        update_scheduler.broadcast_updates,
        interval=config.POLLING_INTERVAL,
        first=10,
        name="periodic_update_check",
    )
    
    logging.info(f"Bot starting polling with cache {'enabled' if config.CACHE_ENABLED else 'disabled'}... 🚀")
    app.run_polling()
    logging.info("Bot stopped. 👋")

if __name__ == "__main__":
    main()
