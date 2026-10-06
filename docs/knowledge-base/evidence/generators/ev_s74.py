"""續七十四證據:evidence/runaway_blit_exit_frees_fake_node_title_reload_20261003.json(續七十三的四個未驗證項目)。

A. 線性 7 = 0x89(v16):假頭像資源由 0x161e3..0x16200 以 src = res + byte[res] 直接交給 blit_rle_image 0x4ebff;
   res[0] = 0 → 寬 0、高 0xaa32 → ECX = 0 的 32 位元 loop 跑 2^32 次,第一列寫不完。DOSBox-X 結束時的狀態(v11 E_Exit、v16 INT 6 迴圈)。
B. 「離開戰場」YES 之後的每次 free(v17):AIL_shutdown 經 0x364fb 釋放 [0x538ac] 與 [0x53ed0],假標頭被當成節點,讀 [0x3f000000] = 0xffffffff。
C. 讓假節點插入真的執行(v18):S 洩漏、空閒數多 1、調色盤緩衝前 4 bytes = S;下一次 0x11d40 把它送進 DAC → 第 0 色 (227,154,125);對照組黑色。
D. 標題 CONTINUE / LOAD(v19):在 0x25ecd 改壞當下調色盤標頭,兩條路徑的第一次重載都在 0x3d67f 讀到改壞的標頭而洩漏,遊戲照常進行。
全部從 .wsl_build/ctr/v16..v19 的原始紀錄重算;任何預測不符就 assert 失敗。
"""
from __future__ import annotations

import hashlib
import json
import re
import struct
import sys
from collections import Counter
from pathlib import Path

from PIL import Image

from _evpaths import GAME, GEN_DIR, ROOT, out_path, rel, require_inputs  # noqa: E402
require_inputs(__file__)
SCR = GEN_DIR
sys.path.insert(0, str(ROOT / "tools"))
import disasm_le as D  # noqa: E402

EXE, DATO = GAME / "FD2.EXE", GAME / "DATO.DAT"
C = ROOT / ".wsl_build/ctr"
V11, V16, V17, V18, V19 = (C / f"{v}/ch25" for v in ("v11", "v16", "v17", "v18", "v19"))
OUT = out_path("runaway_blit_exit_frees_fake_node_title_reload_20261003.json")


def md5(p: Path) -> str:
    return hashlib.md5(p.read_bytes()).hexdigest()


def J(p: Path) -> dict:
    return json.loads(p.read_text(encoding="utf-8"))


assert md5(EXE) == "33464c81e6a364fd0660141139aa8e6e"
dato = DATO.read_bytes()
exe = EXE.read_bytes()
meta = D.parse_le(exe)
code, base = D.load_code(exe, meta)
md = D._capstone()


def insn(addr: int) -> str:
    """反組譯單一指令(與 disasm_le.py dis 同一套 capstone),回 'mnemonic op_str'。"""
    i = next(md.disasm(code[addr - base:addr - base + 16], addr, 1))
    return f"{i.mnemonic} {i.op_str}".strip()


def has_stop(stops: list[dict], eip: str) -> bool:
    return any(s.get("eip") == eip for s in stops)


