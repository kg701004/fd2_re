#!/usr/bin/env python3
"""找出 DOSBox-X 指令追蹤(LOGCPU.TXT)裡,CPU 最後一次離開某段程式碼的那一條指令。

用途(續七十五):失控的迴圈(例如 0x89 假頭像讓 blit_rle_image 的 32 位元 `loop` 跑 2^32 次)
最後會讓模擬器以 E_Exit 結束,或掉進實際模式的 INT 6 迴圈 —— 後者 Alt+Pause 停不住、D / MEMDUMPBIN
也不被接受,事後什麼都讀不到。解法是在失控開始前就用 `tools/dosbox_exec_trace.sh`
(`FD2_TRACE_MODE=LOGL`)把每一條指令連同暫存器、CR0、VM 寫進 LOGCPU.TXT,本工具再從那份檔案找出:

- 「家」(--home 指定的程式碼範圍)裡最後一條指令,和它之後的第一條 —— 真正的逃逸點。
  中途被硬體中斷帶出去又回來的那幾段只算「出差」,不是逃逸(只看第一個不在家的指令會被它們騙)。
- 家裡最後一條 `stos*` 的 EDI(LOGL / LOG 才有暫存器)與家裡 stos 的總數。
- 逃逸之後的模式變化:CS 選擇器、CR0.PE、VM 旗標(只有 LOGL 有 CR0 / VM)。
- 逃逸之後最常執行的 CS:EIP(看是不是卡在某個迴圈)、逃逸後的前幾行、檔案最後幾行。
- 檔案在家裡結束(E_Exit 前最後執行的就是家裡的指令)時,逃逸點是 None,`ends_in_home` 為真。

LOGCPU.TXT 可能有好幾 GB:單趟串流讀,記憶體只留固定大小的緩衝。

格式(dosbox-x src/debug/debug.cpp LogInstruction):
    LOGC  `CCCC:IIIIIIII`
    LOGS  `CCCC:IIII  disasm  EAX:... SS:xxxx C0 Z0 S0 O0 I0`
    LOG   `CCCC:IIIIIIII  disasm  res  EAX:... SS:xxxx CF:0 ... IF:0`
    LOGL  `ts CCCC:IIIIIIII  disasm  res  bytes EAX:... SS:xxxx CF:0 ... IF:0 TF:0 VM:0 FLG:xxxxxxxx CR0:xxxxxxxx`

用法:
    python tools/dosbox_cpulog_escape.py LOGCPU.TXT --home 0x4ec1f-0x4ec27,0x4ec66-0x4ec7c [--json out.json]
    python tools/dosbox_cpulog_escape.py --selftest

位址預設是 native(= live EIP - --delta,只對 --cs 那個選擇器);--delta 0 就直接用 live EIP。
"""
from __future__ import annotations

import argparse
import json
import re
import sys
from collections import Counter, deque
from pathlib import Path

DEFAULT_DELTA = 0x19C000
DEFAULT_CS = "0170"
MODE_CAP = 200   # 逃逸後最多記幾次模式變化
TOP_N = 15       # 逃逸後最常見的 CS:EIP 留幾個
ENTRY_N = 10     # 出差入口留幾個

# CS:EIP 之前可能有 LOGL 的時間戳;EIP 在 LOGS 是 4 位,其他 8 位
_HEAD = re.compile(r"^(?:(\d+\.\d+) )?([0-9A-F]{4}):([0-9A-F]{4,8})(?:\s+(.*))?$")
_REG = re.compile(r"\b([A-Z][A-Z0-9]{1,2}):([0-9A-F]+)\b")


