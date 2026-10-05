"""地形類型 3..5 動態驗證(改寫地形表)的證據 JSON 與登錄表更新(doc98 續五十四)。"""
# 移植說明:原腳本後段是一次性更新 docs/data/function_names.json 的補丁(已套用並提交),不屬於證據重算,移植時刪除。
import json
import re
import struct
from pathlib import Path

from _evpaths import GAME, GEN_DIR, ROOT, out_path, require_inputs  # noqa: E402,F401
require_inputs(__file__)
import _console  # noqa: E402
EVI = out_path("terrain_types_3_5_20260930.json")
D = ROOT / ".wsl_build" / "ctr"
W = 27

cells = (D / "t3_map.bin").read_bytes()
mods = (D / "t3_mods.bin").read_bytes()
A = [struct.unpack_from("<i", mods, 4 * k)[0] for k in range(6)]
B = [struct.unpack_from("<i", mods, 0x18 + 4 * k)[0] for k in range(6)]
assert A == [5, 0, -5, -5, -5, 0] and B == [0, 0, 10, 10, -5, 0], (A, B)
tt0 = (D / "t3_tt.bin").read_bytes()


def tile(x: int, y: int) -> int:
    return struct.unpack_from("<H", cells, 4 + 4 * (y * W + x))[0] & 0x3FF


TA, TB = tile(20, 14), tile(19, 14)
assert (TA, TB) == (0x6E, 0x6D) and tt0[TA * 4 + 1] == 0 and tt0[TB * 4 + 1] == 0


def tdiv(a: int, b: int) -> int:
    """idiv:向零截斷。"""
    q = abs(a) // abs(b)
    return q if (a >= 0) == (b > 0) else -q


def gated(r: bytes) -> bool:
    """unit_uses_move_cost_row19 的靜態規則。"""
    if r[7] == 0x1C:
        return False
    return r[0x20] == 0x13 or r[0x1F] in (4, 5)


# 斷點讀值(EAX;EDX = idiv 餘數)由當時 terr_test.sh 的終端輸出(原始紀錄,見 _console.py)解析;None = 該斷點沒有觸發。
# 第一次呼叫在 u1 之後的 u2..u4 都沒有停在任何斷點、盜賊 HP 未變(攻擊沒有發生),之後分兩次重跑並覆寫了
# pre_/post_/tt_ 傾印;所以每個標籤取「有停點」的那一段,且必須恰好一段。
CONSOLE = ["20260930T005926_toolu_014cYfAvrEVNowAgLydrjBHu", "20260930T010148_toolu_015UkArPfBxCh5EJu1YZ9ZMF",
           "20260930T010426_toolu_015fM1jPVs6fuVBPsQS5tF8k"]
EIP_AP, EIP_DP, EIP_DMG = 0x1CB8DC, 0x1CB921, 0x1CB9FC  # 0x2f8dc / 0x2f921 / 0x2f9fc;執行期 = 靜態 + 0x19c000
HEAD = re.compile(r"(?m)^=== (\w+): attacker type (\d+), defender type (\d+), .*\n")
# terr_test.sh 印出的攻防雙方欄位(攻擊前 pre、攻擊後 post;序號 0 = 索爾、11 = 盜賊)
UNIT_LINE = re.compile(r"(?m)^(pre|post) (\d+) \((\d+), (\d+)\) race (\d+) class (\d+) .* HP (\d+) AP DP HIT EV (\d+) (\d+) ")


def s32(v: int) -> int:
    """暫存器值(無號 32 位元)轉有號。"""
    return v - (1 << 32) if v & 0x80000000 else v


def console_segments(stem: str) -> list[tuple[str, tuple[int, int] | None, str]]:
    """回傳 [(標籤, 標頭印的(攻方類型, 守方類型) 或 None, 該段輸出)]。

    多次呼叫的輸出以 `=== <標籤>: attacker type A, defender type B, ...` 標頭分段;沒有標頭的
    單次呼叫,標籤取指令中 terr_test.sh 的最後一個參數(指令有多行,逐行找呼叫)。
    """
    meta, text = _console.load(stem)
    heads = HEAD.findall(text)
    if not heads:
        (args,) = [a for line in meta["cmd"].splitlines() for a in _console.invocations(line, "terr_test.sh")]
        return [(args[-1], None, text)]
    parts = HEAD.split(text)
    assert parts[0].strip() == "" and len(parts) == 1 + 4 * len(heads), stem
    return [(parts[k], (int(parts[k + 1]), int(parts[k + 2])), parts[k + 3]) for k in range(1, len(parts), 4)]


