#!/usr/bin/env python3
"""fd2_re — 已證實錯誤的位址,在知識庫裡還有多少個「還在拿它當論據」的引用。

為什麼需要這支工具
------------------
`docs/data/known_address_errata.json` 從 2026-08-20 就存在,`query_verified_address.py`
也能查。但**十條驗證軸沒有任何一條讀它**,所以:

* 一個位址被證實錯誤之後,舊的引用不會自己消失,也沒有任何機制會注意到它們還在。
  `91-worklist.md` 在第 1833 行寫著 `0x2a6bd` 的勘誤註記,第 441 行仍以同一個錯誤位址
  立論 —— 同一份檔案、相距 1392 行,中間沒有任何東西把前者接到後者。
* 2026-09-11 doc27 §6.8.4 記下「275 次引用」,是一次性腳本的輸出。同一天用另一個
  pattern 重量一次得到 1044。**兩個都不對**,而且沒有人會發現它們漂移了 —— 這正是
  `verify_findings.py` 當初要消滅的那種數字。

為什麼不能直接用 regex 掃 `wrong_address` 欄位
----------------------------------------------
那個欄位是**自由書寫的散文**,不是機器可讀的欄位。實測兩類偽陽性:

* `0x2bce5` 掃出 628 筆(佔 66%),但該筆勘誤的正文明講「`0x2bce5` 本身作為 ending
  renderer 的存在沒有錯,錯的只是『0x2545d 直接 CALL 它』這條邊」。
* `0x2ff01` 掃出 57 筆,它根本是**正確**位址 —— 它只是出現在另一筆勘誤的說明文字裡
  (「與上一筆 0x27fc9→0x2ff01 是不同的兩件事」),被 regex 一起撈了出來。

所以每筆勘誤必須自己宣告「要掃什麼」。那就是 `citation_check` 區塊:

    "citation_check": {
      "mode": "address" | "edge" | "none",
      "flag":  ["0x2a6bd"],                  # mode=address:這些字面位址本身就是錯的
      "edges": [["0x2545d", "0x2bce5"]],     # mode=edge:兩個位址**相鄰出現**才算錯
      "reason": "...",                       # mode=none:必須說明為什麼掃不了
      "baseline": {"91-worklist.md": 12}     # 每個檔案目前的存量
    }

mode=edge 為什麼還要看距離
--------------------------
只用「同一行」不夠:這個知識庫有大量 300~550 字元的長行,一行裡把五六個位址當成
**各自獨立的事實**並列。實測 `0x25089`/`0x2bce5` 的 10 筆同行命中裡,兩種情況混在一起:

    doc31 L274   `0x25089`(persistent cleanup)→`0x2bce5`(ending renderer)→ self-loop
                 兩者相距 30 字元,這**就是**被推翻的那條邊 -> 要抓

    doc91 L4373  ...`0x25089` persistent cleanup、`0x17aa9` tick、(略 145 字元)...
                 `0x2bce5` 則是獨立收尾的 ending renderer
                 兩者相距 145 字元,是並列的兩個事實,沒有主張誰呼叫誰 -> 不該抓

所以 edge 模式要求兩個位址在 `EDGE_MAX_GAP` 字元內。這兩行都釘在 selftest 裡當地面真相。

**缺少這個區塊的勘誤條目會讓本工具失敗**,而且失敗時不印通過訊息。理由見
`feedback_clean_total_hides_absent_rows`:一筆沒登記的條目和一筆零違規的條目,
在總數裡長得一模一樣;偵測器的輸出必須能**壓掉**那個好看的數字,不能只是擺在旁邊。

豁免判準(兩條都是機械的,不靠人工標註)
--------------------------------------
同一行若滿足任一條,該次引用算 EXEMPT:

1. 這一行同時寫出了對應的**正確位址** —— 訂正跟著引用一起走,讀者不會被誤導。
2. 這一行含勘誤標記字樣(`MARKERS`)。

其餘一律算 ARGUED:文件仍在拿這個位址當論據,而讀者看不到訂正。

棘輪
----
與 `verify_tool_hygiene.py` 同一套規則,**雙向**:
* 某檔 ARGUED 數 **高於** 基準線 -> 失敗(新債)。
* 某檔 ARGUED 數 **低於** 基準線 -> 也失敗(債還了但沒更新基準線)。
所以存量只能往下走,而且每一次下降都會在 commit 裡留下記錄。

用法
----
    python tools/verify_address_citations.py                # 閘門:0 = 沒有新債
    python tools/verify_address_citations.py --report       # 列出每一筆 ARGUED
    python tools/verify_address_citations.py --report --file 91-worklist.md
    python tools/verify_address_citations.py --write-baseline
    python tools/verify_address_citations.py --selftest
"""