ev: dict = {"_meta": {
    "exe": rel(EXE), "exe_md5": md5(EXE), "dato": rel(DATO), "dato_md5": md5(DATO),
    "chapter": "第 25 章戰場 = map 24(reach_battle.py + .wsl_build/FD2.SAV);v16 另套 v9_setup.py + v11_setup.py",
    "raw_dirs": [rel(p) for p in (V16, V17, V18, V19)],
    "drivers": "evidence/generators/:t_v16.py(由 mk_t_v16.py 從 t_v11.py 產生,加 blit 斷點)、t_v17.py、t_v18.py、t_v18b.py、"
               "t_v12.py(v19 戰敗回標題)、t_v19b.py、walk_after.py;本檔由 ev_s74.py 重算",
    "process": [
        "v16:t_v11 設定 4(線性 7 = 0x89)單獨跑;0x161c5 讀完假頭像後掛 0x16559 / 0x1657c / 0x4ebff / 0x4ec31 / 0x4ec0c..0x4ec48 斷點,"
        "讀到寬高後改掛每列結束 0x4ec2a / 0x4ec5e。之後模擬器不再停在任何遊戲斷點;手動 enter-debugger 兩次,面板存成 r1_halt_pane.txt / r1_end_pane.txt;"
        "此後 Alt+Pause 停不住、MEMDUMPBIN 與 D 指令都不被接受(堆積寫到哪裡因此無法傾印)。驅動記到的 eip -0x198a09(= 實際模式 0x35f7)停點本檔濾掉。",
        "v17:手動(無斷點)開系統選單 → 子選單 Down = 離開戰場 → 停在 YES / NO,再啟動 t_v17 改壞 H、下斷點、送 Left, Return。",
        "v18:w1 用預設推一下的按鍵(Return, Down, Return)120 秒內沒有自然 free(轉盤停在第三個 Return 前)→ 停住、把 H 標頭寫回 0x305、清斷點;"
        "w2 改用 Return, Escape, Return 重跑。b1 第一次攻擊:轉盤記住的是狀態項,Return 打開狀態畫面,沒有戰鬥場景(作廢);"
        "Escape ×3 後 [0x53c57] = 0,b2 把敵兵 22 搬到 (8, 43) 再 Return ×3 → 戰鬥場景。對照 c1 / c2:把調色盤前 4 bytes 寫回 0000003f、"
        "索爾 +5 清 0、敵兵 23 搬到 (6, 43),Left, Return ×3 停在目標選擇,c2 再 Return。",
        "v19:戰況記錄(Up, Up, Return, Up, Return, Left, Return, Left, Return)→ 索爾 +5 |= 1 → Escape, Return, Up, Return 開悠妮轉盤 → "
        "t_v12 d1(改壞 H)送 Down, Return;標題動畫每輪以 0x111ba 重載調色盤,驅動永遠不閒置,600 秒逾時被終止(d1.json 沒存到停點,本檔讀 d1.log 的逐行 JSON),"
        "之後手動清斷點。c1:標題上 t_v19b(自己 enter-debugger)送 Down, Down, Return。",
        "v20 作廢:戰敗回標題後 t_v19b 在標題上 enter-debugger,一次沒停住就 resume,送出的『RUN + Enter』被遊戲當成按鍵選了 START(之後 [0x53c03] = 32、名冊 0),"
        "0x25ecd 一次都沒停。改在 v19 回到戰場後先停住(戰場內 Live.halt 可靠)下好 0x25ecd 再戰敗回標題(l2,prearmed),標題上只送選單鍵。"]}}

