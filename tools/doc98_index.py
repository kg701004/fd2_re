#!/usr/bin/env python3
"""fd2_re — doc98(研究工具基礎建設)的主題索引:`docs/knowledge-base/98-index.md` 由本工具產生並檢查。

為什麼要有
----------
`98-tooling-infrastructure.md` 已超過一萬行、180 多節,一節接一節按時間往下長。要找「某件事在哪一輪做的」
只能 grep 標題猜關鍵字;標題沒寫到那個關鍵字就找不到。這裡把每一節歸到主題(問題導向,同 `00-index.md`),
並附上行號,讀的人(多半是 agent)直接用行號跳過去讀那一節。

索引是產生的,不是手寫的:主題由下面 `TOPICS` 的規則決定(標題的關鍵字,或「續 N」的編號範圍)。
`--check` 會抓三件事,任何一件都 exit 1:
  * 孤兒節:有一節沒有落在任何主題 —— 新增一節時要嘛標題帶到既有主題的關鍵字,要嘛在這裡補規則;
  * 沒命中的規則:某條規則一節都沒對到(規則寫錯或那節改了標題);
  * 已提交的 98-index.md 與重算結果不同(行號移動、標題改了、新的一節還沒寫進索引)。
程式碼區塊(``` 之間)裡的 `## ` 不算標題。

每個條目後面的〔來源:…〕是該節本文(到下一個二級標題前)裡出現的原版側來源字樣,用的是
`audit_evidence_provenance.py` 同一張標記表(不含裸位址),取實際命中的字樣而不是標籤 —— 所以索引行本身
也過得了那支稽核的 `--diff`;本文沒有任何來源字樣的節不加標註,照樣會被稽核點名(問題在那一節,不在索引)。

用法
----
    python tools/doc98_index.py              # 印出索引(不寫檔)
    python tools/doc98_index.py --write      # 重寫 docs/knowledge-base/98-index.md
    python tools/doc98_index.py --check      # 閘門:孤兒節 / 沒命中的規則 / 內容不同都 exit 1
    python tools/doc98_index.py --selftest
"""
from __future__ import annotations

import argparse
import re
import sys
import tempfile
from pathlib import Path

if hasattr(sys.stdout, "reconfigure"):
    sys.stdout.reconfigure(encoding="utf-8")
    sys.stderr.reconfigure(encoding="utf-8")

ROOT = Path(__file__).resolve().parents[1]
sys.path.insert(0, str(ROOT / "tools"))
from audit_evidence_provenance import ORIGINAL_MARKERS_NAMED  # noqa: E402

MAX_SOURCES = 3   # 每個條目最多列幾個來源字樣
DOC = ROOT / "docs/knowledge-base/98-tooling-infrastructure.md"
INDEX = ROOT / "docs/knowledge-base/98-index.md"
RECENT = 10   # 索引開頭列出的最近幾節

