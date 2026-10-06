"""法術 9(咒殺)呈現分流動態驗證的證據 JSON 與登錄表更新(doc98 續五十五)。"""
# 移植說明:原腳本後段是一次性更新 docs/data/function_names.json 的補丁(已套用並提交),不屬於證據重算,移植時刪除。
import json
import re
import struct
from pathlib import Path

from _evpaths import GAME, GEN_DIR, ROOT, out_path, require_inputs  # noqa: E402,F401
require_inputs(__file__)
import _console  # noqa: E402
EVI = out_path("spell9_path_20260930.json")
D = ROOT / ".wsl_build" / "ctr"
RESIST = [10, 10, 10, 10, 7, 7, 10, 10, 10, 10, 9, 10, 5, 5, 8, 10, 6, 8, 10, 9, 5, 5, 10, 8, 8]  # 0x51f96 dword 表(靜態)
VALUE, HIT = 999, 50  # 法術列 0x619fd + 9*7 = e7 03 32 03 00 1e 00


def w(b: bytes, i: int, o: int) -> int:
    return struct.unpack_from("<H", b, i * 80 + o)[0]


# 斷點停點由當時 s9_log.sh 的終端輸出(原始紀錄,見 _console.py)解析。s9_log.sh 的停點行:
#   函式入口 "stop N: <名稱> ret=<靜態返回位址> a1=<十進位> a2=<十進位>"
#   "stop N: 0x1c7fe base=<十進位> hit_roll=<十進位>"、"stop N: 0x1c87f dmg_roll=<十進位>"
NAME = {"handler 0x214ad": "command_handler_9 0x214ad", "spell_cast_scene(0x2ff01)": "spell_cast_scene 0x2ff01",
        "ai_spell_execute": "ai_spell_execute", "spell_damage_resolve": "spell_damage_resolve"}
# 玩家指令選單(返回位址 0x1d480)呼叫 handler 0x214ad 的停點:原證據只記函式與返回位址,
# 終端輸出同一行的 a1=1 a2=1 沒有收錄進證據(維持原格式)
PLAYER_MENU_RET = "0x1d480"
_ENTRY = re.compile(r"^stop \d+: (.+?) ret=(0x[0-9a-f]+) a1=(\d+) a2=(\d+)$")
_HIT = re.compile(r"^stop \d+: 0x1c7fe base=(\d+) hit_roll=(\d+)$")
_DMG = re.compile(r"^stop \d+: 0x1c87f dmg_roll=(\d+)$")
# 每回合:s9_setup.sh 那次("setup done <標籤> flag=N")、s9_log.sh 那次、印出傾印內容那次的終端輸出
# A1 沒有重新設定:沿用同一次啟動裡 P2 的 s9_setup.sh(之間沒有 teardown / 重新啟動)
RUNS = {
    "P1": {"setup": ("p1", "20260930T013318_toolu_01KD9sJaRQWEGn4yYXzksot7"), "log": "20260930T013401_toolu_01T3d7ziGoRTHCi8B6WgRyTq",
           "dump_print": None},
    "P2": {"setup": ("p2", "20260930T013831_toolu_013s7XZv1zg8zbhSVC3Hr6w5"), "log": "20260930T013831_toolu_013s7XZv1zg8zbhSVC3Hr6w5",
           "dump_print": "20260930T014039_toolu_01Wee3sVsJcCFTvKKLBnBvgu"},
    "A1": {"setup": ("p2", "20260930T013831_toolu_013s7XZv1zg8zbhSVC3Hr6w5"), "log": "20260930T014013_toolu_012bXS3Ay1S1HqQbikeLfW6u",
           "dump_print": "20260930T014039_toolu_01Wee3sVsJcCFTvKKLBnBvgu"},
    "A2": {"setup": ("a2", "20260930T014249_toolu_015Ga1xJhodH5Eo2z7ZuFmBN"), "log": "20260930T014249_toolu_015Ga1xJhodH5Eo2z7ZuFmBN",
           "dump_print": "20260930T014249_toolu_015Ga1xJhodH5Eo2z7ZuFmBN"},
}


def calls(cmd: str, script: str) -> list[list[str]]:
    """指令裡每一次呼叫 `script` 的參數;這幾次的指令以換行分隔,先逐行切開再交給 _console.invocations。"""
    return [a for line in cmd.splitlines() for a in _console.invocations(line, script)]


def s9_stops(stem: str) -> list[list]:
    """解析一次終端輸出裡所有 s9_log.sh 停點行,轉成證據的停點格式。"""
    out = []
    for line in _console.load(stem)[1].splitlines():
        if not line.startswith("stop "):
            continue
        if m := _ENTRY.match(line):
            s = [NAME[m[1]], f"ret {m[2]}"]
            if not (m[1] == "handler 0x214ad" and m[2] == PLAYER_MENU_RET):
                s += [int(m[3]), int(m[4])]
        elif m := _HIT.match(line):
            s = ["0x1c7fe", f"base {m[1]}", f"hit_roll {m[2]}"]
        elif m := _DMG.match(line):
            s = ["0x1c87f", f"dmg_roll {m[1]}"]
        else:
            raise AssertionError((stem, line))  # 例如 "other EIP=..." —— 不略過未預期的停點
        out.append(s)
    return out