# ================= A:線性 7 = 0x89 的假頭像 =================
r16 = J(V16 / "r1.json")
REALMODE = {"-0x198a09": "C3FF:35F7", "-0x18f59c": "F000:CA60"}  # 手動停住時的實際模式 EIP(0x35f7 / 0xca60 減 delta)
st16 = [s for s in r16["stops"] if s["eip"] not in REALMODE]
assert [s["n"] for s in r16["stops"][len(st16):]] == [69, 70, 71, 72, 73]  # 濾掉的都在尾端(手動停住時)
load = next(s for s in st16 if s["eip"] == "0x161c5" and s.get("portrait_idx") == 137)
assert load["size_53bff"] == 3654 and load["new"] == "0x26c45c" and load["blit_armed"] and load["l7_restored"] == "60ca00f00e007000"
res = dato[0x10:0x10 + 3654]
assert (V16 / load["buf_dump"]).read_bytes() == res
assert bytes.fromhex(load["res_head32"]) == res[:32]
after = st16[st16.index(load) + 1:]
assert [s["eip"] for s in after] == ["0x165ac", "0x4ebff", "0x4ec0c", "0x4ec0e", "0x4ec16"], [s["eip"] for s in after]
box, blit, s0c, s0e, s16 = after
assert (box["ret"], box["x"], box["y"], box["flag"]) == ("0x161dc", 96, 202, 0)
assert (blit["ret"], blit["dst"], blit["src"], blit["stride"]) == ("0x16205", "0xa0728", "0x26c45c", 320)
assert blit["c67"] == "0x728" and int(blit["dst"], 16) == 0xA0000 + 0x728
w, h = struct.unpack_from("<HH", res, res[0])
assert res[0] == 0 and (w, h) == (0, 0xAA32) and (s16["width_bp"], s16["height_dx"]) == (w, h)
assert s0c["esi"] == 0x26C45C and s0e["esi"] == 0x26C45E and s16["esi"] == 0x26C460 and s16["edi"] == 0xA0728
assert not has_stop(r16["stops"], "0x4ec2a") and not has_stop(r16["stops"], "0x16559")
e0 = dato[0x22A:]
assert e0[0] == 0x10 and struct.unpack_from("<HH", e0, e0[0]) == (80, 80)  # 正常頭像(DATO 第 0 條):res[0] = 0x10 → 第 0 格 80×80
static_a = {a: insn(a) for a in (0x161E3, 0x161E9, 0x161EC, 0x16200, 0x4EC16, 0x4EC1C, 0x4EC1F, 0x4EC24, 0x4EC25, 0x4EC2A)}
assert static_a[0x161E9] == "movzx eax, byte ptr [edi]" and static_a[0x161EC] == "add edi, eax"
assert static_a[0x16200] == "call 0x4ebff" and static_a[0x4EC16] == "xor ecx, ecx" and static_a[0x4EC1C] == "mov cx, bp"
assert static_a[0x4EC24].startswith("stosb") and static_a[0x4EC25] == "loop 0x4ec1f" and static_a[0x4EC2A] == "dec dx"
halt = (V16 / "r1_halt_pane.txt").read_text(encoding="utf-8")
end = (V16 / "r1_end_pane.txt").read_text(encoding="utf-8")
assert re.search(r"CS=F000\s+EIP=0000CA60", halt) and " Real" in halt and "C3FF:000035F7 63B94F4F" in halt
assert "arpl" in halt and halt.count("Illegal Unhandled Interrupt Called 6") >= 10 and "E_Exit" not in halt + end
assert end.count("Illegal Unhandled Interrupt Called 6") >= 10
regs = {k: int(v, 16) for k, v in re.findall(r"(EDI|ESI|ECX)=([0-9A-F]{8})", halt)}
crash11 = (V11 / "r1_crash_pane.txt").read_text(encoding="utf-8")
assert "E_Exit: JMP Illegal descriptor type 14" in crash11
ev["A_linear7_0x89_runaway_blit"] = {
    "load": {"stop": load["eip"], "portrait_idx": load["portrait_idx"], "size": load["size_53bff"], "buffer": load["new"],
             "buffer_equals": "DATO.DAT[0x10:0xe56]", "res_first_bytes": res[:8].hex()},
    "open_box_0x165ac": {"ret": box["ret"], "xy_flag": [box["x"], box["y"], box["flag"]], "returned": True},
    "draw_call": {"call_site": "0x16200(0x161e3 讀 [0x53a85]、0x161e9 movzx byte、0x161ec add)", "ret": blit["ret"],
                  "dst": blit["dst"], "dst_is": "0xa0000 + [0x53c67] 0x728", "src": blit["src"],
                  "src_rule": "res + byte[res];res[0] = 0 → src = res 本身", "stride": blit["stride"]},
    "header_at_0x4ec16": {"width_bp": w, "height_dx": h, "esi": hex(s16["esi"]), "edi": hex(s16["edi"])},
    "loop": "0x4ec16 xor ecx, ecx;0x4ec1c mov cx, bp(= 0);0x4ec1f..0x4ec25 call 0x4ec66 / stosb / loop 0x4ec1f —— "
            "32 位元 loop 用 ECX:0 先減成 0xffffffff,所以第一列要寫 2^32 個 byte 才結束;每列結束 0x4ec2a 的斷點一次都沒停",
    "normal_control_static": "DATO 第 0 條 res[0] = 0x10 → src = res + 0x10 = 第 0 格,寬高 (80, 80);0x89 的假資源 res[0] = 0",
    "static_insns": {hex(k): v for k, v in static_a.items()},
    "end_state_v16": {"stops_after_0x4ec16": len(after) - 1 - after.index(s16), "pane": "r1_halt_pane.txt / r1_end_pane.txt",
                      "cpu": "實際模式(Real),CS:IP F000:CA60(= 中斷向量表第 0 項 60ca00f0 那個 BIOS 預設處理常式)",
                      "code_overview": "C3FF:35F7 63 B9 4F 4F = arpl [illegal],線性 0xc75e7(視訊 BIOS 區)",
                      "output": "ERROR CPU:Illegal Unhandled Interrupt Called 6 不斷重複(INT 6 = 無效指令),模擬器沒有結束",
                      "regs_unreliable": {k: hex(v) for k, v in regs.items()},
                      "regs_note": "EDI / ESI 看似是 blit 的寫入 / 讀取指標(0x17602b / 0x2a14b3),但亂碼程式裡有 dec di,不能當寫到哪裡的證據"},
    "end_state_v11": "E_Exit: JMP Illegal descriptor type 14(DOSBox-X 本身結束,r1_crash_pane.txt)",
    "conclusion": "遊戲最後執行的是 blit_rle_image 第一列的 0x4ec1f..0x4ec25 迴圈(由 0x16200 呼叫),從 0xa0728 一路往高位址寫;"
                  "DOSBox-X 何時、以哪一條指令出事取決於寫壞了什麼:v11 以 E_Exit 結束,v16 停在實際模式的 INT 6 迴圈,不是同一條指令"}

