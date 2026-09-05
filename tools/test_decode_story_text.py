"""decode_story_text 的說話者解析回歸測試。

背景:2026-09-04 之前 `decode_string` 不看開框碼,`0xFFEC..0xFFEF` 四種一律拿
operand 查 `PORT`。doc09 用**原版截圖**抓到 ch01 王宮兩句被標成索爾、畫面上是國王;
全 FDTXT 量測顯示這種框有 273/1450(18.8%)。

這裡刻意同時測**兩個方向**:runtime-unit 框必須停止猜名字,身分查找框必須**照舊**
解出名字。只測前者的話,把 `resolve_speaker` 寫成「一律回傳 unit#N」也會通過。
"""

import glob
import pathlib
import sys
import unittest
from unittest import mock

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


class FindRuntimeTodoTest(unittest.TestCase):
    """`--runtime-todo`(2026-09-05 新增)的正反向驗證。

    2026-09-05:使用者要求「新建工具請正反向驗證」。`find_runtime_todo` 是純後處理
    (不碰 `decode_string`/`resolve_speaker`),但它自己有一個真實踩過的錯誤形狀——
    第一版用「只對 `- **` 開頭的行計數」當 box_index,會在遇到不帶說話者的續行
    (`  text`,沒有 `- **` 前綴)時漏算,讓後面所有 box_index 全部錯位一格。
    這裡用 `mock.patch` 餵合成的 `render_chapter` 輸出,不依賴真實 FDTXT 檔案就能
    測到這個對齊問題——比只跑真實資料更精確,因為真實資料湊巧對不對齊很難用眼睛看出來。
    """

    def test_box_index_survives_an_interspersed_non_speaker_line(self):
        """負對照(故障注入的反面):重現曾經真實發生過的錯位錯誤。

        如果 box_index 只對 `- **` 開頭的行計數(舊錯誤形狀),第三行(真正的
        runtime box)會被誤算成 index 1,而不是正確的 2。
        """
        fake_lines = [
            "- **索爾**：哈囉",                       # index 0:身分框,不進清單
            "  這是一句沒有說話者的續行",                 # index 1:非說話者行
            "- **unit#5(執行期決定)**：你是誰？",        # index 2:runtime 框,該進清單
        ]
        with mock.patch.object(D, "render_chapter", return_value=fake_lines):
            todo = D.find_runtime_todo("<fake path, patched>")
        self.assertEqual(len(todo), 1)
        self.assertEqual(todo[0]["box_index"], 2,
                         "box_index 沒有正確跳過非說話者續行——這正是曾經真實發生過的錯位")
        self.assertEqual(todo[0]["operand"], 5)

    def test_identity_boxes_never_appear_in_the_todo(self):
        """正對照:身分查找框(已解出真名)不該出現在『靜態不可解』清單裡。"""
        fake_lines = [
            "- **索爾**：這句已經解出名字了",
            "- **蓋亞**：這句也是",
            "  純續行,沒有說話者",
        ]
        with mock.patch.object(D, "render_chapter", return_value=fake_lines):
            todo = D.find_runtime_todo("<fake path, patched>")
        self.assertEqual(todo, [], "全部都是已解出名字的框,待辦清單應該是空的")

    def test_empty_chapter_yields_empty_todo(self):
        """邊界:沒有任何框(空章節)不該噴例外,回傳空清單。"""
        with mock.patch.object(D, "render_chapter", return_value=[]):
            self.assertEqual(D.find_runtime_todo("<fake path, patched>"), [])

    def test_multiple_runtime_boxes_keep_independent_indices(self):
        """正對照:兩個以上 runtime 框,各自的 box_index/operand 不能互相污染。"""
        fake_lines = [
            "- **unit#3(執行期決定)**：第一句",
            "- **索爾**：中間插一句已解出的",
            "- **unit#7(執行期決定)**：第二句",
        ]
        with mock.patch.object(D, "render_chapter", return_value=fake_lines):
            todo = D.find_runtime_todo("<fake path, patched>")
        self.assertEqual([(t["box_index"], t["operand"]) for t in todo],
                         [(0, 3), (2, 7)])


class RuntimeTodoRealDataTest(unittest.TestCase):
    """實資料層:對全部 35 個 FDTXT 跑一次,核對已知真值。

    `extracted/` 不入版控,沒有時 skip。
    """

    @classmethod
    def setUpClass(cls):
        if not RAW.is_dir():
            raise unittest.SkipTest(f"缺少 {RAW}(extracted/ 不入版控)")
        cls.files = sorted(glob.glob(str(RAW / "*.bin")))
        if not cls.files:
            raise unittest.SkipTest(f"{RAW} 底下沒有 .bin 檔")

    def test_total_matches_the_documented_273(self):
        """回歸鎖定:B.6(2026-09-04)記載全 35 個 FDTXT 有 273/1450 筆執行期說話者。

        這是本測試檔案能做的最強對照——不是重新推導出一個看起來合理的數字,是跟
        既有、獨立記錄下來的統計逐一核對。哪天 `decode_string`/`resolve_speaker`
        被改動而不小心動到判準,這裡會先炸,而不是等到活體驗證階段才發現對不上。
        """
        total = sum(len(D.find_runtime_todo(p)) for p in self.files)
        self.assertEqual(total, 273,
                         "273 這個數字是本專案 2026-09-04 已經記錄的既有統計,"
                         "跟這裡的數字對不上代表判準被動過,不是這份測試該遷就的地方")

    def test_no_identity_box_leaks_into_any_file_s_todo(self):
        """負對照(跨全部檔案):任何一個 FDTXT 的待辦清單裡都不該出現已解出的名字。"""
        for p in self.files:
            for entry in D.find_runtime_todo(p):
                self.assertNotIn("**", entry["text_snippet"],
                                 f"{p} 的待辦清單裡混進了看起來像已解出說話者格式的行")

    def test_box_indices_are_unique_and_sorted_per_file(self):
        """一致性:同一個 FDTXT 內,box_index 不能重複也不能倒退。"""
        for p in self.files:
            indices = [e["box_index"] for e in D.find_runtime_todo(p)]
            self.assertEqual(indices, sorted(set(indices)),
                             f"{p} 的 box_index 有重複或順序錯亂:{indices}")


if __name__ == "__main__":
    unittest.main()
