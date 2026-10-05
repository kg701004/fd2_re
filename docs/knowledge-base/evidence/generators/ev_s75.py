"""續七十五證據:evidence/runaway_blit_triple_fault_continue_load_control_20261005.json(續七十四的兩個未驗證項目)。

A. 0x89 的失控 blit 怎麼讓 DOSBox-X 出事(v21,LOGL 逐指令追蹤 + 事前 / 事後記憶體):
   寫到 DOS/4GW 的 GDT(base 0x170010)→ 下一次計時器 IRQ 載入 CS 0070 失敗 → 三重錯誤 → CPU 重置、CMOS 關機碼 9 的
   INT 15h block move 返回 → DOS/4GW 實際模式碼 → call far XMS 入口 C3FF:0010(已被 blit 蓋掉)→ 執行像素資料 → arpl → INT 6 迴圈。
B. 寫入內容取決於 blit 讀過頭的來源(堆積),所以每次執行的垃圾碼不同:v16 終點 C3FF:35F7 的 63 b9 4f 4f 不是 v21 在那裡寫的值。
C. 工具:dosbox_exec_trace.sh(FD2_TRACE_MODE / heavylog / 計數上限)、dosbox_cpulog_escape.py、fd2_dosbox_live_helper.sh mem-dump 依 CPU 模式判斷選擇器。
D. CONTINUE / LOAD 的完好標頭對照(v22)vs 續七十四 v19 的改壞標頭。
全部從 .wsl_build/ctr/v21、v22(與 v16、v19 對照)的原始紀錄重算;任何預測不符就 assert 失敗。
"""
from __future__ import annotations

import hashlib
import json
import struct
import sys
from pathlib import Path

from _evpaths import GAME, GEN_DIR, ROOT, out_path, rel, require_inputs  # noqa: E402
require_inputs(__file__)
sys.path.insert(0, str(ROOT / "tools"))
import dosbox_cpulog_escape as E  # noqa: E402

EXE = GAME / "FD2.EXE"
C = ROOT / ".wsl_build/ctr"
V16, V19, V21, V22 = (C / f"{v}/ch25" for v in ("v16", "v19", "v21", "v22"))
OUT = out_path("runaway_blit_triple_fault_continue_load_control_20261005.json")
DELTA = 0x19C000


def md5(p: Path) -> str:
    return hashlib.md5(p.read_bytes()).hexdigest()


def J(p: Path) -> dict:
    return json.loads(p.read_text(encoding="utf-8"))


assert md5(EXE) == "33464c81e6a364fd0660141139aa8e6e"

# ---------------- A. v21 ----------------
r1 = J(V21 / "r1.json")
arm = next(s for s in r1["stops"] if "arm_out" in s)
assert arm["eip"] == "0x4ec16" and arm["width_bp"] == 0 and arm["height_dx"] == 43570 and arm["edi"] == 0xA0728
assert arm["heavylog_pane"] == ["DEBUG: Heavy cpu logging on."]
assert arm["arm_out"].startswith("armed: LOGL 1000000 (16777216 instructions)")
st = r1["state"]
assert st["trace_end"] == "count_done", st["trace_end"]
assert st["after_regs"]["EIP"] == "0xca60"

