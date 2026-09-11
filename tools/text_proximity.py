#!/usr/bin/env python3
"""fd2_re — 共用的「兩個東西在同一行裡是不是離得夠近」判準。

為什麼需要這支模組
------------------
2026-09-11 同一天,同一個形狀的判準被各自獨立寫了三次:

  1. `verify_address_citations.py` 的 `mode=edge` —— 兩個**位址**要不要算同一條
     被推翻的呼叫邊,實測不看距離會把 `0x2bce5` 誤抓成 628 筆偽陽性。
  2. `verify_address_claim_coverage.py` 那輪對「已標訂正未登記」的 59 筆抽查 ——
     判準只在對話裡手算過(位址 span 到最近勘誤字樣 span 的距離),從未寫進程式碼。
  3. `verify_address_citations.py --diff` 的 `correction_debt()` —— 判準原本只檢查
     「這一行**同時**含勘誤措辭與位址」,完全沒有距離,是 (1) 那個偽陽性問題的
     同一個 bug,只是換了個對象。**用真實資料驗證過**:今天被這個洞誤擋下的
     `91-worklist.md:446`,三個位址與最近的勘誤措辭都相距 98~260 字元
     (遠超 80 的門檻);而真陽性案例(注入測試)相距只有 2~3 字元 —— 加上距離
     判準,前者不再需要 `--mark-correction`,後者仍然抓得到。

這個知識庫有大量 300~550 字元的長行,一行裡把五六個位址/措辭當成**各自獨立的
事實**並列,「同一行」不足以當作關聯判準。本模組把「兩組文字位置是否相鄰」抽成
一個共用、獨立驗證過的判準,新判準只需要呼叫它,不必重新發明。

核心 API
--------
    normalize_addr(s)              位址字串正規化(大小寫/前導零收斂),壞輸入回 None
    address_spans(text, addr)      `addr` 在 `text` 裡所有出現位置(含各種寫法)
    regex_spans(text, pattern)     任意已編譯 regex 在 `text` 裡的所有出現位置
    gap(spans_a, spans_b)          兩組位置之間的最小字元距離;任一組為空回 None
    near(spans_a, spans_b, max_gap)  是否有一對距離 <= max_gap
    addresses_near(text, a, b, max_gap=DEFAULT_MAX_GAP)   兩個位址的便利包裝
    ADDR_RE                        「文字裡的位址字面」通用 regex(不含變體展開)
    DEFAULT_MAX_GAP = 80           見上面「為什麼」段落的實測依據

用法
----
    python tools/text_proximity.py --selftest
"""

from __future__ import annotations

import re
import sys

if hasattr(sys.stdout, "reconfigure"):
    sys.stdout.reconfigure(encoding="utf-8")
    sys.stderr.reconfigure(encoding="utf-8")

# 「文字裡的位址字面」通用 regex —— 找存在性用(不管寫法變體),與 `address_spans`
# 的用途不同(`address_spans` 是「這個*已知*位址在文字裡的所有寫法命中哪裡」)。
# 字元類 `[0-9a-fA-F]` 本身就不分大小寫,不需要 re.IGNORECASE。
ADDR_RE = re.compile(r"0x[0-9a-fA-F]{4,6}(?![0-9a-fA-F])")

DEFAULT_MAX_GAP = 80


def normalize_addr(s: str) -> str | None:
    """`0x027fc9` / `0x27FC9` / `27fc9` 都收斂成 `0x27fc9`;壞輸入回 None。

    這是整條鏈的比對鍵。它一錯,呼叫端會**靜默少算**而不是報錯 —— 實測
    `known_address_errata.json` 裡同一個位址同時以 `0x027fc9` 和 `0x27fc9` 出現過。
    """
    s = (s or "").strip()
    if s.lower().startswith("0x"):
        s = s[2:]
    if not s or not re.fullmatch(r"[0-9a-fA-F]+", s):
        return None
    return "0x" + format(int(s, 16), "x")


def address_variants(addr: str) -> list[str]:
    """一個正規化位址在文件裡可能的字面寫法(含前導零與大小寫)。"""
    body = addr[2:]
    out = {body, body.upper(), body.zfill(len(body) + 1), body.upper().zfill(len(body) + 1)}
    return ["0x" + v for v in sorted(out)]


