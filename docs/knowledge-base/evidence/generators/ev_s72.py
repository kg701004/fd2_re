"""續七十二證據:evidence/garble_portrait_heap_null_speaker_20261002.json(續七十一的三個未驗證項目)。

A. 亂碼畫面的頭像:v10a 同一個敵方回合觸發事件 0 三次(k=0 自然、k=1 入口把 [0x53c67] 改 0x9017、k=2 入口把 arg8 改 0)。
B. 調色盤區塊標頭被改壞後的釋放 / 重新配置:v10b 讀取戰況三次(c0 對照、c1 先把標頭改成 0x00042b10、c2 不改)。
C. 0xFFEF 的說話者不在戰場也不在名冊:v10a k=2 把第 3 條的開框碼改成 0xFFEF、運算元 = 沒有任何紀錄使用的角色 id。
全部從 .wsl_build/ctr/v10a、v10b 的原始紀錄與傾印重算;任何預測不符就 assert 失敗。
"""
from __future__ import annotations

import hashlib
import json
import struct
import sys
from collections import Counter
from pathlib import Path

from _evpaths import GAME, GEN_DIR, ROOT, out_path, require_inputs  # noqa: E402
require_inputs(__file__)
SCR = GEN_DIR
sys.path.insert(0, str(SCR))
import dato_match as DM  # noqa: E402

EXE, DATO = GAME / "FD2.EXE", GAME / "DATO.DAT"
A_, B_ = ROOT / ".wsl_build/ctr/v10a/ch25", ROOT / ".wsl_build/ctr/v10b/ch25"
OUT = out_path("garble_portrait_heap_null_speaker_20261002.json")


def md5(p: Path) -> str:
    return hashlib.md5(p.read_bytes()).hexdigest()


assert md5(EXE) == "33464c81e6a364fd0660141139aa8e6e"
assert DATO.read_bytes() == DM.DATO, "dato_match 讀的 DATO.DAT 與倉庫內的不同"
ev: dict = {"_meta": {
    "exe": str(EXE.relative_to(ROOT)), "exe_md5": md5(EXE), "dato": str(DATO.relative_to(ROOT)), "dato_md5": md5(DATO),
    "chapter": "第 25 章戰場 = map 24(reach_battle.py + .wsl_build/FD2.SAV md5 e6d9a357…;v10a 另套 v9_setup.py,同續七十一)",
    "raw_dirs": [".wsl_build/ctr/v10a/ch25", ".wsl_build/ctr/v10b/ch25"],
    "drivers": "evidence/generators/:t_v10a.py / t_v10b.py / dato_match.py(本檔由 ev_s72.py 從原始紀錄重算)",
    "dato_layout": "6 bytes 'LLLLLL' + 137 個 dword 偏移 → 136 條;0x111ba(檔名, old, i) = free(old)、讀第 i 條整段進 malloc 的緩衝區",
    "dato_duplicates": None}}
groups: dict[bytes, list[int]] = {}
for i, e in enumerate(DM.ENTS):
    groups.setdefault(e, []).append(i)
ev["_meta"]["dato_duplicates"] = [v for v in groups.values() if len(v) > 1]
assert len(DM.ENTS) == 136

# ---------------- A / C:v10a ----------------
a = json.loads((A_ / "a2.json").read_text(encoding="utf-8"))
stops = a["stops"]
assert a["state"]["trig_units"] == [48, 49, 50] and a["state"]["done"]
by_n = {s["n"]: s for s in stops}


def dump_match(name: str) -> list[int]:
    return DM.match_prefix((A_ / name).read_bytes(), DM.ENTS)


writers = []
for s in stops:
    if s["eip"] in ("0x17f30", "0x1967e", "0x161c5", "0x162aa", "0x163d7", "0x16453", "0x28f5e", "0x2967f", "0x31ff5"):
        b = (A_ / s["buf_dump"]).read_bytes()
        writers.append({"n": s["n"], "store_at": s["eip"], "portrait_idx": s["portrait_idx"], "new": s["new"],
                        "c67_after": s["c67"], "dump_len": len(b), "entry_len": len(DM.ENTS[s["portrait_idx"]]),
                        "buf_dato": dump_match(s["buf_dump"]), "buf_dato_full_match": DM.match(b, DM.ENTS)})
