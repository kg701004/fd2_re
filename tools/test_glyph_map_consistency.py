"""glyph_map.json 的內部一致性不變量。

2026-09-04 全工具重驗時,對 1824 個字模逐一取雜湊、依 Unicode 分組,發現**只有兩個字**
被多個 glyph 索引共用,而且**兩對的字模都不相同**——也就是每對至少有一邊是錯的:

* 「痺」= glyph 423 + 445 —— a73158c6 把 423 由「庫」改成「痺」造成。已還原 423 → 庫。
* 「、」= glyph 1188 + 1507 —— **既有的未解問題**,現有證據無法分離,刻意不猜,列入白名單。

判準:**不是「字模有沒有差」,是「重疊得像不像同一個字」**
---------------------------------------------------------
第一版寫成「同字必須同字模」,結果 423 還原成「庫」之後撞到 glyph 1614(本來就是庫)——
同一個字有兩份**近似但不同**的刻版是正常的,那條判準會把正常情況也判成錯。

第二版改用差異像素數,但它**與字的大小相關**:「、」只有 9~11 個墨點,兩個完全不重疊的
「、」也只差 20 像素,遠低於漢字的門檻,於是 1188/1507 根本不會被判為衝突——白名單空轉。
(這是實際跑出來的:清空白名單當對照組,測試照樣通過,證明那條判準沒在保護它。)

第三版改用 **IoU(墨色交集/聯集)**,與字的大小無關。300 組隨機字對:
中位 0.223、95% 分位 0.359、最大 0.438。

| 比較 | IoU | 判讀 |
|---|---|---|
| 423 vs 1614(同為庫) | **0.533** | 高於隨機最大值 → 同一個字的兩份刻版 |
| 423 vs 445(痺) | 0.250 | 隨機中位數水準 → **不同字** |
| 1188 vs 1507(、) | **0.000** | 完全不重疊 → 不同符號 |
| 444(痲) vs 445(痺) | 0.302 | 參考:同部首不同字 |

門檻 `SAME_CHAR_IOU = 0.359`(隨機基準的 95% 分位):**低於此值即視為不同字**。
兩組都會被抓到,白名單這才真的有作用。

這條不變量便宜又抓得到真問題:任何「拿名稱層級的結論去改像素層級對映」的修改都會撞到它。
"""

import collections
import hashlib
import json
import pathlib
import sys
import unittest

sys.path.insert(0, str(pathlib.Path(__file__).resolve().parent))

REPO = pathlib.Path(__file__).resolve().parent.parent
GLYPH_MAP = REPO / "docs" / "data" / "glyph_map.json"
FONT = REPO / "extracted" / "raw" / "FDOTHER" / "FDOTHER_004.bin"

# 已知且**刻意未解**的共用:證據不足以分離,不猜。加白名單必須寫明理由。
KNOWN_UNRESOLVED = {
    "、": [1188, 1507],
}

# 隨機字對 IoU 的 95% 分位(300 組取樣,見 docstring)。低於此值即視為不同字。
SAME_CHAR_IOU = 0.359


def _load_map():
    raw = json.loads(GLYPH_MAP.read_text(encoding="utf-8"))
    raw = raw.get("glyphs", raw)
    return {int(k): v for k, v in raw.items() if k.lstrip("-").isdigit()}


class GlyphMapConsistencyTest(unittest.TestCase):
    @classmethod
    def setUpClass(cls):
        if not FONT.exists():
            raise unittest.SkipTest(f"缺少 {FONT}(extracted/ 不入版控)")
        from decode_text import load_font, render_glyph

        cls.gm = _load_map()
        font, _ = load_font(str(FONT))
        cls.bitmap = {}
        cls.bits = {}
        for i in cls.gm:
            try:
                img = render_glyph(font, i)
            except Exception:
                cls.bitmap[i] = cls.bits[i] = None
                continue
            cls.bitmap[i] = hashlib.md5(img.tobytes()).hexdigest()
            cls.bits[i] = bytes(1 if b > 127 else 0 for b in img.convert("L").tobytes())

    def _iou(self, a: int, b: int) -> float:
        """墨色交集/聯集。**刻意不用差異像素數**——那個與字的大小相關,
        小字元(如「、」)永遠達不到漢字的門檻,見模組 docstring。"""
        A, B = self.bits[a], self.bits[b]
        inter = sum(x & y for x, y in zip(A, B))
        union = sum(x | y for x, y in zip(A, B))
        return inter / union if union else 1.0

    def _shared(self):
        by_char = collections.defaultdict(list)
        for idx, ch in self.gm.items():
            by_char[ch].append(idx)
        return {ch: sorted(ix) for ch, ix in by_char.items() if len(ix) > 1}

    def test_no_character_is_shared_by_glyphs_that_barely_overlap(self):
        offenders = []
        for ch, idx in self._shared().items():
            if KNOWN_UNRESOLVED.get(ch) == idx:
                continue                      # 已知未解,見模組 docstring
            worst = min((self._iou(idx[i], idx[j]) for i in range(len(idx))
                         for j in range(i + 1, len(idx))), default=1.0)
            if worst < SAME_CHAR_IOU:
                offenders.append((ch, idx, round(worst, 3)))
        self.assertEqual(
            offenders, [],
            "有 glyph 差得像兩個不相干的字,卻對到同一個 Unicode——至少一邊是錯的。"
            "若是像 423/445 那種『名稱裁決被套進像素對映』,修的是對映不是這條測試;"
            "若真的無法分離,加進 KNOWN_UNRESOLVED 並寫明理由。")

    def test_glyph_423_is_the_pixel_decode_not_the_ruled_name(self):
        """回歸鎖:423 是 庫,不是名稱裁決的「痺」。用量測而不是肉眼判讀。"""
        self.assertEqual(self.gm[423], "庫")
        self.assertEqual(self.gm[445], "痺")
        self.assertLess(
            self._iou(423, 445), SAME_CHAR_IOU,
            "423 與 445 若變得相似,表示字型或渲染改了,這條結論要重驗")
        self.assertGreaterEqual(
            self._iou(423, 1614), SAME_CHAR_IOU,
            "423 應與另一個『庫』(1614)重疊——這是它是庫的正面證據,不只是『不是痺』")

    def test_the_known_unresolved_pair_is_still_actually_unresolved(self):
        """對照組:白名單不可以變成掩蓋。它必須仍然是**字模不同**才有存在意義。"""
        for ch, idx in KNOWN_UNRESOLVED.items():
            self.assertEqual([self.gm[i] for i in idx], [ch] * len(idx))
            worst = min(self._iou(idx[i], idx[j]) for i in range(len(idx))
                        for j in range(i + 1, len(idx)))
            self.assertLess(worst, SAME_CHAR_IOU,
                            f"{ch} 的字模已經足夠相似,這筆白名單該移除了")

    def test_only_one_glyph_has_a_blank_bitmap(self):
        """glyph 181 字模全零(見 command_labels id9 的覆寫)。多出來的空字模要被看見。"""
        blank = sorted(i for i, h in self.bitmap.items() if h == self.bitmap[181])
        self.assertEqual(blank, [181])


if __name__ == "__main__":
    unittest.main()