def address_spans(text: str, addr: str) -> list[tuple[int, int]]:
    """`addr` 在這一行的所有出現位置(含各種寫法)。右邊界擋掉 `0x2a6bdf` 這種更長的位址。"""
    out: list[tuple[int, int]] = []
    for v in address_variants(addr):
        for m in re.finditer(re.escape(v) + r"(?![0-9a-fA-F])", text, re.IGNORECASE):
            out.append((m.start(), m.end()))
    return sorted(set(out))


def regex_spans(text: str, pattern: re.Pattern) -> list[tuple[int, int]]:
    """任意已編譯 regex 在 `text` 裡的所有出現位置。"""
    return [m.span() for m in pattern.finditer(text)]


def gap(spans_a: list[tuple[int, int]], spans_b: list[tuple[int, int]]) -> int | None:
    """兩組位置之間的最小字元距離。任一組為空回 None(不是 0 —— 0 會被誤讀成「緊貼著」)。

    負值代表兩個 span 重疊,視為距離 0 以下、必然算相鄰(`near()` 的 `<= max_gap`
    對負值自然成立,不需要另外 clamp)。
    """
    if not spans_a or not spans_b:
        return None
    return min(max(x[0], y[0]) - min(x[1], y[1]) for x in spans_a for y in spans_b)


def near(spans_a: list[tuple[int, int]], spans_b: list[tuple[int, int]],
         max_gap: int = DEFAULT_MAX_GAP) -> bool:
    """兩組位置裡,是否存在一對距離 <= max_gap。"""
    g = gap(spans_a, spans_b)
    return g is not None and g <= max_gap


def addresses_near(text: str, a: str, b: str, max_gap: int = DEFAULT_MAX_GAP) -> bool:
    """便利包裝:兩個位址在同一行是否相鄰。"""
    return near(address_spans(text, a), address_spans(text, b), max_gap)


