#!/usr/bin/env python3
"""fd2_re - parse `docs/knowledge-base/91-worklist.md` reliably, and append to it safely.

Why this exists
---------------
On 2026-09-07/08 three separate ad-hoc sweeps of the worklist gave three
different, wrong answers about "what is still open". Every failure was a
parsing bug, not a judgement error:

1. **Only the first physical line was read.** Appends land on the item's header
   line, so a scan that took `lines[i]` alone saw the newest headline but none
   of its bullets -- and a scan that took the block's *tail* saw the OLDEST
   text, because of (3).
2. **Keyword hits were attributed to the wrong item.** 54 of the file's 138
   items are written `N - A（2026-09-06由D關閉…）- …` with a FULL-WIDTH
   parenthetical between the class letter and the second dash. The obvious
   regex `^\\d+ - [A-F] - ` does not match those, so their text was silently
   folded into the *preceding* item's body. Since those are closed A-items
   whose prose quotes their own former "仍未解 / 仍開放" wording, the
   preceding B-F item looked open when it was not. This single bug produced
   most of the false positives.
3. **Continuation bullets are in REVERSE chronological order.** Appending with
   `lines[i] = lines[i] + "…\\n  * bullet"` splits on the next read, so the next
   append lands on the header line again -- ahead of the previous append's
   bullets. Net effect: headlines on the header line run forward in time,
   bullets after it run backward. Both facts are load-bearing and both are
   asserted by `--selftest`.

What it gives you
-----------------
    python tools/worklist_status.py --summary          # per-class counts
    python tools/worklist_status.py --open             # items whose NEWEST dated
                                                       #段 still asserts open work
    python tools/worklist_status.py --item 587         # one item, chronological
    python tools/worklist_status.py --append 587 --text "**2026-09-08 …**"
    python tools/worklist_status.py --selftest

`--append` is the fix for cause (3): it writes the new entry as its own block at
the END of the item, so the file stops accumulating reversed bullets. Existing
reversed bullets are left alone -- rewriting历史 text is a separate decision.

Verification design (`--selftest`, 6 checks)
--------------------------------------------
1. Structural: every line that looks like an item header is claimed by exactly
   one item, and no item's body contains another item's header.
2. The loose regex finds 138 items; the strict one finds 84 -- and **all 54 of
   the difference are class A**. This pins cause (2) as real and characterised.
3. Fault injection: swapping in the strict regex must make check 1 FAIL.
4. Ordering: on the header line, the dated markers are non-decreasing in time.
5. Reverse-bullet rule, pinned on a hand-verified item (587): its newest
   headline is 2026-09-08 and its FIRST bullet belongs to that entry.
6. Round-trip: `--append` then re-parse must show the appended text as the item's
   newest segment, and must not disturb neighbouring items (byte comparison of
   every other item's block).
"""

from __future__ import annotations

import argparse
import re
import sys
from pathlib import Path

if hasattr(sys.stdout, "reconfigure"):
    sys.stdout.reconfigure(encoding="utf-8")
    sys.stderr.reconfigure(encoding="utf-8")

WORKLIST = Path(__file__).resolve().parent.parent / "docs/knowledge-base/91-worklist.md"

# A worklist item header. The optional full-width/half-width parenthetical between
# the class letter and the second dash is what the naive regex missed; keeping it
# optional is the whole point of this pattern.
ITEM = re.compile(r"^(\d+)\s*-\s*([A-F])\s*(?:[（(][^）)]*[）)]\s*)?-\s*")
STRICT = re.compile(r"^(\d+) - ([A-F]) - ")
# A dated ENTRY marker, not merely a date in bold. The distinction is real: item
# 857's header contains `是**2026-08-19稽核當時…版本的行號**`, a date quoted
# mid-sentence, which a bare `\*\*date` pattern reads as a new entry and thereby
# reports the item's history as out of order. A genuine marker always opens at a
# sentence boundary, so require start-of-line or a terminator before the `**`.
DATE = re.compile(r"(?:^|(?<=[。．！？）)」\s]))\*\*\s*(\d{4}-\d\d-\d\d)")

