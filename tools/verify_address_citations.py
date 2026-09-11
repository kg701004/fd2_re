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
    python tools/verify_address_citations.py --diff              # 源頭閘門(pre-commit)
    python tools/verify_address_citations.py --mark-correction <檔> <行> <verdict> <理由>
    python tools/verify_address_citations.py --selftest

源頭閘門 `--diff`
-----------------
上面的棘輪管的是**已登記**勘誤的引用。但知識庫裡「同時含訂正措辭與位址」的行有
110 行、涉及 250 個相異位址,登記表只登記了 22 個(**約 8%**)—— 絕大多數位址訂正
從來只以散文存在,因為流程裡沒有「發現位址錯了就登記」那一步。`--diff` 補的就是
那一步:新增一行訂正措辭 + 位址,就必須同時登記,或用 `--mark-correction` 明確宣告
被訂正的不是位址本身(例如「handler export 的 PUSH 順序」)。它不處理存量,只讓
存量停止增長。
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


# ---------------------------------------------------------------------------
# 位址訂正的「源頭閘門」:讓訂正在寫下的當下就變成資料,而不是事後考古
# ---------------------------------------------------------------------------
#
# 2026-09-11 量到的根本問題:知識庫裡「同時含訂正措辭與位址」的行有 **110 行、
# 分佈 20 份文件、涉及 250 個相異位址**,而 `known_address_errata.json` 只登記了
# 15 筆條目 / 22 個位址 —— **約 8%**。
#
# 這不是有人偷懶,是**流程裡沒有那一步**:發現位址錯了的人,就在當下正在編輯的那份
# 文件裡寫一句話。登記表是專案開始兩個月後才補建的,所以要補完就只能對散文做考古。
# 而對散文做考古,正是本檔開頭那段說明裡診斷過的、`wrong_address` 欄位不可機器消費
# 的同一件事 —— 同一個錯誤換個對象再做一次。
#
# 所以這道閘門**不處理存量**(110 行是一次性的考古債,可以慢慢還),它只做一件事:
# **讓存量停止增長**。新增一行訂正措辭 + 位址,就必須同時登記,或明確宣告它不是位址勘誤。
#
# 為什麼需要「宣告不是位址勘誤」這條路:實測 `0x35822` 那行寫著「**已證實的勘誤**:
# `0x35822` 的 handler export 保存來源 `PUSH` 順序」—— 訂正措辭確實指向這個位址,
# 但被訂正的是**PUSH 順序**不是位址值。分辨這兩者要讀懂主張,不是讀懂用了哪些詞,
# 任何詞彙層的工具都做不到,所以留一條可審查的人工出口。

CORRECTION_WORDS = re.compile(
    r"位址勘誤|位址更正|位址訂正|原標|原記|誤植|誤記|應為|實際(?:是|應)|改為")

REVIEWS = ROOT / "docs" / "data" / "correction_line_reviews.json"
VERDICTS = ("not_address_erratum", "restates_existing")


def _audit_mod():
    """借用 `audit_evidence_provenance` 的未追蹤檔案處理與摘要雜湊。

    刻意不自己重寫:那支工具已經踩過「`git diff` 完全不含未追蹤檔案,一份全新的
    文件會整份繞過閘門」這個洞(2026-09-10)。兩邊各寫一份必然漂移。
    """
    import audit_evidence_provenance as A
    return A


def added_kb_lines(base: str = "HEAD") -> list[tuple[str, int, str]]:
    """`git diff <base>` 裡**新增**的 knowledge-base 行 -> (檔名, 行號, 原文)。

    行號必須靠 `@@ ... +start,count @@` 追蹤,不能用序號累加 —— 一個 hunk 不一定
    從檔案開頭起算。selftest 第 (10) 題用一個起點非 1 的合成 diff 釘住這件事。
    """
    import subprocess
    A = _audit_mod()
    r = subprocess.run(["git", "diff", "--unified=0", base, "--",
                        "docs/knowledge-base/*.md"],
                       cwd=str(ROOT), capture_output=True, text=True,
                       encoding="utf-8", errors="replace")
    return parse_added(((r.stdout or "") + A._untracked_as_diff()))


