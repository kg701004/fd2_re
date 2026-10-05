"""續七十六~七十七證據:evidence/runaway_blit_fault_class_dos16m_guard_20261005.json(續七十五的三個未驗證項目)。

A. DOSBox-X 原始碼(執行中二進位的同一棵樹,GIT_COMMIT_HASH 6fb8c07):中斷閘的檢查順序、雙重 / 三重錯誤、
   CMOS 關機碼分派、「JMP Illegal descriptor type」只在 CPU_JMP、CPU_JMP 只由遠跳指令呼叫。
B. 五次取樣的 IDT / GDT:計時器(向量 8)與 #GP(向量 0x0D)的閘都指向 0070;0070 被蓋成的 DPL 都 > CPL 0 → #GP。
C. 重置後回到的是 DOS/4GW(DOS/16M 核心)的「非自願切回實際模式」防護碼:印錯誤訊息,之後 XMS 清理。
D. 防護碼印完先照平常 jmp 0018:0334 回保護模式;0018 早被 blit 蓋掉,結果由它的型別決定(五份追蹤都在兩次重置之間跳一次)。
F. 受控注入 g1~g4(原版 FD2.EXE,停在 0070:42D1 改 8 bytes):0x24 / 0x5c → Exception 13;0018 改成型別 0x14 → 與 v11 逐字相同的 E_Exit。
G. v11:成因由 g3 重現;v11 當次 0018 的實際 byte 沒有傾印。
全部從 .wsl_build 的原始紀錄重算;任何預測不符就 assert 失敗。
"""
from __future__ import annotations

import hashlib
import json
import re
import struct
from pathlib import Path

from _evpaths import GAME, GEN_DIR, ROOT, out_path, require_inputs  # noqa: E402
require_inputs(__file__)
EXE = GAME / "FD2.EXE"
C = ROOT / ".wsl_build/ctr"
SRC = ROOT / ".wsl_build/dosbox_src_6fb8c07"
RUNS = ("v21", "v30", "v31", "v32", "v33")
OUT = out_path("runaway_blit_fault_class_dos16m_guard_20261005.json")
EXT = 0x100000          # r1_pre_ext1m.bin 的起點
IDT = 0x18A110          # 續七十五:IRQ0 的閘在 0x18a150 = 向量 8
GDT = 0x170010          # 續七十五:平坦 code / data 在 +0x170 / +0x178
GDT_DUMP = 0x170000     # r1_post0_gdt.bin 的起點
MSG = "DOS/16M error: [0]  involuntary switch to real mode"


def md5(p: Path) -> str:
    return hashlib.md5(p.read_bytes()).hexdigest()


def sha(p: Path) -> str:
    return hashlib.sha256(p.read_bytes()).hexdigest()


def J(p: Path) -> dict:
    return json.loads(p.read_text(encoding="utf-8"))


def T(name: str) -> str:
    return (SRC / name).read_text(encoding="utf-8", errors="replace")


def body(src: str, head: str) -> str:
    """從 head 開始到下一個頂層函式(行首非空白的 'void ' / 'bool ' / 'static ')為止。"""
    i = src.index(head)
    m = re.search(r"\n(?:void|bool|static|Bitu|uint8_t) [A-Za-z_]", src[i + len(head):])
    return src[i: i + len(head) + (m.start() if m else len(src))]


def lineno(src: str, needle: str) -> int:
    assert src.count(needle) == 1, needle
    return src[: src.index(needle)].count("\n") + 1


def desc(b: bytes) -> dict:
    acc = b[5]
    return {"raw": b.hex(), "access": f"0x{acc:02x}", "p": acc >> 7, "dpl": (acc >> 5) & 3, "type": f"0x{acc & 0x1F:02x}"}


assert md5(EXE) == "33464c81e6a364fd0660141139aa8e6e"

# ---------------- A. 原始碼 ----------------
cpu, mem, cmos, dbg = T("cpu.cpp"), T("memory.cpp"), T("cmos.cpp"), T("debug_gui.cpp")
pn, p66, cpuh = T("prefix_none.h"), T("prefix_66.h"), T("cpu.h")
assert '#define GIT_COMMIT_HASH "6fb8c07"' in T("build_timestamp.h")
bstr = T("binary_strings.txt").splitlines()
for s in ("Triple Fault. Resetting CPU.", "already in progress, triggering double fault instead",
          "INT 15 block move reset", "JMP Illegal descriptor type %X"):
    assert any(s in x for x in bstr), s
