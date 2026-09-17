#!/usr/bin/env python3
"""fd2_re — 知識庫宣稱是「函式入口」的位址,有多少個拿得出證據?

為什麼需要這支工具
------------------
`verify_findings.py` 每輪報 `17/17 相符`,但 **17 是「有人記得登記的結論」數,不是文件
主張的數量**。doc25 §10 那整欄位址(全部 `0x356` 太低)能活過五輪、中間還有一輪「仔細
複驗」產出更有信心的錯答案,原因就是**它從來沒有被登記過** —— 滿分與它無關。

這支工具補的是那個分母:知識庫裡被宣稱為入口/handler/函式的位址,**有幾個拿得出
位元組層級的證據**。

判準:四個互相獨立的入口訊號(全部只讀 EXE 位元組,免 capstone、免 JVM)
--------------------------------------------------------------------
1. **Watcom 序頭**:`push imm32 ; call __STK(0x3702f)` —— 本專案既有的嚴格判準,541 個。
2. **直接 CALL 目標**:全 obj1 掃 `E8 rel32`,目標落在 obj1 內。
3. **fixup 目標**:被重定位表指向的 obj1 位址(間接跳表就是靠這個)。
4. **JMP 目標**(2026-09-17):全 obj1 掃 `E9 rel32`。thunk 的本體只由 jmp 抵達(`delay`
   `0x3790a` = `jmp 0x3e01d`),前三個訊號都看不到,卻是真實函式。

INNER:函式內部引用,不是入口主張(2026-09-17)
------------------------------------------
宣稱語言是「同一行有『函式/handler/入口』字樣」,於是文件講某函式時順帶提到的呼叫點、分支點
(`0x2c469` = `0x2c441 +0x28`)全部被算成「宣稱為入口」。2026-09-17 實測 955 個無訊號位址裡
770 個落在某個有訊號函式**內部**的合法指令邊界上 —— 它們不是入口主張,是內部引用。有 capstone
時把這一類分出來(INNER),不進棘輪分母;沒有 capstone(WSL)時閘門只印摘要、不比基準線。
已知上限:錯的位址若剛好落在別的函式內部的合法邊界上,也會被歸成 INNER(與邊界判準的 10/14 召回
同一個結構性上限);已登記為勘誤的位址在 INNER 之前就被分到 KNOWN_ERRATUM,不受影響。

**為什麼一定要三個**:541 那個集合是「需要堆疊探測的函式」,**不是全部函式**。小型
葉函式沒有序頭。實測 `0x4ebe3` 有 **40 個直接呼叫端**、起頭是乾淨的 `33 c0`
(`xor eax,eax`),但它**不在** 541 裡 —— 只用序頭判準會把它誤報成沒有證據。

判準的雙向控制(selftest 第 3、4 題,實測數字)
----------------------------------------------
* **正向**:`known_address_errata.json` 旗標中落在 obj1 的 13 個位址,**13/13 全部無訊號**。
  已證實錯的位址,本判準 100% 抓到。
* **負向**:`0x4ebe3`(40 個呼叫端)必須**有**訊號;`0x4e893`(0 個呼叫端、起頭
  `08 ba ...` 是指令中段)必須**無**訊號。這一對是實測出來的,不是構造的。

這支工具**不是閘門的全部,是量測**
----------------------------------
「無訊號」不等於「錯」。已知的合理來源至少有三類:
* 文件在談某個函式**內部**的位址(呼叫點、分支點),同一行剛好有「函式」兩個字;
* 2026-08-14 改基準 EXE 之前的舊版位址;
* 只透過 computed call 抵達、且其跳表不在本工具掃得到的地方的程式碼。

所以輸出分成 `KNOWN_ERRATUM`(已登記為錯,不算新債)與 `UNREVIEWED`(沒人看過),
並且**只對 UNREVIEWED 設雙向棘輪**:存量只能往下走,而且每次下降都會留在 commit 裡。
一次性把 963 筆判成待辦是錯的 —— 本專案已經量過一次類似的天真判準會產生 2836 筆偽陽性。

用法
----
    python tools/verify_address_claim_coverage.py                # 閘門
    python tools/verify_address_claim_coverage.py --report       # 依引用次數列出 UNREVIEWED
    python tools/verify_address_claim_coverage.py --addr 0x4e893 # 單一位址的四個訊號與分類
    python tools/verify_address_claim_coverage.py --triage       # 殘餘依『是否落在指令邊界』分流
    python tools/verify_address_claim_coverage.py --dossier 20 --json out.json   # 殘餘的判讀資料(四個假說)
    python tools/verify_address_claim_coverage.py --write-baseline
    python tools/verify_address_claim_coverage.py --selftest
"""

from __future__ import annotations

import argparse
import glob
import json
import os
import re
import struct
import sys
from collections import Counter

if hasattr(sys.stdout, "reconfigure"):
    sys.stdout.reconfigure(encoding="utf-8")
    sys.stderr.reconfigure(encoding="utf-8")

HERE = os.path.dirname(os.path.abspath(__file__))
ROOT = os.path.dirname(HERE)
sys.path.insert(0, HERE)

EXE = os.path.join(ROOT, "org_game", "炎龍騎士團", "FLAME2", "FD2.EXE")
KB = os.path.join(ROOT, "docs", "knowledge-base")
BASELINE = os.path.join(ROOT, "docs", "data", "address_claim_coverage_baseline.json")
ERRATA = os.path.join(ROOT, "docs", "data", "known_address_errata.json")

STACK_PROBE = 0x3702F

# 同一行出現這些字樣,才把該行的位址當成「被宣稱為入口」。刻意不含「位址」這種泛稱:
# 那會把每一行都算進來,分母就又變成「有人提過的位址」而不是「有人主張是入口的位址」。
CLAIM_WORDS = re.compile(
    r"入口|handler|函式|函數|entry\s*point|序頭|FUN_[0-9a-fA-F]|呼叫目標|dispatcher")
ADDR = re.compile(r"0x[0-9a-fA-F]{4,6}(?![0-9a-fA-F])")
# 2026-09-17 第二批審閱後加的兩條排除(都是「同一行有入口字樣」抓進來的非主張):
# * 範圍終點:`0x2670e..0x26995`、`0x1b750–0x1b83c` 的右端是函式結束(下一個函式的起點或末指令之後),不是入口。
# * 否定句:「0x154D1 只是 …中段,不能當施法入口」「不是任何函式的真正入口」是在說它**不是**入口。
RANGE_END = re.compile(r"(?:\.\.|–|—|~|-|到|至)\s*`?(0x[0-9a-fA-F]{4,6})(?![0-9a-fA-F])")
NEGATED = re.compile(r"不是(?:任何)?(?:函式)?(?:的)?(?:真正)?(?:的)?入口|不能當[^,。;]{0,12}入口|不是入口|非入口")


def load_image() -> tuple[bytes, dict, bytes, int, int]:
    """(檔案位元組, LE meta, obj1 程式碼, obj1 base, obj1 上界)。"""
    from le_xref import parse_le
    import disasm_le as D
    data = open(EXE, "rb").read()
    meta = parse_le(data)
    code, base = D.load_code(data, meta)
    return data, meta, code, base, base + meta["objs"][0]["vsize"]


