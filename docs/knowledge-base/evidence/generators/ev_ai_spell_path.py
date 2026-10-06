"""AI 施法路徑動態驗證的證據 JSON 與登錄表更新(doc98 續五十二)。"""
# 移植說明:原腳本後段是一次性更新 docs/data/function_names.json 的補丁(已套用並提交),不屬於證據重算,移植時刪除。
import json
import re
import struct
from pathlib import Path

from _evpaths import GAME, GEN_DIR, ROOT, out_path, require_inputs  # noqa: E402,F401
require_inputs(__file__)
import _console  # noqa: E402
EVI = out_path("ai_spell_path_20260929.json")
D = ROOT / ".wsl_build" / "ctr"

# 斷點停點由當時 bp_log.sh 的終端輸出(原始紀錄,見 _console.py)解析。停點行:
#   函式入口 "stop N: EIP=<執行期> <名稱> ret=<執行期> (static <靜態>) arg1=<十進位> arg2=<十進位> ESI=.. EDX=.."
#   0x1c7fe / 0x1c87f "stop N: EIP=<執行期> <名稱>  ESI=.. EDX=.."(ESI=base / 目標記錄位址,EDX=命中 / 傷害亂數)
# 函式名稱依入口位址(執行期 = 靜態 + 0x19c000)對到證據沿用的名稱,不採用終端上的暫名。
DELTA = 0x19C000
UNITS, REC = 0x26BDC8, 0x50  # 單位表 [0x53a45] 的位址與每筆記錄長度
CASTER = 11  # 盜賊;下面核對每回合唯一一次 ai_spell_execute 的 arg1 就是它
ENTRY = {0x15311: "ai_spell_execute", 0x2FF01: "0x2ff01", 0x1C75E: "spell_damage_resolve"}
_ARGS = re.compile(r" ret=(0x[0-9a-f]+) \(static (0x[0-9a-f]+)\) arg1=(\d+) arg2=(\d+) ")
# 每回合:設定(印出 / 讀回施法前狀態)、停點紀錄、施法後傾印(印出前後 HP / MP)三次終端輸出
RUNS = {
    "C1": {"setup": "20260929T152625_toolu_01J8Cy4woDUWWixEu6YTuAoU", "log": "20260929T152801_toolu_01FAiVPthATfdDVBtKrCTRxG",
           "post_print": "20260929T152822_toolu_017ub1ji95mkXhEuRxnvtUDh"},
    "C2": {"setup": "20260929T153047_toolu_01LfMBxLVmoZybZfY7t9A3Qh", "log": "20260929T153221_toolu_01Q2yRDe3bjnLbZpaSCrxCRy",
           "post_print": "20260929T153239_toolu_018jSC3D1yMzzVMj8Wv7daWk"},
}


def bp_stops(stem: str) -> list[dict]:
    """解析一次終端輸出裡所有 bp_log.sh 停點行,轉成證據的停點格式。"""
    out = []
    for line in _console.load(stem)[1].splitlines():
        if not line.startswith("stop "):
            continue
        (s,) = _console.stops(line)
        eip = s["EIP"] - DELTA
        if eip in ENTRY:
            m = _ARGS.search(line)
            assert m and int(m[1], 16) - DELTA == int(m[2], 16), (stem, line)
            out.append({"function": ENTRY[eip], "return_static": m[2], "arg1": int(m[3]), "arg2": int(m[4])})
        elif eip == 0x1C7FE:
            out.append({"function": "0x1c7fe", "esi_base": s["ESI"], "edx_hit_roll": s["EDX"]})
        elif eip == 0x1C87F:
            out.append({"function": "0x1c87f", "esi_target_record": hex(s["ESI"]), "edx_damage_roll": s["EDX"]})
        else:
            raise AssertionError((stem, line))
    return out


rounds = {
    "C1": {"flag_53af9": 1, "pre": "c_pre1.bin", "post": "c_post1.bin"},
    "C2": {"flag_53af9": 0, "pre": "c_pre2.bin", "post": "c_post2.bin"},
}
for tag, r in rounds.items():
    smeta, stext = _console.load(RUNS[tag]["setup"])
    # 設定那次的指令設 [0x53af9] 並傾印施法前單位表;C2 另有讀回值(C1 沒有讀回,只能比對指令)
    assert f"SM 0170:1efaf9 {r['flag_53af9']:02x}" in smeta["cmd"] and f"--out $D/{r['pre']}" in smeta["cmd"], tag
    assert re.findall(r"(?m)^raw: ([0-9a-f]{2})$", stext) == ([] if tag == "C1" else [f"{r['flag_53af9']:02x}"]), tag
    lmeta = _console.load(RUNS[tag]["log"])[0]
    assert [a[0] for a in _console.invocations(lmeta["cmd"], "bp_log.sh")] == [tag], tag
    r["stops"] = bp_stops(RUNS[tag]["log"])
    # 命中 / 傷害亂數停點讀到的 base 與亂數;受擊者 = 0x1c87f 時 ESI 指向的單位記錄
    (hit,) = [s for s in r["stops"] if s["function"] == "0x1c7fe"]
    (roll,) = [s for s in r["stops"] if s["function"] == "0x1c87f"]
    (sdr,) = [s for s in r["stops"] if s["function"] == "spell_damage_resolve"]
    # 施法者 = 本回合唯一一次 ai_spell_execute 的 arg1
    assert [s["arg1"] for s in r["stops"] if s["function"] == "ai_spell_execute"] == [CASTER], (tag, r["stops"])
    t, rem = divmod(int(roll["esi_target_record"], 16) - UNITS, REC)
    assert rem == 0 and 0 <= t < 21, (tag, roll)
    # 交叉檢查(終端輸出內部):目標記錄位址換算的單位 = spell_damage_resolve 的 arg1(目標);arg2 = 法術 8
    assert (sdr["arg1"], sdr["arg2"]) == (t, 8), (tag, sdr, t)
    r.update({"target": t, "base": hit["esi_base"], "damage_roll": roll["edx_damage_roll"]})