# ================= B:離開戰場之後的每次 free =================
x1 = J(V17 / "x1.json")
pre17, s17 = x1["pre"], x1["stops"]
assert pre17["corrupt"] and pre17["H"] == "0x1fd0c0" and pre17["H_hdr"] == "0x305" and pre17["H_hdr_after_sm"] == "0x42b10"
assert pre17["pal_first4"] == "0x3f000000" and pre17["ail_seq_53ed0"] == "0x1f7018" and pre17["lib_buf_538ac"] == "0x1fa6bc"
assert pre17["known_hdrs"] == {"ail_seq_53ed0": "0x36a5", "lib_buf_538ac": "0x2005", "roster": "0xa05", "palette": "0x305"}
assert not x1["state"]["emulator_gone"] and x1["state"]["frees"] == 17
order = [s["eip"] for s in s17]
i_yes, i_main, i_ail = order.index("0x1a301"), order.index("0x25e97"), order.index("0x37ed8")
assert i_yes < i_main < i_ail and s17[i_ail]["ret0"] == "0x25e9c"
frees = [s for s in s17 if s["eip"] == "0x3d670"]
before = [s for s in frees if s["n"] < s17[i_ail]["n"]]
afterail = [s for s in frees if s["n"] > s17[i_ail]["n"]]
assert [(s["ret_game"], s["hdr"]) for s in before] == [("0x19721", "0xfa05"), ("0x1972f", "0xfa05"), ("0x1973d", "0xfa05")]
assert Counter(s["ret_game"] for s in afterail) == Counter({"0x3651d": 7, "0x3dc31": 7})
assert x1["state"]["known_freed"] == [[20, "lib_buf_538ac"], [33, "ail_seq_53ed0"]]
assert not has_stop(s17, "0x3da31") and not has_stop(s17, "0x4d021")
kn = {}
for n0, label in x1["state"]["known_freed"]:
    seq = [s for s in s17 if n0 < s["n"] <= n0 + 4 and s["eip"] != "0x3d670"]
    seq = seq[:next(i for i, s in enumerate(seq) if s["eip"] == "0x3d739") + 1]
    node = next(s for s in seq if s["eip"] == "0x3d72e")
    rd = next(s for s in seq if s["eip"] == "0x3d737")
    ad = next(s for s in seq if s["eip"] == "0x3d739")
    assert node["node_is_H"] and node["edi_h"] == "0x1fd0c0"
    assert rd["edi_h"] == "0x3f000000" and ad["eax_h"] == "0x3effffff"
    kn[label] = {"free_stop_n": n0, "path": [s["eip"] for s in seq], "freed_blk": node["esi_h"], "node": node["edi_h"],
                 "eax_at_0x3d72e": node["eax_h"], "read_[P]": "0xffffffff(0x3effffff − 0x3f000000)"}
assert kn["lib_buf_538ac"]["path"] == ["0x3d6f5", "0x3d72e", "0x3d737", "0x3d739"]
assert kn["ail_seq_53ed0"]["path"] == ["0x3d72e", "0x3d737", "0x3d739"] and kn["ail_seq_53ed0"]["eax_at_0x3d72e"] == "0x56a8"
assert 0x36A4 + 0x2004 == 0x56A8
nodes_h = [s["n"] for s in s17 if s["eip"] == "0x3d72e" and s["node_is_H"]]
assert nodes_h == [22, 34] and sum(1 for s in s17 if s["eip"] == "0x3d72e") == 17
dos = Image.open(V17 / "x1_11_-.png").convert("RGB")
dark = sum(1 for p in dos.crop((200, 220, 824, 592)).getdata() if p == (0, 0, 0)) / (624 * 372)
assert dark > 0.98
static_b = {a: insn(a) for a in (0x364FB, 0x3650A, 0x36517, 0x3651D, 0x3DA0E, 0x3DA31, 0x4CFBB, 0x4CFC5, 0x4D020, 0x4D021, 0x3776E,
                                  0x37774)}