# CPU_CHECK_COND = 丟例外(不是 E_Exit、不是忽略)
assert re.search(r"^#define CPU_CHECK_EXCEPT 1", cpu, re.M) and re.search(r"^// #define CPU_CHECK_IGNORE 1", cpu, re.M)
chk = cpu[cpu.index("#elif defined(CPU_CHECK_EXCEPT)"): cpu.index("#else", cpu.index("#elif defined(CPU_CHECK_EXCEPT)"))]
assert "CPU_Exception(exc,sel);" in chk
# 中斷閘:先比 DPL(> CPL → #GP),再看 present(#NP);型別不是程式碼段 → E_Exit
intr = body(cpu, "void CPU_Interrupt(Bitu num,Bitu type,uint32_t oldeip) {")
i_priv = intr.index('"Interrupt to higher privilege"')
i_np_in = intr.index('"INT:Inner level:CS segment not present"')
i_np_same = intr.index('"INT:Same level:CS segment not present"')
i_bad = intr.index('E_Exit("INT:Gate Selector points to illegal descriptor with type %x"')
assert i_priv < i_np_in < i_np_same < i_bad
assert "CPU_CHECK_COND(cs_dpl>cpu.cpl," in intr and "EXCEPTION_GP,(gate_sel & 0xfffc)+((type&CPU_INT_SOFTWARE)?0:1))" in intr
# 雙重 / 三重錯誤
exc = body(cpu, "void CPU_Exception(Bitu which,Bitu error ) {")
assert exc.index("CPU_Exception_Level[EXCEPTION_DF] != 0 && cpu_triple_fault_reset") < exc.index("On_Software_CPU_Reset();")
assert 'LOG_MSG("CPU_Exception: Exception %d already in progress, triggering double fault instead",(int)which);' in exc
assert "which = EXCEPTION_DF;" in exc
# CMOS 關機碼分派:5 / 0A → reset vector(暫存器設成 0x2010000 …),9 → INT 15 block move 返回,其他 → 整機重置
reset = body(mem, "void On_Software_CPU_Reset() {")
sw = reset[reset.index("switch (c=CMOS_GetShutdownByte())"):]
assert re.search(r"case 0x05:.*?case 0x0A:.*?On_Software_286_reset_vector\(c\);", sw, re.S)
assert re.search(r"case 0x09:.*?On_Software_286_int15_block_move_return\(c\);", sw, re.S)
assert "throw int(3);" in reset
blk = body(mem, "void On_Software_286_int15_block_move_return(unsigned char code) {")
pops = re.findall(r"CPU_Pop16\(\)", blk)
assert len(pops) == 10 and "CPU_IRET(false,0);" in blk and "phys_readw(0x400 + 0x67)" in blk
frame_bytes = 2 * len(pops) + 6        # ES、DS、POPA 八個字(含丟掉的 SP)+ IRET 的 IP / CS / FLAGS
assert frame_bytes == 26
vec = body(mem, "void On_Software_286_reset_vector(unsigned char code) {")
assert "reg_eax = 0x2010000;" in vec and "reg_esp = 0x4F8;" in vec
assert "case 0x0f:      /* Shutdown status byte */" in cmos
# 「JMP Illegal descriptor type」只在 CPU_JMP 的 default;CPU_JMP 只由 JMP Ap(0xEA)與 JMP Ep(FF /5)呼叫
assert cpu.count("JMP Illegal descriptor type") == 1
jmp = body(cpu, "void CPU_JMP(bool use32,Bitu selector,Bitu offset,uint32_t oldeip) {")
assert 'E_Exit("JMP Illegal descriptor type %X",(int)desc.Type());' in jmp
assert "if (!cpu.pmode || (reg_flags & FLAG_VM)) {" in jmp       # 實際 / V86 模式不檢查描述子
callers = {}
for nm, s in (("prefix_none.h", pn), ("prefix_66.h", p66)):
    for m in re.finditer(r"CPU_JMP\(", s):
        ctx = s[max(0, m.start() - 700): m.start()]
        tag = re.findall(r"CASE_[WD]\(0xea\)|case 0x05:", ctx)
        callers.setdefault(nm, []).append(tag[-1] if tag else None)
