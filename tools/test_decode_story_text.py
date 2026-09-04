"""decode_story_text 的說話者解析回歸測試。

背景:2026-09-04 之前 `decode_string` 不看開框碼,`0xFFEC..0xFFEF` 四種一律拿
operand 查 `PORT`。doc09 用**原版截圖**抓到 ch01 王宮兩句被標成索爾、畫面上是國王;
全 FDTXT 量測顯示這種框有 273/1450(18.8%)。

這裡刻意同時測**兩個方向**:runtime-unit 框必須停止猜名字,身分查找框必須**照舊**
解出名字。只測前者的話,把 `resolve_speaker` 寫成「一律回傳 unit#N」也會通過。
"""

import pathlib
import sys
import unittest

sys.path.insert(0, str(pathlib.Path(__file__).resolve().parent))

import decode_story_text as D

RAW = pathlib.Path(__file__).resolve().parent.parent / "extracted" / "raw" / "FDTXT"


class ResolveSpeakerTest(unittest.TestCase):
    """純函式層:四種開框碼各自的行為。"""

    def test_identity_boxes_resolve_a_real_name(self):
        for code in (0xFFEE, 0xFFEF):
            self.assertEqual(D.resolve_speaker(code, 0), "索爾")
            self.assertEqual(D.resolve_speaker(code, 0x1E), "蓋亞")

    def test_runtime_boxes_refuse_to_name_and_say_why(self):
        for code in (0xFFEC, 0xFFED):
            got = D.resolve_speaker(code, 0)
            self.assertIn("unit#0", got)
            self.assertNotIn("索爾", got,
                             "runtime-unit 框的 operand 是執行期索引,靜態解不出姓名")

    def test_same_operand_gives_different_answers_per_box_code(self):
        """對照組:分流必須真的依開框碼,而不是碰巧兩邊都改成同一種回答。"""
        self.assertNotEqual(D.resolve_speaker(0xFFEE, 0), D.resolve_speaker(0xFFED, 0))

    def test_unknown_leading_code_is_reported_not_guessed(self):
        got = D.resolve_speaker(0xFFFE, 3)
        self.assertIn("?#3", got)
        self.assertNotIn("哈瓦特", got)


class Ch01PalaceRealDataTest(unittest.TestCase):
    """實資料層:doc09 記載、以原版截圖判定的那三句。

    `extracted/` 不入版控(原版素材著作權),沒有時 skip 而不是假裝通過。
    """

    @classmethod
    def setUpClass(cls):
        f = RAW / "FDTXT_033.bin"
        if not f.exists():
            raise unittest.SkipTest(f"缺少 {f}(extracted/ 不入版控)")
        cls.boxes = [(spk, "".join(lines))
                     for codes in D.parse_strings(f)
                     for spk, lines in D.decode_string(codes)]

    def test_king_lines_are_not_attributed_to_sol(self):
        """第 2、4 句:原版畫面是上框+右頭像=NPC(國王),舊解碼標成索爾。"""
        for idx in (1, 3):                      # 0-based
            spk, text = self.boxes[idx]
            self.assertIn("unit#", spk, f"第 {idx + 1} 句仍被硬套名字:{spk}")
            self.assertNotIn("索爾", spk)
        self.assertIn("你來啦", self.boxes[1][1])   # 錨定確實是那一句

    def test_sol_line_is_still_attributed_to_sol(self):
        """對照組:第 12 句原版畫面是下框+左頭像=我方,標記本來就對,不可被誤傷。"""
        spk, text = self.boxes[11]
        self.assertEqual(spk, "索爾")
        self.assertIn("並未繼承", text)

    def test_runtime_boxes_are_a_minority_but_not_negligible(self):
        """守住量級:若哪天分流被改壞成全部走同一支,這裡會抓到。"""
        runtime = sum(1 for spk, _ in self.boxes if spk and "unit#" in spk)
        self.assertGreater(runtime, 0)
        self.assertLess(runtime, len(self.boxes),
                        "不可能整章都是 runtime-unit 框——那代表分流壞了")


if __name__ == "__main__":
    unittest.main()