# capstone 印的是位移欄位 0x275c;disasm_le 的 fixup 註記把它解成 obj2 的 0x5275c
assert static_b[0x36517] == "call dword ptr [0x275c]" and static_b[0x3650A] == "call 0x36683"
fx = D.build_fixups(exe, meta)
assert fx[0x36519] == 0x5275C  # 0x36517 的 ff 15 之後 2 bytes 是 fixup 位置
assert static_b[0x3DA0E] == "mov dword ptr [eax], 0xffffffff" and static_b[0x3DA31] == "call 0x3777e"
assert static_b[0x4CFBB] == "call 0x3707e" and static_b[0x4CFC5] == "je 0x4d020" and static_b[0x4D020] == "push edi"
ev["B_exit_path_frees"] = {
    "setup": {"H": "0x1fd0c0", "H_hdr": "0x305 → 0x00042b10", "P = 調色盤前 4 bytes": "0x3f000000",
              "[0x53ed0]": "0x1f7018(標頭 0x36a5)", "[0x538ac]": "0x1fa6bc(標頭 0x2005)"},
    "sequence": "YES → 0x1a301(回 −1)→ main 0x25e97 → AIL_shutdown 0x37ed8(返回 0x25e9c)→ 回 DOS",
    "frees_before_ail_shutdown": [{"ret_game": s["ret_game"], "ptr": s["ptr"], "hdr": s["hdr"]} for s in before],
    "frees_after_ail_shutdown": [{"n": s["n"], "ptr": s["ptr"], "hdr": s["hdr"], "ret_game": s["ret_game"],
                                  **({"known": s["known"]} if "known" in s else {})} for s in afterail],
    "known_blocks": kn,
    "node_is_H_stops": {"n": nodes_h, "of_0x3d72e_stops": sum(1 for s in s17 if s["eip"] == "0x3d72e"), "note": "17 次 free 只有這兩次把 H 當節點,其餘選到的都是真正的空閒區塊"},
    "ail_free_path": "0x3651d 是 0x364fb(ptr, size)裡 call [0x5275c] 的返回位址;0x364fb 先 0x36683(ptr, size)再經函式指標 [0x5275c] 呼叫 free 包裝 0x3776e",
    "library_free_call_sites": "0x3da31 / 0x4d021 都沒有停:0x3da31 是堆積擴充(0x3da0e 寫結尾標記後釋放新段的本體),"
                               "0x4d021 只在 0x4cfbb 第二次 malloc 失敗(0x4cfc5 je 0x4d020)時釋放剛配置的環境字串(靜態)",
    "static_insns": {hex(k): v for k, v in static_b.items()},
    "end": "x1_11_-.png 是 C:\\> 提示字元畫面(遊戲區 98% 以上為黑);模擬器沒有結束(state.emulator_gone = false)",
    "conclusion": "AIL_shutdown 會釋放 0x1fa6b8 與 0x1f7014 這兩塊;標頭改壞時兩次都把假標頭 H 當成空閒串列節點,"
                  "讀 [0x3f000000] 得到 0xffffffff(16 MB 以外讀到全 1,沒有錯誤),程式照常回到 DOS"}

# ================= C:假節點插入真的執行 =================
w2 = J(V18 / "w2.json")
g = w2["geo"]
assert (g["S"], g["S_hdr"], g["roster_blk"], g["H"], g["H_hdr"], g["P_pal_first4"]) == \
    ("0x1fa6b8", "0x2005", "0x1fc6bc", "0x1fd0c0", "0x305", "0x3f000000")
assert g["chain_from_53ed0"] == [["0x1f7014", "0x36a5"], ["0x1fa6b8", "0x2005"]] and g["H_hdr_set"] == "0x42b10"
assert w2["eax_after_sr"] == "0x1fa6bc"
seq = [(s["eip"], s["edi"], s["eax"]) for s in w2["stops"]]
assert [e for e, _, _ in seq] == ["0x3d6f5", "0x3d72e", "0x3d737", "0x3d739", "0x3d74d", "0x3d756", "0x3d75b", "0x3d75e", "0x3d776"]
assert seq[1][1] == "0x1fd0c0" and seq[2][1] == "0x3f000000" and seq[3][2] == "0x3effffff"
S16, H16 = bytes.fromhex(w2["after"]["S16"]), bytes.fromhex(w2["after"]["H16"])
assert struct.unpack_from("<3I", S16) == (0x2004, 0x3F000000, 0x1FD0C0)
assert struct.unpack_from("<2I", H16) == (0x42B10, 0x1FA6B8)
assert w2["after"]["ivt_0_16"].startswith("60ca00f00e007000")
sys.argv = ["walk_after.py", str(V18 / "w2_heap_after.bin"), str(V18 / "w2_desc2.bin"), "1fa6b8", "1fd0c0", "1fd3c4"]
import io  # noqa: E402
import contextlib  # noqa: E402
buf = io.StringIO()
with contextlib.redirect_stdout(buf):
    exec(compile((SCR / "walk_after.py").read_text(encoding="utf-8"), "walk_after.py", "exec"), {"__name__": "walk"})