esc = J(V21 / "escape.json")
assert esc["lines"] == esc["parsed"] == 16777216 and esc["unparsed"] == 0
# 第 1..4 行是 0x4ec16..0x4ec1c(迴圈之前),第 5 行 0x4ec1f 才進家
assert esc["home"] == [["0x4ec1f", "0x4ec27"], ["0x4ec66", "0x4ec7c"]] and esc["first_home_line"] == 5
assert esc["home_stos"] == 851760 and esc["excursions"] == 332
assert esc["excursion_entries"] == [["0070:000042D1", 332]]
last_home = E.parse_line(esc["last_home"]["text"])
escape = E.parse_line(esc["escape"]["text"])
assert esc["last_home"]["line"] == 7060957 and esc["escape"]["line"] == 7060958
assert last_home["cs"] == "0170" and last_home["eip"] - DELTA == 0x4EC6A and last_home["regs"]["CR0"] == 0x11
assert last_home["regs"]["EDI"] == 0x170658 and last_home["regs"]["VM"] == 0
assert escape["cs"] == "0C5C" and escape["eip"] == 0xB94 and escape["regs"]["CR0"] == 0x10
# 低 16 位全 0、高 16 位保留(16 位元 POPA 框架);SS:SP = [40:67] + 0x1a
lo_zero = {k: (last_home["regs"][k] & 0xFFFF0000, escape["regs"][k]) for k in ("EAX", "ECX", "EDX", "ESI", "EDI", "EBP")}
assert all(a == b for a, b in lo_zero.values()), lo_zero
assert escape["regs"]["EBX"] == 0 and escape["regs"]["SS"] == 0x823 and escape["regs"]["ESP"] == 0x9F5
assert escape["regs"]["DS"] == 0 and escape["regs"]["ES"] == 0 and escape["regs"]["FLG"] == 0x202
top = dict((k, c) for k, c in esc["after_escape_top"])
assert top["C3FF:000094C8"] == top["F000:0000CA60"] == 3227611 and top["F000:0000CA64"] == 3227610
assert esc["after_escape_lines"] == 16777216 - 7060957

# 中斷出差:每段第一行(行號 / CS:EIP / EDI)
exc = [ln.split() for ln in (V21 / "exc_entries.txt").read_text(encoding="utf-8").splitlines()]
assert exc[0][:3] == ["1", "0170:001EAC16", "EDI:000A0728"]
irq = [(int(x[0]), x[1], int(x[2][4:], 16)) for x in exc[1:]]
assert len(irq) == 332 and all(c == "0070:000042D1" for _, c, _ in irq)
gaps = [b[0] - a[0] for a, b in zip(irq, irq[1:])]
last_irq = irq[-1]
assert last_irq == (7039301, "0070:000042D1", 0x16FBAB)
# 逃逸發生在下一個計時器週期:與上一次出差的行距落在一般週期的範圍內
assert min(gaps) <= 7060958 - last_irq[0] <= max(gaps), (min(gaps), max(gaps))

# stosb:每次 EDI + 1,0xa0728 → 0x170657
writes: dict[int, int] = {}
prev = None
for ln in (V21 / "stos_writes.txt").read_text(encoding="utf-8").splitlines():
    a, v = ln.split()
    a = int(a, 16)
    assert prev is None or a == prev + 1
    prev = a
    writes[a] = int(v, 16)
assert len(writes) == 851760 and min(writes) == 0xA0728 and max(writes) == 0x170657

pre = (V21 / "r1_pre_ext1m.bin").read_bytes()
vga = (V21 / "r1_pre_vgabios.bin").read_bytes()
ivt = (V21 / "r1_pre_ivt.bin").read_bytes()
assert len(pre) == 0x100000 and len(vga) == 0x8000 and len(ivt) == 0x500


def P(lin: int, n: int) -> bytes:
    return pre[lin - 0x100000:lin - 0x100000 + n]


# GDT:平坦 code / data 描述子只出現一次,位在 +0x170 / +0x178 → base 0x170010
flat = [i for i in range(len(pre) - 16) if pre[i:i + 8] in (bytes.fromhex("ffff0000009acf00"), bytes.fromhex("ffff0000009bcf00"))
        and pre[i + 8:i + 16] in (bytes.fromhex("ffff00000092cf00"), bytes.fromhex("ffff00000093cf00"))]
assert [0x100000 + i for i in flat] == [0x170180]
GDT = 0x170180 - 0x170


def desc(b: bytes) -> dict:
    lo, blo, bmid, acc, fl, bhi = struct.unpack("<HHBBBB", b)
    return {"hex": b.hex(), "base": hex(blo | bmid << 16 | bhi << 24), "limit": hex(lo | (fl & 15) << 16),
            "access": hex(acc), "present": bool(acc & 0x80), "type5": hex(acc & 0x1F)}


