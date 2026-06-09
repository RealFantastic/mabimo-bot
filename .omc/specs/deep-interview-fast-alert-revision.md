# Deep Interview Spec: Fast Alert Revision

## Metadata
- Interview ID: fast-alert-revision-2026-06-09
- Type: brownfield
- Generated: 2026-06-09
- Threshold: 20%
- Threshold Source: default
- Status: approved for implementation

## Goal
Revise the service direction from summarized notice delivery to fast Discord alerts based on list data. Notifications should preserve the current useful metadata structure while removing summary/detail-body business logic.

## Decisions
- Remove summary business logic completely.
- Remove OpenAI integration and related dependency.
- Remove notice detail body collection from the current execution path.
- Discord notifications should use title, category, published date, and original URL.
- Existing-post update detection, body hash comparison, and versioning are deferred to a later planning discussion.
- Scheduler planning should happen after the summary-removal commit.

## Acceptance Criteria
- [x] `app/main.py` no longer calls detail body collection or summary generation.
- [x] `app/services/summary_service.py` and related tests are removed.
- [x] Detail body parser/collector code and tests are removed from the active code path.
- [x] SQLite repository no longer creates, inserts, or selects `detail_body`/`summary_text`.
- [x] Discord messages contain no summary section.
- [x] `requirements.txt` no longer depends on `openai`.
- [x] README/AGENT planning documents reflect automation as the next priority.
- [x] Unit tests pass.

## Deferred Work
- APScheduler planning and implementation.
- Update/event board expansion.
- User-feedback-based notification reliability and UX improvements.
- Existing-post update detection, body hash comparison, and versioning.
