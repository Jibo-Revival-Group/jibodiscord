import unittest

import youtube

FEED = """<?xml version="1.0" encoding="UTF-8"?>
<feed xmlns:yt="http://www.youtube.com/xml/schemas/2015" xmlns="http://www.w3.org/2005/Atom">
 <title>Someone</title>
 <entry><yt:videoId>newest</yt:videoId><title>B</title></entry>
 <entry><yt:videoId>older</yt:videoId><title>A</title></entry>
</feed>"""


class YouTubeTest(unittest.TestCase):
    def test_feed_ids_oldest_first(self):
        self.assertEqual(youtube.parse_feed(FEED), ("Someone", [{"id": "older", "title": "A"}, {"id": "newest", "title": "B"}]))

    def test_first_check_posts_nothing_then_only_new(self):
        seen = {}
        self.assertEqual(youtube.new_videos(seen, "@a", ["older"]), [])
        self.assertEqual(youtube.new_videos(seen, "@a", ["older", "newest"]), ["newest"])
        self.assertEqual(youtube.new_videos(seen, "@a", ["older", "newest"]), [])
        self.assertEqual(youtube.new_videos(seen, "@b", ["older"]), [])  # a channel added later starts quiet too

    def test_seven_channels(self):
        self.assertEqual(len(youtube.CHANNELS), 7)
        self.assertTrue(all(i.startswith("UC") and len(i) == 24 for i in youtube.CHANNELS.values()))


if __name__ == "__main__":
    unittest.main()