def prologue_entries(code: bytes, base: int) -> set[int]:
    """訊號 1:`push imm32 ; call __STK`。與已登記結論 `584-entries`(541)同一判準。"""
    out = set()
    for i in range(len(code) - 10):
        if code[i] == 0x68 and code[i + 5] == 0xE8:
            addr = base + i
            if addr + 10 + struct.unpack_from("<i", code, i + 6)[0] == STACK_PROBE:
                out.add(addr)
    return out


def call_targets(code: bytes, base: int, hi: int) -> Counter:
    """訊號 2:直接 `E8 rel32` 的目標 -> 呼叫端數。"""
    out: Counter = Counter()
    for i in range(len(code) - 5):
        if code[i] == 0xE8:
            t = base + i + 5 + struct.unpack_from("<i", code, i + 1)[0]
            if base <= t < hi:
                out[t] += 1
    return out


def jmp_targets(code: bytes, base: int, hi: int) -> set[int]:
    """訊號 4:直接 `E9 rel32` 的目標(thunk 本體)。與 E8 掃描同樣接受資料位元組的偶然命中。"""
    out = set()
    for i in range(len(code) - 5):
        if code[i] == 0xE9:
            t = base + i + 5 + struct.unpack_from("<i", code, i + 1)[0]
            if base <= t < hi:
                out.add(t)
    return out


def fixup_targets(data: bytes, meta: dict, base: int, hi: int) -> set[int]:
    """訊號 3:重定位表指向 obj1 的位址(間接跳表靠這個)。"""
    import disasm_le as D
    return {t for t in D.build_fixups(data, meta).values() if base <= t < hi}


def signals() -> dict:
    data, meta, code, base, hi = load_image()
    pro = prologue_entries(code, base)
    cal = call_targets(code, base, hi)
    fix = fixup_targets(data, meta, base, hi)
    jmp = jmp_targets(code, base, hi)
    return {"base": base, "hi": hi, "code": code,
            "prologue": pro, "calls": cal, "fixups": fix, "jmps": jmp,
            "plausible": pro | set(cal) | fix | jmp}


def signals_for(sig: dict, addr: int) -> list[str]:
    out = []
    if addr in sig["prologue"]:
        out.append("Watcom 序頭")
    if addr in sig["calls"]:
        out.append(f"直接 CALL×{sig['calls'][addr]}")
    if addr in sig["fixups"]:
        out.append("fixup 目標")
    if addr in sig.get("jmps", ()):
        out.append("JMP 目標(thunk)")
    return out


def _capstone():
    """延遲匯入:`--triage` 才需要,`--selftest`/閘門在沒有 capstone 的 WSL 下仍可用。"""
    import capstone
    return capstone.Cs(capstone.CS_ARCH_X86, capstone.CS_MODE_32)


def containing_entry(sig: dict, addr: int, cache: dict) -> int | None:
    """`addr` 所在函式的入口 = 不大於它的最後一個可信入口候選;沒有則 None。

    2026-09-11 從 `boundary_from_entry` 裡抽出來,理由是突變測試:把
    `bisect_right(...) - 1` 改成 `- 2`(選到**前一個**函式)整組 selftest 照樣通過,
    因為從前一個函式線性反組譯通常也掃得到目標位址。抽成函式之後 selftest 第 (11) 題
    才打得到**真正在跑的這一份**,而不是在測試裡重寫一次同樣的邏輯。
    """
    import bisect
    ent = cache.setdefault("_ent", sorted(sig["plausible"]))
    i = bisect.bisect_right(ent, addr) - 1
    return ent[i] if i >= 0 else None


def boundary_from_entry(sig: dict, addr: int, _cache: dict | None = None) -> bool | None:
    """`addr` 是否落在合法指令邊界 —— **只從所在函式的入口單一起點**線性反組譯。

    回傳 True/False,無法判定(找不到所在函式或距離過遠)回 None。

    **為什麼不是多起點收斂**:那個做法試過,被自己的負向控制打掉。從 `addr` 之前
    k 個 byte 各起一次反組譯,看起來比較穩健,實測卻讓 14 個已知錯誤位址裡的 **5 個**
    被判成「是邊界」—— 短視窗從任意偏移起算會湊出自洽但錯誤的解碼,這是線性反組譯的
    經典偽陽性。單一起點(與 Ghidra 同源)反而乾淨:150 個已知正確入口 **0 誤報**。

    **已知上限**:對已知錯誤位址的召回率是 **10/14 = 71%**。抓不到的 4 個
    (`0x27fc9`/`0x320fc`/`0x3453e`/`0x36d98`)是錯位址但**剛好落在合法邊界上** ——
    「是邊界」不等於「是入口」。這個比率由 selftest 第 (8)(9) 題釘住。
    """
    cache = _cache if _cache is not None else {}
    entry = containing_entry(sig, addr, cache)
    if entry is None or addr - entry > 6000:
        return None
    if entry not in cache:
        md = cache.get("_md")
        if md is None:
            md = cache["_md"] = _capstone()
        off = entry - sig["base"]
        cache[entry] = {x.address for x in md.disasm(bytes(sig["code"][off:off + 6200]), entry)}
    return addr in cache[entry]


def triage() -> int:
    """把 UNREVIEWED 依「是否落在合法指令邊界」分流,非邊界者依引用次數排序印出。

    這是 `--report` 的下一層:`--report` 說「這些沒有證據」,本模式說
    「這些之中,**哪些連指令邊界都不是**」—— 後者才是候選的位址誤記。
    """
    try:
        _capstone()
    except ImportError:
        print("SKIP:本模式需要 capstone(閘門與 --selftest 不需要)")
        return 0
    r = classify_all()
    sig, un = r["sig"], r["unreviewed"]
    cache: dict = {}
    rows = [(a, len(un[a]), boundary_from_entry(sig, a, cache)) for a in un]
    nb = [x for x in rows if x[2] is False]
    tb = [x for x in rows if x[2] is True]
    nn = [x for x in rows if x[2] is None]
    print(f"UNREVIEWED {len(rows)} 個 -> 合法指令邊界 {len(tb)} / "
          f"**不在指令邊界 {len(nb)}** / 無法判定 {len(nn)}")
    print("(判準:誤報率 0/150 已知正確入口;對已知錯誤召回 10/14。"
          "「是邊界」不等於「是入口」,所以 tb 那一欄不代表正確。)\n")
    print(f"{'位址':>9} {'引用':>4}  所在函式")
    for a, n, _ in sorted(nb, key=lambda x: -x[1])[:40]:
        import bisect
        ent = cache["_ent"]
        i = bisect.bisect_right(ent, a) - 1
        e = ent[i] if i >= 0 else None
        print(f"{a:#09x} {n:4d}  {format(e, '#09x') if e else '?'}  (+{a - e if e else 0:#x})")
    return 0