def parse_line(line: str) -> dict | None:
    """把 LOGCPU.TXT 的一行拆成欄位;不是指令行就回 None。

    Args:
        line: 一行文字(可含結尾換行)。

    Returns:
        {"cs", "eip", "text", "mnem", "regs"};regs 只有 " EAX:" 之後的 KEY:HEX(反組譯文字裡的
        `es:[edi]` 之類不會被誤當成暫存器)。LOGC 行的 regs 是空 dict。
    """
    m = _HEAD.match(line.rstrip("\r\n"))
    if not m:
        return None
    rest = m.group(4) or ""
    k = rest.find("EAX:")
    if k >= 0 and (k == 0 or rest[k - 1] == " "):
        text, regtxt = rest[:k].rstrip(), rest[k:]
    else:
        text, regtxt = rest.rstrip(), ""
    regs = {a: int(b, 16) for a, b in _REG.findall(regtxt)}
    return {"cs": m.group(2), "eip": int(m.group(3), 16), "text": text,
            "mnem": text.split()[0].lower() if text else "", "regs": regs}


def parse_home(spec: str) -> list[tuple[int, int]]:
    """`0x4ec1f-0x4ec27,0x4ec66-0x4ec7c` → [(lo, hi)],hi 不含。"""
    out = []
    for part in spec.split(","):
        lo, _, hi = part.strip().partition("-")
        a, b = int(lo, 16), int(hi, 16)
        if b <= a:
            raise ValueError(f"範圍要 lo < hi(hi 不含):{part}")
        out.append((a, b))
    return out


def analyze(lines, home: list[tuple[int, int]], cs: str = DEFAULT_CS, delta: int = DEFAULT_DELTA,
            keep: int = 40) -> dict:
    """單趟掃描,回傳逃逸點與前後摘要。

    Args:
        lines: 可疊代的文字行(檔案物件即可)。
        home: native 位址範圍 [(lo, hi)]。
        cs: 「家」所在的程式碼選擇器(四位十六進位字串)。
        delta: native = live EIP - delta。
        keep: 逃逸後前幾行、檔案最後幾行各留多少。

    Returns:
        JSON 可序列化的摘要 dict。
    """
    def in_home(rec: dict) -> bool:
        if rec["cs"] != cs:
            return False
        nat = rec["eip"] - delta
        return any(lo <= nat < hi for lo, hi in home)

    n = parsed = n_home = stos = 0
    last_home: tuple[int, str] | None = None
    last_home_regs: dict = {}
    last_stos: tuple[int, dict] | None = None
    first_home: int | None = None
    # 目前這段「不在家」的指令:回到家就算一次出差,檔案結束時還沒回來就是逃逸
    away: list[tuple[int, str]] = []
    away_len = 0
    away_first: tuple[int, str] | None = None
    away_first_key = ""
    away_cs_eip: Counter = Counter()
    away_modes: list[dict] = []
    prev_mode: tuple | None = None
    excursions = 0
    exc_entry: Counter = Counter()
    exc_max = 0
    tail: deque = deque(maxlen=keep)
    unparsed = 0
    for raw in lines:
        n += 1
        line = raw.rstrip("\r\n")
        tail.append((n, line))
        rec = parse_line(line)
        if rec is None:
            unparsed += 1
            continue
        parsed += 1
        if in_home(rec):
            if first_home is None:
                first_home = n
            if away_len:
                excursions += 1
                exc_entry[away_first_key] += 1
                exc_max = max(exc_max, away_len)
            n_home += 1
            last_home = (n, line)
            last_home_regs = rec["regs"]
            if rec["mnem"].startswith("stos"):
                stos += 1
                last_stos = (n, rec["regs"])
            away, away_len, away_first = [], 0, None
            away_cs_eip = Counter()
            away_modes = []
            prev_mode = (rec["cs"], (rec["regs"]["CR0"] & 1) if "CR0" in rec["regs"] else None,
                         rec["regs"].get("VM"))
            continue
        if first_home is None:
            continue  # 還沒進過家:前置的指令不算出差也不算逃逸
        away_len += 1
        key = f"{rec['cs']}:{rec['eip']:08X}"
        if away_first is None:
            away_first, away_first_key = (n, line), key
        if len(away) < keep:
            away.append((n, line))
        away_cs_eip[key] += 1
        mode = (rec["cs"], (rec["regs"]["CR0"] & 1) if "CR0" in rec["regs"] else None, rec["regs"].get("VM"))
        if mode != prev_mode and len(away_modes) < MODE_CAP:
            away_modes.append({"line": n, "cs": mode[0], "pe": mode[1], "vm": mode[2], "at": key})
        prev_mode = mode

    escaped = first_home is not None and away_len > 0
    return {
        "lines": n, "parsed": parsed, "unparsed": unparsed,
        "home": [[hex(a), hex(b)] for a, b in home], "cs": cs, "delta": hex(delta),
        "home_lines": n_home, "first_home_line": first_home,
        "last_home": {"line": last_home[0], "text": last_home[1]} if last_home else None,
        "last_home_regs": {k: hex(v) for k, v in last_home_regs.items()},
        "home_stos": stos,
        "last_home_stos": {"line": last_stos[0], "edi": hex(last_stos[1]["EDI"]) if "EDI" in last_stos[1] else None}
        if last_stos else None,
        "excursions": excursions, "excursion_entries": exc_entry.most_common(ENTRY_N), "excursion_max_len": exc_max,
        "ends_in_home": first_home is not None and away_len == 0,
        "escape": {"line": away_first[0], "text": away_first[1]} if escaped else None,
        "after_escape_lines": away_len if escaped else 0,
        "after_escape_head": [{"line": a, "text": b} for a, b in away] if escaped else [],
        "after_escape_modes": away_modes if escaped else [],
        "after_escape_top": away_cs_eip.most_common(TOP_N) if escaped else [],
        "file_tail": [{"line": a, "text": b} for a, b in tail],
    }


