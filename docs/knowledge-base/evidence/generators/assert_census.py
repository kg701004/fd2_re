"""證據產生器的 assert 數量閘門:每個產生器的 assert 個數只能隨基準一起改,不能悄悄變少;重算時每個 assert 都要真的執行到。

產生器的可信度來自它的 assert(判準與預測);證據 JSON 逐 byte 相同(run_all)不代表判準還在 —— 刪掉一個 assert,
輸出完全不變,run_all 仍是 IDENTICAL,變異測試也只驗還留著的那些。本工具補這個缺口:
    靜態    以 AST 數每個產生器(inputs_manifest.json 列的 ev_*.py)的 assert 個數,與 assert_census.json 的基準比。
            SHRANK(變少)、GREW(變多但基準沒更新)、NEW(基準沒有)、GONE(清單沒有了)、ZERO(一個都沒有)都 FAIL。
    動態    --executed:在暫存目錄重算產生器,每個 assert 前插一個計數呼叫(AST 改寫,行號不變),
            記錄哪些 assert 從來沒執行到 —— 沒執行到的 assert 不是檢查。與基準的 executed 比,變少就 FAIL。
            輸入不符(MISSING_INPUT)的產生器記為 NOT TESTED,不算 FAIL 也不算 PASS。

用法:
    python assert_census.py                    靜態檢查(秒級;提交前跑)
    python assert_census.py --executed [ev …]   動態檢查(要重算產生器,全部約與 run_all 相同時間)
    python assert_census.py --update [--executed]  依目前結果重寫基準(刻意增刪 assert 時;提交時 diff 會顯示)
    python assert_census.py --selftest          正反對照
"""
from __future__ import annotations

import argparse
import ast
import json
import os
import subprocess
import sys
import tempfile
from pathlib import Path

from _evpaths import EVIDENCE, GEN_DIR, MANIFEST, MISSING_INPUT_RC

BASELINE = Path(os.environ.get("FD2_ASSERT_CENSUS") or GEN_DIR / "assert_census.json")
HIT_FN = "__assert_census_hit__"


def assert_lines(src: str) -> list[int]:
    """原始碼裡每個 assert 敘述的行號(由小到大)。"""
    return sorted(n.lineno for n in ast.walk(ast.parse(src)) if isinstance(n, ast.Assert))


def generators() -> list[str]:
    """inputs_manifest.json 列的產生器名稱(清單順序)。"""
    return list(json.loads(MANIFEST.read_text(encoding="utf-8"))["generators"])


def static_counts(names: list[str], gen_dir: Path = GEN_DIR) -> dict[str, int]:
    return {g: len(assert_lines((gen_dir / f"{g}.py").read_text(encoding="utf-8"))) for g in names}


def compare_static(counts: dict[str, int], base: dict[str, dict]) -> list[tuple[str, str, str]]:
    """回傳 [(產生器, 判定, 說明)];判定 OK 以外都是 FAIL。"""
    rows = []
    for g, n in counts.items():
        b = base.get(g, {}).get("asserts")
        if n == 0:
            rows.append((g, "ZERO", "一個 assert 都沒有"))
        elif b is None:
            rows.append((g, "NEW", f"{n} 個,基準沒有這個產生器(--update 記錄)"))
        elif n < b:
            rows.append((g, "SHRANK", f"{b} → {n}"))
        elif n > b:
            rows.append((g, "GREW", f"{b} → {n}(基準沒更新;--update)"))
        else:
            rows.append((g, "OK", str(n)))
    rows += [(g, "GONE", "基準有、清單沒有") for g in base if g not in counts]
    return rows


# ================= 動態 =================
class _Instrument(ast.NodeTransformer):
    """在每個 assert 前插 `__assert_census_hit__(行號)`;新節點沿用 assert 的位置,行號不變。"""

    def generic_visit(self, node: ast.AST) -> ast.AST:
        super().generic_visit(node)
        for field in ("body", "orelse", "finalbody"):
            stmts = getattr(node, field, None)
            if not isinstance(stmts, list) or not stmts or not isinstance(stmts[0], ast.stmt):
                continue
            new: list[ast.stmt] = []
            for s in stmts:
                if isinstance(s, ast.Assert):
                    call = ast.Expr(ast.Call(ast.Name(HIT_FN, ast.Load()), [ast.Constant(s.lineno)], []))
                    new.append(ast.copy_location(call, s))
                    ast.fix_missing_locations(call)
                new.append(s)
            setattr(node, field, new)
        return node