assert callers == {"prefix_none.h": ["CASE_W(0xea)", "case 0x05:"], "prefix_66.h": ["CASE_D(0xea)", "case 0x05:"]}, callers
cpu_jmp_other = [m.start() for m in re.finditer(r"CPU_JMP\(", cpu) if not cpu[m.start() - 5: m.start()].endswith("void ")]
assert len(cpu_jmp_other) == 1 and "CPU_JMP(false,0,0,0);" in cpu   # 開機時設定 CPU 核心那一次(實際模式)
assert re.search(r"#define DESC_DATA_ED_RO_NA\s+0x14u", cpuh)
assert re.search(r"uint32_t type\s+:5;", cpuh)
src_facts = {
    "tree": "~/fd2-dosbox-build/dosbox-x(build_timestamp.h GIT_COMMIT_HASH 6fb8c07;執行中二進位 md5 "
            + T("binary_md5.txt").split()[0] + ",訊息字串都在二進位裡)",
    "files_sha256": {n: sha(SRC / n) for n in ("cpu.cpp", "memory.cpp", "cmos.cpp", "debug_gui.cpp", "prefix_none.h",
                                               "prefix_66.h", "cpu.h")},
    "interrupt_gate_order": {
        "cs_dpl_gt_cpl_GP": lineno(cpu, '"Interrupt to higher privilege",'),
        "inner_level_not_present_NP": lineno(cpu, '"INT:Inner level:CS segment not present",'),
        "same_level_not_present_NP": lineno(cpu, '"INT:Same level:CS segment not present",'),
        "non_code_E_Exit": lineno(cpu, 'E_Exit("INT:Gate Selector points to illegal descriptor with type %x"'),
        "meaning": "CPU_CHECK_EXCEPT 有效時,閘的 CS 描述子 DPL > CPL 先丟 #GP,輪不到 present 檢查(#NP)"},
    "double_triple": {"double": lineno(cpu, 'LOG_MSG("CPU_Exception: Exception %d already in progress, triggering double fault instead",(int)which);'),
                      "triple": lineno(cpu, 'LOG_MSG("CPU_Exception: Double fault already in progress == Triple Fault. Resetting CPU.");')},
    "shutdown_dispatch": {"0x05_0x0A": "On_Software_286_reset_vector:CS:IP = [40:67],EAX 0x2010000、ESP 0x4F8、DS 0040",
                          "0x09": f"On_Software_286_int15_block_move_return:SS:SP = [40:67],彈出 ES、DS、POPA、IRET,共 {frame_bytes} bytes",
                          "other": "throw int(3) = 整機重置"},
    "jmp_e_exit": {"line": lineno(cpu, 'E_Exit("JMP Illegal descriptor type %X",(int)desc.Type());'),
                   "callers": callers,
                   "meaning": "只有保護模式(非 V86)的遠跳 JMP Ap / JMP Ep 會走到;印出的 14 是十六進位,"
                              "= DESC_DATA_ED_RO_NA(資料段、向下擴展、唯讀),CPU_JMP 的 switch 沒有資料段的 case"}}

