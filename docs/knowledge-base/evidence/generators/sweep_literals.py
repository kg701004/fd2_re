"""逐一改動產生器裡的數字常數,找出「寫進證據卻沒有任何檢查擋得住」的手寫值。

每個數字常數(`ast.Constant` 的 int / float,不含 bool)改成 +1(十六進位寫法維持十六進位),
在暫存目錄重算一次,與已提交的證據檔比對:

    KILLED         以 AssertionError 失敗:這個值有判準把關。
    MISSING_INPUT  exit 3:改到的是輸入路徑 / 檔名,輸入檢查擋下。
    CRASH          其他例外(IndexError、ValueError…):不是判準擋下的,只是剛好跑不下去。
    INERT          成功且輸出逐 byte 相同:這個值不影響證據內容。
    ESCAPED        成功但輸出不同:這個值流進證據,改了也沒有判準發現 —— 需要逐筆看。
    TIMEOUT        超過時限(變異版跑不完;算變異結果,不讓工具失敗)。
    CONTROL_FAIL   未變異對照與已提交檔案不同:該產生器的變異都沒有意義,工具 exit 1。

ESCAPED 不一定是錯:可能是設定紀錄(例如測試時擺的座標)、純說明文字裡的數字,或讀傾印用的位移。
要逐筆判斷它是「該由輸入算出 / 檢查卻是手寫」還是「本來就是記錄性的值」。

變異版寫在暫存目錄、輸出導到暫存目錄,不碰已提交的檔案;每個產生器先跑未變異對照,
重算結果必須與已提交檔案相同,否則跳過該產生器(CONTROL_FAIL)。

用法:
    python sweep_literals.py [ev_s65b ...] [--workers 4] [--out result.json]
    python sweep_literals.py --module _terrain.py ev_terrain_modifier ev_attack_path_selection
    python sweep_literals.py --selftest
"""
from __future__ import annotations

import argparse
import ast
import json
import os
import re
import subprocess
import sys
import tempfile
from collections import Counter
from concurrent.futures import ThreadPoolExecutor
from dataclasses import asdict, dataclass, field
from pathlib import Path
from typing import Any

from _evpaths import EVIDENCE, GEN_DIR, MANIFEST, MISSING_INPUT_RC

TIMEOUT_S = 180
# 只影響輸出排版、不是資料的常數(改了必然 ESCAPED,沒有判讀價值)
SKIP_KEYWORDS = {"indent"}


@dataclass
class Site:
    """一個可變異的數字常數。"""

    line: int
    col: int          # UTF-8 byte 位移(ast 的 col_offset)
    end_col: int
    text: str         # 原始寫法
    new: str          # 變異寫法
    in_assert: bool
    context: str      # 那一行原始碼(去頭尾空白)
    role: str = ""    # 語法位置,見 _role()


@dataclass
class Result:
    """一個變異的結果。"""

    gen: str
    module: str
    line: int
    text: str
    new: str
    in_assert: bool
    context: str
    verdict: str
    role: str = ""
    detail: list[str] = field(default_factory=list)


def _lines(src: str) -> list[str]:
    r"""依 \n 切行(保留換行);ast 的行號只算 \n,str.splitlines 還會在 \f、\u2028 等處切。"""
    return re.split(r"(?<=\n)", src)


def _mutated_text(text: str, value: int | float) -> str:
    """回傳 +1 後的寫法;原本是十六進位就維持十六進位(大小寫跟原文)。"""
    if isinstance(value, float):
        return repr(value + 1.0)
    low = text.lower()
    if low.startswith("0x"):
        h = format(value + 1, "x")
        return ("0x" if text[1] == "x" else "0X") + (h.upper() if any(c in "ABCDEF" for c in text[2:]) else h)
    return str(value + 1)


# 自我測試的探針:ev_s65b 由傾印算出的欄位(換成手寫常數就是要找的缺陷)
SPAWN_COMPUTED = '"terrain_of_spawn_cells": next(iter(spawn_types))}'
ROLES = {"data", "offset", "call_arg", "arith", "compare", "other"}
_CONTAINERS = (ast.Dict, ast.List, ast.Tuple, ast.Set, ast.UnaryOp, ast.keyword, ast.Starred)


