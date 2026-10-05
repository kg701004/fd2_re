"""休息回復(0x13fd4)動態驗證的證據 JSON 與登錄表更新(doc98 續五十九)。

停點(入口 / 回 0 / 寫入)由當時 rg_log.sh 的終端輸出(原始紀錄,見 _console.py)解析;
入口行印出的 +0x25 / +0x26 / HP / MaxHP 與寫入行印出的 MaxHP、MaxHP/5 必須等於同一停點的 rg_u_* 傾印;入口時的單位狀態由 rg_u_* 傾印讀出;前後 HP 由 rg_pre/rg_post 傾印讀出。
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
EVI = out_path("rest_recover_20260930.json")

# (輪, 入口停點, 單位, 結果停點類型, 寫入的新 HP 或 None):由當時 rg_log.sh 的終端輸出(原始紀錄,見 _console.py)解析
CONSOLE = ["20260930T040549_toolu_01M1wWxY2fJ2WjGL25LQGgxa", "20260930T041014_toolu_01Y4fkz87W32qw6LTPjESBgj"]
_ENTRY = re.compile(r"stop (\d+): rest-entry unit=(\d+) ret=(0x[0-9a-f]+) \+25=(\d+) \+26=(\d+) HP=(\d+)/(\d+)")
_REJ = re.compile(r"stop (\d+): rest-rejected \(return 0\)")
_WRITE = re.compile(r"stop (\d+): rest-write newHP=(\d+) max=(\d+) maxHP/5=(\d+)")
STOPS, CON_ENTRY, CON_WRITE = [], {}, {}
for _stem in CONSOLE:
    _meta, _text = _console.load(_stem)
    (_args,) = _console.invocations(_meta["cmd"], "rg_log.sh")
    # rg_log.sh 的第一個參數 = 輪標籤(傾印檔名 rg_u_<輪>_<停點>.bin);同一段後面可能接著換行後的其他指令,故取 [0]
    _run = _args[0]
    _pending = None
    for _line in _text.splitlines():
        if not _line.startswith("stop "):
            continue
        if (_m := _ENTRY.fullmatch(_line)) is not None:
            assert _pending is None, _line  # 每個入口之後必須先停在回 0 或寫入
            assert _m[3] == "0x13c14", _line  # 返回位址(靜態)= 模式 0 備援的呼叫點
            _pending = (_run, int(_m[1]), int(_m[2]))
            CON_ENTRY[_pending[:2]] = tuple(int(x) for x in _m.groups()[3:])
            continue
        _r, _w = _REJ.fullmatch(_line), _WRITE.fullmatch(_line)
        # 不接受 other 停點或前面沒有入口的結果停點;結果停點必須緊接在入口之後(不猜對應)
        assert _pending is not None and (_r or _w) and int((_r or _w)[1]) == _pending[1] + 1, _line
        if _r:
            STOPS.append((*_pending, "rejected", None))
        else:
            STOPS.append((*_pending, "write", int(_w[2])))
            CON_WRITE[_pending[:2]] = (int(_w[3]), int(_w[4]))
        _pending = None
    assert _pending is None, _stem
assert [s[0] for s in STOPS] == ["r1"] * 6 + ["r2"] * 6, STOPS


def rest(hp: int, mx: int, b25: int, b26: int):
    """0x13fd4 的靜態規則:HP != MaxHP 且 +0x25、+0x26 都為 0 時寫入 min(HP + MaxHP/5, MaxHP),否則回 0 不寫。"""
    if hp == mx or b25 or b26:
        return None
    return min(hp + mx // 5, mx)


rows = []
for run, n, unit, kind, newhp in STOPS:
    r = (D / f"rg_u_{run}_{n}.bin").read_bytes()
    hp, mx = struct.unpack_from("<HH", r, 0x40)
    # 終端輸出與傾印必須一致(證明這段輸出與 rg_u_* 傾印是同一次執行、停點編號對得上):
    # 入口行的 +0x25 / +0x26 / HP / MaxHP;寫入行的 MaxHP(ESI)與 MaxHP/5(EAX)
    assert CON_ENTRY[run, n] == (r[0x25], r[0x26], hp, mx), (run, n, CON_ENTRY[run, n])
    assert kind != "write" or CON_WRITE[run, n] == (mx, mx // 5), (run, n, CON_WRITE.get((run, n)))
    pred = rest(hp, mx, r[0x25], r[0x26])
    got = newhp if kind == "write" else None
    assert pred == got, (run, unit, hp, mx, r[0x25], r[0x26], pred, got)
    rows.append({"run": run, "stop": n, "unit": unit, "at_entry": {"hp": hp, "maxhp": mx, "b25": r[0x25], "b26": r[0x26]},
                 "predicted_new_hp": pred, "observed": kind, "observed_new_hp": got,
                 "round_instead_of_floor_would_give": None if pred is None else min(hp + round(mx / 5), mx)})

# 前後傾印:狀態計數與其他觀察
obs = {}
for run, pre, post in (("r1", "rg_pre", "rg_post1"), ("r2", "rg_pre2", "rg_post2")):
    a, b = (D / f"{pre}.bin").read_bytes(), (D / f"{post}.bin").read_bytes()
    obs[run] = {str(i): {"xy": [[a[i * 80], a[i * 80 + 1]], [b[i * 80], b[i * 80 + 1]]], "b25": [a[i * 80 + 0x25], b[i * 80 + 0x25]],
                         "b26": [a[i * 80 + 0x26], b[i * 80 + 0x26]],
                         "hp": [struct.unpack_from("<H", a, i * 80 + 0x40)[0], struct.unpack_from("<H", b, i * 80 + 0x40)[0]]}
                for i in (11, 13, 14, 15, 16, 17, 18)}
# 中毒:+0x25 在評分前 -1、HP -MaxHP/10;麻痺:+0x26 -1,仍非 0 時沒有進 0x13fd4
assert obs["r1"]["16"]["b25"] == [1, 0] and obs["r2"]["16"]["b25"] == [3, 2]
assert obs["r2"]["16"]["hp"] == [9, 7] and obs["r2"]["17"]["b26"] == [3, 2] and obs["r2"]["17"]["hp"] == [9, 9]
assert not any(x["unit"] == 17 for x in rows if x["run"] == "r2")
print("stops", len(rows), "ok")
EVI.write_bytes((json.dumps({
    "note": "DOSBox-X 斷點停點(0x13fd4 入口、0x14012 回 0、0x1410a 寫入)與單位表傾印;FD2.EXE md5 33464c81e6a364fd0660141139aa8e6e。"
            "左上一群沒有我方可打的敵人走模式 0 的備援(ai_choose_action 回 0 → 0x14121 → 0x13e9c 沒移動 → 0x13fd4,返回位址 0x13c14)。"
            "r1 的 #18 移動了(4,6 -> 5,9),沒有進 0x13fd4;r2 把它放到 (5,5) 後照規則回復。中毒 / 麻痺計數在評分前各減 1,"
            "r1 設 1 時到 0x13fd4 已歸 0;r2 設 3 時中毒的 #16 讀到 +0x25 = 2 被擋下,麻痺的 #17 沒有進 0x13fd4。",
    "stops": rows, "pre_post": obs,
}, ensure_ascii=False, indent=1) + "\n").encode("utf-8"))
print("evidence ok")
