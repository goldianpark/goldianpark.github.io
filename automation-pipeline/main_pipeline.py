#!/usr/bin/env python3
import os
import sys
import yaml
import argparse
from datetime import datetime
from modules.generation_control import legacy_generation_allowed

# 에이전트 및 연동 모듈 로드
from agents.keyword_harvester import KeywordHarvester
from agents.content_writer import ContentWriter, ContentGenerationError
from modules.content_validation import validate_article, ContentValidationError
from agents.editorial_reviewer import EditorialReviewAgent
from agents.policy_inspector import PolicyInspector
from agents.performance_tracker import PerformanceTracker
from modules.draft_queue import DraftApprovalQueue, serialize_publication
from modules.gpt_images import prepare_article_images
from integrations.github_publisher import GitHubPublisher
from integrations.google_indexing import GoogleIndexing
from integrations.telegram_bot import TelegramNotifier

def load_config(config_path="config/config.yaml"):
    from modules.configuration import load_configuration
    return load_configuration(os.path.dirname(__file__), config_path)

@serialize_publication
def publish_queued_draft(config: dict, draft_id: str, *, human_approved: bool = False, expected_review_token=None) -> tuple:
    from modules.publication_workflow import submit
    return submit(config, draft_id, DraftApprovalQueue(), GitHubPublisher, human_approved=human_approved, expected_review_token=expected_review_token)


@serialize_publication
def reconcile_queued_draft(config: dict, draft_id: str) -> tuple:
    from modules.publication_workflow import reconcile

    def after_verified(draft, record):
        keyword = draft.get("topic", {}).get("_csv_keyword")
        if keyword:
            KeywordHarvester(config).mark_csv_keyword_published(keyword, record["slug"])

    def notify(draft, record):
        article = draft["article"]
        TelegramNotifier(config).send_article_published(article, {
            "score": draft.get("review", {}).get("total_score", 0),
            "char_count": len(article.get("markdown_content", ""))}, record["url"])

    return reconcile(config, draft_id, DraftApprovalQueue(), GitHubPublisher,
                     after_verified=after_verified, notify=notify)

def run_auto_pipeline(config: dict, auto_approve: bool = False, target_category: str = None):
    if not legacy_generation_allowed(config):
        return
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

    article = prepare_article_images(article, config)

    # 3단계: GPT (high reasoning) 독립 감수 에이전트 검증
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
    if not legacy_generation_allowed(config):
        return
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
    if not legacy_generation_allowed(config):
        return
    from agents.geeknews_harvester import GeekNewsHarvester
    topic = GeekNewsHarvester(config).harvest_weekly_briefing_topic()
    article = prepare_article_images(ContentWriter(config).write_article(topic), config)
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
    parser.add_argument("--reconcile-draft", help="승인된 초안의 Pages 및 공개 이미지 확인")
    parser.add_argument("--reconcile-all", action="store_true", help="배포 대기 중인 승인 초안 모두 확인")
    parser.add_argument("--list-queue", action="store_true", help="대기 큐 목록 조회")
    parser.add_argument("--category", type=str, default=None, help="특정 카테고리 지정")
    args = parser.parse_args()

    config = load_config()
    if args.reconcile_draft or args.reconcile_all:
        ids = [args.reconcile_draft] if args.reconcile_draft else [d["draft_id"] for d in DraftApprovalQueue().list_deployments()]
        for draft_id in ids:
            success, message = reconcile_queued_draft(config, draft_id)
            print(f"{draft_id}: {'발행 확인 완료' if success else '배포 확인 대기'}: {message}")
        return
    if not (args.publish_draft or args.list_queue) and args.mode in ("auto", "dryrun", "geeknews_weekly", "trend", "interactive"):
        if not legacy_generation_allowed(config):
            return
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
            print(f"⏳ 발행 상태: {res}")
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
