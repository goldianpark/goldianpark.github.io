import unittest
from modules.content_validation import body_fingerprint


class IllustrationIdentityTests(unittest.TestCase):
    def test_unique_image_does_not_disguise_duplicate_article(self):
        original = "## 제목\n실제 원고의 설명입니다.\n\n## 실행\n입력을 확인합니다."
        figure = "<!-- article-illustration:example-01 -->\n<figure><img src='/images/articles/unique.webp' alt='설명'/><figcaption>AI로 제작한 설명용 이미지</figcaption></figure>\n<!-- /article-illustration:example-01 -->\n"
        decorated = original.replace("## 실행", figure + "## 실행")
        self.assertEqual(body_fingerprint(original), body_fingerprint(decorated))

    def test_real_text_changes_still_affect_article_identity(self):
        self.assertNotEqual(body_fingerprint("입력을 확인합니다."), body_fingerprint("입력을 저장합니다."))


if __name__ == "__main__":
    unittest.main()