from __future__ import annotations

import argparse
import json
import re
import sys
from collections import Counter
from dataclasses import dataclass, field
from pathlib import Path

if hasattr(sys.stdout, "reconfigure"):
    sys.stdout.reconfigure(encoding="utf-8")
    sys.stderr.reconfigure(encoding="utf-8")

ROOT = Path(__file__).resolve().parent.parent
ERRATA = ROOT / "docs" / "data" / "known_address_errata.json"
KB = ROOT / "docs" / "knowledge-base"

MODES = ("address", "edge", "none")

# mode=edge 時兩個位址之間允許的最大字元距離。見模組說明:同一行不足以區分
# 「A 呼叫 B」與「A 是這個、B 是那個」兩種寫法,這個知識庫的長行常達 500 字元。
EDGE_MAX_GAP = 80

# 同一行出現任一個就算「引用時已帶訂正」。刻意維持短小:每多一個詞就多一分把
# 真正的論據行誤放的風險,而 selftest 的負向控制會量測拿掉這串之後 ARGUED 漲多少。
MARKERS = ("勘誤", "訂正", "誤植", "誤記", "無效", "舊位址", "superseded",
           "errata", "不可用", "推翻", "打錯", "抄錯", "已證實錯")


@dataclass
class Spec:
    """一筆勘誤條目要掃描的內容。`index` 是它在 errata 陣列裡的位置。"""

    index: int
    mode: str
    flags: list[str] = field(default_factory=list)
    edges: list[tuple[str, str]] = field(default_factory=list)
    correct: list[str] = field(default_factory=list)
    reason: str = ""
    baseline: dict[str, int] = field(default_factory=dict)
    label: str = ""


@dataclass
class Citation:
    """一次命中。`exempt_by` 非空代表這一行自己帶了訂正。"""

    file: str
    line: int
    spec_index: int
    token: str
    exempt_by: str
    text: str


def normalize(s: str) -> str | None:
    """`0x027fc9` / `0x27FC9` / `27fc9` 都收斂成 `0x27fc9`;壞輸入回 None。

    這個函式是整支工具的比對鍵。它一錯,掃描會**靜默少算**而不是報錯 —— 實測
    errata 檔裡同一個位址同時以 `0x027fc9` 和 `0x27fc9` 兩種寫法出現過。
    """
    s = (s or "").strip()
    if s.lower().startswith("0x"):
        s = s[2:]
    if not s or not re.fullmatch(r"[0-9a-fA-F]+", s):
        return None
    return "0x" + format(int(s, 16), "x")


def _variants(addr: str) -> list[str]:
    """一個正規化位址在文件裡可能的字面寫法(含前導零與大小寫)。"""
    body = addr[2:]
    out = {body, body.upper(), body.zfill(len(body) + 1), body.upper().zfill(len(body) + 1)}
    return ["0x" + v for v in sorted(out)]


