#!/usr/bin/env python3
"""audit_evidence_provenance.py — 把知識庫裡的「驗證主張」依證據來源分類。

問題
----
使用者的判斷是「remake 驗證過的資料本身就有問題,驗出來的也會有問題」
(2026-09-02 的移除指示)。但 `remake/` 移除之後,**文件裡還留著大量以 remake 為
證據來源的結論**,而它們與原版側(DOSBox-X 實機、靜態反組譯、原版資產、外部攻略)
驗證的結論混在同一批文字裡,肉眼分不出來。本工具把這件事變成可重跑的清單。

2026-09-03 已經抓到一個具體案例:`command_labels.json` 的 id27 覆寫,commit
`a1851a76` 自稱「Live-verified end to end by building fd2.exe ... screenshotting the
actual drawNativeCommandGrid render」——`drawNativeCommandGrid` 是 remake 的函式名,
那次驗證只證明字串在 remake 字型管線不吐亂碼,不證明語意。本工具就是為了系統性地
找出同一形狀的其他主張。

做法(刻意保守)
----------------
只用**明確、不含歧義的標記**分類,不做自然語言推論:

* REMAKE 標記:`fd2-linux-verify`(remake 執行檔)、`drawNative*`、`.go` 檔名、
  `go test`、`cmd/fd2`、`remake/`、`FD2_SHOT_*`/`FD2_CAMP_*`(remake 專用 debug
  env hook)、檔名含 `remake` 的圖。
* ORIGINAL 標記:`DOSBox-X`/`dosbox-x`、`MEMDUMPBIN`、`Alt+Pause`、`debugger`、
  `Ghidra`/`IDA`/`capstone`、`反組譯`/`decompile`/`disasm`、`青衫攻略`/`攻略`、
  `org_game`、原版容器名(`FDTXT`/`FDOTHER`/`FDFIELD`/`FDSHAP`/`FDMUS`/`DATO`)。

分類:
* `REMAKE_ONLY` —— 有驗證語言 + 只有 remake 標記。**這是可疑集合**。
* `MIXED` —— 兩種標記都有。需要人逐句讀,工具不替它下結論。
* `ORIGINAL` —— 只有原版標記。
* `NO_MARKER` —— 有驗證語言但沒有任何來源標記(出處不明,本身也是一種問題)。

**工具不宣稱 REMAKE_ONLY 的結論是錯的**——只宣稱它的**證據來源是 remake**,
依使用者的判準需要用原版重驗。這個區別是刻意的。

用法
----
    python tools/audit_evidence_provenance.py                # 摘要 + 可疑清單
    python tools/audit_evidence_provenance.py --status REMAKE_ONLY --limit 40
    python tools/audit_evidence_provenance.py --json out.json
    python tools/audit_evidence_provenance.py --selftest     # 反向驗證
"""

from __future__ import annotations

import argparse
import hashlib
import json
import re
import subprocess
import sys
from dataclasses import dataclass, asdict, field
from pathlib import Path

REPO = Path(__file__).resolve().parent.parent
KB = REPO / "docs" / "knowledge-base"

for _s in (sys.stdout, sys.stderr):
    try:
        _s.reconfigure(encoding="utf-8", errors="backslashreplace")
    except (AttributeError, OSError):
        pass

# 「這句話在宣稱某件事被驗證過」的語言。刻意寬鬆——寧可多收再分類。
#
# 2026-09-04 修正:原本這裡有一個裸的 `E2`(想收「E2E 驗證」)。在 `re.I` 下它會
# 命中任何字串裡的 `e2`,而**原版遊戲的目錄名 `FLAME2` 本身就含 `E2`**——於是每一行
# 提到 `org_game/炎龍騎士團/FLAME2/` 的敘述都被當成「驗證主張」收進來,連 hex 位元組
# (`fe2c`、`0x1e2a4`)也一樣。實測:全庫 7270 筆主張裡有 **816 筆是只因這條進來的**
# (其中 489 筆還被判成 ORIGINAL),等於分母膨脹 11%。改成 `\bE2E\b`。
VERIFY_LANG = re.compile(
    r"(已證實|已確認|證實|確認|驗證|實測|逐位元組|逐字|閉合|\bE2E\b|verified|confirmed"
    r"|cross-check|已證|佐證|complete evidence|已閉合)",
    re.I,
)

REMAKE_MARKERS = [
    (r"fd2-linux-verify", "remake 執行檔"),
    (r"drawNative\w*", "remake 渲染函式"),
    (r"\bcmd/fd2\b", "remake 主程式"),
    (r"\bgo test\b", "remake Go 測試"),
    (r"remake/", "remake 路徑"),
    (r"\bplay\.sh\b", "remake 啟動腳本"),
    (r"FD2_SHOT_\w+", "remake debug hook"),
    (r"FD2_CAMP_\w+", "remake debug hook"),
    (r"\w+\.go\b", "remake Go 原始碼"),
    (r"[-\w]*remake[-\w]*\.png", "remake 截圖"),
]

ORIGINAL_MARKERS = [
    (r"DOSBox-X|dosbox-x|DOSBox", "原版模擬器實機"),
    (r"MEMDUMPBIN", "活體記憶體讀取"),
    (r"Alt\+Pause|debugger|斷點|BPLIST|SMV ", "原版 debugger"),
    (r"Ghidra|IDA|capstone|Capstone", "靜態反組譯工具"),
    (r"反組譯|decompile|disasm|逐指令", "反組譯"),
    (r"青衫攻略|攻略", "外部攻略(玩家社群)"),
    (r"org_game", "原版遊戲檔"),
    # 2026-09-05 修正:原本的 `\bFDTXT\b` 這類寫法,`\b` 是「\w 字元 ↔ 非 \w 字元」
    # 的邊界,而底線 `_` **本身也是 \w**——所以 `FDTXT_033` 這種本專案最常見的
    # 具體資源檔名寫法(`FDTXT_NNN`/`FDMUS_NNN` 等),結尾的 `\b` 在 `T` 跟 `_`
    # 之間**找不到邊界,整條規則不會命中**。實測:`re.search(r"\bFDTXT\b",
    # "FDTXT_033")` 是 `None`。這代表全庫任何一句「只提到 FDTXT_033 之類具體
    # 檔名、沒有另外寫出裸字 FDTXT」的主張,先前都被漏判成 NO_MARKER——方向上
    # 只會讓 ORIGINAL 主張被低估(漏判成 NO_MARKER),不會讓 REMAKE_ONLY 或
    # NO_MARKER 被誤判成 ORIGINAL,是安全方向的修正(跟 `ADDR_MARKER` 那種
    # 「裸位址可能只是巧合」的風險方向相反,這裡的容器檔名是本專案自訂的具體
    # 原版資源命名,不是巧合數字)。改成 `(?:_\d+)?` 選擇性尾綴,讓
    # `FDTXT`/`FDTXT_033` 都能命中,但仍然不會誤吃 `FDTXTFOO` 這種真正黏在
    # 別的詞裡的情況(見 selftest 的正反向驗證)。
    (r"\bFDTXT(?:_\d+)?\b|\bFDOTHER(?:_\d+)?\b|\bFDFIELD(?:_\d+)?\b|"
     r"\bFDSHAP(?:_\d+)?\b|\bFDMUS(?:_\d+)?\b|\bDATO(?:_\d+)?\b|FDICON",
     "原版資產容器"),
    (r"FD2\.EXE", "原版執行檔"),
]

