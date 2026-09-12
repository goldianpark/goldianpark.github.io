"""Offline behavior tests for generation, review, queue, and publication boundaries."""
import asyncio
import importlib
import json
import os
from pathlib import Path
import subprocess
import tempfile
import unittest
from unittest.mock import AsyncMock, Mock, patch, mock_open

from agents.content_writer import ContentWriter, ContentGenerationError
from agents.editorial_reviewer import EditorialReviewAgent
from agents.policy_inspector import PolicyInspector
from integrations.github_publisher import GitHubPublisher
from modules.content_validation import ContentValidationError, validate_article
from modules.draft_queue import DraftApprovalQueue
import main_pipeline as pipeline


def article(**changes):
    result = {"title": "FastAPI 요청 검증", "description": "입력 검증 오류를 확인하는 예제", "category": "개발 & 테크",
              "tags": ["FastAPI"], "markdown_content": "## 요청 검증\nFastAPI 예제의 입력과 오류 응답을 구분합니다.\n\n실행 환경과 결과는 검토자가 확인해야 합니다.", "faqs": []}
    result.update(changes)
    return result


class EditorialSafetyTests(unittest.TestCase):
    def setUp(self):
        self.temp = tempfile.TemporaryDirectory()
        self.addCleanup(self.temp.cleanup)
        self.directory = Path(self.temp.name)
        self.config = {"github": {"repo_root": str(self.directory), "blog_content_dir": str(self.directory / "blog"),
                                  "auto_git_commit": False, "auto_git_push": False}, "telegram": {"enabled": False}}
        self.queue = DraftApprovalQueue(str(self.directory / "drafts.json"))
        self.topic = {"title": "임플란트 재수술 때 확인할 질문", "target_keyword": "임플란트 재수술", "key_points": ["보험 적용 조건을 확인할 곳"]}
        self.environment = patch.dict(os.environ, {}, clear=True)
        self.environment.start()
        self.addCleanup(self.environment.stop)
        # A missing stub must fail the test rather than contact an external endpoint.
        self.network = patch("requests.sessions.Session.request", side_effect=AssertionError("network disabled in offline tests"))
        self.network.start()
        self.addCleanup(self.network.stop)

    def test_writer_failure_never_substitutes_article(self):
        with patch("agents.content_writer.AntigravityRunner") as engine:
            for raw in (None, "not JSON", '[]', '{"markdown_content":"text"}'):
                engine.return_value.generate_text.return_value = raw
                with self.assertRaises(ContentGenerationError):
                    ContentWriter(self.config).write_article(self.topic)
        self.assertFalse((self.directory / "blog").exists())

    def test_valid_writer_output_remains_unapproved_draft(self):
        with patch("agents.content_writer.AntigravityRunner") as engine:
            engine.return_value.generate_text.return_value = json.dumps(article(human_approved=True))
            result = ContentWriter(self.config).write_article(self.topic)
            self.assertNotIn("human_approved", result)
            self.assertTrue(result["requires_human_review"])
            self.assertEqual(result["generation_status"], "draft")
            self.assertIn("임플란트 재수술", engine.return_value.generate_text.call_args.kwargs["user_prompt"])

    def test_failed_direct_api_cannot_publish_fallback(self):
        fake = Mock()
        fake.GenerativeModel.side_effect = RuntimeError("upstream unavailable")
        with patch("agents.content_writer.AntigravityRunner") as engine, patch.dict("sys.modules", {"google.generativeai": fake}):
            engine.return_value.generate_text.return_value = None
            with self.assertRaises(ContentGenerationError):
                ContentWriter(self.config, api_key="test-key").write_article(self.topic)

    def test_legacy_template_and_faq_are_rejected_at_writer_parse(self):
        writer = ContentWriter(self.config)
        bad_body = "체계적인 자동화 워크플로우. 주당 최소 5~10시간 절약. 나만의 템플릿 자산화"
        self.assertIsNone(writer._parse_article(json.dumps(article(markdown_content=bad_body))))
        faq = [{"question": "구글 애드센스 승인용 글로 충분한가요?", "answer": "네, 1,500자 이상과 FAQ가 있어 승인 가이드라인에 완벽히 부합합니다."}]
        self.assertIsNone(writer._parse_article(json.dumps(article(faqs=faq))))

    def test_absence_of_blacklist_words_is_not_policy_approval(self):
        report = PolicyInspector(self.config).inspect_article(article(markdown_content="성인 건강 정보와 불법 대출 피해 예방 안내"))
        self.assertTrue(report["format_valid"])
        self.assertFalse(report["is_approved"])
        self.assertEqual(report["policy_risk"], "Unknown")
        self.assertEqual(report["fact_check_status"], "not_checked")

    def test_review_unavailable_never_awards_fact_score(self):
        with patch("agents.editorial_reviewer.AntigravityRunner") as engine:
            engine.return_value.generate_text.return_value = None
            result = EditorialReviewAgent(self.config).review_article(article(), self.topic)
        self.assertFalse(result["is_approved"])
        self.assertEqual(result["review_status"], "unavailable")
        self.assertEqual(result["breakdown"], {})
        self.assertEqual(result["fact_check_status"], "not_checked")

    def test_model_pass_remains_advice_and_sees_original_topic(self):
        with patch("agents.editorial_reviewer.AntigravityRunner") as engine:
            engine.return_value.generate_text.return_value = '{"total_score":99,"verdict":"PASS"}'
            result = EditorialReviewAgent(self.config).review_article(article(), self.topic)
            prompt = engine.return_value.generate_text.call_args.kwargs["user_prompt"]
        self.assertIn("임플란트 재수술", prompt)
        self.assertIn("FastAPI", prompt)
        self.assertFalse(result["is_approved"])
        self.assertEqual(result["model_verdict"], "PASS")
        self.assertEqual(result["verdict"], "REVIEW_REQUIRED")

    def test_malformed_review_is_not_normalized_to_default_pass(self):
        reviewer = EditorialReviewAgent(self.config)
        for value in ('{"total_score":"high"}', '{"total_score":true,"verdict":"PASS"}', '{"total_score":NaN,"verdict":"PASS"}', '{"total_score":99}'):
            self.assertIsNone(reviewer._parse_json_response(value))

    def test_auto_approve_only_queues_concrete_article(self):
        with patch.object(pipeline, "KeywordHarvester") as harvester, patch.object(pipeline, "ContentWriter") as writer, patch.object(pipeline, "EditorialReviewAgent") as reviewer, patch.object(pipeline, "DraftApprovalQueue", return_value=self.queue), patch.object(pipeline, "TelegramNotifier"), patch.object(pipeline, "publish_queued_draft") as publish:
            harvester.return_value.harvest_ideas.return_value = [self.topic]
            writer.return_value.write_article.return_value = article()
            reviewer.return_value.review_article.return_value = {"total_score":99, "verdict":"PASS"}
            pipeline.run_auto_pipeline(self.config, auto_approve=True)
            publish.assert_not_called()
        self.assertEqual(self.queue.list_all()[0]["status"], "pending_review")

    def test_generation_failure_in_pipeline_leaves_no_queue_or_publication(self):
        with patch.object(pipeline, "KeywordHarvester") as harvester, patch.object(pipeline, "ContentWriter") as writer, patch.object(pipeline, "DraftApprovalQueue", return_value=self.queue), patch.object(pipeline, "TelegramNotifier"), patch.object(pipeline, "publish_queued_draft") as publish:
            harvester.return_value.harvest_ideas.return_value = [self.topic]
            writer.return_value.write_article.side_effect = ContentGenerationError("failed")
            with self.assertRaises(ContentGenerationError):
                pipeline.run_auto_pipeline(self.config, auto_approve=True)
            publish.assert_not_called()
        self.assertEqual(self.queue.list_all(), [])

    def test_old_pending_bad_faq_cannot_be_approved(self):
        bad = article(faqs=[{"question":"애드센스 승인?", "answer":"네, 가이드라인에 완벽히 부합합니다."}])
        draft_id = self.queue.add_draft(bad, {"total_score":99})
        with patch.object(pipeline, "DraftApprovalQueue", return_value=self.queue), patch.object(pipeline, "GitHubPublisher") as publisher:
            success, reason = pipeline.publish_queued_draft(self.config, draft_id, human_approved=True)
            publisher.assert_not_called()
        self.assertFalse(success)
        self.assertIn("FAQ", reason)
        self.assertEqual(self.queue.get_draft(draft_id)["status"], "pending_review")

    def test_explicit_approval_is_required_and_rejected_drafts_stay_rejected(self):
        draft_id = self.queue.add_draft(article(), {"total_score":99})
        with patch.object(pipeline, "DraftApprovalQueue", return_value=self.queue), patch.object(pipeline, "GitHubPublisher") as publisher:
            self.assertFalse(pipeline.publish_queued_draft(self.config, draft_id)[0])
            self.queue.mark_rejected(draft_id)
            self.assertFalse(pipeline.publish_queued_draft(self.config, draft_id, human_approved=True)[0])
            publisher.assert_not_called()

    def test_publication_failure_is_not_marked_published(self):
        draft_id = self.queue.add_draft(article(), {"total_score":0})
        with patch.object(pipeline, "DraftApprovalQueue", return_value=self.queue), patch.object(pipeline, "GitHubPublisher") as publisher, patch.object(pipeline, "GoogleIndexing") as indexer, patch.object(pipeline, "TelegramNotifier") as notifier:
            publisher.return_value.publish_article.side_effect = RuntimeError("push failed")
            result = pipeline.publish_queued_draft(self.config, draft_id, human_approved=True)
            indexer.return_value.ping_sitemap.assert_not_called()
            notifier.return_value.send_article_published.assert_not_called()
        self.assertFalse(result[0])
        self.assertNotEqual(self.queue.get_draft(draft_id)["status"], "published")

    def test_human_can_publish_review_unavailable_draft_after_own_review(self):
        draft_id = self.queue.add_draft(article(), {"total_score":0, "verdict":"REVIEW_REQUIRED"})
        with patch.object(pipeline, "DraftApprovalQueue", return_value=self.queue), patch.object(pipeline, "GoogleIndexing"), patch.object(pipeline, "TelegramNotifier"):
            success, _ = pipeline.publish_queued_draft(self.config, draft_id, human_approved=True)
        self.assertTrue(success)
        self.assertEqual(self.queue.get_draft(draft_id)["status"], "published")
        self.assertEqual(len(list((self.directory / "blog").glob("*.md"))), 1)

    def test_publisher_requires_human_and_prevents_title_only_duplicate(self):
        publisher = GitHubPublisher(self.config)
        with self.assertRaises(PermissionError):
            publisher.publish_article(article(human_approved=True))
        first = publisher.publish_article(article(), human_approved=True)
        with self.assertRaises(ContentValidationError):
            publisher.publish_article(article(title="완전히 다른 제목"), human_approved=True)
        self.assertTrue(Path(first).exists())

    def test_existing_update_checks_faq_and_preserves_publication_date(self):
        publisher = GitHubPublisher(self.config)
        first = Path(publisher.publish_article(article(pubDate="2020-01-02"), human_approved=True))
        bad = article(faqs=[{"question":"애드센스 승인?", "answer":"승인 100%를 보장합니다."}])
        original = first.read_text()
        with self.assertRaises(ContentValidationError):
            publisher.update_existing_article(first.stem, bad, human_approved=True)
        self.assertEqual(first.read_text(), original)
        publisher.update_existing_article(first.stem, article(markdown_content="새 본문. 주제에 맞는 질문입니다."), human_approved=True)
        self.assertIn("2020-01-02", first.read_text())

    def test_approved_held_article_preserves_optional_fields_and_clears_hold(self):
        import yaml
        publisher = GitHubPublisher(self.config)
        original = Path(publisher.publish_article(article(heroImage="/images/before.png", summaryCards=[{"badge":"before", "title":"before", "desc":"old"}]), human_approved=True))
        meta, body = publisher._read_post(original)
        meta.update({"draft": True, "reviewStatus": "on_hold", "reviewReason": "needs revision", "customExisting": "keep"})
        original.write_text("---\n" + yaml.safe_dump(meta, allow_unicode=True) + "---\n" + body)
        revised = article(markdown_content="주제별로 고친 본문", heroImage="/images/after.png", summaryCards=[{"badge":"after", "title":"after", "desc":"new"}])
        publisher.update_existing_article(original.stem, revised, human_approved=True)
        meta, _ = publisher._read_post(original)
        self.assertEqual(meta["heroImage"], "/images/after.png")
        self.assertEqual(meta["summaryCards"], revised["summaryCards"])
        self.assertEqual(meta["customExisting"], "keep")
        self.assertIn("updatedDate", meta)
        self.assertNotIn("reviewStatus", meta)
        self.assertNotIn("reviewReason", meta)
        self.assertFalse(meta["draft"])

    def test_keyword_queue_maps_slug_and_keeps_complete_health_topic(self):
        from agents.keyword_harvester import KeywordHarvester
        data = "keyword,category,status\n대상포진 예방접종 지원,시니어 건강 & 일상,ready\n"
        harvester = KeywordHarvester({"content":{"categories":[{"slug":"health", "name":"시니어 건강 & 일상"}]}})
        with patch("agents.keyword_harvester.os.path.exists", return_value=True), patch("builtins.open", mock_open(read_data=data)):
            topic = harvester.harvest_from_csv_queue("health")
        self.assertEqual(topic["target_keyword"], "대상포진 예방접종 지원")
        self.assertEqual(topic["category"], "시니어 건강 & 일상")
        self.assertEqual(topic["key_points"], [])
        self.assertNotIn("고단가수익", topic["tags"])

    def test_missing_weekly_sources_do_not_invent_news(self):
        from agents.geeknews_harvester import GeekNewsHarvester
        harvester = GeekNewsHarvester(self.config)
        with patch.object(harvester, "fetch_weekly_articles", return_value=[]), patch.object(harvester.runner, "generate_text") as generate:
            with self.assertRaises(RuntimeError):
                harvester.harvest_weekly_briefing_topic()
            generate.assert_not_called()

    def test_git_push_failure_propagates(self):
        config = {**self.config, "github": {**self.config["github"], "auto_git_commit":True, "auto_git_push":True}}
        result = Mock(returncode=0)
        changed = Mock(returncode=1)
        with patch("integrations.github_publisher.subprocess.run", side_effect=[result, changed, result, subprocess.CalledProcessError(1,"push")]) as git:
            with self.assertRaises(subprocess.CalledProcessError):
                GitHubPublisher(config).publish_article(article(), human_approved=True)
        self.assertEqual(git.call_args.args[0][:3], ["git", "push", "origin"])

    def test_queue_persistence_failure_is_not_reported_as_success(self):
        with patch.object(self.queue, "_save_data", return_value=False):
            with self.assertRaises(OSError):
                self.queue.add_draft(article(), {"total_score":0})

    def test_daily_news_is_queued_not_written_to_public_content(self):
        import daily_trend_generator as daily
        with patch.object(daily, "GoogleNewsCrawler") as crawler, patch.object(daily, "load_config", return_value=self.config), patch.object(daily, "ContentWriter") as writer, patch.object(daily, "EditorialReviewAgent") as reviewer, patch.object(daily, "DraftApprovalQueue", return_value=self.queue):
            crawler.return_value.fetch_top_news.return_value = [{"title":"출처 제목", "summary":"참고 요약", "url":"https://example.org"}]
            writer.return_value.write_article.return_value = article()
            reviewer.return_value.review_article.return_value = {"total_score":0}
            draft_id = daily.generate_trend_post("FastAPI")
        self.assertEqual(self.queue.get_draft(draft_id)["status"], "pending_review")
        self.assertFalse((self.directory / "blog").exists())

    def test_weekly_news_is_queued_even_with_model_pass(self):
        with patch("agents.geeknews_harvester.GeekNewsHarvester") as harvester, patch.object(pipeline, "ContentWriter") as writer, patch.object(pipeline, "EditorialReviewAgent") as reviewer, patch.object(pipeline, "DraftApprovalQueue", return_value=self.queue), patch.object(pipeline, "TelegramNotifier"), patch.object(pipeline, "GitHubPublisher") as publisher:
            harvester.return_value.harvest_weekly_briefing_topic.return_value = self.topic
            writer.return_value.write_article.return_value = article()
            reviewer.return_value.review_article.return_value = {"total_score":99,"verdict":"PASS"}
            draft_id = pipeline.run_geeknews_weekly_pipeline(self.config)
            publisher.assert_not_called()
        self.assertEqual(self.queue.get_draft(draft_id)["status"], "pending_review")

    def test_retired_bulk_script_has_no_import_side_effect(self):
        import batch_content_generator as bulk
        with self.assertRaises(SystemExit):
            bulk.main()
        self.assertFalse((self.directory / "blog").exists())

    def test_telegram_plan_approval_opens_draft_review_and_batch_queues(self):
        with patch.object(pipeline, "load_config", return_value=self.config), patch("integrations.telegram_bot._load_env_file"):
            daemon = importlib.import_module("telegram_daemon")
        context = Mock()
        context.bot.send_message = AsyncMock()
        daemon.sessions[1] = {"topic":self.topic}
        with patch.object(daemon, "create_article_draft", new_callable=AsyncMock) as create, patch.object(daemon, "GitHubPublisher") as publisher:
            asyncio.run(daemon.execute_publish(1, context, is_draft=False))
            create.assert_awaited_once()
            publisher.assert_not_called()
        daemon.sessions[1] = {"topics":[self.topic]}
        with patch.object(daemon, "ContentWriter") as writer, patch.object(daemon, "EditorialReviewAgent") as reviewer, patch.object(daemon, "DraftApprovalQueue", return_value=self.queue), patch.object(daemon, "TelegramNotifier"), patch.object(daemon, "GitHubPublisher") as publisher:
            writer.return_value.write_article.return_value = article()
            reviewer.return_value.review_article.return_value = {"total_score":99}
            asyncio.run(daemon.execute_batch_publish(1, context))
            publisher.assert_not_called()
        daemon.sessions.clear()
        self.assertEqual(self.queue.list_all()[0]["status"], "pending_review")


if __name__ == "__main__":
    unittest.main()
