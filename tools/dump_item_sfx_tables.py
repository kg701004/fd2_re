#!/usr/bin/env python3
"""fd2_re — dump the three 33-byte item-effect SFX tables at 0x51f33/0x51f54/0x51f75 in full.

背景(item 1117 SFX sample-identity調查,2026-09-06)：`FUN_0001c4cc`(item effect共用受擊/
演出迴圈)一開頭把三張表從靜態資料複製到自己的stack frame——`0x51f33`→`abStack_84`(每個
effect子類型的最大播放幀數門檻)、`0x51f54`→`local_3c`(resource sub-index，用途未完全確認)、
`0x51f75`→`local_60`(**這張表的值同時是「該幀是否觸發播放SFX」的布林條件，也是實際傳給
`play_sfx_a`(`0x25a96`)的`index`引數本身**——見`docs/knowledge-base/91-worklist.md`item 1117
「2026-09-06再續十」節的byte-exact反組譯佐證)。之前只手動dump過index13(type11/MP恢復)這
一格，這個工具把三張表**全部33個byte**一次dump出來，讓每個已知呼叫`FUN_0001c4cc`的effect
type都能直接查出自己的`local_60[param_2]`(SFX播放與否+sample index)，不必再逐一手動`bytes`。

用法:
    python tools/dump_item_sfx_tables.py
    python tools/dump_item_sfx_tables.py --output docs/data/item_sfx_tables.json
    # 2026-09-08 勘誤:本行原本還寫著 `--types-json docs/data/item_sfx_dispatch_types.json`,
    # 但**那個輸入檔不在 repo 裡**,照抄會直接 FileNotFoundError。已提交的
    # item_sfx_tables.json 的 `per_type_lookup` 區塊就是用它產的,因此該區塊目前無法重現;
    # 核心的 `tables` 區塊不需要它,重生後與 committed 版逐位元組相同。
"""

from __future__ import annotations

import argparse
import json
from pathlib import Path

import ghidra_batch_probe as gbp
import capstone_probe as cprobe

TABLE_LEN = 33

TABLES = {
    "abStack_84_max_frame": 0x51F33,
    "local_3c_resource_subindex": 0x51F54,
    "local_60_trigger_and_index": 0x51F75,
}


def dump_tables(*, ghidra_install, project_dir, project_name, process_name, timeout, quiet) -> dict:
    out = {}
    for name, addr in TABLES.items():
        data = cprobe.fetch_bytes(
            addr, TABLE_LEN,
            ghidra_install=ghidra_install, project_dir=project_dir, project_name=project_name,
            process_name=process_name, timeout=timeout, quiet=quiet,
        )
        out[name] = {
            "address": hex(addr),
            "length": TABLE_LEN,
            "bytes_hex": data.hex(),
            "bytes_dec": list(data),
        }
    return out


def main() -> int:
    ap = argparse.ArgumentParser(description=__doc__, formatter_class=argparse.RawDescriptionHelpFormatter)
    ap.add_argument("--types-json", type=Path, help="Optional JSON mapping {item_effect_type: param_2_index} to annotate the output with per-type lookups.")
    ap.add_argument("--output", type=Path, help="Path to write the full dump (and per-type lookup, if --types-json given) as JSON.")
    ap.add_argument("--ghidra", default=gbp.DEFAULT_GHIDRA_INSTALL)
    ap.add_argument("--project-dir", default=gbp.DEFAULT_PROJECT_DIR)
    ap.add_argument("--project-name", default=gbp.DEFAULT_PROJECT_NAME)
    ap.add_argument("--process-name", default=gbp.DEFAULT_PROCESS_NAME)
    ap.add_argument("--timeout", type=int, default=600)
    ap.add_argument("--quiet", action="store_true")
    args = ap.parse_args()

    tables = dump_tables(
        ghidra_install=args.ghidra, project_dir=args.project_dir, project_name=args.project_name,
        process_name=args.process_name, timeout=args.timeout, quiet=args.quiet,
    )

    for name, t in tables.items():
        print(f"{name} @ {t['address']}: {t['bytes_hex']}")

    result: dict = {"tables": tables}

    if args.types_json:
        types = json.loads(args.types_json.read_text(encoding="utf-8"))
        local_60 = tables["local_60_trigger_and_index"]["bytes_dec"]
        local_3c = tables["local_3c_resource_subindex"]["bytes_dec"]
        max_frame = tables["abStack_84_max_frame"]["bytes_dec"]
        lookups = {}
        for type_name, param_2 in types.items():
            if not isinstance(param_2, int) or not (0 <= param_2 < TABLE_LEN):
                lookups[type_name] = {"param_2": param_2, "note": "param_2 not a resolved static index in [0,33)"}
                continue
            lookups[type_name] = {
                "param_2": param_2,
                "local_60_trigger_and_index": local_60[param_2],
                "plays_sound_frame0": local_60[param_2] != 0,
                "local_3c_resource_subindex": local_3c[param_2],
                "abStack_84_max_frame": max_frame[param_2],
            }
            print(
                f"  type {type_name}: param_2={param_2} -> local_60={local_60[param_2]} "
                f"(plays_sound_frame0={local_60[param_2] != 0}), local_3c={local_3c[param_2]}, "
                f"max_frame={max_frame[param_2]}"
            )
        result["per_type_lookup"] = lookups

    if args.output:
        args.output.write_text(json.dumps(result, indent=2), encoding="utf-8")
        print(f"[dump_item_sfx_tables] wrote {args.output}")

    return 0


if __name__ == "__main__":
    raise SystemExit(main())