def _role(node: ast.AST, parents: dict[int, ast.AST]) -> str:
    """常數在語法上的位置,用來把 ESCAPED 分組。

    Returns:
        "data":    只經過 dict / list / tuple(含負號)就到敘述或函式參數 —— 手寫的資料值。
        "offset":  在下標或切片裡(讀傾印的位移、索引)。
        "call_arg": 直接當函式參數(`unpack_from(..., 0x40)`、`range(3)`、`w(pre, i, 0x48)`)。
        "arith":   算式的一部分。
        "compare": 比較式的一部分。
        "other":   其他(條件運算式、推導式…)。
    """
    cur, via_container = node, False
    while True:
        p = parents.get(id(cur))
        if p is None or isinstance(p, ast.stmt):
            return "data"
        if isinstance(p, ast.Subscript) and cur is p.slice or isinstance(p, ast.Slice):
            return "offset"
        if isinstance(p, ast.Call):
            return "data" if via_container else "call_arg"
        if isinstance(p, (ast.BinOp, ast.AugAssign)):
            return "arith"
        if isinstance(p, (ast.Compare, ast.BoolOp)):
            return "compare"
        if isinstance(p, _CONTAINERS):
            via_container = via_container or not isinstance(p, ast.UnaryOp)
            cur = p
            continue
        return "other"


def find_sites(src: str) -> list[Site]:
    """列出原始碼裡要變異的數字常數(依出現順序)。"""
    tree = ast.parse(src)
    parents: dict[int, ast.AST] = {}
    for node in ast.walk(tree):
        for ch in ast.iter_child_nodes(node):
            parents[id(ch)] = node
    skip: set[int] = set()
    for node in ast.walk(tree):
        if isinstance(node, ast.keyword) and node.arg in SKIP_KEYWORDS:
            skip.add(id(node.value))
    lines = _lines(src)
    sites = []
    for node in ast.walk(tree):
        if not (isinstance(node, ast.Constant) and type(node.value) in (int, float)) or id(node) in skip:
            continue
        if node.lineno != node.end_lineno:
            continue
        raw = lines[node.lineno - 1].encode("utf-8")
        text = raw[node.col_offset:node.end_col_offset].decode("utf-8")
        p, in_assert = parents.get(id(node)), False
        while p is not None:
            if isinstance(p, ast.Assert):
                in_assert = True
                break
            p = parents.get(id(p))
        sites.append(Site(node.lineno, node.col_offset, node.end_col_offset, text,
                          _mutated_text(text, node.value), in_assert, lines[node.lineno - 1].strip()[:160],
                          _role(node, parents)))
    sites.sort(key=lambda s: (s.line, s.col))
    return sites


def apply(src: str, site: Site) -> str:
    """把 site 那個常數換成變異寫法;換之前確認原文相符。"""
    lines = _lines(src)
    raw = lines[site.line - 1].encode("utf-8")
    assert raw[site.col:site.end_col].decode("utf-8") == site.text, (site.line, site.text)
    lines[site.line - 1] = (raw[:site.col] + site.new.encode("utf-8") + raw[site.end_col:]).decode("utf-8")
    return "".join(lines)


def diff_paths(a: Any, b: Any, path: str = "$") -> list[str]:
    """兩份 JSON 值不同的葉節點路徑。"""
    if type(a) is not type(b):
        return [path]
    if isinstance(a, dict):
        out: list[str] = []
        for k in list(a) + [k for k in b if k not in a]:
            if k not in a or k not in b:
                out.append(f"{path}.{k}")
            else:
                out += diff_paths(a[k], b[k], f"{path}.{k}")
        return out
    if isinstance(a, list):
        if len(a) != len(b):
            return [f"{path}[len {len(a)}→{len(b)}]"]
        out = []
        for i, (x, y) in enumerate(zip(a, b)):
            out += diff_paths(x, y, f"{path}[{i}]")
        return out
    return [] if a == b else [path]