# ---------------- B. 五次取樣:閘、被蓋成的描述子、預測 vs 記錄 ----------------
runs = {}
for v in RUNS:
    d = C / v / "ch25"
    pre = (d / "r1_pre_ext1m.bin").read_bytes()
    post = (d / "r1_post0_gdt.bin").read_bytes()
    gates = {}
    for n in (0x08, 0x0D):
        g = pre[IDT - EXT + n * 8: IDT - EXT + n * 8 + 8]
        gates[f"0x{n:02x}"] = {"selector": f"{struct.unpack_from('<H', g, 2)[0]:04x}", "access": f"0x{g[5]:02x}"}
    assert all(x == {"selector": "0070", "access": "0x8e"} for x in gates.values()), (v, gates)
    D = {}
    for sel in (0x18, 0x70, 0x80):
        a = GDT + sel
        D[f"{sel:04x}"] = {"pre": desc(pre[a - EXT: a - EXT + 8]), "post": desc(post[a - GDT_DUMP: a - GDT_DUMP + 8])}
    assert D["0070"]["pre"]["raw"] == "cf5730e0189b0000" and D["0018"]["pre"]["raw"] == "ffffc0c5009b0000"
    esc = J(d / "escape.json")
    # CPL:迴圈裡 CS = 0170,RPL 0(DOSBox-X 把 CS 值設成 選擇器 | CPL)
    assert " 0170:" in esc["last_home"]["text"]
    cpl = 0x0170 & 3
    o = D["0070"]["post"]
    assert o["raw"] != D["0070"]["pre"]["raw"]
    # 原始碼預測:閘 0070 的 CS DPL > CPL → #GP(0x0D);#GP 的閘也是 0070 → 再 #GP → 雙重錯誤(向量 8,也是 0070)→ 三重
    predicted = "GP(13)" if o["dpl"] > cpl else ("E_Exit INT" if int(o["type"], 16) < 0x18 else "NP(11)" if not o["p"] else "ok")
    assert predicted == "GP(13)", (v, o)
    e = esc["escape"]["text"]
    assert " 0C5C:00000B94 " in e and "ESP:000009F5" in e and "CR0:00000010" in e
    assert esc["after_escape_modes"] and esc["excursion_entries"][0][0] == "0070:000042D1"
    runs[v] = {"idt_gates_0x08_0x0d": gates, "descriptors": D, "cpl": cpl, "predicted_fault": predicted,
               "escape_line": esc["escape"]["line"], "escape": "0C5C:0B94 ESP 0x9F5 CR0 0x10"}

# v33:DOSBox-X 記錄檔(FD2_HARNESS_LOGFILE=1)逐字
logx = (C / "v33/ch25/dosbox-x_log_excerpt.txt").read_text(encoding="utf-8").splitlines()
L = {int(x.split(":", 1)[0]): x.split(":", 1)[1] for x in logx[1:]}
seq = [L[k] for k in sorted(L) if k < 3330258][-3:]
assert seq == ["CPU_Exception: Exception 13 already in progress, triggering double fault instead",
               "CPU_Exception: Double fault already in progress == Triple Fault. Resetting CPU.",
               "CMOS Shutdown byte 0x09 says to do INT 15 block move reset 0823:09db. "
               "Only weirdos like Windows 3.1 use this... NOT WELL TESTED!"], seq
rom = [L[k] for k in sorted(L) if "Write" in L[k] and "to rom" in L[k]]
assert rom and rom[-1].endswith("lin=fffff phys=fffff")
assert logx[0].startswith("# total_lines 3330262") and "int6_lines 3247840" in logx[0]
bda = (C / "v33/ch25/r1_post0_bda.bin").read_bytes()
frame = (C / "v33/ch25/r1_post0_resetframe.bin").read_bytes()
assert bda[0x67:0x6B] == bytes.fromhex("db092308")              # [40:67] = 0823:09DB
assert frame == bytes(20) + bytes.fromhex("940b5c0c0002")       # ES DS POPA 全 0、IP 0B94、CS 0C5C、FLAGS 0200
assert 0x9DB + frame_bytes == 0x9F5
for v in RUNS[1:]:
    assert (C / v / "ch25/r1_post0_xms.bin").read_bytes()[:10] != bytes.fromhex("eb039090 90fe384300cb".replace(" ", ""))
log_v33 = {"source": ".wsl_build/ctr/v33/ch25/dosbox-x_log_excerpt.txt(全檔 3,330,262 行,INT 6 迴圈 3,247,840 行)",
           "sequence": seq, "last_rom_write": rom[-1].split(" ", 1)[1],
           "bda_40_67": "0823:09DB", "reset_frame": frame.hex(),
           "prediction_vs_log": "原始碼對 0xfd(DPL 3)預測 #GP(13),記錄檔是 Exception 13;v21(0x24,DPL 1)、v30 / v31(0x5c,DPL 2)"
                                "同一條判斷也是 #GP,但那幾次沒開記錄檔(預測,未逐字讀到)"}

