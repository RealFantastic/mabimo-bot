# Deep Interview Spec: Notice Body Summary

## Metadata
- Interview ID: notice-summary-2026-06-02
- Rounds: 5
- Final Ambiguity Score: 14.40%
- Type: brownfield
- Generated: 2026-06-02
- Threshold: 20%
- Threshold Source: default
- Initial Context Summarized: no
- Status: approved for implementation

## Clarity Breakdown
| Dimension | Score | Weight | Weighted |
|-----------|-------|--------|----------|
| Goal Clarity | 0.88 | 0.35 | 0.3080 |
| Constraint Clarity | 0.84 | 0.25 | 0.2100 |
| Success Criteria | 0.84 | 0.25 | 0.2100 |
| Context Clarity | 0.88 | 0.15 | 0.1320 |
| **Total Clarity** | | | **0.8560** |
| **Ambiguity** | | | **14.40%** |

## Topology
| Component | Status | Description | Coverage / Deferral Note |
|-----------|--------|-------------|--------------------------|
| Summary Method | active | Use an external LLM API to summarize collected notice detail bodies. | OpenAI API is selected. Prefer a low-cost model with enough quality for Korean game notices. |
| Summary Output Format | active | Format Discord-facing summaries with emoji sections and bullet points. | User approved the proposed structure with summary bullets and checklist bullets. |
| Integration Point | active | Decide when summaries are generated, stored, and reused. | Generate once when a new notice is detected, store it, and reuse it for Discord retries. |
| Operational Constraints | active | Define cost, API key, failure behavior, security, and retry expectations. | Small API cost is acceptable. Fallback is required so alerts do not stop on LLM failure. |

## Goal
Automatically summarize collected Mabinogi Mobile notice detail bodies so Discord notifications replace the current manual workflow of pasting notice links into ChatGPT. The summary should be readable at a glance, use appropriate emoji section markers, and surface important action/check items in bullet points.

## Constraints
- Use OpenAI API for the first summary implementation.
- Use the OpenAI Responses API for new text generation integration.
- Recommended default model: `gpt-5-mini` for quality/cost balance.
- Optional lower-cost configuration: allow `gpt-5-nano` through environment configuration if cost becomes more important than quality.
- Generate summaries only for newly detected posts whose `detail_body` is collected.
- Store the generated summary in SQLite so Discord retry does not call the LLM again.
- If LLM summarization fails, store/use a fallback preview derived from `detail_body`.
- Do not block Discord notification delivery solely because summarization failed.
- Keep Discord `allowed_mentions: {"parse": []}` behavior.
- Do not implement scheduler, board expansion, update detection/versioning, slash commands, or admin controls in this feature.
- Do not summarize existing posts retroactively in the first implementation unless explicitly requested later.

## Non-Goals
- LLM provider comparison beyond selecting OpenAI for the first implementation.
- Multi-provider abstraction unless needed by tests and simple boundaries.
- Prompt tuning for every notice category.
- Detecting changed existing notices.
- Creating `post_versions`.
- Automatically translating or rewriting notices beyond concise Korean summary/checklist extraction.
- Sending raw long body text to Discord.

## Accepted Discord Output Format
```text
📢 [공지사항] {title}

🧾 요약
- 핵심 내용 1
- 핵심 내용 2
- 핵심 내용 3

✅ 체크사항
- 기간/시간: ...
- 보상/대상: ...
- 해야 할 일: ...

🔗 원문: {url}
```

Rules:
- The checklist section should include only items present in the notice.
- Maintenance notices should prioritize time, affected service, and user action.
- Event notices should prioritize period, reward, target, and participation method.
- Empty checklist items should be omitted rather than filled with placeholders.

## Acceptance Criteria
- [ ] A new summary service can create a Korean summary from `detail_body`.
- [ ] The summary request uses OpenAI API and reads the API key from environment configuration.
- [ ] The model is configurable, with `gpt-5-mini` as the recommended default.
- [ ] The prompt instructs the model to produce concise Korean output in the approved structure.
- [ ] The system stores generated summary text in SQLite for each new post.
- [ ] A Discord retry uses the stored summary and does not call the LLM again.
- [ ] If the OpenAI call fails, the system stores or uses a safe fallback preview from `detail_body`.
- [ ] Discord notification formatting uses the approved emoji + bullet structure.
- [ ] Tests mock the OpenAI API; no unit test calls the real API.
- [ ] Existing notifier security behavior remains intact: no webhook URL logging and mentions disabled.
- [ ] Existing 11 tests continue to pass.

