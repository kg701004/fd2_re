"""`H.game_alive()` 的判別性測試 —— 特別是**短暫黑畫面**這個失敗模式。

2026-09-04 的教訓:第一版是單幀判斷,並用 5 張靜態截圖驗證「5/5 正確」。
那組樣本裡**沒有一張是轉場中的畫面**,所以看不出真正的失敗模式——
轉場黑畫面同樣「顏色少、幾乎全黑」,會被判成「遊戲已離開」。
實際發生過:同一個實例被判成已離開,兩分鐘後又量到 102 色。

修法依據**持續性**:DOS 提示字元會一直在,轉場黑畫面是短暫的。
所以多幀取樣、任一幀像遊戲就算存活。

本測試用合成畫面,不依賴不入版控的截圖,並且**兩個方向都測**:
只測「持續黑 → 判死」的話,一個永遠回傳存活的函式也會通過。
"""

import sys
import unittest
from pathlib import Path

sys.path.insert(0, str(Path(__file__).resolve().parent))

try:
    from PIL import Image
except ImportError:                                   # pragma: no cover
    Image = None

import fd2_dosbox_live_helper as H


def _make(path: Path, kind: str) -> None:
    """合成一張畫面。`game` 用多色雜訊,`dos` 用近乎全黑加少量文字色。"""
    im = Image.new("RGB", (320, 200), (0, 0, 0))
    px = im.load()
    if kind == "game":
        for y in range(200):
            for x in range(320):
                px[x, y] = ((x * 7) % 256, (y * 5) % 256, ((x + y) * 3) % 256)
    else:                                             # dos / 轉場黑畫面
        for y in range(8, 12):
            for x in range(4, 60):
                px[x, y] = (170, 170, 170)
    im.save(path)


@unittest.skipIf(Image is None, "缺少 Pillow")
class GameAliveTest(unittest.TestCase):
    def setUp(self):
        import tempfile
        self.td = tempfile.TemporaryDirectory()
        self.d = Path(self.td.name)
        _make(self.d / "game.png", "game")
        _make(self.d / "dos.png", "dos")
        self._real = H.screenshot

    def tearDown(self):
        H.screenshot = self._real
        self.td.cleanup()

    def _drive(self, seq):
        """讓 H.screenshot 依序吐出指定種類的畫面。"""
        import shutil
        state = {"i": 0}

        def fake(instance, out):
            kind = seq[min(state["i"], len(seq) - 1)]
            state["i"] += 1
            shutil.copy(self.d / f"{kind}.png", out)
            return Path(out)

        H.screenshot = fake
        return state

    # ---- 單幀判準:兩個方向 -------------------------------------------
    def test_single_frame_classifies_both_kinds(self):
        self.assertTrue(H._frame_looks_alive(self.d / "game.png")["alive"])
        self.assertFalse(H._frame_looks_alive(self.d / "dos.png")["alive"])

    # ---- 新邏輯真正要防的那件事 ---------------------------------------
    def test_transient_dark_frame_does_not_read_as_exited(self):
        """黑、黑、遊戲 → 必須判為存活。這是舊版會判錯的情形。"""
        st = self._drive(["dos", "dos", "game"])
        alive, m = H.game_alive("x", shot=self.d / "s.png", samples=3, gap=0)
        self.assertTrue(alive, f"轉場黑畫面被誤判成已離開:{m}")
        self.assertEqual(st["i"], 3, "應該一直取樣到看見遊戲畫面為止")

    def test_persistently_dark_reads_as_exited(self):
        """一直黑 → 判為已離開。缺這條的話,一個永遠回傳存活的函式也會通過上一條。"""
        self._drive(["dos", "dos", "dos"])
        alive, m = H.game_alive("x", shot=self.d / "s.png", samples=3, gap=0)
        self.assertFalse(alive, f"持續黑畫面應判為已離開:{m}")

    def test_alive_short_circuits_on_first_frame(self):
        """遊戲畫面第一幀就該回傳,不要白等——存活是常態,不能每次都花滿取樣時間。"""
        st = self._drive(["game", "dos", "dos"])
        alive, _ = H.game_alive("x", shot=self.d / "s.png", samples=3, gap=0)
        self.assertTrue(alive)
        self.assertEqual(st["i"], 1)

    def test_measurements_are_returned_for_review(self):
        """布林不夠:可疑時要能自己覆核每一幀的數字。"""
        self._drive(["dos", "game"])
        _, m = H.game_alive("x", shot=self.d / "s.png", samples=2, gap=0)
        self.assertEqual(len(m["frames"]), 2)
        for f in m["frames"]:
            self.assertIn("distinct_colors", f)
            self.assertIn("nonblack_ratio", f)


if __name__ == "__main__":
    unittest.main()