# ---------------- C. 重置後:DOS/16M 的「非自願切回實際模式」處理 ----------------
msgs = {}
for x in (C / "post_reset_messages.txt").read_text(encoding="utf-8").splitlines():
    v, t = x.split(" ", 1)
    msgs[v] = t
assert sorted(msgs) == list(RUNS)
for v, t in msgs.items():
    assert t == (MSG + "|~") * 2, (v, t)
exe = EXE.read_bytes()
assert exe.count(b"involuntary switch to real mode") == 1
# 0C5C 段 = FD2.EXE 檔案位移 + 0x1DD0(v21 重置後執行過的指令位元組,262 處唯一比對都是同一個位移)
SEG = 0x1DD0
tr = (C / "v21/ch25/post_reset_trace.txt").read_text(encoding="utf-8", errors="replace").splitlines()
code = {}
for ln in tr:
    m = re.match(r"\s*\S+\s+0C5C:([0-9A-F]{8})\s+(.*?)\s{2,}((?:[0-9A-F]{2} )+)\s*$", ln.split("EAX:")[0])
    if m:
        code[int(m.group(1), 16)] = bytes.fromhex(m.group(3).replace(" ", ""))
diff = {o: (b.hex(), exe[SEG + o: SEG + o + len(b)].hex()) for o, b in code.items() if exe[SEG + o: SEG + o + len(b)] != b}
# 不一致的三條都有解釋:兩條是 MZ 重定位(檔案 0000 → 載入後資料段 0823),一條是執行期把 3e 前綴改成 66(lgdt 改 32 位元)
assert len(code) == 365 and diff == {0xB94: ("b82308", "b80000"), 0x347: ("bb2308", "bb0000"),
                                     0x31F: ("660f01167409", "3e0f01167409")}, diff
xms_loop = exe[SEG + 0x1DEC: SEG + 0x1E12]
assert xms_loop.hex() == "bb10004b4b781e8b97dc0a0bd274f453b40dff1eec0ab40aff1eec0a5bc787dc0a0000ebdec3"
writes = [ln for ln in tr if " 0C5C:" in ln and re.search(r"\sint\s+21\s", ln)]
assert len(writes) >= 4 and all("EBX:00000002" in w and re.search(r"EAX:\w{4}40", w) for w in writes)
post_reset = {"message": MSG, "printed_per_run": {v: 2 for v in RUNS},
              "printer": "INT 21h AH=40h,BX=2(stderr),DS=0823;DOSBox-X 再經 INT 10h 印到畫面(v21 r1_trace_end.png 看得到)",
              "string_in_exe": "FD2.EXE 內嵌的 DOS/4GW(DOS/16M 核心)錯誤表第一條",
              "segment_0C5C_file_offset": f"0x{SEG:x}(v21 重置後執行過的 {len(code)} 條指令,{len(code) - len(diff)} 條逐 byte 相同;"
                                          "其餘 3 條是 MZ 重定位 0000 → 0823 兩條、執行期 3e → 66 前綴一條)",
              "after_message": "0C5C:1DEC~1E11 依序對 8 個 XMS handle 做 AH=0Dh(解鎖)、AH=0Ah(釋放)—— DOS/4GW 的結束清理;"
                               "第一個 call far [0AEC] 就進了被蓋掉的 XMS 入口 0xc4000",
              "meaning": "[40:67] 與關機碼 9 是 DOS/4GW 預先設好的防護:CPU 被重置時回到自己的實際模式碼、印錯誤、清理後結束。"
                         "INT 6 迴圈只是因為清理時呼叫的 XMS 入口已被 blit 蓋掉"}

# ---------------- D. 重置後一定經過 jmp 0018:0334:結果由 0018 被蓋成什麼決定 ----------------
# 0C5C:032D jmp 0018:0334 是 DOS/4GW 平常從實際模式回保護模式的那一跳(lmsw 之後 PE = 1,DOSBox-X 走保護模式的 CPU_JMP)
assert exe[SEG + 0x31A: SEG + 0x332].hex() == "0f01e00c01" + "3e0f01167409" + "0f011ed008" + "0f01f0" + "ea34031800"
reent = {}
for ln in (C / "guard_reentry_lines.txt").read_text(encoding="utf-8").splitlines():
    v = ln.split(" ", 1)[0]
    grab = {k: [int(x) for x in re.search(k + r"\[([\d ]*) \]", ln).group(1).split()] for k in ("entry", "jmp0018", "xms")}
    reent[v] = grab