rounds = {
    "P1": {"caster": 1, "flag": 0, "pre": "s9_pre_p1", "post": None, "target": 11,
           "note": "施法後遊戲回到標題畫面(所有 NPC 都設了 +5 bit0),沒有施法後傾印"},
    "P2": {"caster": 1, "flag": 0, "pre": "s9_pre_p2", "post": "s9_pre_a1", "target": 11},
    "A1": {"caster": 11, "flag": 0, "pre": "s9_pre_a1", "post": "s9_post_a1", "target": 1},
    "A2": {"caster": 11, "flag": 1, "pre": "s9_pre_a2", "post": "s9_post_a2", "target": 1},
}
for tag, r in rounds.items():
    stag, sstem = RUNS[tag]["setup"]
    smeta, stext = _console.load(sstem)
    assert calls(smeta["cmd"], "s9_setup.sh") == [[str(r["flag"]), stag]], tag
    # 交叉檢查(終端輸出 ↔ 傾印):s9_setup.sh 讀回的 [0x53af9] = 同一次寫出的 s9_flag_<標籤>.bin = 本回合設定
    assert re.findall(rf"(?m)^setup done {stag} flag=(\d+)$", stext) == [str(r["flag"])], tag
    assert (D / f"s9_flag_{stag}.bin").read_bytes() == bytes([r["flag"]]), tag
    lmeta = _console.load(RUNS[tag]["log"])[0]
    assert [a[0] for a in calls(lmeta["cmd"], "s9_log.sh")] == [tag.lower()], tag
    r["stops"] = s9_stops(RUNS[tag]["log"])
    (hit,) = [s for s in r["stops"] if s[0] == "0x1c7fe"]
    dmg_stops = [s for s in r["stops"] if s[0] == "0x1c87f"]
    assert len(dmg_stops) <= 1, tag
    # 交叉檢查(終端輸出內部):第一個函式入口停點(玩家 handler 0x214ad 或 ai_spell_execute)的 a1 = 本回合施法者;
    # 玩家選單那次的 a1 沒有收錄進證據,這裡直接讀終端輸出原文
    first = next(m for line in _console.load(RUNS[tag]["log"])[1].splitlines() if (m := _ENTRY.match(line)))
    assert int(first[3]) == r["caster"], (tag, first[0])
    (sdr,) = [s for s in r["stops"] if s[0] == "spell_damage_resolve"]
    # 交叉檢查(終端輸出內部):spell_damage_resolve 的 (目標, 法術) = (本回合目標, 9)
    assert sdr[2:] == [r["target"], 9], (tag, sdr)
    r.update({"base": int(hit[1].split()[1]), "hit_roll": int(hit[2].split()[1]),
              "dmg_roll": int(dmg_stops[0][1].split()[1]) if dmg_stops else None})

_PRINT = re.compile(r"(?m)^(s9_[a-z0-9_]+) 悠妮 HP (\d+)\b.*?\| 盜賊 .*?HP (\d+) MP (\d+) \|")
out = {}
for tag, r in rounds.items():
    pre = (D / f"{r['pre']}.bin").read_bytes()
    t, c = r["target"], r["caster"]
    cls = pre[t * 80 + 0x20]
    base = VALUE * RESIST[cls - 1] // 10
    # 交叉檢查(終端輸出 ↔ 傾印):0x1c7fe 停點讀到的 base = 依施法前傾印裡目標職業查魔抗表算出的值
    assert base == r["base"], (tag, base)
    hit = r["hit_roll"] < HIT
    assert hit == (r["dmg_roll"] is not None), tag
    dmg = base * 9 // 10 + r["dmg_roll"] * base // 1000 if hit else 0
    rec = {"flag_53af9": r["flag"], "caster": c, "target": t, "target_class": cls, "breakpoint_stops": r["stops"],
           "base_predicted": base, "hit_roll": r["hit_roll"], "hit": hit, "damage_predicted": dmg}
    if r["post"]:
        post = (D / f"{r['post']}.bin").read_bytes()
        hp0, hp1 = w(pre, t, 0x40), w(post, t, 0x40)
        assert hp0 - hp1 == dmg, (tag, hp0, hp1, dmg)
        assert w(pre, c, 0x44) - w(post, c, 0x44) == 30, tag
        # 交叉檢查(終端輸出 ↔ 傾印):當時印出的施法前後 悠妮 HP、盜賊 HP / MP 必須等於兩份傾印
        printed = {m[0]: [int(v) for v in m[1:]] for m in _PRINT.findall(_console.load(RUNS[tag]["dump_print"])[1])}
        for ph, b in ((r["pre"], pre), (r["post"], post)):
            assert printed.get(ph) == [w(b, 1, 0x40), w(b, 11, 0x40), w(b, 11, 0x44)], (tag, ph, printed.get(ph))
        rec.update({"target_hp": [hp0, hp1], "caster_mp": [w(pre, c, 0x44), w(post, c, 0x44)]})
    if "note" in r:
        rec["note"] = r["note"]
    out[tag] = rec
    print(tag, rec.get("target_hp"), dmg)

EVI.write_bytes((json.dumps({
    "note": "DOSBox-X 斷點停點(返回位址為靜態位址)與施法前後單位表傾印;FD2.EXE md5 33464c81e6a364fd0660141139aa8e6e。法術 9 列 = 999 / 命中 50 / "
            "距離 3 / 範圍 0 / MP 30。base_predicted = 999 × 魔抗表 0x51f96[職業-1] / 10;命中 = 亂數 < 50;damage = base*9//10 + roll*base//1000。"
            "P1、P2 是 悠妮 #1 對盜賊 #11,A1、A2 是盜賊 #11(只會法術 9、拿掉武器)對 悠妮 #1。",
    "rounds": out,
}, ensure_ascii=False, indent=1) + "\n").encode("utf-8"))
print("evidence ok")