# 每次寫入的緩衝區 = DATO 第 portrait_idx 條(重複條目一起列)
for w in writers:
    assert w["portrait_idx"] in w["buf_dato"], w
units = (A_ / "a2_ids_units.bin").read_bytes()
u7 = {i: units[i * 0x50 + 7] for i in (0, 16)}
assert u7 == {0: 32, 16: 26}, u7

trig = []
for k in range(3):
    t = next(s for s in stops if s.get("trigger_k") == k)
    g = next(s for s in stops if s["eip"] == "0x15f84" and s.get("idx") == 11 and s["k"] == k)
    gend = next(s for s in stops if s["eip"] == "0x164ac" and s.get("idx") == 11 and s["k"] == k)
    first559 = [s for s in stops if s["eip"] == "0x16559" and s.get("in_garble") and s["k"] == k]
    trig.append({
        "k": k, "unit": t["unit"], "garble_entry_n": g["n"], "control": g["control"],
        "entry_0x53a85": g["0x53a85"], "entry_0x53c67": g["0x53c67"], "c67_after_control": g["after_c67"],
        "arg8_after_control": g["after_arg8"], "a85_buffer_dato": dump_match(g["a85_dump"]),
        "0x16559_during_garble": gend["a559_hits_during_garble"],
        "first_0x16559": ({kk: first559[0][kk] for kk in ("ret", "frame", "a85", "c67")} if first559 else None),
        "garble_end_shot": f"a2_{gend['n']:03d}_164ac.png"})
# 預測:k=0 頭像 = 回合結束時 open_dialog_box(0x1967e)載入的 32、位置 0x9017;k=1、k=2 = k=0 第 3 條載入的 26
assert trig[0]["a85_buffer_dato"] == [32, 50] and trig[0]["entry_0x53c67"] == "0x9017"
assert trig[1]["a85_buffer_dato"] == [26] and trig[1]["entry_0x53c67"] == "0x0" and trig[1]["c67_after_control"] == "0x9017"
assert trig[2]["a85_buffer_dato"] == [26] and trig[2]["arg8_after_control"] == 0
assert trig[0]["first_0x16559"]["ret"] == trig[1]["first_0x16559"]["ret"] == "0x1652f"
assert trig[0]["first_0x16559"]["c67"] == trig[1]["first_0x16559"]["c67"] == "0x9017"
assert trig[2]["0x16559_during_garble"] == 0 and trig[2]["first_0x16559"] is None
idx3_loads = [s for s in stops if s["eip"] == "0x163d7"]
assert [s["portrait_idx"] for s in idx3_loads] == [26, 26]

ev["A_garble_portrait"] = {
    "static": {
        "per_glyph": "0x1647f 畫完一個字模後:[esp+0x58](arg8)≠0 就 call 0x164e8(typewriter_tick);0x10620 偵測到按鍵就把 arg8 清 0",
        "tick": "0x164e8 每 2 次推進 [0x53a10] 並 call 0x16559(影格) —— 把 [0x53a85] 頭像資源的那一格畫到 0xa0000 + [0x53c67];[0x53c67] == 0x9017 時改用鏡像版 0x4ec31",
        "no_box_reset": "0x15f84 入口不設定 [0x53c67] / [0x53a85];只有開框碼(0x16174 等)會設,結束時 [esp+0x18] ≠ 0(開過框)才把 [0x53c67] 清 0(0x164d7)",
        "a85_writers": "0x161c5 / 0x162aa / 0x163d7 / 0x16453(dialog 開框)、0x17f30(單位狀態畫面,[0x53c67] = 0xc88)、0x1967e(open_dialog_box,依 res_idx 0x80..0x84 設 [0x53c67] = 0x10bb / 0x6ab / 0xf63 / 0x576 / 0xe3c,其他值 0x9017)、0x28f5e、0x2967f、0x31ff5;全部經 0x111ba(0x51a70 'DATO.DAT', old, i)",
        "event0_args": "事件 0 呼叫 dialog 時 arg8 = 1(rest 最後一項)"},
    "writers_seen_v10a": writers,
    "unit_plus7": {"unit0_索爾": u7[0], "unit16_第3條說話者": u7[16]},
    "triggers": trig,
    "screens": {"k0": "a2_g0_054.png(左下鏡像的索爾 32)", "k1": "a2_g1_114.png(左下鏡像的龍 26)",
                "k2": "a2_092_164ac.png(沒有頭像)",
                "earlier": "v8/ch25 j1_dlg_a.png、v9a t1_40_-.png:入口 [0x53c67] = 0(v9a 紀錄),頭像在左上角"},
    "conclusion": "頭像不是對白檔或字碼流畫的,是 dialog 逐字動畫(arg8 = 1)每兩個字模重貼一次的「目前頭像資源」[0x53a85];"
                  "內容是最後一次載入頭像的那個畫面留下的,位置是最後一次設定的 [0x53c67]。"}