assert sorted(reent) == list(RUNS)
jtype = {}
for v in RUNS:
    g = reent[v]
    e1, e2 = g["entry"]
    between = [x for x in g["jmp0018"] if e1 < x < e2]
    assert len(g["entry"]) == 2 and between == [e2 - 1] and g["jmp0018"][-1] == e2 - 1, (v, g)
    assert len([x for x in g["jmp0018"] if x < e1]) >= 40           # 平常就一直在用
    assert len(g["xms"]) == 1 and g["xms"][0] > e2, (v, g["xms"])          # 第二次進防護碼之後才做 XMS 清理
    d18 = runs[v]["descriptors"]["0018"]["post"]
    t18 = int(d18["type"], 16)
    # 原始碼(CPU_JMP)對各型別的預測:閘(4 / 5)且不存在 → #NP;conforming 程式碼 DPL > CPL → #GP;0x14 → E_Exit
    if t18 in (0x04, 0x05, 0x0C):
        pred = "NP" if not d18["p"] else "gate"
    elif t18 in (0x1C, 0x1D, 0x1E, 0x1F):
        pred = "GP" if d18["dpl"] > 0 else "ok"
    elif t18 == 0x14:
        pred = "E_Exit JMP Illegal descriptor type 14"
    else:
        pred = "other"
    assert pred in ("NP", "GP"), (v, d18, pred)        # 都不是 E_Exit → 第二次三重錯誤 → 第二次重置(entry 2)→ XMS 清理
    jtype[v] = {"0018_post": d18["raw"], "type": d18["type"], "predicted_at_jmp": pred,
                "entry_lines": g["entry"], "jmp_0018_between_entries": between, "xms_call_line": g["xms"],
                "jmp_0018_before_crash": len([x for x in g["jmp0018"] if x < e1])}
assert {v: x["predicted_at_jmp"] for v, x in jtype.items()} == {"v21": "NP", "v30": "NP", "v31": "NP", "v32": "GP", "v33": "GP"}
assert jmp.index("case DESC_TASK_GATE:") < jmp.index('"JMP:Gate:Segment not present",') < jmp.index('E_Exit("JMP Illegal descriptor type')
assert jmp.index('"JMP:C:CPL < DPL",') < jmp.index("CODE_jmp:")
reentry = {"site": "0C5C:031A~032D smsw / or al,1 / lgdt / lidt / lmsw / jmp 0018:0334(FD2.EXE 位移 0x20EA~0x2101)",
           "runs": jtype,
           "meaning": "第一次重置後,防護碼印完訊息就照平常的方式回保護模式:jmp 0018:0334。0018 的描述子(0x170028)早被 blit 蓋掉,"
                      "所以結果完全由那個 byte 的型別決定:v21 0x25(task gate)、v30 / v31 0x24(call gate)不存在 → #NP;"
                      "v32 / v33 0xfd(DPL 3 conforming)→ #GP;都再三重錯誤 → 第二次重置 → 第二次印訊息 → XMS 清理 → INT 6。"
                      "若那個 byte 的型別是 0x14,CPU_JMP 直接 E_Exit「JMP Illegal descriptor type 14」—— v11 的訊息"}

# ---------------- F. 受控注入(續七十七):原版 FD2.EXE 第 25 章戰場,停在 0070:42D1 改 8 bytes 後放開 ----------------
INJ = C / "inj"
inj = {}
want = {"g1": ("0070", "0x24", ["CPU_Exception: Exception 13 already in progress, triggering double fault instead",
                                 "CPU_Exception: Double fault already in progress == Triple Fault. Resetting CPU."], None),
        "g2": ("0070", "0x5c", ["CPU_Exception: Exception 13 already in progress, triggering double fault instead",
                                 "CPU_Exception: Double fault already in progress == Triple Fault. Resetting CPU."], None),
        "g3": ("0018", "0x54", ["CPU_Exception: Exception 11 already in progress, triggering double fault instead",
                                 "CPU_Exception: Double fault already in progress == Triple Fault. Resetting CPU."],
               "E_Exit: JMP Illegal descriptor type 14"),
        "g4": ("0018", "0x24", [], "E_Exit: Illegal descriptor type 1F for int D")}
