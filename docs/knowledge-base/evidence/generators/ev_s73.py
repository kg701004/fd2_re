"""續七十三證據:evidence/speaker_lookup_title_palette_heap_walk_20261002.json(續七十二的五個未驗證項目)。

A. v9b 第二次觸發的索爾頭像:v11 把索爾 +7 由 32 改 20 → 狀態畫面與 0x1967e 都載入 20、亂碼畫面變成頭像 20(翻轉);
   v9b 自己沒有斷點,以 f1 的操作順序與左下區域像素對 v10a / v11 的相似度歸到 0x1967e。
B. 說話者查找 0x12c60 的分支與線性 7:v11 同一個敵方回合 5 次(名冊重複 id、戰場上陣亡單位、兩邊都沒有 × 線性 7 = 原值 / 0x4b / 0x89),
   v14 單獨 1 次(線性 7 = 0xf0)。
C. 標題 0x25ebb 路徑:v15 調色盤標頭改壞 → 索爾陣亡 → 戰敗回標題 → 新遊戲;v12 離開戰場 → DOS(不經標題)。
D. free 往後走訪:v12 堆積排列快照(geo1)+ 強制把一次自然 free 的指標換成 S = 0x1fa6b8(f0 對照、f1 改壞),停在 0x3d72e 後撤銷。
全部從 .wsl_build/ctr/v9b、v10a、v11、v12、v14、v15 的原始紀錄與傾印重算;任何預測不符就 assert 失敗。
"""
from __future__ import annotations

import glob
import hashlib
import json
import struct
import sys
from pathlib import Path

from PIL import Image, ImageChops

from _evpaths import GAME, GEN_DIR, ROOT, out_path, rel, require_inputs  # noqa: E402
require_inputs(__file__)
SCR = GEN_DIR
sys.path.insert(0, str(SCR))
import dato_match as DM  # noqa: E402

EXE, DATO = GAME / "FD2.EXE", GAME / "DATO.DAT"
C = ROOT / ".wsl_build/ctr"
V9B, V10A, V11, V12, V13, V14, V15 = (C / f"{v}/ch25" for v in ("v9b", "v10a", "v11", "v12", "v13", "v14", "v15"))
OUT = out_path("speaker_lookup_title_palette_heap_walk_20261002.json")
DELTA = 0x19C000


def md5(p: Path) -> str:
    return hashlib.md5(p.read_bytes()).hexdigest()


def J(p: Path) -> dict:
    return json.loads(p.read_text(encoding="utf-8"))


assert md5(EXE) == "33464c81e6a364fd0660141139aa8e6e"
assert DATO.read_bytes() == DM.DATO
ev: dict = {"_meta": {
    "exe": rel(EXE), "exe_md5": md5(EXE), "dato": rel(DATO), "dato_md5": md5(DATO),
    "chapter": "第 25 章戰場 = map 24(reach_battle.py + .wsl_build/FD2.SAV md5 e6d9a357…);v11 / v14 另套 v9_setup.py + v11_setup.py",
    "raw_dirs": [rel(p) for p in (V11, V12, V13, V14, V15)],
    "drivers": "evidence/generators/:t_v11.py(v11、v14)、v11_setup.py、t_v12.py(v12 離開戰場、v13、v15)、t_v12f.py(v12 強制 free)、"
               "heap_geom.py / heap_geom_off.py(v12 堆積快照)、dato_match.py、rel32_callers.py;本檔由 ev_s73.py 重算",
    "process": [
        "v11:k = 4(線性 7 = 0x89)開框動畫返回後 DOSBox-X 以 'E_Exit: JMP Illegal descriptor type 14' 結束(r1_crash_pane.txt,轉錄);"
        "驅動之後讀到的全 0 紀錄(eip -0x19c000)本檔濾掉。k = 5(0xf0)改在 v14 單獨跑。",
        "v12:先做 heap_geom(第一次 geo0 用未檢查的 enter-debugger,停在 DOS 呼叫裡,描述讀到全 0,作廢;geo1 用 Live.halt() 重跑),"
        "再做強制 free f0 / f1,最後『離開戰場』p1。f0 第一次等了 120 秒沒有自然 free(只按方向鍵),改按『轉盤 → Down → Return』才觸發。",
        "v13:驅動 p1 的按鍵沒完成待機,手動中止並清斷點時遊戲已戰敗回標題,標題流程沒有斷點 → 只做事後堆積檢查(posthoc_title.txt),"
        "斷點歸因改由 v15 重跑。",
        "v15:先手動(無斷點)Escape、Return、Down、Return、Down 讓悠妮停在待機前,再啟動 t_v12 改壞標頭、下斷點,送最後的 Return。"],
    "dato_duplicates": None}}