# 裸的 linear 位址。單獨拉出來,因為它與上面那些**強度不同**。
#
# 2026-09-03 加上這條是為了修一個真實誤報:doc27 驗證表的證據欄正是
# `0x2f7b6`/`0x276ec`/`0x1c75e` 這類反組譯位址,remake 欄只是「實作對照」,少了這條
# 整張表會被誤報成 remake-only。
#
# 但 2026-09-04 量測發現它也是**反方向風險**的來源:ORIGINAL 2857 筆裡有 1268 筆
# (44%)完全只靠這一條規則成立。一個十六進位常數並不證明有人做過原版側工作——它
# 也可能只是遮罩、顏色、Go 常數。假 REMAKE_ONLY 只是浪費人工複核,**假 ORIGINAL 會
# 讓 remake 證據永久隱形**,是危險的那個方向。
#
# 折衷:位址仍算 ORIGINAL 標記(否則 doc27 那類表又壞掉),但單獨記一個
# `addr_only` 旗標,讓報告能把「由具名原版工具支撐的 ORIGINAL」與「只有一個裸位址的
# ORIGINAL」分開,不把兩者混為同一種可信度。
ADDR_MARKER = (r"\b0x[0-9a-fA-F]{4,6}\b", "原版 EXE 位址")
ORIGINAL_MARKERS.append(ADDR_MARKER)
ORIGINAL_MARKERS_NAMED = [m for m in ORIGINAL_MARKERS if m is not ADDR_MARKER]

# 2026-09-04,一個**被自己的對照組否決掉**的改動,留紀錄避免以後有人重做:
#
# 逐行掃描看不到跨行證據(表頭、上一個 bullet、章節標題),所以我加了 ±3 行的 context
# 視窗,量到「NO_MARKER 4137 筆裡有 3152 筆看 ±3 行就能定來源,其中 231 筆的上下文只有
# remake 標記」,本來要把那 231 筆當成「逐行掃描藏起來的可疑集合」寫進報告。
#
# 陰性對照直接否決:把 context 視窗**挪到同一份文件裡與主張無關的位置**
# (`ctx_shift` 137/501/1009 行),newly_remake 得到 224/198/211 筆——與真實鄰接的
# 214 筆一樣多甚至更多,false_original 還從 68 漲到 94~124。鄰接關係打散後訊號沒掉,
# 表示它量到的根本不是「主張旁邊的證據」,而是「這份文件通篇都在講 remake」。
#
# 結論:context 視窗對這份語料**沒有鑑別力**,已移除。資料實際支撐的是**文件層級**的
# 來源密度(見 `doc_provenance()`)——那本來就是首次人工複核用的分層方式
# (174 筆裡 148 筆落在本質上就是 remake 紀錄的文件),只是這次把它變成可量測的。
# 用 `ctx_lines=0` 當對照沒有用:那會讓 context 退化成主張本身,恆等於逐行結果。

# 第二個**被對照組否決**的改動,同樣留紀錄:
#
# context 視窗失敗後,我改用「文件層級 remake 標記密度」來重現人工分層
# (148 筆預期 / 26 筆要處理)。也不成立:`58-remake-live-verification-log.md`
# ——這份文件本身就是 remake 實機驗證記錄——密度只有 0.17;把裸位址排除後升到 0.23,
# 但同時 `11-enemy-ai.md` 變成 0.27、`27-...-checklist.md` 變成 0.34,**比 doc58 還高**,
# 與人工判讀完全相反。任何門檻都切不出正確的那條線。
#
# 原因不難理解:「這份文件本質上是 remake 側紀錄」是**文件的用途**,不是任何文字統計
# 量得到的性質。doc58 通篇引用原版位址,因為它在比對兩邊;密度指標只看得到符號。
#
# 所以不假造推導不出來的指標,改成**明列 + 註明理由**的人工判斷,並讓它可被審查:
# 名單裡的文件若消失會被 selftest 抓到,名單外冒出新的 REMAKE_ONLY 文件會被報告點名。
REMAKE_SIDE_DOCS = {
    "58-remake-live-verification-log.md": "文件本身就是 remake 實機驗證記錄",
    "91-worklist.md": "M5 remake 工項清單(2026-09-03 已就地標記失效)",
    "92-m5-normal-playthrough-log.md": "remake 正常玩法遊玩記錄",
    "56-fd2-remake-sdd.md": "remake 的軟體設計文件",
    "42-re-vs-remake-gap-audit.md": "原版 vs remake 差異稽核,工作對象即 remake",
    "44-ch1-remake-vs-original.md": "ch01 remake/原版逐項對照",
    "57-ui-evidence-matrix.md": "UI 證據矩陣,本來就分欄追蹤兩側來源",
    "19-scenario-script-system-design.md": "remake 劇本腳本系統設計",
    "38-editor-design.md": "remake 編輯器設計",
    "41-packaging.md": "remake 打包發佈",
    "98-tooling-infrastructure.md": "工具紀錄,含 remake 期工具的歷史條目",
    "99-reflections-log.md": "跨輪反省記錄,含 remake 期反省",
    "SESSION-HANDOFF-2026-07-06.md": "remake 開發期的交接文件",
    "SESSION-HANDOFF-2026-09-03.md": "交接文件,含 remake 移除當下的狀態描述",
}


# 排除註記本身會提到 remake、也會帶「驗證」字樣,若不排掉就會被自己當成新的主張
# (而且是 REMAKE_ONLY),閘門會擋住自己的註記。帶這個標籤的行視為註記,不是主張。
# 標籤刻意寫得長而具體,避免誤傷正常敘述。
EXCLUSION_TAG = "[remake 證據排除]"


@dataclass
class Claim:
    file: str
    line: int
    status: str                 # 逐行分類(與 2026-09-03 首次稽核可直接比對)
    remake_hits: list[str]
    original_hits: list[str]
    excerpt: str
    addr_only: bool = False     # 逐行 ORIGINAL 是否只靠一個裸位址成立


def _hits(text: str, table: list[tuple[str, str]]) -> list[str]:
    out = []
    for pat, label in table:
        if re.search(pat, text):
            out.append(label)
    return sorted(set(out))


def classify(text: str) -> tuple[str, list[str], list[str]] | None:
    """回傳 (status, remake_hits, original_hits);沒有驗證語言則回傳 None。"""
    if not VERIFY_LANG.search(text):
        return None
    r = _hits(text, REMAKE_MARKERS)
    o = _hits(text, ORIGINAL_MARKERS)
    if r and o:
        status = "MIXED"
    elif r:
        status = "REMAKE_ONLY"
    elif o:
        status = "ORIGINAL"
    else:
        status = "NO_MARKER"
    return status, r, o


def scan(kb: Path) -> list[Claim]:
    claims: list[Claim] = []
    for p in sorted(kb.glob("*.md")):
        for n, line in enumerate(p.read_text(encoding="utf-8", errors="replace")
                                 .splitlines(), start=1):
            s = line.strip()
            if len(s) < 30 or EXCLUSION_TAG in s:
                continue
            got = classify(s)
            if got is None:
                continue
            status, r, o = got
            claims.append(Claim(p.name, n, status, r, o, s[:200],
                                addr_only=(status == "ORIGINAL"
                                           and not _hits(s, ORIGINAL_MARKERS_NAMED))))
    return claims


REGISTRY = REPO / "docs" / "data" / "remake_excluded_claims.json"


def _sha(excerpt: str) -> str:
    return hashlib.sha1(excerpt.encode("utf-8")).hexdigest()


