from celery import shared_task
from django.db.models import F
from django.contrib.auth import get_user_model
from .models import Video, VideoHistory
import logging

logger = logging.getLogger(__name__)
User = get_user_model()

@shared_task(bind=True, max_retries=3, default_retry_delay=5)
def increment_video_views_task(self, video_id):
    """
    Safely executes database view increment variations out-of-band.
    """
    try:
        # Atomic database row adjustment execution
        updated_rows = Video.objects.filter(pk=video_id, status="READY").update(views_count=F('views_count') + 1)
        if not updated_rows:
            logger.warning(f"Failed to increment views for video {video_id}: Not found or not ready.")
    except Exception as exc:
        logger.error(f"Error processing views increment task: {exc}. Retrying...")
        raise self.retry(exc=exc)


@shared_task(bind=True, max_retries=3, default_retry_delay=5)
def log_user_history_task(self, user_id, video_id):
    """
    Safely registers or modifies user history entries in background processes.
    """
    try:
        VideoHistory.objects.update_or_create(
            user_id=user_id,
            video_id=video_id
        )
    except Exception as exc:
        logger.error(f"Error mapping user watch history log: {exc}. Retrying...")
        raise self.retry(exc=exc)