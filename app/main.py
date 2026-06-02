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


BOARD_TYPE = "notice"


def send_pending_notifications(connection, webhook_url: str | None) -> tuple[int, int]:
    pending_posts = find_pending_notifications(connection)
    if not webhook_url:
        if pending_posts:
            print("[ERROR] DISCORD_WEBHOOK_URL is not configured.")
        return 0, len(pending_posts)

    sent = 0
    failed = 0
    for post in pending_posts:
        try:
            send_discord_notification(webhook_url, post)
        except DiscordNotificationError as exc:
            failed += 1
            print(f"[ERROR] Discord send failed for {post['thread_id']}: {exc}")
            continue
        except Exception:
            failed += 1
            print(f"[ERROR] Discord send failed for {post['thread_id']}: unexpected error")
            continue

        notified_at = datetime.now(timezone.utc).isoformat()
        update_notified_at(connection, post["thread_id"], notified_at)
        sent += 1

    return sent, failed


def main() -> None:
    load_dotenv()

    notices = fetch_notice_list()
    webhook_url = os.getenv("DISCORD_WEBHOOK_URL")

    with closing(connect()) as connection:
        initialize(connection)
        new_posts = detect_and_store_new_posts(
            connection,
            notices,
            board_type=BOARD_TYPE,
        )
        sent, failed = send_pending_notifications(connection, webhook_url)

    print(f"fetched: {len(notices)}")
    print(f"new: {len(new_posts)}")
    print(f"sent: {sent}")
    print(f"failed: {failed}")


if __name__ == "__main__":
    main()