# --------------------------------------------------------------------------- #
# --dossier:殘餘無訊號位址的判讀資料(2026-09-17)
# --------------------------------------------------------------------------- #
# INNER 分掉之後剩下的每一個都「不在指令邊界」:不是資料就是錯位址。逐一開 Ghidra 每個要
# 5–15 分鐘;這裡把能機械算的假說先算好,人只讀一份資料下結論。四個假說:
#   DATA      往前最近的 fixup 目標當表基底,偏移小且基底不是程式碼 -> 表格內部
#   EDITION   加上已知的舊→新位移(勘誤表與 EDITION_MOVED 實測的),落到有訊號入口/合法邊界
#   TYPO      ±16 bytes 內有有訊號入口
#   WORDING   引用行的措辭:表格/資料 vs 入口/函式 vs 舊版/勘誤
# 假說是候選,不是結論:勘誤登錄仍要人看過 —— 錯登一筆比留著不審更糟。
DATA_WINDOW = 0x2000
TYPO_WINDOW = 16
WORD_DATA = re.compile(r"表|table|資料|陣列|array|欄位|record|record|struct|offset|偏移")
WORD_OLD = re.compile(r"舊版|old edition|357074|勘誤|誤植|原標|應為")
WORD_CORR = re.compile(r"位址更正|位址已撤回|應為|新版對應|真正的?(函式)?入口|真正起於|落在[^|]{0,30}byte|勘誤|誤植|誤記|原標")


# 被文件自己的更正否決過的位移:+0x5844 對 0x2a2e8 提出 0x2fb2c(party montage 迴圈),而 doc32 L747 明寫
# 新版對應是 0x2ac7d。兩對 +0x5844 勘誤的 root_cause 也都寫「個別誤記、非系統性」。
DELTA_DENY = {
    0x5844: "0x2a2e8 的文件更正(0x2ac7d)否決;兩對來源勘誤自述為個別誤記",
    # 0x26896/0x26945 → 0x25a96/0x25b45 是同一批(doc36 第 8 輪)手動誤記,兩對同位移純屬同批;
    # 若 0x26xxx 真的整段移了 -0xe00,doc36 自己記的 FUN_0002670e 就不會還在 0x2670e。
    -0xe00: "doc36 第 8 輪同批誤記,不是區段位移(FUN_0002670e 兩版同址)",
}
DELTA_MIN_SUPPORT = 2


def edition_deltas(sig: dict) -> dict[int, str]:
    """已知的舊→新位址位移 -> 來源。只採**至少兩對**獨立配對支持的(EDITION_MOVED 的實測配對算兩對),
    且不在 DELTA_DENY 裡。一對就採會把個別誤記(0x2a2e8 的 +0x395、0x2cad7 的 -0x6985)當成系統性位移,
    2026-09-17 實測那樣會讓已知入口的誤提率從 2/100 升到 4/100。
    """
    support: dict[int, list[str]] = {}
    out: dict[int, str] = {}
    try:
        with open(ERRATA, encoding="utf-8") as f:
            for e in json.load(f).get("errata", []):
                try:
                    w, c = int(e["wrong_address"], 16), int(e["correct_address"], 16)
                except (KeyError, ValueError, TypeError):
                    continue
                if sig["base"] <= w < sig["hi"] and sig["base"] <= c < sig["hi"] and c != w:
                    support.setdefault(c - w, []).append(f"errata {w:#x}->{c:#x}")
    except (OSError, ValueError):
        pass
    try:
        import dump_chapter_beats as DC
        for op, (old, new) in DC.EDITION_MOVED.items():
            # 實測過的版本差(同一呼叫點在兩版分別呼叫的位址),不套支持數門檻
            out[new - old] = f"EDITION_MOVED {op}"
    except Exception:                                          # noqa: BLE001
        pass
    for delta, srcs in support.items():
        if delta in out or delta in DELTA_DENY:
            continue
        if len(srcs) >= DELTA_MIN_SUPPORT:
            out[delta] = f"{len(srcs)} 對:" + ", ".join(srcs)
    return out


def propose(sig: dict, addr: int, cache: dict, deltas: dict[int, str]) -> dict:
    """一個位址的四個假說(純機械,不看文件)。"""
    import bisect
    d: dict = {"addr": f"{addr:#07x}"}
    off = addr - sig["base"]
    d["bytes"] = sig["code"][off:off + 16].hex(" ")
    ent = containing_entry(sig, addr, cache)
    d["containing"] = None if ent is None else {"entry": f"{ent:#x}", "offset": addr - ent}
    fx = cache.setdefault("_fix", sorted(sig["fixups"]))
    i = bisect.bisect_right(fx, addr) - 1
    d["data"] = None
    if i >= 0 and addr - fx[i] <= DATA_WINDOW:
        fb = fx[i]
        d["data"] = {"base": f"{fb:#x}", "offset": addr - fb,
                     "base_is_code": fb in sig["prologue"] or fb in sig["calls"]}
    d["edition"] = []
    for delta, src in sorted(deltas.items()):
        cand = addr + delta
        if not sig["base"] <= cand < sig["hi"]:
            continue
        sigs = signals_for(sig, cand)
        if sigs:
            d["edition"].append({"delta": f"{delta:+#x}", "cand": f"{cand:#x}", "signals": sigs, "from": src})
    ent_sorted = cache.setdefault("_ent", sorted(sig["plausible"]))
    j = bisect.bisect_left(ent_sorted, addr - TYPO_WINDOW)
    near = []
    while j < len(ent_sorted) and ent_sorted[j] <= addr + TYPO_WINDOW:
        if ent_sorted[j] != addr:
            near.append(ent_sorted[j])
        j += 1
    d["typo"] = [f"{e:#x}({e - addr:+d})" for e in near]
    d["doc"] = []                      # 由 dossier() 以 wording() 的結果填:引用行自帶的更正位址
    # 假說排序:唯一的舊版位移命中 > 資料表(基底不是程式碼) > 多個位移命中 > 打字錯 > 不明。
    # 實測(selftest 14):EDITION 對 100 個已知入口只誤提 2 個;TYPO 誤提 14 個(小型 leaf 函式本來
    # 就相鄰),所以 TYPO 只當旁證,排最後。四種已知位移裡 +0x5844 與 +0x350 各出現在兩對勘誤上,
    # 勘誤表的 root_cause 寫「個別誤記、非系統性」—— 同一個位移出現兩次不像巧合,保留但由人判。
    # DOC 假說由 dossier() 在拿到引用行之後覆蓋(propose 不看文件)
    if len(d["edition"]) == 1:
        d["hypothesis"] = "EDITION"
    elif d["data"] and not d["data"]["base_is_code"]:
        d["hypothesis"] = "DATA"
    elif d["edition"]:
        d["hypothesis"] = "EDITION?"
    elif d["typo"]:
        d["hypothesis"] = "TYPO"
    else:
        d["hypothesis"] = "UNKNOWN"
    return d


def doc_corrections(sites: list[tuple[str, int]], addr: int, sig: dict) -> list[str]:
    """引用行若帶更正措辭(位址更正/應為/新版對應/真正入口/落在…byte),同一行的**其他**有訊號位址就是文件自己給的答案。

    第一批審閱(2026-09-17)10 個裡 6 個文件早就寫了正確位址,只是沒登錄勘誤表;這條假說讓它們直接浮出來,
    而且優先於位移推論 —— 0x2a2e8 的 +0x5844 位移候選就是被文件自己的更正(0x2ac7d)否決的。
    """
    out: list[str] = []
    for name, lineno in sites:
        try:
            lines = open(os.path.join(KB, name), encoding="utf-8", errors="replace").read().splitlines()
            text = lines[lineno - 1] if 1 <= lineno <= len(lines) else ""
        except OSError:
            continue
        if not WORD_CORR.search(text):
            continue
        for m in ADDR.findall(text):
            n = int(m, 16)
            if n != addr and sig["base"] < n < sig["hi"] and n in sig["plausible"] and f"{n:#x}" not in out:
                out.append(f"{n:#x}")
    return out


