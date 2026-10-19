"""續一百二十四:lc124_analyze(原 an124)的突變測試(原暫存 mut_an124.py,續一百三十四移進倉庫)。
每個突變把紀錄複本改錯一處,要求指定的檢查變成 FAIL、其餘不出 Traceback。

由 ev_rest_and_item79_branch.py 以子行程執行,輸出原樣寫進證據。
"""
from __future__ import annotations

import contextlib
import importlib
import io
import json
import shutil
import sys
import tempfile
import traceback
from pathlib import Path
from typing import Callable

sys.stdout.reconfigure(encoding="utf-8")
HERE = Path(__file__).resolve().parent
sys.path.insert(0, str(HERE))
from _evpaths import ROOT  # noqa: E402
SRC = ROOT / ".wsl_build" / "lc124_live"


def edit_json(tag: str, fn: Callable[[list[dict]], None]) -> Callable[[Path], None]:
    def go(d: Path) -> None:
        f = d / f"{tag}.json"
        log = json.loads(f.read_text(encoding="utf-8"))
        fn(log["stops"])
        f.write_text(json.dumps(log, ensure_ascii=False), encoding="utf-8")
    return go


def at(stops: list[dict], a: str) -> dict:
    return next(s for s in stops if s["at"] == a)


def set_unit_hp(stops: list[dict], a: str, i: int, hp: int) -> None:
    next(u for u in at(stops, a)["units"] if u["i"] == i)["hp"] = hp


def poke_frame(name: str, x: int, y: int) -> Callable[[Path], None]:
    def go(d: Path) -> None:
        f = d / f"{name}.bin"
        b = bytearray(f.read_bytes())
        b[y * 320 + x] ^= 0xFF
        f.write_bytes(bytes(b))
    return go


def tbl(stops: list[dict]) -> None:
    s = at(stops, "0x20f80")
    b = bytearray.fromhex(s["tbl_frame_count_1f54"])
    b[3] = 9
    s["tbl_frame_count_1f54"] = b.hex()


MUTANTS: list[tuple[str, Callable[[Path], None], str]] = [
    ("傷害 +1", edit_json("r1", lambda st: at(st, "0x1c897").__setitem__("ebp_damage", 467)), "r1 目標 #5 命中與傷害"),
    ("休息寫入值 +1", edit_json("r1", lambda st: at(st, "0x1410a").__setitem__("edi_new_hp", 168)), "r1 休息"),
    ("移動後 HP 被補", edit_json("r3", lambda st: set_unit_hp(st, "0x15055", 0, 167)), "r3 移動後休息不回血"),
    ("跳字位移改錯", edit_json("r2", lambda st: at(st, "0x20fe5").__setitem__("dx", "02070c1102080c11")), "r2 跳字佇列"),
    ("沒命中卻扣血", edit_json("r2", lambda st: set_unit_hp(st, "0x20fe5", 3, 800)), "r2 目標 #3 沒命中"),
    ("動畫幀目標格外改一點", poke_frame("r1_anim03", 10, 10), "r1 動畫畫面只動在目標格"),
    ("收尾幀目標格外改一點", poke_frame("r2_fin05", 300, 190), "r2 收尾畫面只動在目標格"),
    ("動畫表幀數改 9", edit_json("r1", tbl), "動畫表 = EXE 靜態(0x51f33 / 0x51f54 / 0x51f75)"),
    ("基礎傷害改錯", edit_json("r3", lambda st: at(st, "0x1c7ed").__setitem__("esi_base", 401)), "r3 目標 #3 基礎傷害"),
]


def run_with(d: Path) -> tuple[list[dict], str, str | None]:
    import lc124_analyze as an124
    an124 = importlib.reload(an124)
    an124.D = d
    buf = io.StringIO()
    err = None
    try:
        with contextlib.redirect_stdout(buf):
            an124.main()
    except Exception:  # noqa: BLE001
        err = traceback.format_exc()
    return an124.results, buf.getvalue(), err


def main() -> int:
    bad = 0
    with tempfile.TemporaryDirectory() as td:
        base = Path(td) / "base"
        shutil.copytree(SRC, base)
        res, _out, err = run_with(base)
        assert err is None, err
        assert all(r["ok"] for r in res if not r["control"]), "基準複本本身就有 FAIL"
        for label, mut, target in MUTANTS:
            d = Path(td) / "m"
            if d.exists():
                shutil.rmtree(d)
            shutil.copytree(base, d)
            mut(d)
            res, out, err = run_with(d)
            hit = [r for r in res if r["name"] == target]
            ran = bool(hit)
            failed = ran and not hit[0]["ok"]
            marker = "[FAIL] " + target in out
            ok = err is None and ran and failed and marker
            bad += not ok
            others = [r["name"] for r in res if not r["control"] and not r["ok"] and r["name"] != target]
            print(f"{'抓到' if ok else '漏掉'}  {label}: 目標檢查 {'有跑' if ran else '沒跑'}、{'FAIL' if failed else 'PASS'}、"
                  f"輸出有 FAIL 標記 {marker}、Traceback {'有' if err else '無'};其他一起 FAIL 的 {others}")
    print("突變", len(MUTANTS), "漏掉", bad)
    return 1 if bad else 0


if __name__ == "__main__":
    sys.exit(main())
