import os
import json
import re
from templates.prompt_templates import CONTENT_WRITER_SYSTEM_PROMPT
from integrations.antigravity_runner import AntigravityRunner
from modules.content_validation import validate_article, ContentValidationError


class ContentGenerationError(RuntimeError):
    """No publishable draft was returned; do not substitute a shared article."""


class ContentWriter:
    def __init__(self, config, api_key=None):
        self.config = config
        self.api_key = api_key or os.getenv("GEMINI_API_KEY")
        self.model_name = config.get("agent", {}).get("model_name", "gemini-2.5-flash")
        self.antigravity_runner = AntigravityRunner(config)

    def _parse_article(self, raw):
        if not isinstance(raw, str) or not raw.strip():
            return None
        clean = re.sub(r"^```(?:json)?\s*", "", raw.strip())
        clean = re.sub(r"\s*```$", "", clean)
        try:
            data = validate_article(json.loads(clean))
        except (ValueError, TypeError):
            return None
        # The producer cannot authorize its own publication.
        data.pop("human_approved", None)
        data["generation_status"] = "draft"
        data["requires_human_review"] = True
        return data

    def write_article(self, topic):
        if not isinstance(topic, dict) or not str(topic.get("title", "")).strip():
            raise ContentGenerationError("기획 제목이 없습니다. 주제를 먼저 지정하세요.")
        user_prompt = (
            "다음 기획 JSON의 원래 제목, 검색 의도, 자료 범위에 맞는 초안을 작성하세요. "
            "다른 주제의 공통 본문으로 대체하지 마세요. sources는 제공된 자료일 뿐 검증 완료가 아닙니다. "
            "필요한 근거가 없으면 확인 필요 사항을 명시하고 제도 금액/치료법/실험 결과를 추정하지 마세요.\n"
            + json.dumps(topic, ensure_ascii=False, indent=2)
        )
        try:
            raw = self.antigravity_runner.generate_text(
                system_prompt=CONTENT_WRITER_SYSTEM_PROMPT, user_prompt=user_prompt)
            article = self._parse_article(raw)
            if article:
                return article
        except Exception as exc:
            print(f"[ContentWriter] 엔진 응답 실패: {type(exc).__name__}")
        if self.api_key:
            try:
                import google.generativeai as genai
                genai.configure(api_key=self.api_key)
                model = genai.GenerativeModel(
                    model_name=self.model_name, system_instruction=CONTENT_WRITER_SYSTEM_PROMPT,
                    generation_config={"response_mime_type": "application/json", "temperature": 0.4, "max_output_tokens": 8192})
                article = self._parse_article(model.generate_content(user_prompt).text)
                if article:
                    return article
            except Exception as exc:
                print(f"[ContentWriter] API 응답 실패: {type(exc).__name__}")
        raise ContentGenerationError("본문 생성 실패: 유효한 주제별 초안을 받지 못했습니다. 발행하지 않고 재시도/검토가 필요합니다.")
