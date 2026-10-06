"""存檔:原 scratchpad 驅動腳本,路徑保留當時的工作環境,不保證能直接執行(見 README.md)。

地形修正動態驗證的證據 JSON 與登錄表更新(doc98 續五十)。"""
import json
import struct
from pathlib import Path

ROOT = Path(r"C:\Users\kg701\Desktop\GAME\fd2_re")
OUT = ROOT / "docs" / "data" / "function_names.json"
EVI = ROOT / "docs" / "knowledge-base" / "evidence" / "terrain_modifier_20260929.json"
D = ROOT / ".wsl_build" / "ctr"
W = 27
A = [5, 0, -5, -5, -5, 0]
B = [0, 0, 10, 10, -5, 0]

cells = (D / "t_map.bin").read_bytes()
tt = (D / "t_tt.bin").read_bytes()
mods = (D / "t_mods.bin").read_bytes()
assert [struct.unpack_from("<i", mods, 4 * k)[0] for k in range(6)] == A
assert [struct.unpack_from("<i", mods, 0x18 + 4 * k)[0] for k in range(6)] == B


def ttype(x: int, y: int) -> int:
    tile = struct.unpack_from("<H", cells, 4 + 4 * (y * W + x))[0] & 0x3FF
    return tt[tile * 4 + 1]


def gated(r: bytes) -> bool:
    """unit_uses_move_cost_row19 的靜態規則。"""
    if r[7] == 0x1C:
        return False
    return r[0x20] == 0x13 or r[0x1F] in (4, 5)


def tdiv(a: int, b: int) -> int:
    """idiv:向零截斷。"""
    q = abs(a) // abs(b)
    return q if (a >= 0) == (b > 0) else -q


# 斷點讀值抄錄自本次終端輸出:None = 該斷點沒有觸發
bp = {
    "T1": (5, 0, 13), "T2": (None, 0, 9), "T3": (5, 10, 4), "T4": (5, None, 13),
    "T5": (-5, 0, 9), "T6": (None, 0, 13), "T7": (-5, 0, 9),
}
cases = []
for tag, (bap, bdp, bdmg) in bp.items():
    pre = (D / f"pre_{tag}.bin").read_bytes()
    post = (D / f"post_{tag}.bin").read_bytes()
    a, d = pre[0:80], pre[11 * 80:12 * 80]
    w = lambda r, o: struct.unpack_from("<H", r, o)[0]
    ap, dp = w(a, 0x48), w(d, 0x4A)
    ta, td = ttype(a[0], a[1]), ttype(d[0], d[1])
    apm = None if gated(a) else tdiv(ap * A[ta], 100)
    dpm = None if gated(d) else tdiv(dp * B[td], 100)
    dmg = max(0, ((ap + (apm or 0)) - (dp + (dpm or 0))) * 9 // 10)
    assert dmg < 18  # 亂數項為 0
    hp_drop = w(d, 0x40) - w(post[11 * 80:12 * 80], 0x40)
    floor_ap = None if apm is None else (ap * A[ta]) // 100
    rec = {
        "case": tag,
        "attacker": {"xy": [a[0], a[1]], "terrain_type": ta, "race": a[0x1F], "class": a[0x20], "plus7": a[7], "ap": ap, "gated": gated(a)},
        "defender": {"xy": [d[0], d[1]], "terrain_type": td, "race": d[0x1F], "class": d[0x20], "plus7": d[7], "dp": dp, "gated": gated(d)},
        "predicted": {"ap_mod": apm, "dp_mod": dpm, "damage": dmg},
        "breakpoints": {"ap_mod_0x2f8dc": bap, "dp_mod_0x2f921": bdp, "damage_0x2f9fc": bdmg},
        "defender_hp_drop": hp_drop,
        "floor_division_would_give_ap_mod": floor_ap,
    }
    assert (apm, dpm, dmg) == (bap, bdp, bdmg) and hp_drop == dmg, rec
    cases.append(rec)
assert cases[4]["floor_division_would_give_ap_mod"] == -6
EVI.write_bytes((json.dumps({
    "note": "DOSBox-X 記憶體傾印與斷點讀值整理;FD2.EXE md5 33464c81e6a364fd0660141139aa8e6e。地形類型 = 地形表 [0x53a69] 第 tile 列的 byte 1"
            "(tile = 地圖格 [0x53a51] 的 u16 & 0x3ff);AP/DP 修正表執行期讀回 [5,0,-5,-5,-5,0] / [0,0,10,10,-5,0]。"
            "predicted 依 scene_attack_resolve 0x2f89a..0x2f921 與 unit_uses_move_cost_row19 的靜態規則計算;null = 該修正被跳過。",
    "cases": cases,
}, ensure_ascii=False, indent=1) + "\n").encode("utf-8"))
print("evidence ok", [(c["case"], c["predicted"]["damage"]) for c in cases])

raw = OUT.read_bytes()
assert b"\r" not in raw
doc = json.loads(raw.decode("utf-8"))
ADD = {
    "0x1f183": (
        " 2026-09-29 DOSBox-X 動態驗證(doc98 續五十,在 scene_attack_resolve 的地形修正閘門上):種族 1 修正照做、種族 5 跳過、"
        "職業 0x13(種族 1)跳過、+7 = 0x1c(種族 5)照做,攻守兩方各自判定。種族 4 未測。"
    ),
    "0x12e38": (
        " out[5](地形表列的 byte 1)是地形類型 0..5,scene_attack_resolve 以它索引 [0x51a12]/[0x51a2a];"
        "DOSBox-X(doc98 續五十)讀第 1 章地圖只出現 0、1、2 三種,三種都實測過修正值。"
    ),
    "0x2f7b6": (
        "地形修正(續五十):攻方 AP += AP × [0x51a12][t] / 100、守方 DP += DP × [0x51a2a][t] / 100,t = map_cell_info 的 out[5],"
        "idiv 向零截斷;unit_uses_move_cost_row19 為真的一方不修正。DOSBox-X 斷點 0x2f8dc/0x2f921/0x2f9fc 實測 7 擊全部符合:"
        "修正值 +5/0、跳過/0、+5/+10、+5/跳過、-5/0(餘數 -50,向下取整會是 -6)、跳過/0(職業 0x13)、-5/0(+7 = 0x1c),傷害 13/9/4/13/9/13/9。"
    ),
}
EV = {
    "0x1f183": [("0x1f1c3", "mov eax, 1")],
    "0x12e38": [],
    "0x2f7b6": [("0x2f8bf", "movzx eax, byte ptr [esp + 5]"), ("0x2f8da", "idiv ecx"), ("0x2f909", "mov edx, dword ptr [eax*4 + 0x1a2a]")],
}
n = 0
for x in doc["names"]:
    if x["addr"] in ADD:
        assert "續五十" not in x["summary"]
        x["summary"] += ADD[x["addr"]]
        for a, i in EV[x["addr"]]:
            x["evidence"].append({"at": a, "insn": i})
        if x["addr"] == "0x1f183":
            assert x["confidence"] == "static_re"
            x["confidence"] = "verified_dynamic"
        n += 1
assert n == 3
OUT.write_bytes((json.dumps(doc, ensure_ascii=False, indent=1) + "\n").encode("utf-8"))
print("total", len(doc["names"]))
