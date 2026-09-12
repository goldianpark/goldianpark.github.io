#!/usr/bin/env python3
import os
import sys
import yaml
import argparse
from datetime import datetime

# 에이전트 및 연동 모듈 로드
from agents.keyword_harvester import KeywordHarvester
from agents.content_writer import ContentWriter, ContentGenerationError
from modules.content_validation import validate_article, ContentValidationError
from agents.editorial_reviewer import EditorialReviewAgent
from agents.policy_inspector import PolicyInspector
from agents.performance_tracker import PerformanceTracker
from modules.draft_queue import DraftApprovalQueue
from integrations.github_publisher import GitHubPublisher
from integrations.google_indexing import GoogleIndexing
from integrations.telegram_bot import TelegramNotifier

def load_config(config_path: str = "config/config.yaml") -> dict:
    abs_path = os.path.abspath(os.path.join(os.path.dirname(__file__), config_path))
    if not os.path.exists(abs_path):
        print(f"⚠️ 설정 파일을 찾을 수 없습니다: {abs_path}")
        return {}
    with open(abs_path, "r", encoding="utf-8") as f:
        return yaml.safe_load(f)

def publish_queued_draft(config: dict, draft_id: str, *, human_approved: bool = False) -> tuple:
    """
    검토 대기 큐(DraftApprovalQueue)의 특정 초안을 승인하여
    GitHub Pages에 최종 퍼블리싱하고 텔레그램 알림 및 색인 요청을 수행
    """
    queue = DraftApprovalQueue()
    draft_item = queue.get_draft(draft_id)
    if not draft_item:
        return False, f"초안 ID '{draft_id}'를 찾을 수 없습니다."
        
    if draft_item.get("status") == "published":
        existing_url = draft_item.get("published_url", "")
        return True, f"이미 발행 완료된 글입니다: {existing_url}"

    if not human_approved:
        return False, "초안 본문과 출처 검토 후 사람이 승인해야 발행할 수 있습니다."
    if draft_item.get("status") not in ("pending_review", "approved"):
        return False, "보류/반려된 초안은 발행할 수 없습니다. 수정 후 다시 검토하세요."

    article = draft_item.get("article", {})
    topic = draft_item.get("topic", {})
    review = draft_item.get("review", {})
    
    try:
        validate_article(article, topic)
    except ContentValidationError as exc:
        return False, f"발행 전 내용 점검 실패: {exc}"
    if not queue.mark_approved(draft_item["draft_id"]):
        return False, "승인 상태 저장 실패. 발행하지 않았습니다."

    publisher = GitHubPublisher(config)
    indexer = GoogleIndexing(config)
    telegram = TelegramNotifier(config)
    site_url = config.get("site", {}).get("url", "https://goldianpark.github.io").rstrip("/")
    
    existing_slug = draft_item.get("existing_slug") or article.get("existing_slug")
    try:
        if existing_slug:
            saved_path, post_slug = publisher.update_existing_article(existing_slug, article, human_approved=True)
        else:
            saved_path = publisher.publish_article(article, human_approved=True)
            post_slug = os.path.splitext(os.path.basename(saved_path))[0]
    except Exception as exc:
        return False, f"발행 실패 (승인 기록 유지): 저장소/Push 상태를 확인하세요. 이미 저장된 글은 기존 글 수정 경로로 처리해야 합니다. {type(exc).__name__}: {exc}"
    full_post_url = f"{site_url}/blog/{post_slug}/"
    
    # 큐 상태 갱신
    if not queue.mark_published(draft_item["draft_id"], post_slug, full_post_url):
        return False, "저장/Push 후 큐 갱신 실패. 저장소 상태를 확인하세요."
    
    # 키워드 CSV 업데이트
    if topic.get("_csv_keyword"):
        try:
            harvester = KeywordHarvester(config)
            harvester.mark_csv_keyword_published(topic["_csv_keyword"], post_slug)
        except Exception:
            pass

    # 색인 요청 (Sitemap Ping)
    indexer.ping_sitemap()
    
    # 텔레그램 발행 완료 알림
    inspection = {
        "score": review.get("total_score", 0),
        "char_count": review.get("char_count") or len(article.get("markdown_content", "").replace(" ", "").replace("\n", ""))
    }
    telegram.send_article_published(article, inspection, full_post_url)
    
    return True, full_post_url