groups: dict[bytes, list[int]] = {}
for i, e in enumerate(DM.ENTS):
    groups.setdefault(e, []).append(i)
ev["_meta"]["dato_duplicates"] = [v for v in groups.values() if len(v) > 1]


def full_match(p: Path) -> list[int]:
    return DM.match(p.read_bytes(), DM.ENTS)


# ================= A:v9b 的索爾頭像 =================
r11 = J(V11 / "r1.json")
s11 = [s for s in r11["stops"] if s["eip"] != "-0x19c000"]
assert len(s11) == 129 and s11[-1]["n"] == 128
plan = r11["plan"]
assert plan["sol_plus7_before"] == 32 and plan["sol_plus7_after"] == 20
w11 = [s for s in s11 if s["eip"] in ("0x17f30", "0x1967e") and s["n"] < 50]
assert [(s["eip"], s["portrait_idx"], s["c67"]) for s in w11] == [("0x17f30", 20, "0xc88"), ("0x1967e", 20, "0x9017")]
for s in w11:
    assert full_match(V11 / s["buf_dump"]) == [20]
g0 = next(s for s in s11 if s["eip"] == "0x15f84" and s.get("idx") == 11 and s.get("k") == 0)
assert g0["0x53c67"] == "0x9017" and full_match(V11 / g0["a85_dump"]) == [20]
a10 = J(V10A / "a2.json")["stops"]
w10 = [(s["eip"], s["portrait_idx"], s["c67"]) for s in a10 if s["eip"] in ("0x17f30", "0x1967e") and s["n"] < 50]
assert w10 == [("0x17f30", 32, "0xc88"), ("0x1967e", 32, "0x9017")]
f1 = J(V9B / "f1.json")
f1_steps = [(i, st["key"], [x["eip"] for x in st["stops"]]) for i, st in enumerate(f1) if st["stops"]]
assert f1_steps[-3:][0][0] == 30 and f1_steps[-2][0] == 34 and "0x34531" in f1_steps[-2][2]
assert any(x.get("ret") == "0x18a2b" and x.get("esi") == plan_ub for st in [f1[24]] for x in st["stops"]
           for plan_ub in [int(plan["ubase"], 16)])


def crop(p: str) -> Image.Image:
    return Image.open(p).convert("RGB").crop((200, 420, 380, 600))


def same(a: Image.Image, b: Image.Image) -> float:
    d = ImageChops.difference(a, b).convert("L").tobytes()
    return sum(1 for x in d if x == 0) / len(d)


pix = {}
for f in ("f1_34_-.png", "f1_35_-.png"):
    a = crop(str(V9B / f))
    b10 = max((same(a, crop(g)), Path(g).name) for g in glob.glob(str(V10A / "a2_g0_*.png")))
    b11 = max((same(a, crop(g)), Path(g).name) for g in glob.glob(str(V11 / "r1_g0_*.png")))
    pix[f] = {"best_v10a_k0_sol32": [round(b10[0], 4), b10[1]], "best_v11_k0_portrait20": [round(b11[0], 4), b11[1]]}
    assert b10[0] > 0.95 and b11[0] < 0.5, pix[f]