PROBE = r'''
import ast, atexit, json, os, sys
sys.path.insert(0, os.environ["CENSUS_GEN_DIR"])
from assert_census import _Instrument, HIT_FN
path = sys.argv[1]
sys.argv = [path]
hits = set()
def _dump():
    with open(os.environ["CENSUS_OUT"], "w", encoding="utf-8") as f:
        json.dump(sorted(hits), f)
atexit.register(_dump)
tree = _Instrument().visit(ast.parse(open(path, encoding="utf-8").read(), path))
code = compile(tree, path, "exec")
g = {"__name__": "__main__", "__file__": path, "__builtins__": __builtins__, HIT_FN: hits.add}
sys.path[0] = os.path.dirname(path)
exec(code, g)
'''


def run_instrumented(script: Path, out_dir: Path, gen_dir: Path = GEN_DIR) -> tuple[int, list[int], str]:
    """以 AST 改寫後的產生器在 out_dir 重算;回傳 (exit code, 執行到的 assert 行號, stderr 尾端)。"""
    hits_f = out_dir / "_census_hits.json"
    probe = out_dir / "_census_probe.py"
    probe.write_text(PROBE, encoding="utf-8")
    gen_out = out_dir / "out"
    gen_out.mkdir()
    env = dict(os.environ, FD2_EVIDENCE_OUT_DIR=str(gen_out), PYTHONPATH=str(gen_dir), CENSUS_OUT=str(hits_f),
               CENSUS_GEN_DIR=str(Path(__file__).resolve().parent))
    env.pop("FD2_EVIDENCE_MANIFEST_BUILD", None)
    r = subprocess.run([sys.executable, "-X", "utf8", "-W", "ignore", str(probe), str(script)], cwd=gen_dir, env=env,
                       capture_output=True, text=True, encoding="utf-8", errors="replace")
    hits = json.loads(hits_f.read_text(encoding="utf-8")) if hits_f.exists() else []
    return r.returncode, hits, r.stderr[-400:]


def executed(names: list[str]) -> dict[str, dict]:
    """每個產生器:{verdict, asserts, executed, not_executed_lines}。verdict = RAN / MISSING_INPUT / ERROR。"""
    res = {}
    with tempfile.TemporaryDirectory(prefix="census_") as tdn:
        for g in names:
            script = GEN_DIR / f"{g}.py"
            lines = assert_lines(script.read_text(encoding="utf-8"))
            d = Path(tdn) / g
            d.mkdir()
            rc, hits, err = run_instrumented(script, d)
            if rc == MISSING_INPUT_RC and "MISSING_INPUT" in err:
                verdict = "MISSING_INPUT"
            elif rc != 0:
                verdict = "ERROR"
            else:
                verdict = "RAN"
            res[g] = {"verdict": verdict, "asserts": len(lines), "executed": len(set(hits) & set(lines)),
                      "not_executed_lines": sorted(set(lines) - set(hits)) if verdict == "RAN" else None,
                      **({"stderr": err.strip().splitlines()[-1:]} if verdict == "ERROR" else {})}
            print(f"{verdict:13} {g}: {res[g]['executed']}/{len(lines)}", flush=True)
    return res


def compare_executed(ex: dict[str, dict], base: dict[str, dict]) -> list[tuple[str, str, str]]:
    rows = []
    for g, v in ex.items():
        b = base.get(g, {})
        if v["verdict"] == "MISSING_INPUT":
            rows.append((g, "NOT TESTED", "輸入與清單不符"))
        elif v["verdict"] == "ERROR":
            rows.append((g, "ERROR", " ".join(v.get("stderr", []))))
        elif b.get("executed") is None:
            rows.append((g, "NEW", f"{v['executed']}/{v['asserts']}(--update --executed 記錄)"))
        elif v["executed"] < b["executed"]:
            rows.append((g, "SHRANK", f"執行到的 assert {b['executed']} → {v['executed']};沒執行到 {v['not_executed_lines']}"))
        elif v["executed"] > b["executed"]:
            rows.append((g, "GREW", f"{b['executed']} → {v['executed']}(基準沒更新)"))
        else:
            rows.append((g, "OK", f"{v['executed']}/{v['asserts']}"))
    return rows