def classify(rc: int | None, stderr: str, out_dir: Path, outputs: list[str]) -> tuple[str, list[str]]:
    """依結束碼、stderr 與輸出判定變異結果。rc 為 None 表示逾時。"""
    if rc is None:
        return "TIMEOUT", []
    if rc == MISSING_INPUT_RC and "MISSING_INPUT" in stderr:
        return "MISSING_INPUT", []
    if rc != 0:
        tail = [x for x in stderr.strip().splitlines() if x.strip()]
        last = tail[-1][:200] if tail else f"rc={rc}"
        # AssertionError 必須是最後拋出的例外,且有 Traceback(不是印出來的字串)
        if "Traceback" in stderr and last.startswith("AssertionError"):
            return "KILLED", [last]
        return "CRASH", [last]
    made = sorted(p.name for p in out_dir.iterdir()) if out_dir.exists() else []
    if made != sorted(outputs):
        return "ESCAPED", [f"輸出檔 {made} != {sorted(outputs)}"]
    detail: list[str] = []
    for n in outputs:
        got, ref = (out_dir / n).read_bytes(), (EVIDENCE / n).read_bytes()
        if got == ref:
            continue
        try:
            paths = diff_paths(json.loads(ref), json.loads(got))
        except ValueError:
            paths = ["<非 JSON>"]
        detail += [f"{n}:{p}" for p in (paths or ["<只差排版>"])]
    return ("ESCAPED", detail[:8]) if detail else ("INERT", [])


def _run(script: Path, out_dir: Path) -> tuple[int | None, str]:
    env = dict(os.environ, FD2_EVIDENCE_OUT_DIR=str(out_dir), PYTHONPATH=str(GEN_DIR))
    env.pop("FD2_EVIDENCE_MANIFEST_BUILD", None)
    try:
        r = subprocess.run([sys.executable, "-X", "utf8", "-W", "ignore", str(script)], cwd=GEN_DIR, env=env,
                           capture_output=True, text=True, encoding="utf-8", errors="replace", timeout=TIMEOUT_S)
    except subprocess.TimeoutExpired:
        return None, ""
    return r.returncode, r.stderr


def run_variant(gen: str, outputs: list[str], td: Path, tag: str, gen_src: str,
                module: str | None = None, module_src: str | None = None) -> tuple[str, list[str]]:
    """在 td/tag 寫入(可能變異過的)產生器與模組,重算並判定。"""
    d = td / tag
    d.mkdir()
    out = d / "out"
    out.mkdir()
    if module:
        (d / module).write_text(module_src or "", encoding="utf-8", newline="\n")
    script = d / f"{gen}.py"  # 檔名同產生器:require_inputs 依檔名查清單
    script.write_text(gen_src, encoding="utf-8", newline="\n")
    rc, err = _run(script, out)
    return classify(rc, err, out, outputs)


def sweep(gen: str, module: str | None = None, src: str | None = None) -> list[Result]:
    """對一個產生器(或它匯入的一個模組)做全部常數的變異。

    Args:
        gen: 產生器名稱。
        module: 改這個匯入模組而不是產生器本身。
        src: 以這份原始碼取代產生器檔案(自我測試用;不可與 module 併用)。
    """
    assert not (module and src)
    man = json.loads(MANIFEST.read_text(encoding="utf-8"))["generators"]
    outputs = man[gen]["outputs"]
    gen_src = src if src is not None else (GEN_DIR / f"{gen}.py").read_text(encoding="utf-8")
    target = module or f"{gen}.py"
    tsrc = gen_src if not module else (GEN_DIR / target).read_text(encoding="utf-8")
    res: list[Result] = []
    with tempfile.TemporaryDirectory(prefix=f"swl_{gen}_") as tdn:
        td = Path(tdn)
        v, det = run_variant(gen, outputs, td, "control", gen_src, module, tsrc if module else None)
        if v != "INERT":
            return [Result(gen, target, 0, "", "", False, "", "CONTROL_FAIL", [v] + det)]
        for i, s in enumerate(find_sites(tsrc)):
            m = apply(tsrc, s)
            if module:
                v, det = run_variant(gen, outputs, td, f"m{i}", gen_src, module, m)
            else:
                v, det = run_variant(gen, outputs, td, f"m{i}", m)
            res.append(Result(gen, target, s.line, s.text, s.new, s.in_assert, s.context, v, detail=det, role=s.role))
    return res