def gate(claims: list[Claim], registry: Path = REGISTRY) -> tuple[list[Claim], list[dict]]:
    """2026-09-04 使用者判準:無條件排除 remake 證據的結論,以 DOSBox-X 原版為準。

    光把判準寫進文件擋不住下一輪再寫一筆進去,所以做成閘門:落在原版知識文件裡的
    REMAKE_ONLY 主張**必須**列管在 `docs/data/remake_excluded_claims.json`,否則
    `--gate` 失敗。

    以 excerpt 的 sha1 為鍵而不是行號:行號會因為任何一次插入而整份漂移,行號式登錄
    表會在無人察覺的情況下對錯行;文字被改動時 sha1 不合,反而正是需要重新判定的時候。

    回傳 (未列管的主張, 登錄表裡已找不到的條目)。
    """
    reg = json.loads(registry.read_text(encoding="utf-8"))["claims"]
    known = {(e["file"], e["excerpt_sha1"]) for e in reg}
    _, actionable = stratify(claims)
    seen = {(c.file, _sha(c.excerpt)) for c in actionable}
    return ([c for c in actionable if (c.file, _sha(c.excerpt)) not in known],
            [e for e in reg if (e["file"], e["excerpt_sha1"]) not in seen])


def stratify(claims: list[Claim]) -> tuple[list[Claim], list[Claim]]:
    """把 REMAKE_ONLY 分成「預期的」與「要處理的」。

    依 `REMAKE_SIDE_DOCS`(人工判斷,附理由),不是依任何自動指標——兩種自動分層
    都被對照組否決了,見該常數上方的紀錄。
    """
    ro = [c for c in claims if c.status == "REMAKE_ONLY"]
    return ([c for c in ro if c.file in REMAKE_SIDE_DOCS],
            [c for c in ro if c.file not in REMAKE_SIDE_DOCS])


def report(claims: list[Claim], only: str | None, limit: int) -> None:
    import collections
    by_status = collections.Counter(c.status for c in claims)
    print("=== 驗證主張總覽(依證據來源)===")
    for st in ("REMAKE_ONLY", "MIXED", "ORIGINAL", "NO_MARKER"):
        print(f"  {st:12} {by_status.get(st, 0):5}")
    print(f"  {'總計':12} {len(claims):5}\n")

    print("=== REMAKE_ONLY 依文件分佈(可疑集合)===")
    per_doc = collections.Counter(c.file for c in claims if c.status == "REMAKE_ONLY")
    for f, n in per_doc.most_common():
        print(f"  {n:4}  {f}")

    # ORIGINAL 的兩種強度不該混為一談(見 ADDR_MARKER 的註解)。
    ao = sum(1 for c in claims if c.addr_only)
    orig = by_status.get("ORIGINAL", 0)
    print(f"\n=== ORIGINAL 的證據強度 ===")
    print(f"  具名原版工具/資產支撐   {orig - ao:5}")
    print(f"  只有一個裸位址          {ao:5}  ← 可信度較弱,不等於做過原版驗證")

    expected, actionable = stratify(claims)
    print("\n=== REMAKE_ONLY 分層(依 REMAKE_SIDE_DOCS 人工名單)===")
    print(f"  落在 remake 側紀錄文件(預期,非問題)  {len(expected):5}")
    print(f"  落在原版知識文件(**要處理**)          {len(actionable):5}")
    for f, n in collections.Counter(c.file for c in actionable).most_common():
        print(f"      {n:4}  {f}")
    missing = [f for f in REMAKE_SIDE_DOCS if not (KB / f).exists()]
    if missing:
        print(f"  ⚠ 名單裡有 {len(missing)} 份文件已不存在,名單過期:{missing}")

    if only:
        sel = [c for c in claims if c.status == only]
        print(f"\n=== {only} 明細(前 {min(limit, len(sel))} / {len(sel)})===")
        for c in sel[:limit]:
            print(f"\n  {c.file}:{c.line}")
            print(f"    標記: remake={c.remake_hits} original={c.original_hits}"
                  f"{' [僅裸位址]' if c.addr_only else ''}")
            print(f"    {c.excerpt[:170]}")


def stratify_no_marker(claims: list[Claim]) -> tuple[list[Claim], list[Claim]]:
    """把 NO_MARKER 分成「落在 remake 側紀錄文件」與「落在原版知識文件,要處理」。

    跟 `stratify()`(REMAKE_ONLY 版)共用同一份 `REMAKE_SIDE_DOCS` 人工名單,拆成
    獨立函式是為了讓 `no_marker_worklist()`(純印報表)跟這個判斷邏輯分開,才能
    不用捕捉 stdout 就測試分層對不對。
    """
    nm = [c for c in claims if c.status == "NO_MARKER"]
    return ([c for c in nm if c.file in REMAKE_SIDE_DOCS],
            [c for c in nm if c.file not in REMAKE_SIDE_DOCS])


NO_MARKER_REGISTRY = REPO / "docs" / "data" / "no_marker_reviewed.json"
NO_MARKER_VERDICTS = {"benign", "marker_added", "needs_verification"}


def load_no_marker_reviews(registry: Path = NO_MARKER_REGISTRY) -> list[dict]:
    return json.loads(registry.read_text(encoding="utf-8"))["reviews"]


def split_reviewed(claims: list[Claim],
                   registry: Path = NO_MARKER_REGISTRY) -> tuple[list[Claim], list[Claim]]:
    """把一批 NO_MARKER 主張分成「已登錄審閱過」與「還沒審閱」。

    2026-09-05:沒有這一層,`--no-marker-worklist` 每次重跑都會把已經讀過、判定過
    benign/marker_added 的主張跟真正沒動過的混在一起,讓人分不出這一輪實際上還
    剩多少要看——跟 REMAKE_ONLY 那邊 `gate()`/`remake_excluded_claims.json` 是
    同一個道理,只是這裡不是硬性閘門(NO_MARKER 本來就不是「必須列管才能過關」的
    性質),純粹是進度追蹤。
    """
    reviewed_keys = {(r["file"], r["excerpt_sha1"]) for r in load_no_marker_reviews(registry)}
    seen, unseen = [], []
    for c in claims:
        (seen if (c.file, _sha(c.excerpt)) in reviewed_keys else unseen).append(c)
    return seen, unseen


def _build_review_entry(file: str, line: int, verdict: str, note: str,
                        claims_by_key: dict[tuple[str, int], Claim],
                        already: set[tuple[str, str]]) -> tuple[dict | None, str | None]:
    """算出一筆審閱登錄項,或回傳失敗原因(不寫檔——寫檔是呼叫端的事,拆開是為了
    讓 `--mark-reviewed-batch` 能一次驗證整批、只成功寫入一次檔案)。"""
    if verdict not in NO_MARKER_VERDICTS:
        return None, f"verdict 必須是 {sorted(NO_MARKER_VERDICTS)} 之一,收到 {verdict!r}"
    match = claims_by_key.get((file, line))
    if match is None:
        return None, (f"{file}:{line} 不是目前掃描結果裡的 NO_MARKER 主張——"
                      "行號可能已經漂移(檔案被改過),重新掃一次確認正確行號再登錄。")
    sha = _sha(match.excerpt)
    if (file, sha) in already:
        return None, f"{file}:{line} 已經登錄過,不重複新增(如果判定要改,先手動刪除舊條目)。"
    return {"file": file, "line": line, "excerpt_sha1": sha,
            "excerpt": match.excerpt, "verdict": verdict, "note": note}, None


