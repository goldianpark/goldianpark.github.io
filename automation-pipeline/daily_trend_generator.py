#!/usr/bin/env python3
"""News-informed drafts enter the same human review queue as regular articles."""
from modules.news_crawler import GoogleNewsCrawler
from agents.content_writer import ContentWriter
from agents.editorial_reviewer import EditorialReviewAgent
from modules.draft_queue import DraftApprovalQueue
from main_pipeline import load_config


def generate_trend_post(keyword="시니어 복지"):
    news_items = GoogleNewsCrawler().fetch_top_news(keyword, num_articles=5)
    if not news_items:
        raise RuntimeError("뉴스 자료가 없습니다. 글을 생성/발행하지 않았습니다.")
    config = load_config()
    topic = {"title": f"{keyword}: 뉴스에서 확인할 내용", "target_keyword": keyword,
             "category": "시니어 건강 & 일상", "tags": [keyword],
             "search_intent": "제공된 뉴스 범위의 사실과 확인이 필요한 내용을 구분하기",
             "sources": news_items, "key_points": []}
    article = ContentWriter(config).write_article(topic)
    review = EditorialReviewAgent(config).review_article(article, topic)
    draft_id = DraftApprovalQueue().add_draft(article, review, topic=topic)
    print(f"뉴스 초안 검토 대기: {draft_id}")
    return draft_id


if __name__ == "__main__":
    generate_trend_post()
