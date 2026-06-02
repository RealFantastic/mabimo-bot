import os
import re
from collections.abc import Callable, Mapping
from typing import Any

from app.utils.logger import get_logger


DEFAULT_SUMMARY_MODEL = "gpt-5-mini"
logger = get_logger(__name__)


def generate_notice_summary(
    post: Mapping[str, Any],
    *,
    env: Mapping[str, str] | None = None,
    client_factory: Callable[[str], Any] | None = None,
) -> str:
    detail_body = str(post.get("detail_body") or "")
    resolved_env = env if env is not None else os.environ
    api_key = resolved_env.get("OPENAI_API_KEY", "").strip()
    if not api_key:
        logger.info("OPENAI_API_KEY is not configured; using fallback notice summary")
        return fallback_summary(detail_body)

    model = resolved_env.get("OPENAI_SUMMARY_MODEL", DEFAULT_SUMMARY_MODEL).strip()
    if not model:
        model = DEFAULT_SUMMARY_MODEL
    logger.info("OpenAI summary model selected: %s", model)

    try:
        client = (
            client_factory(api_key)
            if client_factory is not None
            else _create_openai_client(api_key)
        )
        response = client.responses.create(
            model=model,
            input=[
                {
                    "role": "system",
                    "content": _system_prompt(),
                },
                {
                    "role": "user",
                    "content": _user_prompt(post, detail_body),
                },
            ],
        )
        summary_text = _extract_response_text(response)
        if summary_text:
            logger.debug("OpenAI notice summary generated: chars=%s", len(summary_text))
            return summary_text
        logger.warning("OpenAI summary response did not include text; using fallback summary")
    except Exception as exc:
        logger.warning(
            "OpenAI notice summary generation failed: error_type=%s; using fallback summary",
            exc.__class__.__name__,
        )

    return fallback_summary(detail_body)


def fallback_summary(detail_body: str, *, max_chars: int = 240) -> str:
    preview = re.sub(r"\s+", " ", detail_body).strip()
    if not preview:
        logger.debug("Fallback summary used because detail body is empty")
        preview = "본문 내용을 확인할 수 없습니다."
    elif len(preview) > max_chars:
        logger.debug(
            "Fallback summary truncating detail preview: chars=%s max_chars=%s",
            len(preview),
            max_chars,
        )
        # Prefer ending fallback previews at a sentence boundary when one is nearby.
        truncated = preview[:max_chars]
        sentence_boundary = max(
            truncated.rfind("."),
            truncated.rfind("!"),
            truncated.rfind("?"),
            truncated.rfind("。"),
        )
        if sentence_boundary > max_chars // 2:
            truncated = truncated[:sentence_boundary]
        preview = truncated.rstrip(" .") + "..."

    return f"🧾 요약\n- {preview}"


def _create_openai_client(api_key: str) -> Any:
    from openai import OpenAI

    return OpenAI(api_key=api_key)


def _system_prompt() -> str:
    return (
        "너는 마비노기 모바일 공지사항을 요약하는 한국어 알림 작성자다. "
        "본문에 있는 사실만 사용하고 추측하지 않는다. "
        "Discord 메시지 중간에 들어갈 요약만 작성한다.\n\n"
        "형식:\n"
        "🧾 요약\n"
        "- 핵심 내용 1\n"
        "- 핵심 내용 2\n"
        "- 핵심 내용 3\n\n"
        "✅ 체크사항\n"
        "- 기간/시간: 본문에 있을 때만 작성\n"
        "- 보상/대상: 본문에 있을 때만 작성\n"
        "- 해야 할 일: 본문에 있을 때만 작성\n\n"
        "규칙:\n"
        "- 전체 출력은 한국어로 작성한다.\n"
        "- 체크사항은 본문에 있는 항목만 포함하고, 빈 항목이나 자리표시자는 쓰지 않는다.\n"
        "- 점검 공지는 시간, 영향 서비스, 이용자 행동을 우선한다.\n"
        "- 이벤트 공지는 기간, 보상, 대상, 참여 방법을 우선한다.\n"
        "- 제목 줄과 원문 URL 줄은 쓰지 않는다."
    )


def _user_prompt(post: Mapping[str, Any], detail_body: str) -> str:
    return (
        f"제목: {post.get('title', '')}\n"
        f"분류: {post.get('category', '')}\n\n"
        f"본문:\n{detail_body}"
    )


def _extract_response_text(response: Any) -> str:
    output_text = getattr(response, "output_text", "")
    if isinstance(output_text, str) and output_text.strip():
        return output_text.strip()

    output = getattr(response, "output", None)
    if not output:
        return ""

    parts: list[str] = []
    for item in output:
        for content in getattr(item, "content", []) or []:
            text = getattr(content, "text", "")
            if isinstance(text, str) and text.strip():
                parts.append(text.strip())

    return "\n".join(parts).strip()