# ---------------- C:k=2 第 3 條 ----------------
i3 = next(s for s in stops if s["eip"] == "0x15f84" and s.get("idx") == 3 and s["k"] == 2)
spk = next(s for s in stops if s["eip"] == "0x16188" and s["n"] > i3["n"])
por = next(s for s in stops if s["eip"] == "0x161b1" and s["n"] > i3["n"])
ld = next(s for s in stops if s["eip"] == "0x111ba" and s["n"] > i3["n"] and s["ret"] == "0x161c2")
st5 = next(s for s in stops if s["eip"] == "0x161c5" and s["n"] > i3["n"])
box = next(s for s in stops if s["eip"] == "0x165ac" and s["n"] > i3["n"])
ivt = bytes.fromhex(i3["ivt_0_8"])
absent = i3["patched"]["char_id"]
assert absent not in i3["battle_ids"] and absent not in i3["roster_ids"] and absent != 0x27
assert spk["lookup_ret"] == -1 and spk["c1b"] == "0x0"
assert por["portrait_idx_ebp"] == ivt[7] == ld["res_idx"] == st5["portrait_idx"] == 0
assert (box["x"], box["y"], box["flag"]) == (ivt[0], ivt[1], 0)
assert dump_match(st5["buf_dump"]) == [0] and DM.match(( A_ / st5["buf_dump"]).read_bytes(), DM.ENTS) == [0]
k1_3 = next(s for s in stops if s["eip"] == "0x15f84" and s.get("idx") == 3 and s["k"] == 1)
ev["C_null_speaker"] = {
    "static": "0x16183 call 0x12c60(id) 回 -1 → 旗標 0;id ≠ 0x27 時 edi = [0x53c1b]、頭像 = byte [edi+7](0x161ad),"
              "開框座標 = byte [edi]、[edi+1](0x161ce / 0x161d3)",
    "patch": {"open_before": i3["open_before"], "open_after": i3["open_after"], "char_id": absent,
              "battle_ids": sorted(set(i3["battle_ids"])), "roster_ids": i3["roster_ids"]},
    "lookup": {"ret": spk["lookup_ret"], "0x53c1b": spk["c1b"]},
    "linear_0_8": i3["ivt_0_8"],
    "linear_0_8_meaning": "DOS 中斷向量表:int0 = F000:CA60、int1 = 0070:000E;byte 7 = int1 段址的高位 0x00(DOSBox-X 的值,實機 DOS 可能不同)",
    "portrait_idx": por["portrait_idx_ebp"], "loader": {"ret": ld["ret"], "res_idx": ld["res_idx"], "size_0x53bff": st5["size_53bff"],
                                                         "len_DATO_000": len(DM.ENTS[0]), "buf_dato_full_match": [0]},
    "box_anim": {"x": box["x"], "y": box["y"], "flag": box["flag"], "cursor": box["cursor"]},
    "screen": "a2_s007_pre_Return.png:頂端開框,頭像是 DATO_000(doc01:索爾),台詞照常顯示,鏡頭沒動,遊戲沒有當掉",
    "roster_branch_control": {"attempted_k1": k1_3.get("patched"), "reason": "名冊 18 筆的 id 全都在戰場上,沒有只在名冊的角色;驅動照設計不改碼,第 3 條走原本的 0xFFED",
                              "not_done": "未另外改名冊紀錄 +8 重做;k=0/k=1 的第 3 條走 0xFFED(單位索引)分支、不經 0x12c60,不能當這一支的對照"},
    "conclusion": "說話者不在戰場也不在名冊時 [0x53c1b] = 0,頭像索引與開框座標從線性位址 7、0、1 讀;在 DOSBox-X 是 0 → 載入 DATO 第 0 條,不會當掉。"
                  "線性 7 的值若 ≥ 136,0x111ba 會把檔頭外的資料當偏移(靜態:DATO 第 0xF0 條的『大小』= -16974001),走到「Out of Memory at Load」(0x500fc)— 未實測。"}