ev["A_v9b_portrait_source"] = {
    "question": "續七十二仍未驗證:v9b 第二次觸發(f1)亂碼畫面左下角鏡像的索爾,是哪一次載入的",
    "v9b_f1_sequence": {"steps_with_stops": f1_steps,
                        "reading": "第 24 步 Return 時 0x12cea 以索爾紀錄(ESI = 單位 0)返回 0x18a2b;f1_26~29 截圖是索爾的狀態畫面,"
                                   "第 33 步截圖是對龍人戰士施放的戰鬥場景(MP 805 → 781),第 34 步在單位 0 的分派檢查觸發事件 0。"
                                   "與 v10a a2 前 5 個 Return 的順序相同(狀態畫面 → 聖光彈 → 敵方回合)"},
    "v10a_writers_before_trigger": w10,
    "v11_flip": {"sol_plus7": [plan["sol_plus7_before"], plan["sol_plus7_after"]], "writers_before_trigger": [(s["eip"], s["portrait_idx"], s["c67"]) for s in w11],
                 "garble_entry": {"n": g0["n"], "0x53c67": g0["0x53c67"], "a85_buf_match": full_match(V11 / g0["a85_dump"])},
                 "screen": "r1_g0_054.png:亂碼畫面左下角是頭像 20(綠髮女性),不是索爾"},
    "v9b_pixel_similarity_lower_left": pix,
    "conclusion": "亂碼畫面的頭像是『索爾行動後 open_dialog_box 0x1967e 依單位 +7 載入、[0x53c67] = 0x9017』留下的:"
                  "v11 把 +7 改成 20,0x17f30 與 0x1967e 都跟著載入 20,亂碼畫面就變成頭像 20(DOSBox-X)。"
                  "v9b 當時沒有斷 [0x53a85],它的操作順序與 v10a / v11 相同,左下區域與 v10a k=0(索爾 32)像素 98.7% 相同、"
                  "與 v11 k=0(頭像 20)只有 27.9% → 同一個來源(推論:v9b 本身沒有寫入點停點)"}

# ================= B:說話者查找與線性 7 =================
by_k: dict[int, list[dict]] = {}
cur = None
for s in s11:
    if "trigger_k" in s:
        cur = s["trigger_k"]
    if cur is not None:
        by_k.setdefault(cur, []).append(s)
assert sorted(by_k) == [0, 1, 2, 3, 4] and r11["state"]["trig_units"] == [48, 49, 50, 51, 52]
rp = int(plan["roster_ptr"], 16)
added = plan["roster_added"]
assert [(r["char_id"], r["+7"], tuple(r["xy"])) for r in added] == [(2, 10, (5, 40)), (2, 11, (6, 41)), (3, 12, (7, 42))]
X, Z, A, U = plan["X"], plan["Z"], plan["A"], plan["U"]
assert (X, Z, A) == (2, 3, 5) and all(x not in plan["battle_ids"] + plan["roster_ids"] for x in (X, Z, A))
ivt = bytes.fromhex(plan["ivt_0_8"])
assert ivt.hex() == "60ca00f00e007000"


def line3(seg: list[dict]) -> dict:
    i0 = next(i for i, s in enumerate(seg) if s["eip"] == "0x15f84" and s.get("idx") == 3)
    out = {"patched": seg[i0]["patched"], "ivt_at_patch": seg[i0]["ivt_0_8"]}
    for s in seg[i0 + 1:]:
        e = s["eip"]
        if e == "0x16188":
            out["lookup_ret"], out["c1b_is"] = s["lookup_ret"], s["c1b_is"]
            out["c1b_rec16"] = s.get("c1b_rec16")
        elif e == "0x161b1":
            out["portrait_idx_ebp"], out["ivt_at_161b1"] = s["portrait_idx_ebp"], s["ivt_0_8"]
        elif e == "0x111ba" and s.get("ret") == "0x161c2":
            out["load"] = {"file": s["file"], "res_idx": s["res_idx"]}
        elif e == "0x161c5":
            out["writer"] = {"portrait_idx": s["portrait_idx"], "size": s["size_53bff"], "buf": s.get("buf_dump"),
                             "l7_restored": s.get("l7_restored")}
        elif e == "0x165ac":
            out["box"] = [s["x"], s["y"], s["flag"]]
        elif e == "0x164ac" and s.get("idx") == 3:
            out["line_end"] = s["n"]
            break
    return out


