"""續一百三十證據:evidence/phase_loop_no_breakpoint_calllog_20261016.json。

沒有斷點時光束炮(道具 79)八圈相位迴圈實際畫出哪幾階。DOSBox-X 呼叫紀錄(tools/dosbox/fd2_calllog_patch.py)
只列 5 個執行期 EIP,遊戲途中不下任何斷點;每筆 E 紀錄帶當下的暫存器:
  0x152a0 每圈開頭(ebx = k)、0x12117 `[0x51a93] == -1` 分支(eax = BIOS tick)、0x12132 推進 `[0x53c1f]`、
  0x12169 取換色表之前(eax = 這次畫的階)、0x152ba `redraw(1)` + `wait_ticks(1)` 之後(eax = tick、ebx = k)。
全部從 .wsl_build/lc130a_phase_eips.txt 與 FD2.EXE 重算;任何判準或預測不符就 assert 失敗。
"""
from __future__ import annotations

import hashlib
import json
import sys
from pathlib import Path

from _evpaths import GAME, ROOT, out_path, rel, require_inputs  # noqa: E402
require_inputs(__file__)
sys.path.insert(0, str(ROOT / "tools"))
import disasm_le as dl  # noqa: E402

EXE = GAME / "FD2.EXE"
LOG = ROOT / ".wsl_build" / "lc130a_phase_eips.txt"
S123 = ROOT / "docs/knowledge-base/evidence/ai_item_action_item79_flow_20261013.json"
OUT = out_path("phase_loop_no_breakpoint_calllog_20261016.json")
DELTA = 0x19C000                 # 原生 linear + DELTA = 執行期 EIP
RELOC = 0x1EC000                 # 指向 obj2 的位移:執行期 = 檔案內值 + 0x50000 + DELTA
# 原生位址 -> (說明, 指令內 obj2 位移所在的 byte 位置)
SITES = {
    0x152A0: ("相位迴圈每圈開頭 mov [0x53c1f], ebx(ebx = k)", (2,)),
    0x12117: ("draw_terrain_layer [0x51a93] == -1 分支 sub eax, [0x539f4](eax = BIOS tick)", (2,)),
    0x12132: ("推進 inc [0x53c1f]", (2, 8)),
    0x12169: ("取換色表 movzx eax, byte [eax + 0x51a97](eax = 這次畫的階)", (3, 9)),
    0x152BA: ("inc ebx(redraw(1) + wait_ticks(1) 之後;eax = tick、ebx = k)", (8,)),
}
E_START, E_TICK, E_ADV, E_DRAW, E_END = (a + DELTA for a in (0x152A0, 0x12117, 0x12132, 0x12169, 0x152BA))


def md5(p: Path) -> str:
    return hashlib.md5(p.read_bytes()).hexdigest()


def sha(p: Path) -> str:
    return hashlib.sha256(p.read_bytes()).hexdigest()


# ---- 讀紀錄 ----
header = None
recs: list[tuple[int, int, int, int, str]] = []     # (seq, eip, eax, ebx, code hex)
periodic: list[int] = []                           # T 行的指令數
for ln in LOG.read_text(encoding="ascii").split("\n"):
    if ln.startswith("H "):
        header = ln
    elif ln.startswith("T "):
        kind, n = ln.split(" ")[1:3]
        assert kind == "periodic", ln
        periodic.append(int(n))
    elif ln.startswith("E "):
        p = ln.split(" ")
        code = next(x[2:] for x in p if x.startswith("c="))
        recs.append((int(p[1]), int(p[2], 16), int(p[6], 16), int(p[7], 16), code))
assert header is not None and "entries=5 " in header and "dump=0 " in header, header
assert [r[0] for r in recs] == list(range(1, len(recs) + 1)), "seq 不連續"
assert {r[1] for r in recs} == {a + DELTA for a in SITES}, sorted({hex(r[1]) for r in recs})
# fd2_calllog_patch.py:`(ginstr & ((1 << 26) - 1)) == 0` 時寫一行 T periodic;T 行必須是第 1、2、3 … 個 2^26
assert periodic and periodic == [(i + 1) << 26 for i in range(len(periodic))], periodic[:3]