def spans(text: str, addr: str) -> list[tuple[int, int]]:
    """`addr` 在這一行的所有出現位置。右邊界必須擋掉 `0x2a6bdf` 這種更長的位址。"""
    out: list[tuple[int, int]] = []
    for v in _variants(addr):
        for m in re.finditer(re.escape(v) + r"(?![0-9a-fA-F])", text, re.IGNORECASE):
            out.append((m.start(), m.end()))
    return sorted(set(out))


def cites(text: str, addr: str) -> bool:
    """這一行是否引用了 `addr`。"""
    return bool(spans(text, addr))


def near(text: str, a: str, b: str, max_gap: int = EDGE_MAX_GAP) -> bool:
    """`a` 與 `b` 是否在同一行且相距不超過 `max_gap` 字元(見模組說明的 edge 模式)。"""
    sa, sb = spans(text, a), spans(text, b)
    if not sa or not sb:
        return False
    return any(max(x[0], y[0]) - min(x[1], y[1]) <= max_gap for x in sa for y in sb)


def exempt_reason(text: str, spec: Spec, use_markers: bool = True,
                  use_correct: bool = True) -> str:
    """回傳豁免理由;沒有豁免則回空字串。

    `use_markers` / `use_correct` 存在**只**為了 selftest 的負向控制:把判準關掉之後
    ARGUED 必須明顯上升,否則這兩條規則是裝飾用的。
    """
    if use_correct:
        for c in spec.correct:
            if cites(text, c):
                return f"同行帶正確位址 {c}"
    if use_markers:
        low = text.lower()
        for m in MARKERS:
            if m.lower() in low:
                return f"同行有勘誤標記「{m}」"
    return ""


def load_errata(path: Path = ERRATA) -> dict:
    with open(path, encoding="utf-8") as f:
        return json.load(f)


def build_specs(errata: dict) -> tuple[list[Spec], list[str]]:
    """把 errata 轉成 Spec。回傳 (specs, problems);problems 非空即為完整性缺口。"""
    specs: list[Spec] = []
    problems: list[str] = []
    for i, e in enumerate(errata.get("errata", [])):
        label = f"#{i} {str(e.get('wrong_address', ''))[:38]}"
        cc = e.get("citation_check")
        if not isinstance(cc, dict):
            problems.append(f"{label}:沒有 citation_check 區塊")
            continue
        mode = cc.get("mode")
        if mode not in MODES:
            problems.append(f"{label}:mode={mode!r} 不在 {MODES}")
            continue

        flags, edges = [], []
        for a in cc.get("flag", []):
            n = normalize(a)
            if n is None:
                problems.append(f"{label}:flag 裡的 {a!r} 不是位址")
            else:
                flags.append(n)
        for pair in cc.get("edges", []):
            ns = [normalize(a) for a in pair]
            if len(ns) != 2 or any(n is None for n in ns):
                problems.append(f"{label}:edges 裡的 {pair!r} 不是一對位址")
            else:
                edges.append((ns[0], ns[1]))

        if mode == "address" and not flags:
            problems.append(f"{label}:mode=address 卻沒有任何 flag")
        if mode == "edge" and not edges:
            problems.append(f"{label}:mode=edge 卻沒有任何 edges")
        if mode == "none" and not (cc.get("reason") or "").strip():
            problems.append(f"{label}:mode=none 必須寫 reason 說明為什麼掃不了")

        correct = [n for n in (normalize(a) for a in
                               re.findall(r"0x[0-9a-fA-F]{4,6}", e.get("correct_address", "")))
                   if n]
        specs.append(Spec(index=i, mode=mode, flags=flags, edges=edges, correct=correct,
                          reason=cc.get("reason", ""), baseline=dict(cc.get("baseline", {})),
                          label=label))
    return specs, problems


def kb_files(kb: Path = KB) -> list[Path]:
    return sorted(p for p in kb.glob("*.md") if p.is_file())