def run_auto_pipeline(config: dict, auto_approve: bool = False, target_category: str = None):
    site_title = config.get("site", {}).get("title", "골든라이프(GoldenLife)")
    site_url = config.get("site", {}).get("url", "https://goldianpark.github.io")
    print("=" * 60)
    print(f"🤖 [{site_title}] 에이전트 파이프라인 가동 시작")
    print(f"📌 블로그: {site_title} ({site_url})")
    print("=" * 60)

    # 0. 모듈 초기화
    harvester = KeywordHarvester(config)
    writer = ContentWriter(config)
    reviewer = EditorialReviewAgent(config)
    queue = DraftApprovalQueue()
    telegram = TelegramNotifier(config)

    # 1단계: 키워드 발굴 & 주제 선정
    print(f"\n🔍 [1단계: 자료 수집 및 키워드 발굴] 카테고리={target_category or '전체'}")
    ideas = harvester.harvest_ideas(target_category)
    if not ideas:
        print("❌ 키워드 발굴에 실패했습니다.")
        telegram.send_health_report({"error_details": "키워드 발굴 실패"}, is_alert=True)
        return

    selected_topic = ideas[0]
    title = selected_topic.get("title", "")
    print(f"\n🎯 최종 선정된 주제: '{title}'")

    # 📲 텔레그램 알림 1: 새로운 주제 탐색 보고
    telegram.send_topic_discovered(selected_topic)

    # 2단계: 심층 아티클 작성
    print("\n✍️ [2단계: 주제별 초안 작성 중...]")
    article = writer.write_article(selected_topic)
    print(f"✅ 글 작성 완료! 제목: {article.get('title', '')}")

    # 3단계: Gemini 3.1 Pro (Thinking Effort: High) 독립 감수 에이전트 검증
    print("\n🧐 [3단계: AI 편집 의견 요청 (사실 확인 및 발행 승인 아님)]")
    review = reviewer.review_article(article, selected_topic)
    score = review.get("total_score", 0)
    verdict = review.get("verdict", "UNKNOWN")
    print(f"📊 감수 종합 결과: {score}/100점 (판정: {verdict})")

    # 4단계: 지속적 검토 대기 큐(DraftApprovalQueue)에 적재
    print("\n📥 [4단계: 지속적 검토 대기 큐(data/draft_queue.json)에 적재]")
    draft_id = queue.add_draft(article, review, topic=selected_topic)
    print(f"✅ 대기 큐 적재 완료! 초안 ID: {draft_id}")

    # 5단계: 텔레그램 감수 보고서 및 승인 요청 전송
    print("\n📲 [5단계: 텔레그램 스마트 감수 보고서 전송]")
    telegram.send_review_report(draft_id, article, review)

    # Generated articles always wait for review of the concrete draft.
    if auto_approve:
        print("⚠️ --approve 자동 승인은 지원하지 않습니다. 생성된 본문을 검토한 뒤 --publish-draft ID로 승인하세요.")
    print(f"\n⏳ 검토 대기: {draft_id}. 텔레그램에서 초안 전문/출처를 확인하고 승인하세요.")

    print("\n✨ 파이프라인 프로세스가 안전하게 완료되었습니다!")

def run_dryrun_pipeline(config: dict):
    print("=" * 60)
    print("🔍 [헬스체크 에이전트] 파이프라인 Dry-run 이상 탐지 가동 시작")
    print("=" * 60)
    telegram = TelegramNotifier(config)
    
    try:
        harvester = KeywordHarvester(config)
        writer = ContentWriter(config)
        inspector = PolicyInspector(config)
        
        # 1단계: 키워드 발굴 테스트 (API 의존성 체크)
        ideas = harvester.harvest_ideas(None)
        if not ideas:
            raise Exception("키워드 발굴 실패 (결과 없음)")
        
        selected_topic = ideas[0]
        
        # 2단계: 아티클 작성 테스트 (LLM 의존성 체크)
        article = writer.write_article(selected_topic)
        if not article or "title" not in article:
            raise Exception("아티클 생성 실패 (LLM 응답 오류)")
            
        # 3단계: 정책 검사 테스트 (코드 로직 체크)
        inspection = inspector.inspect_article(article)
        if "score" not in inspection:
            raise Exception("정책 검사(PolicyInspector) 로직 에러")
            
        print("✅ Dry-run 체크 완료: 파이프라인 전 과정(탐색->작성->검사) 정상 동작 확인.")
        
    except Exception as e:
        print(f"❌ Dry-run 이상 탐지: {e}")
        telegram.send_health_report({"error_details": f"🚨 [Dry-run 실패] 파이프라인 에러 감지: {e}"}, is_alert=True)

def run_geeknews_weekly_pipeline(config: dict):
    from agents.geeknews_harvester import GeekNewsHarvester
    topic = GeekNewsHarvester(config).harvest_weekly_briefing_topic()
    article = ContentWriter(config).write_article(topic)
    review = EditorialReviewAgent(config).review_article(article, topic)
    draft_id = DraftApprovalQueue().add_draft(article, review, topic=topic)
    TelegramNotifier(config).send_review_report(draft_id, article, review)
    print(f"GeekNews 초안 검토 대기: {draft_id}")
    return draft_id


