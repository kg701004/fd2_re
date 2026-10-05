"""AI 物理/法術/道具勝者選擇(0x14ef0 的 0x14f62..0x15050)動態驗證的證據 JSON 與登錄表更新(doc98 續五十七)。

P、S、I、法術、物理目標與 d 直接由 0x14f62 停點的傾印(mix_g / mix_d)讀出;單位(ESI)、bit(EBP)與停在哪個執行函式由當時 mix_log.sh 的終端輸出(原始紀錄,見 _console.py)解析;
同一行印出的 P/S/I/法術/物理目標/d 必須等於該停點的傾印(證明停點編號與傾印檔對得上)。
"""
# 移植說明:原腳本後段是一次性更新 docs/data/function_names.json 的補丁(已套用並提交),不屬於證據重算,移植時刪除。
import json
import re
import struct
from pathlib import Path

from _evpaths import GAME, GEN_DIR, ROOT, out_path, require_inputs  # noqa: E402,F401
require_inputs(__file__)
import _console  # noqa: E402
D = ROOT / ".wsl_build" / "ctr"
EVI = out_path("ai_action_choice_20260930.json")
SPELL_VALUE = {8: 440, 13: 70}  # 法術列 +0(靜態 0x619fd + id*7)

# (停點, 單位, bit40, 之後停下的執行函式):由當時 mix_log.sh 的終端輸出(原始紀錄,見 _console.py)解析
CONSOLE = "20260930T022701_toolu_01C7HRyy34FyazDrSd6xhTat"
_meta, _text = _console.load(CONSOLE)
(_args,) = _console.invocations(_meta["cmd"], "mix_log.sh")
TAG = _args[0]  # mix_log.sh 的參數 = 傾印檔名標籤(mix_g_<標籤>_<停點>.bin / mix_d_<標籤>_<停點>.bin)
assert TAG == "m1", _args
_DECIDE = re.compile(r"stop (\d+): decide unit=(\d+) bit40=(\d+) "
                     r"P=(-?\d+) S=(-?\d+) I=(-?\d+) spell=(-?\d+) ptarget=(-?\d+) d=(-?\d+)")
_EXEC = re.compile(r"stop (\d+): -> (physical|spell|item) 0x([0-9a-f]+)")
_EXEC_ADDR = {"physical": "1548e", "spell": "15311", "item": "15055"}  # 靜態位址(執行期 = 靜態 + 0x19c000)
LOG, CON_VALUES = [], {}
_pending = None
for _line in _text.splitlines():
    if not _line.startswith("stop "):
        continue
    if (_m := _DECIDE.fullmatch(_line)) is not None:
        assert _pending is None, _line  # 每個決策點之後必須先停在一個執行函式
        _n, _unit, _bit, *_vals = map(int, _m.groups())
        _pending, CON_VALUES[_n] = (_n, _unit, _bit), tuple(_vals)
        continue
    _m = _EXEC.fullmatch(_line)
    # 不接受 other 停點或前面沒有決策點的執行函式(不猜對應)
    assert _m is not None and _pending is not None and _EXEC_ADDR[_m[2]] == _m[3], _line
    LOG.append((*_pending, _m[2]))
    _pending = None
assert _pending is None and len(LOG) == 8, LOG
DESIGN = {11: "S > P", 13: "P == S、法術 < 11、440 < d", 14: "P(0x12)> S", 15: "P == S、法術 < 11、440 < d 不成立(d = 440)",
          16: "P == S、法術 >= 11、bit 0x40 = 1", 17: "P == S、法術 >= 11、bit 0x40 = 0", 12: "(未設計)P > S = 0", 18: "(未設計)P > S = 0"}


def decide(p: int, s: int, i: int, spell: int, d: int, bit: int) -> str:
    """0x14f62..0x15050 的靜態規則。"""
    if p < 6 and s < 6 and i < 6:
        return "none"
    if p > s and p > i:
        return "physical"
    if p == s and p > i:
        if spell < 0xB:
            return "physical" if SPELL_VALUE[spell] < d else "spell"
        return "physical" if bit else "spell"
    if p == i and p > s:
        return "physical" if bit else "item"
    if s > p and s >= i:
        return "spell"
    if i > p and i > s:
        return "item"
    return "none"


rows = []
for n, unit, bit, got in LOG:
    g = (D / f"mix_g_{TAG}_{n}.bin").read_bytes()
    d = struct.unpack("<i", (D / f"mix_d_{TAG}_{n}.bin").read_bytes()[:4])[0]
    v = lambda o: struct.unpack_from("<i", g, o - 0x23)[0]
    p, s, i, spell, pt = v(0x4F), v(0x23), v(0x33), v(0x2F), v(0x4B)
    # 同一行終端輸出印出的值必須等於該停點的傾印(證明這段輸出與傾印是同一次執行、停點編號對得上)
    assert CON_VALUES[n] == (p, s, i, spell, pt, d), (n, CON_VALUES[n], (p, s, i, spell, pt, d))
    pred = decide(p, s, i, spell, d, bit)
    assert pred == got, (unit, p, s, i, spell, d, bit, pred, got)
    rows.append({"stop": n, "unit": unit, "design": DESIGN[unit], "P_53c4f": p, "S_53c23": s, "I_53c33": i, "spell_53c2f": spell,
                 "physical_target_53c4b": pt, "d_ap_minus_target_dp": d, "bit40_34": bit, "predicted": pred, "executor_observed": got})
    print(unit, p, s, i, spell, d, bit, pred)

pre, post = (D / "mix_pre.bin").read_bytes(), (D / "mix_post.bin").read_bytes()
w = lambda b, i, o: struct.unpack_from("<H", b, i * 80 + o)[0]
effects = {str(i): {"xy": [[pre[i * 80], pre[i * 80 + 1]], [post[i * 80], post[i * 80 + 1]]], "hp": [w(pre, i, 0x40), w(post, i, 0x40)],
                    "mp": [w(pre, i, 0x44), w(post, i, 0x44)]} for i in (0, 1, 2, 3, 4, 5, 6, 11, 12, 13, 14, 15, 16, 17, 18)}
# 施法者 MP:法術 8 扣 24、法術 13 扣 3;選物理的不扣
for u, cost in ((11, 24), (15, 24), (17, 3), (13, 0), (14, 0), (16, 0)):
    assert w(pre, u, 0x44) - w(post, u, 0x44) == cost, u
assert w(post, 18, 0x40) == 28 and w(post, 1, 0x40) < 300
EVI.write_bytes((json.dumps({
    "note": "DOSBox-X 斷點停點與記憶體讀值;FD2.EXE md5 33464c81e6a364fd0660141139aa8e6e。0x14f62 停下時讀 [0x53c23..0x53c52]、[ESP](= 攻方 +0x48 - 物理目標 +0x4a)、"
            "EBP(= 攻方 +0x34 & 0x40)、ESI(單位);之後停在 0x1548e / 0x15311 / 0x15055 其中之一即為勝者。predicted 依 0x14f62..0x15050 的靜態規則。"
            "物理攻擊全部未命中(HP 不變),這不影響選擇;#15 的法術打到了 NPC 回合走進射程的 NPC #5(與 #4 同為 8 分,掃描序在前)。"
            "#12、#18 的 [0x53c2f] 是前一個單位留下的值(它們不會法術,S = 0)。",
    "decisions": rows, "effects_hp_mp": effects,
}, ensure_ascii=False, indent=1) + "\n").encode("utf-8"))
print("evidence ok")