def _fmt_logl(ts: str, cs: str, eip: int, dis: str, regs: dict, cr0: int = 0x80000011, vm: int = 0) -> str:
    """照 debug.cpp cpuLogType 2 的版面組一行(selftest 用)。"""
    r = {"EAX": 0, "EBX": 0, "ECX": 0, "EDX": 0, "ESI": 0, "EDI": 0, "EBP": 0, "ESP": 0, **regs}
    return (f"{ts} {cs}:{eip:08X}  {dis:<30}  {'':<22}  {'AA ':<21}"
            f" EAX:{r['EAX']:08X} EBX:{r['EBX']:08X} ECX:{r['ECX']:08X} EDX:{r['EDX']:08X}"
            f" ESI:{r['ESI']:08X} EDI:{r['EDI']:08X} EBP:{r['EBP']:08X} ESP:{r['ESP']:08X}"
            f" DS:0178 ES:0178 FS:0000 GS:0020 SS:0178 CF:0 ZF:0 SF:0 OF:0 AF:0 PF:0 IF:1"
            f" TF:0 VM:{vm} FLG:00000202 CR0:{cr0:08X}")


def selftest() -> int:
    """以照 debug.cpp 版面組出的假追蹤驗證判準。

    (1) 迴圈中被中斷帶出去又回來 → 只算出差;逃逸點是家裡最後一條之後那一條(不是第一次出差)。
    (2) 同一序列的 LOGC 版本得到同一個逃逸行號。
    (3) 全程在家 → 沒有逃逸、ends_in_home。
    (4) 進家之前的指令不算出差;壞行只計數不崩。
    (5) delta 真的參與:換 delta,家就是空的。
    (6) 反組譯文字裡的 `es:[edi]` 不能被當成暫存器;LOGL 的 EDI / CR0 / VM 要讀對。
    (7) 檔案在家裡最後一條之後還有指令,但那段又回家 → 不是逃逸(最後一次回家才算)。
    """
    for s in (sys.stdout, sys.stderr):
        try:
            s.reconfigure(encoding="utf-8")
        except (AttributeError, OSError):
            pass
    D = DEFAULT_DELTA
    H = [(0x4EC1F, 0x4EC27), (0x4EC66, 0x4EC7C)]
    call = lambda edi: _fmt_logl("1.0", "0170", 0x4EC1F + D, "call 001EAC66", {"EDI": edi})  # noqa: E731
    sub = lambda edi: _fmt_logl("1.0", "0170", 0x4EC66 + D, "or   ah,ah", {"EDI": edi})  # noqa: E731
    sto = lambda edi: _fmt_logl("1.0", "0170", 0x4EC24 + D, "stosb es:[edi],al", {"EDI": edi})  # noqa: E731
    lop = lambda edi: _fmt_logl("1.0", "0170", 0x4EC25 + D, "loop 001EAC1F", {"EDI": edi})  # noqa: E731
    isr = [_fmt_logl("1.1", "0170", 0x3D000 + D, "push eax", {}), _fmt_logl("1.1", "0170", 0x3D001 + D, "iretd", {})]
    esc = [_fmt_logl("2.0", "F000", 0xCA60, "iret", {}, cr0=0x10), _fmt_logl("2.0", "C3FF", 0x35F7, "arpl", {}, cr0=0x10),
           _fmt_logl("2.0", "F000", 0xCA60, "iret", {}, cr0=0x10), _fmt_logl("2.0", "C3FF", 0x35F7, "arpl", {}, cr0=0x10)]
    pre = [_fmt_logl("0.5", "0170", 0x4EBFF + D, "push ebp", {})]
    body = []
    for i in range(3):
        body += [call(0xA0728 + i), sub(0xA0728 + i), sto(0xA0728 + i), lop(0xA0729 + i)]
    seq = pre + body[:8] + isr + body[8:] + esc
    fails: list[str] = []

    def check(name: str, cond: bool, got) -> None:
        print(f"{'PASS' if cond else 'FAIL'} {name}: {got}")
        if not cond:
            fails.append(name)

    r1 = analyze(seq, H)
    esc_line = len(pre) + len(body) + len(isr) + 1
    check("(1) 逃逸點 = 家裡最後一條之後", r1["escape"] and r1["escape"]["line"] == esc_line,
          (r1["escape"] or {}).get("line"))
    check("(1) 出差 1 次、長度 2、入口 0170:001D9000", r1["excursions"] == 1 and r1["excursion_max_len"] == 2 and
          r1["excursion_entries"] == [("0170:001D9000", 1)], (r1["excursions"], r1["excursion_max_len"], r1["excursion_entries"]))
    check("(1) 逃逸後 PE 1→0、CS F000", r1["after_escape_modes"][:1] == [
        {"line": esc_line, "cs": "F000", "pe": 0, "vm": 0, "at": "F000:0000CA60"}], r1["after_escape_modes"][:1])
    check("(1) 逃逸後 4 行、最常見 2 個位址各 2 次", r1["after_escape_lines"] == 4 and
          sorted(c for _, c in r1["after_escape_top"]) == [2, 2], (r1["after_escape_lines"], r1["after_escape_top"]))
    check("(1) 家裡 stos 3 次,最後一次 EDI 0xa072a", r1["home_stos"] == 3 and r1["last_home_stos"]["edi"] == "0xa072a",
          (r1["home_stos"], r1["last_home_stos"]))

    logc = [f"{p['cs']}:{p['eip']:08X}" for p in map(parse_line, seq)]
    r2 = analyze(logc, H)
    check("(2) LOGC 同一個逃逸行", r2["escape"] and r2["escape"]["line"] == esc_line and r2["last_home_regs"] == {},
          (r2["escape"] or {}).get("line"))

    r3 = analyze(pre + body, H)
    check("(3) 全程在家 → 無逃逸、ends_in_home", r3["escape"] is None and r3["ends_in_home"],
          (r3["escape"], r3["ends_in_home"]))

    r4 = analyze(["garbage", ""] + pre + ["0170:ZZZZ"] + body + esc, H)
    check("(4) 前置不算出差、壞行 3", r4["excursions"] == 0 and r4["unparsed"] == 3 and r4["first_home_line"] == 5,
          (r4["excursions"], r4["unparsed"], r4["first_home_line"]))

    r5 = analyze(seq, H, delta=D + 0x1000)
    check("(5) 換 delta 家就空了", r5["home_lines"] == 0 and r5["escape"] is None, r5["home_lines"])

    p6 = parse_line(sto(0x17602B))
    check("(6) es:[edi] 不是暫存器、EDI / CR0 / VM 讀對", "ES" in p6["regs"] and p6["regs"]["ES"] == 0x178 and
          p6["regs"]["EDI"] == 0x17602B and p6["regs"]["CR0"] == 0x80000011 and p6["regs"]["VM"] == 0 and
          p6["mnem"] == "stosb", {k: p6["regs"].get(k) for k in ("ES", "EDI", "CR0", "VM")})

    r7 = analyze(pre + body + isr + body[:4], H)
    check("(7) 出去又回家 → 不是逃逸", r7["escape"] is None and r7["excursions"] == 1 and r7["ends_in_home"],
          (r7["escape"], r7["excursions"]))

    # (8) 解析邊界:EAX: 在開頭(k == 0)要解析;嵌在字詞裡(前一字元不是空白)不算暫存器起點
    p8a = parse_line("0170:1234 EAX:00000005 EBX:00000006")
    p8b = parse_line("0170:00001234  mov  REAX:00000005,1")
    check("(8) EAX: 在開頭 / 嵌在字詞裡", p8a["regs"].get("EAX") == 5 and p8a["regs"].get("EBX") == 6 and
          p8b["regs"] == {} and p8b["mnem"] == "mov", (p8a["regs"], p8b["regs"]))
    p8c = parse_line(_fmt_logl("1.0", "0170", 0x10, "nop", {}))
    check("(8) 假追蹤的預設暫存器都是 0", all(p8c["regs"][k] == 0 for k in
          ("EAX", "EBX", "ECX", "EDX", "ESI", "EDI", "EBP", "ESP")), {k: p8c["regs"][k] for k in ("EAX", "ESP")})

    # (9) 計數欄位、最後一條在家的行、沒出差時最長出差為 0、沒逃逸時逃逸後 0 行
    check("(9) parsed / home_lines / last_home", r1["parsed"] == len(seq) and r1["home_lines"] == len(body) and
          r1["last_home"]["line"] == esc_line - 1 and r1["last_home"]["text"] == seq[esc_line - 2] and
          r1["last_home_stos"]["line"] == esc_line - 2,
          (r1["parsed"], r1["home_lines"], r1["last_home"]["line"], r1["last_home_stos"]["line"]))
    check("(9) 沒出差 → 最長 0;沒逃逸 → 逃逸後 0 行、無熱點", r4["excursion_max_len"] == 0 and
          r3["after_escape_lines"] == 0 and r3["after_escape_top"] == [] and r3["after_escape_head"] == [],
          (r4["excursion_max_len"], r3["after_escape_lines"]))

    # (10) 逃逸後只有 1 行也是逃逸;逃到同 CS、同 PE / VM 的別處 → 沒有模式變化
    same = _fmt_logl("3.0", "0170", 0x10000 + D, "hlt", {"EDI": 1})
    r10 = analyze(pre + body + [same], H)
    check("(10) 逃逸後 1 行、模式不變就不記", r10["escape"] and r10["escape"]["line"] == len(pre) + len(body) + 1 and
          r10["after_escape_lines"] == 1 and r10["after_escape_modes"] == [],
          ((r10["escape"] or {}).get("line"), r10["after_escape_modes"]))

    # (11) keep 限制逃逸後前幾行與檔案最後幾行
    r11 = analyze(seq, H, keep=2)
    check("(11) keep=2", len(r11["after_escape_head"]) == 2 and r11["after_escape_head"][0]["line"] == esc_line and
          [t["line"] for t in r11["file_tail"]] == [len(seq) - 1, len(seq)],
          (len(r11["after_escape_head"]), [t["line"] for t in r11["file_tail"]]))

    # (12) VM = 1 時 pe / vm 欄位不能對調
    vm1 = _fmt_logl("4.0", "0170", 0x20000 + D, "nop", {}, cr0=0x11, vm=1)
    r12 = analyze(pre + body + [vm1], H)
    check("(12) VM=1 → pe 1、vm 1", r12["after_escape_modes"] == [
        {"line": len(pre) + len(body) + 1, "cs": "0170", "pe": 1, "vm": 1, "at": f"0170:{0x20000 + D:08X}"}],
        r12["after_escape_modes"])
    pm0 = _fmt_logl("4.1", "0080", 0x20, "nop", {}, cr0=0x11, vm=0)
    r12b = analyze(pre + body + [pm0], H)
    check("(12) 換 CS、PE 1 / VM 0 → pe 1、vm 0", [(m["pe"], m["vm"]) for m in r12b["after_escape_modes"]] == [(1, 0)],
          r12b["after_escape_modes"])

    # (13) 上限:模式變化最多 MODE_CAP 次、熱點最多 TOP_N 個、出差入口最多 ENTRY_N 個
    flip = [_fmt_logl("5.0", "F000" if i % 2 else "C000", 0x100 + i, "nop", {}, cr0=0x10) for i in range(MODE_CAP + 5)]
    r13 = analyze(pre + body + flip, H)
    many_isr = []
    for i in range(ENTRY_N + 3):
        many_isr += [_fmt_logl("1.2", "0170", 0x30000 + i + D, "iretd", {}), body[0]]
    r13b = analyze(pre + body + many_isr, H)
    check("(13) 上限 MODE_CAP / TOP_N / ENTRY_N", len(r13["after_escape_modes"]) == MODE_CAP and
          len(r13["after_escape_top"]) == TOP_N and r13["after_escape_lines"] == MODE_CAP + 5 and
          len(r13b["excursion_entries"]) == ENTRY_N and r13b["excursions"] == ENTRY_N + 3,
          (len(r13["after_escape_modes"]), len(r13["after_escape_top"]), len(r13b["excursion_entries"])))
    check("(13) 常數", (MODE_CAP, TOP_N, ENTRY_N) == (200, 15, 10), (MODE_CAP, TOP_N, ENTRY_N))

    if fails:
        print("SELFTEST FAILED:", fails)
        return 1
    print("--selftest passed(逃逸 vs 出差、LOGC / LOGL、全程在家、前置與壞行、delta、暫存器解析、回家不算逃逸)")
    return 0