def wording(sites: list[tuple[str, int]], limit: int = 4) -> list[dict]:
    """引用行的原文與措辭分類(只看文件,與 propose 獨立)。"""
    out = []
    for name, lineno in sites[:limit]:
        try:
            lines = open(os.path.join(KB, name), encoding="utf-8", errors="replace").read().splitlines()
            text = lines[lineno - 1].strip() if 1 <= lineno <= len(lines) else ""
        except OSError:
            text = ""
        tags = []
        if WORD_OLD.search(text):
            tags.append("old/erratum")
        if WORD_DATA.search(text):
            tags.append("data")
        if CLAIM_WORDS.search(text):
            tags.append("entry")
        out.append({"where": f"{name}:{lineno}", "tags": tags, "text": text[:160]})
    return out


def dossier(limit: int | None, json_out: str | None) -> int:
    try:
        _capstone()
    except ImportError:
        print("SKIP:本模式需要 capstone")
        return 0
    r = classify_all()
    sig, un = r["sig"], r["unreviewed"]
    cache: dict = {}
    deltas = edition_deltas(sig)
    order = sorted(un, key=lambda a: (-len(un[a]), a))
    if limit:
        order = order[:limit]
    rows = []
    for addr in order:
        d = propose(sig, addr, cache, deltas)
        d["doc"] = doc_corrections(un[addr], addr, sig)
        if len(d["doc"]) == 1:
            d["hypothesis"] = "DOC"
        elif d["doc"] and d["hypothesis"] != "EDITION":
            d["hypothesis"] = "DOC?"
        d["refs"] = len(un[addr])
        d["cites"] = wording(un[addr])
        rows.append(d)
    print(f"殘餘無訊號位址 {len(un)} 個,列出 {len(rows)} 個;已知舊→新位移 {len(deltas)} 種 "
          f"{[f'{k:+#x}' for k in sorted(deltas)]}\n")
    print(f"{'位址':>9} {'引用':>4} {'假說':9} {'所在函式':>16} {'資料基底':>18}  文件更正 / 舊版候選 / 鄰近入口")
    for d in rows:
        c = d["containing"]; dt = d["data"]
        print(f"{d['addr']:>9} {d['refs']:4d} {d['hypothesis']:9} "
              f"{(c['entry'] + '+' + hex(c['offset'])) if c else '?':>16} "
              f"{(dt['base'] + '+' + hex(dt['offset']) + ('(code)' if dt['base_is_code'] else '')) if dt else '-':>18}  "
              f"{', '.join(d['doc']) or '-'} / {', '.join(e['cand'] + e['delta'] for e in d['edition']) or '-'} / {', '.join(d['typo']) or '-'}")
    from collections import Counter as _C
    print("\n假說分佈:", dict(_C(d["hypothesis"] for d in rows)))
    if json_out:
        with open(json_out, "w", encoding="utf-8", newline="\n") as f:
            json.dump({"deltas": {f"{k:+#x}": v for k, v in deltas.items()}, "rows": rows},
                      f, ensure_ascii=False, indent=1)
        print(f"-> {json_out}")
    return 0


def kb_entry_claims(base: int, hi: int) -> dict[int, list[tuple[str, int]]]:
    """被入口語言同行提及、且落在 obj1 的相異位址 -> [(檔名, 行號), ...]。"""
    out: dict[int, list[tuple[str, int]]] = {}
    for path in sorted(glob.glob(os.path.join(KB, "*.md"))):
        name = os.path.basename(path)
        with open(path, encoding="utf-8", errors="replace") as f:
            for lineno, text in enumerate(f, 1):
                if not CLAIM_WORDS.search(text):
                    continue
                if NEGATED.search(text):
                    continue
                ends = {int(m, 16) for m in RANGE_END.findall(text)}
                for m in ADDR.findall(text):
                    n = int(m, 16)
                    if n in ends:
                        continue
                    # obj1 基底本身(`stored + 0x10000` 這種寫法)不是入口主張
                    if base < n < hi:
                        out.setdefault(n, []).append((name, lineno))
    return out


def known_bad() -> set[int]:
    """`known_address_errata.json` 已旗標的位址(citation_check.flag)。"""
    try:
        with open(ERRATA, encoding="utf-8") as f:
            er = json.load(f)
    except (OSError, ValueError):
        return set()
    out = set()
    for e in er.get("errata", []):
        for a in (e.get("citation_check") or {}).get("flag", []):
            try:
                out.add(int(a, 16))
            except ValueError:
                pass
    return out


def is_inner(sig: dict, addr: int, cache: dict) -> bool:
    """落在某個有訊號函式**內部**(偏移 > 0)的合法指令邊界 = 內部引用,不是入口主張。"""
    entry = containing_entry(sig, addr, cache)
    if entry is None or entry == addr:
        return False
    return boundary_from_entry(sig, addr, cache) is True


def classify_all() -> dict:
    sig = signals()
    claims = kb_entry_claims(sig["base"], sig["hi"])
    bad = known_bad()
    covered, erratum, inner, unreviewed = {}, {}, {}, {}
    try:
        _capstone()
        inner_ok = True
    except ImportError:
        inner_ok = False
    cache: dict = {}
    for addr, sites in claims.items():
        if addr in sig["plausible"]:
            covered[addr] = sites
        elif addr in bad:
            erratum[addr] = sites
        elif inner_ok and is_inner(sig, addr, cache):
            inner[addr] = sites
        else:
            unreviewed[addr] = sites
    return {"sig": sig, "claims": claims, "covered": covered, "erratum": erratum,
            "inner": inner, "inner_available": inner_ok, "unreviewed": unreviewed}


def unreviewed_by_file(unreviewed: dict) -> dict[str, int]:
    """{檔名: 該檔中「無訊號且未登記」的相異位址數} —— 基準線就是這個形狀。"""
    per: dict[str, set[int]] = {}
    for addr, sites in unreviewed.items():
        for name, _ in sites:
            per.setdefault(name, set()).add(addr)
    return {k: len(v) for k, v in sorted(per.items())}


def load_baseline() -> dict[str, int]:
    try:
        with open(BASELINE, encoding="utf-8") as f:
            return json.load(f).get("unreviewed_by_file", {})
    except (OSError, ValueError):
        return {}


def compare(current: dict[str, int], base: dict[str, int]) -> tuple[list[str], list[str]]:
    worse, better = [], []
    for f in sorted(set(current) | set(base)):
        c, o = current.get(f, 0), base.get(f, 0)
        if c > o:
            worse.append(f"{f}: {o} -> {c}(+{c - o})")
        elif c < o:
            better.append(f"{f}: {o} -> {c}(-{o - c})")
    return worse, better


def write_baseline() -> int:
    r = classify_all()
    cur = unreviewed_by_file(r["unreviewed"])
    payload = {
        "_meta": {
            "purpose": "知識庫宣稱為函式入口、但三個位元組訊號都拿不出來、且尚未登記為"
                       "勘誤的位址存量。由 tools/verify_address_claim_coverage.py 產生,"
                       "雙向棘輪:超標與已還未更新都會失敗。",
            "criterion": "訊號 = Watcom 序頭(push imm32; call 0x3702f)｜直接 E8 CALL 目標｜fixup 目標｜直接 E9 JMP 目標;"
                         "落在有訊號函式內部合法指令邊界的位址歸 INNER(內部引用),不計入",
            "note": "『無訊號』不等於『錯』——見工具 docstring 列出的三類合理來源。",
        },
        "unreviewed_by_file": cur,
    }
    with open(BASELINE, "w", encoding="utf-8", newline="\n") as f:
        f.write(json.dumps(payload, ensure_ascii=False, indent=2) + "\n")
    print(f"已寫入基準線:{sum(cur.values())} 筆(相異位址×檔案),分佈 {len(cur)} 份文件。")
    return 0