L3 = {k: line3(v) for k, v in by_k.items()}
# k0:名冊兩筆同 id → 後一筆(index 17、+7 = 11、(6, 41))勝出;「第一筆」對手預測 10、(5, 40)
k0 = L3[0]
assert k0["patched"] == {"mode": "roster_dup", "char_id": X, "l7": None}
assert k0["lookup_ret"] == -1 and k0["c1b_is"] == ["roster", 17] and k0["portrait_idx_ebp"] == 11
assert k0["load"] == {"file": "0x51a70", "res_idx": 11} and k0["box"] == [6, 41, 0]
assert full_match(V11 / k0["writer"]["buf"]) == [11] and 11 != added[0]["+7"]
# k1:戰場單位 U 改成 id Z、+5 bit0、+7 13;名冊也有 Z(+7 12)→ 預測 [0x53c1b] = U、頭像 13、開框 U 的座標
k1 = L3[1]
assert k1["patched"] == {"mode": "dead_battlefield", "char_id": Z, "l7": None}
assert k1["lookup_ret"] == -1 and k1["c1b_is"] == ["unit", U] and U == 61
rec = bytes.fromhex(k1["c1b_rec16"])
assert rec[5] & 1 and rec[7] == 13 and rec[8] == Z and list(rec[:2]) == plan["U_before"]["xy"] == [10, 7]
assert k1["portrait_idx_ebp"] == 13 and k1["box"] == [10, 7, 0] and full_match(V11 / k1["writer"]["buf"]) == [13]
u_rest = next(s for s in by_k[1] if s["eip"] == "0x164ac" and s.get("idx") == 3)["U_restored"]
assert bytes.fromhex(u_rest)[5] == 0 and bytes.fromhex(u_rest)[7:9] == bytes([125, 125])
# k2..k4:兩邊都沒有 → [0x53c1b] = 0,頭像 = 線性 7、座標 = 線性 0 / 1
exp_l7 = {2: 0x00, 3: 0x4B, 4: 0x89}
for k, v in exp_l7.items():
    o = L3[k]
    assert o["patched"]["char_id"] == A and o["lookup_ret"] == -1 and o["c1b_is"] == ["other", 0]
    assert bytes.fromhex(o["ivt_at_161b1"])[7] == v and o["portrait_idx_ebp"] == v and o["load"]["res_idx"] == v
    assert o["box"] == [ivt[0], ivt[1], 0] == [96, 202, 0]
    if k in (3, 4):
        assert o["writer"]["l7_restored"] == "60ca00f00e007000"
