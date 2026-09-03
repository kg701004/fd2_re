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
import json
import re
import sys
from dataclasses import dataclass, asdict
from pathlib import Path

REPO = Path(__file__).resolve().parent.parent
KB = REPO / "docs" / "knowledge-base"

for _s in (sys.stdout, sys.stderr):
    try:
        _s.reconfigure(encoding="utf-8", errors="backslashreplace")
    except (AttributeError, OSError):
        pass

# 「這句話在宣稱某件事被驗證過」的語言。刻意寬鬆——寧可多收再分類。
VERIFY_LANG = re.compile(
    r"(已證實|已確認|證實|確認|驗證|實測|逐位元組|逐字|閉合|E2|verified|confirmed"
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
    (r"\bFDTXT\b|\bFDOTHER\b|\bFDFIELD\b|\bFDSHAP\b|\bFDMUS\b|\bDATO\b|FDICON",
     "原版資產容器"),
    (r"FD2\.EXE", "原版執行檔"),
    # 2026-09-04 修正:裸的 FD2.EXE linear 位址本身就是原版側證據。
    # 少了這條會把 doc27 驗證表整批誤報成 remake-only——那張表的證據欄位正是
    # `0x2f7b6`/`0x276ec`/`0x1c75e` 這類反組譯位址,remake 欄只是「實作對照」。
    # 這是本工具第一版的實際缺陷,由逐筆人工複核發現。
    (r"\b0x[0-9a-fA-F]{4,6}\b", "原版 EXE 位址"),
]


@dataclass
class Claim:
    file: str
    line: int
    status: str
    remake_hits: list[str]
    original_hits: list[str]
    excerpt: str


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
            if len(s) < 30:
                continue
            got = classify(s)
            if got is None:
                continue
            status, r, o = got
            claims.append(Claim(p.name, n, status, r, o, s[:200]))
    return claims


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

    if only:
        sel = [c for c in claims if c.status == only]
        print(f"\n=== {only} 明細(前 {min(limit, len(sel))} / {len(sel)})===")
        for c in sel[:limit]:
            print(f"\n  {c.file}:{c.line}")
            print(f"    標記: remake={c.remake_hits}")
            print(f"    {c.excerpt[:170]}")


# --------------------------------------------------------------------------- #
# 反向驗證
# --------------------------------------------------------------------------- #

def selftest() -> int:
    print("audit_evidence_provenance selftest — 故障注入 + 同組態陽性對照\n")
    fails: list[str] = []

    def expect(text: str, want: str, why: str) -> None:
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
    if classify("remake/internal/battle/model.go 定義了 Unit 結構") is not None:
        fails.append("純敘述(無驗證語言)不該被收進清單")

    # --- 有驗證語言但無來源標記 → NO_MARKER ---
    expect("這條結論已經確認無誤,細節見上文", "NO_MARKER",
           "出處不明本身也要被看見")

    # --- 對照組:確認掃描器真的掃得到東西(避免空掃過關)---
    real = scan(KB)
    if len(real) < 50:
        fails.append(f"對照組:實際掃描只找到 {len(real)} 筆驗證主張,"
                     "疑似掃描器沒作用(空掃會讓所有檢查假通過)")
    if not any(c.status == "REMAKE_ONLY" for c in real):
        fails.append("對照組:實際知識庫裡一筆 REMAKE_ONLY 都沒有,與本專案已知歷史不符")

    total = 9
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
    args = ap.parse_args()

    if args.selftest:
        return selftest()

    if not KB.is_dir():
        print(f"找不到知識庫目錄:{KB}", file=sys.stderr)
        return 2
    claims = scan(KB)
    report(claims, args.status, args.limit)
    if args.json:
        Path(args.json).write_text(
            json.dumps([asdict(c) for c in claims], ensure_ascii=False, indent=2),
            encoding="utf-8")
        print(f"\nwrote {args.json}")
    return 0


if __name__ == "__main__":
    sys.exit(main())
