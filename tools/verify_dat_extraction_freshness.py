#!/usr/bin/env python3
"""fd2_re — verify an `extracted/raw/<NAME>/` unpack matches a live .DAT file's own directory.

背景(item 1117 SFX sample-identity調查,2026-09-06)：`0x25a96`(play_sfx_a)的index查表
算式byte-exact吻合`FDOTHER.DAT`(LLLLLL容器)的目錄格式，但算出來的resource內容(用
`extracted/raw/FDOTHER/FDOTHER_NNN.bin`核對)卻是圖片/巢狀容器，不是音效——這個矛盾其中
一個誠實列出、未證實的可能解釋是「`extracted/raw/FDOTHER/`本身對應的可能是舊版/不同版本的
FDOTHER.DAT，resource編號在版本間不保證穩定」。這個工具直接檢驗這個假說：不靠檔案hash
比對(兩個不同版本檔案總長度/hash當然不同，但這不能證明「編號位移了」，只能證明「不是同一份
檔案」——不夠具體)，而是**重新對活體.DAT檔案跑`unpack_dat.py`自己的`parse_directory`**，
逐一比對每個resource index的(offset, length)有沒有跟`extracted/raw/<NAME>/`目錄下對應
編號檔案的實際大小一致——如果某個index的長度對不上，代表該index目前對應的內容已經跟
解包當時不同，是版本飄移的直接證據；如果全部吻合，代表版本飄移這個假說可以排除。

用法:
    python tools/verify_dat_extraction_freshness.py \\
        --dat-file "C:/Users/kg701/Desktop/GAME/FD2/FDOTHER.DAT" \\
        --extracted-dir extracted/raw/FDOTHER
"""

from __future__ import annotations

import argparse
import hashlib
import sys
from pathlib import Path

sys.path.insert(0, str(Path(__file__).resolve().parent))
import unpack_dat  # noqa: E402


def main() -> int:
    ap = argparse.ArgumentParser(description=__doc__, formatter_class=argparse.RawDescriptionHelpFormatter)
    ap.add_argument("--dat-file", type=Path, required=True, help="Path to the live .DAT container file.")
    ap.add_argument("--extracted-dir", type=Path, required=True, help="Path to the extracted/raw/<NAME>/ directory holding the already-unpacked resources.")
    ap.add_argument("--indices", type=str, help="Comma-separated list of specific resource indices to check (default: all).")
    args = ap.parse_args()

    data = args.dat_file.read_bytes()
    sha256 = hashlib.sha256(data).hexdigest()
    print(f"[verify_dat_extraction_freshness] {args.dat_file}: {len(data)} bytes, sha256={sha256}")

    try:
        entries = unpack_dat.parse_directory(data)
    except unpack_dat.NotAContainer as exc:
        print(f"[verify_dat_extraction_freshness] ERROR: {args.dat_file} is not a recognized LLLLLL container: {exc}")
        return 1
    print(f"[verify_dat_extraction_freshness] live directory: {len(entries)} resources")

    existing = sorted(args.extracted_dir.glob("*.bin"))
    if not existing:
        print(f"[verify_dat_extraction_freshness] ERROR: no .bin files found under {args.extracted_dir}")
        return 1
    print(f"[verify_dat_extraction_freshness] extracted dir: {len(existing)} files")

    if args.indices:
        wanted = {int(x) for x in args.indices.split(",")}
    else:
        wanted = set(range(max(len(entries), len(existing))))

    mismatches = []
    checked = 0
    for idx in sorted(wanted):
        live = entries[idx] if idx < len(entries) else None
        extracted_path = existing[idx] if idx < len(existing) else None
        live_len = live[1] if live else None
        extracted_len = extracted_path.stat().st_size if extracted_path else None
        checked += 1
        status = "OK" if live_len == extracted_len else "MISMATCH"
        if status == "MISMATCH":
            mismatches.append((idx, live_len, extracted_len, extracted_path.name if extracted_path else None))
        print(
            f"  idx {idx:>3}: live_length={live_len!r}  extracted_length={extracted_len!r} "
            f"({extracted_path.name if extracted_path else 'MISSING'})  -> {status}"
        )

    print(f"\n[verify_dat_extraction_freshness] {checked} indices checked, {len(mismatches)} mismatches")
    if mismatches:
        print("[verify_dat_extraction_freshness] VERDICT: extraction is STALE relative to the live .DAT file for at least one index.")
        return 1
    print("[verify_dat_extraction_freshness] VERDICT: extraction matches the live .DAT file's own directory exactly -- version-drift hypothesis REFUTED for the checked indices.")
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
