import os
import tempfile
import unittest
from pathlib import Path

os.environ.setdefault("DISCORD_TOKEN", "test")
os.environ.setdefault("DISCORD_GUILD_ID", "1")
import bot  # noqa: E402


class SeenTest(unittest.TestCase):
    def test_one_loop_saving_keeps_what_another_recorded(self):
        with tempfile.TemporaryDirectory() as d:
            bot.SEEN_FILE, bot._seen = Path(d) / "seen.json", None
            youtube_loop = bot.load_seen()            # e.g. the YouTube check, still waiting on the network
            forum_loop = bot.load_seen()
            forum_loop.setdefault("forum", []).append("8")  # the forum check posts 8
            bot.save_seen(forum_loop)
            youtube_loop.setdefault("@chan", []).append("v1")
            bot.save_seen(youtube_loop)               # the slower loop saves afterwards
            bot._seen = None
            self.assertIn("8", bot.load_seen().get("forum", []), "post 8 would be announced again")


if __name__ == "__main__":
    unittest.main()
