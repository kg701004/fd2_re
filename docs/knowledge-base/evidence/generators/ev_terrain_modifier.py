"""地形修正動態驗證的證據 JSON 與登錄表更新(doc98 續五十)。"""
# 移植說明:原腳本後段是一次性更新 docs/data/function_names.json 的補丁(已套用並提交),不屬於證據重算,移植時刪除。
import json
import re
import struct
from pathlib import Path

from _evpaths import GAME, GEN_DIR, ROOT, out_path, require_inputs  # noqa: E402,F401
require_inputs(__file__)
import _console  # noqa: E402
EVI = out_path("terrain_modifier_20260929.json")
D = ROOT / ".wsl_build" / "ctr"
# 地形規則與修正表寫在 _terrain.py(ev_attack_path_selection 共用);本產生器以斷點讀值逐案驗證
from _terrain import AP_PCT as A, DP_PCT as B, gated, modifier, terrain_type  # noqa: E402

cells = (D / "t_map.bin").read_bytes()
tt = (D / "t_tt.bin").read_bytes()
mods = (D / "t_mods.bin").read_bytes()
assert [struct.unpack_from("<i", mods, 4 * k)[0] for k in range(6)] == A
assert [struct.unpack_from("<i", mods, 0x18 + 4 * k)[0] for k in range(6)] == B


def ttype(x: int, y: int) -> int:
    return terrain_type(cells, tt, x, y)


# 斷點讀值由當時 terr_test.sh 的終端輸出(原始紀錄,見 _console.py)解析;None = 該斷點沒有觸發
CONSOLE = ["20260929T141755_toolu_016aVQX4onVApXD9GXvG9Xx1", "20260929T142012_toolu_01MLSiWLxgWdoxdoGccSPNJL",
           "20260929T142227_toolu_01Gh23mQrScrC5Xn7eZ5oJDp", "20260929T142505_toolu_01Y3jUrvUiPx1NJDgFLuLoXL"]
EIP_AP, EIP_DP, EIP_DMG = 0x1CB8DC, 0x1CB921, 0x1CB9FC  # 0x2f8dc / 0x2f921 / 0x2f9fc;執行期 = 靜態 + 0x19c000
# terr_test.sh 印出的攻防雙方欄位(攻擊前 pre、攻擊後 post;序號 0 = 索爾、11 = 盜賊)
UNIT_LINE = re.compile(r"(?m)^(pre|post) (\d+) \((\d+), (\d+)\) race (\d+) class (\d+) .* HP (\d+) AP DP HIT EV (\d+) (\d+) ")


def s32(v: int) -> int:
    """暫存器值(無號 32 位元)轉有號。"""
    return v - (1 << 32) if v & 0x80000000 else v


bp, unit_console = {}, {}
for stem in CONSOLE:
    for args, seg in _console.segments(stem, "terr_test.sh"):
        tag = args[-1]  # terr_test.sh 的最後一個參數 = 案例標籤(傾印檔名 pre_<tag>.bin / post_<tag>.bin)
        st = _console.stops(seg)
        eax = {s["EIP"]: s32(s["EAX"]) for s in st}
        assert len(eax) == len(st) and set(eax) <= {EIP_AP, EIP_DP, EIP_DMG}, (tag, st)
        assert tag not in bp, tag
        bp[tag] = (eax.get(EIP_AP), eax.get(EIP_DP), eax[EIP_DMG])
        unit_console[tag] = {(m[0], int(m[1])): tuple(int(v) for v in m[2:]) for m in UNIT_LINE.findall(seg)}
assert list(bp) == ["T1", "T2", "T3", "T4", "T5", "T6", "T7"], bp
cases = []
for tag, (bap, bdp, bdmg) in bp.items():
    pre = (D / f"pre_{tag}.bin").read_bytes()
    post = (D / f"post_{tag}.bin").read_bytes()
    a, d = pre[0:80], pre[11 * 80:12 * 80]
    w = lambda r, o: struct.unpack_from("<H", r, o)[0]
    ap, dp = w(a, 0x48), w(d, 0x4A)
    ta, td = ttype(a[0], a[1]), ttype(d[0], d[1])
    apm = modifier(ap, A, ta, a)
    dpm = modifier(dp, B, td, d)
    dmg = max(0, ((ap + (apm or 0)) - (dp + (dpm or 0))) * 9 // 10)
    assert dmg < 18  # 亂數項為 0
    hp_drop = w(d, 0x40) - w(post[11 * 80:12 * 80], 0x40)
    # 同一段終端輸出印出的雙方欄位必須等於該案例的傾印(證明這段輸出與傾印是同一次執行)
    for (ph, i), (x, y, race, cls, hp, ap_, dp_) in unit_console[tag].items():
        r = (pre if ph == "pre" else post)[i * 80:(i + 1) * 80]
        assert (x, y, race, cls, hp, ap_, dp_) == (r[0], r[1], r[0x1F], r[0x20], w(r, 0x40), w(r, 0x48), w(r, 0x4A)), (tag, ph, i)
    assert sorted(unit_console[tag]) == [("post", 0), ("post", 11), ("pre", 0), ("pre", 11)], tag
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
