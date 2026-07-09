# Deep Interview Spec: Mabimo Notice MVP

Status: pending approval
Created: 2026-06-01
Threshold: 20%
Threshold source: default
Project type: brownfield

## Clarity Breakdown

| Dimension | Score | Weight | Weighted |
|-----------|-------|--------|----------|
| Goal Clarity | 0.92 | 0.35 | 0.3225 |
| Constraint Clarity | 0.88 | 0.25 | 0.2200 |
| Success Criteria | 0.88 | 0.25 | 0.2200 |
| Context Clarity | 0.90 | 0.15 | 0.1350 |
| **Total Clarity** | | | **0.8975** |
| **Ambiguity** | | | **10.25%** |

## Topology

| Component | Status | Description | Coverage / Deferral Note |
|-----------|--------|-------------|--------------------------|
| Notice Collection | active | Collect latest posts from the currently implemented notice board. | 1st MVP only targets notices. Updates and events are deferred. |
| New Post Detection and Storage | active | Detect new posts by comparing scraped `thread_id` values against SQLite records. | A missing `thread_id` means new; an existing `thread_id` means old. Store discovery and notification timestamps. |
| Discord Notification | active | Send a Discord webhook message for newly detected notices. | Message uses list data only: title, category, published date, URL. Webhook URL comes from `DISCORD_WEBHOOK_URL`. |
| Manual Execution | active | Run the MVP once by `python app/main.py`. | Scheduling is deferred until after notice MVP and board expansion. |
| Detail Collection and Summary | deferred | Fetch detail pages and generate summaries. | Deferred to phase 2. |
| Existing Post Update Detection | deferred | Detect title/body changes, `(추가)`, `(완료)`, update history, and versioning. | Deferred to phase 3. |
| Update/Event Boards | deferred | Extend collection to update and event boards. | Deferred until before scheduling work. |

## Goal

Build the 1st MVP as a manually executed notice-board notification flow:
collect the latest N posts from the Mabinogi Mobile official notice board,
detect posts whose `thread_id` is not yet stored in SQLite, persist them,
and send a Discord webhook notification containing only the title, category,
published date, and URL.

## Constraints

- Target only the currently implemented notice board for the 1st MVP.
- Use `thread_id` as the only new-post identity key.
- Existing `thread_id` records are treated as old posts even if the title or content changed.
- Do not fetch detail pages in the 1st MVP.
- Do not summarize body content in the 1st MVP.
- Do not use LLM summarization in the 1st MVP.
- Do not include APScheduler in the 1st MVP completion criteria.
- Updates and events are deferred until after notice MVP and before scheduling.
- Existing post update detection and versioning are deferred to phase 3.
- Discord webhook URL is read from `.env` / environment variable `DISCORD_WEBHOOK_URL`.
- Manual execution command remains `python app/main.py`.
- Manual execution output includes aggregate counts: `fetched`, `new`, `sent`, and `failed`.

## Non-Goals

- Detail page parsing.
- Body text extraction.
- Content hash comparison.
- Title-change tracking.
- `(추가)` / `(완료)` update alerting.
- Post version history.
- Scheduled repeated execution.
- Update board collection.
- Event board collection.
- Discord slash commands or bot interactions.
- Admin controls.

## Acceptance Criteria

- [ ] A manual command runs the notice MVP once.
- [ ] The command fetches the latest N notice-board posts.
- [ ] Each scraped post includes `thread_id`, `title`, `category`, `published_at`, and `url`.
- [ ] SQLite stores seen notice posts keyed by `thread_id`.
- [ ] SQLite `posts` table includes `thread_id`, `board_type`, `title`, `category`, `published_at`, `url`, `first_seen_at`, and `notified_at`.
- [ ] If a scraped `thread_id` is absent from SQLite, the post is classified as new.
- [ ] If a scraped `thread_id` already exists in SQLite, the post is classified as existing.
- [ ] New posts are saved to SQLite.
- [ ] A Discord webhook notification is sent for each new post.
- [ ] The Discord notification contains title, category, published date, and URL.
- [ ] Discord webhook URL is configured through `DISCORD_WEBHOOK_URL`.
- [ ] On successful Discord send, `notified_at` is recorded.
- [ ] On failed Discord send, the post remains stored with `notified_at = NULL`.
- [ ] Posts with `notified_at = NULL` can be retried on a later manual run.
- [ ] Existing posts do not trigger another Discord notification.
- [ ] Manual execution is available via `python app/main.py`.
- [ ] Manual execution prints `fetched`, `new`, `sent`, and `failed` counts.
- [ ] No detail page request is required for the 1st MVP.

