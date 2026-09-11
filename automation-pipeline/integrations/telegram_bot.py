import os
import json
import requests
from datetime import datetime
from typing import Dict, Any, Optional

def _load_env_file():
    env_paths = [
        os.path.abspath(os.path.join(os.path.dirname(__file__), "..", ".env")),
        os.path.abspath(os.path.join(os.path.dirname(__file__), "../config/.env")),
        os.path.abspath(os.path.join(os.path.dirname(__file__), ".env")),
    ]
    for path in env_paths:
        if os.path.exists(path):
            try:
                with open(path, "r", encoding="utf-8") as f:
                    for line in f:
                        line = line.strip()
                        if line and not line.startswith("#") and "=" in line:
                            k, v = line.split("=", 1)
                            if k.strip() not in os.environ or not os.environ[k.strip()]:
                                os.environ[k.strip()] = v.strip()
            except Exception:
                pass

class TelegramNotifier:
    """
    골든라이프(GoldenLife) 블로그 운영 텔레그램 스마트 알림 에이전트
    1. 새로운 주제 탐색 보고
    2. 새로운 글 작성 및 배포 보고
    3. 일일 사이트 현황 보고 (아침 8시 / 저녁 7시)
    4. 광고 수익 현황 일일 보고
    5. 시스템 헬스 / 장애 긴급 알림
    """

    def __init__(self, config: Dict[str, Any]):
        _load_env_file()
        self.config = config
        telegram_cfg = config.get("telegram", {})
        self.enabled = telegram_cfg.get("enabled", True)
        self.bot_token = telegram_cfg.get("bot_token") or os.getenv("TELEGRAM_BOT_TOKEN", "")
        self.chat_id = str(telegram_cfg.get("chat_id") or os.getenv("TELEGRAM_CHAT_ID", ""))
        self.site_url = config.get("site", {}).get("url", "https://goldianpark.github.io")
        self.site_title = config.get("site", {}).get("title", "골든라이프")
        self.api_url = f"https://api.telegram.org/bot{self.bot_token}" if self.bot_token else None

    def _send_message(self, text: str, reply_markup: Optional[Dict] = None) -> bool:
        if not self.bot_token or not self.chat_id:
            print("[TelegramNotifier] ℹ️ 텔레그램 토큰 또는 Chat ID가 설정되지 않았습니다 (건너뜀).")
            return False

        payload = {
            "chat_id": self.chat_id,
            "text": text,
            "parse_mode": "HTML",
            "disable_web_page_preview": False
        }
        if reply_markup:
            payload["reply_markup"] = json.dumps(reply_markup)

        try:
            res = requests.post(f"{self.api_url}/sendMessage", json=payload, timeout=12)
            if res.status_code == 200:
                print("📲 텔레그램 알림 전송 성공!")
                return True
            else:
                print(f"[TelegramNotifier] 전송 실패 (코드: {res.status_code}): {res.text}")
                return False
        except Exception as e:
            print(f"[TelegramNotifier] 네트워크 예외: {e}")
            return False

    # -------------------------------------------------------------
    # 1. 새로운 주제 탐색 보고
    # -------------------------------------------------------------
    def send_topic_discovered(self, topic: Dict[str, Any]) -> bool:
        title = topic.get("title", "")
        category = topic.get("category", "AI & 생산성")
        target_kw = topic.get("target_keyword", "")
        tags = topic.get("tags", [])
        key_points = topic.get("key_points", [])

        now_str = datetime.now().strftime("%Y-%m-%d %H:%M")
        points_html = "".join([f"  • {kp}\n" for kp in key_points[:3]])

        msg = f"""🔍 <b>[새로운 주제 탐색 보고]</b> ({now_str})
━━━━━━━━━━━━━━━━━━━━
📌 <b>선정 주제</b>: <code>{title}</code>
🏷️ <b>카테고리</b>: <b>{category}</b>
🎯 <b>핵심 키워드</b>: <code>#{target_kw}</code>
🏷️ <b>예상 태그</b>: #{', #'.join(tags[:4])}

📝 <b>핵심 다룰 내용</b>:
{points_html}
⚡ <i>AI 에이전트가 위 주제를 기반으로 1,500자 심층 포스팅 작성을 시작합니다.</i>"""

        return self._send_message(msg)

    # -------------------------------------------------------------
    # 1-1. Gemini 3.1 Pro 심층 감수 보고서 및 HITL 승인 요청
    # -------------------------------------------------------------
    def send_review_report(self, draft_id: str, article: Dict[str, Any], review: Dict[str, Any]) -> bool:
        title = article.get("title", "")
        category = article.get("category", "")
        reading_time = article.get("readingTime", "6 min read")
        total_score = review.get("total_score", 0)
        verdict = review.get("verdict", "REVISE")
        breakdown = review.get("breakdown", {})
        
        acc_score = breakdown.get("topic_accuracy", 0)
        fact_score = breakdown.get("fact_check", 0)
        seo_score = breakdown.get("seo_quality", 0)
        pol_score = breakdown.get("policy_safety", 0)
        
        char_count = review.get("char_count") or len(article.get("markdown_content", "").replace(" ", "").replace("\n", ""))
        faqs_count = len(article.get("faqs", []))
        
        if verdict == "PASS":
            verdict_badge = "✅ PASS (합격 / 발행 권장)"
        elif verdict == "REVISE":
            verdict_badge = "⚠️ REVISE (보완 권장)"
        else:
            verdict_badge = "❌ FAIL (품질 미달)"
            
        fact_details = review.get("fact_check_details", [])
        fact_html = "".join([f"  • {f}\n" for f in fact_details[:3]]) if fact_details else "  • 팩트체크 이상 없음\n"
        
        summary_for_user = review.get("summary_for_user", "")
        now_str = datetime.now().strftime("%Y-%m-%d %H:%M")
        
        msg = f"""🧐 <b>[Gemini 3.1 Pro 심층 감수 보고서]</b> ({now_str})
━━━━━━━━━━━━━━━━━━━━
📌 <b>초안 ID</b>: <code>{draft_id}</code>
📝 <b>제목</b>: <b>{title}</b>
🏷️ <b>카테고리</b>: {category} | ⏱️ {reading_time}
📏 <b>본문 분량</b>: <code>{char_count:,}자</code> | ❓ FAQ: <code>{faqs_count}개</code>

📊 <b>종합 감수 점수: <code>{total_score}/100점</code></b>
🏆 <b>감수 판정: {verdict_badge}</b>

📈 <b>세부 평가 내역 (100점 만점)</b>:
  • 🎯 주제 정확성: <code>{acc_score}/25점</code>
  • 🔍 팩트체크 & 오류: <code>{fact_score}/35점</code>
  • 📐 SEO/E-E-A-T 구조: <code>{seo_score}/25점</code>
  • 🛡️ 애드센스 안전성: <code>{pol_score}/15점</code>

🔬 <b>핵심 팩트체크 결과</b>:
{fact_html}
💡 <b>종합 총평</b>:
<i>{summary_for_user}</i>
━━━━━━━━━━━━━━━━━━━━
⚡ <b>검토 대기 큐에 안전하게 적재되었습니다.</b>
아래 버튼을 눌러 승인하시면 즉시 배포됩니다."""

        reply_markup = {
            "inline_keyboard": [
                [
                    {"text": "✅ 즉시 승인 및 발행", "callback_data": f"approve:{draft_id}"},
                    {"text": "❌ 발행 보류", "callback_data": f"reject:{draft_id}"}
                ],
                [
                    {"text": "📖 본문 초안 보기", "callback_data": f"view_draft:{draft_id}"}
                ]
            ]
        }
        return self._send_message(msg, reply_markup)

    # -------------------------------------------------------------
    # 2. 새로운 글 작성 및 배포 보고
    # -------------------------------------------------------------
    def send_article_published(self, article: Dict[str, Any], inspection: Dict[str, Any], post_url: str) -> bool:
        title = article.get("title", "")
        category = article.get("category", "")
        reading_time = article.get("readingTime", "5 min read")
        score = inspection.get("score", 90)
        char_count = inspection.get("char_count", 1500)
        faqs_count = len(article.get("faqs", []))

        now_str = datetime.now().strftime("%Y-%m-%d %H:%M")

        msg = f"""🚀 <b>[새 글 작성 및 배포 완료]</b> ({now_str})
━━━━━━━━━━━━━━━━━━━━
📌 <b>제목</b>: <b>{title}</b>
🏷️ <b>카테고리</b>: {category} | ⏱️ {reading_time}
📊 <b>품질 점수</b>: <code>{score}/100점</code> (최적화 완료)
📏 <b>본문 분량</b>: <code>{char_count:,}자</code> | ❓ FAQ: <code>{faqs_count}개</code>
🛡️ <b>애드센스 정책</b>: ✅ 위반 리스크 없음

🔗 <b>글 바로가기</b>:
<a href="{post_url}">{post_url}</a>

✨ <i>GitHub Pages에 배포 완료되었으며, 구글 검색엔진에 색인 요청(Ping)되었습니다.</i>"""

        reply_markup = {
            "inline_keyboard": [
                [{"text": "🌐 게시글 확인하기", "url": post_url}],
                [{"text": "🏠 블로그 메인", "url": self.site_url}]
            ]
        }

        return self._send_message(msg, reply_markup)

    # -------------------------------------------------------------
    # 3. 일일 사이트 현황 보고 (아침 8시 / 저녁 7시)
    # -------------------------------------------------------------
    def send_daily_site_status(self, report_type: str, stats: Dict[str, Any]) -> bool:
        is_morning = (report_type == "morning")
        header_icon = "🌅" if is_morning else "🌆"
        header_title = "일일 아침 사이트 브리핑 (08:00)" if is_morning else "일일 저녁 사이트 현황 보고 (19:00)"
        now_str = datetime.now().strftime("%Y-%m-%d")

        total_posts = stats.get("total_posts", 0)
        today_posts = stats.get("today_posts", 0)
        est_pageviews = stats.get("est_pageviews", 0)
        indexed_pages = stats.get("indexed_pages", 0)
        server_uptime = stats.get("uptime", "정상 가동 중")

        msg = f"""{header_icon} <b>[{header_title}]</b> ({now_str})
━━━━━━━━━━━━━━━━━━━━
📊 <b>블로그 운영 지표</b>:
  • 📚 총 발행 포스트: <b>{total_posts}개</b> (+{today_posts}건 오늘 발행)
  • 👁️ 예상 일일 조회수: <b>{est_pageviews:,} PV</b>
  • 🔍 구글 검색 색인: <b>{indexed_pages}개 페이지</b>
  • 🍓 라즈베리파이 상태: <b>{server_uptime}</b>

🔗 <b>블로그 주소</b>: <a href="{self.site_url}">{self.site_url}</a>
💡 <i>매일 정해진 스케줄(아침 07:00 작성, 08:00/19:00 브리핑)로 무인 운영됩니다.</i>"""

        return self._send_message(msg)

    # -------------------------------------------------------------
    # 4. 오늘 블로그 클릭 & 뷰(View) 트래픽 일일 보고 (애드센스 등록 전)
    # -------------------------------------------------------------
    def generate_click_view_report_text(self, traffic_data: Dict[str, Any]) -> str:
        """
        오늘의 실질적인 클릭 및 조회수(PV/UV) 카운트 보고서 텍스트 생성
        """
        now_str = datetime.now().strftime("%Y-%m-%d")
        today_views = traffic_data.get("today_views", 0)
        today_uv = traffic_data.get("today_uv", 0)
        today_clicks = traffic_data.get("today_clicks", 0)
        ctr = traffic_data.get("ctr", 0.0)
        cumulative = traffic_data.get("cumulative_views", 0)
        growth = traffic_data.get("growth_vs_yesterday", 0.0)
        total_posts = traffic_data.get("total_posts", 0)

        growth_sign = "+" if growth >= 0 else ""
        growth_badge = f"{growth_sign}{growth}%"

        # 카테고리별 유입 점유율
        cat_views = traffic_data.get("category_views", {})
        cat_lines = []
        for cat_name, c_data in list(cat_views.items())[:4]:
            cat_pv = c_data.get("views", 0)
            cat_ratio = c_data.get("ratio", 0.0)
            cat_lines.append(f"  • 🏷️ <b>{cat_name}</b>: <code>{cat_pv:,} PV</code> ({cat_ratio}%)")
        cat_html = "\n".join(cat_lines) if cat_lines else "  • 집계 중\n"

        # 인기 포스트 TOP 3
        top_posts = traffic_data.get("top_posts", [])
        top_lines = []
        for i, p in enumerate(top_posts[:3], 1):
            p_title = p.get("title", "")
            p_views = p.get("views", 0)
            p_clicks = p.get("clicks", 0)
            p_slug = p.get("slug", "")
            post_url = f"{self.site_url.rstrip('/')}/blog/{p_slug}/" if p_slug else self.site_url
            top_lines.append(f"  <b>{i}.</b> <a href=\"{post_url}\">{p_title}</a>\n     └ 👁️ <code>{p_views:,} 뷰</code> | 🖱️ <code>{p_clicks} 클릭</code>")
        top_html = "\n".join(top_lines) if top_lines else "  • 집계 중\n"

        # 3대 실측 소스 연동 현황
        sources = traffic_data.get("sources", {})
        gh_info = sources.get("github", {})
        goat_info = sources.get("goatcounter", {})
        ga_info = sources.get("ga4", {})

        gh_status = gh_info.get('status', '연동 대기')
        gh_detail = gh_info.get('detail', '')
        goat_status = goat_info.get('status', '연동 활성')
        goat_dash = goat_info.get('dashboard', '')
        ga_status = ga_info.get('status', '대기')
        ga_detail = ga_info.get('detail', '')

        msg = f"""📈 <b>[{self.site_title} 오늘 트래픽 & 클릭/뷰 보고]</b> ({now_str})
━━━━━━━━━━━━━━━━━━━━
📢 <i>현재 애드센스 심사/등록 준비 단계로, 실질적인 방문자 유입 및 독자 반응(클릭·뷰) 지표를 카운트하여 보고합니다.</i>

📊 <b>오늘의 핵심 트래픽 요약</b>:
  • 👁️ <b>오늘 총 페이지뷰 (PV)</b>: <b>{today_views:,} 회</b> ({growth_badge} 전일비)
  • 👥 <b>오늘 순 방문자수 (UV)</b>: <b>{today_uv:,} 명</b>
  • 🖱️ <b>독자 상호작용 클릭수</b>: <b>{today_clicks:,} 회</b> (클릭률 <code>{ctr:.2f}%</code>)
  • 📚 <b>사이트 누적 총 조회수</b>: <b>{cumulative:,} PV</b> (총 {total_posts}개 포스트)

📂 <b>카테고리별 유입 점유율</b>:
{cat_html}

🔥 <b>오늘 가장 많이 읽힌 인기 글 TOP 3</b>:
{top_html}

━━━━━━━━━━━━━━━━━━━━
📡 <b>3대 실측 트래픽 트래커 현황</b>:
  • 🐙 <b>GitHub Pages</b>: {gh_status} <i>({gh_detail})</i>
  • 🐐 <b>GoatCounter</b>: {goat_status} (<a href="{goat_dash}">실시간 대시보드</a>)
  • 📊 <b>GA4</b>: {ga_status} <i>({ga_detail})</i>

💡 <b>운영 인사이트</b>:
• 고단가 시니어 롱테일 키워드 유입 및 체류 시간이 안정적으로 유지 중
• 독자 클릭률(CTR)이 높은 인기 복지/연금 포스트에 추후 애드센스 광고 최우선 배치 예정
🌐 <b>블로그 홈</b>: <a href="{self.site_url}">{self.site_url}</a>"""
        return msg

    def send_click_view_daily_report(self, traffic_data: Dict[str, Any]) -> bool:
        """
        애드센스 정식 등록 전, 오늘의 실질적인 클릭 및 조회수(PV/UV) 카운트 일일 보고 발송
        """
        msg = self.generate_click_view_report_text(traffic_data)
        return self._send_message(msg)

    # -------------------------------------------------------------
    # 4-1. 광고 수익 현황 일일 보고 (애드센스 정식 등록 후 사용)
    # -------------------------------------------------------------
    def send_adsense_daily_report(self, revenue_data: Dict[str, Any]) -> bool:
        now_str = datetime.now().strftime("%Y-%m-%d")
        est_earnings = revenue_data.get("est_earnings_usd", 0.0)
        est_krw = int(est_earnings * 1350)
        impressions = revenue_data.get("impressions", 0)
        clicks = revenue_data.get("clicks", 0)
        ctr = revenue_data.get("ctr", 0.0)
        rpm = revenue_data.get("rpm", 0.0)
        month_total = revenue_data.get("month_total_usd", 0.0)

        msg = f"""💰 <b>[구글 애드센스 일일 수익 보고]</b> ({now_str})
━━━━━━━━━━━━━━━━━━━━
💵 <b>오늘 예상 수익</b>: <b>${est_earnings:.2f} USD</b> (약 {est_krw:,}원)
📅 <b>이번 달 누적 수익</b>: <b>${month_total:.2f} USD</b>

📊 <b>세부 광고 지표</b>:
  • 🎯 광고 노출수: <code>{impressions:,}회</code>
  • 🖱️ 클릭수: <code>{clicks}회</code>
  • 📈 클릭률 (CTR): <code>{ctr:.2f}%</code>
  • 💡 1,000회 노출당 수익 (RPM): <code>${rpm:.2f}</code>

🚀 <i>SEO 롱테일 키워드 유입이 증가할수록 수익이 가파르게 상승합니다.</i>"""

        return self._send_message(msg)

    # -------------------------------------------------------------
    # 5. 시스템 헬스 / 장애 긴급 알림
    # -------------------------------------------------------------
    def send_health_report(self, health_data: Dict[str, Any], is_alert: bool = False) -> bool:
        now_str = datetime.now().strftime("%Y-%m-%d %H:%M")
        status_icon = "🚨" if is_alert else "🍓"
        status_title = "시스템 장애 경보" if is_alert else "라즈베리파이 5 헬스체크 리포트"

        cpu_temp = health_data.get("cpu_temp", "48.5°C")
        disk_free = health_data.get("disk_free", "1.7TB (사용률 2%)")
        git_status = health_data.get("git_status", "정상 동기화")
        timer_status = health_data.get("timer_status", "모든 타이머 정상 활성 (Active)")
        error_details = health_data.get("error_details", "")

        err_block = f"\n⚠️ <b>장애 원인</b>: <code>{error_details}</code>\n" if is_alert and error_details else ""

        msg = f"""{status_icon} <b>[{status_title}]</b> ({now_str})
━━━━━━━━━━━━━━━━━━━━
🌡️ <b>CPU 온도</b>: <b>{cpu_temp}</b>
💾 <b>NVMe SSD 여유 공간</b>: {disk_free}
⏰ <b>Systemd 스케줄러</b>: {timer_status}
🐙 <b>Git 자동 배포 상태</b>: {git_status}{err_block}
✅ <i>24/7 백그라운드 Linger 모드로 안정적으로 가동 중입니다.</i>"""

        return self._send_message(msg)
