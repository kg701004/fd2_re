#!/usr/bin/env python3
"""safe_output.py — 輸出路徑防護:不讓 JSON 產生器把非 JSON 的既有檔案吃掉。

為什麼需要這一層
----------------
2026-09-04 全工具重驗時,`extract_event_id_groups.py` 被以
`extract_event_id_groups.py <EXE> <輸出>` 呼叫——但**它的 `argv[1]` 是輸出路徑**,
於是 509158 B 的參考 `FD2.EXE` 被 12 KB 的 JSON 覆寫。倉庫裡 `org_game/` 是
gitignore 的,沒有 git 副本;能救回來純粹是因為 `fd2_dosbox_live_helper.sh` 另外
留了 `~/fd2-run/FD2.EXE.pristine_bak` 並記著 pristine md5。

根因不是打錯字,是**參數慣例不一致**:這個目錄下幾乎每支工具第一個位置參數都是
*輸入*,只有它是*輸出*。慣例不一致沒辦法靠記憶避免,只能靠工具自己擋。

規則(刻意只有一條,才不會被繞過)
----------------------------------
要寫 JSON 到一個**已存在**的檔案時,該檔案必須本來就是 JSON。
不是 JSON 就代表呼叫端把別的東西當成輸出路徑了——執行檔、二進位資產、原始
dump 都會在這裡被擋下,而且是在 `open(..., "w")` 截斷檔案**之前**。

不做的事:不備份、不改名、不猜使用者意圖。只拒絕並說明。
"""

from __future__ import annotations

import json
import os
from pathlib import Path

__all__ = ["guard_json_output", "UnsafeOutputPath"]


class UnsafeOutputPath(Exception):
    """輸出路徑指向一個不是 JSON 的既有檔案。"""


def guard_json_output(path: str | os.PathLike[str], *, probe_bytes: int = 4096) -> Path:
    """檢查 `path` 可以安全地被寫成 JSON,回傳 `Path`。

    * 檔案不存在 → 通過(只確認上層目錄在)。
    * 檔案存在且能被解析成 JSON → 通過(這是正常的重生)。
    * 檔案存在但不是 JSON → 丟 `UnsafeOutputPath`,**不動那個檔案**。

    只讀開頭 `probe_bytes` 就能判掉二進位;完整解析留給文字檔,避免把大 JSON
    整份讀進來只為了做一次檢查。
    """
    p = Path(path)
    parent = p.parent if str(p.parent) else Path(".")
    if not parent.is_dir():
        raise UnsafeOutputPath(f"輸出目錄不存在: {parent}")
    if not p.exists():
        return p
    if p.is_dir():
        raise UnsafeOutputPath(f"輸出路徑是目錄,不是檔案: {p}")

    head = p.open("rb").read(probe_bytes)
    if b"\x00" in head:
        raise UnsafeOutputPath(
            f"拒絕覆寫 {p}({p.stat().st_size} bytes):內容含 NUL,是二進位檔而不是 JSON。"
            f"\n這通常表示位置參數放反了——請確認該工具的輸出參數位置。")
    try:
        json.loads(p.read_text(encoding="utf-8"))
    except (UnicodeDecodeError, json.JSONDecodeError) as exc:
        raise UnsafeOutputPath(
            f"拒絕覆寫 {p}({p.stat().st_size} bytes):既有內容不是有效的 JSON({exc.__class__.__name__})。"
            f"\n這通常表示位置參數放反了——請確認該工具的輸出參數位置。") from exc
    return p


def _selftest() -> int:
    import tempfile

    fails: list[str] = []

    def check(name: str, cond: bool) -> None:
        print(f"  {'✓' if cond else '✗'} {name}")
        if not cond:
            fails.append(name)

    with tempfile.TemporaryDirectory() as td:
        d = Path(td)

        # 1. 不存在的檔案:放行
        ok = True
        try:
            guard_json_output(d / "new.json")
        except UnsafeOutputPath:
            ok = False
        check("不存在的輸出路徑放行", ok)

        # 2. 既有 JSON:放行(正常重生)
        j = d / "old.json"
        j.write_text('{"a": 1}', encoding="utf-8")
        ok = True
        try:
            guard_json_output(j)
        except UnsafeOutputPath:
            ok = False
        check("既有 JSON 放行(重生)", ok)

        # 3. **真正要擋的那個**:MZ 執行檔
        exe = d / "FD2.EXE"
        exe.write_bytes(b"MZ\x90\x00\x03\x00\x00\x00" + bytes(512))
        blocked = False
        try:
            guard_json_output(exe)
        except UnsafeOutputPath:
            blocked = True
        check("擋下 MZ 執行檔(2026-09-04 實際事故的形狀)", blocked)
        check("被擋下時原檔完全沒被動到", exe.read_bytes()[:2] == b"MZ" and exe.stat().st_size == 520)

        # 4. 文字但非 JSON
        txt = d / "notes.md"
        txt.write_text("# 標題\n內文\n", encoding="utf-8")
        blocked = False
        try:
            guard_json_output(txt)
        except UnsafeOutputPath:
            blocked = True
        check("擋下非 JSON 文字檔", blocked)

        # 5. 對照組:確認 2 與 3 不是同一條路徑造成的——把 JSON 改成二進位後必須翻面
        j.write_bytes(b"\x00\x01\x02")
        blocked = False
        try:
            guard_json_output(j)
        except UnsafeOutputPath:
            blocked = True
        check("對照組:同一路徑內容改為二進位後改判為擋下", blocked)

        # 6. 目錄
        blocked = False
        try:
            guard_json_output(d)
        except UnsafeOutputPath:
            blocked = True
        check("擋下目錄", blocked)

    print(f"\nsafe_output 自驗:{'全部通過 ✓' if not fails else '失敗 ' + str(fails)}")
    return 0 if not fails else 1


if __name__ == "__main__":
    import sys

    # `--selftest` 是本目錄的慣例旗標,verify_all_tools.py 的 selftest 層靠它辨識;
    # 裸執行也跑自驗,因為這支沒有別的用途。
    if len(sys.argv) > 1 and sys.argv[1] not in ("--selftest", "-h", "--help"):
        print(__doc__)
        print("用法: safe_output.py [--selftest]   (函式庫,由其他工具 import)")
        sys.exit(2)
    if len(sys.argv) > 1 and sys.argv[1] in ("-h", "--help"):
        print(__doc__)
        print("用法: safe_output.py [--selftest]   (函式庫,由其他工具 import)")
        sys.exit(0)
    sys.exit(_selftest())