## Data Model

### `posts`

| Column | Type | Constraint | Meaning |
|--------|------|------------|---------|
| `thread_id` | TEXT | PRIMARY KEY | Official site post identifier; MVP new-post key. |
| `board_type` | TEXT | NOT NULL | Board identifier. For 1st MVP this is `notice`. |
| `title` | TEXT | NOT NULL | Title from the notice list. |
| `category` | TEXT | NULL allowed | Category label from the notice list. |
| `published_at` | TEXT | NULL allowed | Published date text shown by the official site. |
| `url` | TEXT | NOT NULL | Canonical notice URL. |
| `first_seen_at` | TEXT | NOT NULL | Timestamp when this bot first detected the post. |
| `notified_at` | TEXT | NULL allowed | Timestamp when Discord notification succeeded. `NULL` means pending or failed notification. |

`first_seen_at` is intentionally separate from `published_at`: `published_at` is official-site data, while `first_seen_at` is local bot observation time. This supports future delay measurement and retry handling.

### Future `post_versions`

Post update detection and body-version history are deferred, but the MVP schema keeps `thread_id` stable so a later version table can be added without changing the identity model.

Potential future table:

| Column | Type | Meaning |
|--------|------|---------|
| `id` | INTEGER | Version row identifier. |
| `thread_id` | TEXT | Parent post identifier. |
| `title` | TEXT | Version title. |
| `content_text` | TEXT | Parsed detail body text. |
| `content_hash` | TEXT | Hash for change detection. |
| `detected_at` | TEXT | Time this version/change was detected. |
| `change_type` | TEXT | Example: `title_changed`, `content_changed`, `status_marker_changed`. |

## Notification Policy

- New notices are inserted into `posts` before Discord send is attempted.
- If Discord send succeeds, update `notified_at`.
- If Discord send fails, keep the row with `notified_at = NULL`.
- A later manual run may retry rows where `notified_at IS NULL`.
- The 1st MVP uses one webhook URL: `DISCORD_WEBHOOK_URL`.

Message format:

```text
[공지사항]

제목: {title}
분류: {category}
작성일: {published_at}
링크: {url}
```

## Manual Execution

Command:

```powershell
python app/main.py
```

Minimum console summary:

```text
fetched: N
new: N
sent: N
failed: N
```

## Assumptions Exposed & Resolved

| Assumption | Challenge | Resolution |
|------------|-----------|------------|
| New post detection may need detail content. | The site can update existing posts with title markers and detail history. | 1st MVP ignores updates and uses only new `thread_id`. |
| MVP needs summaries. | Summary requires detail collection and additional parsing. | 1st MVP sends title, category, date, and URL only. |
| MVP needs scheduling. | Scheduling adds operational concerns before the core flow is complete. | 1st MVP is a manual one-shot command. |
| MVP should cover all README target boards. | Only notice collection has been tested so far. | 1st MVP is notice-only; updates/events are deferred. |
| Saving only `thread_id` may block future versioning. | Existing posts may later need title/body change history. | Use `posts` as master table and add a future `post_versions` table keyed by `thread_id`. |
| Failed Discord sends may cause lost alerts or duplicate alerts. | Storing only after successful send risks reclassifying posts on failure. | Store first, then set `notified_at` only on successful Discord send. |

## Technical Context

- README defines the broader project as a Mabinogi Mobile official-site notification bot.
- Current tested state: notice-board list crawling works.
- `app/main.py` currently calls `fetch_notice_list()` and prints notice records.
- `app/collectors/notice.py` contains the implemented notice list collector.
- `app/collectors/update.py` and `app/collectors/event.py` are empty.
- `app/repositories/sqlite_repository.py`, `app/services/diff_service.py`, `app/services/notifier_service.py`, and `app/scheduler.py` are empty.
- Dependencies already include `httpx`, `beautifulsoup4`, `lxml`, `apscheduler`, and `python-dotenv`.

