"""續一百二十九:lut_circle_ramp_at_unit 在 cycles 2500 / 10000 的每次呼叫時間 —— 檢查 5 份新紀錄,並與續一百二十六 / 一百二十七的紀錄合併看比例。

新紀錄在 .wsl_build/lc129a_live(cycles 2500)與 .wsl_build/lc129d_live(cycles 10000);舊紀錄讀倉庫 evidence(不讀暫存)。
原暫存 an129t.py,續一百三十四移進倉庫。
入口引數與返回位址的期望值由 FD2.EXE 兩個呼叫點的 push 立即值導出(不寫死)。
用法:lc129t_analyze.py [--runs-dir DIR] [--exe PATH]
每項印 PASS / FAIL;對照項(control)要 FAIL 才算檢查有效。最後一行 "ALL OK" 或 "BAD n"。
"""
from __future__ import annotations

import argparse
import json
import sys
from pathlib import Path

import capstone

HERE = Path(__file__).resolve().parent
sys.path.insert(0, str(HERE))
from _evpaths import GAME, ROOT as REPO  # noqa: E402
sys.path.insert(0, str(REPO / "tools"))
from disasm_le import load_code  # noqa: E402
from le_xref import parse_le  # noqa: E402

EV = REPO / "docs" / "knowledge-base" / "evidence"
EV126 = EV / "lut_circle_ramp_frame_time_ch22_post_20261015.json"
EV127 = EV / "lut_ch22_post_cycles2500_chapter_tables_20261015.json"
LUT, FRAME, END, AFTER = 0x2189A, 0x2198E, 0x21998, 0x219A8
# 法術 -> 呼叫點裡第一個 push 的位址(push 每幀加、push 起始半徑、push [esp+0xc]、call lut)
SITES = {11: 0x2187B, 12: 0x21ABA}
# 新紀錄:(cycles, 法術, 逐幀?)
NEW = {"c2500_s12_nof": (2500, 12, False), "c2500_s12_frames": (2500, 12, True),
       "c10000_s11_nof": (10000, 11, False), "c10000_s12_nof": (10000, 12, False), "c10000_s12_frames": (10000, 12, True)}
# 預測(量測之前寫在 pred129.txt):H1 與 cycles 成反比
PRED = {(2500, 12): (17, 24), (10000, 11): (2, 5), (10000, 12): (4, 7)}

results: list[dict] = []


def check(name: str, ok: bool, detail: str, control: bool = False) -> None:
    results.append({"name": name, "ok": bool(ok), "control": control, "detail": detail})
    print(("對照 " if control else "") + ("PASS" if ok else "FAIL"), name, "|", detail)


def site_args(code: bytes, cbase: int) -> dict[int, tuple[str, list[int]]]:
    """{法術: (返回位址, [使用者 0, 起始半徑, 每幀加])},從 FD2.EXE 解碼。"""
    md = capstone.Cs(capstone.CS_ARCH_X86, capstone.CS_MODE_32)
    out = {}
    for sp, a in SITES.items():
        ins = list(md.disasm(code[a - cbase:a - cbase + 16], a))[:4]
        assert [i.mnemonic for i in ins] == ["push", "push", "push", "call"] and int(ins[3].op_str, 16) == LUT, ins
        out[sp] = (hex(ins[3].address + ins[3].size), [0, int(ins[1].op_str, 16), int(ins[0].op_str, 16)])
    return out


def span(stops: list[dict]) -> int | None:
    e = [s["tick"] for s in stops if s.get("at") == hex(LUT)]
    f = [s["tick"] for s in stops if s.get("at") == hex(END)]
    return f[0] - e[0] if len(e) == 1 and len(f) == 1 else None


def shape_ok(stops: list[dict], frames: bool, exp: tuple[str, list[int]]) -> tuple[bool, str]:
    at = [s.get("at") for s in stops]
    want = [hex(LUT)] + ([hex(FRAME)] * 10 if frames else []) + [hex(END), hex(AFTER)]
    ent = stops[0] if stops else {}
    fr = [s for s in stops if s.get("at") == hex(FRAME)]
    r0, step = exp[1][1], exp[1][2]
    ok = (at == want and ent.get("ret") == exp[0] and ent.get("args") == exp[1]
          and [s["frame"] for s in fr] == list(range(len(fr)))
          and [s["radius"] for s in fr] == [r0 + k * step for k in range(len(fr))]
          and all(s.get("ebx") == 10 for s in stops if s.get("at") == hex(END)))
    return ok, f"站 {len(at)}(期望 {len(want)}),ret {ent.get('ret')} args {ent.get('args')},期望 {exp}"