def scan(specs: list[Spec], kb: Path = KB, use_markers: bool = True,
         use_correct: bool = True) -> list[Citation]:
    """掃描全知識庫。同一行對同一個 spec 只記一次,避免同行重複引用膨脹數字。"""
    out: list[Citation] = []
    for path in kb_files(kb):
        try:
            lines = path.read_text(encoding="utf-8", errors="replace").splitlines()
        except OSError:
            continue
        name = path.name
        for lineno, text in enumerate(lines, 1):
            for spec in specs:
                token = ""
                if spec.mode == "address":
                    token = next((a for a in spec.flags if cites(text, a)), "")
                elif spec.mode == "edge":
                    for a, b in spec.edges:
                        if near(text, a, b):
                            token = f"{a}+{b}"
                            break
                if not token:
                    continue
                out.append(Citation(file=name, line=lineno, spec_index=spec.index,
                                    token=token,
                                    exempt_by=exempt_reason(text, spec, use_markers, use_correct),
                                    text=text.strip()[:160]))
    return out


def argued_counts(cits: list[Citation]) -> dict[str, dict[str, int]]:
    """{spec_index(str): {file: argued_count}} —— 基準線就是這個形狀。"""
    per: dict[str, Counter] = {}
    for c in cits:
        if c.exempt_by:
            continue
        per.setdefault(str(c.spec_index), Counter())[c.file] += 1
    return {k: dict(sorted(v.items())) for k, v in sorted(per.items(), key=lambda kv: int(kv[0]))}


def compare(current: dict[str, dict[str, int]],
            specs: list[Spec]) -> tuple[list[str], list[str]]:
    """回傳 (新增的債, 已還但基準線沒更新的)。兩者都算失敗。"""
    worse, better = [], []
    base = {str(s.index): s.baseline for s in specs}
    for key in sorted(set(current) | set(base), key=int):
        cur, old = current.get(key, {}), base.get(key, {})
        for f in sorted(set(cur) | set(old)):
            c, o = cur.get(f, 0), old.get(f, 0)
            if c > o:
                worse.append(f"errata#{key} {f}: {o} -> {c}(+{c - o})")
            elif c < o:
                better.append(f"errata#{key} {f}: {o} -> {c}(-{o - c})")
    return worse, better


def write_baseline(path: Path = ERRATA) -> int:
    errata = load_errata(path)
    specs, problems = build_specs(errata)
    if problems:
        print("無法寫入基準線 —— 先修好這些完整性問題:")
        for p in problems:
            print("  -", p)
        return 1
    cur = argued_counts(scan(specs))
    for s in specs:
        errata["errata"][s.index].setdefault("citation_check", {})["baseline"] = \
            cur.get(str(s.index), {})
    # newline="\n" 是刻意的:`write_text` 在 Windows 會把 \n 換成 \r\n,寫進工作區的
    # 副本就變成 CRLF。git 提交時會正規化所以看不出來,但**工作區那份才是 WSL 實際執行
    # 的檔案** —— 2026-09-11 就是這樣讓兩支工具的 shebang 變成 CRLF、被 hygiene 的
    # shebang 規則擋下。寫 repo 內檔案的工具不要依賴平台預設。
    with open(path, "w", encoding="utf-8", newline="\n") as f:
        f.write(json.dumps(errata, ensure_ascii=False, indent=2) + "\n")
    total = sum(sum(v.values()) for v in cur.values())
    print(f"已寫入基準線:{len(specs)} 筆勘誤,ARGUED 存量共 {total} 筆。")
    return 0


def report(only_file: str | None) -> int:
    errata = load_errata()
    specs, problems = build_specs(errata)
    cits = [c for c in scan(specs) if not c.exempt_by]
    if only_file:
        cits = [c for c in cits if c.file == only_file]
    by_file: dict[str, list[Citation]] = {}
    for c in cits:
        by_file.setdefault(c.file, []).append(c)
    for f in sorted(by_file, key=lambda k: -len(by_file[k])):
        print(f"\n== {f} ({len(by_file[f])} 筆) ==")
        for c in by_file[f]:
            print(f"  {c.line:>5}  [errata#{c.spec_index} {c.token}]  {c.text}")
    print(f"\n共 {len(cits)} 筆 ARGUED 引用。")
    if problems:
        print(f"另有 {len(problems)} 筆勘誤條目沒有 citation_check(見閘門模式)。")
    return 0


