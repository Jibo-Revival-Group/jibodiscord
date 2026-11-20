import unittest

import reddit

RAW = [
    {"id": "t3_b2", "title": " Newer ", "author": "zane", "permalink": "/r/Jibo/comments/b2/x/", "type": "image", "href": "https://i.redd.it/p.jpg"},
    {"id": "t3_a1", "title": "Older", "author": None, "permalink": "/r/Jibo/comments/a1/y/", "type": "text", "href": "https://www.reddit.com/r/Jibo/comments/a1/y/"},
    {"id": "ad-123", "title": "Promoted", "permalink": ""},
]


class RedditTest(unittest.TestCase):
    def test_posts_oldest_first_without_ads(self):
        self.assertEqual(reddit.to_posts("Jibo", RAW), [
            {"id": "a1", "title": "Older", "author": "[deleted]", "subreddit": "Jibo",
             "url": "https://www.reddit.com/r/Jibo/comments/a1/y/", "image": ""},
            {"id": "b2", "title": "Newer", "author": "zane", "subreddit": "Jibo",
             "url": "https://www.reddit.com/r/Jibo/comments/b2/x/", "image": "https://i.redd.it/p.jpg"},
        ])


if __name__ == "__main__":
    unittest.main()