bp, seg_info = {}, {}
for stem in CONSOLE:
    for tag, head_types, seg in console_segments(stem):
        units = {(m[0], int(m[1])): tuple(int(v) for v in m[2:]) for m in UNIT_LINE.findall(seg)}
        assert sorted(units) == [("post", 0), ("post", 11), ("pre", 0), ("pre", 11)], (stem, tag)
        st = _console.stops(seg)
        if not st:  # 沒有停點 = 攻擊沒有發生:盜賊 HP 必須未變,且不採用這段
            assert units[("pre", 11)][4] == units[("post", 11)][4], (stem, tag)
            continue
        regs = {s["EIP"]: (s32(s["EAX"]), s32(s["EDX"])) for s in st}
        assert len(regs) == len(st) and set(regs) <= {EIP_AP, EIP_DP, EIP_DMG}, (tag, st)
        assert tag not in bp, tag
        bp[tag] = {"ap": regs.get(EIP_AP), "dp": regs.get(EIP_DP), "dmg": regs[EIP_DMG][0]}
        seg_info[tag] = (head_types, units)
assert list(bp) == ["u1", "u2", "u3", "u4"], bp
cases = []
for tag, obs in bp.items():
    tt = (D / f"tt_{tag}.bin").read_bytes()
    ta, tb = tt[TA * 4 + 1], tt[TB * 4 + 1]
    pre = (D / f"pre_{tag}.bin").read_bytes()
    post = (D / f"post_{tag}.bin").read_bytes()
    a, d = pre[0:80], pre[11 * 80:12 * 80]
    w = lambda r, o: struct.unpack_from("<H", r, o)[0]
    assert (a[0], a[1]) == (20, 14) and (d[0], d[1]) == (19, 14), tag
    ap, dp = w(a, 0x48), w(d, 0x4A)
    apm = None if gated(a) else tdiv(ap * A[ta], 100)
    dpm = None if gated(d) else tdiv(dp * B[tb], 100)
    dmg = max(0, (ap + (apm or 0) - dp - (dpm or 0)) * 9 // 10)
    assert dmg < 18, "亂數項必須為 0"
    got_ap = None if obs["ap"] is None else obs["ap"][0]
    got_dp = None if obs["dp"] is None else obs["dp"][0]
    assert (got_ap, got_dp, obs["dmg"]) == (apm, dpm, dmg), (tag, got_ap, got_dp, obs["dmg"], apm, dpm, dmg)
    drop = w(pre, 11 * 80 + 0x40) - w(post, 11 * 80 + 0x40)
    assert drop == dmg, (tag, drop)
    # 同一段終端輸出印出的地形類型(標頭)與雙方欄位必須等於該案例的傾印(證明這段輸出與傾印是同一次執行)
    head_types, units = seg_info[tag]
    assert head_types is None or head_types == (ta, tb), (tag, head_types, ta, tb)
    for (ph, i), (x, y, race, cls, hp, ap_, dp_) in units.items():
        r = (pre if ph == "pre" else post)[i * 80:(i + 1) * 80]
        assert (x, y, race, cls, hp, ap_, dp_) == (r[0], r[1], r[0x1F], r[0x20], w(r, 0x40), w(r, 0x48), w(r, 0x4A)), (tag, ph, i)
    floor_ap = None if apm is None else (ap * A[ta]) // 100
    floor_dp = None if dpm is None else (dp * B[tb]) // 100
    cases.append({
        "case": tag,
        "attacker": {"xy": [20, 14], "tile": hex(TA), "terrain_type": ta, "race": a[0x1F], "ap": ap, "gated": gated(a)},
        "defender": {"xy": [19, 14], "tile": hex(TB), "terrain_type": tb, "race": d[0x1F], "dp": dp, "gated": gated(d)},
        "predicted": {"ap_mod": apm, "dp_mod": dpm, "damage": dmg},
        "breakpoints": {"ap_mod_0x2f8dc_eax_edx": obs["ap"], "dp_mod_0x2f921_eax_edx": obs["dp"], "damage_0x2f9fc": obs["dmg"]},
        "defender_hp_drop": drop,
        "floor_division_would_give": {"ap_mod": floor_ap, "dp_mod": floor_dp},
    })
    print(tag, "types", ta, tb, "mods", apm, dpm, "dmg", dmg, "floor", floor_ap, floor_dp)

EVI.write_bytes((json.dumps({
    "note": "DOSBox-X 記憶體傾印與斷點讀值;FD2.EXE md5 33464c81e6a364fd0660141139aa8e6e。第 1 章地圖沒有地形類型 3..5,"
            "所以每擊之前把地形表 [0x53a69](執行期 0x22841c)中索爾所在格 tile 0x6e 與盜賊所在格 tile 0x6d 那兩列的 byte 1 改成指定類型"
            "(tt_*.bin 為改寫後讀回)。修正表執行期讀回 [5,0,-5,-5,-5,0] / [0,0,10,10,-5,0]。predicted 依 scene_attack_resolve 與 "
            "unit_uses_move_cost_row19 的靜態規則計算;null = 該修正被跳過。",
    "cases": cases,
}, ensure_ascii=False, indent=1) + "\n").encode("utf-8"))
print("evidence ok")
