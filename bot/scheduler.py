import asyncio
import logging
from typing import List

from telegram.ext import ContextTypes

from models.tracking import TrackingInfo
from services.storage import StorageService
from services.notifier import NotificationService

class UpdateScheduler:
    """Handles scheduled updates checking for all users."""
    
    def __init__(self, storage: StorageService, notifier: NotificationService):
        self.storage = storage
        self.notifier = notifier
        
    async def broadcast_updates(self, ctx: ContextTypes.DEFAULT_TYPE) -> None:
        """Background task: Check all tracked items for all users and notify of changes."""
        subscriptions = self.storage.subscriptions
        
        if not subscriptions:
            logging.info("Broadcast: No subscribers to check.")
            return

        logging.info(
            "Broadcast: Starting scheduled update check for %d users.", 
            len(subscriptions)
        )
        start_time = asyncio.get_event_loop().time()

        all_tracking_infos: List[TrackingInfo] = []
        for chat_id, prefs in list(subscriptions.items()):
            student_id = prefs.id_no
            if not student_id:
                logging.debug("Broadcast: Skipping user %d - no ID set.", chat_id)
                continue

            for course in prefs.courses:
                all_tracking_infos.append(
                    TrackingInfo(chat_id, student_id, course, track_all=True)
                )

            for course, class_numbers in prefs.sections.items():
                if class_numbers:
                    all_tracking_infos.append(
                        TrackingInfo(
                            chat_id, student_id, course,
                            track_all=False, class_numbers=class_numbers,
                        )
                    )

        if not all_tracking_infos:
            logging.info("Broadcast: No items being tracked by any user.")
            return

        logging.info("Broadcast: Processing %d tracking items.", len(all_tracking_infos))

        # Process each tracking item
        for info in all_tracking_infos:
            prefs = subscriptions[info.chat_id]
            current_data = await self.notifier.process_course_updates(
                ctx, info, prefs.previous_data
            )
            if current_data is not None:
                prefs.previous_data[info.get_data_key()] = current_data
                
        # Save all subscriptions after processing
        self.storage.save()

        end_time = asyncio.get_event_loop().time()
        logging.info(
            "Broadcast: Finished update cycle in %.2f seconds.", 
            end_time - start_time
        )
