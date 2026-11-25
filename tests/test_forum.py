import unittest
from datetime import datetime, timezone

import forum

DOC = {
    "data": [
        {"type": "posts", "id": "9", "attributes": {"number": 2, "contentType": "comment", "createdAt": "2026-11-25T01:00:00+00:00",
                                                    "contentHtml": "<p>Mine works &amp; talks!</p>"},
         "relationships": {"discussion": {"data": {"type": "discussions", "id": "4"}}, "user": {"data": {"type": "users", "id": "7"}}}},
        {"type": "posts", "id": "8", "attributes": {"number": 3, "contentType": "discussionRenamed", "createdAt": "2026-11-25T00:59:00+00:00"},
         "relationships": {"discussion": {"data": {"type": "discussions", "id": "4"}}}},
        {"type": "posts", "id": "5", "attributes": {"number": 1, "contentType": "comment", "createdAt": "2026-11-25T00:40:00+00:00",
                                                    "contentHtml": "<p>Hello <strong>everyone</strong></p>"},
         "relationships": {"discussion": {"data": {"type": "discussions", "id": "4"}}, "user": {"data": None}}},
    ],
    "included": [
        {"type": "discussions", "id": "4", "attributes": {"title": "My Jibo is back"}},
        {"type": "users", "id": "7", "attributes": {"displayName": "cazberg", "avatarUrl": "https://forum.jiborevival.com/assets/avatars/a.png"}},
    ],
}


class ForumTest(unittest.TestCase):
    def test_comments_oldest_first_with_discussion_and_author(self):
        self.assertEqual(forum.to_posts(DOC), [
            {"id": "5", "number": 1, "title": "My Jibo is back", "author": "[deleted]", "avatar": "",
             "url": "https://forum.jiborevival.com/d/4/1", "summary": "Hello everyone", "created": "2026-11-25T00:40:00+00:00", "image": "", "video": ""},
            {"id": "9", "number": 2, "title": "My Jibo is back", "author": "cazberg", "avatar": "https://forum.jiborevival.com/assets/avatars/a.png",
             "url": "https://forum.jiborevival.com/d/4/2", "summary": "Mine works & talks!", "created": "2026-11-25T01:00:00+00:00", "image": "", "video": ""},
        ])

    def test_media_prefers_the_full_size_upload_then_any_image(self):
        upload = ('<p>Look<img src="https://forum.jiborevival.com/assets/emoji/1f600.png" class="emoji"></p>'
                  '<a href="https://forum.jiborevival.com/assets/files/2026-11-25/1-jibo.png" target="_blank" rel="noopener noreferrer" '
                  'class="FoFUpload--Upl-Image-Preview-Link"><img class="FoFUpload--Upl-Image-Preview" '
                  'src="https://forum.jiborevival.com/assets/files/2026-11-25/1-jibo-thumb.webp"></a>')
        self.assertEqual(forum.media(upload)["image"], "https://forum.jiborevival.com/assets/files/2026-11-25/1-jibo.png")
        self.assertEqual(forum.media('<p><img class="emoji" src="https://x/e.png"><img src="https://i.imgur.com/a.jpg" alt=""></p>'),
                         {"image": "https://i.imgur.com/a.jpg", "video": ""})
        video = '<div class="ButtonGroup" data-fof-upload-download-uuid="9b1c2d3e-aaaa-4bbb-8ccc-123456789abc">clip.mp4</div>'
        self.assertEqual(forum.media(video), {"image": "", "video": "https://forum.jiborevival.com/api/fof/download/9b1c2d3e-aaaa-4bbb-8ccc-123456789abc"})
        self.assertEqual(forum.media("<p>Just text</p>"), {"image": "", "video": ""})

    def test_long_posts_are_cut_at_a_word(self):
        text = forum.summary("<p>" + "word " * 100 + "</p>")
        self.assertTrue(text.endswith("word…") and len(text) <= forum.SUMMARY_LENGTH + 1)

    def test_only_recent_posts_count(self):
        now = datetime(2026, 11, 25, 12, tzinfo=timezone.utc)
        self.assertTrue(forum.is_recent({"created": "2026-11-25T01:00:00+00:00"}, now))
        self.assertFalse(forum.is_recent({"created": "2026-11-23T01:00:00+00:00"}, now))
        self.assertFalse(forum.is_recent({"created": ""}, now))


if __name__ == "__main__":
    unittest.main()
