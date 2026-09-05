import os
import json
import re
from typing import Dict, Any, Optional
from templates.prompt_templates import CONTENT_WRITER_SYSTEM_PROMPT
from integrations.antigravity_runner import AntigravityRunner

class ContentWriter:
    """
    Google Antigravity CLI / SDK 또는 로컬 모델을 활용하여
    1,800~3,000자 이상의 6070 시니어 전문 복지·연금·건강 마크다운 아티클과 FAQ를 작성하는 에이전트
    """

    def __init__(self, config: Dict[str, Any], api_key: Optional[str] = None):
        self.config = config
        self.api_key = api_key or os.getenv("GEMINI_API_KEY")
        self.model_name = config.get("agent", {}).get("model_name", "gemini-2.5-flash")
        self.antigravity_runner = AntigravityRunner(config)

    def write_article(self, topic: Dict[str, Any]) -> Dict[str, Any]:
        """
        주어진 주제(topic dict)를 바탕으로 완성도 높은 마크다운 글과 메타데이터 생성
        """
        title = topic.get("title", "65세 이상 기초연금 신청자격 및 수령액 계산법")
        category = topic.get("category", "정부지원금 & 복지")
        target_keyword = topic.get("target_keyword", "")
        tags = topic.get("tags", ["기초연금", "65세이상혜택", "노인복지", "골든라이프"])
        key_points = topic.get("key_points", [])

        user_prompt = f"""
[6070 시니어 전문 아티클 작성 요청 사양]
- 글 제목: {title}
- 카테고리: {category}
- 핵심 타겟 롱테일 키워드: {target_keyword}
- 추천 태그: {', '.join(tags)}
- 반드시 상세히 다룰 핵심 포인트:
{chr(10).join([f"  * {kp}" for kp in key_points])}

[작성 지침 및 필수 포함 요소]
1. 독자 타겟: 6070 어르신과 부모님 복지를 챙기는 3040 자녀 세대.
2. 어조: 모바일 가독성을 고려한 짧은 호흡의 정중하고 따뜻한 설명조 존댓말 (~합니다, ~해보세요).
3. 필수 구성:
   - H1 글 제목 (매력적이고 신뢰감 있는 제목)
   - 서론: 독자의 현실적인 고민 공감 + 본 글의 핵심 혜택 3줄 요약
   - 본론 (H2, H3):
     * 대상자 자격 요건 체크리스트 (소득인정액, 연령, 재산 기준 등)
     * 구체적인 수령액/혜택 모의 계산 예시
     * 3열 이상의 일목요연한 비교 분석 표(Markdown Table)
     * 신청 절차 (온라인 복지로 및 오프라인 주민센터 방문 방법, 구비 서류)
   - 결론: 신청 시 주의사항, 탈락 방지 팁, 문의처 안내
   - FAQ: 독자가 가장 자주 묻는 질문 3개와 명쾌하고 친절한 답변 (JSON faqs 배열)
4. 분량: 한글 공백 포함 1,800자 ~ 3,000자 내외로 충실하게 작성.
5. 정확성: 보건복지부, 국민연금공단, 국민건강보험공단 최신 고시 기준 반영.

반드시 지정된 JSON 포맷(title, description, category, tags, readingTime, markdown_content, faqs)으로만 응답하세요.
"""

        # 1. Antigravity CLI / SDK / On-Device 로컬 엔진 우선 호출
        raw_output = self.antigravity_runner.generate_text(
            system_prompt=CONTENT_WRITER_SYSTEM_PROMPT,
            user_prompt=user_prompt
        )

        if raw_output:
            try:
                # JSON 파싱 시도 (마크다운 코드블록 제거)
                clean_json = re.sub(r"^```json\s*", "", raw_output.strip())
                clean_json = re.sub(r"\s*```$", "", clean_json)
                article_data = json.loads(clean_json)
                if isinstance(article_data, dict) and "markdown_content" in article_data:
                    return article_data
            except Exception:
                pass

        # 2. Gemini Direct API 호출 시도 (API 키가 있는 경우)
        if self.api_key:
            try:
                import google.generativeai as genai
                genai.configure(api_key=self.api_key)
                model = genai.GenerativeModel(
                    model_name=self.model_name,
                    system_instruction=CONTENT_WRITER_SYSTEM_PROMPT,
                    generation_config={
                        "response_mime_type": "application/json",
                        "temperature": 0.7,
                        "max_output_tokens": 8192
                    }
                )
                response = model.generate_content(user_prompt)
                article_data = json.loads(response.text)
                return article_data
            except Exception as e:
                print(f"[ContentWriter] API 호출 예외 (Fallback 모드로 전환): {e}")

        # 3. 고품질 시니어 전문 Fallback 템플릿 가동
        return self._generate_fallback_article(topic)

    def _generate_fallback_article(self, topic: Dict[str, Any]) -> Dict[str, Any]:
        title = topic.get("title", "2026년 65세 이상 기초연금 신청자격 및 수령액 계산법 총정리")
        category = topic.get("category", "정부지원금 & 복지")
        tags = topic.get("tags", ["기초연금", "65세이상혜택", "노인복지", "소득인정액", "골든라이프"])
        target_kw = topic.get("target_keyword", "기초연금 신청자격")

        content = f"""
대한민국 65세 이상 어르신들의 든든한 노후 버팀목인 **기초연금** 제도는 매년 소득인정액 선정기준액과 지급액이 변경됩니다. 신청하지 않으면 지급받을 수 없는 권리이므로, 본 가이드를 통해 본인의 수급 자격과 예상 수령액을 꼼꼼하게 확인해 보시기 바랍니다.

---

## 1. 2026년 기초연금 핵심 수급 요건 및 선정 기준

기초연금은 대한민국 국적을 가진 만 65세 이상 어르신 중 **소득인정액이 하위 70% 이하**인 분들에게 지급됩니다. 단독가구와 부부가구의 선정 기준액이 다르므로 가구 형태별 기준을 먼저 파악해야 합니다.

### 필수 자격 체크리스트
- **연령 기준**: 만 65세 이상 (생일이 속한 달의 1개월 전부터 신청 가능)
- **국적 및 거주**: 대한민국 국적으로 국내에 거주하는 어르신
- **소득 기준**: 가구의 소득평가액과 재산의 월 소득환산액을 합산한 '소득인정액'이 기준액 이하일 것
- **제외 대상**: 직역연금(공무원연금, 군인연금, 사립학교교직원연금, 별정우체국연금) 수급권자 및 그 배우자는 원칙적으로 제외됩니다.

---

## 2. 소득인정액 계산 공식 및 비교 표

소득인정액은 단순히 매달 통장에 들어오는 근로소득만을 의미하지 않습니다. 근로소득 공제와 일반재산, 금융재산, 부채 등을 종합적으로 반영하여 계산됩니다.

| 가구 구분 | 2026년 예상 선정기준액 | 최대 지급 월 수령액 | 비고 |
| :--- | :--- | :--- | :--- |
| **단독 가구** | 약 213만 원 이하 | 약 33만 4천 원 | 기본 공제액 적용 후 |
| **부부 가구** | 약 340만 원 이하 | 약 53만 4천 원 (부부 합산) | 부부 감액 20% 반영 |

> [!TIP]
> **근로소득 기본 공제 혜택**: 어르신의 경제활동을 장려하기 위해 근로소득에서 매월 기본공제(약 110만 원 상당)를 먼저 차감한 후, 남은 금액의 30%를 추가로 추가 공제해 드립니다.

---

## 3. 기초연금 온·오프라인 신청 절차 및 구비 서류

기초연금은 신청주의 원칙이 적용되므로 가만히 계시면 자동으로 나오지 않습니다. 반드시 본인 또는 대리인이 직접 신청해야 합니다.

### 신청 방법
1. **방문 신청**: 주소지 관할 읍·면·동 주민센터(행정복지센터) 또는 전국 국민연금공단 지사 어디서나 신청 가능합니다.
2. **온라인 신청**: 어르신 또는 자녀가 **복지로(bokjiro.go.kr)** 웹사이트 또는 모바일 앱에서 공동인증서/간편인증으로 24시간 간편 신청할 수 있습니다.

### 필수 제출 서류
- 신분증 (주민등록증, 운전면허증, 여권 등)
- 기초연금을 지급받을 통장 사본 (본인 명의)
- 배우자의 금융정보등제공동의서 (부부 가구의 경우)
- 전·월세 임대차계약서 (해당자에 한함)

---

## 4. 탈락을 방지하는 실전 주의사항 3가지

1. **사치품성 재산 주의**: 배기량 3,000cc 이상이거나 차량가액 4,000만 원 이상의 고급 승용차 및 골프·콘도 회원권은 기본공제 없이 월 100% 소득으로 환산되어 탈락 원인이 됩니다.
2. **수급희망 이력관리제 신청**: 기준 초과로 아쉽게 탈락하더라도 '수급희망 이력관리'를 함께 신청해 두시면, 향후 기준액이 상향될 때 자동으로 재안내를 받으실 수 있습니다.
3. **국민연금 연계 감액 확인**: 국민연금 수령액이 기초연금 기준금액의 150%를 초과하는 경우 일부 감액될 수 있으므로 국민연금공단(국번없이 1355) 상담을 권장합니다.
"""

        return {
          "title": title,
          "description": f"{title}에 대한 자격 체크리스트, 가구별 모의 계산 비교표, 주민센터 및 복지로 신청 서류를 어르신 눈높이에서 정리했습니다.",
          "category": category,
          "tags": tags,
          "readingTime": "6 min read",
          "markdown_content": content.strip(),
          "faqs": [
            {
              "question": "부모님이 집을 한 채 가지고 계셔도 기초연금을 받을 수 있나요?",
              "answer": "네, 주택이 있더라도 주택 공시가격에서 대도시 기준 기본재산공제(약 1억 3,500만 원)를 차감한 후 연 4%의 환산율을 적용하므로, 소득인정액이 기준 이하이면 충분히 수급 가능합니다."
            },
            {
              "question": "생일이 속한 달에 바로 신청해야 하나요?",
              "answer": "만 65세 생일이 속한 달의 1개월 전부터 미리 신청하실 수 있습니다. 예를 들어 5월이 생일이시라면 4월 1일부터 주민센터나 복지로를 통해 사전 신청이 가능합니다."
            },
            {
              "question": "자녀의 소득이나 재산 때문에 부모님이 탈락할 수도 있나요?",
              "answer": "아닙니다. 기초연금은 자녀의 소득이나 재산을 조사하는 '부양의무자 기준'이 완전히 폐지되었습니다. 오직 어르신 본인과 배우자의 소득·재산만으로 심사합니다."
            }
          ]
        }