def selftest() -> int:
    """正反對照:判定器每一種結果都要能出現,且在真實產生器上分得出 KILLED / ESCAPED / INERT。"""
    fails: list[str] = []
    # 1. 改寫:十六進位維持十六進位與大小寫,位置以 UTF-8 byte 計(同一行前面有中文也換對)
    src = 'x = "中文"; y = 0x26EA0C; z = 0xff; w = 0.5; b = True\n'
    sites = find_sites(src)
    if [s.new for s in sites] != ["0x26EA0D", "0x100", "1.5"]:
        fails.append(f"改寫錯誤:{[s.new for s in sites]}(bool 不應列入)")
    elif apply(src, sites[0]) != 'x = "中文"; y = 0x26EA0D; z = 0xff; w = 0.5; b = True\n':
        fails.append(f"位置錯誤:{apply(src, sites[0])!r}")
    if find_sites("json.dump(o, f, indent=1)\n"):
        fails.append("indent 應略過")
    if not find_sites("assert x == 3\n")[0].in_assert:
        fails.append("assert 內的常數應標 in_assert")
    rsrc = 'x = {"a": 5, "b": [1, -2]}\ny = u[0x40]\nz = f(r, 7)\nw = a + 3\nf({"k": 9})\nif q == 4: pass\n'
    roles = [s.role for s in find_sites(rsrc)]
    if roles != ["data", "data", "data", "offset", "call_arg", "arith", "data", "compare"]:
        fails.append(f"role 分類錯誤:{roles}")
    # 2. 判定器:印出來的 AssertionError 字串不算 KILLED;例外鏈最後不是 AssertionError 也不算
    with tempfile.TemporaryDirectory(prefix="swl_self_") as tdn:
        e = Path(tdn) / "empty"
        e.mkdir()
        cases = [
            ((1, "Traceback (most recent call last):\n  ...\nAssertionError: x"), "KILLED"),
            ((1, "AssertionError 只是印出來的字\n"), "CRASH"),
            ((1, "Traceback (most recent call last):\nAssertionError\n\nDuring handling...\nTraceback (most recent call last):\nIndexError: x"), "CRASH"),
            ((MISSING_INPUT_RC, "MISSING_INPUT\n  a.bin 缺檔"), "MISSING_INPUT"),
            ((None, ""), "TIMEOUT"),
            ((0, ""), "ESCAPED"),   # 沒有產生清單上的輸出
        ]
        for (rc, err), want in cases:
            got = classify(rc, err, e, ["x.json"])[0]
            if got != want:
                fails.append(f"classify(rc={rc}, {err[:30]!r}) = {got},應為 {want}")
    # 3. 真實產生器 ev_s65b:已知有判準的值、已知沒判準的重複手寫值、不影響輸出的值
    gen = "ev_s65b"
    man = json.loads(MANIFEST.read_text(encoding="utf-8"))["generators"]
    outs = man[gen]["outputs"]
    gsrc = (GEN_DIR / f"{gen}.py").read_text(encoding="utf-8")
    probes = [
        ('a["hp_change"] == {"17": 14, "57": 13}', '{"17": 14,', '{"17": 15,', "KILLED"),
        (SPAWN_COMPUTED, SPAWN_COMPUTED, '"terrain_of_spawn_cells": 6}', "ESCAPED"),
        ('print("ok", OUT)', 'print("ok", OUT)', 'print("ok", OUT, 1)', "INERT"),
        ("indent=1)", 'ensure_ascii=False, indent=1)\nopen(OUT', 'ensure_ascii=False, indent=2)\nopen(OUT', "ESCAPED"),
    ]
    with tempfile.TemporaryDirectory(prefix="swl_self_") as tdn:
        td = Path(tdn)
        v, det = run_variant(gen, outs, td, "control", gsrc)
        if v != "INERT":
            fails.append(f"{gen} 未變異對照應為 INERT,得到 {v} {det}")
        for i, (anchor, old, new, want) in enumerate(probes):
            if gsrc.count(anchor) != 1 or gsrc.count(old) != 1:
                fails.append(f"{gen} 找不到探針 {anchor!r},對照沒有執行")
                continue
            v, det = run_variant(gen, outs, td, f"p{i}", gsrc.replace(old, new))
            if v != want:
                fails.append(f"{gen} 探針 {new!r} 應為 {want},得到 {v} {det}")
        # 4. 把一個由傾印算出的欄位換回等值的手寫常數(輸出不變,正是要找的缺陷樣式):
        #    sweep 的對照要通過,該常數要被點名為 ESCAPED / data,且同時有 KILLED
        rs = sweep(gen, src=gsrc.replace(SPAWN_COMPUTED, '"terrain_of_spawn_cells": 5}'))
        vs = Counter(r.verdict for r in rs)
        if not vs["KILLED"] or not any(r.verdict == "ESCAPED" and r.role == "data" and r.text == "5"
                                       and "terrain_of_spawn_cells" in r.context for r in rs):
            fails.append(f"sweep({gen}) 應有 KILLED 且點名手寫的 terrain_of_spawn_cells:{dict(vs)}")
        # 結果欄位型別:role 是語法位置字串、detail 是清單(曾經位置參數對調,main 印出時才崩潰)
        bad = [r for r in rs if not (isinstance(r.detail, list) and r.role in ROLES)]
        if bad:
            fails.append(f"sweep({gen}) 結果欄位錯位:{bad[0]}")
    for f in fails:
        print("FAIL", f)
    print("selftest", "PASS" if not fails else f"FAIL ({len(fails)})")
    return 1 if fails else 0