def mark_reviewed(file: str, line: int, verdict: str, note: str,
                  claims: list[Claim], registry: Path = NO_MARKER_REGISTRY) -> int:
    """把 `file:line` 對應的 NO_MARKER 主張登錄進審閱表。回傳 0 成功、非 0 失敗。"""
    reg = json.loads(registry.read_text(encoding="utf-8"))
    already = {(r["file"], r["excerpt_sha1"]) for r in reg["reviews"]}
    claims_by_key = {(c.file, c.line): c for c in claims if c.status == "NO_MARKER"}
    entry, err = _build_review_entry(file, line, verdict, note, claims_by_key, already)
    if err:
        print(err, file=sys.stderr)
        return 2
    reg["reviews"].append(entry)
    registry.write_text(json.dumps(reg, ensure_ascii=False, indent=1) + "\n", encoding="utf-8")
    print(f"已登錄 {file}:{line} verdict={verdict}")
    return 0


def mark_reviewed_batch(items: list[dict], claims: list[Claim],
                        registry: Path = NO_MARKER_REGISTRY) -> int:
    """一次登錄多筆(`{file, line, verdict, note}` 的清單)。

    2026-09-05:1782 筆待審閱、單筆 CLI 一次一筆效率太低,加這個是為了讓一次審完
    一整份文件(甚至好幾份)能一次寫檔,而不是每筆都重讀重寫 JSON。**每一筆各自
    獨立驗證**(verdict 合法、行號存在、沒有重複),失敗的印出來但不中止其餘筆——
    一批 50 筆裡有 1 筆行號漂移,不該讓另外 49 筆全部作廢重來。**只有全部驗證過
    的那些筆會被寫進檔案**,失敗的完全不寫入(不會半套)。
    """
    reg = json.loads(registry.read_text(encoding="utf-8"))
    already = {(r["file"], r["excerpt_sha1"]) for r in reg["reviews"]}
    claims_by_key = {(c.file, c.line): c for c in claims if c.status == "NO_MARKER"}
    ok, fails = [], []
    seen_this_batch: set[tuple[str, str]] = set()
    for it in items:
        entry, err = _build_review_entry(it["file"], it["line"], it["verdict"],
                                         it.get("note", ""), claims_by_key,
                                         already | seen_this_batch)
        if err:
            fails.append(f"{it['file']}:{it['line']}  {err}")
            continue
        seen_this_batch.add((entry["file"], entry["excerpt_sha1"]))
        ok.append(entry)
    if ok:
        reg["reviews"].extend(ok)
        registry.write_text(json.dumps(reg, ensure_ascii=False, indent=1) + "\n",
                            encoding="utf-8")
    print(f"批次登錄:成功 {len(ok)} 筆、失敗 {len(fails)} 筆")
    for f in fails:
        print(f"  FAIL  {f}")
    return 0 if not fails else 1


def no_marker_worklist(claims: list[Claim], out_dir: Path | None) -> None:
    """把 NO_MARKER 存量按檔案分組、**依筆數由少到多排序**印出來。

    2026-09-05:3987+ 筆 NO_MARKER 本身不是能一次做完的量,但它不是均勻分布在
    35 個文件裡的——先前的「文件層級標記密度」自動分類已被本檔上方負對照否決
    (量不出「這份文件本質上是不是 remake 紀錄」),但**單純數筆數**是另一回事,
    不涉及任何猜測來源的判斷,只是把「一次做完 3987 筆」重新框成「依序做完
    N 份文件,每份幾筆到幾十筆不等」——跟 2026-09-05 稍早那次 27 筆
    REMAKE_ONLY 逐筆複核走的是同一個「先讓範圍變得可管理」的做法,不是新招。

    不猜測、不分類來源,只排序——真正的人工判讀(這句話到底該補 ORIGINAL 還是
    REMAKE_ONLY 依據,還是根本沒有問題只是漏標)留給實際讀那份文件的人或後續任務。
    """
    import collections
    on_remake_side, needs_review_all = stratify_no_marker(claims)
    already_reviewed, needs_review = split_reviewed(needs_review_all)
    print(f"\n=== NO_MARKER 分層(沿用 REMAKE_SIDE_DOCS 名單)===")
    print(f"  落在 remake 側紀錄文件(優先度低)     {len(on_remake_side):5}")
    print(f"  落在原版知識文件,已登錄審閱過        {len(already_reviewed):5}")
    print(f"  落在原版知識文件,**還沒審閱**          {len(needs_review):5}")

    per_doc: dict[str, list[Claim]] = collections.defaultdict(list)
    for c in needs_review:
        per_doc[c.file].append(c)
    ordered = sorted(per_doc.items(), key=lambda kv: len(kv[1]))
    print(f"\n=== 原版知識文件裡還沒審閱的 NO_MARKER 待辦清單(依檔案筆數由少到多,"
          f"共 {len(needs_review)} 筆、{len(ordered)} 份文件)===")
    running = 0
    for f, cs in ordered:
        running += len(cs)
        print(f"  {len(cs):4}  {f}  (累計 {running}/{len(needs_review)})")
    if out_dir:
        out_dir.mkdir(parents=True, exist_ok=True)
        for f, cs in ordered:
            payload = [{"file": c.file, "line": c.line, "excerpt": c.excerpt} for c in cs]
            (out_dir / f"{f}.json").write_text(
                json.dumps(payload, ensure_ascii=False, indent=1), encoding="utf-8")
        (out_dir / "_order.json").write_text(
            json.dumps([{"file": f, "count": len(cs)} for f, cs in ordered],
                      ensure_ascii=False, indent=1),
            encoding="utf-8")
        print(f"\n已匯出 {len(ordered)} 份審閱包到 {out_dir}"
              "(每份文件一個 JSON,`_order.json` 是建議處理順序——由少到多)。")


def scan_diff(base: str = "HEAD") -> list[Claim]:
    """只掃 `git diff <base>` 裡**新增**的 knowledge-base 行,不重掃全庫。

    2026-09-05:3987 筆 NO_MARKER 是存量問題(見 SESSION-HANDOFF 的討論——文字層級的
    自動分類已經被本檔上方兩個負對照否決,不重做),但**新增的**沒有標記的驗證主張
    是可以在源頭擋下來的存量控制,跟修好水管漏水與擦掉已經漏出來的水是兩件事。
    這個函式只服務後者:讓 `--diff` 模式能當 pre-commit 檢查用,而不必每次都掃
    全庫的 6700+ 筆主張。

    解析 unified diff 的加號行 + `@@ ... +start,count @@` 追蹤新檔案的行號——
    不能只用行序號累加,因為一個 hunk 可能不是從檔案開頭起算。
    """
    r = subprocess.run(["git", "diff", "--unified=0", base, "--",
                        "docs/knowledge-base/*.md"],
                       cwd=REPO, capture_output=True, text=True,
                       encoding="utf-8", errors="replace")
    return parse_diff_claims(r.stdout or "")


def parse_diff_claims(diff_text: str) -> list[Claim]:
    """`scan_diff()` 的純解析部分,拆出來是為了能不碰真實 git/檔案系統就測試。

    2026-09-05:使用者要求「新建工具請正反向驗證」——`scan_diff()` 直接呼叫
    `subprocess.run(["git", "diff", ...])`,測試若要驗證「多個 hunk」「刪除行
    不佔行號」這類邏輯,勢必要嘛真的改檔案跑 git diff(慢、會弄髒工作區、
    測試失敗時還要確保還原),要嘛把「解析 unified diff 文字」單獨拆成純函式、
    餵合成的 diff 字串進去。選後者。
    """
    claims: list[Claim] = []
    cur_file = None
    cur_line = None
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
                s = raw[1:].strip()
                if len(s) >= 30 and EXCLUSION_TAG not in s:
                    got = classify(s)
                    if got is not None:
                        status, hr, ho = got
                        claims.append(Claim(cur_file, cur_line, status, hr, ho, s[:200],
                                            addr_only=(status == "ORIGINAL"
                                                       and not _hits(s, ORIGINAL_MARKERS_NAMED))))
            if cur_line is not None:
                cur_line += 1
        elif raw.startswith("-"):
            pass  # 刪除行不佔用新檔案的行號
    return claims