gdt_pre = {hex(s): desc(P(GDT + s, 8)) for s in (0x70, 0x80, 0x170, 0x178)}
assert gdt_pre["0x70"]["hex"] == "cf5730e0189b0000" and gdt_pre["0x70"]["present"]
gdt_written = {hex(s): desc(bytes(writes[GDT + s + i] for i in range(8))) for s in (0x70, 0x80, 0x170, 0x178)}
assert gdt_written["0x70"]["hex"] == "2424242424242424" and not gdt_written["0x70"]["present"]
assert gdt_written["0x80"]["hex"] == "5c5c5c5c5c5c5c5c" and not gdt_written["0x80"]["present"]

# 事後(實際模式,段 0)讀回:與追蹤還原的寫入逐 byte 相同;前緣之後與事前相同
post_gdt = (V21 / "r1_post0_gdt.bin").read_bytes()
mism = [a for a in range(GDT, 0x170658) if post_gdt[a - 0x170000] != writes[a]]
assert not mism and all(post_gdt[a - 0x170000] == P(a, 1)[0] for a in range(0x170658, 0x170700))

# IDT:0070:42d1 的閘在 0x18a150(整段 IDT 在寫入前緣之上,沒被寫到)
gate = struct.unpack("<HHBBH", P(0x18A150, 8))
assert gate[1] == 0x70 and (gate[4] << 16 | gate[0]) == 0x42D1 and gate[3] == 0x8E and 0x18A110 > 0x170657

# 重置向量與框架
bda_pre = struct.unpack_from("<HH", ivt, 0x467)
assert bda_pre == (0x09DB, 0x0823)
post_bda = (V21 / "r1_post0_bda.bin").read_bytes()
assert struct.unpack_from("<HH", post_bda, 0x67) == (0x09DB, 0x0823)
frame = struct.unpack("<13H", (V21 / "r1_post0_resetframe.bin").read_bytes())
assert frame[:10] == (0,) * 10 and frame[10:] == (0xB94, 0xC5C, 0x200)
assert 0x9DB + 2 * 13 == 0x9F5

# XMS 入口與 INT 6 指令的位元組
xms_pre = vga[0x4000:0x400A]
assert xms_pre == bytes.fromhex("eb039090 90fe3843 00cb".replace(" ", ""))
xms_post = (V21 / "r1_post0_xms.bin").read_bytes()[:16]
assert xms_post == bytes(writes[0xC4000 + i] for i in range(16)) and xms_post[:8] == b"\x4c" * 8
arpl_post = (V21 / "r1_post0_arpl.bin").read_bytes()[0x18:0x1C]
assert arpl_post == bytes(writes[0xCD4B8 + i] for i in range(4)) == bytes.fromhex("63b94b4b")
assert 0xC3FF0 + 0x94C8 == 0xCD4B8 and 0xC3FF0 + 0x10 == 0xC4000

ex = (V21 / "trace_excerpt.txt").read_text(encoding="utf-8").splitlines()
assert ex[0].startswith("# lines 16777216 bytes 5402271701 sha256 10d20cbdae4634c4")
assert ex[1] == "# first_C3FF 7064626 first_INT6_handler 7094386"
exl = {int(x.split("\t")[0]): x.split("\t", 1)[1] for x in ex[2:]}
call_xms = E.parse_line(exl[7064625])
assert call_xms["cs"] == "0C5C" and call_xms["eip"] == 0x1DFE and "call far word [0AEC]" in call_xms["text"]
assert call_xms["regs"]["EAX"] & 0xFF00 == 0x0D00
first_c3 = E.parse_line(exl[7064626])
assert first_c3["cs"] == "C3FF" and first_c3["eip"] == 0x10 and first_c3["mnem"] == "dec"
i6 = E.parse_line(exl[7094386])
assert i6["cs"] == "F000" and i6["eip"] == 0xCA60 and E.parse_line(exl[7094385])["eip"] == 0x94C8

