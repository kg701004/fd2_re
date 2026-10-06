"""地圖攻擊路徑動態驗證的證據 JSON 與登錄表更新(doc98 續五十一)。"""
# 移植說明:原腳本後段是一次性更新 docs/data/function_names.json 的補丁(已套用並提交),不屬於證據重算,移植時刪除。
import json
import re
import struct
from pathlib import Path

from _evpaths import GAME, GEN_DIR, ROOT, out_path, require_inputs  # noqa: E402,F401
require_inputs(__file__)
import _console  # noqa: E402
from _terrain import AP_PCT, DP_PCT, exchange, gated, terrain_type  # noqa: E402
EVI = out_path("attack_path_selection_20260929.json")
D = ROOT / ".wsl_build" / "ctr"

# 斷點停點(函式, 返回位址靜態值, arg1, arg2)由當時 bp_log.sh 的終端輸出(原始紀錄,見 _console.py)解析。
# bp_log.sh 的停點行:"stop N: EIP=<執行期入口> <名稱> ret=<執行期> (static <靜態>) arg1=<十進位> arg2=<十進位>";
# 函式名稱依入口位址(執行期 = 靜態 + 0x19c000)對到登錄表名稱,不採用終端上的暫名。
DELTA = 0x19C000
FUNC = {0x2F7B6: "scene_attack_resolve", 0x1548E: "ai_attack_execute", 0x1E856: "map_attack_sequence",
        0x1ECC7: "map_attack_resolve"}
_BP = re.compile(r"^stop \d+: EIP=([0-9A-F]{8}) .*? ret=(0x[0-9a-f]+) \(static (0x[0-9a-f]+)\) arg1=(\d+) arg2=(\d+)\s*$")
# 每回合:依序執行的停點紀錄(bp_log.sh 的標籤, 終端輸出);攻擊後傾印的那次終端輸出(印出攻擊前後的座標與 HP)
RUNS = {
    "M1": {"stops": [("M1", "20260929T145112_toolu_01Jam8p46WdBMVCCtgxbqaZT")],
           "post_print": "20260929T145133_toolu_013yFpSAjgHNYjfCRxkHThAp"},
    "M2": {"stops": [("M2", "20260929T145329_toolu_01TCCLhMocBBLY62AXZ8ANUZ")],
           "post_print": "20260929T145348_toolu_01HZESbratRbtoBt7nFWYDd1"},
    # M3 的敵方回合分三次記錄:M3(玩家攻擊)、M3b(無停點)、M3c_1..12(逐次按鍵推進對話,輸出經 grep "^stop")
    "M3": {"stops": [("M3", "20260929T145513_toolu_01MAtsszyxnc2AvPzVaN7L7C"),
                     ("M3b", "20260929T145610_toolu_01HMmAHLMBLbasV4Mx93D3sr"),
                     ("M3c_$r", "20260929T145843_toolu_01C6kN2ZnGtKspQ3srSVfJ28")],
           "post_print": "20260929T145904_toolu_01EShrTCKKxKaEsq3pHwTK6w"},
}


def bp_stops(stem: str) -> list[tuple[str, str, int, int]]:
    """解析一次終端輸出裡所有 bp_log.sh 停點行,回傳 [(函式, 返回位址靜態值字串, arg1, arg2)]。"""
    out = []
    for line in _console.load(stem)[1].splitlines():
        if not line.startswith("stop "):
            continue
        m = _BP.match(line)
        assert m, (stem, line)  # 每一行停點都要能解析,不略過
        eip, ret, ret_s = int(m[1], 16), int(m[2], 16), int(m[3], 16)
        assert ret - DELTA == ret_s, (stem, line)
        out.append((FUNC[eip - DELTA], hex(ret_s), int(m[4]), int(m[5])))
    return out


rounds = {
    "M1": {"flag_53af9": 1, "pre": "m_pre.bin", "post": "m_post1.bin"},
    "M2": {"flag_53af9": 0, "pre": "m_pre2.bin", "post": "m_post2.bin"},
    "M3": {"flag_53af9": 1, "pre": "m_pre3.bin", "post": "m_post3.bin"},
}
for tag, info in rounds.items():
    info["stops"] = []
    for k, (bp_tag, stem) in enumerate(RUNS[tag]["stops"]):
        meta = _console.load(stem)[0]
        # bp_log.sh 的第一個參數 = 標籤(M3c 那次後面接 | grep,所以不取最後一個)
        assert {a[0] for a in _console.invocations(meta["cmd"], "bp_log.sh")} == {bp_tag}, (tag, stem)
        if k == 0:
            # 第一次記錄的同一個指令先設 [0x53af9]、讀回、再傾印攻擊前的單位表
            assert f"SM 0170:1efaf9 {info['flag_53af9']:02x}" in meta["cmd"] and f"--out $D/{info['pre']}" in meta["cmd"], tag
            flag_rb = re.findall(r"(?m)^raw: ([0-9a-f]{2})$", _console.load(stem)[1])
            assert flag_rb == [f"{info['flag_53af9']:02x}"], (tag, flag_rb)
        info["stops"] += bp_stops(stem)