walk = json.loads(buf.getvalue())
assert walk["closed"] and walk["nodes"] == 23 and walk["numfree_desc_18"] == 24 and not walk["bad_back_links"]
assert walk["contains"] == {"0x1fa6b8": False, "0x1fd0c0": False, "0x1fd3c4": True} and walk["desc_c"] == "0x2004"


def dac8(v6: int) -> int:
    return (v6 << 2) | (v6 >> 4)


pred0 = tuple(dac8(b & 0x3F) for b in bytes.fromhex("b8a61f"))
assert pred0 == (227, 154, 125)
b2, c2 = J(V18 / "b2.json"), J(V18 / "c2.json")
assert b2["pre"]["pal8"] == "b8a61f003c273f33" and c2["pre"]["pal8"] == "0000003f3c273f33"
for run in (b2, c2):
    assert [(s["ret"], s["first"], s["last"], s["darken"]) for s in run["stops"]] == \
        [("0x1f510", 0, 255, 0), ("0x1f510", 0, 255, 1), ("0x1f510", 0, 255, 2)]
    assert all(s["pal_ptr"] == "0x1fd0c4" for s in run["stops"])


def colors(p: Path) -> Counter:
    return Counter(Image.open(p).convert("RGB").crop((200, 208, 824, 592)).getdata())


cb, cc = colors(V18 / "b2_02_Return.png"), colors(V18 / "c2_00_Return.png")
assert cb.most_common(1)[0][0] == pred0 and cb[pred0] > 30000  # 黑色仍有(其他調色盤項目也是黑),第 0 色的大背景變成橘粉色
assert cc.most_common(1)[0][0] == (0, 0, 0) and cc[pred0] == 0  # 對照幀在淡出中,整體偏暗;第 0 色黑、橘粉色 0 點


def px(name: str) -> tuple:
    return Image.open(V18 / name).convert("RGB").getpixel((194, 400))  # 遊戲畫面左側外框 = DAC 第 0 色


border = {"b2_00_Return.png(改壞的緩衝上傳之前)": px("b2_00_Return.png"), "c1_00_Left.png(改壞的緩衝上傳之後)": px("c1_00_Left.png"),
          "c2_hit1.png(寫回 0000003f、上傳之前)": px("c2_hit1.png"), "c2_05_-.png(寫回後的緩衝上傳之後)": px("c2_05_-.png")}