# v16 對照:終點位元組不是 v21 在同一位址寫的值 → 寫入內容每次不同
v16_pane = (V16 / "r1_halt_pane.txt").read_text(encoding="utf-8")
assert "C3FF:000035F7 63B94F4F" in v16_pane
assert bytes(writes[0xC75E7 + i] for i in range(4)) == b"\xfd" * 4
assert arm["esi"] == 0x26C460 and last_home["regs"]["ESI"] == 0x2A3B30

ev: dict = {"_meta": {
    "exe": rel(EXE), "exe_md5": md5(EXE),
    "chapter": "第 25 章戰場 = map 24(reach_battle.py + .wsl_build/FD2.SAV);v21 另套 v9_setup.py + v11_setup.py,t_v21 只跑設定 4(線性 7 = 0x89)",
    "raw_dirs": [rel(V21), rel(V22)] + [rel(C / f"{v}/ch25") for v in ("v30", "v31", "v32")],
    "drivers": "evidence/generators/:t_v21.py(由 mk_t_v21.py 從 t_v16.py 產生)、t_v19b.py(nocorrupt prearmed)、v21_exc.sh、v21_gdt.sh、v21_c4000.sh、v21_excerpt.sh;本檔由 ev_s75.py 重算",
    "trace": {"file": "~/fd2-run-harness-v21/LOGCPU.TXT(WSL,不複製)", "header": ex[0][2:], "mode": "LOGL",
              "count": "0x1000000", "armed_at": "0x4ec16(寬 0、高 43570 已讀進 BP / DX),BPDEL * 後 heavylog + arm"},
    "process": [
        "v21:t_v21 停在 0x4ec16 時先傾印事前狀態(IVT + BDA 0x0..0x500、0xc0000..0xc8000、0x100000..0x200000,選擇器 0170 = 保護模式平坦),"
        "BPDEL *、dosbox_exec_trace.sh heavylog、FD2_TRACE_MODE=LOGL arm 1000000,之後不送 resume,只看 pane 與檔案狀態。55 秒後計數用完,除錯器自己停住。",
        "第一次事後傾印仍用選擇器 0170,但那時 CPU 在實際模式:MEMDUMPBIN 把 0170 當段落讀 0x1700 + 位址(IVT 讀成全 0),作廢;"
        "改 fd2_dosbox_live_helper.sh 依模式判斷後,以段 0 重讀 GDT / XMS 入口 / arpl / BDA / 重置框架(r1_post0_*.bin)。",
        "escape.json = dosbox_cpulog_escape.py LOGCPU.TXT --home 0x4ec1f-0x4ec27,0x4ec66-0x4ec7c --keep 60(WSL 端跑,2 分 17 秒)。",
        "v22:戰況記錄 → 0x25ecd 斷點在戰場內下好 → 索爾 +5 |= 1、悠妮轉盤 Down, Return → 戰敗回標題 → t_v19b c1(CONTINUE)nocorrupt prearmed;"
        "回到戰場後同樣再一次 → t_v19b l1(LOAD)nocorrupt prearmed。",
        "v23 ~ v27:reach_battle.py 以固定 30 次 Escape 後盲選 LOAD,開機變慢時按鍵落到 START 開成新遊戲,五次全部作廢;"
        "改成截圖確認標題選單(火焰標誌 + 藍色副標)才選 LOAD、載入後全黑就報錯(v28 起;標題在第 27 次 Escape 才出現)。",
        "v28 / v29 在暫停期間 WSL 重啟而中斷(v28 只記到第一個停點),作廢。v30 / v31 照 v21 只跑 k = 4;v32 照 v11 跑 k = 0..4。"
        "v30 ~ v32 的 escape.json 同樣由 dosbox_cpulog_escape.py 在 WSL 端算,事後記憶體以段 0 讀(r1_post0_*.bin)。"]}}

