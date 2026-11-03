#!/usr/bin/env python3
"""fd2_re - `91-worklist.md` 的勾選框(`- [ ]` / `- [~]`)逐項分類與覆蓋檢查。

為什麼要有這支
--------------
`worklist_status.py` 只讀 `N - X` 型的稽核項目(146 項),不讀勾選框。2026-11-03 被問
「還有哪些問題」時,勾選框那一層只能用 grep 數 `[ ]`:數到的 30 行裡有一半帶著
「隨 remake 移除失效」的註記,另一半有的早已被後來的章節解掉(例如 UI 音效 index
1 / 8 / 0xc 在 doc98 續一百八十四已實機看過,勾選框沒改)。數字本身說不出哪些是真的。

所以這支不用關鍵字猜「開放 / 已解」(`worklist_status.py` 實測那條路約六成假陽性),
而是:

* **每個未勾項目都要在 `docs/data/worklist_checklist_triage.json` 有一筆人工分類**,
  分類只能是 `DISPOSITIONS` 之一;沒有分類的項目、分類了卻已不存在的項目都算錯。
  清單因此一定能歸零,不會留下「沒列到所以看起來沒事」的列。
* `closed` 必須附依據:檔案存在、引文逐字出現在該檔;`duplicate` 必須指向另一筆
  非 duplicate 的分類;`open_static` / `open_live` 必須寫下一步。
* `--suggest` 只是加速:把項目裡的位址(依數值,不分大小寫)與 `docs/knowledge-base`
  其他文件各節的位址求交集,列出最可能結案的章節,給人讀。它不做判斷。

項目的 key 是勾選框後文字(去掉 `→【…】` 註記、壓縮空白)的 sha1 前 10 碼;同一段文字
出現第二次時加 `-2`。所以勾成 `[x]` 或補 `→【…】` 都不會讓 key 變;改寫標題會讓舊分類
變成「已不存在」、新標題變成「沒有分類」——這是故意的,改了內容就該重看。

用法
----
    python tools/worklist_checklist.py --summary        # 各狀態 / 分類計數 + 開放清單
    python tools/worklist_checklist.py --check          # 覆蓋與依據檢查,有錯 exit 1
    python tools/worklist_checklist.py --item 4085      # 一項(行號或 key)+ 分類 + 建議章節
    python tools/worklist_checklist.py --suggest        # 未分類項目的建議章節
    python tools/worklist_checklist.py --skeleton OUT   # 未分類項目的 JSON 骨架(給人填)
    python tools/worklist_checklist.py --selftest
"""

from __future__ import annotations

import argparse
import hashlib
import json
import re
import sys
from dataclasses import dataclass, field
from pathlib import Path

if hasattr(sys.stdout, "reconfigure"):
    sys.stdout.reconfigure(encoding="utf-8")
    sys.stderr.reconfigure(encoding="utf-8")

ROOT = Path(__file__).resolve().parent.parent
WORKLIST = ROOT / "docs/knowledge-base/91-worklist.md"
KB = ROOT / "docs/knowledge-base"
TRIAGE = ROOT / "docs/data/worklist_checklist_triage.json"

CHECK = re.compile(r"^(\s*)- \[([ x~])\](.*)$")
ANNOT = re.compile(r"\s*→【[^】]*】")
HEADING = re.compile(r"^#{1,6} ")
# 4 .. 6 位十六進位才算位址;0x50 這種短值是欄位位移 / 常數,拿來配對只會雜訊
HEX = re.compile(r"(?<![0-9A-Za-z_])0x([0-9A-Fa-f]{4,6})(?![0-9A-Za-z_])")

DISPOSITIONS = ("closed", "obsolete_remake", "duplicate", "not_a_task", "open_static", "open_live")
OPEN_DISPOSITIONS = ("open_static", "open_live")
MIN_QUOTE = 8


@dataclass
class Check:
    """一個勾選框項目:標題行 + 續行。"""

    line: int                 # 1 起算
    state: str                # " " / "~" / "x"
    indent: int
    text: str                 # 勾選框後的標題行文字
    cont: list[str]
    section: str
    key: str = ""

    @property
    def is_open(self) -> bool:
        return self.state != "x"

    @property
    def body(self) -> str:
        return "\n".join([self.text] + self.cont)