assert full_match(V11 / L3[2]["writer"]["buf"]) == [0] and full_match(V11 / L3[3]["writer"]["buf"]) == [75]
b137 = (V11 / L3[4]["writer"]["buf"]).read_bytes()
off = struct.unpack_from("<2I", DM.DATO, 6 + 4 * 0x89)
assert off == (0x10, 0xE56) and L3[4]["writer"]["size"] == 3654 == off[1] - off[0] and b137 == DM.DATO[0x10:0xE56]
assert "line_end" not in L3[4] and L3[2].get("line_end") and L3[3].get("line_end")
crash = (V11 / "r1_crash_pane.txt").read_text(encoding="utf-8")
assert "E_Exit: JMP Illegal descriptor type 14" in crash
# v14:線性 7 = 0xf0 → 大小為負 → 0x1125e
r14 = J(V14 / "r1.json")
s14 = r14["stops"]
assert r14["plan"]["ivt_0_8"] == "60ca00f00e007000" and r14["state"]["oom"] and r14["state"]["trig_units"] == [48]
p14 = next(s for s in s14 if s["eip"] == "0x15f84" and s.get("idx") == 3)
assert p14["patched"] == {"mode": "absent_l7", "char_id": r14["plan"]["A"], "l7": 0xF0}
eb = next(s for s in s14 if s["eip"] == "0x161b1")
ld = next(s for s in s14 if s["eip"] == "0x111ba" and s.get("ret") == "0x161c2")
oom = next(s for s in s14 if s["eip"] == "0x1125e")
offf = struct.unpack_from("<2I", DM.DATO, 6 + 4 * 0xF0)
assert eb["portrait_idx_ebp"] == 240 == ld["res_idx"] and oom["size_53bff"] == (offf[1] - offf[0]) & 0xFFFFFFFF == 4277993295
assert not any(s["eip"] == "0x161c5" for s in s14 if s["n"] > ld["n"])
ev["B_speaker_lookup_and_linear7"] = {
    "static": "0x12c60:先清 [0x53c1b],掃戰場 +8 == id 就把 [0x53c1b] 設成那筆,0x34894(索引)(= +5 & 1)為 0 才回索引,否則繼續掃;"
              "掃完 [0x53c1b] 仍是 0 才掃名冊,而且掃到底(最後一筆同 id 勝出);沒回索引就回 -1。dialog 0x16174..0x161dc:回 -1 → 旗標 0;"
              "id ≠ 0x27 時頭像 = [[0x53c1b] + 7],座標 = [[0x53c1b] + 0 / + 1] → 0x165ac(x, y, 旗標)",
    "setup": {"roster_added": added, "X_Z_A": [X, Z, A], "U": U, "U_before": plan["U_before"],
              "ivt_0_8": plan["ivt_0_8"], "roster_count": [plan["roster_count_before"], plan["roster_count_after"]]},
    "v11_line3": {str(k): v for k, v in L3.items()},
    "k0_rival": "若是第一筆同 id 勝出,會載入 10、開框 (5, 40);實測 11、(6, 41)",
    "k1_rival": "若陣亡的戰場單位不算、改掃名冊,會載入 12、開框 (7, 42);實測 13、(10, 7) = U 的座標",
    "k4_dato_offsets": {"entry_0x89": [hex(x) for x in off], "loaded": "DATO.DAT[0x10:0xe56](3654 bytes,逐 byte 相同)= 偏移表後段 0x10..0x22a(538 bytes)+ 第 0 條開頭 3116 bytes;第 0x89 個「偏移」位在 0x22a,其實是第 0 條資料的前 8 bytes(0x10、0xe56)",
                        "after": "0x165ac(96, 202, 0) 返回後、第 3 條結束前,DOSBox-X 以 'E_Exit: JMP Illegal descriptor type 14' 結束"
                                 "(r1_crash_pane.txt);確切在哪一條指令沒有定位"},
    "v14_f0": {"patched": p14["patched"], "portrait_idx_ebp": eb["portrait_idx_ebp"], "entry_0xf0_offsets": [hex(x) for x in offf],
               "size_53bff": oom["size_53bff"], "size_signed": oom["size_53bff"] - (1 << 32),
               "screen": "r1_oom_060.png:圖形畫面左上印出『Out of Memory at Load DATO.DAT Number:240!!』,接著是 C:\\> 提示字元"},
    "conclusion": "名冊重複 id → 最後一筆;戰場上同 id 但已陣亡(+5 bit0)→ 用那筆戰場紀錄、不看名冊,回 -1、旗標 0;"
                  "兩邊都沒有 → 讀線性 7 / 0 / 1。線性 7 = 0x4b 就載入頭像 75(證明讀的是線性 7);"
                  "0x89 把偏移表後段 + 第 0 條開頭當頭像載入,之後模擬器結束;0xf0 算出的大小為負 → 印 Out of Memory 結束程式(DOSBox-X)"}