ev["A_triple_fault_chain_v21"] = {
    "blit_writes": {"stosb": 851760, "from": "0xa0728", "to": "0x170657", "step": "+1(每次 EDI 恰好加 1,沒有跳)"},
    "timer_irq_excursions": {"count": 332, "entry": "0070:000042D1(IDT 0x18a150 的閘,type 0x8e)",
                             "period_lines": [min(gaps), max(gaps)], "last_ok": {"line": 7039301, "edi": "0x16fbab"},
                             "escape_gap_lines": 7060958 - last_irq[0]},
    "gdt": {"base": hex(GDT), "found_by": "事前傾印裡唯一一組平坦 code + data 描述子(+0x170 / +0x178)",
            "before": gdt_pre, "written_by_blit": gdt_written, "post_read_back_equals_trace": "0x170010..0x170657 共 1608 bytes 全同;0x170658 之後與事前相同"},
    "escape": {"last_in_loop": {"line": 7060957, "at": "0x4ec6a dec ah", "cr0": "0x11", "edi": "0x170658"},
               "next": {"line": 7060958, "at": "0C5C:0B94 mov ax, 0823", "cr0": "0x10", "ss_esp": "0823:09F5"},
               "registers": {k: [hex(last_home["regs"][k]), hex(escape["regs"][k])] for k in ("EAX", "EBX", "ECX", "EDX", "ESI", "EDI", "EBP")},
               "between": "沒有任何一條指令被記下(DOSBox-X 在 C++ 裡處理三重錯誤與重置)"},
    "reset_path(DOSBox-X 原始碼,~/fd2-dosbox-build/dosbox-x/src)": {
        "cpu/cpu.cpp CPU_Exception": "Double fault already in progress == Triple Fault → On_Software_CPU_Reset()",
        "hardware/memory.cpp On_Software_CPU_Reset": "CMOS 關機碼 0x05 / 0x0A → 跳 [40:67](暫存器設成 EAX 0x2010000 …);0x09 → INT 15h block move 返回",
        "hardware/memory.cpp 關機碼 9": "SS:SP = [40:67],彈出 ES、DS、16 位元 POPA(DI SI BP 略過 SP BX DX CX AX)再 IRET —— 32 位元暫存器只換掉低 16 位",
        "observed": {"[40:67]": "0823:09DB(事前、事後相同)", "frame_at_0823:09DB": "ES DS 0、POPA 全 0、IP 0B94、CS 0C5C、FLAGS 0200",
                     "sp_check": "0x9DB + 13 × 2 = 0x9F5 = 逃逸行的 ESP"},
        "inference": "只有關機碼 9 這條路同時符合 CS:IP、SS:SP 與『低 16 位清 0、高 16 位保留』;CMOS 位元組本身沒有讀(INFERRED)"},
    "after_reset": {"real_mode_code": "DOS/4GW 0C5C 段", "xms_call": "0C5C:1DFE call far word [0AEC](AH = 0Dh,XMS 解鎖 EMB)→ C3FF:0010 = 0xc4000",
                    "xms_entry_before": xms_pre.hex(" ") + "(jmp +3 / nop×3 / DOSBox-X callback 0x43 / retf)",
                    "xms_entry_written": xms_post.hex(" ") + "(blit 寫入值 = 事後讀回值;被當成 dec sp … 執行)",
                    "first_C3FF_line": 7064626, "first_int6_line": 7094386,
                    "int6_insn": "C3FF:94C8 = 0xcd4b8 的 63 b9 4b 4b(arpl,實際模式無效指令),也是 blit 寫的",
                    "loop": "C3FF:94C8 → F000:CA60(BIOS 預設 INT 6 處理常式 callback)→ iret 各 3,227,611 次直到計數用完"},
    "conclusion": "0x89 的假頭像讓 blit 從 0xa0728 一路往上寫;途中先蓋掉 DOSBox-X 在 0xc4000 的 XMS 入口,再在 0x170010 蓋掉 DOS/4GW 的 GDT。"
                  "遊戲自己的段暫存器有描述子快取,所以 blit 照跑;下一次計時器 IRQ 要載入 CS 0070 時描述子已是 24242424…(不存在),"
                  "錯誤處理也用同一組描述子 → 三重錯誤 → DOSBox-X 重置 CPU、依 CMOS 關機碼 9 回到 DOS/4GW 的實際模式碼 → 它呼叫已被蓋掉的 XMS 入口 → "
                  "執行 blit 寫的像素資料,直到無效指令 arpl 進 INT 6 迴圈。"}