def norm(text: str) -> str:
    """key 的輸入:去 `→【…】` 註記、壓縮空白。"""
    return " ".join(ANNOT.sub("", text).split())


def parse(src: str) -> list[Check]:
    """解析全部勾選框。續行 = 縮排比標題深、非空、且不是另一個勾選框的連續行。"""
    lines = src.replace("\r", "").split("\n")
    out: list[Check] = []
    seen: dict[str, int] = {}
    section = ""
    i = 0
    while i < len(lines):
        ln = lines[i]
        if HEADING.match(ln):
            section = ln
        m = CHECK.match(ln)
        if not m:
            i += 1
            continue
        ind = len(m.group(1))
        j = i + 1
        while j < len(lines) and lines[j].strip() and not CHECK.match(lines[j]) \
                and len(lines[j]) - len(lines[j].lstrip()) > ind:
            j += 1
        c = Check(i + 1, m.group(2), ind, m.group(3).strip(), lines[i + 1:j], section)
        base = hashlib.sha1(norm(c.text).encode("utf-8")).hexdigest()[:10]
        seen[base] = seen.get(base, 0) + 1
        c.key = base if seen[base] == 1 else f"{base}-{seen[base]}"
        out.append(c)
        i = j
    return out


def addresses(text: str) -> set[int]:
    """文字中的位址,依數值(0x1A4EB 與 0x1a4eb 同一個)。"""
    return {int(h, 16) for h in HEX.findall(text)}


@dataclass
class Section:
    path: str
    line: int
    heading: str
    addrs: set[int] = field(default_factory=set)


def sections() -> list[Section]:
    """`docs/knowledge-base` 下每個 .md(worklist 本身除外)依標題切節,記下每節的位址集合。"""
    out: list[Section] = []
    for p in sorted(KB.glob("*.md")):
        if p == WORKLIST:
            continue
        cur = Section(p.relative_to(ROOT).as_posix(), 1, "")
        buf: list[str] = []
        for n, ln in enumerate(p.read_text(encoding="utf-8").replace("\r", "").split("\n"), 1):
            if HEADING.match(ln):
                cur.addrs = addresses("\n".join(buf))
                out.append(cur)
                cur, buf = Section(cur.path, n, ln), []
            else:
                buf.append(ln)
        cur.addrs = addresses("\n".join(buf))
        out.append(cur)
    return out


def suggest(c: Check, secs: list[Section], top: int = 3) -> list[tuple[int, Section]]:
    """與項目共用最多位址的章節;同分時後面的章節(較新)在前。"""
    mine = addresses(c.body)
    scored = [(len(mine & s.addrs), k, s) for k, s in enumerate(secs)]
    scored = [t for t in scored if t[0]]
    scored.sort(key=lambda t: (-t[0], -t[1]))
    return [(n, s) for n, _, s in scored[:top]]


def load_triage(path: Path = TRIAGE) -> list[dict]:
    if not path.exists():
        return []
    return json.loads(path.read_text(encoding="utf-8"))["items"]


