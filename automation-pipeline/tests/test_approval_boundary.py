"""Offline regression tests for Astro metadata and Telegram approval authority."""
import asyncio
from copy import deepcopy
import importlib
import os
from pathlib import Path
import tempfile
from types import SimpleNamespace
import unittest
from unittest.mock import AsyncMock, Mock, patch

from integrations.github_publisher import GitHubPublisher
from modules.content_validation import ContentValidationError, validate_article
from modules.approval_binding import issue_approval, consume_approval, invalidate_approvals
import main_pipeline


def article(**changes):
    data = {"title":"초안 A", "description":"검토할 글", "category":"General", "tags":[], "faqs":[], "markdown_content":"초안 A의 구체적인 내용입니다."}
    data.update(changes)
    return data


class ApprovalBoundaryTests(unittest.TestCase):
    def setUp(self):
        self.temp = tempfile.TemporaryDirectory()
        self.addCleanup(self.temp.cleanup)
        self.directory = Path(self.temp.name)
        self.env = patch.dict(os.environ, {}, clear=True)
        self.env.start()
        self.addCleanup(self.env.stop)
        with patch.object(main_pipeline, "load_config", return_value={}), patch("integrations.telegram_bot._load_env_file"):
            self.daemon = importlib.import_module("telegram_daemon")
        self.cfg = patch.object(self.daemon, "config", {"telegram":{"chat_id":"42"}})
        self.cfg.start()
        self.addCleanup(self.cfg.stop)
        self.daemon.sessions.clear()
        self.addCleanup(self.daemon.sessions.clear)
        self.context = SimpleNamespace(args=["known-draft"], bot=SimpleNamespace(send_message=AsyncMock(return_value=SimpleNamespace(edit_text=AsyncMock()))))
        self.network = patch("requests.sessions.Session.request", side_effect=AssertionError("offline: no network"))
        self.network.start()
        self.addCleanup(self.network.stop)

    def update(self, data="", chat=42):
        message = SimpleNamespace(chat_id=chat, message_id=1, text="/approve known-draft", reply_text=AsyncMock())
        query = SimpleNamespace(data=data, message=message, answer=AsyncMock(), edit_message_text=AsyncMock())
        return SimpleNamespace(effective_chat=SimpleNamespace(id=chat), message=message, callback_query=query)

    def test_all_registered_handlers_reject_unknown_chat_before_work(self):
        names = ("start", "handle_help_command", "handle_status_command", "handle_traffic_command", "handle_cancel", "handle_queue_command", "handle_approve_command", "handle_reject_command", "handle_review_command", "handle_write_command", "handle_edit_command", "handle_text_message", "button_callback")
        update = self.update("approve:known-draft", chat=99)
        with patch.object(self.daemon, "DraftApprovalQueue") as queue, patch.object(self.daemon, "publish_queued_draft") as publish, patch.object(self.daemon, "GitHubPublisher") as publisher:
            for name in names:
                handler = getattr(self.daemon, name)
                self.assertTrue(hasattr(handler, "__wrapped__"), name)
                asyncio.run(handler(update, self.context))
            queue.assert_not_called()
            publish.assert_not_called()
            publisher.assert_not_called()
        update.message.reply_text.assert_not_awaited()
        update.callback_query.answer.assert_not_awaited()
        self.context.bot.send_message.assert_not_awaited()

    def test_missing_or_invalid_config_fails_closed_even_for_known_button(self):
        for value in (None, "", True, "@someone", [], "not-a-chat"):
            with patch.object(self.daemon, "config", {"telegram":{"chat_id":value}}), patch.object(self.daemon, "publish_queued_draft") as publish:
                asyncio.run(self.daemon.button_callback(self.update("approve:known-draft"), self.context))
                publish.assert_not_called()
                self.assertIsNone(self.daemon.configured_chat_id())

    def test_existing_environment_chat_and_group_chat_are_supported(self):
        with patch.object(self.daemon, "config", {}), patch.dict(os.environ, {"TELEGRAM_CHAT_ID":"-1001234"}), patch.object(self.daemon, "DraftApprovalQueue") as queue:
            queue.return_value.list_pending.return_value = []
            allowed = self.update(chat=-1001234)
            asyncio.run(self.daemon.handle_queue_command(allowed, self.context))
            allowed.message.reply_text.assert_awaited_once()
            queue.assert_called_once()
            asyncio.run(self.daemon.handle_queue_command(self.update(chat=-1009999), self.context))
            queue.assert_called_once()

    def test_existing_queue_approval_only_for_configured_chat(self):
        with patch.object(self.daemon, "publish_queued_draft", return_value=(False,"needs review")) as publish:
            asyncio.run(self.daemon.button_callback(self.update("approve:known-draft"), self.context))
            publish.assert_called_once_with(self.daemon.config, "known-draft", human_approved=True)

    def test_invalid_metadata_is_rejected_before_file_write(self):
        invalid = ({"pubDate":"2026-02-30"}, {"pubDate":123}, {"updatedDate":"yesterday"}, {"updatedDate":None},
                   {"heroImage":{}}, {"summaryCards":[{"title":"wrong", "value":"shape"}]},
                   {"summaryCards":[{"badge":"b", "title":"t", "desc":"d", "icon":5}]},
                   {"summaryCards":None}, {"featured":1}, {"draft":"false"}, {"readingTime":5}, {"author":None})
        publisher = GitHubPublisher({"github":{"repo_root":str(self.directory),"blog_content_dir":str(self.directory/"blog"),"auto_git_commit":False}})
        for fields in invalid:
            with self.subTest(fields=fields), self.assertRaises(ContentValidationError):
                publisher.publish_article(article(**fields), human_approved=True)
        self.assertFalse((self.directory/"blog").exists())

    def test_valid_metadata_matches_supported_astro_schema(self):
        validate_article(article(pubDate="2024-02-29", updatedDate="2026-09-12T10:20:30Z", heroImage="/hero.png",
                         summaryCards=[{"badge":"조건", "title":"신청 전 확인", "desc":"대상을 확인하세요.", "icon":"info"}],
                         featured=False, draft=True, author="편집팀", readingTime="3 min read"))

    def test_existing_invalid_metadata_is_not_serialized_during_edit(self):
        publisher = GitHubPublisher({"github":{"repo_root":str(self.directory),"blog_content_dir":str(self.directory/"blog"),"auto_git_commit":False}})
        path = Path(publisher.publish_article(article(), human_approved=True))
        original = path.read_text().replace("featured: false", "featured: broken")
        path.write_text(original)
        with self.assertRaises(ContentValidationError):
            publisher.update_existing_article(path.stem, article(markdown_content="새 내용"), human_approved=True)
        self.assertEqual(path.read_text(), original)

    def test_old_revision_session_and_legacy_buttons_cannot_publish_current_article(self):
        session = {"draft":article()}
        old = issue_approval(session, "draft")
        session["draft"] = article(title="초안 B", markdown_content="다른 원고 B")
        latest = issue_approval(session, "draft")
        self.daemon.sessions[42] = session
        with patch.object(self.daemon, "execute_publish", new_callable=AsyncMock) as execute:
            asyncio.run(self.daemon.button_callback(self.update("btn_publish_draft:"+old), self.context))
            asyncio.run(self.daemon.button_callback(self.update("btn_publish_draft"), self.context))
            execute.assert_not_awaited()
            # Replacing the conversation invalidates the formerly latest button too.
            self.daemon.sessions[42] = {"draft":deepcopy(session["draft"])}
            issue_approval(self.daemon.sessions[42], "draft")
            asyncio.run(self.daemon.button_callback(self.update("btn_publish_draft:"+latest), self.context))
            execute.assert_not_awaited()

    def test_payload_change_without_token_refresh_and_changed_edit_slug_are_rejected(self):
        for field in ("draft", "data"):
            session = {field:article(), "slug":"original"}
            token = issue_approval(session, field)
            session[field]["faqs"] = [{"question":"q", "answer":"new answer"}]
            self.assertIsNone(consume_approval(session, field, token))
        session = {"data":article(), "slug":"original"}
        token = issue_approval(session,"data")
        session["slug"] = "different-target"
        self.assertIsNone(consume_approval(session,"data",token))
        invalidate_approvals(session)
        self.assertNotIn("data_approval",session)

    def test_correct_revision_is_published_once_using_captured_payload(self):
        session = {"draft":article()}
        token = issue_approval(session,"draft")
        self.daemon.sessions[42] = session
        update = self.update("btn_publish_draft:"+token)
        status = SimpleNamespace(edit_text=AsyncMock())
        async def during_status(**kwargs):
            # Simulate a double-click arriving during the awaited progress message.
            await self.daemon.button_callback(update,self.context)
            # Even an in-memory change cannot switch the approved payload.
            session["draft"] = article(title="B",markdown_content="unapproved B")
            return status
        self.context.bot.send_message.side_effect = during_status
        with patch.object(self.daemon,"GitHubPublisher") as publisher, patch.object(self.daemon,"GoogleIndexing"), patch.object(self.daemon,"TelegramNotifier"):
            publisher.return_value.publish_article.return_value = str(self.directory/"approved-a.md")
            asyncio.run(self.daemon.button_callback(update,self.context))
            publisher.return_value.publish_article.assert_called_once_with(article(),human_approved=True)
            asyncio.run(self.daemon.button_callback(update,self.context))
            publisher.return_value.publish_article.assert_called_once()
        self.assertNotIn("draft_approval",session)
        self.assertFalse(session["busy"])

    def test_edit_approval_binds_revision_and_target_then_consumes_token(self):
        session = {"data":article(),"slug":"original"}
        token = issue_approval(session,"data")
        self.daemon.sessions[42] = session
        with patch.object(self.daemon,"GitHubPublisher") as publisher, patch.object(self.daemon,"GoogleIndexing"):
            publisher.return_value.update_existing_article.return_value=(str(self.directory/"original.md"),"original")
            asyncio.run(self.daemon.button_callback(self.update("btn_apply_edit:"+token),self.context))
            publisher.return_value.update_existing_article.assert_called_once_with("original",article(),new_slug=None,human_approved=True)
            asyncio.run(self.daemon.button_callback(self.update("btn_apply_edit:"+token),self.context))
            publisher.return_value.update_existing_article.assert_called_once()


if __name__ == "__main__":
    unittest.main()