def load_base() -> dict[str, dict]:
    return json.loads(BASELINE.read_text(encoding="utf-8"))["generators"] if BASELINE.exists() else {}


def write_base(base: dict[str, dict]) -> None:
    doc = {"_note": "每個證據產生器的 assert 個數(asserts,AST 靜態)與重算時執行到的個數(executed)。"
                    "由 assert_census.py --update 產生;asserts / executed 變少要在提交訊息說明原因。",
           "generators": {g: base[g] for g in generators() if g in base}}
    BASELINE.write_bytes((json.dumps(doc, ensure_ascii=False, indent=1) + "\n").encode("utf-8"))


def report(rows: list[tuple[str, str, str]], ok_states: tuple[str, ...]) -> int:
    bad = [r for r in rows if r[1] not in ok_states]
    for g, v, msg in rows:
        if v != "OK":
            print(f"{v:10} {g}: {msg}")
    print(f"{len(rows) - len(bad)}/{len(rows)} 通過" + ("" if not bad else f";FAIL {len(bad)}"))
    return 1 if bad else 0


# ================= 自我測試 =================
def selftest() -> int:
    """正反對照:靜態四種失敗都要說得出來;動態要分得出執行到 / 沒執行到,且改寫不改變產生器的輸出。"""
    fails = []
    # 1. 靜態:同數 OK、少一個 SHRANK、多一個 GREW、新的 NEW、沒了 GONE、零個 ZERO
    base = {"a": {"asserts": 2}, "b": {"asserts": 2}, "c": {"asserts": 2}, "gone": {"asserts": 1}}
    got = {g: v for g, v, _ in compare_static({"a": 2, "b": 1, "c": 3, "new": 4, "z": 0}, base)}
    want = {"a": "OK", "b": "SHRANK", "c": "GREW", "new": "NEW", "z": "ZERO", "gone": "GONE"}
    if got != want:
        fails.append(f"靜態判定 {got} != {want}")
    # 2. 靜態計數吃得到巢狀(函式、迴圈、try/except、else)裡的 assert
    src = ("def f(x):\n    assert x\n    for i in x:\n        assert i\n    else:\n        assert 1\n"
           "try:\n    assert 2\nexcept Exception:\n    assert 3\nfinally:\n    assert 4\nassert f\n")
    if assert_lines(src) != [2, 4, 6, 8, 10, 12, 13]:
        fails.append(f"巢狀 assert 行號 {assert_lines(src)}")
    with tempfile.TemporaryDirectory(prefix="census_self_") as tdn:
        td = Path(tdn)
        # 3. 動態:執行到 / 沒執行到(死分支、未呼叫的函式、except 沒觸發)
        s = td / "ev_selftest_probe.py"
        s.write_text("x = 1\nassert x == 1\nif x == 2:\n    assert False\n"
                     "def never():\n    assert 0\n"
                     "for i in range(3):\n    assert i < 3\n"
                     "try:\n    pass\nexcept ValueError:\n    assert 0\n", encoding="utf-8")
        (td / "s1").mkdir()
        rc, hits, err = run_instrumented(s, td / "s1")
        if rc != 0 or sorted(set(hits)) != [2, 8]:
            fails.append(f"動態:rc={rc} hits={hits} {err}")
        # 4. assert 失敗時,失敗之前執行到的仍要記下來,exit code 非 0
        s2 = td / "ev_selftest_fail.py"
        s2.write_text("assert 1 == 1\nassert 1 == 2, 'boom'\nassert 3\n", encoding="utf-8")
        (td / "s2").mkdir()
        rc, hits, err = run_instrumented(s2, td / "s2")
        if rc == 0 or sorted(hits) != [1, 2] or "AssertionError" not in err or "ev_selftest_fail.py" not in err:
            fails.append(f"assert 失敗時:rc={rc} hits={hits} {err[-200:]}")
        # 5. 改寫不改變真實產生器的輸出(最小的 ev_s65b),且它的 assert 全部執行到
        gen = "ev_s65b"
        outs = json.loads(MANIFEST.read_text(encoding="utf-8"))["generators"][gen]["outputs"]
        (td / "real").mkdir()
        rc, hits, err = run_instrumented(GEN_DIR / f"{gen}.py", td / "real")
        lines = assert_lines((GEN_DIR / f"{gen}.py").read_text(encoding="utf-8"))
        same = rc == 0 and all((td / "real/out" / n).read_bytes() == (EVIDENCE / n).read_bytes() for n in outs)
        if rc == MISSING_INPUT_RC:
            print(f"    NOT TESTED:{gen} 輸入與清單不符,第 5 題略過")
        elif not same or sorted(set(hits)) != lines:
            fails.append(f"{gen} 改寫後:rc={rc} 輸出相同={same} 執行到 {len(set(hits))}/{len(lines)} {err[-200:]}")
        # 6. 刪掉一個 assert:輸出照樣相同(run_all 看不出來),但靜態計數抓得到
        src65 = (GEN_DIR / f"{gen}.py").read_text(encoding="utf-8")
        tree = ast.parse(src65)
        first = next(n for n in ast.walk(tree) if isinstance(n, ast.Assert))
        cut = src65.splitlines(keepends=True)
        line = cut[first.lineno - 1]
        cut[first.lineno - 1:first.end_lineno] = [line[:len(line) - len(line.lstrip())] + "pass\n"]
        (td / "cut").mkdir()
        (td / "cut" / f"{gen}.py").write_text("".join(cut), encoding="utf-8")
        n_cut = static_counts([gen], td / "cut")[gen]
        v = compare_static({gen: n_cut}, {gen: {"asserts": len(lines)}})[0][1]
        if n_cut != len(lines) - 1 or v != "SHRANK":
            fails.append(f"刪一個 assert:計數 {n_cut}(原 {len(lines)}),判定 {v}")
    if fails:
        print("SELFTEST FAILED:")
        for f in fails:
            print("  -", f)
        return 1
    print("--selftest passed(靜態 6 種判定 + 巢狀計數 + 動態執行到 / 沒執行到 + 失敗時仍記錄 + 改寫不改輸出 + 刪 assert 抓得到)")
    return 0


