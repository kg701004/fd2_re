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
    (r"\bFDTXT\b|\bFDOTHER\b|\bFDFIELD\b|\bFDSHAP\b|\bFDMUS\b|\bDATO\b|FDICON",
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
    args = ap.parse_args()

    if args.selftest:
        return selftest()

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
    if args.json:
        Path(args.json).write_text(
            json.dumps([asdict(c) for c in claims], ensure_ascii=False, indent=2),
            encoding="utf-8")
        print(f"\nwrote {args.json}")
    return 0


if __name__ == "__main__":
    sys.exit(main())