def main():
    parser = argparse.ArgumentParser(description="골든라이프(GoldenLife) 자동화 블로그 파이프라인")
    parser.add_argument("--mode", choices=["auto", "dryrun", "geeknews_weekly", "trend", "interactive", "report", "morning_report", "evening_report", "revenue_report", "traffic_report", "health", "test_telegram"], default="auto")
    parser.add_argument("--approve", action="store_true", help="호환 옵션: 자동 발행하지 않고 검토 큐에 저장")
    parser.add_argument("--publish-draft", type=str, default=None, help="대기 큐의 특정 draft_id 즉시 승인 및 배포")
    parser.add_argument("--list-queue", action="store_true", help="대기 큐 목록 조회")
    parser.add_argument("--category", type=str, default=None, help="특정 카테고리 지정")
    args = parser.parse_args()

    config = load_config()
    telegram = TelegramNotifier(config)
    tracker = PerformanceTracker(config)

    if args.list_queue:
        queue = DraftApprovalQueue()
        pending = queue.list_pending()
        print(f"\n📋 [대기 중인 초안 큐 ({len(pending)}건)]")
        for d in pending:
            print(f"  • [{d['draft_id']}] ({d['created_at']}) {d['title']} - {d['review'].get('total_score')}점 ({d['review'].get('verdict')})")
        return

    if args.publish_draft:
        success, res = publish_queued_draft(config, args.publish_draft, human_approved=True)
        if success:
            print(f"🎉 성공적으로 발행되었습니다: {res}")
        else:
            print(f"❌ 발행 실패: {res}")
        return

    if args.mode == "auto":
        run_auto_pipeline(config, auto_approve=args.approve, target_category=args.category)
        
    elif args.mode == "geeknews_weekly":
        run_geeknews_weekly_pipeline(config)

    elif args.mode == "dryrun":
        run_dryrun_pipeline(config)

    elif args.mode == "trend":
        import subprocess
        print("📰 [최신 트렌드 RAG 자동 포스팅] 시작...")
        try:
            # daily_trend_generator.py 실행
            script_path = os.path.join(os.path.dirname(__file__), "daily_trend_generator.py")
            subprocess.run([sys.executable, script_path], check=True)
            print("✨ 트렌드 기반 포스팅이 생성되었습니다.")
        except subprocess.CalledProcessError as e:
            print(f"❌ 트렌드 스크립트 실행 실패: {e}")
            telegram.send_health_report({"error_details": f"daily_trend_generator.py 실행 실패: {e}"}, is_alert=True)

    elif args.mode == "morning_report":
        # 매일 아침 08:00 KST
        stats = tracker.get_site_statistics()
        print("🌅 [일일 아침 사이트 현황 보고 (08:00)] 전송 중...")
        telegram.send_daily_site_status("morning", stats)

    elif args.mode == "evening_report":
        # 매일 저녁 19:00 KST (오늘 클릭/뷰 트래픽 카운트 보고)
        stats = tracker.get_site_statistics()
        traffic = tracker.get_click_view_statistics()
        print("🌆 [일일 저녁 사이트 현황 및 오늘 클릭/뷰 트래픽 보고 (19:00)] 전송 중...")
        telegram.send_daily_site_status("evening", stats)
        telegram.send_click_view_daily_report(traffic)

    elif args.mode in ["revenue_report", "traffic_report"]:
        # 오늘 클릭 및 페이지뷰(PV/UV) 카운트 보고
        traffic = tracker.get_click_view_statistics()
        print("📈 [오늘 클릭/뷰 트래픽 현황 보고] 전송 중...")
        telegram.send_click_view_daily_report(traffic)

    elif args.mode == "health":
        health = tracker.get_system_health()
        print("🍓 [시스템 헬스 보고] 전송 중...")
        telegram.send_health_report(health)

    elif args.mode == "report":
        stats = tracker.get_site_statistics()
        traffic = tracker.get_click_view_statistics()
        telegram.send_daily_site_status("evening", stats)
        telegram.send_click_view_daily_report(traffic)

    elif args.mode == "test_telegram":
        print("📲 [텔레그램 5종 알림 테스트 발송 시작]...")
        sample_topic = {
            "title": "2026년 파이썬 업무 자동화로 매일 2시간 아끼는 법",
            "category": "개발 & 테크",
            "target_keyword": "파이썬 업무자동화",
            "tags": ["파이썬", "업무자동화", "생산성"],
            "key_points": ["반복 엑셀 취합 자동화", "텔레그램 알림 봇 연동", "라즈베리파이 24시간 스케줄러"]
        }
        telegram.send_topic_discovered(sample_topic)

        sample_article = {
            "title": "2026년 파이썬 업무 자동화로 매일 2시간 아끼는 법",
            "category": "개발 & 테크",
            "readingTime": "7 min read",
            "faqs": [{"question": "비전공자도 가능한가요?", "answer": "네, 가능합니다."}]
        }
        sample_inspection = {"score": 95, "char_count": 1850}
        telegram.send_article_published(sample_article, sample_inspection, "https://absianp.github.io/blog/2026-python-automation-routines/")

        stats = tracker.get_site_statistics()
        telegram.send_daily_site_status("morning", stats)
        telegram.send_daily_site_status("evening", stats)

        revenue = tracker.get_adsense_statistics()
        telegram.send_adsense_daily_report(revenue)

        health = tracker.get_system_health()
        telegram.send_health_report(health)
        print("✨ 5종 텔레그램 알림 테스트 전송 완료!")

if __name__ == "__main__":
    main()