## Assumptions Exposed & Resolved
| Assumption | Challenge | Resolution |
|------------|-----------|------------|
| Summary could be rule-based to avoid cost. | User currently relies on ChatGPT-like manual summaries and wants quality. | Use external LLM API. Small API cost is acceptable. |
| Summary can be generated at notification time. | Discord retry could repeatedly call the LLM and increase cost. | Generate once for a new notice and store the result. |
| Summary failure can fail the notification. | Notification delivery is the core bot value. | Use fallback preview if LLM fails. |
| Output format is uncertain. | Discord readability depends on predictable structure. | Use the approved emoji sections and bullet/checklist format. |

## Technical Context
- `app/parsers/detail_parser.py` parses `detail_body` from notice detail HTML.
- `app/collectors/notice.py` exposes `fetch_notice_detail_body(url)`.
- `app/services/diff_service.py` currently fetches `detail_body` only for newly detected posts.
- `app/repositories/sqlite_repository.py` stores `posts.detail_body` and performs a compatibility migration.
- `app/services/notifier_service.py` currently formats title/category/date/link only and does not use summary fields.
- `app/main.py` calls `detect_and_store_new_posts(..., detail_body_fetcher=fetch_notice_detail_body)`.
- Current tests cover body parsing, body fetch wrapping, new-only body collection, SQLite compatibility, and notifier safety.

## OpenAI Stack Decision
- Use the OpenAI Python SDK.
- Use the Responses API because OpenAI documentation recommends it for new text generation apps.
- Use `gpt-5-mini` as the default target model for summary quality with controlled cost.
- Keep model configurable via environment variable such as `OPENAI_SUMMARY_MODEL`.
- Use an environment variable such as `OPENAI_API_KEY` for credentials.
- Consider `gpt-5-nano` as a future cost-saving option if summary quality remains acceptable.

## Ontology
| Entity | Type | Fields | Relationships |
|--------|------|--------|---------------|
| NoticePost | domain record | `thread_id`, `title`, `url`, `detail_body`, `summary_text` | New posts trigger detail collection and summary generation. |
| DetailBody | input content | normalized body text | Input to summary generation. |
| Summary | generated content | summary bullets, checklist bullets, fallback marker | Stored and used by DiscordNotification. |
| CheckItem | generated content | label, value | Rendered under checklist section when present. |
| LLMProvider | external system | provider, model, API key | Generates Summary from DetailBody. |
| DiscordMessage | outbound message | title, summary, checklist, url | Sent through existing webhook notifier. |
| FallbackPreview | fallback content | preview text | Used when LLMProvider fails. |

## Ontology Convergence
| Round | Entity Count | New | Changed | Stable | Stability Ratio |
|-------|-------------|-----|---------|--------|----------------|
| 1 | 5 | Summary, DetailBody, LLMProvider, DiscordMessage, UserDecision | - | - | - |
| 2 | 7 | FallbackPreview, ApiCostLimit | - | 5 | 71% |
| 3 | 7 | CheckItem | ApiCostLimit folded into OperationalConstraints | 6 | 86% |
| 4 | 7 | SummaryText | Summary storage clarified | 6 | 86% |
| 5 | 7 | - | LLMProvider fixed to OpenAI API | 7 | 100% |

## Interview Transcript
<details>
<summary>Full Q&A (5 rounds)</summary>

### Round 0
**Q:** Confirm topology: Summary Method, Summary Output Format, Integration Point, Operational Constraints.
**A:** 맞아 이 4개로 진행하자.

### Round 1
**Q:** Should summarization use an external LLM API, rule-based local logic, or hybrid?
**A:** 아직 잘 모르겠어. 장단점을 비교해줘.
**Ambiguity:** 48.00%

### Round 2
**Q:** Which operational direction is closest: quality-first LLM, cost/simple rule-based, or hybrid?
**A:** 1번에 제일 가까워. 단, API 비용은 소량이면 좋겠어.
**Ambiguity:** 35.50%

### Round 3
**Q:** Is the proposed Discord format acceptable?
**A:** 지금 구조 딱 맘에든다.
**Ambiguity:** 21.90%

### Round 4
**Q:** Should summaries be generated and stored when a new notice is detected?
**A:** 추천하는 방향으로 확정해줘.
**Ambiguity:** 16.90%

### Round 5
**Q:** Should the LLM stack use OpenAI API as recommended?
**A:** 추천하는 방식으로 진행해줘.
**Ambiguity:** 14.40%

</details>
