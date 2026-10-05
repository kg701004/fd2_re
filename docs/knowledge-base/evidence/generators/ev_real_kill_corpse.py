"""真實擊殺後屍體座標保留的動態驗證:離線重算、證據 JSON、登錄表更新(doc98 續六十一)。"""
# 移植說明:原腳本後段是一次性更新 docs/data/function_names.json 的補丁(已套用並提交),不屬於證據重算,移植時刪除。
import json
from pathlib import Path

from _evpaths import GAME, GEN_DIR, ROOT, out_path, require_inputs  # noqa: E402,F401
require_inputs(__file__)
D = ROOT / ".wsl_build" / "ctr"
EVI = out_path("real_kill_corpse_20260930.json")


def units(b: bytes) -> list[dict]:
    return [{"i": i, "x": b[i * 80], "y": b[i * 80 + 1], "f5": b[i * 80 + 5], "side": b[i * 80 + 6],
             "hp": b[i * 80 + 0x40] | b[i * 80 + 0x41] << 8} for i in range(len(b) // 80)]


def nearest(us: list[dict], actor: int, drop: set[int]) -> tuple:
    """0x13e9c(a2 = 0):取 +6 != 0 的單位中曼哈頓距離嚴格最小者;drop 是對照規則要剔除的單位。"""
    ax, ay = us[actor]["x"], us[actor]["y"]
    best, bd = None, 0xFFFF
    for u in us:
        if u["side"] == 0 or u["i"] in drop:
            continue
        d = abs(ax - u["x"]) + abs(ay - u["y"])
        if d < bd:
            best, bd = u, d
    return (best["x"], best["y"], best["i"], bd)


pre = (D / "kc_pre.bin").read_bytes()
runs = {}
# 兩個回合在 0x13e9c 入口的傾印,以及 #13 移動後的傾印;observed = 記錄到的 0x14b78 引數
for tag, entry, post, observed in (("turn1", "kc_u_t1r1_6", "kc_u_t1r1_10", (1, 7)), ("turn2", "kc_u_t2_17", "kc_u_t2_22", (1, 7))):
    us = units((D / f"{entry}.bin").read_bytes())
    assert us[7]["f5"] & 1 and us[7]["hp"] == 0 and (us[7]["x"], us[7]["y"]) == (1, 7), (tag, us[7])
    code = nearest(us, 13, set())
    # 對照規則:「真的陣亡時座標被清掉/移出地圖」→ 屍體不可能是最近的候選,等於把所有 HP 0 且 bit0 的單位剔除
    rival = nearest(us, 13, {u["i"] for u in us if u["f5"] & 1 and u["hp"] == 0})
    assert (code[0], code[1]) == observed and (rival[0], rival[1]) != observed, (tag, code, rival)
    p = units((D / f"{post}.bin").read_bytes())
    runs[tag] = {"actor": 13, "actor_xy": [us[13]["x"], us[13]["y"]], "observed_0x14b78_target": list(observed),
                 "corpse_7": {"xy": [us[7]["x"], us[7]["y"]], "f5": us[7]["f5"], "hp": us[7]["hp"]},
                 "predicted_corpse_kept": {"xy": [code[0], code[1]], "unit": code[2], "distance": code[3]},
                 "rival_corpse_cleared": {"xy": [rival[0], rival[1]], "unit": rival[2], "distance": rival[3]},
                 "actor_moved_to": [p[13]["x"], p[13]["y"]]}
    print(tag, "code", code, "rival", rival, "moved", runs[tag]["actor_moved_to"])

# 被真的打死的兩個單位(NPC #7 被敵人 #11 打死、敵人 #12 被索爾打死):整筆記錄與設定後相比只有這些位移改變
last = (D / "kc_u_t2_22.bin").read_bytes()
changed = {}
for u in (7, 12):
    a, b = pre[u * 80:u * 80 + 80], last[u * 80:u * 80 + 80]
    changed[str(u)] = [[hex(i), a[i], b[i]] for i in range(80) if a[i] != b[i]]
    assert not {0, 1} & {i for i in range(80) if a[i] != b[i]}, (u, changed[str(u)])
assert [c[0] for c in changed["7"]] == ["0x5", "0x26", "0x40"], changed
print("changed", changed)

EVI.write_bytes((json.dumps({
    "note": "DOSBox-X 斷點停點與單位表傾印;FD2.EXE md5 33464c81e6a364fd0660141139aa8e6e。第 1 章戰場第 1 回合:NPC #7 在 (1,7)(HP 1、DP 0、麻痺 3),"
            "敵人 #11 在 (2,7)(HP/DP 999),敵人 #13 在 (1,1);活著的我方與 NPC 都在曼哈頓距離 >= 30 外。敵人回合 #11 以 0x14b78(2,7,11,0) 原地攻擊並真的打死 #7,"
            "死亡旗標由 0x1db65 內 0x1dd4c(演出後的迴圈)寫入;之後 #13 停在 0x14121 入口 → 0x141cd(回 0)→ 0x13e9c → 0x14b78(1,7,13,0)。"
            "第 2 回合([0x53bef] = 2)索爾打死敵人 #12,#13 再次 0x14121 回 0 → 0x14b78(1,7,13,0)。rival_corpse_cleared 是「真的陣亡時座標被清掉」的對照規則。"
            "0x1dc61(沒有新死者時的捷徑迴圈)在之後每次呼叫都對 HP 0 的 #7 / #12 再寫一次 +5 = 1。",
    "runs": runs,
    "killed_record_changes_vs_setup": changed,
    "death_flag_writes": [
        {"turn": 1, "at": "0x1dd4c", "unit": 7, "after": "敵人 #11 攻擊"},
        {"turn": 1, "at": "0x1dc61", "unit": 7, "after": "後續行動(已是 bit0,再寫一次)"},
        {"turn": 2, "at": "0x1dd4c", "unit": 12, "after": "索爾攻擊"},
        {"turn": 2, "at": "0x1dc61", "unit": 7, "after": "後續行動"},
    ],
}, ensure_ascii=False, indent=1) + "\n").encode("utf-8"))
print("evidence ok")