for gname, (sel, byte, chain, eexit) in want.items():
    r = J(INJ / gname / "inj.json")
    assert r["selector"] == sel and r["byte"] == byte and r["injected"] == byte[2:] * 8, gname
    assert r["pre"] == {"0018": "ffffc0c5009b0000", "0070": "cf5730e0189b0000", "0080": "3f5e2048179a0000"}
    assert r["regs_at_inject"]["EIP"] == "0x42d1" and r["state"] == "battle (reach_battle.py)"
    keys = [x.split(":", 1)[1] for x in r["log_key_lines"]]
    keys = [x.split(". Only")[0] for x in keys]
    exits = [x for x in keys if x.startswith("E_Exit")]
    if chain:
        assert keys[:3] == chain + ["CMOS Shutdown byte 0x09 says to do INT 15 block move reset 0823:09db"], (gname, keys)
    assert exits == ([eexit] if eexit else []), (gname, exits)
    inj[gname] = {"selector": sel, "byte_x8": byte, "access": r["access"], "log": keys}
# g3:逐指令(HEAVYLOG,E_Exit 時寫出最後 20000 條)
h3 = (INJ / "g3/LOGCPU_INT_CD.TXT").read_text(encoding="utf-8", errors="replace").splitlines()
assert len(h3) == 20000
ds18 = [i for i, x in enumerate(h3) if x.startswith("0070:0000522F  mov  ds,dx")]
assert len(ds18) == 3                              # IRQ → #NP 處理 → 雙重錯誤處理,各一次 mov ds,0018
assert h3[ds18[-1] + 1].startswith("0C5C:00000B94  mov  ax,0823")
assert sum(x.startswith("0C5C:00000B94 ") for x in h3) == 1
cm = [i for i, x in enumerate(h3) if x.startswith("0C5C:000008CA  mov  al,0F")]
assert cm and "ds:[000010EE]=0109" in h3[cm[-1] + 3] and h3[cm[-1] + 4].startswith("0C5C:000008D3  out  71,al")
assert h3[-1].startswith("0C5C:0000032D  jmp  0018:0334")
txt3 = "".join(chr(int(re.search(r"EAX:(\w+)", x).group(1), 16) & 0xFF) for x in h3 if x.startswith("C000:000000EE"))
assert txt3 == MSG + "\r\n"
# g3 從 0C5C:0B94 起到 E_Exit 的路徑,與 v21 第一次重置後的路徑逐步相同(rep 重複的同一位址併成一步)


def path(lines: list[str]) -> list[int]:
    out: list[int] = []
    for x in lines:
        m = re.search(r"(?:^|\s)0C5C:([0-9A-F]{8})\s", x)
        if m and (not out or out[-1] != int(m.group(1), 16)):
            out.append(int(m.group(1), 16))
    return out[out.index(0xB94):]


p21, p3 = path(tr), path(h3)
assert p21[: len(p3)] == p3 and p3[-1] == 0x32D, (len(p21), len(p3))
inj["g3"]["heavylog"] = {"first_fault": "0070:522F mov ds,dx(DX = 0018)× 3:IRQ、#NP 處理、雙重錯誤處理",
                         "cmos": "0C5C:08CA~08D3 out 70,0F;out 71,[10EE] = 09 —— 關機碼 9 是 DOS/4GW 自己每次切回保護模式前寫的",
                         "printed": MSG, "last": "0C5C:032D jmp 0018:0334",
                         "same_path_as_v21_steps": len(p3)}