# ================= C:標題 0x25ebb 路徑 =================
p15 = J(V15 / "p1.json")
assert p15["corrupt"] and p15["pre"]["pal"] == "0x1fd0c4" and p15["pre"]["pal_hdr_after_sm"] == "102b0400"
st = p15["stops"]
seq = [(s["eip"], s.get("ret"), s.get("res_idx")) for s in st[:9]]
assert seq[0] == ("0x111ba", "0x22e90", 79) and seq[2] == ("0x25ebb", "0x25dc2", None) and seq[3][0] == "0x1f894"
assert st[2]["pal"] == "0x1fd0c4"
first = st[5]
assert first["eip"] == "0x111ba" and first["ret"] == "0x1f90f" and first["old"] == "0x1fd0c4" and first["old_hdr"] == "102b0400"
assert [s["eip"] for s in st[6:9]] == ["0x3d67f", "0x111d5", "0x1f912"]
assert st[6]["hdr"] == "102b0400" and st[6]["blk"] == "0x1fd0c0" and st[8]["new_pal"] == "0x207c30"
watched = []
i = 0
while i < len(st):
    s = st[i]
    if s.get("armed"):
        j = next(j for j in range(i + 1, len(st)) if st[j]["eip"] == "0x111d5")
        path = [x["eip"] for x in st[i + 1:j]]
        watched.append({"n": s["n"], "ret": s["ret"], "old": s["old"], "old_hdr": s["old_hdr"], "path": path,
                        "real_free": "0x3d685" in path})
        i = j
    i += 1
assert len(watched) == 6 and not watched[0]["real_free"] and all(w["real_free"] for w in watched[1:])
assert all(w["old"] == "0x207c30" and w["old_hdr"] == "05030000" for w in watched[1:])
ng = next(s for s in st if s.get("ret") == "0x25ef2")
assert ng["old"] == "0x207c30" and ng["res_idx"] == 0 and ng["key_i"] == 5
ng_w = next(s for s in st if s["eip"] == "0x25ef5")
assert ng_w["new_pal"] == "0x207c30"
p12 = J(V12 / "p1.json")
assert p12["corrupt"] and p12["stops"] == []
ev["C_title_path"] = {
    "static": "main 0x25bf4:0x25db1 起 call 0x25ebb(標題 / 讀檔 / 繼續的分流)→ 0x25dce call 0x117e7(戰場迴圈),回傳 0 再進戰場、"
              "-1 → 結束程式(0x25e97 AIL_shutdown …)、其他值 → 回 0x25db1 再進 0x25ebb。[0x53ecc] == 1 時先 0x22e5c(FDOTHER #79)再當成 1。"
              "0x25ebb 只有這一個呼叫端(位元組掃描 rel32);它內含 [0x53a65] 的 0x25ef5(新遊戲)、0x25f7c(讀檔),"
              "標題序列 0x1f894 內含 0x1f77a … 0x1fce4 共 11 處;0x26130(CONTINUE)呼叫 0x10010。"
              "離開戰場 YES:0x1a301 mov eax, -1 → 戰場迴圈回 -1 → 結束程式,不經標題",
    "v12_leave_battle": "標頭改壞後『離開戰場 → YES』:斷點 0x111ba / 0x25ebb / 0x1f894 / 13 個調色盤寫入點 0 次停;"
                        "p1_01 起畫面是 DOS 提示字元 C:\\>(程式結束,沒有當掉)",
    "v15_defeat": {"pre": p15["pre"], "first_stops": seq,
                   "watched_palette_frees": watched,
                   "new_game_reload": {"ret": ng["ret"], "old": ng["old"], "res_idx": ng["res_idx"], "new_pal": ng_w["new_pal"]},
                   "screens": "p1_04_-.png 標題(START / LOAD / CONTINUE)、p1_05_Return.png 之後新遊戲的城堡序章,色彩正常"},
    "v13_posthoc": (V13 / "posthoc_title.txt").read_text(encoding="utf-8"),
    "conclusion": "戰敗(索爾陣亡)回標題時,標題序列第一次重新載入調色盤(0x1f90a,i = 76)就 free 那塊改壞的區塊:"
                  "0x3d67f 讀到 102b0400 → 不經 0x3d685 直接返回 → 洩漏;新調色盤配到 0x207c30,之後 5 次 free 都真的釋放,"
                  "新遊戲的 0x25eed 也照常。和 v10b 讀取戰況(0x10010)的結果相同(DOSBox-X)"}

# ================= D:free 往後走訪 =================
heap = (V12 / "geo1_heap.bin").read_bytes()
R0 = 0x1E0000
desc = struct.unpack("<16I", (V12 / "geo1_desc.bin").read_bytes())
gl = (V12 / "geo1_globals.bin").read_bytes()


