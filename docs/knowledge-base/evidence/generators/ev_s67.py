"""續六十七證據:evidence/path_search_hits_friendly_mode8_20261001.json。
A. 0x4e4f6(路徑搜尋)三種 mode:由入口傾印逐指令重算,比對回傳值、outBuf 與整張地圖;另比對 0x4e390 泛洪。
B. 一次攻擊打幾下:場景 0x2ebe1 與地圖 0x1e856,以停點讀到的武器類型與亂數預測下數,再數實際的每一擊停點。
C. 友軍回合 0x1d80b 的 AI 模式 8。
全部由 .wsl_build/ctr/v4/ch25 的原始傾印與停點紀錄重新計算,不抄對話輸出。
"""
import json
import struct
import sys
import types
from pathlib import Path

from _evpaths import GAME, GEN_DIR, ROOT, out_path, require_inputs  # noqa: E402
require_inputs(__file__)
S = GEN_DIR
sys.path.insert(0, str(S))
from sim_path import Grid, bfs_rival, flood1, search  # noqa: E402
sys.path.insert(0, str(ROOT / "tools"))
import disasm_le as dl  # noqa: E402
import fd2save as F  # noqa: E402
from _exeops import operand  # noqa: E402

D = ROOT / ".wsl_build/ctr/v4/ch25"
OUT = out_path("path_search_hits_friendly_mode8_20261001.json")
UB = 0x26EA0C
tt = (D / "d0_tt.bin").read_bytes()
# 道具表(EXE 0x602AD,215 列 × 0x17 bytes):+9 是武器類型,供 B 段的靜態值重算
_exe = (GAME / "FD2.EXE").read_bytes()
_meta = dl.parse_le(_exe)
ITEMS = [bytes(dl.object_bytes(_exe, _meta, 0x602AD + i * 0x17, 0x17)) for i in range(215)]


def stops_of(tag: str) -> list[dict]:
    return [s for st in json.loads((D / f"{tag}.json").read_text(encoding="utf-8")) for s in st["stops"]]


def keys_of(tag: str) -> list[dict]:
    return [{"key": st["key"], "stops": [s["eip"] for s in st["stops"]]}
            for st in json.loads((D / f"{tag}.json").read_text(encoding="utf-8"))]


def gdiff(a: bytes | bytearray, b: bytes) -> int:
    assert len(a) == len(b), (len(a), len(b))
    return sum(x != y for x, y in zip(a, b))


# ---------------- A. 路徑搜尋 ----------------
src = (S / "sim_path.py").read_text(encoding="utf-8")
assert src.count("al <= (g.b[i + 1] & 0xFC)") == 1
fewer = types.ModuleType("fewer")
exec(src.replace("al <= (g.b[i + 1] & 0xFC)", "al >= (g.b[i + 1] & 0xFC)"), fewer.__dict__)

floods = []
for tag in ("a1", "a2", "a4"):
    st = stops_of(tag)
    assert st[0]["eip"] == "0x1894d", st[0]["eip"]
    cost_p, sx, sy, cl, _grid_p, _tt_p = st[0]["args"]  # 0x4e390(costRow, x, y, budget, grid, terrainTable)
    pre = (D / f"{tag}_0_f1pre.bin").read_bytes()
    post = (D / f"{tag}_1_f1post.bin").read_bytes()
    g = Grid(pre, tt, (D / "costrows.bin").read_bytes()[0x13 * 0x14:0x14 * 0x14])
    assert cost_p == 0x1F3646 + 0x13 * 0x14
    flood1(g, sx, sy, cl)
    floods.append({"run": tag, "start": [sx, sy], "budget": cl, "grid_bytes": len(pre), "grid_diff": gdiff(g.b, post)})


def calls_of(tag: str, entry: str, rets: tuple[str, ...], pre_fmt: str, post_fmt: str) -> list[tuple]:
    st = stops_of(tag)
    out, cur = [], None
    for n, s in enumerate(st):
        if s["eip"] == entry:
            cur = (n, s)
        elif cur and s["eip"] in rets:
            out.append((cur[0], cur[1], n, s | {"_tag": tag}, D / pre_fmt.format(tag=tag, n=cur[0]), D / post_fmt.format(tag=tag, n=n)))
            cur = None
    return out