# (主題, [規則...]);規則是標題的 regex 字串,或 (下限, 上限) 表示「續 N」編號範圍(含兩端)。一節可屬於多個主題。
TOPICS: list[tuple[str, list[str | tuple[int, int]]]] = [
    ("Ghidra 與反組譯工具", [r"Ghidra|ghidra|ProbeBatch|decompile"]),
    ("位址資料庫、位址勘誤與位址引用檢查",
     [r"verified_addresses|errata|勘誤|位址訂正|verify_address|dossier|still_pending|舊版位址|stale-edition"]),
    ("函式清單(1356 個入口)、命名與名稱登錄表",
     [r"function_inventory|function_names|函式清單|命名|名稱|入口|Watcom|AIL|callee_argc|浮點模擬|分母|PRIM|戰鬥路徑|遊戲區|保留字"]),
    ("函式摘要與參數篩選(續一百零九 ~ 一百二十一)", [(109, 121), r"摘要|param_"]),
    ("DOSBox-X 原版實機操作工具(harness、live helper、宣告式驗證器)",
     [r"dosbox_harness|dosbox-x live|harness|live_helper|fd2_original_verify|dialogue_walker|env_healthcheck|debugger-cmd|"
      r"chapter_sweep|確認鍵送不進|麻痺術"]),
    ("原版實機執行軌跡與函式呼叫紀錄", [r"exec_trace|軌跡|呼叫紀錄|plan_trace_coverage|執行位址|死函式"]),
    ("工具的自我驗證、突變測試與閘門",
     [r"verify_all_tools|全工具|突變|窮舉|selftest|反向驗證|重驗|驗證層|自檢|worklist_status|不穩定|工具缺陷|盲點清單|"
      r"登錄表理由|稽核工具本身|工具驗證|逃逸|assert 數量|閘門"]),
    ("證據來源判準(排除 remake 證據)", [r"remake 驗證|排除 remake|audit_evidence_provenance|判準變更"]),
    ("remake 時期的工具(remake 已移除,歷史紀錄)", [r"remake|fd2_live_input_helper|xdotool"]),
    ("戰鬥公式與敵方 AI 的 DOSBox-X 實機驗證(續四十 ~ 六十八)", [(40, 68)]),
    ("單位落到地圖外、亂碼對白與例外路徑(續六十九 ~ 七十七)", [(69, 77)]),
    ("證據產生器(evidence/generators)", [r"證據產生器|產生器|手寫值掃描"]),
    ("畫面、換色與繪圖(LUT、光束炮、移動範圍明暗、HUD、FDICON、RLE)",
     [(122, 999), r"lut_circle|光束炮|明暗|HUD|FDICON|RLE|GAME OVER"]),
    ("dispatch 跳表與指令表", [r"dispatch|指令表|跳表"]),
    ("音訊與曲號", [r"曲號|音訊"]),
    ("文字與字模", [r"字模|glyph"]),
    ("交接與歸檔", [r"歸檔|SESSION-HANDOFF"]),
    ("資料抽取與新版 EXE 複驗", [r"新版 EXE|verify_native_tables_new_edition|extraction_freshness|global_writers|item 791|"
                               r"item 1117|A類殘留|未完項"]),
    ("防拷", [r"防拷"]),
]

_DIG = {"零": 0, "一": 1, "二": 2, "兩": 2, "三": 3, "四": 4, "五": 5, "六": 6, "七": 7, "八": 8, "九": 9}


def cn_number(s: str) -> int | None:
    """中文數字(1 ~ 999,含「一百零一」「一百一十」「十」這類寫法)→ int;不是數字回傳 None。

    「百」前面一定要有數字(「一百」);單獨的「百」不算數字。「十」前面可以省略「一」。
    """
    if not s or any(c not in _DIG and c not in "十百" for c in s):
        return None
    total = cur = 0
    for c in s:
        if c in _DIG:
            cur = _DIG[c]
        elif c == "百":
            if not cur:
                return None
            total += cur * 100
            cur = 0
        else:
            total += (cur or 1) * 10
            cur = 0
    return total + cur


_NUM = "[零一二兩三四五六七八九十百]+"
_SEQ = re.compile(rf"續({_NUM})(?:\s*[~～]\s*續?({_NUM}))?")


def seq_range(title: str) -> tuple[int, int] | None:
    """標題裡第一個「續 N」或「續 N~M」的 (N, M);沒有回傳 None。"""
    m = _SEQ.search(title)
    if not m:
        return None
    a = cn_number(m.group(1))
    b = cn_number(m.group(2)) if m.group(2) else a
    return (a, b) if a is not None and b is not None else None


def seq_of(title: str) -> int | None:
    """標題裡第一個「續 N」的 N(例如「續七十六~七十七」取 76);沒有回傳 None。"""
    r = seq_range(title)
    return r[0] if r else None


def headings(text: str) -> list[tuple[int, str]]:
    """文件的二級標題 [(行號, 標題文字)];``` 程式碼區塊裡的不算。"""
    out, fence = [], False
    for i, line in enumerate(text.splitlines(), 1):
        if line.startswith("```"):
            fence = not fence
        elif not fence and line.startswith("## "):
            out.append((i, line[3:].strip()))
    return out


