#!/usr/bin/env python3
"""計算本專案反向工程所依據之原版檔案版本指紋。

只讀取玩家自備的合法原版檔案，不複製內容。預設輸出穩定排序的 JSON，
可與 docs/data/fd2-reference-files.json 比對。
"""

from __future__ import annotations

import argparse
import hashlib
import json
from pathlib import Path


REFERENCE_FILES = (
    "FD2.EXE",
    "ANI.DAT",
    "BG.DAT",
    "DATO.DAT",
    "FDFIELD.DAT",
    "FDICON.B24",
    "FDMUS.DAT",
    "FDOTHER.DAT",
    "FDSHAP.DAT",
    "FDTXT.DAT",
    "FIGANI.DAT",
    "TAI.DAT",
    "TITLE.DAT",
)


def digest(path: Path) -> dict[str, object]:
    md5 = hashlib.md5()
    sha256 = hashlib.sha256()
    size = 0
    with path.open("rb") as source:
        for block in iter(lambda: source.read(1024 * 1024), b""):
            size += len(block)
            md5.update(block)
            sha256.update(block)
    return {
        "file": path.name,
        "size": size,
        "md5": md5.hexdigest(),
        "sha256": sha256.hexdigest(),
    }


def selftest() -> int:
    """分塊讀取的雜湊最容易錯在**邊界**:區塊大小的整數倍、剛好差 1、以及空檔。

    這支的輸出是整個專案的版本指紋(`fd2-reference-files.json`),一旦算錯,
    「這是不是同一份 EXE」這個判斷就全錯,而且不會有任何錯誤訊息 —— 只會有一個
    看起來很正常的十六進位字串。所以第 (1) 題拿標準函式庫的一次性雜湊當**獨立
    對照**,而不是只驗它自己前後一致。
    """
    import os
    import sys
    import tempfile
    if hasattr(sys.stdout, "reconfigure"):
        sys.stdout.reconfigure(encoding="utf-8")
        sys.stderr.reconfigure(encoding="utf-8")
    fails = []
    block = 1024 * 1024

    print("(1) 與一次性雜湊逐檔對照(含分塊邊界:0、1、block-1、block、block+1)")
    sizes = [0, 1, block - 1, block, block + 1, block * 2 + 7]
    with tempfile.TemporaryDirectory() as td:
        for n in sizes:
            p = Path(td) / f"probe_{n}.bin"
            data = bytes((i * 37 + 11) & 0xFF for i in range(n))
            p.write_bytes(data)
            got = digest(p)
            want = {"file": p.name, "size": n,
                    "md5": hashlib.md5(data).hexdigest(),
                    "sha256": hashlib.sha256(data).hexdigest()}
            ok = got == want
            print(f"    {'PASS' if ok else 'FAIL'}: {n:>9} bytes -> "
                  f"md5 {got['md5'][:12]}… size={got['size']}")
            if not ok:
                fails.append(f"{n} bytes 的 digest 與一次性雜湊不符")

    print("\n(2) 非恆真控制:內容差 1 個 byte 的兩個檔必須有不同的雜湊")
    with tempfile.TemporaryDirectory() as td:
        a, b = Path(td) / "a.bin", Path(td) / "b.bin"
        a.write_bytes(b"\x00" * 4096)
        b.write_bytes(b"\x00" * 4095 + b"\x01")
        da, db = digest(a), digest(b)
        ok2 = da["md5"] != db["md5"] and da["sha256"] != db["sha256"] and da["size"] == db["size"]
        print(f"    {'PASS' if ok2 else 'FAIL'}: 同大小({da['size']})但 md5 "
              f"{da['md5'][:8]}… vs {db['md5'][:8]}…")
        if not ok2:
            fails.append("差 1 byte 的檔案雜湊相同 —— 這支工具沒有鑑別力")

    print("\n(3) 參考檔清單必須非空,且不得含可變動的存檔/暫存檔")
    volatile = [n for n in REFERENCE_FILES if n.upper() in ("FD2.SAV", "FD2.TMP")]
    ok3 = len(REFERENCE_FILES) >= 5 and not volatile
    print(f"    {'PASS' if ok3 else 'FAIL'}: {len(REFERENCE_FILES)} 個參考檔"
          + (f",混入可變動檔 {volatile}" if volatile else ""))
    if not ok3:
        fails.append(f"參考檔清單有問題:{len(REFERENCE_FILES)} 個,可變動 {volatile}")

    print("\n(4) 與已提交的指紋對得上(現行 org_game 若在,雜湊必須逐檔相符)")
    root = Path(__file__).resolve().parent.parent
    game = root / "org_game" / "炎龍騎士團" / "FLAME2"
    committed = root / "docs" / "data" / "fd2-reference-files.json"
    if game.is_dir() and committed.is_file():
        want = {f["file"]: f for f in json.loads(committed.read_text(encoding="utf-8"))["files"]}
        bad = []
        for name in REFERENCE_FILES:
            p = game / name
            if not p.is_file() or name not in want:
                continue
            d = digest(p)
            if d["md5"] != want[name]["md5"] or d["size"] != want[name]["size"]:
                bad.append(name)
        ok4 = not bad
        print(f"    {'PASS' if ok4 else 'FAIL'}: 比對 {len(want)} 個已提交指紋"
              + ("全部相符" if ok4 else f",不符 {bad}"))
        if not ok4:
            fails.append(f"現行 org_game 與已提交指紋不符:{bad}")
    else:
        print("    SKIP: 找不到 org_game 或已提交的指紋檔")

    if fails:
        print("\nSELFTEST FAILED:")
        for f in fails:
            print("  -", f)
        return 1
    print("\n--selftest passed(獨立雜湊對照含分塊邊界 + 非恆真控制 + "
          "清單完整性 + 與已提交指紋比對)。")
    return 0


def main() -> int:
    parser = argparse.ArgumentParser()
    parser.add_argument("game_dir", type=Path, nargs="?",
                        help="含 FD2.EXE 的原版 FLAME2 目錄")
    parser.add_argument("--selftest", action="store_true")
    args = parser.parse_args()
    if args.selftest:
        return selftest()
    if args.game_dir is None:
        parser.error("需要 game_dir(或用 --selftest)")

    missing = [name for name in REFERENCE_FILES if not (args.game_dir / name).is_file()]
    if missing:
        parser.error("缺少原版檔案：" + "、".join(missing))

    result = {
        "schema_version": 1,
        "scope": "FD2 反向工程所使用的執行檔與唯讀遊戲資產；不含可變動的 FD2.SAV、FD2.TMP",
        "files": [digest(args.game_dir / name) for name in REFERENCE_FILES],
    }
    print(json.dumps(result, ensure_ascii=False, indent=2))
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
