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
import re
import sys
from pathlib import Path

sys.path.insert(0, str(Path(__file__).resolve().parent))
import unpack_dat  # noqa: E402


def index_extracted(extracted_dir: Path) -> dict[int, Path]:
    """檔名編號 -> 路徑。**不能用排序後的位置當索引。**

    2026-09-08:原本寫 `existing = sorted(dir.glob("*.bin"))` 然後 `existing[idx]`,
    等於假設「第 idx 個檔就是編號 idx」。目前 FDOTHER 恰好 0..103 連續,所以看不
    出問題;但只要**少一個檔**,它後面每一個都會往前錯一格 —— 而「解包過期」最可能
    的形式就是缺檔或多檔。也就是說,這支工具在它最該起作用的情況下會給出錯誤答案。
    改成用檔名裡的編號查表。
    """
    out: dict[int, Path] = {}
    for p in sorted(extracted_dir.glob("*.bin")):
        m = re.search(r"_(\d+)\.bin$", p.name)
        if m:
            out[int(m.group(1))] = p
    return out


def compare(entries, extracted: dict[int, Path], wanted) -> list[dict]:
    """逐 index 比對 live 目錄長度與已解包檔案大小,回傳每一列的結果。"""
    rows = []
    for idx in sorted(wanted):
        live = entries[idx] if idx < len(entries) else None
        path = extracted.get(idx)
        live_len = live[1] if live else None
        got_len = path.stat().st_size if path else None
        rows.append({"idx": idx, "live": live_len, "extracted": got_len,
                     "name": path.name if path else None,
                     "ok": live_len == got_len})
    return rows


def selftest() -> int:
    """這支工具的價值全在它的判定,所以**必須證明它會說 STALE**。

    一個永遠回「相符」的檢查器會通過任何只驗正向的測試 —— 而它的用途正是在
    解包過期時發出警告。所以第 (2)(3) 題刻意把已解包的檔案改大小/移走,
    要求判定翻成 MISMATCH。

    第 (4) 題是同一輪修掉的錯位 bug 的回歸:原本按排序位置取檔,缺一個檔就會
    讓後面全部錯位 —— 而缺檔正是「過期」最常見的形式。
    """
    import shutil
    import tempfile
    if hasattr(sys.stdout, "reconfigure"):
        sys.stdout.reconfigure(encoding="utf-8")
        sys.stderr.reconfigure(encoding="utf-8")
    fails = []
    root = Path(__file__).resolve().parent.parent
    dat = root / "org_game" / "炎龍騎士團" / "FLAME2" / "FDOTHER.DAT"
    src = root / "extracted" / "raw" / "FDOTHER"
    if not (dat.is_file() and src.is_dir()):
        print("SKIP: 找不到 FDOTHER.DAT 或 extracted/raw/FDOTHER")
        return 0
    data = dat.read_bytes()
    entries = unpack_dat.parse_directory(data)

    print("(1) 正向:目前的解包必須與活體 .DAT 目錄完全相符")
    rows = compare(entries, index_extracted(src), range(len(entries)))
    bad = [r for r in rows if not r["ok"]]
    ok1 = not bad
    print(f"    {'PASS' if ok1 else 'FAIL'}: {len(rows)} 個 index,不符 {len(bad)}"
          + (f" 例:{bad[:2]}" if bad else ""))
    if not ok1:
        fails.append(f"目前解包已與 .DAT 不符:{bad[:2]}")

    with tempfile.TemporaryDirectory() as td:
        work = Path(td) / "FDOTHER"
        shutil.copytree(src, work)

        print("\n(2) 負向:把某個已解包檔案改大小,判定必須翻成 MISMATCH")
        victim = index_extracted(work)[7]
        victim.write_bytes(victim.read_bytes() + b"\x00" * 16)
        rows2 = compare(entries, index_extracted(work), [7])
        ok2 = not rows2[0]["ok"]
        print(f"    {'PASS' if ok2 else 'FAIL'}: idx 7 live={rows2[0]['live']} "
              f"extracted={rows2[0]['extracted']} -> ok={rows2[0]['ok']}")
        if not ok2:
            fails.append("改了大小卻仍判定相符 —— 這個檢查器沒有鑑別力")

        print("\n(3) 負向:把某個已解包檔案移走,該 index 必須判定不符")
        gone = index_extracted(work)[9]
        gone.unlink()
        rows3 = compare(entries, index_extracted(work), [9])
        ok3 = not rows3[0]["ok"] and rows3[0]["extracted"] is None
        print(f"    {'PASS' if ok3 else 'FAIL'}: idx 9 -> extracted="
              f"{rows3[0]['extracted']}、ok={rows3[0]['ok']}")
        if not ok3:
            fails.append("檔案不存在時沒有判定為不符")

        print("\n(4) 回歸:缺檔不得讓後面的 index 錯位(舊版按排序位置取檔的 bug)")
        # idx 9 已被移走。若仍按位置取檔,idx 10 之後全部會往前錯一格。
        rows4 = compare(entries, index_extracted(work), [10, 11, 50, 103])
        misaligned = [r for r in rows4 if not r["ok"]]
        ok4 = not misaligned
        print(f"    {'PASS' if ok4 else 'FAIL'}: 缺一個檔之後,idx 10/11/50/103 仍各自"
              f"對到自己的檔案(不符 {len(misaligned)})")
        if not ok4:
            fails.append(f"缺檔造成錯位:{misaligned[:2]}")

    print("\n(5) 非恆真控制:非容器輸入必須被 parse_directory 擋下")
    try:
        unpack_dat.parse_directory(b"not a container" * 8)
        ok5 = False
    except unpack_dat.NotAContainer:
        ok5 = True
    print(f"    {'PASS' if ok5 else 'FAIL'}: 非容器 -> NotAContainer")
    if not ok5:
        fails.append("非容器輸入沒有被擋下")

    if fails:
        print("\nSELFTEST FAILED:")
        for f in fails:
            print("  -", f)
        return 1
    print("\n--selftest passed(正向 + 改大小/移走兩種負向 + 缺檔錯位回歸 + "
          "非容器控制)。")
    return 0


def main() -> int:
    ap = argparse.ArgumentParser(description=__doc__, formatter_class=argparse.RawDescriptionHelpFormatter)
    ap.add_argument("--dat-file", type=Path, help="Path to the live .DAT container file.")
    ap.add_argument("--extracted-dir", type=Path, help="Path to the extracted/raw/<NAME>/ directory holding the already-unpacked resources.")
    ap.add_argument("--indices", type=str, help="Comma-separated list of specific resource indices to check (default: all).")
    ap.add_argument("--selftest", action="store_true")
    args = ap.parse_args()
    if args.selftest:
        return selftest()

    data = args.dat_file.read_bytes()
    sha256 = hashlib.sha256(data).hexdigest()
    print(f"[verify_dat_extraction_freshness] {args.dat_file}: {len(data)} bytes, sha256={sha256}")

    try:
        entries = unpack_dat.parse_directory(data)
    except unpack_dat.NotAContainer as exc:
        print(f"[verify_dat_extraction_freshness] ERROR: {args.dat_file} is not a recognized LLLLLL container: {exc}")
        return 1
    print(f"[verify_dat_extraction_freshness] live directory: {len(entries)} resources")

    extracted = index_extracted(args.extracted_dir)
    existing = sorted(extracted.values())
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
        extracted_path = extracted.get(idx)
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
