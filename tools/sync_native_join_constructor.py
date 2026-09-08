#!/usr/bin/env python3
"""從雜湊綁定的 EXE 表格輸出重製端 JOIN 建構器資產。"""

import argparse
import json
from pathlib import Path


def load_json(path: Path):
    return json.loads(path.read_text(encoding="utf-8"))


def build(reference: Path, defaults: Path, growth: Path) -> dict:
    refs = load_json(reference)
    exe = next((row for row in refs.get("files", []) if row.get("file") == "FD2.EXE"), None)
    if exe is None:
        raise ValueError("reference manifest lacks FD2.EXE")
    default_rows = load_json(defaults)
    growth_rows = load_json(growth)
    if len(default_rows) < 32 or len(growth_rows) < 32:
        raise ValueError("JOIN tables must contain at least 32 rows")

    rows = []
    for idx in range(32):
        default = default_rows[idx]
        grow = growth_rows[idx]
        if default.get("idx") != idx or grow.get("idx") != idx:
            raise ValueError(f"JOIN row {idx} is not position-indexed")
        default_raw = bytes.fromhex(default.get("raw", ""))
        growth_raw = bytes.fromhex(grow.get("raw", ""))
        if len(default_raw) != 0x18 or len(growth_raw) != 0x0B:
            raise ValueError(f"JOIN row {idx} has invalid raw stride")
        rows.append(
            {
                "id": idx,
                "default_file_offset": default["off"],
                "growth_file_offset": grow["off"],
                "default_raw": default_raw.hex(),
                "growth_raw": growth_raw.hex(),
            }
        )
    return {
        "schema_version": 1,
        "source": {
            "reference_file": "docs/data/fd2-reference-files.json",
            "exe_size": exe["size"],
            "exe_md5": exe["md5"],
            "exe_sha256": exe["sha256"],
            "ida_default_table": "0x61da1",
            "ida_growth_table": "0x620a1",
            "constructor": "0x112a5",
        },
        "evidence_level": "已證實",
        "rows": rows,
    }