# Words that, in this file's house style, assert work that is still to be done.
OPEN_WORDS = ("尚未關閉", "仍不宣告", "仍待完成", "仍缺的一步", "本輪未做", "仍開放", "無法回答")
# ...but the same words are quoted in order to negate them. These win.
CLOSE_WORDS = ("已解", "已關閉", "已完成", "不成立", "已定案", "無殘留", "不應繼續",
               "範圍消失", "已無對象", "已閉合", "不是仍待完成", "本項閉合")


class Item:
    def __init__(self, num: str, cls: str, start: int, lines: list[str]):
        self.num, self.cls, self.start = num, cls, start
        self.lines = lines                      # header line + continuation lines

    @property
    def header(self) -> str:
        return self.lines[0]

    @property
    def bullets(self) -> list[str]:
        """Continuation lines, NEWEST FIRST (see cause 3 in the module docstring)."""
        return [l for l in self.lines[1:] if l.strip()]

    @property
    def dates(self) -> list[str]:
        """Dated markers on the header line, oldest first."""
        return DATE.findall(self.header)

    @property
    def newest_segment(self) -> str:
        """The newest dated headline plus the bullets that belong to it.

        The headline is the text after the LAST dated marker on the header line;
        its bullets are the FIRST run of continuation lines, because bullets are
        stored in reverse order of appending.

        Entries written by `--append` land at the END of the block instead, so
        both sources are considered and the later date wins; on a tie the
        trailing one wins because it was written afterwards. Without this the
        tool's writer and reader disagree -- `--append` would add an entry that
        `--open`/`is_open` never looks at.
        """
        marks = [m.start() for m in DATE.finditer(self.header)]
        head_date = self.dates[-1] if self.dates else ""
        head = self.header[marks[-1]:] if marks else self.header
        run = []
        for l in self.bullets:
            if l.lstrip().startswith("*") or not run:
                run.append(l)
            else:
                break
        head_seg = head + "\n" + "\n".join(run)

        tail_date, tail_seg = "", ""
        for l in reversed(self.lines[1:]):
            d = DATE.findall(l)
            if d:
                tail_date, tail_seg = d[-1], l
                break
        if tail_date and tail_date >= head_date:
            return tail_seg
        return head_seg

    def is_open(self) -> bool:
        """Does the newest entry assert work that is still to be done?

        Two rewriting steps come first, and both were forced by real false
        positives in this file, not invented defensively:

        * **Quoted claims don't count.** The house style for closing an item is
          to quote its old wording and then negate it -- item 1069's newest
          entry reads 「本項自陳『本輪未做』的 … 已執行完畢」. Reading the quoted
          span as an assertion marks a finished item as open. Anything inside
          「」/『』 is therefore stripped before the scan.
        * **Negated claims don't count.** 53 and 1604 both end 「…不是仍待完成的
          工作」. An open word preceded by 不是/並非/非 is dropped.
        """
        seg = re.sub(r"[「『][^」』]*[」』]", "", self.newest_segment)
        seg = re.sub(r"(?:不是|並非|非)\s*(?:" + "|".join(OPEN_WORDS) + ")", "", seg)
        if any(w in seg for w in CLOSE_WORDS):
            return False
        return any(w in seg for w in OPEN_WORDS)


def parse(path: Path = WORKLIST, pattern: re.Pattern = ITEM) -> list[Item]:
    lines = path.read_text(encoding="utf-8").split("\n")
    starts = [(i, m.group(1), m.group(2))
              for i, m in ((i, pattern.match(l)) for i, l in enumerate(lines)) if m]
    items = []
    for k, (i, num, cls) in enumerate(starts):
        end = starts[k + 1][0] if k + 1 < len(starts) else len(lines)
        items.append(Item(num, cls, i, lines[i:end]))
    return items


def cmd_summary(items: list[Item]) -> None:
    import collections
    c = collections.Counter(it.cls for it in items)
    print(f"項目總數 {len(items)}:" + "  ".join(f"{k}={c[k]}" for k in sorted(c)))
    op = [it for it in items if it.is_open()]
    print(f"最新一段仍主張有待辦工作的:{len(op)} 項" + (f" -> {[it.num for it in op]}" if op else ""))


