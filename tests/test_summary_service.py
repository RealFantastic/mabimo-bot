import unittest
from types import SimpleNamespace
from unittest.mock import Mock, patch

from app.services.summary_service import (
    DEFAULT_SUMMARY_MODEL,
    fallback_summary,
    generate_notice_summary,
)


class SummaryServiceTest(unittest.TestCase):
    def test_generate_notice_summary_calls_openai_responses_api_with_prompt(self) -> None:
        client = Mock()
        client.responses.create.return_value = SimpleNamespace(
            output_text="🧾 요약\n- 서버 점검이 진행됩니다.\n\n✅ 체크사항\n- 기간/시간: 10:00~12:00"
        )
        client_factory = Mock(return_value=client)
        env = {
            "OPENAI_API_KEY": "test-api-key",
            "OPENAI_SUMMARY_MODEL": "gpt-5-nano",
        }

        summary = generate_notice_summary(
            {
                "title": "점검 안내",
                "category": "공지",
                "detail_body": "10:00부터 12:00까지 서버 점검이 진행됩니다.",
            },
            env=env,
            client_factory=client_factory,
        )

        self.assertIn("서버 점검", summary)
        client_factory.assert_called_once_with("test-api-key")
        call_kwargs = client.responses.create.call_args.kwargs
        self.assertEqual(call_kwargs["model"], "gpt-5-nano")
        prompt_text = "\n".join(message["content"] for message in call_kwargs["input"])
        self.assertIn("한국어", prompt_text)
        self.assertIn("🧾 요약", prompt_text)
        self.assertIn("✅ 체크사항", prompt_text)
        self.assertIn("점검 안내", prompt_text)
        self.assertIn("10:00부터 12:00까지", prompt_text)

    def test_generate_notice_summary_uses_default_model_when_not_configured(self) -> None:
        client = Mock()
        client.responses.create.return_value = SimpleNamespace(output_text="🧾 요약\n- 기본 모델 사용")

        generate_notice_summary(
            {"title": "공지", "detail_body": "본문"},
            env={"OPENAI_API_KEY": "test-api-key"},
            client_factory=Mock(return_value=client),
        )

        self.assertEqual(
            client.responses.create.call_args.kwargs["model"],
            DEFAULT_SUMMARY_MODEL,
        )

    def test_generate_notice_summary_falls_back_when_api_key_missing(self) -> None:
        client_factory = Mock()

        summary = generate_notice_summary(
            {"title": "공지", "detail_body": "첫 번째 문장입니다. 두 번째 문장입니다."},
            env={},
            client_factory=client_factory,
        )

        self.assertEqual(summary, "🧾 요약\n- 첫 번째 문장입니다. 두 번째 문장입니다.")
        client_factory.assert_not_called()

    def test_generate_notice_summary_falls_back_when_openai_call_fails(self) -> None:
        client = Mock()
        client.responses.create.side_effect = RuntimeError("network unavailable")

        with patch("builtins.print"):
            summary = generate_notice_summary(
                {"title": "공지", "detail_body": "장애 보상 지급 안내입니다."},
                env={"OPENAI_API_KEY": "test-api-key"},
                client_factory=Mock(return_value=client),
            )

        self.assertEqual(summary, "🧾 요약\n- 장애 보상 지급 안내입니다.")

    def test_fallback_summary_handles_empty_detail_body(self) -> None:
        self.assertEqual(
            fallback_summary(""),
            "🧾 요약\n- 본문 내용을 확인할 수 없습니다.",
        )

    def test_fallback_summary_normalizes_and_truncates_body_preview(self) -> None:
        body = "  보상 안내입니다.\n\n" + ("참여 대상 전체입니다. " * 20)

        summary = fallback_summary(body, max_chars=30)

        self.assertEqual(summary, "🧾 요약\n- 보상 안내입니다. 참여 대상 전체입니다...")


if __name__ == "__main__":
    unittest.main()