inj_meta = {"method": "reach_battle.py 進第 25 章戰場 → 除錯器 BP 0070:42D1(計時器 IRQ 入口)→ 刪斷點 → 確認 GDT / IDT 與五次取樣相同 → "
                      "SM 0170:<描述子線性位址> 寫 8 個相同 byte → 放開。不改 FD2.EXE、不改存檔",
            "raw": ".wsl_build/ctr/inj/g1~g4", "runs": inj,
            "g4_control": "0018 改成 0x24(call gate、不存在)時是另一個 E_Exit(IDT 0x0D 的閘被後續亂跑的程式碼弄壞),"
                          "不是「JMP Illegal descriptor type 14」—— 這句只對應型別 0x14"}

v11 = {"constraint_from_source": "E_Exit 字串只在 CPU_JMP 的 default:保護模式(非 V86)下以 JMP Ap / JMP Ep 跳到 access & 0x1f = 0x14 的描述子",
       "mechanism": "每次 0x89 當機都會走到 0C5C:032D jmp 0018:0334(五份追蹤都在第一、二次重置之間各一次);"
                    "0018 被蓋成型別 0x14 的 byte(0x14、0x34、0x54 … 0xf4)時,這一跳就是 v11 的 E_Exit",
       "reproduced": "g3:只把 0018 改成 0x54 × 8,DOSBox-X 依序記下 #NP(11)→ 雙重 → 三重 → 關機碼 0x09 → 印訊息一次 → "
                     "jmp 0018:0334 → 「E_Exit: JMP Illegal descriptor type 14」,與 v11 逐字相同",
       "verdict": "成因 LOG CONFIRMED(受控重現,路徑與 v21 逐步相同)。v11 那一次 0018 實際被寫成哪個 byte 沒有讀到(當時沒有傾印),"
                  "這一點是 INFERRED;另外 6 次取樣裡 1 次落在型別 0x14 只是與「8 / 256 個 byte 值」量級相符,不是統計檢定"}

ev = {
    "_meta": {"topic": "續七十六~七十七:續七十五的三個未驗證項目 —— 計時器 IRQ 失敗的例外種類、CMOS 關機碼、v11 E_Exit 那一支",
              "exe_md5": md5(EXE), "runs": list(RUNS),
              "generator": "evidence/generators/ev_s76.py(變異測試 mut_s76.py)",
              "raw": ".wsl_build/ctr/v21、v30~v33(v33 = 新跑,FD2_HARNESS_LOGFILE=1)、inj/g1~g4(受控注入);.wsl_build/dosbox_src_6fb8c07"},
    "A_dosbox_x_source": src_facts,
    "B_fault_class": {"runs": runs, "v33_log": log_v33},
    "C_dos16m_involuntary_switch_guard": post_reset,
    "D_guard_reentry_jmp_0018": reentry,
    "E_tools": {"tools/dosbox_harness.sh": "FD2_HARNESS_LOGFILE=1 → -set \"log logfile=<workdir>/dosbox-x.log\";"
                                          "DOSBox-X 的 LOG_MSG 會 fflush 到檔案,當機時的例外 / 重置 / E_Exit 訊息不再只在會被拆掉的除錯器面板裡",
                "tools/fd2_dosbox_live_helper.sh mem-dump": "續七十五加的模式判斷在 v33 實際擋下了實際模式下的 0170 傾印(r1.json post_dumps = error)"},
    "F_fault_injection": inj_meta,
    "G_v11_branch": v11,
    "status": {"fault_class": "LOG CONFIRMED:0x24(g1)、0x5c(g2)、0xfd(v33)三種被蓋成的值都是 Exception 13(#GP)",
               "cmos_shutdown_byte": "LOG CONFIRMED(v33、g1~g3 記錄檔 0x09,0823:09db;g3 逐指令看到 DOS/4GW 自己寫 CMOS 0x0F = 09)",
               "dos16m_guard": "LOG CONFIRMED(五份追蹤 + g3 的列印內容)",
               "v11_e_exit": "成因 LOG CONFIRMED(g3 受控重現);v11 當次 0018 的實際 byte INFERRED(沒有傾印)"},
}

def write() -> None:
    OUT.write_text(json.dumps(ev, ensure_ascii=False, indent=1) + "\n", encoding="utf-8", newline="\n")
    print("ok", OUT.name, len(OUT.read_bytes()))


if __name__ == "__main__":
    write()