def scan_text_one(text: str) -> Claim:
    """把單行文字走完 scan() 的同一條路(含 addr_only 判定),給 selftest 用。"""
    status, r, o = classify(text)
    return Claim("<selftest>", 1, status, r, o, text[:200],
                 addr_only=(status == "ORIGINAL"
                            and not _hits(text, ORIGINAL_MARKERS_NAMED)))

# --------------------------------------------------------------------------- #
# 反向驗證
# --------------------------------------------------------------------------- #

def selftest() -> int:
    print("audit_evidence_provenance selftest — 故障注入 + 同組態陽性對照\n")
    fails: list[str] = []
    checks = 0

    def expect(text: str, want: str, why: str) -> None:
        nonlocal checks
        checks += 1
        got = classify(text)
        got_status = got[0] if got else "<無驗證語言>"
        if got_status != want:
            fails.append(f"期望 {want},實得 {got_status}:{why}\n      {text[:110]}")

    # --- 真實案例(來自 commit a1851a76,本專案實際踩過的那一個)---
    expect("Live-verified end to end by building fd2.exe and screenshotting the actual "
           "drawNativeCommandGrid render: all 5 labels render correctly",
           "REMAKE_ONLY", "a1851a76 的實際措辭,必須被抓出來")

    # --- 陽性對照:原版側驗證,不該被誤報 ---
    expect("2026-08-18 以 Ghidra headless 唯讀重讀 getBytes(0x51e63,30) 逐位元組複核",
           "ORIGINAL", "純靜態反組譯驗證")
    expect("用 DOSBox-X 實機 MEMDUMPBIN 讀出單位陣列,逐筆確認 char_id 與等級",
           "ORIGINAL", "原版實機驗證")
    expect("與青衫攻略的字面值逐項核對,26 筆全部吻合,已確認",
           "ORIGINAL", "外部攻略交叉驗證")

    # --- 配對對照:兩種標記都有 → MIXED,不可誤判成 REMAKE_ONLY ---
    expect("已用 DOSBox-X 原版截圖與 remake/ 產出的畫面逐像素比對,確認一致",
           "MIXED", "配對對照:兩邊都有標記時不可歸為 remake-only")

    # --- 配對對照 2:doc27 驗證表那種「原版位址 + remake 實作」的列 ---
    # 少了「裸位址算原版證據」這條規則時,這種列會被誤報成 REMAKE_ONLY。
    expect("| 2 | 物理攻擊地形修正 | ✓ `0x1acf3`/`0x51a12` + 本輪確認 `0x2f7b6` 內部"
           "經 `0x1f183` gate 呼叫同一張表 | `terrain.go TerrainAPDPPct` | ✓ 一致",
           "MIXED", "原版位址 + remake 實作對照 = MIXED,不是 remake-only")

    # --- 沒有驗證語言 → 不該進清單 ---
    checks += 1
    if classify("remake/internal/battle/model.go 定義了 Unit 結構") is not None:
        fails.append("純敘述(無驗證語言)不該被收進清單")

    # --- 有驗證語言但無來源標記 → NO_MARKER ---
    expect("這條結論已經確認無誤,細節見上文", "NO_MARKER",
           "出處不明本身也要被看見")

    # --- 2026-09-05 補:`\bFDTXT\b` 這類容器名標記漏判具體檔名的故障注入 ---
    expect("這段對話已經確認來自 FDTXT_033 的原始位元組", "ORIGINAL",
           "正對照:FDTXT_033 這種具體檔名(底線+數字)必須命中容器標記,"
           "先前 \\bFDTXT\\b 版本在 T 與 _ 之間找不到邊界,整條規則會漏判")
    expect("這段對話已經確認來自裸字 FDTXT 容器格式", "ORIGINAL",
           "回歸:沒有底線數字尾綴的原始寫法也不能被這次修正弄壞")
    expect("這件事已經確認跟 FDTXTFOOBAR 完全無關", "NO_MARKER",
           "負對照:FDTXT 黏在別的詞中間(FDTXTFOOBAR)不該被新的選擇性尾綴"
           "誤放行——尾綴只接受底線+數字,不接受任意字母")

    # --- 2026-09-04 補:反方向對照。第一版的 6 個對照**全部**在防「不該被誤報成
    # REMAKE_ONLY」,一個都沒防「不該被誤報成 ORIGINAL」——而後者才是危險方向:
    # 假 REMAKE_ONLY 只浪費人工複核,假 ORIGINAL 會讓 remake 證據永久隱形。
    checks += 2
    if classify("已確認遮罩值為 `0x0080`")[0] != "ORIGINAL":
        fails.append("裸位址仍應算 ORIGINAL 標記(否則 doc27 那類驗證表又會壞掉)")
    _s = scan_text_one("已確認遮罩值為 `0x0080`")
    if not _s.addr_only:
        fails.append("只有裸位址的 ORIGINAL 必須標記 addr_only,"
                     "否則它與『Ghidra 逐指令複核』被當成同一種可信度")
    checks += 1
    if scan_text_one("2026-08-18 以 Ghidra 唯讀重讀 `0x51e63` 逐位元組複核").addr_only:
        fails.append("具名原版工具支撐的 ORIGINAL 不該被標成 addr_only")

    # --- FLAME2 迴歸:原版目錄名含 `E2`,不可被當成「E2E 驗證」收進來 ---
    checks += 2
    if classify("遊戲本體在 `org_game/炎龍騎士團/FLAME2/`,攻略鏡像在 `references/`") \
            is not None:
        fails.append("`FLAME2` 又被當成驗證語言收進來了(E2 迴歸)")
    if classify("E2E 測試已通過,全鏈路無誤") is None:
        fails.append("修 E2 的同時把真正的 E2E 主張也擋掉了(過度修正)")

    # --- 排除註記不可被當成新主張(否則閘門會擋住自己的註記)。
    #     配對對照:拿掉標籤的同一句話**必須**照樣被收進來,證明是標籤在作用,
    #     不是這句話剛好不像主張。---
    _tag = (f"> ⛔ **{EXCLUSION_TAG}**(2026-09-04):本節結論的證據來自 "
            "`remake/internal/battle`,依現行判準視為未驗證")
    checks += 2
    if classify(_tag) is None or EXCLUSION_TAG not in _tag:
        fails.append("測資本身就不是主張,這組對照沒有鑑別力")
    if classify(_tag.replace(EXCLUSION_TAG, "備註")) is None:
        fails.append("配對對照:拿掉標籤後這句話也不算主張,無法證明是標籤在作用")

    # --- 對照組:確認掃描器真的掃得到東西(避免空掃過關)---
    real = scan(KB)
    checks += 2
    if len(real) < 50:
        fails.append(f"對照組:實際掃描只找到 {len(real)} 筆驗證主張,"
                     "疑似掃描器沒作用(空掃會讓所有檢查假通過)")
    if not any(c.status == "REMAKE_ONLY" for c in real):
        fails.append("對照組:實際知識庫裡一筆 REMAKE_ONLY 都沒有,與本專案已知歷史不符")

    # --- 分層名單:它的失效模式不是算錯,而是**過期**(文件改名/刪除後悄悄失準)。---
    checks += 2
    _missing = [f for f in REMAKE_SIDE_DOCS if not (KB / f).exists()]
    if _missing:
        fails.append(f"REMAKE_SIDE_DOCS 名單過期,這些文件已不存在:{_missing}")
    if not all(REMAKE_SIDE_DOCS.values()):
        fails.append("名單裡有條目沒寫理由——人工判斷沒附理由就無法被審查")

    # --- 分層必須在真實語料上真的切開,且比例要接近人工複核的量級
    #     (預期 ≫ 要處理)。只要求「兩邊都非空」太鬆:上一版的密度指標切成
    #     168/3 也能通過那種檢查,卻與人工判讀完全相反。---
    expected, actionable = stratify(real)
    checks += 2
    if not expected or not actionable:
        fails.append(f"分層沒作用:預期={len(expected)} 要處理={len(actionable)},"
                     "有一邊是空的")
    if len(expected) <= len(actionable):
        fails.append(f"分層方向可疑:預期({len(expected)})不多於要處理"
                     f"({len(actionable)})——人工複核的量級是 148:26,"
                     "反過來代表名單或標記表出了問題")

    # --- 已知真值錨點:doc58 是 remake 實機驗證記錄,它的 REMAKE_ONLY **必須**
    #     落在「預期」那一側。這是兩個自動指標都答錯的那一題。---
    checks += 1
    if any(c.file == "58-remake-live-verification-log.md" for c in actionable):
        fails.append("真值錨點:doc58(remake 實機驗證記錄)被判為『要處理』——"
                     "這正是密度指標答錯的那一題")

    # --- 閘門:真實語料必須全數列管(現狀),而**故障注入必須讓它失敗**。
    #     一個永遠通過的閘門擋不住任何東西,兩個方向都要驗。---
    checks += 3
    unreg, stale = gate(real)
    if unreg:
        fails.append(f"閘門:真實語料有 {len(unreg)} 筆未列管,"
                     f"首筆 {unreg[0].file}:{unreg[0].line}")
    if stale:
        fails.append(f"閘門:登錄表有 {len(stale)} 筆已找不到對應主張(文字被改過?),"
                     f"首筆 {stale[0]['file']}")
    _fake = Claim("11-enemy-ai.md", 1, "REMAKE_ONLY", ["remake 路徑"], [],
                  "本輪已確認此結論,證據為 `remake/internal/battle/model.go`")
    if not gate(real + [_fake])[0]:
        fails.append("故障注入:塞進一筆未列管的 remake 證據主張,閘門竟然放行——"
                     "這個閘門擋不住任何東西")

    # ======================================================================= #
    # 2026-09-05 新增:`--diff`/`--no-marker-worklist` 的正反向驗證
    # (使用者明確要求「新建工具請正反向驗證」)
    # ======================================================================= #

    # --- parse_diff_claims:負對照,新增 NO_MARKER 行必須被抓出來 ---
    checks += 1
    diff_no_marker = (
        "diff --git a/docs/knowledge-base/99-fake.md b/docs/knowledge-base/99-fake.md\n"
        "--- a/docs/knowledge-base/99-fake.md\n"
        "+++ b/docs/knowledge-base/99-fake.md\n"
        "@@ -10,0 +11,1 @@\n"
        "+這條結論已經確認無誤,但完全沒有寫出任何來源標記,占滿三十字元測試用。\n"
    )
    got = parse_diff_claims(diff_no_marker)
    if not (len(got) == 1 and got[0].status == "NO_MARKER"
            and got[0].file == "99-fake.md" and got[0].line == 11):
        fails.append(f"parse_diff_claims 負對照失敗:應抓到 99-fake.md:11 的 NO_MARKER,"
                     f"實得 {got}")

    # --- 正對照:同一個位置換成有原版位址的行,`parse_diff_claims` 本身仍會把它列進
    #     回傳值(它跟 `scan()` 一樣回傳全部有驗證語言的主張,不只是「有問題」的)——
    #     正對照驗的是**分類結果是 ORIGINAL**,不是「完全不出現」;真正決定要不要
    #     攔下來是 `main()` 的 `--diff` 分支自己再過濾一次 status,這裡不重覆呼叫
    #     CLI 入口,只驗證 parse_diff_claims 給的分類是對的。 ---
    checks += 1
    diff_original = diff_no_marker.replace(
        "這條結論已經確認無誤,但完全沒有寫出任何來源標記,占滿三十字元測試用。",
        "這條結論已經用 DOSBox-X 反組譯確認,位址 0x12345,應該被放行測試用。")
    got = parse_diff_claims(diff_original)
    if not (len(got) == 1 and got[0].status == "ORIGINAL"):
        fails.append(f"parse_diff_claims 正對照失敗:帶原版標記的新增行該分類成 ORIGINAL,"
                     f"實得 {got}")

    # --- 負對照:REMAKE_ONLY 新增行,且不在 REMAKE_SIDE_DOCS,main() 該視為 FAIL ---
    checks += 1
    diff_remake_only = diff_no_marker.replace(
        "這條結論已經確認無誤,但完全沒有寫出任何來源標記,占滿三十字元測試用。",
        "這條結論已經用 fd2-linux-verify 跑過 go test 確認,drawNativeCommandGrid 正常。")
    got = parse_diff_claims(diff_remake_only)
    if not (len(got) == 1 and got[0].status == "REMAKE_ONLY"
            and got[0].file not in REMAKE_SIDE_DOCS):
        fails.append(f"parse_diff_claims 負對照失敗:REMAKE_ONLY 新增行該被抓到"
                     f"且該檔不在 REMAKE_SIDE_DOCS,實得 {got}")

    # --- 正對照:同一種 REMAKE_ONLY 措辭,但落在 REMAKE_SIDE_DOCS 名單裡的文件——
    #     main() 的 --diff 邏輯必須認得這是「預期」,不能一律當成新增問題攔下來。
    #     這裡直接檢查 main() 用的判斷式本身(REMAKE_SIDE_DOCS 成員檢查),
    #     不重跑一次 main()(CLI 進入點不適合在 selftest 裡呼叫)。 ---
    checks += 1
    diff_remake_side = diff_remake_only.replace(
        "docs/knowledge-base/99-fake.md", "docs/knowledge-base/58-remake-live-verification-log.md")
    got = parse_diff_claims(diff_remake_side)
    unreg_here = [c for c in got if c.status == "REMAKE_ONLY" and c.file not in REMAKE_SIDE_DOCS]
    if unreg_here or not got or got[0].file not in REMAKE_SIDE_DOCS:
        fails.append(f"parse_diff_claims 正對照失敗:REMAKE_SIDE_DOCS 名單內文件的新增"
                     f"REMAKE_ONLY 行,--diff 的『未預期』過濾不該把它算進去,實得 {got}")

    # --- 多個 hunk:行號要各自從自己的 @@ 起算,不能整份檔案累加 ---
    checks += 1
    diff_multi_hunk = (
        "+++ b/docs/knowledge-base/99-fake.md\n"
        "@@ -1,0 +2,1 @@\n"
        "+這條結論已經確認無誤,但完全沒有寫出任何來源標記,占滿三十字元測試用一。\n"
        "@@ -50,0 +80,1 @@\n"
        "+這條結論也已經確認無誤,同樣沒有來源標記,占滿三十字元測試用二號內容。\n"
    )
    got = sorted(parse_diff_claims(diff_multi_hunk), key=lambda c: c.line)
    if [c.line for c in got] != [2, 80]:
        fails.append(f"parse_diff_claims 多 hunk 失敗:期望行號 [2, 80],"
                     f"實得 {[c.line for c in got]}——代表行號被跨 hunk 累加而非各自起算")

    # --- 刪除行:context 裡混雜「-」行時,不能讓它偷佔掉新檔案的行號計數 ---
    checks += 1
    diff_with_deletion = (
        "+++ b/docs/knowledge-base/99-fake.md\n"
        "@@ -5,2 +5,2 @@\n"
        "-這是被刪掉的舊行,內容不重要,只是要佔一行測試刪除不影響行號一二三四五。\n"
        "-這也是被刪掉的舊行,同樣不重要,純粹佔位測試刪除不影響行號一二三四五六。\n"
        "+這條結論已經確認無誤,但完全沒有寫出任何來源標記,占滿三十字元測試用。\n"
        "+這條結論已經確認無誤,同上,依然沒有任何來源標記,占滿三十字元測試二。\n"
    )
    got = sorted(parse_diff_claims(diff_with_deletion), key=lambda c: c.line)
    if [c.line for c in got] != [5, 6]:
        fails.append(f"parse_diff_claims 刪除行失敗:期望新增的兩行落在 [5, 6],"
                     f"實得 {[c.line for c in got]}——代表『-』行被誤算進新檔案行號")

    # --- stratify_no_marker:負對照,原版知識文件裡的 NO_MARKER 必須落在「要處理」---
    checks += 1
    _nm_fake_review = Claim("11-enemy-ai.md", 1, "NO_MARKER", [], [], "測試用")
    _nm_fake_remake_side = Claim("58-remake-live-verification-log.md", 1, "NO_MARKER", [], [],
                                 "測試用")
    on_side, review = stratify_no_marker([_nm_fake_review, _nm_fake_remake_side])
    if _nm_fake_review not in review or _nm_fake_review in on_side:
        fails.append("stratify_no_marker 負對照失敗:原版知識文件的 NO_MARKER "
                     "沒有被分進『要處理』")

    # --- stratify_no_marker:正對照,REMAKE_SIDE_DOCS 文件的 NO_MARKER 必須落在
    #     「remake 側」,不能混進『要處理』膨脹待辦清單 ---
    checks += 1
    if _nm_fake_remake_side not in on_side or _nm_fake_remake_side in review:
        fails.append("stratify_no_marker 正對照失敗:REMAKE_SIDE_DOCS 文件的 NO_MARKER "
                     "跑進了『要處理』清單")

    # --- 對真實語料的合理性檢查:兩層加起來要等於全部 NO_MARKER,不能漏筆或重複算 ---
    checks += 1
    real_on_side, real_review = stratify_no_marker(real)
    real_nm_total = sum(1 for c in real if c.status == "NO_MARKER")
    if len(real_on_side) + len(real_review) != real_nm_total:
        fails.append(f"stratify_no_marker 對真實語料算不平:on_side={len(real_on_side)} + "
                     f"review={len(real_review)} != 全部 NO_MARKER {real_nm_total}")

    # ======================================================================= #
    # 2026-09-05 新增:NO_MARKER 審閱登錄表(`no_marker_reviewed.json`)的正反向驗證
    # ======================================================================= #
    import tempfile
    with tempfile.TemporaryDirectory() as tmpdir:
        tmp_reg = Path(tmpdir) / "no_marker_reviewed_test.json"
        tmp_reg.write_text(json.dumps({"_policy": "test", "reviews": []}), encoding="utf-8")

        _target = next((c for c in real if c.status == "NO_MARKER"), None)
        checks += 1
        if _target is None:
            fails.append("找不到任何真實 NO_MARKER 主張可以拿來測 mark_reviewed,"
                         "語料可能整個變了")
        else:
            # --- 正對照:合法登錄應該成功,而且 split_reviewed 要把它分進『已審閱』 ---
            checks += 1
            rc = mark_reviewed(_target.file, _target.line, "benign", "selftest",
                               real, registry=tmp_reg)
            if rc != 0:
                fails.append(f"mark_reviewed 正對照失敗:合法輸入卻回傳非 0({rc})")
            seen, unseen = split_reviewed([_target], registry=tmp_reg)
            if _target not in seen or _target in unseen:
                fails.append("split_reviewed 正對照失敗:剛登錄的主張沒有被分進『已審閱』")

            # --- 負對照:重複登錄同一筆必須拒絕,不能靜默疊加或覆寫 ---
            checks += 1
            rc2 = mark_reviewed(_target.file, _target.line, "benign", "selftest 第二次",
                               real, registry=tmp_reg)
            if rc2 == 0:
                fails.append("mark_reviewed 負對照失敗:重複登錄同一筆竟然成功了")

            # --- 負對照:非法 verdict 必須拒絕 ---
            checks += 1
            rc3 = mark_reviewed(_target.file, _target.line, "not_a_real_verdict", "x",
                               real, registry=tmp_reg)
            if rc3 == 0:
                fails.append("mark_reviewed 負對照失敗:非法 verdict 竟然被接受")

            # --- 負對照:file:line 對不上任何 NO_MARKER 主張(行號漂移/打錯)必須拒絕 ---
            checks += 1
            rc4 = mark_reviewed(_target.file, 999999, "benign", "x", real, registry=tmp_reg)
            if rc4 == 0:
                fails.append("mark_reviewed 負對照失敗:對不到主張的行號竟然被接受")

        # --- mark_reviewed_batch:正對照,混合成功+失敗的一批,成功的要真的寫入、
        #     失敗的不能拖累成功的那些(部分失敗不是全部作廢) ---
        checks += 1
        _others = [c for c in real if c.status == "NO_MARKER"][:3]
        if len(_others) < 2:
            fails.append("找不到至少 2 筆真實 NO_MARKER 主張測 mark_reviewed_batch")
        else:
            tmp_reg2 = Path(tmpdir) / "no_marker_reviewed_batch_test.json"
            tmp_reg2.write_text(json.dumps({"_policy": "test", "reviews": []}),
                               encoding="utf-8")
            batch = [
                {"file": _others[0].file, "line": _others[0].line,
                 "verdict": "benign", "note": "batch selftest ok #1"},
                {"file": "不存在的檔案.md", "line": 1,
                 "verdict": "benign", "note": "batch selftest 故意失敗"},
                {"file": _others[1].file, "line": _others[1].line,
                 "verdict": "benign", "note": "batch selftest ok #2"},
            ]
            rc5 = mark_reviewed_batch(batch, real, registry=tmp_reg2)
            if rc5 == 0:
                fails.append("mark_reviewed_batch 負對照失敗:批次裡混了一筆對不到的"
                             "項目,整體回傳碼卻是 0(該回報有失敗)")
            written = load_no_marker_reviews(tmp_reg2)
            written_keys = {(r["file"], r["line"]) for r in written}
            if (_others[0].file, _others[0].line) not in written_keys:
                fails.append("mark_reviewed_batch 正對照失敗:批次裡合法的第 1 筆沒有"
                             "被寫入")
            if (_others[1].file, _others[1].line) not in written_keys:
                fails.append("mark_reviewed_batch 正對照失敗:批次裡合法的第 3 筆沒有"
                             "被寫入(前面那筆失敗不該拖累它)")
            if len(written) != 2:
                fails.append(f"mark_reviewed_batch 正對照失敗:應該只寫入 2 筆合法項目,"
                             f"實際寫入 {len(written)} 筆——失敗項目可能被誤寫入了")

            # --- 負對照:同一批裡兩筆指向同一筆主張(重複),第二筆該被拒絕 ---
            checks += 1
            tmp_reg3 = Path(tmpdir) / "no_marker_reviewed_batch_dup_test.json"
            tmp_reg3.write_text(json.dumps({"_policy": "test", "reviews": []}),
                               encoding="utf-8")
            dup_batch = [
                {"file": _others[0].file, "line": _others[0].line,
                 "verdict": "benign", "note": "第一次"},
                {"file": _others[0].file, "line": _others[0].line,
                 "verdict": "benign", "note": "同一批裡的重複,該被拒絕"},
            ]
            mark_reviewed_batch(dup_batch, real, registry=tmp_reg3)
            if len(load_no_marker_reviews(tmp_reg3)) != 1:
                fails.append("mark_reviewed_batch 負對照失敗:同一批裡對同一筆主張"
                             "登錄兩次,應該只留 1 筆卻沒有")

        # --- 對真實登錄表的合理性檢查:不能有重複鍵(同一個 file+sha1 出現兩次) ---
        checks += 1
        real_reviews = load_no_marker_reviews()
        real_keys = [(r["file"], r["excerpt_sha1"]) for r in real_reviews]
        if len(real_keys) != len(set(real_keys)):
            fails.append("docs/data/no_marker_reviewed.json 裡有重複的 (file, excerpt_sha1) 鍵")

    total = checks
    print(f"檢查:{total - len(fails)}/{total} 通過")
    for f in fails:
        print("  FAIL  " + f)
    if not fails:
        print(f"\n全部通過。掃描器在真實知識庫上找到 {len(real)} 筆驗證主張,"
              "其中包含 REMAKE_ONLY,證明不是空掃。")
    return 1 if fails else 0