def u32(a: int) -> int:
    return struct.unpack_from("<I", heap, a - R0)[0]


head = 0x527B0 + DELTA + 0x1C
nodes, p = [], desc[9]
while p != head:
    assert p not in nodes and u32(p) & 1 == 0
    nodes.append(p)
    p = u32(p + 8)
assert len(nodes) == desc[6] == 23
H = 0x1FD0C0
before = sorted(x for x in nodes if x < H)
assert before == [0x1F6C88, 0x1F6E38]
a = 0x1F6E38
while u32(a) != 0xFFFFFFFF:
    a += u32(a) & ~1
assert a == 0x1F6FF8
chain, a = [], 0x1F7014
while a <= H:
    chain.append((a, u32(a)))
    a += u32(a) & ~1
N = a
assert [(hex(x), hex(h)) for x, h in chain] == [("0x1f7014", "0x36a5"), ("0x1fa6b8", "0x2005"), ("0x1fc6bc", "0xa05"),
                                                ("0x1fd0c0", "0x305")]
assert N == 0x1FD3C4 and N in nodes


def owners(v: int) -> list[str]:
    return [hex(0x53A00 + i) for i in range(len(gl) - 3) if struct.unpack_from("<I", gl, i)[0] == v]


own = {hex(b): owners(b + 4) for b, _ in chain} | {hex(N): owners(N + 4)}
assert own == {"0x1f7014": ["0x53ed0"], "0x1fa6b8": [], "0x1fc6bc": ["0x53bf7"], "0x1fd0c0": ["0x53a65"],
               "0x1fd3c4": ["0x53a18"]}
ptr_1fa6bc = [hex(R0 + i) for i in range(len(heap) - 3) if struct.unpack_from("<I", heap, i)[0] == 0x1FA6BC]
assert ptr_1fa6bc[0] == "0x1ef8ac" and 0x1EF8AC - DELTA == 0x538AC


def walk_limit(numalloc: int, numfree: int) -> int:
    """0x3d6d8..0x3d6f3 的計數(逐指令照抄);0 表示 dec 後回捲成 2^32 - 1,等於不設上限。"""
    ecx = numfree + 1
    eax = numalloc // ecx
    ecx -= 1
    if eax >= ecx:
        return -1  # jae 0x3d70d:不走訪
    edx = numalloc - ecx
    eax += eax
    if not edx > ecx:
        eax = 0
    return eax


f0, f1x = J(V12 / "f0.json"), J(V12 / "f1.json")
res_f = {}
for nm, f, exp in (("f0_control", f0, "N"), ("f1_corrupt", f1x, "H")):
    g = f["geo"]
    assert g["S"] == "0x1fa6b8" and g["H"] == "0x1fd0c0" and g["N"] == "0x1fd3c4" and g["H_hdr"] == "0x305"
    assert g["H_hdr_set"] == ("0x305" if exp == "N" else "0x42b10")
    assert f["eax_after_sr"] == "0x1fa6bc"
    eips = [s["eip"] for s in f["stops"]]
    assert eips == ["0x3d68b", "0x3d6f5", "0x3d72e"]
    assert f["stops"][0]["edi"] == "0x1fc6bc"  # 下一塊 = 名冊區塊(使用中)→ 不合併
    assert f["stops"][1]["eax"] == "0x0" and walk_limit(g["numalloc_14"], g["numfree_18"]) == 0
    last = f["stops"][2]
    assert last["edi_is"] == exp and last["eip_after_sr"] == "0x3d776" and last["S_hdr_restored"] == "0x2005"
    passed = (1 << 32) - int(last["eax"], 16)
    assert passed == (2 if exp == "N" else 1)
    assert f["H_hdr_final"] == "0x305" and f["S_hdr_final"] == "0x2005"
    res_f[nm] = {"geo": g, "natural_eax_skipped": f["natural_eax"], "stops": f["stops"], "in_use_blocks_passed": passed}