# 每一擊的(攻方, 守方);AP / DP 讀攻擊前傾印,地形修正由地圖傾印依 _terrain.py 的規則算出
hits = {
    "M1": [(0, 11), (11, 0), (11, 5)],
    "M2": [(0, 11), (11, 0), (11, 6)],
    "M3": [(0, 11), (11, 0), (11, 0), (0, 11), (13, 9), (17, 9)],
}
# 地圖:M3 攻擊後同一個指令傾印的 m_map3.bin;與地形測試開始前的 t_map.bin 逐 byte 相同,所以 M1~M3 期間地圖沒變。
# 地形表與修正表沿用地形測試的傾印(ev_terrain_modifier 以斷點驗證過同一組傾印與規則)。
cells = (D / "m_map3.bin").read_bytes()
assert cells == (D / "t_map.bin").read_bytes()
tt = (D / "t_tt.bin").read_bytes()
mods = (D / "t_mods.bin").read_bytes()
assert [struct.unpack_from("<i", mods, 4 * k)[0] for k in range(6)] == AP_PCT
assert [struct.unpack_from("<i", mods, 0x18 + 4 * k)[0] for k in range(6)] == DP_PCT
_ROW = re.compile(r"(?m)^(\d+) (?:side \d+ )?\((\d+), (\d+)\) -> \((\d+), (\d+)\) (?:terr (\d+) )?.*?HP (\d+) -> (\d+)\b")
_PRE = re.compile(r"(?m)^(\d+) \((\d+), (\d+)\) f5 (0x[0-9a-f]+) \+26 (\d+) HP (\d+) AP DP HIT EV (\d+) (\d+) (\d+) (\d+)$")
out = {}
for tag, info in rounds.items():
    pre = (D / info["pre"]).read_bytes()
    post = (D / info["post"]).read_bytes()
    w = lambda b, i, o: struct.unpack_from("<H", b, i * 80 + o)[0]

    def terr(i: int) -> int:
        """單位 i 出手 / 被打時所在格的地形類型。

        出手或被打的位置是攻擊前或攻擊後的位置之一(移動後才攻擊,攻擊後不再移動);兩處類型必須相同,
        結果才不取決於是哪一處。
        """
        t0 = terrain_type(cells, tt, pre[i * 80], pre[i * 80 + 1])
        assert t0 == terrain_type(cells, tt, post[i * 80], post[i * 80 + 1]), (tag, i)
        return t0

    loss, loss_no_terrain, rows_hit = {}, {}, []
    for (a, d) in hits[tag]:
        ra, rd = pre[a * 80:(a + 1) * 80], pre[d * 80:(d + 1) * 80]
        # 跳過與否看的欄位(+7、種族、職業)在攻擊前後相同
        assert gated(ra) == gated(post[a * 80:(a + 1) * 80]) and gated(rd) == gated(post[d * 80:(d + 1) * 80]), (tag, a, d)
        ap, dp = w(pre, a, 0x48), w(pre, d, 0x4A)
        terr(a), terr(d)  # 攻擊前後所在格類型相同(下面以攻擊前的位置計算)
        apm, dpm, dmg = exchange(ap, dp, ra, rd, lambda r: terrain_type(cells, tt, r[0], r[1]))
        assert dmg < 18
        loss[d] = loss.get(d, 0) + dmg
        loss_no_terrain[d] = loss_no_terrain.get(d, 0) + max(0, (ap - dp) * 9 // 10)
        rows_hit.append((a, d, ap, apm, dp, dpm))
    measured = {}
    for d in loss:
        measured[d] = w(pre, d, 0x40) - w(post, d, 0x40)
    # M1 前 #11 是新設的 999;M2 前 #11 的 HP 在設定時重設為 999
    assert measured == loss, (tag, measured, loss)
    # 對照:只有 M3(AP 24 的盜賊站類型 0,+1)的實測能區分「有 / 沒有地形修正」;M1、M2 兩種預測相同,
    # 所以那兩輪的地形修正欄位只是規則的套用,不是實測結果
    assert (loss_no_terrain != measured) == (tag == "M3"), (tag, loss_no_terrain, measured)
    # 交叉檢查 1:停點紀錄裡每次結算(scene_attack_resolve / map_attack_resolve)的 (arg1, arg2) 依序就是
    # hits 的 (攻方, 守方) —— 預測傷害逐擊對到實際被呼叫的結算,而 HP 差由傾印量得
    assert [(x, y) for f, r, x, y in info["stops"] if f in ("scene_attack_resolve", "map_attack_resolve")] == \
        hits[tag], tag
    # 交叉檢查 2:攻擊後傾印那次的終端輸出(同一次執行)印出的座標與 HP 必須等於兩份傾印,
    # 且每個受傷單位都在其中(證明這兩份傾印就是該次執行的攻擊前後)
    pmeta, ptext = _console.load(RUNS[tag]["post_print"])
    assert f"--out $D/{info['post']}" in pmeta["cmd"] and info["pre"] in pmeta["cmd"], tag
    rows = {int(m[0]): [int(v) for v in m[1:5] + m[6:]] for m in _ROW.findall(ptext)}
    printed_terr = {int(m[0]): int(m[5]) for m in _ROW.findall(ptext) if m[5]}
    assert set(loss) <= set(rows), (tag, sorted(rows))
    for i, (x0, y0, x1, y1, h0, h1) in rows.items():
        assert [x0, y0, x1, y1, h0, h1] == [pre[i * 80], pre[i * 80 + 1], post[i * 80], post[i * 80 + 1],
                                              w(pre, i, 0x40), w(post, i, 0x40)], (tag, i)
    # M3 那次指令同時傾印 m_map3.bin 並以 t_tt.bin 印出每個變動單位攻擊後所在格的地形類型(terr):
    # 必須等於本產生器從同一組傾印算出的類型。那次只印位置或 HP 有變的單位,所以沒印出的出手 / 被打單位
    # 必須是位置與 HP 都沒變的(例如 M3 的 #17)
    assert (tag == "M3") == bool(printed_terr), tag
    if printed_terr:
        assert f"--out $D/m_map3.bin" in pmeta["cmd"] and "t_tt.bin" in pmeta["cmd"], tag
        for i in {i for h in hits[tag] for i in h} - set(printed_terr):
            assert pre[i * 80:i * 80 + 2] == post[i * 80:i * 80 + 2] and w(pre, i, 0x40) == w(post, i, 0x40), (tag, i)
        for i, t in printed_terr.items():
            assert t == terrain_type(cells, tt, post[i * 80], post[i * 80 + 1]), (tag, i)
    if tag == "M1":
        # M1 的停點紀錄同一個指令在傾印 m_pre.bin 後立即印出 #0~#4、#11 的記錄
        pre_rows = _PRE.findall(_console.load(RUNS[tag]["stops"][0][1])[1])
        assert [int(m[0]) for m in pre_rows] == [0, 1, 2, 3, 4, 11], pre_rows
        for m in pre_rows:
            i = int(m[0])
            assert [int(m[1]), int(m[2]), int(m[3], 16), int(m[4]), int(m[5])] + [int(v) for v in m[6:]] == \
                [pre[i * 80], pre[i * 80 + 1], pre[i * 80 + 5], pre[i * 80 + 0x26]] + \
                [w(pre, i, o) for o in (0x40, 0x48, 0x4A, 0x4C, 0x4E)], (tag, i)
    out[tag] = {
        "flag_53af9": info["flag_53af9"],
        "breakpoint_stops": [{"function": f, "return_static": r, "arg1": x, "arg2": y} for f, r, x, y in info["stops"]],
        "hits": [{"attacker": a, "defender": d, "attacker_ap": ap, "attacker_terrain_mod": apm, "defender_dp": dp,
                  "defender_terrain_mod": dpm, "predicted": max(0, (ap + (apm or 0) - dp - (dpm or 0)) * 9 // 10)}
                 for (a, d, ap, apm, dp, dpm) in rows_hit],
        "hp_loss_predicted": {str(k): v for k, v in loss.items()},
        "hp_loss_measured": {str(k): v for k, v in measured.items()},
    }
    ai = [s for s in info["stops"] if s[0] in ("map_attack_resolve", "scene_attack_resolve") and s[1] in ("0x1e917",) or
          (s[0] == "scene_attack_resolve" and info["stops"].index(s) > 1)]
    if info["flag_53af9"]:
        assert all(s[0] != "scene_attack_resolve" for s in info["stops"][2:]), tag
    else:
        assert all(not s[0].startswith("map_") for s in info["stops"]), tag
    assert info["stops"][0][0] == "scene_attack_resolve", tag
EVI.write_bytes((json.dumps({
    "note": "DOSBox-X 斷點停點(函式入口,[ESP] 返回位址、[ESP+4]/[ESP+8] 前兩個參數)與攻擊前後單位記錄的 HP 差;FD2.EXE md5 33464c81e6a364fd0660141139aa8e6e。"
            "每回合前:玩家其餘 4 人設已行動,索爾攻擊盜賊 #11 後自動進入友軍與敵方回合。predicted 依 (AP+地形修正-DP-地形修正)*9//10,"
            "攻守數值皆 <= 17 或整除使亂數項為 0。地形修正由 M3 同一指令傾印的地圖格(m_map3.bin,與地形測試的 t_map.bin 相同)、"
            "地形表與修正表依 unit_uses_move_cost_row19 與 scene_attack_resolve 的規則算出(ev_terrain_modifier 以斷點驗證);"
            "null = 該方被跳過(索爾種族 5)。只有 M3 的 HP 實測能區分有無地形修正。",
    "rounds": out,
}, ensure_ascii=False, indent=1) + "\n").encode("utf-8"))
print("evidence ok", {k: v["hp_loss_measured"] for k, v in out.items()})
