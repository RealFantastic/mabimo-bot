import argparse
import os
import sys
from contextlib import closing
from collections.abc import Callable, Sequence
from dataclasses import dataclass
from datetime import datetime, timezone
from pathlib import Path

from dotenv import load_dotenv


PROJECT_ROOT = Path(__file__).resolve().parent.parent
if str(PROJECT_ROOT) not in sys.path:
    sys.path.insert(0, str(PROJECT_ROOT))

from app.collectors.notice import fetch_notice_list
from app.repositories.sqlite_repository import (
    connect,
    create_test_delivery,
    find_pending_notifications,
    initialize,
    mark_delivery_failed_final,
    mark_delivery_failed,
    mark_delivery_sent,
)
from app.services.diff_service import detect_and_store_new_posts
from app.services.notifier_service import (
    DiscordNotificationError,
    UnknownBoardTypeError,
    send_discord_message,
    send_discord_notification,
)
from app.scheduler import DEFAULT_INTERVAL_MINUTES, create_scheduler
from app.utils.logger import configure_logger, get_logger


BOARD_TYPE = "notice"
logger = get_logger(__name__)


@dataclass(frozen=True)
class BoardSource:
    board_type: str
    fetch: Callable[[], list[dict]]


BOARD_SOURCES: tuple[BoardSource, ...] = (
    BoardSource(board_type=BOARD_TYPE, fetch=fetch_notice_list),
)


def positive_interval(value: str) -> int:
    try:
        interval = int(value)
    except ValueError as exc:
        raise argparse.ArgumentTypeError("interval must be an integer") from exc
    if interval <= 0:
        raise argparse.ArgumentTypeError("interval must be greater than 0")
    return interval


def parse_args(argv: Sequence[str] | None = None) -> argparse.Namespace:
    parser = argparse.ArgumentParser(description="Run the Mabimo board notifier.")
    subparsers = parser.add_subparsers(dest="command")
    subparsers.add_parser("run-once", help="Run new-post detection once and exit.")
    scheduler_parser = subparsers.add_parser("scheduler", help="Run the APScheduler loop.")
    scheduler_parser.add_argument(
        "--interval-minutes",
        type=positive_interval,
        default=DEFAULT_INTERVAL_MINUTES,
        help="Scheduler interval in minutes. Must be greater than 0.",
    )
    test_parser = subparsers.add_parser(
        "send-test",
        help="Send a Discord test message and record it as a test delivery.",
    )
    test_parser.add_argument(
        "--message",
        help="Custom test message content. Defaults to a generated connection check.",
    )
    parser.set_defaults(command="run-once", interval_minutes=DEFAULT_INTERVAL_MINUTES)
    return parser.parse_args(argv)


def send_pending_notifications(connection, webhook_url: str | None) -> tuple[int, int]:
    pending_posts = find_pending_notifications(connection)
    logger.info("Pending Discord notifications: %s", len(pending_posts))
    if not webhook_url:
        if pending_posts:
            logger.error("DISCORD_WEBHOOK_URL is not configured.")
        attempted_at = datetime.now(timezone.utc).isoformat()
        for post in pending_posts:
            mark_delivery_failed(
                connection,
                post["delivery_id"],
                attempted_at=attempted_at,
                error_message="DISCORD_WEBHOOK_URL is not configured.",
            )
        return 0, len(pending_posts)

    sent = 0
    failed = 0
    for post in pending_posts:
        thread_id = post["thread_id"]
        try:
            response_status_code = send_discord_notification(webhook_url, post)
        except DiscordNotificationError as exc:
            failed += 1
            attempted_at = datetime.now(timezone.utc).isoformat()
            mark_delivery_failed(
                connection,
                post["delivery_id"],
                attempted_at=attempted_at,
                error_message=str(exc),
                response_status_code=exc.status_code,
            )
            logger.error("Discord send failed for thread_id=%s: %s", thread_id, exc)
            continue
        except UnknownBoardTypeError as exc:
            failed += 1
            attempted_at = datetime.now(timezone.utc).isoformat()
            mark_delivery_failed(
                connection,
                post["delivery_id"],
                attempted_at=attempted_at,
                error_message=str(exc),
            )
            logger.error("Discord message skipped for thread_id=%s: %s", thread_id, exc)
            continue
        except Exception as exc:
            failed += 1
            attempted_at = datetime.now(timezone.utc).isoformat()
            mark_delivery_failed(
                connection,
                post["delivery_id"],
                attempted_at=attempted_at,
                error_message=exc.__class__.__name__,
            )
            logger.exception(
                "Discord send failed for thread_id=%s: unexpected error",
                thread_id,
            )
            continue

        sent_at = datetime.now(timezone.utc).isoformat()
        mark_delivery_sent(
            connection,
            post["delivery_id"],
            sent_at=sent_at,
            response_status_code=response_status_code or 204,
        )
        sent += 1

    logger.info("Discord notification summary: sent=%s failed=%s", sent, failed)
    return sent, failed