def parse_added(diff_text: str) -> list[tuple[str, int, str]]:
    out: list[tuple[str, int, str]] = []
    cur_file, cur_line = None, None
    for raw in diff_text.splitlines():
        if raw.startswith("+++ b/"):
            cur_file = Path(raw[6:]).name
            continue
        m = re.match(r"^@@ -\d+(?:,\d+)? \+(\d+)(?:,\d+)? @@", raw)
        if m:
            cur_line = int(m.group(1))
            continue
        if raw.startswith("+++") or raw.startswith("---"):
            continue
        if raw.startswith("+"):
            if cur_file is not None and cur_line is not None:
                out.append((cur_file, cur_line, raw[1:]))
                cur_line += 1
    return out


def load_reviews() -> set[tuple[str, str]]:
    try:
        with open(REVIEWS, encoding="utf-8") as f:
            return {(e["file"], e["excerpt_sha1"]) for e in json.load(f)["entries"]}
    except (OSError, ValueError, KeyError):
        return set()


def correction_debt(base: str = "HEAD") -> list[dict]:
    """新增的、含訂正措辭與位址、卻既沒登記也沒宣告的行。"""
    A = _audit_mod()
    flagged = set()
    for e in load_errata().get("errata", []):
        for a in (e.get("citation_check") or {}).get("flag", []):
            n = normalize(a)
            if n:
                flagged.add(n)
    reviewed = load_reviews()
    out = []
    for name, lineno, text in added_kb_lines(base):
        if not CORRECTION_WORDS.search(text):
            continue
        addrs = {normalize(a) for a in re.findall(r"0x[0-9a-fA-F]{4,6}(?![0-9a-fA-F])", text)}
        addrs.discard(None)
        if not addrs:
            continue
        if addrs & flagged:
            continue                       # 該行提到的位址已在登記表裡 -> 已覆蓋
        if (name, A._sha(text.strip()[:200])) in reviewed:
            continue                       # 已明確宣告「不是位址勘誤」
        out.append({"file": name, "line": lineno, "text": text.strip()[:160],
                    "addrs": sorted(a for a in addrs if a)})
    return out


def gate_diff(base: str = "HEAD") -> int:
    debt = correction_debt(base)
    if not debt:
        print("diff 檢查通過:沒有新增「寫了訂正卻沒登記」的行。")
        return 0
    print(f"FAIL 新增 {len(debt)} 行寫下了位址訂正,但既沒登記進 "
          f"known_address_errata.json,也沒宣告它不是位址勘誤:\n")
    for d in debt[:15]:
        print(f"  {d['file']}:{d['line']}  {d['addrs']}")
        print(f"      {d['text']}")
    print("\n處置二選一:")
    print("  (a) 在 known_address_errata.json 新增一筆(含 citation_check),再跑 "
          "--write-baseline;")
    print("  (b) 若被訂正的不是位址本身(例如『PUSH 順序』),用 "
          "--mark-correction <檔> <行> <verdict> <理由> 宣告,"
          f"verdict ∈ {VERDICTS}。")
    return 1