D = DM.DATO
a_, c_ = struct.unpack_from("<ii", D, 6 + 4 * 0xF0)
ev["C_null_speaker"]["static_idx_0xF0_size"] = c_ - a_

# ---------------- B:v10b ----------------
runs = {}
for tag in ("c0", "c1", "c2"):
    d = json.loads((B_ / f"{tag}.json").read_text(encoding="utf-8"))
    st = d["stops"]
    pal_old = int(d["pre"]["pal"], 16)
    hdr = int(d["pre"]["roster"], 16) + 0xA00
    frees = [s for s in st if s["eip"] == "0x3d67f"]
    real = [s for s in st if s["eip"] == "0x3d685"]
    runs[tag] = {
        "corrupt": d["corrupt"], "pre": {k: d["pre"][k] for k in ("roster", "pal", "hdr_after_roster", "count")},
        "after_sm_hdr": d["after_sm"]["hdr_after_roster"],
        "post": {k: d["post"][k] for k in ("pal", "pal_hdr", "hdr_after_roster")},
        "palette_load": [{"n": s["n"], "old": s["old"], "res_idx": s["res_idx"]} for s in st
                         if s["eip"] == "0x111ba" and s["ret"] == "0x1013b"],
        "free_palette_block": [{"n": s["n"], "hdr": s["hdr"]} for s in frees if int(s["blk"], 16) + 4 == pal_old],
        "real_free_palette_block": [s["n"] for s in real if int(s["blk"], 16) + 4 == pal_old],
        "new_pal": [s["new_pal"] for s in st if s["eip"] == "0x1013e"],
        "frees_total": len(frees), "real_frees_total": len(real),
        "walk_or_merge_node_is_after_roster": [s["n"] for s in st if s["eip"] in ("0x3d72e", "0x3d693")
                                               and int(s["node"], 16) == hdr],
        "stop_counts": dict(Counter(s["eip"] for s in st)), "shot": f"{tag}_09_-.png"}