def gate() -> int:
    errata = load_errata()
    specs, problems = build_specs(errata)
    cits = scan(specs)
    cur = argued_counts(cits)
    worse, better = compare(cur, specs)

    argued = sum(1 for c in cits if not c.exempt_by)
    exempt = sum(1 for c in cits if c.exempt_by)
    scanned = [s for s in specs if s.mode != "none"]
    print(f"勘誤條目 {len(errata.get('errata', []))} 筆,其中可掃描 {len(scanned)} 筆;"
          f"知識庫 {len(kb_files())} 份文件")
    print(f"命中 {argued + exempt} 筆:ARGUED {argued} / EXEMPT {exempt}")

    # 完整性缺口必須「壓掉」好看的總數,不能只是印在它旁邊。
    if problems:
        print(f"\nFAIL 完整性:{len(problems)} 筆勘誤條目無法掃描")
        for p in problems:
            print("  -", p)
        return 1
    if worse:
        print(f"\nFAIL 新增 {len(worse)} 筆未登錄的引用:")
        for w in worse[:20]:
            print("  +", w)
        return 1
    if better:
        print(f"\nFAIL {len(better)} 筆已經還掉但基準線沒更新"
              f"(請在同一個 commit 跑 --write-baseline):")
        for b in better[:20]:
            print("  -", b)
        return 1
    print("\n沒有新增未登錄的引用,基準線也沒有過期項目。")
    return 0