calls = []
for tag in ("a1b", "a2", "a4"):
    calls += [("player",) + c for c in calls_of(tag, "0x189f8", ("0x189fd",), "{tag}_{n}_f2pre.bin", "{tag}_{n}_f2post.bin")]
for tag in ("c7a", "c7b"):
    calls += [("entry",) + c for c in calls_of(tag, "0x4e4f6", ("0x141b5", "0x14c3f", "0x14c82", "0x14ea4", "0x189fd"),
                                                "{tag}_{n}_pre.bin", "{tag}_{n}_post.bin")]
# 呼叫端(回傳位址)→ mode,與 A.static.callers 相同
CALLER_MODE = {"0x189fd": 0, "0x14c3f": 0, "0x14c82": 1, "0x141b5": 2, "0x14ea4": 0}
search_rows = []
for kind, n0, e, n1, r, fpre, fpost in calls:
    # 0x4e4f6(costRow, startX, startY, budget, outBuf, tgtX, tgtY, mode, grid, terrainTable)
    _cost_p, sx, sy, bud, _out_p, tx, ty, mode, _grid_p, _tt_p = e["args"]
    pre, post = fpre.read_bytes(), fpost.read_bytes()
    g = Grid(pre, tt, bytes(e["cost"]))
    res, path = search(g, sx, sy, bud, tx, ty, mode)
    last = search.last
    buf = [last["buf"][k] for k in sorted(last["buf"])]
    row = {"run": fpre.name.split("_")[0], "caller_ret": e.get("ret", "0x189fd"), "start": [sx, sy], "budget": bud,
           "target": [tx, ty], "mode": mode, "live_eax": r["eax"], "sim": res, "outbuf_written_sim": buf,
           "outbuf_live": r["outbuf"][:len(buf)], "grid_diff": gdiff(g.b, post), "target_arrival_depths": last["arrivals"]}
    assert row["run"] == fpost.name.split("_")[0] == r["_tag"] and mode == CALLER_MODE[row["caller_ret"]], row
    if "forced40" in e:
        fx, fy, f_old, f_new = e["forced40"]  # 偵錯器把該格 c2 由 f_old 改成 f_new
        assert not f_old & 0x40 and f_new & 0x40 and pre[g.idx(fx, fy) + 2] == f_new, e["forced40"]
        row["forced_flag_0x40_on"] = [fx, fy]
    if mode == 0 and res not in (0, 0xFF):
        rb, pb = bfs_rival(Grid(pre, tt, bytes(e["cost"])), sx, sy, bud, tx, ty)
        row["rival_bfs_first_shortest"] = {"result": rb, "path": pb, "differs": pb != path}
        row["rival_manhattan"] = abs(tx - sx) + abs(ty - sy)
    if mode == 1:
        g0 = Grid(pre, tt, bytes(e["cost"]))
        r0, p0 = search(g0, sx, sy, bud, tx, ty, 0)
        gf = fewer.Grid(pre, tt, bytes(e["cost"]))
        rf, pf = fewer.search(gf, sx, sy, bud, tx, ty, mode)
        row["rival_mode0_rules"] = {"result": r0, "grid_diff": gdiff(g0.b, post)}
        row["rival_equal_budget_fewer_turns"] = {"result": rf, "path_head": pf[:12], "grid_diff": gdiff(gf.b, post)}
        # 兩個對照規則都至少有一格與實際地圖不同(對照被否決)
        assert row["rival_mode0_rules"]["grid_diff"] > 0 and row["rival_equal_budget_fewer_turns"]["grid_diff"] > 0, row
    if mode == 2:
        cells = [(x, y) for y in range(g.H) for x in range(g.W) if pre[g.idx(x, y) + 2] & 0x40]
        g_pre = Grid(pre, tt, bytes(e["cost"]))
        entered = {(x, y) for y in range(g.H) for x in range(g.W) if g.mark(x, y) != g_pre.mark(x, y)}

        def dist(c: tuple[int, int]) -> int:
            cx, cy = c
            return abs(cx - sx) + abs(cy - sy)
        hits = last["hits"]
        first_hit, *_ = hits
        row["mode2_hits_in_order"] = [list(h) for h in hits]
        row["rival_first_hit"] = list(first_hit)
        row["rival_nearest_0x40_cell"] = list(min(cells, key=dist))
        row["rival_nearest_reached_0x40_cell"] = [list(c) for c in sorted(set(hits), key=dist) if dist(c) == min(map(dist, hits))]
        # 每次命中都是入口傾印裡 c2 & 0x40 的格;outBuf 是最後一次命中,三個對照(第一個 / 最近 / 命中中最近)都不是它
        # 命中 = 走進去(記號改變)的 c2 & 0x40 格,不多不少
        assert set(hits) == set(cells) & entered and list(hits[-1]) == buf, (hits, buf)
        assert buf != row["rival_first_hit"] and buf != row["rival_nearest_0x40_cell"] \
            and buf not in row["rival_nearest_reached_0x40_cell"], row
    row["match"] = res == r["eax"] and buf == row["outbuf_live"] and row["grid_diff"] == 0
    search_rows.append(row)