def main(argv: list[str]) -> int:
    ap = argparse.ArgumentParser(description=__doc__.splitlines()[0])
    ap.add_argument("gens", nargs="*")
    ap.add_argument("--module", help="改這個匯入模組(而不是產生器本身)")
    ap.add_argument("--workers", type=int, default=4)
    ap.add_argument("--out", type=Path, help="結果寫成 JSON")
    ap.add_argument("--selftest", action="store_true")
    a = ap.parse_args(argv)
    if a.selftest:
        return selftest()
    man = json.loads(MANIFEST.read_text(encoding="utf-8"))["generators"]
    gens = a.gens or list(man)
    unknown = [g for g in gens if g not in man]
    if unknown:
        raise SystemExit(f"清單裡沒有:{unknown}")
    with ThreadPoolExecutor(max_workers=a.workers) as ex:
        per = list(ex.map(lambda g: sweep(g, a.module), gens))
    allres = [r for rs in per for r in rs]
    for g, rs in zip(gens, per):
        c = Counter(r.verdict for r in rs)
        print(f"{g:40s} " + " ".join(f"{k}={c[k]}" for k in sorted(c)))
    for r in allres:
        if r.verdict in ("ESCAPED", "CONTROL_FAIL", "TIMEOUT"):
            print(f"{r.verdict:12s} {r.role:8s} {r.module}:{r.line} {r.text}→{r.new} | {r.context[:90]} | {'; '.join(r.detail[:3])}")
    tot = Counter(r.verdict for r in allres)
    print("ESCAPED 依語法位置", dict(Counter(r.role for r in allres if r.verdict == "ESCAPED")))
    print("合計", dict(sorted(tot.items())))
    if a.out:
        a.out.write_text(json.dumps([asdict(r) for r in allres], ensure_ascii=False, indent=1) + "\n",
                         encoding="utf-8", newline="\n")
    # TIMEOUT 是變異版跑不完(例如堆積走訪的步長被改成永遠不前進),屬於變異結果,不是工具失敗
    return 1 if tot["CONTROL_FAIL"] else 0


if __name__ == "__main__":
    sys.exit(main(sys.argv[1:]))