def section_sources(text: str, heads: list[tuple[int, str]]) -> dict[int, list[str]]:
    """每一節本文(標題下一行到下一個二級標題前)裡命中的原版側來源字樣,依標記表順序、去重,最多 MAX_SOURCES 個。"""
    lines = text.splitlines()
    out = {}
    for k, (ln, _) in enumerate(heads):
        end = heads[k + 1][0] - 1 if k + 1 < len(heads) else len(lines)
        body = "\n".join(lines[ln:end])
        found: list[str] = []
        for pat, _label in ORIGINAL_MARKERS_NAMED:
            m = re.search(pat, body)
            if m and m.group(0) not in found:
                found.append(m.group(0))
        out[ln] = found[:MAX_SOURCES]
    return out


def _entry(ln: int, title: str, src: dict[int, list[str]]) -> str:
    tag = f" 〔來源:{'、'.join(src[ln])}〕" if src.get(ln) else ""
    return f"- 行 {ln}:{title}{tag}"


def classify(heads: list[tuple[int, str]], topics=TOPICS) -> tuple[dict[str, list[tuple[int, str]]], list, list]:
    """回傳 (主題 → 節, 孤兒節, 沒命中的規則 [(主題, 規則)])。"""
    by_topic: dict[str, list[tuple[int, str]]] = {t: [] for t, _ in topics}
    hit_rules: set[tuple[str, int]] = set()
    orphans = []
    for ln, title in heads:
        n = seq_of(title)
        placed = False
        for t, rules in topics:
            for k, r in enumerate(rules):
                ok = (n is not None and r[0] <= n <= r[1]) if isinstance(r, tuple) else re.search(r, title) is not None
                if ok:
                    hit_rules.add((t, k))
                    if not by_topic[t] or by_topic[t][-1][0] != ln:
                        by_topic[t].append((ln, title))
                    placed = True
        if not placed:
            orphans.append((ln, title))
    dead = [(t, r) for t, rules in topics for k, r in enumerate(rules) if (t, k) not in hit_rules]
    return by_topic, orphans, dead


def render(text: str, topics=TOPICS) -> str:
    """產生 98-index.md 的內容。"""
    heads = headings(text)
    by_topic, orphans, _ = classify(heads, topics)
    src = section_sources(text, heads)
    # 缺號只看「續十」以後:前面的「續一 ~ 九」是各工具章節自己的小節編號,不是全檔的流水號
    seqs = sorted({n for _, t in heads if seq_range(t) for n in range(seq_range(t)[0], seq_range(t)[1] + 1) if n >= 10})
    gaps = [n for n in range(seqs[0], seqs[-1] + 1) if n not in seqs] if seqs else []
    lines = ["# 98 索引 — 研究工具基礎建設(依主題)", "",
             "> 由 `tools/doc98_index.py --write` 從 [`98-tooling-infrastructure.md`](98-tooling-infrastructure.md) 的二級標題產生,"
             "**不要手改**;`--check` 檢查它與 doc98 一致。",
             "> 「行 N」是 doc98 的行號(Read 時用 offset = N)。一節可以出現在多個主題下。", "",
             f"共 {len(heads)} 節、{len(topics)} 個主題。", ""]
    if gaps:
        lines += [f"「續 N」編號缺號(doc98 沒有這一節標題):{'、'.join(map(str, gaps))}。", ""]
    lines += [f"## 最近 {RECENT} 節", ""]
    lines += [_entry(ln, t, src) for ln, t in heads[-RECENT:]]
    lines.append("")
    for t, _ in topics:
        lines += [f"## {t}({len(by_topic[t])} 節)", ""]
        lines += [_entry(ln, title, src) for ln, title in by_topic[t]]
        lines.append("")
    if orphans:
        lines += ["## 沒有歸類的節", ""] + [_entry(ln, title, src) for ln, title in orphans] + [""]
    return "\n".join(lines)