# 哪幾列有哪一種對照:mode 0 且走了至少一步才抵達、mode 1、mode 2(與上面的條件分開寫,任一邊改了都會不符)
assert [("rival_bfs_first_shortest" in r, "rival_mode0_rules" in r, "mode2_hits_in_order" in r) for r in search_rows] == \
    [(r["mode"] == 0 and r["start"] != r["target"] and bool(r["target_arrival_depths"]), r["mode"] == 1, r["mode"] == 2)
     for r in search_rows], search_rows

MUT = {
    "same_depth_does_not_overwrite(> 改 >=)": ('if d > st["res"]:', 'if d >= st["res"]:'),
    # mode 1 不寫段數會讓相等預算無限重進(遞迴不終止),所以只在 mode 0/2 拿掉
    "turn_count_not_written_mode0_2": ("g.b[i + 1] = (g.b[i + 1] & 3) | al  # 0x4e6ca",
                                       "g.b[i + 1] = (g.b[i + 1] & 3) | al if mode == 1 else g.b[i + 1]"),
    "dir_order_up_first": ("for d, nx, ny, ok in ((3, x + 1, y, x + 1 < g.W), (1, x - 1, y, x > 0), (0, x, y + 1, y + 1 < g.H),\n                              (2, x, y - 1, y > 0)):",
                           "for d, nx, ny, ok in ((2, x, y - 1, y > 0), (3, x + 1, y, x + 1 < g.W), (1, x - 1, y, x > 0),\n                              (0, x, y + 1, y + 1 < g.H)):"),
    "mode2_keeps_first_hit": ('st["buf"][0], st["buf"][1] = x, y', 'st["buf"].setdefault(0, x); st["buf"].setdefault(1, y)'),
}
mutations = {}
for name, (old, new) in MUT.items():
    assert src.count(old) >= 1, name
    m = types.ModuleType(name)
    exec(src.replace(old, new, 1), m.__dict__)  # 第一處在 search() 內(bfs_rival 在後面)
    bad, bad_rows = [], []
    for (kind, n0, e, n1, r, fpre, fpost), row in zip(calls, search_rows, strict=True):
        _cost_p, sx, sy, bud, _out_p, tx, ty, mode, _grid_p, _tt_p = e["args"]
        pre, post = fpre.read_bytes(), fpost.read_bytes()
        g = m.Grid(pre, tt, bytes(e["cost"]))
        res, _ = m.search(g, sx, sy, bud, tx, ty, mode)
        b = [m.search.last["buf"][k] for k in sorted(m.search.last["buf"])]
        if not (res == r["eax"] and b == r["outbuf"][:len(b)] and g.b == post):
            bad.append(f'{fpre.name.split("_")[0]}:mode{mode}')
            bad_rows.append(row)
    mutations[name] = {"calls_that_fail": bad, "killed": bool(bad)}
    # 預期會壞的呼叫:同深度覆寫只影響最短深度抵達兩次以上的呼叫;預算 0 不離開起點,方向順序與段數都不影響;
    # 段數只在 mode 0/2 被拿掉;只留第一次命中只影響命中兩次以上的 mode 2
    expect = {"same_depth_does_not_overwrite(> 改 >=)":
              lambda w: (d := w["target_arrival_depths"]) != [] and d.count(min(d)) > 1,
              "turn_count_not_written_mode0_2": lambda w: w["mode"] != 1 and w["budget"] > 0,
              "dir_order_up_first": lambda w: w["budget"] > 0,
              "mode2_keeps_first_hit": lambda w: w["mode"] == 2 and len(set(map(tuple, w["mode2_hits_in_order"]))) > 1}[name]
    assert bad_rows == [w for w in search_rows if expect(w)] and bad == [f'{w["run"]}:mode{w["mode"]}' for w in bad_rows], (name, bad)