def selftest() -> int:
    """`build()` 幾乎全是**驗證**:它的價值就在那 4 條 raise。

    所以這裡的重點不是「跑得出東西」,是每一條驗證都要真的擋得住。它們各自對應
    一種會安靜產出錯誤 JOIN 資產的情況:manifest 沒有 FD2.EXE、表不足 32 列、
    列不是位置索引、raw stride 不對。

    第 (1) 題是**跨工具對照**:它硬編的 stride `0x18`/`0x0B` 必須等於
    `native_unit_tables.json` 裡 `lower_class`/`lower_aux` 的 `record_size`
    (那份是從 EXE 表格直接抽出、且在 artifacts 軸每輪重生比對的)。兩邊各自
    獨立,對不上就代表有一邊過期了。
    """
    import os
    import sys
    import tempfile
    if hasattr(sys.stdout, "reconfigure"):
        sys.stdout.reconfigure(encoding="utf-8")
        sys.stderr.reconfigure(encoding="utf-8")
    fails = []
    root = Path(__file__).resolve().parent.parent
    ref = root / "docs" / "data" / "fd2-reference-files.json"
    dfl = root / "docs" / "data" / "exe_tables" / "character_defaults.json"
    grw = root / "docs" / "data" / "exe_tables" / "growth.json"
    nut = root / "docs" / "data" / "exe_tables" / "native_unit_tables.json"

    print("(1) 跨工具對照:硬編的 stride 必須等於 native_unit_tables 的 record_size")
    if nut.is_file():
        sizes = {k: v["record_size"]
                 for k, v in load_json(nut)["tables"].items()}
        ok1 = sizes.get("lower_class") == 0x18 and sizes.get("lower_aux") == 0x0B
        print(f"    {'PASS' if ok1 else 'FAIL'}: lower_class {sizes.get('lower_class')}"
              f"(硬編 {0x18})、lower_aux {sizes.get('lower_aux')}(硬編 {0x0B})")
        if not ok1:
            fails.append(f"stride 與 native_unit_tables 不符:{sizes}")
    else:
        print("    SKIP: 找不到 native_unit_tables.json")

    if not (ref.is_file() and dfl.is_file() and grw.is_file()):
        print("    SKIP: 缺少輸入 JSON,其餘檢查無法進行")
        return 1 if fails else 0

    print("\n(2) 正向:真實輸入必須建出 32 列,且每列的 raw 長度符合 stride")
    out = build(ref, dfl, grw)
    rows = out["rows"]
    ok2 = (len(rows) == 32
           and all(r["id"] == i for i, r in enumerate(rows))
           and all(len(bytes.fromhex(r["default_raw"])) == 0x18 for r in rows)
           and all(len(bytes.fromhex(r["growth_raw"])) == 0x0B for r in rows))
    print(f"    {'PASS' if ok2 else 'FAIL'}: {len(rows)} 列,id 連續、raw 長度一致")
    if not ok2:
        fails.append(f"正向建構結果不符:{len(rows)} 列")

    print("\n(3) 四條驗證各自的故障注入 —— 每一條都要真的擋得住")
    defaults = load_json(dfl)
    growth = load_json(grw)
    with tempfile.TemporaryDirectory() as td:
        def write(name, obj):
            p = Path(td) / name
            p.write_text(json.dumps(obj, ensure_ascii=False), encoding="utf-8")
            return p

        cases = [
            ("manifest 沒有 FD2.EXE",
             (write("r.json", {"files": [{"file": "OTHER.DAT"}]}), dfl, grw)),
            ("表不足 32 列",
             (ref, write("d.json", defaults[:10]), grw)),
            ("列不是位置索引",
             (ref, write("d2.json", [dict(r, idx=99) for r in defaults]), grw)),
            ("raw stride 不對",
             (ref, write("d3.json", [dict(r, raw="00" * 7) for r in defaults]), grw)),
        ]
        for label, args in cases:
            try:
                build(*args)
                print(f"    FAIL: 「{label}」沒有被擋下")
                fails.append(f"{label} 沒有被擋下")
            except ValueError:
                print(f"    PASS: 「{label}」-> ValueError")
            except Exception as exc:                          # noqa: BLE001
                print(f"    FAIL: 「{label}」丟出 {type(exc).__name__}")
                fails.append(f"{label} 丟出 {type(exc).__name__}")

    print("\n(4) 非恆真控制:上面全都丟錯也會通過,所以確認正向那半仍建得出來")
    ok4 = len(build(ref, dfl, grw)["rows"]) == 32
    print(f"    {'PASS' if ok4 else 'FAIL'}: 真實輸入仍建出 32 列")
    if not ok4:
        fails.append("正向建構失效")

    if fails:
        print("\nSELFTEST FAILED:")
        for f in fails:
            print("  -", f)
        return 1
    print("\n--selftest passed(stride 跨工具對照 + 正向 + 四條驗證的故障注入 + "
          "非恆真控制)。")
    return 0


def main() -> int:
    import sys
    if len(sys.argv) == 2 and sys.argv[1] == "--selftest":
        return selftest()
    parser = argparse.ArgumentParser()
    parser.add_argument("reference", type=Path)
    parser.add_argument("defaults", type=Path)
    parser.add_argument("growth", type=Path)
    parser.add_argument("output", type=Path)
    mode = parser.add_mutually_exclusive_group(required=True)
    mode.add_argument("--check", action="store_true")
    mode.add_argument("--write", action="store_true")
    args = parser.parse_args()

    rendered = json.dumps(
        build(args.reference, args.defaults, args.growth),
        ensure_ascii=False,
        indent=2,
    ) + "\n"
    if args.check:
        if not args.output.exists() or args.output.read_text(encoding="utf-8") != rendered:
            raise SystemExit(f"{args.output} is not synchronized")
        print(f"verified {args.output}")
        return 0
    args.output.write_text(rendered, encoding="utf-8")
    print(f"wrote {args.output}")
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