def selftest() -> int:
    fails: list[str] = []

    print("(1) normalize_addr:各種寫法收斂、壞輸入回 None")
    same = {normalize_addr(v) for v in ("0x027fc9", "0x27FC9", "27fc9", " 0x27fc9 ")}
    bad = [b for b in ("", "zz", "0x", "0xGG", "12 34") if normalize_addr(b) is not None]
    ok = same == {"0x27fc9"} and not bad and normalize_addr("0x1000") != normalize_addr("0x1001")
    print(f"    {'PASS' if ok else 'FAIL'}: {same}, 壞輸入漏放={bad}")
    if not ok:
        fails.append("normalize_addr 不收斂或壞輸入沒擋掉")

    print("\n(2) address_spans 右邊界:0x2a6bdf 不可以命中 0x2a6bd")
    ok = (bool(address_spans("看 0x2a6bd 這裡", "0x2a6bd"))
          and not address_spans("看 0x2a6bdf 這裡", "0x2a6bd"))
    print(f"    {'PASS' if ok else 'FAIL'}")
    if not ok:
        fails.append("位址右邊界沒擋住較長的十六進位")

    print("\n(2b) address_variants 的前導零寫法必須真的命中,且**不多不少剛好一位**")
    # `zfill(len(body)+1)` 補到「原長度+1」是刻意的:這個知識庫實測同一個位址同時
    # 以 `0x27fc9`(5 碼)與 `0x027fc9`(補到 6 碼)兩種寫法出現過。改成 +2 會補成
    # 7 碼(`0x0027fc9`),文件裡的 6 碼寫法就抓不到 —— 這裡同時測「補 1 位要中」
    # 與「補 2 位不該是預設命中對象」,不能只測前者(那樣 +1/+2 都能過)。
    ok = (bool(address_spans("見 `0x027fc9` 這條鏈", "0x27fc9"))
          and not address_spans("見 `0x0027fc9` 這條鏈", "0x27fc9"))
    print(f"    {'PASS' if ok else 'FAIL'}: 補 1 位(0x027fc9)命中={bool(address_spans('見 `0x027fc9` 這條鏈', '0x27fc9'))}、"
          f"補 2 位(0x0027fc9)不誤命中={not address_spans('見 `0x0027fc9` 這條鏈', '0x27fc9')}")
    if not ok:
        fails.append("前導零補位數不對 —— 補 1 位的真實寫法掃不到,或補 2 位被誤當成命中")

    print("\n(3) near() 距離門檻的兩側,用**純 span**(不依賴位址正規化)直接釘住算術")
    # 恰好等於門檻要過、多 1 要不過;兩種順序(a 在前 / b 在前)都要對稱。
    g = 80
    fwd_at = near([(0, 5)], [(5 + g, 5 + g + 5)], max_gap=g)
    fwd_over = near([(0, 5)], [(6 + g, 6 + g + 5)], max_gap=g)
    rev_at = near([(5 + g, 5 + g + 5)], [(0, 5)], max_gap=g)
    rev_over = near([(6 + g, 6 + g + 5)], [(0, 5)], max_gap=g)
    ok = fwd_at and not fwd_over and rev_at and not rev_over
    print(f"    {'PASS' if ok else 'FAIL'}: 正序 恰好={fwd_at}/多1={fwd_over}、"
          f"反序 恰好={rev_at}/多1={rev_over}(應為 True/False/True/False)")
    if not ok:
        fails.append(f"near() 距離算術不對:{fwd_at}/{fwd_over}/{rev_at}/{rev_over}")

    print("\n(4) gap():任一組為空必須回 None,不能回 0(0 會被誤讀成『緊貼著』)")
    ok = gap([], [(0, 1)]) is None and gap([(0, 1)], []) is None and gap([], []) is None
    print(f"    {'PASS' if ok else 'FAIL'}")
    if not ok:
        fails.append("空 span 組沒有回 None")

    print("\n(5) 重疊的 span 必須算相鄰(負距離也要通過 near())")
    ok = near([(0, 10)], [(5, 15)], max_gap=0)
    print(f"    {'PASS' if ok else 'FAIL'}: gap={gap([(0, 10)], [(5, 15)])}")
    if not ok:
        fails.append("重疊 span 沒有被判為相鄰")

    print("\n(6) addresses_near:真實案例的正負向配對(2026-09-11 實測)")
    # 正向:被今天的洞誤擋過的假陽性,相距 98~260 字元,遠超門檻。
    false_pos = ("...`0x35822`(persistent…)已由 runtime adapter 覆蓋,"
                 + "填充" * 30 + "而『位址訂正』說明見下方章節,`0x9999a` 是另一件事")
    fp_near = addresses_near(false_pos, "0x35822", "0x9999a")
    # 負向:注入測試的真陽性形狀,相距 2~3 字元。
    true_pos = "本節原標 handler `0x9abcd`,誤植,實際應為 `0x9dcba`。"
    tp_near = addresses_near(true_pos, "0x9abcd", "0x9dcba")
    ok = (not fp_near) and tp_near
    print(f"    {'PASS' if ok else 'FAIL'}: 假陽性形狀相鄰={fp_near}(應 False)、"
          f"真陽性形狀相鄰={tp_near}(應 True)")
    if not ok:
        fails.append(f"真實案例配對不對:假陽性={fp_near}, 真陽性={tp_near}")

    print("\n(7) regex_spans:位置必須能反過來從原文切出同一段字")
    # 不手算期望的 (start, end) —— 今天已經在別的夾具上手算錯過一次;這裡改成
    # 用結果反查回原文,任何算法錯誤都會讓切出來的字串跟比對到的字串對不上。
    pat = re.compile(r"誤植|應為")
    probe7 = "本節原標 handler,誤植,實際應為修正"
    got = regex_spans(probe7, pat)
    sliced = [probe7[s:e] for s, e in got]
    ok = len(got) == 2 and sliced == [m.group() for m in pat.finditer(probe7)]
    print(f"    {'PASS' if ok else 'FAIL'}: 位置={got},切回原文={sliced}")
    if not ok:
        fails.append(f"regex_spans 位置不對:{got} -> {sliced}")

    if fails:
        print("\nSELFTEST FAILED:")
        for f in fails:
            print("  -", f)
        return 1
    print("\n--selftest passed(8 項:正規化 + 右邊界 + 前導零補位數 + 距離算術兩側對稱 + "
          "空集合 + 重疊相鄰 + 真實案例正負配對 + regex_spans 位置)。")
    return 0


def main(argv: list[str]) -> int:
    if len(argv) == 2 and argv[1] == "--selftest":
        return selftest()
    print(__doc__)
    return 1


if __name__ == "__main__":
    sys.exit(main(sys.argv))
