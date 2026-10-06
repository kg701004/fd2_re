"""AI 備援移動 0x13e9c(最近單位,不排除 +5 bit0)動態驗證:離線重算、證據 JSON、登錄表更新(doc98 續六十)。"""
# 移植說明:原腳本後段是一次性更新 docs/data/function_names.json 的補丁(已套用並提交),不屬於證據重算,移植時刪除。
import json
from pathlib import Path

from _evpaths import GAME, GEN_DIR, ROOT, out_path, require_inputs  # noqa: E402,F401
require_inputs(__file__)
D = ROOT / ".wsl_build" / "ctr"
EVI = out_path("ai_move_nearest_20260930.json")
ACTOR = 13  # 施動的敵人;下面核對它是兩輪中唯一移動過的 +6 == 0 單位


def units(b: bytes) -> list[dict]:
    return [{"i": i, "x": b[i * 80], "y": b[i * 80 + 1], "f5": b[i * 80 + 5], "side": b[i * 80 + 6]} for i in range(len(b) // 80)]


def nearest(us: list[dict], actor: int, a2: int, skip_dead: bool) -> tuple:
    """0x13e9c:a2 為 0 取 +6 != 0、否則取 +6 == 0 的單位,曼哈頓距離嚴格較小才換(同距保留序號小者);skip_dead 是對照用的另一種規則。"""
    ax, ay = us[actor]["x"], us[actor]["y"]
    best, bd = None, 0xFFFF
    for u in us:
        if (u["side"] != 0) != (a2 == 0):
            continue
        if skip_dead and u["f5"] & 1:
            continue
        d = abs(ax - u["x"]) + abs(ay - u["y"])
        if d < bd:
            best, bd = u, d
    return (best["x"], best["y"], best["i"], bd)


# R1:0x13e9c 入口時 NPC 已走完 NPC 回合 → 用 R1 結束時的位置(我方與屍體沒動),#13 用起點 (1,1)
b1 = bytearray((D / "mv_post_m1.bin").read_bytes())
pre1 = (D / "mv_pre_m1.bin").read_bytes()
b1[ACTOR * 80:ACTOR * 80 + 2] = pre1[ACTOR * 80:ACTOR * 80 + 2]
u1 = units(bytes(b1))
u2 = units((D / "mv_u_m2_10.bin").read_bytes())  # R2 在 0x13e9c 入口的傾印
p1, p2 = (D / "mv_post_m1.bin").read_bytes(), (D / "mv_post_m2.bin").read_bytes()
# 施動者 = 兩輪施動前 → 施動後傾印中唯一座標改變的 +6 == 0(敵方)單位
for before, after in ((units(pre1), units(p1)), (u2, units(p2))):
    moved = [u["i"] for u, v in zip(before, after) if u["side"] == 0 and (u["x"], u["y"]) != (v["x"], v["y"])]
    assert moved == [ACTOR], moved
runs = {}
for tag, us, observed_move in (("R1", u1, (1, 7)), ("R2", u2, (22, 15))):
    code = nearest(us, ACTOR, 0, skip_dead=False)
    rival = nearest(us, ACTOR, 0, skip_dead=True)
    assert (code[0], code[1]) == observed_move, (tag, code, observed_move)
    runs[tag] = {"actor": ACTOR, "actor_xy": [us[ACTOR]["x"], us[ACTOR]["y"]], "observed_0x14b78_target": list(observed_move),
                 "predicted_including_dead": {"xy": [code[0], code[1]], "unit": code[2], "distance": code[3], "dead": bool(us[code[2]]["f5"] & 1)},
                 "rival_excluding_dead": {"xy": [rival[0], rival[1]], "unit": rival[2], "distance": rival[3]}}
    print(tag, "code", code, "rival", rival)
assert runs["R1"]["predicted_including_dead"]["dead"] and runs["R1"]["rival_excluding_dead"]["xy"] != [1, 7]
runs["R1"]["actor_moved_to"] = [p1[ACTOR * 80], p1[ACTOR * 80 + 1]]
runs["R2"]["actor_moved_to"] = [p2[ACTOR * 80], p2[ACTOR * 80 + 1]]
EVI.write_bytes((json.dumps({
    "note": "DOSBox-X 斷點停點與單位表傾印;FD2.EXE md5 33464c81e6a364fd0660141139aa8e6e。敵人 #13 在 (1,1),附近沒有可打的目標(物理 P = 0),"
            "活著的我方與 NPC 都在曼哈頓距離 >= 30 外。兩輪都停在:0x14121 入口 → 0x141cd(找不到,回 0)→ 0x13e9c 入口 → 0x14b78(目標 x, y, 13, 0),"
            "返回位址 0x13fb1。R1 的 NPC #7 設 +5 bit0(屍體)在 (1,7);R2 把屍體移到 (26,19)。rival_excluding_dead 是「跳過 +5 bit0」的另一種規則,R1 兩者不同。",
    "runs": runs,
}, ensure_ascii=False, indent=1) + "\n").encode("utf-8"))
print("evidence ok")