def check(items: list[Check], triage: list[dict], root: Path = ROOT) -> list[str]:
    """覆蓋與依據檢查;回傳錯誤訊息(空 = 通過)。"""
    errs: list[str] = []
    open_ = {c.key: c for c in items if c.is_open}
    by_key: dict[str, dict] = {}
    for e in triage:
        k = e.get("key", "")
        if k in by_key:
            errs.append(f"{k}: 重複登錄")
        by_key[k] = e
    for k, c in open_.items():
        if k not in by_key:
            errs.append(f"{k}: 第 {c.line} 行未分類")
    texts: dict[str, str] = {}
    for k, e in by_key.items():
        c = open_.get(k)
        if c is None:
            errs.append(f"{k}: 分類的項目已不存在或已勾選")
            continue
        if not norm(c.text).startswith(e.get("title") or "\0"):
            errs.append(f"{k}: title 不是第 {c.line} 行標題的開頭")
        d = e.get("disposition")
        if d not in DISPOSITIONS:
            errs.append(f"{k}: 分類 {d!r} 不在 {DISPOSITIONS}")
            continue
        if not e.get("reason", "").strip():
            errs.append(f"{k}: 沒有 reason")
        if d in OPEN_DISPOSITIONS and not e.get("next", "").strip():
            errs.append(f"{k}: {d} 沒有 next")
        if d == "duplicate":
            t = by_key.get(e.get("of", ""))
            if t is None or t.get("disposition") == "duplicate" or e.get("of") == k:
                errs.append(f"{k}: duplicate 的 of 必須指向另一筆非 duplicate 的分類")
        ev = e.get("evidence", [])
        if d == "closed" and not ev:
            errs.append(f"{k}: closed 沒有 evidence")
        for x in ev:
            p = root / x.get("path", "")
            q = x.get("quote", "")
            if len(q) < MIN_QUOTE:
                errs.append(f"{k}: 引文短於 {MIN_QUOTE} 字")
            elif not p.is_file():
                errs.append(f"{k}: 依據檔 {x.get('path')} 不存在")
            else:
                if x["path"] not in texts:
                    texts[x["path"]] = " ".join(p.read_text(encoding="utf-8").split())
                if " ".join(q.split()) not in texts[x["path"]]:
                    errs.append(f"{k}: 引文不在 {x['path']}")
    return errs


def show(c: Check, entry: dict | None, secs: list[Section]) -> str:
    out = [f"第 {c.line} 行 [{c.state}] key={c.key}  {c.section}", f"  {c.text[:300]}",
           f"  續行 {len(c.cont)}"]
    out.append(f"  分類: {json.dumps(entry, ensure_ascii=False) if entry else '(未分類)'}")
    for n, s in suggest(c, secs):
        out.append(f"  建議 {n} 個共用位址: {s.path}:{s.line} {s.heading[:100]}")
    return "\n".join(out)


def summary(items: list[Check], triage: list[dict]) -> str:
    open_ = [c for c in items if c.is_open]
    by_key = {e["key"]: e for e in triage}
    st = {s: sum(c.state == s for c in items) for s in " ~x"}
    out = [f"勾選框 {len(items)}:[x]={st['x']}  [~]={st['~']}  [ ]={st[' ']};未勾 {len(open_)}"]
    cnt = {d: 0 for d in DISPOSITIONS + ("(未分類)",)}
    for c in open_:
        cnt[by_key.get(c.key, {}).get("disposition", "(未分類)")] += 1
    out.append("  " + "  ".join(f"{d}={n}" for d, n in cnt.items()))
    for c in open_:
        e = by_key.get(c.key, {})
        if e.get("disposition") in OPEN_DISPOSITIONS:
            out.append(f"  {e['disposition']:11} 第 {c.line} 行 {norm(c.text)[:70]}\n"
                       f"              next: {e['next']}")
    return "\n".join(out)


def skeleton(items: list[Check], triage: list[dict], secs: list[Section]) -> list[dict]:
    have = {e["key"] for e in triage}
    return [{"key": c.key, "line": c.line, "state": c.state, "title": norm(c.text)[:40],
             "suggest": [f"{s.path}:{s.line} {s.heading[:80]}" for _, s in suggest(c, secs)],
             "disposition": "", "reason": "", "evidence": []}
            for c in items if c.is_open and c.key not in have]


# --- selftest ---------------------------------------------------------------------

SAMPLE = """# 甲
- [ ] **A1** 看 0x1A4EB  →【舊註記】
  續行一 0x22253
  續行二
- [~] B2 第二項
    - [x] C3 子項
      子項續行
- [x] D4 已完成
不縮排的下一行
## 乙
- [ ] **A1** 看 0x1A4EB
- [~] E5 0x00ab 0x123456 0x1234567 x0x1abcd
  - [~] F6 淺一層

- [ ] G7
"""