out = {}
_PRE = re.compile(r"(?m)^(\d+) \((\d+), (\d+)\) f5 (0x[0-9a-f]+) HP (\d+) MP (\d+) (\d+) bits ([0-9a-f]{10}) slot0 (0x[0-9a-f]+) (\d+)$")
_ROW = re.compile(r"(?m)^(\d+) (?:side \d+ )?\((\d+), (\d+)\) -> \((\d+), (\d+)\) .*?HP (\d+) -> (\d+) MP (\d+) -> (\d+)\b")
for tag, r in rounds.items():
    pre = (D / r["pre"]).read_bytes()
    post = (D / r["post"]).read_bytes()
    w = lambda b, i, o: struct.unpack_from("<H", b, i * 80 + o)[0]
    t = r["target"]
    dmg = r["base"] * 9 // 10 + r["damage_roll"] * r["base"] // 1000
    hp0, hp1 = w(pre, t, 0x40), w(post, t, 0x40)
    assert hp1 == max(0, hp0 - dmg), (tag, hp0, hp1, dmg)
    assert w(pre, CASTER, 0x44) - w(post, CASTER, 0x44) == 24, tag
    rec = (D / r["pre"]).read_bytes()[CASTER * 80:(CASTER + 1) * 80]
    assert rec[0x1A:0x1F].hex() == "0001000000" and rec[0xA] == 0, tag
    # 交叉檢查(終端輸出 ↔ 傾印):施法後傾印那次印出的前後座標 / HP / MP 必須等於兩份傾印,且含施法者與目標
    pmeta, ptext = _console.load(RUNS[tag]["post_print"])
    assert f"--out $D/{r['post']}" in pmeta["cmd"] and r["pre"] in pmeta["cmd"], tag
    rows = {int(m[0]): [int(v) for v in m[1:]] for m in _ROW.findall(ptext)}
    assert {CASTER, t} <= set(rows), (tag, sorted(rows))
    for i, v in rows.items():
        assert v == [pre[i * 80], pre[i * 80 + 1], post[i * 80], post[i * 80 + 1], w(pre, i, 0x40), w(post, i, 0x40),
                     w(pre, i, 0x44), w(post, i, 0x44)], (tag, i, v)
    if tag == "C1":
        # C1 設定那次在傾印 c_pre1.bin 後立即印出 #0、#5、#6、#11 的記錄(含盜賊的法術位元與 slot0)
        pre_rows = _PRE.findall(_console.load(RUNS[tag]["setup"])[1])
        assert [int(m[0]) for m in pre_rows] == [0, 5, 6, 11], pre_rows
        for m in pre_rows:
            i, b = int(m[0]), pre[int(m[0]) * 80:int(m[0]) * 80 + 80]
            assert [int(m[1]), int(m[2]), int(m[3], 16), int(m[4]), int(m[5]), int(m[6]), m[7], int(m[8], 16), int(m[9])] == \
                [b[0], b[1], b[5], w(pre, i, 0x40), w(pre, i, 0x44), w(pre, i, 0x46), b[0x1A:0x1F].hex(), b[0xA], b[0xB]], (tag, i)
    out[tag] = {
        "flag_53af9": r["flag_53af9"], "breakpoint_stops": r["stops"],
        "caster": {"unit": CASTER, "spell_bits": rec[0x1A:0x1F].hex(), "weapon_slot0_flag": rec[0xA],
                   "mp_before": w(pre, CASTER, 0x44), "mp_after": w(post, CASTER, 0x44), "xy": [rec[0], rec[1]]},
        "target": {"unit": t, "xy": [pre[t * 80], pre[t * 80 + 1]], "hp_before": hp0, "hp_after": hp1, "predicted_damage": dmg},
    }
EVI.write_bytes((json.dumps({
    "note": "DOSBox-X 斷點停點與施法前後的單位記錄;FD2.EXE md5 33464c81e6a364fd0660141139aa8e6e。盜賊 #11 的已學法術位元欄設為只有法術 8(聖光彈)、"
            "MP 100、拿掉武器(slot0 旗標 0),讓 AI 只能施法。predicted_damage = base*9//10 + roll*base//1000,HP 下限 0。",
    "rounds": out,
}, ensure_ascii=False, indent=1) + "\n").encode("utf-8"))
print("evidence ok", {k: (v["target"]["hp_before"], v["target"]["hp_after"]) for k, v in out.items()})