ev["B_run_to_run_variation"] = {
    "v16_end": "C3FF:35F7 = 0xc75e7 的 63 b9 4f 4f(r1_halt_pane.txt)",
    "v21_written_at_0xc75e7": "fd fd fd fd",
    "src": {"start": "0x26c460(v21,= v16 的 0x26c45c + 兩次 lodsw)", "at_escape": "0x2a3b30"},
    "reason": "資源只有 3654 bytes,blit 的來源指標一路讀過頭(v21 讀了約 0x376d0 bytes 的堆積 / 遊戲資料),寫出的內容隨當下記憶體而變;"
              "XMS 入口之後執行的垃圾碼因此可能不同。v11 為什麼走到 E_Exit「JMP Illegal descriptor type 14」沒有查明 —— 照 v11 的設定(k = 0..4)重跑的 v32 仍走 INT 6(見 E 節)"}

# ---------------- C. 工具 ----------------
ev["C_tools"] = {
    "dosbox_exec_trace.sh": {"FD2_TRACE_MODE": "LOGC(預設)/ LOGS / LOG / LOGL;LOGL 每行含時間戳、反組譯、位元組、全部暫存器、旗標、VM、CR0",
                             "heavylog": "送 HEAVYLOG(切換);E_Exit 時寫 LOGCPU_INT_CD.TXT(最後 20000 條)",
                             "count_guard": "1..7FFFFFFF(debug.cpp 的計數是 int)",
                             "status": "也列出 LOGCPU_INT_CD.TXT",
                             "live": "v21:heavylog 回 'Heavy cpu logging on.'、arm 回 'armed: LOGL 1000000 (16777216 instructions)'、55 秒錄滿 16,777,216 行後自停"},
    "dosbox_cpulog_escape.py": {"what": "串流讀 LOGCPU.TXT,找最後一次離開 --home 的那一條(中斷出差不算)、出差次數 / 入口、家裡 stos 與最後 EDI、逃逸後的模式變化與熱點",
                                "selftest": "13 組;verify_selftest_discrimination --exhaustive 可達突變全部抓到"},
    "fd2_dosbox_live_helper.sh mem-dump": {"before": "一律拒絕選擇器 0,其他值照送 —— 實際模式下 0170 被當段落,靜靜讀 0x1700 + 位址",
                                           "after": "讀 Register Overview 的模式:Real / VM86 時 0 = 平坦讀取、非 0 拒絕(FD2_MEMDUMP_REAL_SEGMENT=1 可強制);"
                                                    "Pr16 / Pr32 / 不明時照舊拒絕 0",
                                           "live": "v21 實際模式:0170 被拒(訊息寫明 0x0170*16 + linear),段 0 讀 GDT / XMS / arpl / BDA / 重置框架"}}

