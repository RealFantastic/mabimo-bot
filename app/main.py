import os
import sys
from contextlib import closing
from datetime import datetime, timezone
from pathlib import Path

from dotenv import load_dotenv


PROJECT_ROOT = Path(__file__).resolve().parent.parent
if str(PROJECT_ROOT) not in sys.path:
    sys.path.insert(0, str(PROJECT_ROOT))

from app.collectors.notice import fetch_notice_list
from app.repositories.sqlite_repository import (
    connect,
    find_pending_notifications,
    initialize,
    update_notified_at,
)
from app.services.diff_service import detect_and_store_new_posts
from app.services.notifier_service import (
    DiscordNotificationError,
    send_discord_notification,
)
from app.utils.logger import configure_logger, get_logger


BOARD_TYPE = "notice"
logger = get_logger(__name__)


def send_pending_notifications(connection, webhook_url: str | None) -> tuple[int, int]:
    pending_posts = find_pending_notifications(connection)
    logger.info("Pending Discord notifications: %s", len(pending_posts))
    if not webhook_url:
        if pending_posts:
            logger.error("DISCORD_WEBHOOK_URL is not configured.")
        return 0, len(pending_posts)

    sent = 0
    failed = 0
    for post in pending_posts:
        thread_id = post["thread_id"]
        try:
            send_discord_notification(webhook_url, post)
        except DiscordNotificationError as exc:
            failed += 1
            logger.error("Discord send failed for thread_id=%s: %s", thread_id, exc)
            continue
        except Exception:
            failed += 1
            logger.exception(
                "Discord send failed for thread_id=%s: unexpected error",
                thread_id,
            )
            continue

        # A post stays pending until Discord accepts it, so transient failures retry next run.
        notified_at = datetime.now(timezone.utc).isoformat()
        update_notified_at(connection, thread_id, notified_at)
        sent += 1

    logger.info("Discord notification summary: sent=%s failed=%s", sent, failed)
    return sent, failed


def main() -> None:
    load_dotenv()
    configure_logger()
    logger.info("Mabimo notice run started")

    notices = fetch_notice_list()
    logger.info("Fetched notice count: %s", len(notices))
    webhook_url = os.getenv("DISCORD_WEBHOOK_URL")

    with closing(connect()) as connection:
        initialize(connection)
        # Store before sending so notification failures do not lose newly discovered posts.
        new_posts = detect_and_store_new_posts(
            connection,
            notices,
            board_type=BOARD_TYPE,
        )
        logger.info("New notice count: %s", len(new_posts))
        sent, failed = send_pending_notifications(connection, webhook_url)

    logger.info(
        "Mabimo notice run finished: fetched=%s new=%s sent=%s failed=%s",
        len(notices),
        len(new_posts),
        sent,
        failed,
    )


if __name__ == "__main__":
    main()
