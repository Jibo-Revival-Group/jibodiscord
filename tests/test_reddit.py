import unittest

import reddit

RAW = [
    {"id": "t3_b2", "title": " Newer ", "author": "zane", "permalink": "/r/Jibo/comments/b2/x/", "type": "video",
     "href": "https://v.redd.it/abc", "body": "", "media": "https://external-preview.redd.it/p.png"},
    {"id": "t3_a1", "title": "Older", "author": None, "permalink": "/r/Jibo/comments/a1/y/", "type": "multi_media",
     "href": "https://www.reddit.com/r/Jibo/comments/a1/y/", "body": "Hi everyone!\n\nWe made a wiki.", "media": ""},
    {"id": "ad-123", "title": "Promoted", "permalink": ""},
]


class RedditTest(unittest.TestCase):
    def test_posts_oldest_first_without_ads(self):
        self.assertEqual(reddit.to_posts("Jibo", RAW), [
            {"id": "a1", "title": "Older", "author": "[deleted]", "subreddit": "Jibo",
             "url": "https://www.reddit.com/r/Jibo/comments/a1/y/", "summary": "Hi everyone! We made a wiki.", "created": "", "image": "", "video": ""},
            {"id": "b2", "title": "Newer", "author": "zane", "subreddit": "Jibo",
             "url": "https://www.reddit.com/r/Jibo/comments/b2/x/", "summary": "", "created": "", "image": "", "video": "https://v.redd.it/abc"},
        ])

    def test_only_recent_posts_count(self):
        from datetime import datetime, timezone
        now = datetime(2026, 11, 20, 22, 0, tzinfo=timezone.utc)
        self.assertTrue(reddit.is_recent({"created": "2026-11-20T21:55:00.000000+0000"}, now))
        self.assertFalse(reddit.is_recent({"created": "2026-10-30T02:48:00.000000+0000"}, now))
        self.assertFalse(reddit.is_recent({"created": ""}, now))

    def test_long_summary_cut_at_a_word(self):
        s = reddit.summary("word " * 100)
        self.assertTrue(s.endswith("word…") and len(s) <= reddit.SUMMARY_LENGTH + 1)

    def test_image_sources(self):
        self.assertEqual(reddit.image({"type": "image", "href": "https://i.redd.it/x.jpg"}), "https://i.redd.it/x.jpg")
        self.assertEqual(reddit.image({"type": "link", "href": "https://youtube.com/watch?v=QRVz697rEx0&si=x"}),
                         "https://i.ytimg.com/vi/QRVz697rEx0/hqdefault.jpg")
        self.assertEqual(reddit.image({"type": "link", "href": "https://example.com/a"}), "")


if __name__ == "__main__":
    unittest.main()