# ---------------- D. v22 對照 ----------------
rows = {}
for tag, choice, ret_load, writer in (("c1", 2, "0x1013b", "0x1013e"), ("l1", 1, "0x25f79", "0x25f7c")):
    run = J(V22 / f"{tag}.json")
    s = run["stops"]
    assert run["pre"] == {"prearmed": True, "corrupt": False}
    assert s[0]["eip"] == "0x25ecd" and s[0]["choice_eax"] == choice
    assert s[0]["pal_hdr_before"] == s[0]["pal_hdr_after"] == "05030000"
    i = next(k for k, x in enumerate(s) if x["eip"] == "0x111ba" and x.get("armed"))
    assert s[i]["ret"] == ret_load and s[i]["old"] == s[0]["pal"] and s[i]["old_hdr"] == "05030000"
    assert [x["eip"] for x in s[i + 1:i + 7]] == ["0x3d67f", "0x3d685", "0x3d693", "0x3d72e", "0x111d5", writer]
    assert s[i + 1]["is_watch"] and s[i + 2]["is_watch"] and s[i + 5]["watch_hdr_after"] == "00060000"
    assert s[i + 6]["new_pal"] == s[0]["pal"] and s[i + 6]["new_pal_hdr"] == "05030000"
    assert not run["state"]["emulator_gone"]
    rows[tag] = {"choice_eax": choice, "pal": s[0]["pal"], "hdr": "05030000(不改)",
                 "reload_free": {"ret": ret_load, "path": ["0x3d67f", "0x3d685", "0x3d693", "0x3d72e", "0x111d5"],
                                 "freed_hdr_after": "00060000", "nodes": [s[i + 3]["node"], s[i + 4]["node"]]},
                 "new_palette": {"writer": writer, "addr": s[i + 6]["new_pal"], "same_block_reused": True}}
v19c, v19l = J(V19 / "c1.json"), J(V19 / "l2.json")
assert v19c["stops"][0]["pal_hdr_after"] == v19l["stops"][0]["pal_hdr_after"] == "102b0400"
ev["D_continue_load_control_v22"] = {
    "CONTINUE(c1)": rows["c1"], "LOAD(l1)": rows["l1"],
    "corrupted(續七十四 v19)": {"CONTINUE": "0x3d67f 讀到 102b0400 → 0x111d5(沒有 0x3d685),新調色盤 0x20fc38,舊塊洩漏",
                              "LOAD": "同上,新調色盤 0x22841c"},
    "screens": {"v22 c1_08_-.png": "回到記錄戰況時的戰場,色彩正常"},
    "conclusion": "標頭完好時,CONTINUE / LOAD 的第一次重載走 0x3d685 → 0x3d693 → 0x3d72e 真的釋放,新調色盤配回同一塊(0x1fd0c4);"
                  "改壞時在 0x3d67f 直接返回而洩漏、新調色盤配到別處。差別只在標頭。"}

# ---------------- E. 取樣:v30 / v31(只跑 k = 4)、v32(照 v11 跑 k = 0..4) ----------------
samples = {"v21": {"cfg": "4", "escape_line": 7060958, "frontier": 0x170657, "gdt_0070_after": post_gdt[0x80:0x88].hex(),
                   "gdt_0070_access": hex(post_gdt[0x85]), "gdt_0070_present": bool(post_gdt[0x85] & 0x80), "excursions": 332}}
for v, cfg, line, front in (("v30", "4", 7024284, 0x170152), ("v31", "4", 7047177, 0x170231),
                            ("v32", "0,1,2,3,4", 7051374, 0x170843)):
    d = C / f"{v}/ch25"
    r = J(d / "r1.json")
    a = next(s for s in r["stops"] if "arm_out" in s)
    assert r["state"]["trace_end"] == "count_done" and a["width_bp"] == 0 and a["height_dx"] == 43570
    e = J(d / "escape.json")
    x = E.parse_line(e["escape"]["text"])
    assert e["lines"] == 16777216 and e["escape"]["line"] == line and int(e["last_home_stos"]["edi"], 16) == front
    assert (x["cs"], x["eip"], x["regs"]["SS"], x["regs"]["ESP"], x["regs"]["CR0"]) == ("0C5C", 0xB94, 0x823, 0x9F5, 0x10)
    assert e["excursion_entries"][0][0] == "0070:000042D1" and len(e["excursion_entries"]) == 1
    fr = struct.unpack("<13H", (d / "r1_post0_resetframe.bin").read_bytes())
    assert fr == (0,) * 10 + (0xB94, 0xC5C, 0x200)
    g = (d / "r1_post0_gdt.bin").read_bytes()
    assert g[0x80:0x88] != bytes.fromhex(gdt_pre["0x70"]["hex"])  # 0070 已不是原本的描述子
    pane = (d / "r1_trace_end_pane.txt").read_text(encoding="utf-8")
    assert "Illegal Unhandled Interrupt Called 6" in pane and "E_Exit" not in pane
    top = dict((k, c) for k, c in e["after_escape_top"])
    samples[v] = {"cfg": cfg, "escape_line": line, "frontier": hex(front), "gdt_0070_after": g[0x80:0x88].hex(),
                  "gdt_0070_access": hex(g[0x85]), "gdt_0070_present": bool(g[0x85] & 0x80),
                  "gdt_0170_after": g[0x180:0x188].hex(), "excursions": e["excursions"],
                  "int6_loop_top": [k for k, _ in e["after_escape_top"][:3]],
                  "end_regs": [ln.strip() for ln in pane.splitlines() if "EAX=" in ln][:1]}