def main(argv: list[str]) -> int:
    ap = argparse.ArgumentParser(description=__doc__.splitlines()[0])
    ap.add_argument("names", nargs="*", help="只看這些產生器(預設 = inputs_manifest.json 全部)")
    ap.add_argument("--executed", action="store_true", help="重算產生器,檢查每個 assert 有沒有執行到")
    ap.add_argument("--update", action="store_true", help="依目前結果重寫基準")
    ap.add_argument("--selftest", action="store_true")
    a = ap.parse_args(argv)
    if a.selftest:
        return selftest()
    names = a.names or generators()
    unknown = [n for n in names if n not in generators()]
    if unknown:
        print(f"清單裡沒有:{unknown}")
        return 2
    base = load_base()
    counts = static_counts(names)
    ex = executed(names) if a.executed else {}
    if a.update:
        for g in names:
            base.setdefault(g, {})["asserts"] = counts[g]
            if g in ex and ex[g]["verdict"] == "RAN":
                base[g]["executed"] = ex[g]["executed"]
                base[g]["not_executed_lines"] = ex[g]["not_executed_lines"]
        write_base(base)
        print(f"基準已更新:{BASELINE.name}({len(names)} 個產生器)")
        return 0
    rc = report(compare_static(counts, {g: base[g] for g in names if g in base} if a.names else base), ("OK",))
    if a.executed:
        rc |= report(compare_executed(ex, base), ("OK", "NOT TESTED"))
    return rc


if __name__ == "__main__":
    if hasattr(sys.stdout, "reconfigure"):
        sys.stdout.reconfigure(encoding="utf-8")
    sys.exit(main(sys.argv[1:]))