r0, r1, r2 = runs["c0"], runs["c1"], runs["c2"]
assert r0["free_palette_block"][0]["hdr"] == "05030000" and r0["real_free_palette_block"] and r0["new_pal"] == [r0["pre"]["pal"]]
assert r1["after_sm_hdr"] == "102b0400" and r1["free_palette_block"][0]["hdr"] == "102b0400"
assert r1["real_free_palette_block"] == [] and r1["new_pal"] != [r1["pre"]["pal"]]
assert r0["frees_total"] == r1["frees_total"] == 117 and r0["real_frees_total"] - r1["real_frees_total"] == 1
assert r2["pre"]["pal"] == r1["new_pal"][0] and r2["real_free_palette_block"] and r2["new_pal"] == [r2["pre"]["pal"]]
assert r2["post"]["hdr_after_roster"] == "102b0400"
assert all(r["walk_or_merge_node_is_after_roster"] == [] for r in runs.values())
from PIL import Image, ImageChops  # noqa: E402
diff01 = ImageChops.difference(Image.open(B_ / "c0_09_-.png").convert("RGB"), Image.open(B_ / "c1_09_-.png").convert("RGB")).getbbox()
assert diff01 is None
ev["B_corrupt_header_free"] = {
    "static": {
        "nfree": "free 0x3776e → 0x3777e → 0x3d670:esi = ptr-4;`test al,1; je 0x3d66b`(0x3d681)—— 標頭最低位是 0 就直接返回,不釋放",
        "merge_and_walk": "真的釋放時,0x3d68b 看下一塊標頭最低位是 0 就合併並用它的 +4 / +8 當串列指標解鏈;0x3d6f5 起往後走過使用中的區塊,遇到最低位 0 的就當空閒串列節點(0x3d72e)",
        "reloaders": "[0x53a65] 有 16 處寫入:13 處是 0x111ba(0x51a4d 'FDOTHER.DAT', old, i)的回傳 —— 0x1013e(0x10010 內)、"
                     "0x1f77a / 0x1f7de / 0x1f85a / 0x1f912 / 0x1f985 / 0x1f9e7 / 0x1fb27 / 0x1fbee / 0x1fc24 / 0x1fce4、0x25ef5 / 0x25f7c;"
                     "另 3 處 0x31afa / 0x31b5c / 0x31b7f 是轉職演出暫時換掉再還原,不經 free。0x10010 的呼叫端是 battle_system_submenu(0x19df7,讀取戰況)與 0x25ebb",
        "roster_never_freed": "對 [0x53bf7] 的 27 處參照沒有任何一處把它傳給 free(0x3776e)"},
    "header_value": "0x00042b10 = 續七十一 v9b 戰後寫回把單位 4 的 +0..+3 複製到名冊第 32 筆後的實測值;本輪以 SM 寫入",
    "runs": runs, "c0_vs_c1_screen_bbox": diff01,
    "conclusion": "標頭被改壞後,下一次重新載入調色盤(每場戰鬥開始、讀取戰況)時 free 直接返回:舊區塊永久洩漏(標頭維持 0x00042b10),"
                  "新調色盤配到別處(0x207c30),畫面正常;之後的重新載入照常在新位址釋放、重配。三次讀檔 351 次 free 都沒有把那個假的空閒區塊當串列節點或合併對象。"}
ev["_meta"]["v10a_process"] = (
    "第一次驅動 a1 開頭送 Return、Down、Return,停在索爾的狀態畫面,之後每個 Return 都重開狀態畫面(紀錄 a1_aborted.log),中止;"
    "手動 BPDEL *、Escape×3 回地圖、Return 開圈、SM [0x53c57] = 3,再跑 a2。a2 的前 5 個 Return:第 2 個之後 0x17f30(狀態畫面,頭像 32),"
    "之後索爾進入戰鬥場景(a2_s004_pre_Return.png,MP 805 → 781),第 5 個之後 0x1967e(頭像 32、[0x53c67] = 0x9017),然後進入敵方回合。"
    "所以 k=0 的 [0x53a85] / [0x53c67] 是索爾那次行動之後的框留下的,不是『回合結束』的框;[0x53c57] = 3 並沒有讓 Return 直接待機。")
b_prompt = [s for s in json.loads((B_ / "c0.json").read_text(encoding="utf-8"))["stops"]
            if s["eip"] == "0x111ba" and s["ret"] == "0x1967b"]
assert [s["res_idx"] for s in b_prompt] == [75]
ev["A_garble_portrait"]["battle_state_prompt_portrait"] = {
    "v10b_c0_open_dialog_box_load": {"n": b_prompt[0]["n"], "ret": "0x1967b", "res_idx": 75},
    "save_prompt_screen": ".wsl_build/ctr/v10b/ch25/m_06_Return.png(記錄戰況提示框,頭像不是索爾)",
    "consequence": "續七十一 v9b 第二次觸發的索爾頭像不是記錄戰況提示框留下的;來源未確認"}
ev["_meta"]["not_covered"] = ("B 只驗證戰場初始化這條路徑(讀取戰況 → 0x10010);0x25ebb(標題 / 新遊戲)沒有實測。"
                              "free 的往後走訪只在本輪的堆積排列下沒有碰到,不代表其他排列也碰不到。C 的線性 7 是 DOSBox-X 的中斷向量表內容。")
OUT.write_text(json.dumps(ev, ensure_ascii=False, indent=1) + "\n", encoding="utf-8", newline="\n")
print("ok", OUT.name, len(OUT.read_bytes()))