samples["v21"]["frontier"] = hex(samples["v21"]["frontier"])
v11_pane = (C / "v11/ch25/r1_crash_pane.txt").read_text(encoding="utf-8")
assert "E_Exit: JMP Illegal descriptor type 14" in v11_pane
assert "C3FF:000035F7" in v16_pane
v32_pane = (C / "v32/ch25/r1_trace_end_pane.txt").read_text(encoding="utf-8")
assert "EDI=0017602B" in v16_pane and "EDI=0017602B" in v32_pane and "ESI=002A14B3" in v32_pane
ev["E_branch_sampling"] = {
    "traced": samples,
    "untraced": {"v11": "設定 0..5 依序跑,k = 4 時 E_Exit「JMP Illegal descriptor type 14」(續七十三,面板逐字轉錄)",
                 "v16": "只跑 k = 4,INT 6 迴圈(C3FF:35F7);終止暫存器與 v32 相同(EDI 0017602B、ESI 002A14B3)"},
    "tally": "INT 6 迴圈 5 次(v16、v21、v30、v31、v32),E_Exit 1 次(v11)",
    "common_chain": "四次追蹤的寫入前緣都在 0x170087 之後(0070 描述子已整個被蓋);下一條指令都是 0C5C:0B94、SS:SP 0823:09F5,重置框架都在 0823:09DB",
    "gdt_0070": "v21 / v30 / v31 被寫成 access 0x24 / 0x5c(不存在);v32 是 0xfd(存在,但成了 DPL 3 的 conforming 程式碼段 —— 中斷閘要求目標段 DPL ≤ CPL 0)。"
                "兩種都讓 IRQ 送不進去,錯誤種類推得是 #NP 與 #GP(INFERRED,追蹤看不到)",
    "conclusion": "從計時器 IRQ 到 0C5C:0B94 的三重錯誤 / 重置路徑在每次追蹤都相同;E_Exit 那一支沒有再出現,連照 v11 的設定重跑也一樣,它的確切指令仍未取得"}

ev["not_covered"] = [
    "v11 那一支(E_Exit「JMP Illegal descriptor type 14」)的確切指令:5 次取樣(含照 v11 設定重跑的 v32)都走 INT 6,沒有重現;"
    "dosbox_exec_trace.sh 的 LOGL + heavylog 已能在它再出現時記下最後一條指令。",
    "CMOS 關機碼 9 本身沒有讀出來,由 CS:IP、SS:SP 與暫存器形狀推得(只有這條重置路徑同時符合)。",
    "計時器 IRQ 的錯誤到底是 #NP 還是 #GP、雙重錯誤用哪個閘,追蹤看不到(DOSBox-X 在 C++ 裡處理,不產生指令紀錄)。"]


def write() -> None:
    OUT.write_text(json.dumps(ev, ensure_ascii=False, indent=1) + "\n", encoding="utf-8", newline="\n")
    print("ok", OUT.name, len(OUT.read_bytes()))


if __name__ == "__main__":
    write()