def cmd_open(items: list[Item]) -> None:
    op = [it for it in items if it.is_open()]
    if not op:
        print("沒有任何項目的最新一段主張有待辦工作。")
        return
    for it in op:
        seg = it.newest_segment.replace("\n", " ")
        hit = [w for w in OPEN_WORDS if w in seg]
        print(f"{it.num} ({it.cls}) {hit}\n   {seg[:300]}\n")


def cmd_item(items: list[Item], num: str) -> int:
    for it in items:
        if it.num != num:
            continue
        print(f"=== {it.num} ({it.cls})  行 {it.start+1},共 {len(it.lines)} 行 ===")
        print(f"日期標記(舊→新):{it.dates}")
        print(f"目前判定:{'**仍開放**' if it.is_open() else '已收斂'}")
        print("\n--- 最新一段 ---")
        print(it.newest_segment[:1500])
        return 0
    print(f"找不到項目 {num}")
    return 1


def cmd_append(num: str, text: str, path: Path = WORKLIST) -> int:
    """Append `text` as its own block at the END of the item -- the fix for the
    reversed-bullet bug. Never touches the header line."""
    lines = path.read_text(encoding="utf-8").split("\n")
    starts = [i for i, l in enumerate(lines) if ITEM.match(l)]
    for k, i in enumerate(starts):
        if ITEM.match(lines[i]).group(1) != num:
            continue
        end = starts[k + 1] if k + 1 < len(starts) else len(lines)
        while end > i + 1 and not lines[end - 1].strip():
            end -= 1
        lines[end:end] = text.split("\n")
        path.write_text("\n".join(lines), encoding="utf-8")
        print(f"已在項目 {num} 的區塊末端附加 {len(text.split(chr(10)))} 行")
        return 0
    print(f"找不到項目 {num}")
    return 1