assert list(border.values()) == [(0, 0, 0), pred0, pred0, (0, 0, 0)]
static_c = {a: insn(a) for a in (0x3D72E, 0x3D733, 0x3D737, 0x3D74D, 0x3D750, 0x3D753, 0x3D756, 0x3D75B, 0x11D8D, 0x11D9A, 0x1F50B)}
assert static_c[0x3D756] == "mov dword ptr [edi + 8], esi" and static_c[0x3D75B] == "mov dword ptr [edi + 4], esi"
assert static_c[0x1F50B] == "call 0x11d40" and static_c[0x11D9A] == "push 0x3c9"
ev["C_fake_node_insert_executed"] = {
    "setup": {"S": "0x1fa6b8(標頭 0x2005)", "roster_blk": "0x1fc6bc", "H": "0x1fd0c0(0x305 → 0x00042b10)", "P": "0x3f000000",
              "forced": f"自然 free 的 EAX {w2['natural_eax']}(標頭 {w2['natural_hdr']})換成 0x1fa6bc;那一塊因此洩漏"},
    "path": [{"eip": e, "edi": d, "eax": a} for e, d, a in seq],
    "writes": {"[S]": "0x2004(清掉使用中位元)", "[S+4]": "0x3f000000(P)", "[S+8]": "0x1fd0c0(H)", "[H+4]": "0x1fa6b8(S)",
               "[P+8] = [0x3f000008]": "16 MB 以外,寫入無效(中斷向量表前 16 bytes 不變)"},
    "free_list_after": {k: walk[k] for k in ("nodes", "numfree_desc_18", "closed", "contains", "desc_c")},
    "free_list_meaning": "真正的空閒串列仍是 23 個節點、首尾相接;S 標成空閒卻不在串列裡(8196 bytes 洩漏),描述的空閒數 24 多算 1,"
                         "+0xc 的最大空閒提示變成 0x2004",
    "palette_upload": {"function": "0x11d40(first, last, darken):outp 0x3c8 / 0x3c9,把 [0x53a65] 的 RGB 減 darken 後送進 DAC",
                       "call": "0x1f50b(返回 0x1f510),戰鬥場景開始時 darken 0、1、2 ...",
                       "corrupted_buffer_first8": b2["pre"]["pal8"], "control_buffer_first8": c2["pre"]["pal8"],
                       "predicted_color0": list(pred0), "predicted_rule": "DAC 只留低 6 位:0xb8→0x38、0xa6→0x26、0x1f;8 位顯示 = v<<2 | v>>4",
                       "b2_02_Return.png": {"most_common": list(cb.most_common(1)[0][0]), "count": cb[pred0], "black": cb[(0, 0, 0)]},
                       "c2_00_Return.png(對照)": {"most_common": list(cc.most_common(1)[0][0]), "count_black": cc[(0, 0, 0)], "count_pred0": cc[pred0]},
                       "map_border_pixel_194_400": {k: list(v) for k, v in border.items()},
                       "border_note": "地圖外框是 DAC 第 0 色:改壞的緩衝上傳後變橘粉色並一直留著;把緩衝寫回 0000003f 後,下一次上傳(c2 的戰鬥場景)才變回黑色"},
    "static_insns": {hex(k): v for k, v in static_c.items()},
    "conclusion": "假節點插入照常完成、不會當掉:S 洩漏、空閒數多 1、調色盤緩衝前 4 bytes 被寫成 S 的位址;"
                  "下一次 0x11d40 上傳時第 0 色變成 (227, 154, 125)、第 1 色的 R 變成 0,戰鬥場景原本黑色的背景變成橘粉色"}

# ================= D:標題 CONTINUE / LOAD =================
d1 = []
for line in (V19 / "d1.log").read_text(encoding="utf-8").splitlines():
    if line.startswith("{"):
        try:
            d1.append(json.loads(line))
        except json.JSONDecodeError:
            pass
title = next(s for s in d1 if s["eip"] == "0x25ebb")
assert title["ret"] == "0x25dc2" and title["pal"] == "0x1fd0c4"
leak = next(s for s in d1 if s["eip"] == "0x111ba" and s.get("ret") == "0x1f90f")
nxt = d1[d1.index(leak) + 1:d1.index(leak) + 4]
assert leak["old_hdr"] == "102b0400" and [s["eip"] for s in nxt] == ["0x3d67f", "0x111d5", "0x1f912"]
assert nxt[0]["hdr"] == "102b0400" and nxt[2]["new_pal"] == "0x207c30"
healthy = next(s for s in d1 if s["eip"] == "0x111ba" and s.get("ret") == "0x1f982")
hn = d1[d1.index(healthy) + 1:d1.index(healthy) + 7]
assert [s["eip"] for s in hn] == ["0x3d67f", "0x3d685", "0x3d693", "0x3d72e", "0x111d5", "0x1f985"] and hn[0]["hdr"] == "05030000"
rows = {}
for tag, choice, ret_load, writer, new in (("c1", 2, "0x1013b", "0x1013e", "0x20fc38"), ("l2", 1, "0x25f79", "0x25f7c", "0x22841c")):
    run = J(V19 / f"{tag}.json")
    s = run["stops"]
    assert s[0]["eip"] == "0x25ecd" and s[0]["choice_eax"] == choice
    assert s[0]["pal_hdr_before"] == "05030000" and s[0]["pal_hdr_after"] == "102b0400"
    i = next(k for k, x in enumerate(s) if x["eip"] == "0x111ba" and x.get("armed"))
    assert s[i]["ret"] == ret_load and s[i]["old"] == s[0]["pal"] and s[i]["old_hdr"] == "102b0400" and s[i]["res_idx"] == 0
    assert [x["eip"] for x in s[i + 1:i + 4]] == ["0x3d67f", "0x111d5", writer]
    assert s[i + 1]["is_watch"] and s[i + 1]["hdr"] == "102b0400" and s[i + 2]["watch_hdr_after"] == "102b0400"
    assert s[i + 3]["new_pal"] == new and s[i + 3]["new_pal_hdr"] == "05030000" and s[i + 3]["old_blk_hdr_now"] == "102b0400"
    assert not has_stop(s, "0x3d685") and not run["state"]["emulator_gone"]
    rows[tag] = {"choice_eax": choice, "pal_at_0x25ecd": s[0]["pal"], "hdr": "05030000 → 102b0400",
                 "before_reload": [{"eip": x["eip"], **({"ret": x["ret"]} if "ret" in x else {})} for x in s[1:i]],
                 "reload_free": {"ret": ret_load, "path": ["0x3d67f(讀到 102b0400)", "0x111d5"], "no_0x3d685": True},
                 "new_palette": {"writer": writer, "addr": new}, "after": [{"eip": x["eip"], **({"ret": x["ret"]} if "ret" in x else {})}
                                                                           for x in s[i + 4:]]}