def mark_correction(name: str, lineno: str, verdict: str, note: str) -> int:
    A = _audit_mod()
    if verdict not in VERDICTS:
        print(f"verdict 必須是 {VERDICTS} 之一,收到 {verdict!r}")
        return 1
    if not note.strip():
        print("必須寫理由 —— 沒有理由的豁免等於沒有這道閘門")
        return 1
    try:
        ln = int(lineno)
    except ValueError:
        print(f"行號無法解析:{lineno!r}")
        return 1
    path = KB / name
    try:
        lines = path.read_text(encoding="utf-8", errors="replace").splitlines()
    except OSError:
        print(f"讀不到 {path}")
        return 1
    if not 1 <= ln <= len(lines):
        print(f"{name} 只有 {len(lines)} 行,給了 {ln}")
        return 1
    text = lines[ln - 1].strip()
    if not CORRECTION_WORDS.search(text):
        print(f"{name}:{ln} 不含訂正措辭,不需要宣告")
        return 1
    try:
        with open(REVIEWS, encoding="utf-8") as f:
            data = json.load(f)
    except (OSError, ValueError):
        data = {"_meta": {
            "purpose": "被 tools/verify_address_citations.py --diff 用來放行的『這行寫了訂正,"
                       "但被訂正的不是位址本身』宣告。key 是 (file, excerpt_sha1) —— "
                       "內容導向,行號漂移不影響。",
            "schema_version": 1}, "entries": []}
    key = (name, A._sha(text[:200]))
    if any((e["file"], e["excerpt_sha1"]) == key for e in data["entries"]):
        print("這一行已經登錄過了")
        return 0
    data["entries"].append({"file": name, "excerpt_sha1": A._sha(text[:200]),
                            "excerpt": text[:120], "verdict": verdict, "note": note})
    with open(REVIEWS, "w", encoding="utf-8", newline="\n") as f:
        f.write(json.dumps(data, ensure_ascii=False, indent=1) + "\n")
    print(f"已登錄 {name}:{ln}({verdict})")
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

    print("\n(10) 源頭閘門的 diff 解析:行號必須靠 @@ 標頭,不能用序號累加")
    # 一個 hunk 不一定從檔案開頭起算。這裡的合成 diff 起點是 207,若改用序號累加
    # 會得到 1/2,這題就會失敗。
    synth = ("+++ b/docs/knowledge-base/zz.md\n"
             "@@ -0,0 +207,2 @@\n"
             "+第一行 誤植 `0x11111`\n"
             "+第二行 應為 `0x22222`\n")
    got = parse_added(synth)
    ok10 = got == [("zz.md", 207, "第一行 誤植 `0x11111`"),
                   ("zz.md", 208, "第二行 應為 `0x22222`")]
    print(f"    {'PASS' if ok10 else 'FAIL'}: {got}")
    if not ok10:
        fails.append(f"diff 加號行的行號解析不對:{got}")

    print("\n(11) 源頭閘門的三條路:未登記要擋、已登記要放、已宣告要放")
    # 這三題用同一行文字、只換條件,所以差異只能來自判定本身。
    flagged = {"0x2a6bd"}          # 已登記的(errata 實際有這一筆)
    def would_block(text, reviewed_keys=frozenset(), flag=flagged):
        if not CORRECTION_WORDS.search(text):
            return False
        ad = {normalize(a) for a in re.findall(r"0x[0-9a-fA-F]{4,6}(?![0-9a-fA-F])", text)}
        ad.discard(None)
        if not ad:
            return False
        if ad & flag:
            return False
        return ("x.md", _audit_mod()._sha(text.strip()[:200])) not in reviewed_keys
    unreg = "本節原標 handler `0x9abcd`,誤植"
    reg = "本節原標 handler `0x2a6bd`,誤植"
    noaddr = "這裡原標的順序誤植了,與位址無關"
    key = {("x.md", _audit_mod()._sha(unreg[:200]))}
    a11 = would_block(unreg)
    b11 = would_block(reg)
    c11 = would_block(unreg, reviewed_keys=key)
    d11 = would_block(noaddr)
    ok11 = a11 and not b11 and not c11 and not d11
    print(f"    {'PASS' if ok11 else 'FAIL'}: 未登記擋={a11}、已登記放={not b11}、"
          f"已宣告放={not c11}、無位址不管={not d11}")
    if not ok11:
        fails.append(f"源頭閘門三條路不對:{a11}/{b11}/{c11}/{d11}")

    print("\n(13) 距離門檻的**兩側**:恰好 EDGE_MAX_GAP 要過、多一個字元就不過")
    # 突變測試發現:`max(x[0], y[0]) - min(x[1], y[1])` 裡的索引被改掉也逃得掉,
    # 因為地面真相的兩個案例(相距 30 與 123)離門檻 80 太遠,位移幾個字元不會翻轉。
    # 這裡直接造出恰好落在門檻兩側的案例,把算術本身釘住。
    A_, B_ = "0x2545d", "0x2bce5"
    # 不加反引號:這樣 A 的 span 是 (0,7)、B 的起點是 7+g,實際 gap 恰好等於 g。
    # (第一版用 `` `0x2545d` `` 包起來,反引號讓實際 gap 多了 2,兩側都變成 False ——
    #  夾具自己算錯,不是程式碼錯。所以下面順便把實測 gap 印出來驗夾具。)
    def line_with_gap(g):
        return A_ + ("-" * g) + B_
    probe_line = line_with_gap(EDGE_MAX_GAP)
    real_gap = spans(probe_line, B_)[0][0] - spans(probe_line, A_)[0][1]
    at = near(probe_line, A_, B_)
    over = near(line_with_gap(EDGE_MAX_GAP + 1), A_, B_)
    ok13 = at and not over and real_gap == EDGE_MAX_GAP
    print(f"    {'PASS' if ok13 else 'FAIL'}: 夾具實測 gap={real_gap}(應={EDGE_MAX_GAP});"
          f"恰好命中={at}、多一個字元命中={over}(應為 True / False)")
    # **順序對稱性**:B 寫在 A 前面時,距離必須算出同一個值。突變測試顯示
    # `max(x[0], y[0])` 的索引被改掉,在「A 在前」的案例裡完全等價(兩邊都取到後者的
    # 起點),只有**反序**才分得出來 —— 會差一個 token 的長度(7 字元)。
    rev_at = near(B_ + ("-" * EDGE_MAX_GAP) + A_, A_, B_)
    rev_over = near(B_ + ("-" * (EDGE_MAX_GAP + 1)) + A_, A_, B_)
    ok13 = ok13 and rev_at and not rev_over
    print(f"           反序(B 在前):恰好命中={rev_at}、多一個字元命中={rev_over}")
    if real_gap != EDGE_MAX_GAP:
        fails.append(f"夾具本身算錯:實測 gap={real_gap} != {EDGE_MAX_GAP}")
    elif not ok13:
        fails.append(f"距離門檻兩側不對:正序 {at}/{over}、反序 {rev_at}/{rev_over}")

    print("\n(14) **真正的 scan() 路徑**必須對每一種 mode 都產出命中")
    # 突變測試發現:`elif spec.mode == "edge"` 改成 `!=`,edge 模式在真正的 scan()
    # 裡整個失效,而第 (5) 題走的是 scan_text()(手寫 spec),完全感覺不到。
    modes_present = {s.mode for s in specs if s.mode != "none"}
    hit_modes = {next(s.mode for s in specs if s.index == c.spec_index) for c in full}
    missing = modes_present - hit_modes
    ok14 = not missing and "edge" in hit_modes
    print(f"    {'PASS' if ok14 else 'FAIL'}: 登記的 mode {sorted(modes_present)}、"
          f"實掃命中的 mode {sorted(hit_modes)}")
    if not ok14:
        fails.append(f"真正的 scan() 對這些 mode 沒有任何命中:{sorted(missing)}")

    print("\n(12) 非恆真:訂正措辭必須真的能在知識庫裡命中")
    hits = 0
    for p in kb_files():
        for line in p.read_text(encoding="utf-8", errors="replace").splitlines():
            if CORRECTION_WORDS.search(line) and re.search(r"0x[0-9a-fA-F]{4,6}", line):
                hits += 1
    ok12 = hits > 20
    print(f"    {'PASS' if ok12 else 'FAIL'}: 全庫命中 {hits} 行(2026-09-11 實測 110)")
    if not ok12:
        fails.append(f"訂正措辭幾乎命中不到東西({hits} 行)—— 這道閘門會是裝飾")

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
    print("\n--selftest passed(14 項:正規化 + 右邊界 + 完整性 + 地面真相 + edge 控制 + "
          "負向控制 + 非恆真 + 雙向棘輪 + 總數壓制 + diff 行號 + 源頭閘門三條路 + "
          "訂正措辭非恆真 + 距離門檻兩側 + scan 對每種 mode 都有命中)。")
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
    ap.add_argument("--diff", nargs="?", const="HEAD", metavar="BASE",
                    help="源頭閘門:新增的訂正行必須已登記或已宣告(預設對 HEAD)")
    ap.add_argument("--mark-correction", nargs=4,
                    metavar=("FILE", "LINE", "VERDICT", "NOTE"),
                    help=f"宣告某行的訂正對象不是位址本身;VERDICT ∈ {VERDICTS}")
    ap.add_argument("--selftest", action="store_true")
    args = ap.parse_args()

    if args.selftest:
        return selftest()
    if args.mark_correction:
        return mark_correction(*args.mark_correction)
    if args.diff:
        return gate_diff(args.diff)
    if args.write_baseline:
        return write_baseline()
    if args.report:
        return report(args.file)
    return gate()


if __name__ == "__main__":
    sys.exit(main())