def check(text: str, committed: str | None, topics=TOPICS) -> list[str]:
    """閘門:回傳問題清單(空 = 通過)。"""
    _, orphans, dead = classify(headings(text), topics)
    probs = [f"孤兒節 行 {ln}:{t}" for ln, t in orphans]
    probs += [f"沒命中的規則:{t} / {r}" for t, r in dead]
    if committed is None:
        probs.append(f"{INDEX.name} 不存在(--write 產生)")
    elif committed != render(text, topics):
        probs.append(f"{INDEX.name} 與重算結果不同(--write 重寫)")
    return probs


def selftest() -> int:
    """正反對照:程式碼區塊不算標題、中文數字、孤兒 / 沒命中 / 不同都抓得到,真實文件沒有孤兒與沒命中的規則。"""
    fails = []
    # 1. 中文數字
    cases = {"十": 10, "十五": 15, "二十": 20, "六十五": 65, "一百": 100, "一百零一": 101, "一百一十": 110,
             "一百三十八": 138, "九十九": 99, "兩百": 200, "百": None, "百零五": None, "abc": None, "": None}
    bad = {k: cn_number(k) for k, v in cases.items() if cn_number(k) != v}
    if bad:
        fails.append(f"中文數字 {bad}")
    if (seq_of("2026-10-05 續七十六~七十七:x") != 76 or seq_of("沒有編號") is not None
            or seq_range("2026-10-05 續七十六~七十七:x") != (76, 77) or seq_range("續九:x") != (9, 9)):
        fails.append("seq_of / seq_range 取錯")
    # 2. 程式碼區塊裡的 ## 不算;行號正確
    doc = "# t\n## 甲 續五十\n```\n## 不是標題\n```\n## 乙 Ghidra\n## 丙 什麼都不是\n"
    if headings(doc) != [(2, "甲 續五十"), (6, "乙 Ghidra"), (7, "丙 什麼都不是")]:
        fails.append(f"headings {headings(doc)}")
    # 3. 分類:範圍規則、regex 規則、孤兒、沒命中
    topics = [("戰鬥", [(40, 68)]), ("Ghidra", [r"Ghidra"]), ("沒人用", [r"不存在的字"])]
    by, orphans, dead = classify(headings(doc), topics)
    if by["戰鬥"] != [(2, "甲 續五十")] or by["Ghidra"] != [(6, "乙 Ghidra")]:
        fails.append(f"分類 {by}")
    if orphans != [(7, "丙 什麼都不是")] or dead != [("沒人用", r"不存在的字")]:
        fails.append(f"孤兒 {orphans} / 沒命中 {dead}")
    # 3b. 同一主題兩條規則都命中同一節:只列一次;不同節不會被當成重複
    by2, _, dead2 = classify([(5, "甲 Ghidra 續五十"), (9, "乙 Ghidra")], [("t", [(40, 68), r"Ghidra"])])
    if by2["t"] != [(5, "甲 Ghidra 續五十"), (9, "乙 Ghidra")] or dead2:
        fails.append(f"同主題多規則 {by2} {dead2}")
    # 3c. 「最近 N 節」剛好列 RECENT 節,而且是最後那幾節
    many = "".join(f"## s{k} 續{'十' if k == 10 else ''}\n" for k in range(1, RECENT + 3))
    body = render(many, [("全部", [r"s"])]).split(f"## 最近 {RECENT} 節")[1].split("## 全部")[0]
    recent = [l for l in body.splitlines() if l.startswith("- ")]
    if len(recent) != RECENT or not recent[0].endswith(f"s3 續") or not recent[-1].endswith(f"s{RECENT + 2} 續"):
        fails.append(f"最近 {RECENT} 節:{recent[:2]} … {recent[-1:]}(共 {len(recent)})")
    # 4. check:一致時通過;改一個行號、多一節、孤兒都要失敗
    ok_topics = [("戰鬥", [(40, 68)]), ("其他", [r"Ghidra|什麼"])]
    good = render(doc, ok_topics)
    if check(doc, good, ok_topics):
        fails.append(f"一致時不該有問題:{check(doc, good, ok_topics)}")
    shifted = "\n" + doc
    if not any("不同" in p for p in check(shifted, good, ok_topics)):
        fails.append("行號移動沒抓到")
    grown = doc + "## 丁 續六十\n"
    if not any("不同" in p for p in check(grown, good, ok_topics)):
        fails.append("新的一節沒抓到")
    if not any("孤兒" in p for p in check(doc + "## 戊 無關\n", render(doc + "## 戊 無關\n", ok_topics), ok_topics)):
        fails.append("孤兒沒抓到")
    if not any("不存在" in p for p in check(doc, None, ok_topics)):
        fails.append("索引不存在沒抓到")
    # 4b. 來源字樣取自該節本文(不是標題、不是下一節),依標記表順序,最多 MAX_SOURCES 個;沒有就不加標註
    sdoc = ("## 甲 DOSBox 標題\n本文用 FD2.EXE 反組譯\n## 乙\n沒有來源\n## 丙\n"
            "DOSBox-X 傾印、Ghidra、反組譯、org_game 檔、攻略\n")
    sh = headings(sdoc)
    ss = section_sources(sdoc, sh)
    if ss != {1: ["反組譯", "FD2.EXE"], 3: [], 5: ["DOSBox-X", "Ghidra", "反組譯"]}:
        fails.append(f"來源字樣 {ss}")
    if _entry(1, "甲", ss) != "- 行 1:甲 〔來源:反組譯、FD2.EXE〕" or _entry(3, "乙", ss) != "- 行 3:乙":
        fails.append(f"條目格式 {_entry(1, '甲', ss)!r} / {_entry(3, '乙', ss)!r}")
    # 5. 缺號
    gapdoc = "## a 續十\n## b 續十二\n## c 續十三~十四\n## d 續十六\n"
    if "缺號(doc98 沒有這一節標題):11、15。" not in render(gapdoc, [("x", [(10, 16)])]):
        fails.append(f"缺號:{[l for l in render(gapdoc, [('x', [(10, 16)])]).splitlines() if '缺號' in l]}")
    # 6. 真實 doc98:沒有孤兒、沒有沒命中的規則
    if DOC.exists():
        _, o, d = classify(headings(DOC.read_text(encoding="utf-8")))
        if o or d:
            fails.append(f"真實 doc98:孤兒 {o[:3]} / 沒命中 {d[:3]}")
    else:
        print("    NOT TESTED:找不到 doc98,第 6 題略過")
    if fails:
        print("SELFTEST FAILED:")
        for f in fails:
            print("  -", f)
        return 1
    print("--selftest passed(中文數字 + 程式碼區塊 + 範圍 / regex 分類 + 孤兒 / 沒命中 / 不同 / 不存在 + 缺號 + 真實 doc98)")
    return 0


def main(argv: list[str]) -> int:
    ap = argparse.ArgumentParser(description=__doc__.splitlines()[0])
    ap.add_argument("--write", action="store_true", help=f"重寫 {INDEX.name}")
    ap.add_argument("--check", action="store_true", help="孤兒節 / 沒命中的規則 / 內容不同都 exit 1")
    ap.add_argument("--selftest", action="store_true")
    a = ap.parse_args(argv)
    if a.selftest:
        return selftest()
    text = DOC.read_text(encoding="utf-8")
    if a.check:
        probs = check(text, INDEX.read_text(encoding="utf-8") if INDEX.exists() else None)
        for p in probs:
            print("FAIL", p)
        print("OK" if not probs else f"{len(probs)} 個問題")
        return 1 if probs else 0
    out = render(text)
    if a.write:
        INDEX.write_bytes(out.encode("utf-8"))
        print(f"寫入 {INDEX.relative_to(ROOT).as_posix()}({len(headings(text))} 節)")
        return 0
    print(out)
    return 0


if __name__ == "__main__":
    sys.exit(main(sys.argv[1:]))
