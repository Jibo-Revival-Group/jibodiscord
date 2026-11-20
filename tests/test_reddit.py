import unittest

import reddit

LISTING = {"data": {"children": [
    {"data": {"id": "b2", "title": " Newer ", "author": "zane", "subreddit": "JiboRevival", "permalink": "/r/JiboRevival/comments/b2/x/",
              "preview": {"images": [{"source": {"url": "https://preview.redd.it/p.jpg"}}]}}},
    {"data": {"id": "a1", "title": "Older", "author": None, "subreddit": "Jibo", "permalink": "/r/Jibo/comments/a1/y/"}},
    {"data": {}},
]}}


class RedditTest(unittest.TestCase):
    def test_listing_oldest_first(self):
        self.assertEqual(reddit.parse_listing(LISTING), [
            {"id": "a1", "title": "Older", "author": "[deleted]", "subreddit": "Jibo",
             "url": "https://www.reddit.com/r/Jibo/comments/a1/y/", "image": ""},
            {"id": "b2", "title": "Newer", "author": "zane", "subreddit": "JiboRevival",
             "url": "https://www.reddit.com/r/JiboRevival/comments/b2/x/", "image": "https://preview.redd.it/p.jpg"},
        ])

    def test_both_subreddits_in_one_request(self):
        self.assertIn("/r/Jibo+JiboRevival/new", reddit.NEW_URL)


if __name__ == "__main__":
    unittest.main()
