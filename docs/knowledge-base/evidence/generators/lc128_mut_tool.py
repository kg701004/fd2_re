"""續一百二十八:verify_event_dispatch_table.py 新增程式碼的突變測試(原暫存 mut128.py,續一百三十四移進倉庫)。
工具原始碼取續一百二十八提交時的 git blob(_blobtools.EDT_SRC);由 ev_dispatch_index_bounds_table_split.py 以子行程執行。

不寫檔:把原始碼改一處後以 compile(..., 真實路徑) 在記憶體裡執行 selftest()。
要求:回傳 1、輸出含 "SELFTEST FAILED"、指定的題號那一行是 FAIL、沒有例外。
"""
from __future__ import annotations

import contextlib
import io
import sys
import traceback
from pathlib import Path

sys.stdout.reconfigure(encoding="utf-8")
sys.path.insert(0, str(Path(__file__).resolve().parent))
from _blobtools import EDT_PATH as TOOL, EDT_SRC  # noqa: E402

MUTANTS: list[tuple[str, str, str, str]] = [
    ("不檢查 opcode", "return op == 0xFF and modrm in (0x14, 0x24)", "return modrm in (0x14, 0x24)", "(12)"),
    ("不檢查 scale", "and (sib & 0xC7) == 0x85", "and (sib & 0x07) == 0x05", "(12)"),
    ("只認 call", "modrm in (0x14, 0x24) and", "modrm == 0x14 and", "(12)"),
    ("下界改成嚴格", "if base <= tgt < base + 4 * count and", "if base < tgt < base + 4 * count and", "(11)"),
    ("記 disp 位置不是指令位置", "out.setdefault(tgt, []).append(src - 3)", "out.setdefault(tgt, []).append(src)", "(11)"),
    ("走錯 object", "build_fixups(data, meta, objects={1})", "build_fixups(data, meta, objects={2})", "(11)"),
    ("丟掉表頭", "starts = sorted(set(sites) | {base})", "starts = sorted(set(sites))", "(12)"),
    ("first 沒除 4", '"first": (s - base) // 4,', '"first": (s - base),', "(11)"),
    ("count 除 2", '"count": (nxt - s) // 4,', '"count": (nxt - s) // 2,', "(11)"),
    ("對齊判準錯", '"aligned": (s - base) % 4 == 0,', '"aligned": (s - base) % 4 == 1,', "(11)"),
    ("all_tables 只掃 1 格", "dispatch_sites(data, meta, base, count)),", "dispatch_sites(data, meta, base, 1)),", "(11)"),
    ("最後一段的結尾錯", "end = base + 4 * count\n", "end = base + 4 * count - 4\n", "(11)"),
    ("off 下界放寬", "if off < 3 or off > len(code):", "if off < 0 or off > len(code):", "(12)"),
]


def run(src: str) -> tuple[int | None, str, str]:
    g = {"__name__": "mut128_target", "__file__": str(TOOL)}
    buf = io.StringIO()
    err = ""
    rc = None
    with contextlib.redirect_stdout(buf):
        try:
            exec(compile(src, str(TOOL), "exec"), g)
            rc = g["selftest"]()
        except Exception:  # noqa: BLE001
            err = traceback.format_exc()
    return rc, buf.getvalue(), err


def item_line(out: str, tag: str) -> str:
    lines = out.splitlines()
    for i, ln in enumerate(lines):
        if ln.startswith(tag):
            return next((x for x in lines[i + 1:i + 4] if x.strip().startswith(("PASS", "FAIL"))), "")
    return ""


def main() -> int:
    base = EDT_SRC
    rc0, out0, err0 = run(base)
    assert rc0 == 0 and not err0 and "(11)" in out0 and "(12)" in out0, (rc0, err0, out0[-500:])
    print("原版: rc=0,(11)(12) 都有跑")
    caught = 0
    for name, old, new, tag in MUTANTS:
        n = base.count(old)
        if n != 1:
            print(f"無效 {name}: 原始碼出現 {n} 次")
            continue
        rc, out, err = run(base.replace(old, new))
        line = item_line(out, tag)
        ok = rc == 1 and "SELFTEST FAILED" in out and line.strip().startswith("FAIL") and not err
        caught += ok
        print(f"{'抓到' if ok else '漏掉'} {name}: rc={rc} {tag}={line.strip()[:70]!r} 例外={bool(err)}")
    print(f"突變 {len(MUTANTS)} 個,抓到 {caught},漏掉 {len(MUTANTS) - caught}")
    return 0 if caught == len(MUTANTS) else 1


if __name__ == "__main__":
    sys.exit(main())