def main(argv: list[str] | None = None) -> int:
    ap = argparse.ArgumentParser()
    ap.add_argument("--runs-dir", default=str(REPO / ".wsl_build"))
    ap.add_argument("--exe", default=str(GAME / "FD2.EXE"))
    a = ap.parse_args(argv)
    data = Path(a.exe).read_bytes()
    code, cbase = load_code(data, parse_le(data))
    exp = site_args(code, cbase)
    rd = Path(a.runs_dir)
    new = {}
    for tag, (cyc, sp, fr) in NEW.items():
        sub = "lc129a_live" if cyc == 2500 else "lc129d_live"
        new[tag] = json.loads((rd / sub / f"{tag}.json").read_text(encoding="utf-8"))
        ok, det = shape_ok(new[tag]["stops"], fr, exp[sp])
        check(f"{tag} 站序 / 引數 / 半徑", ok, det)
    # 每次呼叫的入口 -> 迴圈結束
    meas: dict[tuple[int, int], list[int]] = {}
    for tag, (cyc, sp, fr) in NEW.items():
        meas.setdefault((cyc, sp), []).append(span(new[tag]["stops"]))
    old126 = {r["tag"]: r for r in json.loads(EV126.read_text(encoding="utf-8"))["runs"]}
    old127 = {r["tag"]: r for r in json.loads(EV127.read_text(encoding="utf-8"))["runs"]}
    meas[(5000, 11)] = [span(old126[t]["stops"]) for t in ("s11_frames", "s11_nof")]
    meas[(5000, 12)] = [span(old126[t]["stops"]) for t in ("s12_frames",)]
    meas[(2500, 11)] = [span(old127[t]["stops"]) for t in ("c2500_nof", "c2500_frames")]
    for k in sorted(meas):
        print("  量到", k, meas[k])
    # 缺入口或迴圈結束的紀錄量不到時間:直接判失敗,不往下算(避免 None 參與比較)
    miss = [k for k, v in meas.items() if any(x is None for x in v)]
    check("每份紀錄都有一個入口與一個迴圈結束", not miss, f"缺的 {miss}")
    if miss:
        print(f"BAD {sum(1 for r in results if r['ok'] == r['control'])}")
        return 1
    # 逐幀停與不停相同
    for k in ((2500, 12), (10000, 12)):
        check(f"cycles {k[0]} 法術 {k[1]}:逐幀停與只停兩端相同", len(meas[k]) == 2 and meas[k][0] == meas[k][1], f"{meas[k]}")
    # 預測區間
    for k, (lo, hi) in PRED.items():
        check(f"預測 cycles {k[0]} 法術 {k[1]} 在 {lo}..{hi}", all(v is not None and lo <= v <= hi for v in meas[k]), f"{meas[k]}")
    # 單調:cycles 加倍,時間嚴格變短(兩個法術各自)
    for sp in (11, 12):
        seq = [max(meas[(c, sp)]) for c in (2500, 5000, 10000)]
        check(f"法術 {sp}:2500 > 5000 > 10000", seq[0] > seq[1] > seq[2], f"{seq}")
        # tick × cycles 在 ±1 tick 量化誤差下有共同值(反比)
        lo = max((v - 1) * c for c in (2500, 5000, 10000) for v in [min(meas[(c, sp)])])
        hi = min((v + 1) * c for c in (2500, 5000, 10000) for v in [max(meas[(c, sp)])])
        check(f"法術 {sp}:tick × cycles 在 ±1 tick 內有共同值", lo <= hi, f"共同區間 [{lo}, {hi}]")
    # 裂地術比地震術慢(兩種新 cycles 都是)
    for c in (2500, 10000):
        check(f"cycles {c}:裂地術 > 地震術", min(meas[(c, 12)]) > max(meas[(c, 11)]), f"{meas[(c, 12)]} vs {meas[(c, 11)]}")
    # 對照 H0:與 cycles 無關(cycles 10000 仍在 cycles 5000 的 ±1 內)—— 必須不符
    h0 = all(abs(v - w) <= 1 for sp in (11, 12) for v in meas[(10000, sp)] for w in meas[(5000, sp)])
    check("對照 H0:cycles 10000 與 5000 相同(±1 tick)", h0, f"10000 {meas[(10000, 11)]}/{meas[(10000, 12)]};5000 {meas[(5000, 11)]}/{meas[(5000, 12)]}",
          control=True)
    # 對照:時間與 cycles 成正比(cycles 越大越慢)—— 必須不符
    prop = all(max(meas[(2500, sp)]) < min(meas[(10000, sp)]) for sp in (11, 12))
    check("對照:cycles 越大越慢", prop, "2500 的時間小於 10000", control=True)
    bad = sum(1 for r in results if r["ok"] == r["control"])
    print("ALL OK" if bad == 0 else f"BAD {bad}")
    globals()["MEAS"] = {f"{c}_{s}": v for (c, s), v in sorted(meas.items())}
    return 1 if bad else 0


if __name__ == "__main__":
    sys.stdout.reconfigure(encoding="utf-8")
    sys.exit(main())