## Ontology

| Entity | Type | Fields | Relationships |
|--------|------|--------|---------------|
| NoticePost | scraped record | `thread_id`, `title`, `category`, `published_at`, `url` | Stored as SeenPost; may produce DiscordNotification when new. |
| SeenPost | persistence record | `thread_id`, `title`, `category`, `published_at`, `url`, `created_at` | Used to classify NoticePost as new or existing. |
| DiscordNotification | outbound message | `title`, `category`, `published_at`, `url` | Sent only for new NoticePost records. |
| ManualRun | execution event | run time, fetched count, new count, sent count | Executes the notice-only MVP once. |

## Ontology Convergence

| Round | Entity Count | New | Changed | Stable | Stability Ratio |
|-------|-------------|-----|---------|--------|----------------|
| 1 | 3 | NoticePost, SeenPost, DiscordNotification | - | - | - |
| 2 | 3 | - | SeenPost narrowed to `thread_id` identity | 2 | 67% |
| 3 | 3 | - | DiscordNotification narrowed to list fields only | 2 | 67% |
| 4 | 4 | ManualRun | - | 3 | 75% |
| 5 | 4 | - | NoticePost narrowed to notice board only | 3 | 75% |
| 6 | 4 | - | - | 4 | 100% |

## Recommended Implementation Shape

1. Keep notice collection as the vertical MVP source.
2. Add SQLite repository functions for initializing schema, checking `thread_id`, inserting posts, finding pending notifications, and updating `notified_at`.
3. Add diff/new-post detection around `thread_id`.
4. Add Discord webhook sending from `DISCORD_WEBHOOK_URL`.
5. Make `app/main.py` run the one-shot flow and log fetched/new/sent/failed counts.

## Interview Transcript

<details>
<summary>Full Q&A</summary>

### Round 0
**Q:** Is the topology correct: collection, new detection/storage, summary, Discord notification, scheduling/logging?
**A:** Topology is correct. Current state is notice list crawling tested only; detail content has not been started.

### Round 1
**Q:** What counts as successful new detection for the notice MVP?
**A:** Fetch latest N posts, check whether DB has the same `thread_id`; absent means new, present means existing. The site may update existing posts with title markers and detail history.
**Ambiguity:** 50%

### Round 2
**Q:** Should existing post changes like `(추가)`, `(완료)`, or detail updates be in MVP?
**A:** No. MVP only alerts on new `thread_id`; content changes are deferred.
**Ambiguity:** 39%

### Round 3
**Q:** Is a Discord message using only list data enough?
**A:** Yes. Send title, category, published date, and URL only. No body summary.
**Ambiguity:** 28%

### Round 4
**Q:** Should MVP include scheduler, or should manual one-shot execution be enough?
**A:** Manual one-shot execution is the completion criterion. Detail/summary is phase 2; update detection/versioning is phase 3.
**Ambiguity:** 22%

### Round 5
**Q:** Should the 1st MVP target only notices, or notices/updates/events?
**A:** 1st MVP targets only the currently implemented notice board. Updates/events are deferred until before scheduling.
**Ambiguity:** 10.25%

### Round 6
**Q:** What SQLite fields should the 1st MVP store?
**A:** Use the recommended schema: `thread_id`, `board_type`, `title`, `category`, `published_at`, `url`, `first_seen_at`, `notified_at`.
**Ambiguity:** 9%

### Round 7
**Q:** Has future body update versioning been considered?
**A:** Yes. Keep `posts` as the master table and later add `post_versions` for body/title/status-marker changes.
**Ambiguity:** 9%

### Round 8
**Q:** What should happen when Discord send fails?
**A:** Store new posts first. On success set `notified_at`; on failure leave `notified_at = NULL` for retry.
**Ambiguity:** 8%

### Round 9
**Q:** Should Discord config and message format use `DISCORD_WEBHOOK_URL` and the proposed text template?
**A:** Yes, confirmed.
**Ambiguity:** 7%

### Round 10
**Q:** Should manual execution remain `python app/main.py`, with `fetched`, `new`, `sent`, `failed` output?
**A:** Yes, sufficient.
**Ambiguity:** 6%

</details>