def _selftest() -> int:
    fails: list[str] = []

    def ok(cond: bool, what: str) -> None:
        if not cond:
            fails.append(what)

    it = parse(SAMPLE.replace("\n", "\r\n"))
    ok([c.text[:5] for c in it] == ["**A1*", "B2 第二", "C3 子項", "D4 已完", "**A1*", "E5 0x", "F6 淺一", "G7"],
       f"解析順序 {[c.text for c in it]}")
    ok([c.state for c in it] == [" ", "~", "x", "x", " ", "~", "~", " "], "狀態")
    ok([c.indent for c in it] == [0, 0, 4, 0, 0, 0, 2, 0], "縮排")
    ok([len(c.cont) for c in it] == [2, 0, 1, 0, 0, 0, 0, 0], f"續行 {[len(c.cont) for c in it]}")
    ok(it[0].cont == ["  續行一 0x22253", "  續行二"], "續行內容(CR 已去掉)")
    ok([c.section for c in it] == ["# 甲"] * 4 + ["## 乙"] * 4, "所屬標題")
    ok(it[4].key == it[0].key + "-2" and "-" not in it[0].key and len(it[0].key) == 10, "重複文字 key 加 -2")
    ok(len({c.key for c in it}) == len(it), "key 唯一")
    ok(sum(c.is_open for c in it) == 6, "未勾 = [ ] + [~]")
    ok(norm("a  →【x】 b\t c") == "a b c", "norm 去註記、壓空白")
    ok(addresses(it[5].text) == {0xab, 0x123456}, f"位址 4..6 位、邊界 {addresses(it[5].text)}")
    ok(addresses(it[0].body) == {0x1a4eb, 0x22253} and addresses("0x1a4eb") == {0x1a4eb}, "位址依數值、含續行")

    # suggest:分數高者先、同分新者先、零分不列
    secs = [Section("a", 1, "舊", {0x1a4eb}), Section("b", 5, "新", {0x1a4eb}),
            Section("c", 9, "雙", {0x1a4eb, 0x22253}), Section("d", 12, "無", {0x9999})]
    got = [s.heading for _, s in suggest(it[0], secs)]
    ok(got == ["雙", "新", "舊"], f"suggest 排序 {got}")
    got = [s.heading for _, s in suggest(it[0], [secs[2], secs[0], secs[1]])]
    ok(got == ["雙", "新", "舊"], f"suggest 先比分數、再比先後 {got}")
    ok([n for n, _ in suggest(it[0], secs, top=2)] == [2, 1], "suggest 分數與 top")
    ok(suggest(it[7], secs) == [], "沒有位址就沒有建議")

    # check:乾淨控制 0 錯,每類錯誤各觸發一次
    tmp = ROOT / ".wsl_build" / "worklist_checklist_selftest"
    tmp.mkdir(parents=True, exist_ok=True)
    (tmp / "ev.md").write_text("前文\n依據 甲乙丙丁\n戊己 庚辛壬癸\n", encoding="utf-8")
    ev = [{"path": "ev.md", "quote": "甲乙丙丁 戊己 庚"}]
    k = [c.key for c in it if c.is_open]
    good = [
        {"key": k[0], "title": "**A1** 看", "disposition": "closed", "reason": "r", "evidence": ev},
        {"key": k[1], "title": "B2", "disposition": "open_static", "reason": "r", "next": "n"},
        {"key": k[2], "title": "**A1** 看", "disposition": "duplicate", "reason": "r", "of": k[0]},
        {"key": k[3], "title": "E5", "disposition": "open_live", "reason": "r", "next": "n"},
        {"key": k[4], "title": "F6", "disposition": "not_a_task", "reason": "r"},
        {"key": k[5], "title": "G7", "disposition": "obsolete_remake", "reason": "r"},
    ]
    ok(check(it, good, tmp) == [], f"乾淨控制 {check(it, good, tmp)}")
    ok(check(it, good + [{"key": it[3].key, "title": "D4", "disposition": "not_a_task", "reason": "r"}], tmp)
       == [f"{it[3].key}: 分類的項目已不存在或已勾選"], "已勾選的項目不可分類")

    def bad(i: int, **chg) -> list[str]:
        t = [dict(e) for e in good]
        t[i].update(chg)
        return check(it, t, tmp)

    cases = [
        (bad(1, key="zzz"), [f"{k[1]}: 第 5 行未分類", "zzz: 分類的項目已不存在或已勾選"]),
        (check(it, good + [dict(good[4])], tmp), [f"{k[4]}: 重複登錄"]),
        (bad(1, title="B3"), [f"{k[1]}: title 不是第 5 行標題的開頭"]),
        (bad(1, title=None), [f"{k[1]}: title 不是第 5 行標題的開頭"]),
        (bad(1, disposition="open"), [f"{k[1]}: 分類 'open' 不在 {DISPOSITIONS}"]),
        (bad(4, reason=" "), [f"{k[4]}: 沒有 reason"]),
        (bad(1, next=""), [f"{k[1]}: open_static 沒有 next"]),
        (bad(3, next=" "), [f"{k[3]}: open_live 沒有 next"]),
        (bad(2, of=k[2]), [f"{k[2]}: duplicate 的 of 必須指向另一筆非 duplicate 的分類"]),
        (bad(2, of="nope"), [f"{k[2]}: duplicate 的 of 必須指向另一筆非 duplicate 的分類"]),
        (bad(0, evidence=[]), [f"{k[0]}: closed 沒有 evidence"]),
        (bad(0, evidence=[{"path": "ev.md", "quote": "甲乙丙丁戊己庚辛"}]), [f"{k[0]}: 引文不在 ev.md"]),
        (bad(0, evidence=[{"path": "no.md", "quote": "甲乙丙丁 戊己 庚"}]), [f"{k[0]}: 依據檔 no.md 不存在"]),
        (bad(0, evidence=[{"path": "ev.md", "quote": "丙丁 戊己 庚"}]), [f"{k[0]}: 引文短於 {MIN_QUOTE} 字"]),
        (bad(4, evidence=[{"path": "ev.md", "quote": "甲乙丙丁戊己庚辛"}]), [f"{k[4]}: 引文不在 ev.md"]),
        (bad(4, evidence=ev + [{"path": "ev.md", "quote": "戊己 庚辛壬癸 x"}]), [f"{k[4]}: 引文不在 ev.md"]),
    ]
    t = [dict(e) for e in good]
    t[2]["of"] = k[2]
    t[1]["disposition"] = "duplicate"
    t[1]["of"] = k[2]
    cases.append((check(it, t, tmp), [f"{k[1]}: duplicate 的 of 必須指向另一筆非 duplicate 的分類",
                                      f"{k[2]}: duplicate 的 of 必須指向另一筆非 duplicate 的分類"]))
    for n, (got, want) in enumerate(cases):
        ok(got == want, f"錯誤案例 {n}: {got}")
    ok(check(it, [dict(good[0], evidence=[{"path": "ev.md", "quote": "據 甲乙丙丁\n戊"}])] + good[1:], tmp) == [],
       "引文恰好 8 字通過、跨換行以空白比對")

    sm = summary(it, good)
    ok(sm.splitlines()[0] == "勾選框 8:[x]=2  [~]=3  [ ]=3;未勾 6", f"summary 計數 {sm.splitlines()[0]}")
    ok("closed=1  obsolete_remake=1  duplicate=1  not_a_task=1  open_static=1  open_live=1  (未分類)=0" in sm, "summary 分類")
    ok(summary(it, []).splitlines()[1].endswith("(未分類)=6") and sm.count("next: n") == 2
       and "open_live   第 12 行 E5" in sm and "open_static 第 5 行 B2" in sm, f"summary 未分類與開放清單 {sm}")
    sk = skeleton(it, good[:3], secs)
    ok([e["key"] for e in sk] == k[3:] and sk[0]["line"] == 12 and sk[0]["state"] == "~"
       and sk[0]["title"] == "E5 0x00ab 0x123456 0x1234567 x0x1abcd" and sk[0]["disposition"] == "",
       f"skeleton {sk[:1]}")
    ok(skeleton(it, [], secs)[0]["suggest"] == ["c:9 雙", "b:5 新", "a:1 舊"], "skeleton 附建議")
    sh = show(it[0], good[0], secs).splitlines()
    ok(sh[0] == f"第 2 行 [ ] key={k[0]}  # 甲" and sh[2] == "  續行 2" and '"closed"' in sh[3]
       and sh[4] == "  建議 2 個共用位址: c:9 雙" and len(sh) == 7, f"show {sh}")
    ok(show(it[7], None, secs).splitlines()[3] == "  分類: (未分類)", "show 未分類")
    ok("甲乙丙丁" in sh[3], "show 的分類保留中文")
    # 顯示長度:標題 300 / 70 / 40、章節標題 100 / 80
    lc = Check(1, " ", 0, "0x1a4eb " + "長" * 400, [], "# 長")
    lc.key = "k"
    ls = [Section("p", 3, "#" + "節" * 200, {0x1a4eb})]
    sh = show(lc, None, ls).splitlines()
    ok(len(sh[1]) == 2 + 300 and len(sh[4]) == len("  建議 1 個共用位址: p:3 ") + 100, f"show 截斷 {len(sh[1])} {len(sh[4])}")
    sm = summary([lc], [{"key": "k", "disposition": "open_live", "next": "n"}]).splitlines()
    ok(len(sm[2]) == len("  open_live   第 1 行 ") + 70, f"summary 截斷 {len(sm[2])}")
    sk = skeleton([lc], [], ls)[0]
    ok(len(sk["title"]) == 40 and sk["suggest"] == ["p:3 #" + "節" * 79], f"skeleton 截斷 {sk['title']}")

    # 真實檔:以獨立的寫法數未勾行,與 parse 一致;登錄表存在時必須零錯
    src = WORKLIST.read_text(encoding="utf-8")
    real = parse(src)
    raw_open = sum(1 for ln in src.splitlines() if ln.lstrip().startswith(("- [ ]", "- [~]")))
    ok(raw_open == sum(c.is_open for c in real) and raw_open > 100, f"真實檔未勾 {raw_open}")
    ok(len(real) == src.count("- [x]") + raw_open, "真實檔總數")
    errs = check(real, load_triage())
    ok(not TRIAGE.exists() or errs == [], f"真實登錄表 {len(errs)} 錯:{errs[:3]}")
    s0 = sections()
    ok(any(s.path.endswith("98-tooling-infrastructure.md") for s in s0)
       and not any(s.path.endswith(WORKLIST.name) for s in s0), "章節來源排除 worklist 本身")
    ok(s0[0].line == 1 and s0[0].heading == "", "每檔第一節從第 1 行起、沒有標題")
    heads = [s for s in s0 if s.heading][:50]
    ok(len(heads) == 50 and all((ROOT / s.path).read_text(encoding="utf-8").replace("\r", "").split("\n")[s.line - 1]
                                == s.heading for s in heads), "章節行號指向標題行")

    for f in fails:
        print("FAIL", f)
    print(f"selftest {'FAIL' if fails else 'PASS'}({len(fails)} 項失敗)")
    return 1 if fails else 0