def run_once(
    *,
    webhook_url: str | None = None,
    board_sources: Sequence[BoardSource] = BOARD_SOURCES,
) -> dict[str, int]:
    logger.info("Mabimo board run started")
    fetched_count = 0
    new_count = 0
    board_failed_count = 0
    with closing(connect()) as connection:
        initialize(connection)
        for source in board_sources:
            try:
                posts = source.fetch()
                fetched_count += len(posts)
                logger.info(
                    "Fetched board posts: board_type=%s count=%s",
                    source.board_type,
                    len(posts),
                )
                # Store before sending so notification failures do not lose newly discovered posts.
                new_posts = detect_and_store_new_posts(
                    connection,
                    posts,
                    board_type=source.board_type,
                )
                new_count += len(new_posts)
                logger.info(
                    "New board posts: board_type=%s count=%s",
                    source.board_type,
                    len(new_posts),
                )
            except Exception:
                board_failed_count += 1
                logger.exception(
                    "Board source failed: board_type=%s",
                    source.board_type,
                )
                continue
        sent, failed = send_pending_notifications(connection, webhook_url)

    total_failed = board_failed_count + failed
    logger.info(
        "Mabimo board run finished: fetched=%s new=%s sent=%s failed=%s",
        fetched_count,
        new_count,
        sent,
        total_failed,
    )
    return {
        "fetched": fetched_count,
        "new": new_count,
        "sent": sent,
        "failed": total_failed,
    }


def build_test_message(message: str | None = None) -> str:
    if message:
        return message

    sent_at = datetime.now(timezone.utc).isoformat()
    return "\n".join(
        [
            "[마비모 알림봇 테스트]",
            "",
            "Discord Webhook 연결 확인 메시지입니다.",
            f"발송 시각: {sent_at}",
        ]
    )


def send_test_notification(
    *,
    webhook_url: str | None = None,
    message: str | None = None,
) -> dict[str, int]:
    test_message = build_test_message(message)
    with closing(connect()) as connection:
        initialize(connection)
        delivery_id = create_test_delivery(connection, message=test_message)

        if not webhook_url:
            attempted_at = datetime.now(timezone.utc).isoformat()
            mark_delivery_failed_final(
                connection,
                delivery_id,
                attempted_at=attempted_at,
                error_message="DISCORD_WEBHOOK_URL is not configured.",
            )
            logger.error("DISCORD_WEBHOOK_URL is not configured.")
            return {"sent": 0, "failed": 1}

        try:
            response_status_code = send_discord_message(
                webhook_url,
                test_message,
                log_context=f"test_delivery_id={delivery_id}",
            )
        except DiscordNotificationError as exc:
            attempted_at = datetime.now(timezone.utc).isoformat()
            mark_delivery_failed_final(
                connection,
                delivery_id,
                attempted_at=attempted_at,
                error_message=str(exc),
                response_status_code=exc.status_code,
            )
            logger.error("Discord test send failed: delivery_id=%s %s", delivery_id, exc)
            return {"sent": 0, "failed": 1}
        except Exception as exc:
            attempted_at = datetime.now(timezone.utc).isoformat()
            mark_delivery_failed_final(
                connection,
                delivery_id,
                attempted_at=attempted_at,
                error_message=exc.__class__.__name__,
            )
            logger.exception(
                "Discord test send failed: delivery_id=%s unexpected error",
                delivery_id,
            )
            return {"sent": 0, "failed": 1}

        sent_at = datetime.now(timezone.utc).isoformat()
        mark_delivery_sent(
            connection,
            delivery_id,
            sent_at=sent_at,
            response_status_code=response_status_code or 204,
        )
        logger.info("Discord test notification sent: delivery_id=%s", delivery_id)
        return {"sent": 1, "failed": 0}


def main(argv: Sequence[str] | None = None) -> None:
    args = parse_args(argv)
    load_dotenv()
    configure_logger()
    webhook_url = os.getenv("DISCORD_WEBHOOK_URL")

    if args.command == "run-once":
        run_once(webhook_url=webhook_url)
        return

    if args.command == "send-test":
        summary = send_test_notification(
            webhook_url=webhook_url,
            message=args.message,
        )
        if summary["failed"]:
            sys.exit(1)
        return

    scheduler = create_scheduler(
        lambda: run_once(webhook_url=webhook_url),
        interval_minutes=args.interval_minutes,
    )
    logger.info(
        "Starting Mabimo scheduler: interval_minutes=%s",
        args.interval_minutes,
    )
    scheduler.start()
    try:
        while True:
            import time

            time.sleep(3600)
    except (KeyboardInterrupt, SystemExit):
        scheduler.shutdown()


if __name__ == "__main__":
    main()