def report() -> int:
    r = classify_all()
    un = r["unreviewed"]
    print(f"UNREVIEWED 相異位址 {len(un)} 個,依引用次數排序:\n")
    for addr in sorted(un, key=lambda a: -len(un[a]))[:40]:
        sites = un[addr]
        where = ", ".join(f"{n}:{l}" for n, l in sites[:2])
        print(f"  {addr:#08x}  引用 {len(sites):3d} 次  {where}")
    print(f"\n(另有 {len(r['erratum'])} 個已登記為勘誤、{len(r['inner'])} 個是函式內部引用,不列入待處理。)")
    return 0


def one(addr_s: str) -> int:
    try:
        addr = int(addr_s, 16)
    except ValueError:
        print(f"無法解析位址:{addr_s!r}")
        return 1
    sig = signals()
    if not sig["base"] <= addr < sig["hi"]:
        print(f"{addr:#x} 不在 obj1({sig['base']:#x}..{sig['hi']:#x})")
        return 1
    s = signals_for(sig, addr)
    off = addr - sig["base"]
    print(f"{addr:#08x}  起始位元組 {sig['code'][off:off + 12].hex(' ')}")
    print(f"  入口訊號:{'、'.join(s) if s else '**無**'}")
    print(f"  已登記為勘誤:{addr in known_bad()}")
    try:
        _capstone()
    except ImportError:
        print("  函式內部引用:(需要 capstone)")
    else:
        cache: dict = {}
        ent = containing_entry(sig, addr, cache)
        print(f"  函式內部引用:{is_inner(sig, addr, cache)}"
              + (f"(所在函式 {ent:#x} +{addr - ent:#x})" if ent is not None and ent != addr else ""))
    return 0


def gate() -> int:
    r = classify_all()
    claims, covered, erratum, un = r["claims"], r["covered"], r["erratum"], r["unreviewed"]
    cur = unreviewed_by_file(un)
    worse, better = compare(cur, load_baseline())

    total = len(claims)
    print(f"知識庫宣稱為入口的相異 obj1 位址:{total}")
    print(f"  有位元組訊號   {len(covered):4d}({100 * len(covered) // max(1, total)}%)")
    print(f"  已登記為勘誤   {len(erratum):4d}")
    print(f"  函式內部引用   {len(r['inner']):4d}  (落在有訊號函式內部的合法指令邊界,不是入口主張)")
    print(f"  無訊號未登記   {len(un):4d}  <- 這個數字才是 findings 軸看不見的部分")
    if not r["inner_available"]:
        print("\nSKIP:本環境沒有 capstone,分不出函式內部引用,不比基準線(閘門在 Windows 跑)。")
        return 0
    print(f"\n對照:verify_findings 報的是「已登記結論」的滿分,分母 17;"
          f"本工具的分母是 {total}。")

    if worse:
        print(f"\nFAIL 新增 {len(worse)} 筆未登錄的無訊號入口主張:")
        for w in worse[:20]:
            print("  +", w)
        return 1
    if better:
        print(f"\nFAIL {len(better)} 筆已經處理掉但基準線沒更新"
              f"(請在同一個 commit 跑 --write-baseline):")
        for b in better[:20]:
            print("  -", b)
        return 1
    print("\n沒有新增未登錄的無訊號入口主張,基準線也沒有過期項目。")
    return 0