def selftest() -> int:
    fails: list[str] = []
    items = parse()

    print("(1) 結構:沒有任何項目的內文包含另一個項目的標題行")
    bad = [(it.num, ITEM.match(l).group(1)) for it in items
           for l in it.lines[1:] if ITEM.match(l)]
    print(f"    {'PASS' if not bad else 'FAIL'}: {len(bad)} 個吞併" + (f" {bad[:5]}" if bad else ""))
    if bad:
        fails.append(f"項目內文吞併了其他項目:{bad[:5]}")

    print("\n(2) 寬鬆 vs 嚴格正則的差額必須全是 A 類(把 cause 2 釘住)")
    loose, strict = parse(pattern=ITEM), parse(pattern=STRICT)
    lo = {it.num for it in loose}
    so = {it.num for it in strict}
    diff = [it for it in loose if it.num in lo - so]
    non_a = [it.num for it in diff if it.cls != "A"]
    ok = len(loose) == 138 and len(strict) == 84 and not non_a
    print(f"    {'PASS' if ok else 'FAIL'}: 寬鬆 {len(loose)} / 嚴格 {len(strict)} / "
          f"差額 {len(diff)} 全為 A 類={not non_a}" + (f" 非A={non_a[:5]}" if non_a else ""))
    if not ok:
        fails.append(f"loose={len(loose)} strict={len(strict)} 非A差額={non_a[:5]}")

    print("\n(3) 故障注入:改用嚴格正則後,檢查(1)必須失敗")
    bad2 = [(it.num, ITEM.match(l).group(1)) for it in strict
            for l in it.lines[1:] if ITEM.match(l)]
    print(f"    {'PASS' if bad2 else 'FAIL'}: 嚴格正則下有 {len(bad2)} 個吞併")
    if not bad2:
        fails.append("嚴格正則下沒有吞併——檢查(1)不具鑑別力")

    print("\n(4) 標題行的日期標記必須不遞減(時間正序)")
    bad3 = [it.num for it in items if it.dates != sorted(it.dates)]
    print(f"    {'PASS' if not bad3 else 'FAIL'}: {len(bad3)} 項亂序" + (f" {bad3[:5]}" if bad3 else ""))
    if bad3:
        fails.append(f"標題行日期亂序:{bad3[:5]}")

    print("\n(5) 逆序子項目規則,以手工核對過的 587 釘住")
    it587 = next((i for i in items if i.num == "587"), None)
    ok5 = (it587 is not None and it587.dates and it587.dates[-1] == "2026-09-08"
           and "index 5 = 開啟狀態卡" in (it587.bullets[0] if it587.bullets else ""))
    print(f"    {'PASS' if ok5 else 'FAIL'}: 最新日期={it587.dates[-1] if it587 and it587.dates else '?'},"
          f" 首個子項目屬於該筆={'是' if ok5 else '否'}")
    if not ok5:
        fails.append("587 的逆序子項目規則不成立")

    print("\n(6) 往返:--append 後該項最新一段須含新文字,且其他項目逐字元不變")
    import tempfile
    import shutil
    with tempfile.TemporaryDirectory() as td:
        tmp = Path(td) / "w.md"
        shutil.copy(WORKLIST, tmp)
        before = {it.num: "\n".join(it.lines) for it in parse(tmp)}
        # 日期刻意設在未來,才能與該項既有的 2026-09-08 條目分辨開來。
        MARK = "  * **2099-01-01 SELFTEST-SENTINEL**"
        cmd_append("587", MARK, tmp)
        after_items = parse(tmp)
        after = {it.num: "\n".join(it.lines) for it in after_items}
        it2 = next(i for i in after_items if i.num == "587")
        seen = MARK.strip() in "\n".join(it2.lines)
        # 寫入端與讀取端必須一致:附加的條目要真的成為「最新一段」,否則 --append
        # 會把內容寫進一個 --open/is_open 永遠看不到的位置。
        is_newest = "SELFTEST-SENTINEL" in it2.newest_segment
        others = [n for n in before if n != "587" and before[n] != after.get(n)]
        ok6 = seen and is_newest and not others
        print(f"    {'PASS' if ok6 else 'FAIL'}: 新文字可見={seen}, 成為最新一段={is_newest}, "
              f"受影響的其他項目={len(others)}")
        if not ok6:
            fails.append(f"append 往返失敗 seen={seen} newest={is_newest} others={others[:5]}")

    print("\n(7) 分類器:引號內與被否定的『開放』字樣不得算數(今天所有誤判的形狀)")
    cases = [("1069", False, "自陳『本輪未做』…已執行完畢 —— 引號內"),
             ("53", False, "…不是仍待完成的工作 —— 被否定"),
             ("1604", False, "…不是仍待完成的工作 —— 被否定"),
             ("587", False, "自陳『仍缺的一步』已完成 —— 引號內")]
    bad4 = []
    for num, expect_open, why in cases:
        it = next((i for i in items if i.num == num), None)
        got = it.is_open() if it else None
        print(f"    {num}: 期望{'開放' if expect_open else '收斂'} 實得"
              f"{'開放' if got else '收斂'}  ({why})")
        if got != expect_open:
            bad4.append(num)
    # 負向控制:分類器不能是「永遠回傳收斂」。人工造一個真正的開放敘述必須被抓到。
    probe = Item("X", "D", 0, ["X - D - **2026-09-09 本項尚未關閉,缺口仍待完成。**"])
    if not probe.is_open():
        bad4.append("負向控制:真正的開放敘述沒有被判為開放")
        print("    FAIL 負向控制:一句真正的開放敘述被判成收斂")
    else:
        print("    PASS 負向控制:真正的開放敘述仍被判為開放")
    if bad4:
        fails.append(f"分類器誤判:{bad4}")

    if fails:
        print("\nSELFTEST FAILED:")
        for f in fails:
            print("  -", f)
        return 1
    print("\n--selftest passed(5 正向 + 1 故障注入 + 1 往返 + 1 負向控制)。")
    return 0


def main() -> int:
    ap = argparse.ArgumentParser(description=__doc__,
                                 formatter_class=argparse.RawDescriptionHelpFormatter)
    ap.add_argument("--summary", action="store_true")
    ap.add_argument("--open", action="store_true")
    ap.add_argument("--item")
    ap.add_argument("--append")
    ap.add_argument("--text")
    ap.add_argument("--selftest", action="store_true")
    a = ap.parse_args()
    if a.selftest:
        return selftest()
    if a.append:
        if not a.text:
            ap.error("--append 需要 --text")
        return cmd_append(a.append, a.text)
    items = parse()
    if a.item:
        return cmd_item(items, a.item)
    if a.open:
        cmd_open(items)
        return 0
    cmd_summary(items)
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