sol_after_ff = (D / "sol.bin").read_bytes()
# 索爾是隊員:JOIN 建構子 0x112a5 在 0x11337 寫 +5 = 0;位移讀自那條指令
JOIN_F5 = operand(0x11337, "mov byte ptr [esi + ", "], 0")
# a4:游標 = 0x1894d 的起點往右(第一個 Return 之前的 Right 次數),該格在 d0 傾印裡站著陣營 2 的隊員;
# 被拒後再往右一格,才是 0x189f8 確認的目標
a4_st, a4_keys = stops_of("a4"), [k["key"] for k in keys_of("a4")]
a4_start = next(s["args"][1:3] for s in a4_st if s["eip"] == "0x1894d")
# a4 之後索爾還在 0x1894d 的起點(路徑搜尋回 0xff,沒有移動)
sol_xy_ff = list(sol_after_ff[:2])
assert sol_xy_ff == a4_start, (sol_xy_ff, a4_start)
cursor = [a4_start[0] + a4_keys[:a4_keys.index("Return")].count("Right"), a4_start[1]]
assert next(s["args"] for s in a4_st if s["eip"] == "0x189f8")[5:7] == [cursor[0] + 1, cursor[1]], cursor
d0u = (D / "d0_units.bin").read_bytes()
occ = [i for i in range(len(d0u) // 80) if [d0u[i * 80], d0u[i * 80 + 1]] == cursor]
assert len(occ) == 1 and d0u[occ[0] * 80 + 6] == 2, occ
A = {
    "static": {
        "signature": "0x4e4f6(costRow, startX, startY, budget, outBuf, tgtX, tgtY, mode, grid, terrainTable);格子 4 bytes:c0/c1 圖塊字(c1 高 6 bits 存方向段數×4)、c2 旗標、c3 記號",
        "return": "byte [0x60078]:起點就是目標 → 0;mode 0/1 抵達目標時的深度(步數),同深度或更短的後到者覆寫並把方向陣列寫進 outBuf(只寫前 d 個,較長的舊路徑尾巴留著);沒抵達 → 0xff。mode 2 每進一個 c2 & 0x40 的格就寫 (x, y) 到 outBuf[0..1] 並設 1",
        "enter_rule_0x4e680": "扣成本(無號借位失敗)→ 剩餘與記號有號比較:小於失敗、大於接受、相等只有 mode 1 且這條路的方向段數 > 該格記錄的段數才接受;接受後寫段數。mode 2 直接寫記號並檢查 0x40;mode 0/1:0x40 失敗、0x80 剩餘歸 0、寫記號、檢查目標",
        "dir_order": "右(3)、左(1)、下(0)、上(2)",
        "callers": {"0x189f8": "玩家確認落點,mode 0,預算 MV", "0x14c3a": "move_unit_toward_point,mode 0,預算 MV",
                    "0x14c7d": "move_unit_toward_point,mode 1,預算 0x1c(先 0x4df4c 重設)", "0x141b0": "0x14121,mode 2,預算 0x1c,目標 (0,0)",
                    "0x14e9f": "move_unit_toward_point 的最後一步,mode 0"},
        "caller_0x18890_on_0xff": "0x18b24 → 0x18b77 回 1(與選格時按 Escape 同一個出口,外層 do{}while(r==0) 結束,回地圖游標);沒有呼叫 0x3776e 釋放路徑緩衝",
        "why_0xff_unreachable_from_player_confirm": "0x4e390/0x4e4be 與 mode 0 的 0x4e680 進格規則相同,同一個 0x145cd(1) 標記;target_cursor_loop(4) 只收 0x4e390 記號 != 0xff 的格,而 0x146d1 把同陣營單位格標 0xff",
    },
    "flood1_0x4e390_recompute": floods,
    "path_search_recompute": search_rows,
    "simulator_mutations": mutations,
    "target_loop_reject_occupied": {"run": "a4", "cursor_cell": cursor, "occupied_by": f"隊員 #{occ[0]}",
                                    "keys": keys_of("a4")},
    "after_forced_0xff": {"sol_xy": sol_xy_ff, "sol_f5": sol_after_ff[JOIN_F5],
                          "screen": "a4 之後回到地圖游標,沒有指令環"},
}

# ---------------- B. 打幾下 ----------------
st_cache: dict = {}


def stk(tag: str, n: int, k: int) -> int:
    b = (D / f"{tag}_{n}_st.bin").read_bytes()
    return struct.unpack_from("<I", b, 4 * k)[0]


def scene_hits(used: int, t: int) -> int:
    """場景 0x2ebe1:預設 1、亂數 < 3 → 2,武器類型 3 再 +1(見 B.static)。"""
    return (2 if used < 3 else 1) + (1 if t == 3 else 0)


seqs, seq_at = [], []
for tag in ("b1b", "b2b", "b3b", "b4b", "b5b", "b6b", "b6d", "b6e"):
    st = stops_of(tag)
    i = 0
    while i < len(st):
        s = st[i]
        if s["eip"] == "0x2ecbf":  # 場景:亂數 → 每一擊 0x2ed0c / 0x2f934(EBX 類型)
            atk, dfn = stk(tag, i, 0x28), stk(tag, i, 0x29)
            roll = s["edx"]
            used = s.get("forced_edx", {}).get("after", roll)
            j, hits, types_ = i + 1, 0, []
            while j < len(st) and st[j]["eip"] in ("0x2ed0c", "0x2f934", "0x2f9fc"):
                if st[j]["eip"] == "0x2ed0c":
                    hits += 1
                if st[j]["eip"] == "0x2f934":
                    types_.append(st[j]["ebx"])
                j += 1
            t, *_ = types_
            pred = scene_hits(used, t)
            seqs.append({"run": tag, "path": "scene 0x2ebe1", "attacker": atk, "defender": dfn, "weapon_type_row9": t,
                         "roll": roll, "roll_used": used, "forced": used != roll, "predicted_hits": pred,
                         "observed_hits": hits, "match": pred == hits})
            seq_at.append(None)
            i = j
            continue
        if s["eip"] == "0x1e8b1" and i + 1 < len(st) and st[i + 1]["eip"] == "0x1e8cf":
            r = st[i + 1]
            atk, dfn = stk(tag, i + 1, 8), stk(tag, i + 1, 9)
            t = s["eax"]
            roll = r["edx"]
            used = r.get("forced_edx", {}).get("after", roll)
            j, hits = i + 2, 0
            while j < len(st) and st[j]["eip"] in ("0x1e912", "0x1efce"):
                hits += st[j]["eip"] == "0x1e912"
                j += 1
            pred = 2 if (t == 3 or used < 3) else 1
            seqs.append({"run": tag, "path": "map 0x1e856", "attacker": atk, "defender": dfn, "weapon_type_row9": t,
                         "roll": roll, "roll_used": used, "forced": used != roll, "predicted_hits": pred,
                         "observed_hits": hits, "match": pred == hits,
                         "scene_rule_would_give": scene_hits(used, t)})
            # 這一擊之前最近的 ai_mode_dispatch 停點(沒有 = 不在 AI 回合裡)
            seq_at.append(max((k for k in range(i) if st[k]["eip"] == "0x13aef"), default=None))
            i = j
            continue
        i += 1

# 每一段都抓到了:場景段數 = 0x2ecbf 停點數、地圖段數 = 0x1e8b1 緊接 0x1e8cf 的次數(另外數)
_all = {tag: stops_of(tag) for tag in ("b1b", "b2b", "b3b", "b4b", "b5b", "b6b", "b6d", "b6e")}
assert sum(x["path"] == "scene 0x2ebe1" for x in seqs) == sum(s["eip"] == "0x2ecbf" for st in _all.values() for s in st)
assert sum(x["path"] == "map 0x1e856" for x in seqs) == \
    sum((s["eip"], t["eip"]) == ("0x1e8b1", "0x1e8cf") for st in _all.values() for s, t in zip(st, st[1:]))
# 攻守雙方:場景段兩兩一組(出手、反擊,攻守對調);地圖段的攻方 = 該回合派發的單位,同一次派發的第二擊是反擊(對調)
for tag in _all:
    sc = [(x["attacker"], x["defender"]) for x in seqs if x["run"] == tag and x["path"] == "scene 0x2ebe1"]
    assert len(sc) % 2 == 0 and all(sc[k + 1] == sc[k][::-1] and sc[k][0] != sc[k][1] for k in range(0, len(sc), 2)), (tag, sc)
    prev: dict = {}
    for x, at in zip(seqs, seq_at):
        if x["run"] != tag or x["path"] != "map 0x1e856":
            continue
        assert at is not None, x
        u = (_all[tag][at]["ebx"] - UB) // 80
        if at in prev:
            assert (x["attacker"], x["defender"]) == (prev[at]["defender"], prev[at]["attacker"]), (tag, x)
        else:
            assert x["attacker"] == u != x["defender"], (tag, u, x)
        prev[at] = x

c66 = (ROOT / ".wsl_build/ctr/v3/ch29/bx_pre_units.bin").read_bytes()
# 單位紀錄 +0x0a / +0x0b 是第 0 格道具的旗標 / id(tools/fd2save.py 續三十四已驗證);旗標只會是 0x00 / 0x40 / 0x80,0x80 = 空格
sol_flag0, sol_item0 = c66[F.UNIT_INVENTORY_FLAG_OFFSET], c66[F.UNIT_INVENTORY_ITEM_OFFSET]
assert sol_flag0 in (0x00, 0x40) and sol_item0 == 31, (sol_flag0, sol_item0)  # 索爾第一格是武器 31(鍵名 weapon31_row9)
B = {
    "static": {
        "map_0x1e856": "下數預設 1;攻方武器(find_equipped_slot(攻方, 0))道具列 +9 == 3 → 2;rand()%100 < 3 → 2(不疊加,最多 2)",
        "scene_0x2ebe1": "下數預設 1;rand()%100 < 3 → 2;每一擊後若 scene_attack_resolve 的 out+0x10 != 0(武器列 +9 == 3 時設 1)且還沒加過,下數 +1(只加一次)→ 最多 3",
        "row9_eq_3_items": [i for i, r in enumerate(ITEMS) if r[9] == 3],
        "item71_name_on_status_screen": "魔龍爪",
        "ai_attack_execute_counter_calls": "0x1548e 只有一個反擊呼叫點 0x1560e(不在迴圈內)",
    },
    "sequences": seqs,
    "s66_double_counter": {
        "sol_slot0": [sol_flag0, sol_item0], "weapon31_row9": ITEMS[sol_item0][9],
        "conclusion": "續六十六索爾(武器 31,類型 0)在地圖路徑反擊打 2 下:靜態上只剩 rand()%100 < 3 這一支;該次亂數沒記錄,屬推論",
    },
    "note_ai_used_weapon_as_item": "E #18 原武器 60 的道具列 +0xd = 20,ai_choose_action 走道具執行 0x15055(把武器當道具用)而不是物理攻擊;換成武器 8(+0xd = 0)後才走 0x1548e。道具列 +0xd != 0 的武器:11, 29, 38, 40, 51, 56, 57, 58, 60, 61, 79, 94, 95, 96, 99, 101, 102",
}

# ---------------- C. 友軍回合模式 8 ----------------
fr = []
for tag, m17 in (("b1b", 8), ("b2b", 3), ("b3b", 8), ("b4b", 8)):
    st = stops_of(tag)
    for i, s in enumerate(st):
        if s["eip"] == "0x13aef":
            u = (s["ebx"] - UB) // 80
            if (s["ebx"] - UB) % 80:
                continue
            nxt = []
            for t in st[i + 1:]:
                if t["eip"] in ("0x13aef", "0x1d942", "0x1d9d2"):
                    break
                nxt.append(t["eip"] if t["eip"] != "0x13512" else f"0x13512({t.get('arg1')})")
            end = next((k for k in range(i + 1, len(st)) if st[k]["eip"] in ("0x13aef", "0x1d942", "0x1d9d2")), len(st))
            assert len(nxt) == end - i - 1, (tag, i, len(nxt), end)
            prev = st[i - 1]["eip"] if i else None
            fr.append({"run": tag, "unit": u, "mode_eax": s["eax"], "set_mode17": m17 if u == 17 else None,
                       "phase": "friendly" if prev == "0x1d874" else ("enemy" if prev in ("0x1d942", "0x1d9d2") else prev),
                       "after_until_next_dispatch": [x for x in nxt if x != "0x1d874"][:8]})
# 每次派發的前一個停點都是友軍回合迴圈 0x1d874 或敵方回合 0x1d942 / 0x1d9d2
assert fr and all(f["phase"] in ("friendly", "enemy") for f in fr), [f["phase"] for f in fr]
# SM 設定的 #17 模式(低四位)必須等於 ai_mode_dispatch 停點讀到的值
assert any(f["unit"] == 17 for f in fr) and all(f["mode_eax"] & 0xF == f["set_mode17"] for f in fr if f["unit"] == 17), fr
C = {
    "static": "0x1d80b:單一趟,條件 +6 == 1、+5 & 0x81 == 0、+0x26 == 0,呼叫 ai_mode_dispatch(unit, 1);模式比對不看 a2,所以模式 8 同樣在 0x13d97 跳到結尾",
    "shipped_data": "map 24 友軍 NPC #17(10,0)出貨就是模式 8、MV 0",
    "dispatches": fr,
}

doc = {"note": "DOSBox-X;FD2.EXE md5 33464c81e6a364fd0660141139aa8e6e;第 25 章戰場(map 24),來源存檔 source_ch27.SAV 經 prepare_chapter_save 改章節 byte。"
               "斷點位址為 Ghidra 位址,執行期 +0x19c000。受控設定:[0x53af9] = 1、敵 E 搬到索爾正上方 (7,42)、MV 0、清法術/MP/第二格,雙方 AP 300 / DP 200 / HIT 250 / EV 0 / HP 999,其他敵人與隊員麻痺 9。"
               "強制亂數用偵錯器 SR EDX 0,並讀回 pane 確認。",
       "A_path_search_0x4e4f6": A, "B_hit_count": B, "C_friendly_phase_mode8": C}
# 結論的判準:泛洪與路徑搜尋逐格 / 逐值重現、每一段打幾下都等於預測、每個模擬器變異都至少有一次呼叫不符
assert floods and all(f["grid_diff"] == 0 for f in floods), [f["grid_diff"] for f in floods]
assert search_rows and all(r["match"] for r in search_rows), [r["match"] for r in search_rows]
assert seqs and all(x["match"] for x in seqs), [x["match"] for x in seqs]
assert mutations and all(m["killed"] for m in mutations.values()), mutations
assert B["static"]["row9_eq_3_items"] == [71] and B["s66_double_counter"]["weapon31_row9"] == 0
OUT.write_bytes((json.dumps(doc, ensure_ascii=False, indent=1) + "\n").encode("utf-8"))
print("floods", [f["grid_diff"] for f in floods])
print("search", [(r["run"], r["mode"], r["live_eax"], r["sim"], r["grid_diff"], r["match"]) for r in search_rows])
print("mutations", {k: v["calls_that_fail"] for k, v in mutations.items()})
print("seqs", len(seqs), "all match", all(x["match"] for x in seqs))
for x in seqs:
    if x["weapon_type_row9"] == 3 or x["roll_used"] < 3:
        print("  ", x["path"], x["attacker"], "type", x["weapon_type_row9"], "roll", x["roll"], "->", x["roll_used"], "pred", x["predicted_hits"], "obs", x["observed_hits"])
print("type0 natural:", sum(1 for x in seqs if x["weapon_type_row9"] != 3 and x["roll_used"] >= 3), "all 1:",
      all(x["observed_hits"] == 1 for x in seqs if x["weapon_type_row9"] != 3 and x["roll_used"] >= 3))
print("friendly", [(f["run"], f["unit"], f["mode_eax"], f["phase"], f["after_until_next_dispatch"][:3]) for f in fr if f["unit"] in (17, 18, 19)])