# ---- 靜態:紀錄裡每個 EIP 的 16 個碼位元組 = FD2.EXE 同一位置,只差指向 obj2 的位移(+0x1ec000)----
_D = EXE.read_bytes()
_M = dl.parse_le(_D)
static = {}
for nat, (desc, disp_at) in SITES.items():
    fb = bytes(dl.object_bytes(_D, _M, nat, 16))
    codes = {r[4] for r in recs if r[1] == nat + DELTA}
    assert len(codes) == 1, (hex(nat), codes)
    rb = bytes.fromhex(codes.pop())
    expect = bytearray(fb)
    for o in disp_at:
        v = int.from_bytes(fb[o:o + 4], "little") + RELOC
        expect[o:o + 4] = v.to_bytes(4, "little")
    assert rb == bytes(expect), (hex(nat), rb.hex(), bytes(expect).hex())
    assert rb != fb, hex(nat)          # 至少一個位移真的被重定位(不是拿同一份資料自比)
    static[hex(nat)] = {"desc": desc, "exe_16": fb.hex(), "runtime_16": rb.hex(), "reloc_disp_at": list(disp_at)}

# ---- 切圈 ----
loops: list[list[dict]] = []
cur = None
outside: list[list[int]] = []          # 迴圈外每次地形重畫:[tick, 推進次數]
n_draw = 0
draw_vals: dict[int, int] = {}
last_adv = None
pre_last: list[int | None] = []
pre_n: list[int] = []                  # 每個迴圈開始時已有幾次迴圈外重畫
for seq, eip, eax, ebx, _ in recs:
    if eip == E_START:
        assert cur is None, f"seq {seq}:上一圈沒有收尾"
        if ebx == 1:
            loops.append([])
            pre_last.append(last_adv)
            pre_n.append(len(outside))
        cur = {"k": ebx, "seq": seq, "ticks": [], "adv": 0, "drawn": [], "tick_after": None, "k_after": None}
    elif cur is None:
        if eip == E_TICK:
            outside.append([eax & 0xFFFF, 0])
        elif eip == E_ADV:
            outside[-1][1] += 1
            last_adv = outside[-1][0]
        elif eip == E_DRAW:
            n_draw += 1
            draw_vals[eax] = draw_vals.get(eax, 0) + 1
    elif eip == E_TICK:
        cur["ticks"].append(eax & 0xFFFF)
    elif eip == E_ADV:
        cur["adv"] += 1
    elif eip == E_DRAW:
        cur["drawn"].append(eax)
    elif eip == E_END:
        cur["tick_after"], cur["k_after"] = eax & 0xFFFF, ebx
        loops[-1].append(cur)
        cur = None
assert cur is None
assert len(loops) == 1, f"錄到 {len(loops)} 個迴圈"
out_cnt = {"tick": len(outside), "adv": sum(a for _, a in outside), "draw": n_draw}
loop = loops[0]
last0 = pre_last[0]
# 第 1 圈的「上次推進」= 進迴圈前最後一次有推進的迴圈外重畫的 tick
assert last0 == next(t for t, a in reversed(outside[:pre_n[0]]) if a), last0


def judge(drawn: list[int]) -> dict[str, bool]:
    """逐項判準;drawn 是被判的「每圈畫的階」(實測或對照假設)。"""
    j: dict[str, bool] = {}
    j["八圈 k = 1..8 依序"] = [f["k"] for f in loop] == list(range(1, 9))
    j["每圈收尾 ebx 仍是 k"] = all(f["k_after"] == f["k"] for f in loop)
    j["每圈只畫一次地形"] = all(len(f["drawn"]) == 1 for f in loop)
    j["每圈都走 -1 分支一次"] = all(len(f["ticks"]) == 1 for f in loop)
    j["畫的階 ∈ {k, k + 1}"] = all(d in (f["k"], f["k"] + 1) for d, f in zip(drawn, loop))
    j["推進 ⇔ 畫 k + 1"] = all(f["adv"] <= 1 and (f["adv"] == 1) == (d == f["k"] + 1) for d, f in zip(drawn, loop))
    ok, last = last0 is not None, last0
    for f in loop:
        t = f["ticks"][0] if f["ticks"] else None
        if t is None or last is None:
            ok = False
            continue
        if ((t - last > 2) or (t < last)) != (f["adv"] == 1):
            ok = False
        if f["adv"] == 1:
            last = t
    j["推進 ⇔ tick − 上次推進 > 2(含第 1 圈)"] = ok
    j["至少一圈畫 k + 1"] = any(d == f["k"] + 1 for d, f in zip(drawn, loop))
    adv = [i for i, f in enumerate(loop) if f["adv"] == 1]
    j["兩次推進至少隔 2 圈"] = all(b - a >= 2 for a, b in zip(adv, adv[1:]))
    j["每圈 1 ~ 2 tick"] = all(f["ticks"] and f["tick_after"] is not None and 1 <= f["tick_after"] - f["ticks"][0] <= 2
                               for f in loop)
    return j