def main() -> int:
    ap = argparse.ArgumentParser(description=__doc__, formatter_class=argparse.RawDescriptionHelpFormatter)
    ap.add_argument("--summary", action="store_true")
    ap.add_argument("--check", action="store_true")
    ap.add_argument("--item")
    ap.add_argument("--suggest", action="store_true")
    ap.add_argument("--skeleton")
    ap.add_argument("--selftest", action="store_true")
    a = ap.parse_args()
    if a.selftest:
        return _selftest()
    items = parse(WORKLIST.read_text(encoding="utf-8"))
    triage = load_triage()
    if a.check:
        errs = check(items, triage)
        for e in errs:
            print(e)
        print(f"check {'FAIL' if errs else 'PASS'}:未勾 {sum(c.is_open for c in items)},錯誤 {len(errs)}")
        return 1 if errs else 0
    if a.item:
        secs = sections()
        by_key = {e["key"]: e for e in triage}
        hit = [c for c in items if a.item in (str(c.line), c.key)]
        for c in hit:
            print(show(c, by_key.get(c.key), secs))
        return 0 if hit else 1
    if a.suggest or a.skeleton:
        sk = skeleton(items, triage, sections())
        if a.skeleton:
            Path(a.skeleton).write_text(json.dumps(sk, ensure_ascii=False, indent=1) + "\n", encoding="utf-8")
        for e in sk:
            print(f"第 {e['line']} 行 [{e['state']}] {e['key']} {e['title']}")
            for s in e["suggest"]:
                print(f"    {s}")
        print(f"未分類 {len(sk)}")
        return 0
    print(summary(items, triage))
    return 0


if __name__ == "__main__":
    sys.exit(main())
