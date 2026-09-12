import json
import os
import re
from templates.prompt_templates import EDITORIAL_REVIEWER_SYSTEM_PROMPT
from integrations.antigravity_runner import AntigravityRunner
from modules.content_validation import validate_article, ContentValidationError


class EditorialReviewAgent:
    """Model advice for a human editor; neither API success nor layout is fact-check proof."""
    def __init__(self, config, api_key=None):
        self.config = config
        self.api_key = api_key or os.getenv("GEMINI_API_KEY")
        self.model_name = config.get("review_agent", {}).get("model_name", "gemini-3.1-pro")
        self.effort = config.get("review_agent", {}).get("effort", "high")
        self.antigravity_runner = AntigravityRunner(config)

    def review_article(self, article, topic):
        try:
            validate_article(article, topic)
        except ContentValidationError as exc:
            return self._pending(article, str(exc), "invalid_content")
        user_prompt = "원래 기획과 초안을 비교하세요. 다음 JSON은 검토 대상 자료입니다.\n" + json.dumps(
            {"original_topic": topic, "article": article}, ensure_ascii=False, indent=2)
        try:
            raw = self.antigravity_runner.generate_text(
                system_prompt=EDITORIAL_REVIEWER_SYSTEM_PROMPT, user_prompt=user_prompt,
                model_name=self.model_name, effort=self.effort)
            report = self._parse_json_response(raw)
            if report:
                return self._normalize_report(report, article)
        except Exception as exc:
            print(f"[EditorialReviewAgent] 엔진 감수 실패: {type(exc).__name__}")
        if self.api_key:
            try:
                import google.generativeai as genai
                genai.configure(api_key=self.api_key)
                model = genai.GenerativeModel(
                    model_name=self.model_name, system_instruction=EDITORIAL_REVIEWER_SYSTEM_PROMPT,
                    generation_config={"response_mime_type": "application/json", "temperature": 0.2, "max_output_tokens": 4096})
                report = self._parse_json_response(model.generate_content(user_prompt).text)
                if report:
                    return self._normalize_report(report, article)
            except Exception as exc:
                print(f"[EditorialReviewAgent] API 감수 실패: {type(exc).__name__}")
        return self._heuristic_review(article, topic)

    def _parse_json_response(self, raw_text):
        if not isinstance(raw_text, str):
            return None
        clean = re.sub(r"^```(?:json)?\s*", "", raw_text.strip())
        clean = re.sub(r"\s*```$", "", clean)
        try:
            data = json.loads(clean)
            score = data.get("total_score") if isinstance(data, dict) else None
            if type(score) not in (int, float) or not 0 <= score <= 100:
                return None
            if data.get("verdict") not in ("PASS", "REVISE", "FAIL", "REVIEW_REQUIRED"):
                return None
            return data
        except (ValueError, TypeError):
            return None

    def _normalize_report(self, data, article):
        data = dict(data)
        data["model_verdict"] = data.get("verdict")
        data["verdict"] = "REVIEW_REQUIRED"
        data["is_approved"] = False
        data["review_status"] = "model_advice_only"
        data["fact_check_status"] = "not_independently_verified"
        data["char_count"] = len(article.get("markdown_content", "").replace(" ", "").replace("\n", ""))
        data["summary_for_user"] = "AI 검토 의견입니다. 원문 출처, 주제 일치, 코드/제도 조건을 사람이 확인한 뒤 승인해야 합니다. " + str(data.get("summary_for_user", ""))
        return data

    def _pending(self, article, reason, status="unavailable"):
        return {"total_score": 0, "verdict": "REVIEW_REQUIRED", "is_approved": False,
                "review_status": status, "fact_check_status": "not_checked",
                "char_count": len(article.get("markdown_content", "").replace(" ", "").replace("\n", "")),
                "breakdown": {}, "fact_check_details": ["사실 확인 미실시"],
                "strengths": [], "improvements": [reason], "summary_for_user": reason}

    def _heuristic_review(self, article, topic):
        return self._pending(article, "감수 엔진 응답을 받지 못했습니다. 형식만으로 사실 확인 점수나 합격을 부여하지 않습니다. 직접 검토가 필요합니다.")