drawn = [f["drawn"][0] for f in loop]
real = judge(drawn)
assert all(real.values()), real
ctl_k = judge([f["k"] for f in loop])                            # 對照:「沒有斷點時畫的就是 k」
ctl_shift = judge([drawn[(i + 1) % 8] for i in range(8)])        # 對照:畫的階錯開一圈
# 對照判為不符的是哪幾項逐一釘住(只要求「有一項不符」的話,錯開幾圈改了也看不出來)
assert [k for k, v in ctl_k.items() if not v] == ["推進 ⇔ 畫 k + 1", "至少一圈畫 k + 1"], ctl_k
assert [k for k, v in ctl_shift.items() if not v] == ["畫的階 ∈ {k, k + 1}", "推進 ⇔ 畫 k + 1"], ctl_shift

# 預測(量之前寫下):每圈 k 或 k + 1、至少一圈 k + 1、推進至少隔 2 圈;實測值
assert drawn == [2, 2, 4, 4, 5, 7, 7, 8], drawn
assert [f["adv"] for f in loop] == [1, 0, 1, 0, 0, 1, 0, 0]

# 與續一百二十三斷點下兩輪的比較(那兩輪停在 0x152ba,讀到的 [0x53c1f] 就是那一圈畫的階)
s123 = json.loads(S123.read_text(encoding="utf-8"))
run_a, run_b = ([r["phase_read_at_stop"] for r in run["strip"]["rows"]] for run in s123["runs"])
assert run_a == drawn, run_a
assert run_b != drawn, run_b

# 迴圈外:每次地形重畫都走 -1 分支;20 個階都出現
assert out_cnt["tick"] == out_cnt["draw"] > 0, out_cnt
assert sorted(draw_vals) == list(range(20)) and sum(draw_vals.values()) == out_cnt["draw"], draw_vals
# 迴圈外也是同一條推進規則:每次重畫推進至多一次,推進 ⇔ tick − 上次推進 > 2(tick 回繞時 t < 上次);第一次重畫沒有上次,不判
assert all(a <= 1 for _, a in outside) and out_cnt["adv"] > 0, out_cnt
_last, _bad = None, 0
for _t, _a in outside:
    if _last is not None and ((_t - _last > 2) or (_t < _last)) != (_a == 1):
        _bad += 1
    if _a:
        _last = _t
assert _bad == 0, f"迴圈外 {_bad} 次重畫不符推進規則"

ev = {
    "_meta": {"topic": "續一百三十:沒有斷點時光束炮相位迴圈畫出哪幾階(DOSBox-X 呼叫紀錄只列 5 個 EIP,途中不下斷點)",
              "exe": rel(EXE), "exe_md5": md5(EXE),
              "raw": {"path": ".wsl_build/lc130a_phase_eips.txt", "sha256": sha(LOG), "header": header,
                      "E_records": len(recs), "T_lines": len(periodic)},
              "generator": "evidence/generators/ev_s130.py(變異測試 mut_s130.py)",
              "harness": "cycles 5000(tools/dosbox_harness.sh 預設);FD2_HARNESS_CALLLOG_CAP=100000000、FD2_HARNESS_CALLLOG_DUMP=0;"
                         "第 1 章戰場,敵 #11 搬到 (19, 14)、道具欄第 2 格放道具 79,只改模擬器記憶體裡的單位資料"},
    "static_sites": static,
    "loop": {"frames": loop, "drawn": drawn, "last_advance_tick_before_loop": last0, "checks": real,
             "control_drawn_equals_k": ctl_k, "control_shift_one_frame": ctl_shift},
    "s123_breakpoint_runs": {"runA": run_a, "runB": run_b, "same_as_runA": run_a == drawn},
    "outside_loop": {"counts": out_cnt, "drawn_value_histogram": {str(k): v for k, v in sorted(draw_vals.items())}},
    "status": {"drawn_levels": "LOG CONFIRMED:沒有斷點時八圈畫的是 2、2、4、4、5、7、7、8(k 或 k + 1,第 1、3、6 圈推進)",
               "advance_rule": "LOG CONFIRMED:八圈的推進都等於「tick − 上次推進 > 2」,第 1 圈的上次推進取自迴圈外紀錄",
               "vs_breakpoints": "LOG CONFIRMED:與續一百二十三第一輪(斷點下)逐圈相同;第二輪不同(1、3、3、5、5、7、7、9),"
                                 "不同在哪一個 tick 開始,這裡沒有追",
               "outside": "LOG CONFIRMED:這次 instance 從開機到結束,迴圈外每次地形重畫都走 [0x51a93] == -1 分支;"
                          "移動範圍的明暗循環用的是這一段仍是 INFERRED(沒有對應到畫面上的哪一格)"},
}


def write() -> None:
    OUT.write_text(json.dumps(ev, ensure_ascii=False, indent=1) + "\n", encoding="utf-8", newline="\n")
    print("ok", OUT.name, len(OUT.read_bytes()))


if __name__ == "__main__":
    write()