def main() -> int:
    ap = argparse.ArgumentParser(description=__doc__,
                                 formatter_class=argparse.RawDescriptionHelpFormatter)
    ap.add_argument("--status", choices=["REMAKE_ONLY", "MIXED", "ORIGINAL", "NO_MARKER"])
    ap.add_argument("--limit", type=int, default=25)
    ap.add_argument("--json")
    ap.add_argument("--selftest", action="store_true")
    ap.add_argument("--gate", action="store_true",
                    help="落在原版知識文件的 remake 證據主張必須已列管,否則回傳非 0")
    ap.add_argument("--diff", metavar="BASE", nargs="?", const="HEAD",
                    help="只檢查 `git diff BASE`(預設 HEAD,即目前未提交的變更)新增的"
                         "knowledge-base 行——擋新增的 NO_MARKER/未列管 REMAKE_ONLY,"
                         "不重掃存量。適合當 pre-commit 用,比 --gate 快很多。")
    ap.add_argument("--no-marker-worklist", action="store_true",
                    help="把既有 NO_MARKER 存量依檔案分組、由少到多排序印出來,"
                         "把「3987 筆」重新框成一份可管理的文件待辦清單。"
                         "不猜測來源分類,純粹排序。")
    ap.add_argument("--export-worklist", metavar="DIR",
                    help="配合 --no-marker-worklist,把每份文件的 NO_MARKER 明細"
                         "(file/line/excerpt)寫成 DIR/<檔名>.json,供逐份審閱或委派。")
    ap.add_argument("--mark-reviewed", nargs=4, metavar=("FILE", "LINE", "VERDICT", "NOTE"),
                    help="把 FILE:LINE 這筆 NO_MARKER 主張登錄進"
                         "docs/data/no_marker_reviewed.json,VERDICT 為 benign/"
                         "marker_added/needs_verification 之一,NOTE 是判讀理由。"
                         "登錄過的主張之後 --no-marker-worklist 不會再列入'還沒審閱'。")
    ap.add_argument("--mark-reviewed-batch", metavar="JSON",
                    help="一次登錄多筆:JSON 檔內容是"
                         "`[{\"file\":..,\"line\":..,\"verdict\":..,\"note\":..}, ...]`。"
                         "每筆各自驗證,失敗的印出來但不影響其餘筆,只有驗證過的會寫入。"
                         "審一整份文件時比逐筆呼叫 --mark-reviewed 快很多。")
    args = ap.parse_args()

    if args.selftest:
        return selftest()

    if args.mark_reviewed:
        file, line_s, verdict, note = args.mark_reviewed
        try:
            line = int(line_s)
        except ValueError:
            print(f"LINE 必須是整數,收到 {line_s!r}", file=sys.stderr)
            return 2
        return mark_reviewed(file, line, verdict, note, scan(KB))

    if args.mark_reviewed_batch:
        items = json.loads(Path(args.mark_reviewed_batch).read_text(encoding="utf-8"))
        return mark_reviewed_batch(items, scan(KB))

    if args.diff is not None:
        new_claims = scan_diff(args.diff)
        bad = [c for c in new_claims if c.status == "NO_MARKER"]
        unreg_remake = [c for c in new_claims if c.status == "REMAKE_ONLY"
                        and c.file not in REMAKE_SIDE_DOCS]
        if not bad and not unreg_remake:
            print(f"diff 檢查通過:新增 {len(new_claims)} 筆驗證主張,"
                  "沒有 NO_MARKER 或未預期的 REMAKE_ONLY。")
            return 0
        for c in bad:
            print(f"  FAIL NO_MARKER(新增):{c.file}:{c.line}\n       {c.excerpt}")
        for c in unreg_remake:
            print(f"  FAIL REMAKE_ONLY(新增,不在 REMAKE_SIDE_DOCS 名單):"
                  f"{c.file}:{c.line}\n       {c.excerpt}")
        print(f"\n{len(bad)} 筆缺來源標記、{len(unreg_remake)} 筆疑似只有 remake 證據。"
              "補上原版側依據(位址/DOSBox-X/攻略等),或如果確實只有 remake 證據,"
              "登錄到 docs/data/remake_excluded_claims.json。")
        return 1

    if args.gate:
        unreg, stale = gate(scan(KB))
        expected, actionable = stratify(scan(KB))
        print(f"閘門:原版知識文件裡的 remake 證據主張 {len(actionable)} 筆,"
              f"已列管 {len(actionable) - len(unreg)} 筆")
        for e in stale:
            print(f"  ⚠ 登錄表條目已找不到(文字被改過或已刪除,需重新判定):"
                  f"{e['file']}  {e['excerpt'][:70]}")
        for c in unreg:
            print(f"  FAIL 未列管:{c.file}:{c.line}\n       {c.excerpt[:110]}")
        if unreg:
            print(f"\n未列管 {len(unreg)} 筆。依 2026-09-04 判準,remake 證據的結論一律"
                  "排除;新增這類主張必須同時登錄到 docs/data/remake_excluded_claims.json,"
                  "並註明它是 remake 實作敘述還是需要原版重驗的原版事實。")
            return 1
        print("通過。")
        return 0

    if not KB.is_dir():
        print(f"找不到知識庫目錄:{KB}", file=sys.stderr)
        return 2
    claims = scan(KB)
    report(claims, args.status, args.limit)
    if args.no_marker_worklist:
        no_marker_worklist(claims, Path(args.export_worklist) if args.export_worklist else None)
    if args.json:
        Path(args.json).write_text(
            json.dumps([asdict(c) for c in claims], ensure_ascii=False, indent=2),
            encoding="utf-8")
        print(f"\nwrote {args.json}")
    return 0


if __name__ == "__main__":
    sys.exit(main())