ev["D_free_forward_walk"] = {
    "static": "heap_free_block 0x3d670(ebx 固定 = 0x527b0 描述):標頭最低位 0 → 返回;否則清掉最低位,下一塊空閒就合併(0x3d68b);"
              "否則用 rover [ebx+8] 與首 / 尾節點判斷能不能直接插入,不能才走 0x3d6d8:計數 = 依 [ebx+0x14] / [ebx+0x18] 算出"
              "(本輪兩次都是 0,dec 後回捲 = 不設上限),從被釋放的區塊往後逐塊跳過最低位 1 的區塊,"
              "第一個最低位 0 的區塊就當成空閒串列節點(0x3d72e),讀它的 +4 當前一節點並寫 [前一節點 + 8] = 被釋放的區塊。"
              "走訪只往後,所以只有位址在假標頭之前、而且中間沒有真正空閒區塊的區塊被釋放時才會走到它;"
              "名冊區塊緊接在它前面,但名冊從不被 free(續七十二),所以合併那一支走不到",
    "v12_geometry_geo1": {"free_nodes": len(nodes), "numfree": desc[6], "free_nodes_before_H": [hex(x) for x in before],
                          "their_segment_end_marker": "0x1f6ff8(0xffffffff)",
                          "segment_chain_to_H": [(hex(x), hex(h)) for x, h in chain], "next_after_H": hex(N),
                          "owners_byte_scan_0x53a00_0x54000": own,
                          "pointer_to_0x1fa6bc_in_heap_dump": ptr_1fa6bc[:4],
                          "owner_code": {"0x53ed0": "0x25c26 開機時存入(AIL 音樂序列控制代碼,之後只傳給 AIL 函式)",
                                         "0x538ac": "函式庫程式 0x49770 存入(0x2000 bytes 的緩衝區)"},
                          "candidates": "0x1f7014 與 0x1fa6b8:位址在 H 之前、同一段、中間沒有空閒區塊 —— 只有它們被釋放時走訪會先遇到 H"},
    "free_call_sites": "[0x53ed0] 的 9 處參照(指令 0x17380、0x259aa、0x259d2、0x25a1e、0x25a2c、0x25a55、0x25a74、0x25a86、0x25c26)只傳給 AIL 函式或存入;"
                       "[0x538ac] 只有指令 0x49770(存入)、0x4977d(讀出);沒有一處傳給 free。0x3777e 另有函式庫內的 0x3da31、0x4d021,0x3d670 只有 0x37794",
    "forced": res_f,
    "conclusion": "把一次自然 free 的指標換成 0x1fa6b8:H 標頭完好時走訪越過名冊與 H 兩個使用中區塊,停在真正的空閒區塊 0x1fd3c4;"
                  "H 改成 0x00042b10 時只越過名冊就停在 H,把假標頭當成空閒串列節點(DOSBox-X,停在 0x3d72e 後撤銷,沒有讓它寫入)。"
                  "所以假標頭只會被 0x1f7014 / 0x1fa6b8 的釋放走到;遊戲碼不會釋放它們,函式庫會不會(例如結束時)沒有確認"}

ev["not_covered"] = [
    "0x89 之後 DOSBox-X 結束的確切指令(推論:把錯位的資料當頭像影格,0x161e3 起的貼圖或之後的逐字動畫讀到錯的位移)",
    "函式庫 free(0x3da31、0x4d021)與 AIL_shutdown 會不會釋放 0x1f7014 / 0x1fa6b8;v12 改壞標頭後離開戰場回到 DOS 沒有當掉,但那次沒有斷 free",
    "假標頭被當成節點之後真正寫入 [前一節點 + 8] 的結果(本輪在 0x3d72e 撤銷,沒有讓它發生)",
    "標題的 CONTINUE(0x26130 → 0x10010)與 LOAD(0x25f7c)兩條沒有在改壞標頭的狀態下實測;它們同樣經 0x111ba 的 free(靜態)",
    "v9b 本身沒有 [0x53a85] 寫入點停點(只能以順序與像素歸因)"]
OUT.write_text(json.dumps(ev, ensure_ascii=False, indent=1) + "\n", encoding="utf-8", newline="\n")
print("ok", OUT.name, len(OUT.read_bytes()))