def selftest() -> int:
    fails: list[str] = []

    print("(1) normalize:各種寫法收斂、壞輸入回 None")
    same = {normalize(v) for v in ("0x027fc9", "0x27FC9", "27fc9", " 0x27fc9 ")}
    bad = [b for b in ("", "zz", "0x", "0xGG", "12 34") if normalize(b) is not None]
    # 前導零這一條有真實來源:errata 檔裡同一個位址寫過 `0x027fc9`,文件裡也有。
    # `_variants` 的 zfill 一旦算錯,掃描會**靜默少算**而不是報錯,所以在這裡釘死。
    pad = (cites("見 `0x027fc9` 這條鏈", "0x27fc9")
           and cites("見 `0x27fc9` 這條鏈", "0x27fc9")
           and not cites("見 `0x0027fc9` 這條鏈", "0x27fc9"))
    ok = (same == {"0x27fc9"} and not bad
          and normalize("0x1000") != normalize("0x1001") and pad)
    print(f"    {'PASS' if ok else 'FAIL'}: {same}, 壞輸入漏放={bad}, 前導零寫法可命中={pad}")
    if not ok:
        fails.append("normalize/_variants 不收斂、壞輸入沒擋掉,或前導零寫法掃不到")

    print("\n(2) 右邊界控制:0x2a6bdf 不可以命中 0x2a6bd")
    ok = cites("看 0x2a6bd 這裡", "0x2a6bd") and not cites("看 0x2a6bdf 這裡", "0x2a6bd")
    print(f"    {'PASS' if ok else 'FAIL'}")
    if not ok:
        fails.append("位址右邊界沒擋住較長的十六進位")

    print("\n(3) 完整性:每筆勘誤都必須有可用的 citation_check")
    errata = load_errata()
    specs, problems = build_specs(errata)
    ok = not problems and len(specs) == len(errata.get("errata", []))
    print(f"    {'PASS' if ok else 'FAIL'}: {len(specs)}/{len(errata.get('errata', []))} 筆可掃描"
          + ("" if ok else f",問題 {problems[:3]}"))
    if not ok:
        fails.append(f"{len(problems)} 筆勘誤條目缺 citation_check")

    print("\n(4) 地面真相:論據行必須 ARGUED,帶訂正的行必須 EXEMPT")
    s = Spec(index=0, mode="address", flags=["0x2a6bd"], correct=["0x2ff01"])
    argued_line = "其他 command 走 `0x2a6bd` → `0x1d6c8` jump-table effect path"
    ex_a = "`0x2a6bd` 已勘誤,應為 `0x2ff01`"
    ex_b = "舊位址 `0x2a6bd`(見 §6.3 訂正)"
    r0 = exempt_reason(argued_line, s)
    r1, r2 = exempt_reason(ex_a, s), exempt_reason(ex_b, s)
    ok = (r0 == "") and r1 and r2
    print(f"    {'PASS' if ok else 'FAIL'}: 論據行豁免={r0!r} / 帶正確位址={bool(r1)} / 帶標記={bool(r2)}")
    if not ok:
        fails.append(f"豁免判準在地面真相上不對:{r0!r}/{r1!r}/{r2!r}")

    print("\n(5) edge 模式控制:這是實測 628 筆偽陽性的來源,必須釘住")
    se = Spec(index=0, mode="edge", edges=[("0x2545d", "0x2bce5"), ("0x25089", "0x2bce5")])
    # 第 4 行是 docs/knowledge-base/31-map-unit-sprites-fdicon.md L274 的原文(相距 30 字元,
    # 主張的正是被推翻的那條邊);第 5 行是 doc91 L4373 那種長行的形狀(相距 >80 字元,
    # 兩個各自獨立的事實並列)。兩者只差在距離,判準必須把它們分開。
    real_edge = "`0x25089`(persistent cleanup)→`0x2bce5`(ending renderer)→ self-loop"
    list_line = ("`0x25089` persistent cleanup、`0x17aa9` tick、dynamic palette loop 等已由 "
                 "runtime adapter 與 regression 覆蓋,另外補上 staged 對應與收尾流程說明;"
                 "`0x2bce5` 則是獨立收尾的 ending renderer")
    lines = ["結局 montage renderer `0x2bce5` 的 frame decoder",
             "`0x2545d` 這個 handler 位址本身沒有錯",
             "`0x2545d` call `0x2bce5` 短路抵達 montage",
             real_edge, list_line]
    hits = scan_text(lines, se)
    # 同一組案例再用**真正從 errata 建出來的 spec** 跑一次。上面那個 se 是手寫的,
    # 所以 `build_specs` 把 edges 組錯(例如兩端取成同一個位址,退化成「只要出現
    # 0x2bce5 就算」)不會被上面那題抓到 —— 那正是 628 筆偽陽性的原形。
    real = next((s for s in specs if s.mode == "edge"), None)
    real_hits = scan_text(lines, real) if real else []
    ok_real = real is not None and real_hits == [3, 4] and all(a != b for a, b in real.edges)
    gap = min(abs(m - n) for m in (x[0] for x in spans(list_line, "0x25089"))
              for n in (y[0] for y in spans(list_line, "0x2bce5")))
    # 參數本身的負向控制:把距離上限放到無限大,被排除的那行必須回來 ——
    # 否則「距離」根本不是做事的那條規則。
    relaxed = near(list_line, "0x25089", "0x2bce5", max_gap=10_000)
    ok = hits == [3, 4] and gap > EDGE_MAX_GAP and relaxed and ok_real
    print(f"    {'PASS' if ok else 'FAIL'}: 命中行號={hits}(應為 [3, 4]);"
          f"並列行距離={gap}>{EDGE_MAX_GAP};放寬上限後回來={relaxed};"
          f"errata 實建 spec 一致={ok_real}")
    if not ok:
        fails.append(f"edge 模式的距離/配對判準不對:命中={hits}, gap={gap}, "
                     f"relaxed={relaxed}, 實建 spec={real_hits}")

    print("\n(6) 負向控制:關掉豁免判準,ARGUED 必須明顯上升")
    full = scan(specs)
    base_argued = sum(1 for c in full if not c.exempt_by)
    no_rule = scan(specs, use_markers=False, use_correct=False)
    off_argued = sum(1 for c in no_rule if not c.exempt_by)
    ok = off_argued > base_argued and base_argued > 0
    print(f"    {'PASS' if ok else 'FAIL'}: 判準開 ARGUED={base_argued},"
          f"判準關 ARGUED={off_argued}(+{off_argued - base_argued})")
    if base_argued == 0:
        fails.append("實際掃描 ARGUED=0 —— 這題是空的,不算通過")
    elif not ok:
        fails.append("拿掉豁免判準後 ARGUED 沒有上升 —— 判準是裝飾用的")

    print("\n(7) 非恆真:實際掃描必須真的命中知識庫")
    ok = len(full) > 0 and len({c.file for c in full}) > 1
    print(f"    {'PASS' if ok else 'FAIL'}: 命中 {len(full)} 筆,分布 {len({c.file for c in full})} 份文件")
    if not ok:
        fails.append("掃描沒有命中任何文件 —— 路徑或判準壞了")

    print("\n(8) 棘輪雙向:超標與低於基準線都必須失敗")
    sp = [Spec(index=0, mode="address", flags=["0x1234"], baseline={"a.md": 5})]
    w1, b1 = compare({"0": {"a.md": 6}}, sp)
    w2, b2 = compare({"0": {"a.md": 4}}, sp)
    w3, b3 = compare({"0": {"a.md": 5}}, sp)
    ok = bool(w1) and not b1 and bool(b2) and not w2 and not w3 and not b3
    print(f"    {'PASS' if ok else 'FAIL'}: 6>5 -> 新債={bool(w1)};4<5 -> 過期={bool(b2)};5=5 -> 乾淨={not w3 and not b3}")
    if not ok:
        fails.append("棘輪不是雙向的")

    print("\n(9) 未登錄條目必須壓掉通過訊息(不能兩句真話並排)")
    src = Path(__file__).read_text(encoding="utf-8")
    gate_src = src[src.index("def gate("):src.index("def selftest(")]
    ok = gate_src.index("if problems:") < gate_src.index("沒有新增未登錄的引用")
    print(f"    {'PASS' if ok else 'FAIL'}: 完整性檢查在通過訊息之前 return")
    if not ok:
        fails.append("completeness 缺口沒有擋在通過訊息前面")

    if fails:
        print("\nSELFTEST FAILED:")
        for f in fails:
            print("  -", f)
        return 1
    print("\n--selftest passed(9 項:正規化 + 右邊界 + 完整性 + 地面真相 + edge 控制 + "
          "負向控制 + 非恆真 + 雙向棘輪 + 總數壓制)。")
    return 0


def scan_text(lines: list[str], spec: Spec) -> list[int]:
    """對一組字串跑與 `scan` 相同的命中判定,回傳命中的行號(1-based)。selftest 用。"""
    hit = []
    for i, text in enumerate(lines, 1):
        if spec.mode == "address":
            if any(cites(text, a) for a in spec.flags):
                hit.append(i)
        elif spec.mode == "edge":
            if any(near(text, a, b) for a, b in spec.edges):
                hit.append(i)
    return hit


def main() -> int:
    ap = argparse.ArgumentParser(description="已證實錯誤的位址在知識庫裡的存活引用掃描")
    ap.add_argument("--report", action="store_true", help="列出每一筆 ARGUED 引用")
    ap.add_argument("--file", help="--report 時只看這一份文件")
    ap.add_argument("--write-baseline", action="store_true", help="把目前存量寫回 errata 檔")
    ap.add_argument("--selftest", action="store_true")
    args = ap.parse_args()

    if args.selftest:
        return selftest()
    if args.write_baseline:
        return write_baseline()
    if args.report:
        return report(args.file)
    return gate()


if __name__ == "__main__":
    sys.exit(main())