def main() -> int:
    """命令列入口。"""
    ap = argparse.ArgumentParser(description=__doc__, formatter_class=argparse.RawDescriptionHelpFormatter)
    ap.add_argument("log", type=Path, nargs="?", help="LOGCPU.TXT(dosbox_exec_trace.sh arm 的輸出)")
    ap.add_argument("--home", help="native 位址範圍,逗號分隔,hi 不含:0x4ec1f-0x4ec27,0x4ec66-0x4ec7c")
    ap.add_argument("--cs", default=DEFAULT_CS, help=f"家所在的 CS 選擇器(預設 {DEFAULT_CS})")
    ap.add_argument("--delta", type=lambda s: int(s, 0), default=DEFAULT_DELTA,
                    help=f"native = live EIP - delta(預設 {DEFAULT_DELTA:#x};0 = 直接用 live)")
    ap.add_argument("--keep", type=int, default=40, help="逃逸後前幾行 / 檔案最後幾行各留多少(預設 40)")
    ap.add_argument("--json", type=Path, help="把摘要寫成 JSON")
    ap.add_argument("--selftest", action="store_true")
    a = ap.parse_args()
    if a.selftest:
        return selftest()
    if not a.log or not a.home:
        ap.error("需要 LOGCPU.TXT 與 --home")
    with a.log.open("r", encoding="latin-1") as f:
        res = analyze(f, parse_home(a.home), a.cs.upper(), a.delta, a.keep)
    res["source"] = str(a.log)
    if a.json:
        a.json.write_text(json.dumps(res, indent=1, ensure_ascii=False) + "\n", encoding="utf-8")
    brief = {k: res[k] for k in ("lines", "parsed", "unparsed", "home_lines", "home_stos", "excursions",
                                 "ends_in_home", "after_escape_lines")}
    print(json.dumps(brief, ensure_ascii=False))
    print("last_home:", res["last_home"])
    print("last_home_stos:", res["last_home_stos"])
    print("escape:", res["escape"])
    for m in res["after_escape_modes"][:20]:
        print("  mode", m)
    for k, c in res["after_escape_top"][:10]:
        print("  top", k, c)
    return 0


if __name__ == "__main__":
    sys.exit(main())