def selftest() -> int:
    fails: list[str] = []
    if not os.path.isfile(EXE):
        print("SKIP:找不到 org_game 的 FD2.EXE")
        return 0
    sig = signals()

    print("(1) 三個訊號都必須非空,且序頭數必須等於已登記結論 541")
    ok1 = (len(sig["prologue"]) == 541 and len(sig["calls"]) > 100
           and len(sig["fixups"]) > 100)
    print(f"    {'PASS' if ok1 else 'FAIL'}: 序頭 {len(sig['prologue'])}(應 541)、"
          f"CALL 目標 {len(sig['calls'])}、fixup 目標 {len(sig['fixups'])}")
    if not ok1:
        fails.append(f"訊號數不對:{len(sig['prologue'])}/{len(sig['calls'])}/{len(sig['fixups'])}")

    print("\n(2) 三個訊號必須真的互相獨立:單用序頭會漏掉有呼叫端的小型葉函式")
    only_call = set(sig["calls"]) - sig["prologue"] - sig["fixups"]
    ok2 = len(only_call) > 0 and 0x4EBE3 in sig["calls"] and 0x4EBE3 not in sig["prologue"]
    print(f"    {'PASS' if ok2 else 'FAIL'}: 只有『直接 CALL』訊號的位址 {len(only_call)} 個;"
          f"0x4ebe3 有 {sig['calls'].get(0x4EBE3, 0)} 個呼叫端但不在序頭集合")
    if not ok2:
        fails.append("三個訊號沒有互相補足 —— 單一訊號就夠的話這個聯集是多餘的")

    print("\n(3) 正向控制:已登記為錯的位址必須全部無訊號")
    bad_o1 = {a for a in known_bad() if sig["base"] <= a < sig["hi"]}
    leaked = sorted(a for a in bad_o1 if a in sig["plausible"])
    ok3 = bool(bad_o1) and not leaked
    print(f"    {'PASS' if ok3 else 'FAIL'}: errata 落在 obj1 的 {len(bad_o1)} 個,"
          + ("全部無訊號" if ok3 else f"有訊號的 {[hex(a) for a in leaked]}"))
    if not bad_o1:
        fails.append("errata 裡沒有 obj1 位址 —— 這題是空的,不算通過")
    elif leaked:
        fails.append(f"已證實錯的位址被判為有證據:{[hex(a) for a in leaked]}")

    print("\n(4) 負向控制(實測配對):0x4ebe3 必須有訊號、0x4e893 必須無訊號")
    # 這一對不是構造的:`0x1c7ed` 的 `E8` disp32 算出來的目標是 0x4ebe3(40 個呼叫端、
    # 起頭 `33 c0`),而 verified_addresses.json 當時記的是 0x4e893(0 個呼叫端、
    # 起頭 `08 ba ...` 是指令中段)。少了這一題,判準就沒有「不該被抓」的那一側。
    good, bad = 0x4EBE3 in sig["plausible"], 0x4E893 in sig["plausible"]
    ok4 = good and not bad
    print(f"    {'PASS' if ok4 else 'FAIL'}: 0x4ebe3 有訊號={good}、0x4e893 有訊號={bad}")
    if not ok4:
        fails.append(f"配對控制失敗:0x4ebe3={good}, 0x4e893={bad}")

    print("\n(5) 非恆真:不可以把所有被宣稱的位址都判成無訊號")
    r = classify_all()
    total = len(r["claims"])
    ok5 = total > 100 and len(r["covered"]) > 100 and len(r["unreviewed"]) < total
    print(f"    {'PASS' if ok5 else 'FAIL'}: 宣稱 {total} 個;有訊號 {len(r['covered'])}、"
          f"勘誤 {len(r['erratum'])}、內部引用 {len(r['inner'])}、無訊號未登記 {len(r['unreviewed'])}")
    if not ok5:
        fails.append("分類退化(全部落在同一桶)")

    print("\n(6) 宣稱語言必須真的在篩選:拿掉它,分母必須明顯變大")
    base, hi = sig["base"], sig["hi"]
    allad = set()
    for path in sorted(glob.glob(os.path.join(KB, "*.md"))):
        with open(path, encoding="utf-8", errors="replace") as f:
            for m in ADDR.findall(f.read()):
                n = int(m, 16)
                if base <= n < hi:
                    allad.add(n)
    ok6 = len(allad) > total
    print(f"    {'PASS' if ok6 else 'FAIL'}: 不看語言 {len(allad)} 個 vs 看語言 {total} 個")
    if not ok6:
        fails.append("宣稱語言沒有在篩選 —— 分母等於『有人提過的位址』")

    print("\n(6b) 範圍終點與否定句不算主張;範圍起點與肯定句照算(成對)")
    import tempfile as _tf6
    with _tf6.TemporaryDirectory() as td6:
        kb6 = globals()["KB"]
        globals()["KB"] = td6
        try:
            open(os.path.join(td6, "a.md"), "w", encoding="utf-8").write(
                "函式 `0x10100..0x10200` 的本體\n"            # 0x10200 是終點
                "handler `0x10300`–`0x10400` 範圍\n"           # 0x10400 是終點
                "`0x10500` 只是中段,不能當施法入口\n"          # 否定
                "`0x10600` 不是任何函式的真正入口\n"           # 否定
                "handler 入口 `0x10700`\n")                   # 肯定
            got6 = set(kb_entry_claims(0x10000, 0x20000))
        finally:
            globals()["KB"] = kb6
    ok6b = got6 == {0x10100, 0x10300, 0x10700}
    print(f"    {'PASS' if ok6b else 'FAIL'}: 收進 {sorted(hex(x) for x in got6)}(應 0x10100/0x10300/0x10700)")
    if not ok6b:
        fails.append(f"範圍終點/否定句排除不對:{sorted(hex(x) for x in got6)}")

    print("\n(7) 雙向棘輪")
    w1, b1 = compare({"a.md": 6}, {"a.md": 5})
    w2, b2 = compare({"a.md": 4}, {"a.md": 5})
    w3, b3 = compare({"a.md": 5}, {"a.md": 5})
    ok7 = bool(w1) and not b1 and bool(b2) and not w2 and not (w3 or b3)
    print(f"    {'PASS' if ok7 else 'FAIL'}: 6>5 新債={bool(w1)};4<5 過期={bool(b2)};5=5 乾淨={not (w3 or b3)}")
    if not ok7:
        fails.append("棘輪不是雙向的")

    try:
        _capstone()
    except ImportError:
        print("\n(8)(9) SKIP:沒有 capstone,指令邊界判準的兩題跳過(閘門不需要它)")
    else:
        cache: dict = {}
        print("\n(8) 邊界判準的**誤報率**:150 個已知正確入口不得有任何一個被判成「不是邊界」")
        import random as _rnd
        _rnd.seed(7)
        samp = _rnd.sample(sorted(sig["prologue"]), 150)
        wrong = [a for a in samp if boundary_from_entry(sig, a, cache) is False]
        ok8 = not wrong
        print(f"    {'PASS' if ok8 else 'FAIL'}: 誤報 {len(wrong)}/150 "
              f"{[hex(a) for a in wrong[:5]]}")
        if not ok8:
            fails.append(f"邊界判準對已知正確入口有 {len(wrong)} 個誤報")

        print("\n(9) 邊界判準的**召回率**必須落在已量測的區間(釘住它,也釘住它的上限)")
        # 10/14 是 2026-09-11 的實測值。抓不到的 4 個是「錯位址但剛好落在合法邊界上」,
        # 這是判準的結構性上限,不是 bug —— 所以這裡不要求 14/14,但要求它不得**退步**。
        bad_o1 = sorted(a for a in known_bad() if sig["base"] <= a < sig["hi"])
        caught = [a for a in bad_o1 if boundary_from_entry(sig, a, cache) is False]
        ok9 = len(bad_o1) >= 14 and len(caught) >= 10
        print(f"    {'PASS' if ok9 else 'FAIL'}: {len(caught)}/{len(bad_o1)} 被判為不是邊界"
              f"(2026-09-11 實測 10/14;抓不到的是落在合法邊界上的錯位址)")
        if not ok9:
            fails.append(f"邊界判準召回退步:{len(caught)}/{len(bad_o1)}")

    print("\n(10) 行號必須是真的行號 —— 掃描回報的 (檔, 行) 要能對回原文")
    # 突變測試發現的缺口:`enumerate(f, 1)` 改成 `enumerate(f, 2)`,每一個回報的行號
    # 全部偏一,而基準線只存**每檔筆數**、完全不受影響,所以整個 selftest 都沒感覺。
    # 這裡用獨立的讀法(直接讀檔案、自己數行)反查一筆,把行號釘住。
    claims = kb_entry_claims(sig["base"], sig["hi"])
    mismatch = None
    probe = next(((a, s) for a, s in claims.items() for s in [s] if s), None)
    if probe:
        addr, sites = probe
        name, lineno = sites[0]
        lines = open(os.path.join(KB, name), encoding="utf-8", errors="replace").read().splitlines()
        if not (1 <= lineno <= len(lines)) or not ADDR.findall(lines[lineno - 1]):
            mismatch = f"{name}:{lineno} 對不回原文"
        else:
            got = {int(m, 16) for m in ADDR.findall(lines[lineno - 1])}
            if addr not in got:
                mismatch = f"{name}:{lineno} 該行沒有 {addr:#x}(實際有 {[hex(g) for g in got][:4]})"
    ok10 = probe is not None and mismatch is None
    print(f"    {'PASS' if ok10 else 'FAIL'}: "
          + (f"{probe[1][0][0]}:{probe[1][0][1]} 該行確實含 {probe[0]:#x}" if ok10
             else str(mismatch or "沒有任何主張可抽驗")))
    if not ok10:
        fails.append(f"回報的行號對不回原文:{mismatch}")

    print("\n(11) 所在函式的選擇必須是**正確那一個**:已知入口的所在函式就是它自己")
    # 同一批突變發現:`bisect_right(ent, addr) - 1` 改成 `- 2` 會選到前一個函式,
    # 而 (8)(9) 兩題照樣通過 —— 因為從前一個函式反組譯通常也能掃到目標位址。
    try:
        _capstone()
    except ImportError:
        print("    SKIP:沒有 capstone")
    else:
        import random as _r
        _r.seed(13)
        s3 = _r.sample(sorted(sig["prologue"]), 100)
        pick_cache: dict = {}
        badpick = [a for a in s3 if containing_entry(sig, a, pick_cache) != a]
        ok11 = not badpick
        print(f"    {'PASS' if ok11 else 'FAIL'}: 100 個已知入口中,"
              f"所在函式被選成別人的 {len(badpick)} 個 {[hex(x) for x in badpick[:3]]}")
        if not ok11:
            fails.append(f"所在函式選錯:{len(badpick)}/100")

    print("\n(12) 掃描尾端邊界、呼叫計數、第一個入口、compare 的預設值")
    # 2026-09-11 窮舉突變測試:兩個掃描迴圈的上界 `len - 10` / `len - 5`、呼叫計數的
    # `+= 1`、containing_entry 的 `i >= 0`、compare 的兩個 `get(f, 0)` 改掉全部逃掉 ——
    # 真實映像裡沒有剛好卡在尾端的序頭/CALL,也沒有剛好等於第一個入口的查詢。
    base12 = 0x10000
    code_p = bytearray(32)
    i_p = len(code_p) - 11                      # 迴圈能走到的最後一個位移
    code_p[i_p], code_p[i_p + 5] = 0x68, 0xE8
    struct.pack_into("<i", code_p, i_p + 6, STACK_PROBE - (base12 + i_p) - 10)
    code_c = bytearray(16)
    for at in (0, len(code_c) - 6):             # 兩次 CALL 到同一目標,後者在最後可掃位移
        code_c[at] = 0xE8
        struct.pack_into("<i", code_c, at + 1, (base12 + 2) - (base12 + at + 5))
    code_j = bytearray(16)                     # E9 在最後可掃位移(與 E8 同一個尾端邊界)
    code_j[len(code_j) - 6] = 0xE9
    struct.pack_into("<i", code_j, len(code_j) - 5, (base12 + 3) - (base12 + len(code_j) - 6 + 5))
    sig12 = {"plausible": {100, 200}}
    b12 = {"尾端的序頭": prologue_entries(bytes(code_p), base12) == {base12 + i_p},
           "尾端的 CALL 與計數": call_targets(bytes(code_c), base12, base12 + 16) == Counter({base12 + 2: 2}),
           "尾端的 JMP": jmp_targets(bytes(code_j), base12, base12 + 16) == {base12 + 3},
           "恰好是第一個入口": containing_entry(sig12, 100, {}) == 100,
           "第一個入口之前沒有所在函式": containing_entry(sig12, 99, {}) is None,
           "compare 缺鍵視為 0": compare({"new.md": 1}, {"old.md": 1})
           == (["new.md: 0 -> 1(+1)"], ["old.md: 1 -> 0(-1)"])}
    ok12 = all(b12.values())
    print(f"    {'PASS' if ok12 else 'FAIL'}: " + "、".join(f"{k}={v}" for k, v in b12.items()))
    if not ok12:
        fails.append(f"掃描邊界/計數/入口/compare 不對:{[k for k, v in b12.items() if not v]}")

    print("\n(13) 第四訊號與 INNER 分類:thunk 本體有 JMP 訊號;函式內部位址是 INNER;非邊界位址不是;入口不是 INNER")
    # 2026-09-17:0x3e01d 是 delay 的本體(0x3790a jmp 0x3e01d),前三個訊號都看不到;
    # 0x2332a 是 ch06_post handler(0x232e8,fixup 目標)內的 `jne`,在合法邊界上 → INNER;
    # 0x2c469 / 0x117e6 是 triage 列出的「不在指令邊界」位址,不得成為 INNER。
    b13 = {"0x3e01d 有 JMP 訊號": "JMP 目標(thunk)" in signals_for(sig, 0x3E01D),
           "obj1 基底 0x10000 不算入口主張": sig["base"] not in kb_entry_claims(sig["base"], sig["hi"]),
           "已知錯誤位址加了第四訊號後仍全部無訊號": not [a for a in known_bad()
                                                    if sig["base"] <= a < sig["hi"] and a in sig["plausible"]],
           "0x4e893(負向配對)沒有 JMP 訊號": 0x4E893 not in sig["jmps"]}
    try:
        _capstone()
    except ImportError:
        print("    (INNER 三題 SKIP:沒有 capstone)")
    else:
        c13: dict = {}
        b13["0x2332a(handler 內的 jne)是內部引用"] = is_inner(sig, 0x2332A, c13)
        b13["0x2c469 / 0x117e6(非邊界)不是內部引用"] = not is_inner(sig, 0x2C469, c13) and not is_inner(sig, 0x117E6, c13)
        b13["已知入口 0x2c441 不是內部引用"] = not is_inner(sig, 0x2C441, c13)
        r13 = classify_all()
        b13["INNER 與 UNREVIEWED 互斥且 INNER 非空"] = bool(r13["inner"]) and not (set(r13["inner"]) & set(r13["unreviewed"]))
    ok13 = all(b13.values())
    print(f"    {'PASS' if ok13 else 'FAIL'}: " + "、".join(f"{k}={v}" for k, v in b13.items()))
    if not ok13:
        fails.append(f"第四訊號/INNER:{[k for k, v in b13.items() if not v]}")

    print("\n(14) dossier 假說:對已知勘誤配對的命中率,以及對已知入口不得提出舊版/打字錯假說")
    # 正向:勘誤表裡兩邊都在 obj1 的配對,拿 wrong 去問,候選裡必須含 correct(位移假說是從同一張表
    # 學來的,所以這題只證明「機制接得通」,不證明泛化;泛化看實際審 188 個的命中率)。
    # 負向:100 個已知入口,EDITION(唯一位移命中)的誤提率必須低 —— 它是唯一會被拿去登錄勘誤的假說。
    # 實測 2/100(2026-09-17),容許 ≤3。TYPO 對已知入口誤提 14/100,所以它只是旁證,不在這裡釘。
    deltas14 = edition_deltas(sig)
    c14: dict = {}
    pairs = []
    try:
        with open(ERRATA, encoding="utf-8") as f:
            for e in json.load(f).get("errata", []):
                try:
                    w, c = int(e["wrong_address"], 16), int(e["correct_address"], 16)
                except (KeyError, ValueError, TypeError):
                    continue
                if sig["base"] <= w < sig["hi"] and sig["base"] <= c < sig["hi"] and c != w:
                    pairs.append((w, c))
    except (OSError, ValueError):
        pass
    hit = 0
    in_scope = [(w, c) for w, c in pairs if (c - w) in deltas14]      # 位移被採用的配對才要求命中
    for w, c in in_scope:
        d = propose(sig, w, c14, deltas14)
        cands = {int(x["cand"], 16) for x in d["edition"]} | {int(t.split("(")[0], 16) for t in d["typo"]}
        hit += c in cands
    import random as _r14
    _r14.seed(21)
    good14 = _r14.sample(sorted(sig["prologue"]), 100)
    noisy = [a for a in good14 if propose(sig, a, c14, deltas14)["hypothesis"] == "EDITION"]
    from_errata_only = [dl for dl in deltas14 if "errata" in deltas14[dl]]        # 不靠 EDITION_MOVED 的位移
    ok14 = (bool(pairs) and len(in_scope) >= 5 and hit == len(in_scope) and len(noisy) <= 3
            and len(deltas14) >= 2 and 0x5844 not in deltas14
            and 0x350 in deltas14 and int(deltas14[0x350].split(" 對:")[0]) >= 2   # 勘誤表配對解析 + 支持數門檻
            and -0xe00 not in deltas14                                            # 否決名單生效
            and 0x358 in deltas14)                                              # EDITION_MOVED 的位移不受門檻影響
    print(f"    {'PASS' if ok14 else 'FAIL'}: 勘誤配對 {len(pairs)} 對,位移被採用的 {len(in_scope)} 對中候選含正確位址 {hit} 對(應全部);"
          f"已知入口被提 EDITION 假說 {len(noisy)}/100(容許 ≤3);採用的位移 {[f'{k:+#x}' for k in sorted(deltas14)]}(不得含 +0x5844)")
    if not ok14:
        fails.append(f"dossier 假說:命中 {hit}/{len(pairs)}、誤提 {len(noisy)}、位移 {len(deltas14)}")

    print("\n(15) propose 的邊界(合成訊號集):TYPO 視窗 ±16、資料基底取最近的、DATA 視窗 0x2000、EDITION 計數")
    # 2026-09-17 --precommit 抓到 9 個逃逸,全在這幾個常數與比較上;(14) 只看總數,看不到邊界。
    B = 0x10000
    A = B + 0x1000
    def _sig(pro=(), fix=(), jmp=()):
        pro, fix, jmp = set(pro), set(fix), set(jmp)
        return {"base": B, "hi": B + 0x8000, "code": bytes(0x8000), "prologue": pro,
                "calls": Counter(), "fixups": fix, "jmps": jmp, "plausible": pro | fix | jmp}
    b15 = {}
    # TYPO:±16 含,±17 不含;位址本身(若是入口)不算鄰近
    t = propose(_sig(pro=[A - 16, A - 15, A + 16, A - 17, A + 17, A]), A, {}, {})   # 相鄰兩個:一次跳兩格會漏掉 -15
    b15["TYPO 視窗 ±16 含、±17 不含、自己不算、相鄰的不漏"] = t["typo"] == [f"{A - 16:#x}(-16)", f"{A - 15:#x}(-15)", f"{A + 16:#x}(+16)"]
    b15["位元組摘要恰好 16 bytes"] = len(t["bytes"].split()) == 16
    # 資料基底:兩個 fixup 都在下方時取最近的那個;位址下方沒有 fixup -> None
    t = propose(_sig(fix=[A - 0x100, A - 8]), A, {}, {})
    b15["資料基底取最近的下方 fixup"] = t["data"] == {"base": f"{A - 8:#x}", "offset": 8, "base_is_code": False}
    b15["下方沒有 fixup -> 無資料假說"] = propose(_sig(fix=[A + 4]), A, {}, {})["data"] is None
    # DATA 視窗:恰好 0x2000 算、0x2001 不算;基底是程式碼要標出來
    b15["DATA 視窗恰好 0x2000 算"] = propose(_sig(fix=[A - 0x2000]), A, {}, {})["data"]["offset"] == 0x2000
    b15["DATA 視窗 0x2001 不算"] = propose(_sig(fix=[A - 0x2001]), A, {}, {})["data"] is None
    b15["基底是程式碼要標 base_is_code"] = propose(_sig(pro=[A - 8], fix=[A - 8]), A, {}, {})["data"]["base_is_code"] is True
    # EDITION:恰好一個位移命中 -> EDITION;兩個都命中 -> EDITION?;沒有 -> 不是 EDITION
    one = propose(_sig(pro=[A + 0x356]), A, {}, {0x356: "x", 0x358: "y"})
    two = propose(_sig(pro=[A + 0x356, A + 0x358]), A, {}, {0x356: "x", 0x358: "y"})
    none = propose(_sig(pro=[A + 0x357]), A, {}, {0x356: "x", 0x358: "y"})
    b15["一個位移命中 -> EDITION"] = one["hypothesis"] == "EDITION" and one["edition"][0]["cand"] == f"{A + 0x356:#x}"
    b15["兩個位移命中 -> EDITION?"] = two["hypothesis"] == "EDITION?" and len(two["edition"]) == 2
    b15["沒有命中 -> 不是 EDITION"] = none["hypothesis"] not in ("EDITION", "EDITION?") and none["edition"] == []
    # 排序:DATA(基底非程式碼)高於 TYPO;唯一 EDITION 高於 DATA
    b15["DATA 高於 TYPO"] = propose(_sig(pro=[A + 3], fix=[A - 8]), A, {}, {})["hypothesis"] == "DATA"
    b15["EDITION 高於 DATA"] = propose(_sig(pro=[A + 0x356], fix=[A - 8]), A, {}, {0x356: "x"})["hypothesis"] == "EDITION"
    # DOC:引用行帶更正措辭且含另一個有訊號位址 -> 該位址;沒有更正措辭 -> 不採;無訊號的不採
    import tempfile as _tf15
    with _tf15.TemporaryDirectory() as td15:
        kb_bak = globals()["KB"]
        globals()["KB"] = td15
        try:
            open(os.path.join(td15, "x.md"), "w", encoding="utf-8").write(
                f"handler {A:#x} 位址更正:應為 {A + 0x356:#x}\n"
                f"handler {A:#x} 與 {A + 0x358:#x} 相鄰\n"
                f"handler {A:#x} 應為 {A + 0x999:#x}\n")
            sg = _sig(pro=[A + 0x356, A + 0x358])
            b15["DOC:更正行的有訊號位址"] = doc_corrections([("x.md", 1)], A, sg) == [f"{A + 0x356:#x}"]
            b15["DOC:沒有更正措辭不採"] = doc_corrections([("x.md", 2)], A, sg) == []
            b15["DOC:無訊號的位址不採"] = doc_corrections([("x.md", 3)], A, sg) == []
        finally:
            globals()["KB"] = kb_bak
    ok15 = all(b15.values())
    print(f"    {'PASS' if ok15 else 'FAIL'}: " + "、".join(f"{k}={v}" for k, v in b15.items()))
    if not ok15:
        fails.append(f"propose 邊界:{[k for k, v in b15.items() if not v]}")

    if fails:
        print("\nSELFTEST FAILED:")
        for f in fails:
            print("  -", f)
        return 1
    print("\n--selftest passed(14 項:訊號基數 + 訊號獨立性 + 正向控制 + 實測配對負向控制 + "
          "非恆真 + 宣稱語言有在篩選 + 雙向棘輪 + 邊界判準誤報率 + 邊界判準召回率 + "
          "行號可對回原文 + 所在函式選擇正確 + 第四訊號與 INNER 分類 + dossier 假說的雙向控制 + propose 邊界 + 範圍終點/否定句排除)。")
    return 0


def main() -> int:
    ap = argparse.ArgumentParser(description="知識庫入口主張的位元組證據涵蓋率")
    ap.add_argument("--report", action="store_true", help="列出 UNREVIEWED 位址")
    ap.add_argument("--triage", action="store_true",
                    help="把 UNREVIEWED 依『是否落在合法指令邊界』分流(需要 capstone)")
    ap.add_argument("--addr", help="查單一位址的四個訊號與分類")
    ap.add_argument("--dossier", nargs="?", const=0, type=int, metavar="N",
                    help="殘餘無訊號位址的判讀資料(資料表/舊版位移/打字錯/措辭);N = 只列引用最多的前 N 個")
    ap.add_argument("--json", help="--dossier 的 JSON 輸出路徑")
    ap.add_argument("--write-baseline", action="store_true")
    ap.add_argument("--selftest", action="store_true")
    a = ap.parse_args()
    if a.selftest:
        return selftest()
    if a.addr:
        return one(a.addr)
    if a.dossier is not None:
        return dossier(a.dossier or None, a.json)
    if a.triage:
        return triage()
    if a.write_baseline:
        return write_baseline()
    if a.report:
        return report()
    return gate()


if __name__ == "__main__":
    sys.exit(main())