assert rows["c1"]["before_reload"] == [{"eip": "0x26130", "ret": "-0x19c000"}, {"eip": "0x10010", "ret": "0x26135"}]
assert rows["l2"]["before_reload"] == [{"eip": "0x111ba", "ret": "0x25f5a"}] and rows["l2"]["after"] == [{"eip": "0x29bcb", "ret": "0x2601e"}]
c_end = Image.open(V19 / "c1_08_-.png").convert("RGB")
l_end = Image.open(V19 / "n_04_-.png").convert("RGB")
assert colors(V19 / "c1_08_-.png").most_common(1)[0][0] == (105, 73, 36)  # 戰場岩地,與 v18 b2 戰前畫面相同的主色
static_d = {a: insn(a) for a in (0x25EC8, 0x25ECD, 0x25F74, 0x25F7C, 0x26130, 0x10136, 0x1013E)}
assert static_d[0x25ECD] == "test eax, eax" and static_d[0x25F74] == "call 0x111ba" and static_d[0x10136] == "call 0x111ba"
ev["D_title_continue_load"] = {
    "carried_from_battle(v19 d1)": {"title_ret": "0x25dc2", "leak_free": "0x111ba 返回 0x1f90f(i = 76),0x3d67f 讀到 102b0400 → 0x111d5,沒有 0x3d685;新調色盤 0x207c30",
                                   "healthy_control_same_run": "下一次(返回 0x1f982,標頭 05030000)走 0x3d67f → 0x3d685 → 0x3d693 → 0x3d72e,真的釋放",
                                   "note": "與續七十三 v15 相同:戰場上改壞的標頭在標題序列 0x1f90a 那次就洩漏,輪不到 CONTINUE / LOAD"},
    "title_animation": "標題畫面每一輪都以 0x111ba 重載調色盤(i = 101 / 102 交替,返回 0x1fbeb / 0x1fc21)並 free 舊區塊;"
                       "在標題上改壞的標頭會先被這裡吃掉,所以改在 0x25ecd(標題序列返回、EAX = 選項)才改",
    "CONTINUE(c1)": rows["c1"], "LOAD(l2)": rows["l2"],
    "screens": {"c1_08_-.png": "回到戰況記錄當時的戰場(索爾在原位、游標停在記錄時的空格),色彩正常",
                "l2 / n_04_-.png": "選槽清單 → 『要記錄戰況嗎?』→ NO → 出戰人數選擇畫面,色彩正常"},
    "static_insns": {hex(k): v for k, v in static_d.items()},
    "conclusion": "CONTINUE(0x26130 → 0x10010 → 0x10136)與 LOAD(0x25f74)的第一次調色盤重載,舊區塊標頭被改壞時都在 0x3d67f 判定未使用而直接返回:"
                  "舊區塊洩漏、新調色盤配到別處,遊戲照常進行;和讀取戰況(續七十二 v10b)、標題序列(續七十三 v15)同一個結果"}

ev["not_covered"] = [
    "v11 的 E_Exit 是哪一條模擬指令觸發的:v16 同樣的條件以 INT 6 迴圈收場,而且之後除錯器停不住,記憶體傾印也不被接受,寫到哪裡沒有量到。",
    "CONTINUE / LOAD 沒有另跑標頭完好的對照;完好標頭走 0x3d685 的路徑以同一輪 d1 的標題重載(返回 0x1f982)為對照。",
    "AIL_shutdown 之後回 DOS 的假節點寫入只在結束時發生,後果只看到『沒有當掉』。"]
OUT.write_text(json.dumps(ev, ensure_ascii=False, indent=1) + "\n", encoding="utf-8", newline="\n")
print("ok", OUT.name, len(OUT.read_bytes()))
