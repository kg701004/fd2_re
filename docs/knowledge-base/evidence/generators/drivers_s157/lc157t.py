# 存檔:原 scratchpad 驅動腳本(續一百五十七),路徑保留當時的工作環境,不保證能直接執行(見 README.md)。
"""續一百五十七第 2 項(實機,使用者 2026-10-27 核准):光束炮相位迴圈裡 redraw 的內部時間,第一輪擺法 vs 第二輪擺法。
只對原版 FD2.EXE、WSL -d Ubuntu;只改模擬器記憶體(單位資料、游標),程式碼不動,遊戲途中不下斷點。

修補版 dosbox-x(tools/dosbox/fd2_calllog_patch.py 續一百五十七版)以 FD2_CALLLOG_ICOUNT=1 在 E / R / A 行尾附
i=遊戲選擇子指令數 n=全部指令數 t=PIC_FullIndex(ms);FD2_CALLLOG_GATE = ai_item_action 入口,之前不寫 E。

用法:
  python lc157t.py entries
  python lc157t.py launch NAME
  python lc157t.py hud NAME | arm NAME | armC NAME | endturn NAME     # 沿用 lc130 / lc131
  python lc157t.py laps NAME                                          # 數 0x152ba 的 E 筆數
  python lc157t.py pull NAME                                          # 複製紀錄到 .wsl_build/lc157_live/
"""
from __future__ import annotations

import os
import subprocess
import sys
from pathlib import Path

sys.stdout.reconfigure(encoding="utf-8", line_buffering=True)
HERE = Path(__file__).resolve().parent
ROOT = HERE.parent
sys.path.insert(0, str(ROOT))      # lc130 / lc131 / cl / live 用 scratchpad 根目錄那一份
REPO = Path(r"C:/Users/kg701/Desktop/GAME/fd2_re")
sys.path.insert(0, str(REPO / "tools"))

ENTRY_DIR = "/home/kg701004/fd2-calllog-s157"
ENTRY_FILE = f"{ENTRY_DIR}/entries_redraw.txt"
DELTA = 0x19C000
GATE = 0x15055                      # ai_item_action 入口
NATIVE = {
    0x15055: "ai_item_action 入口(閘門)",
    0x152A0: "相位迴圈每圈開頭(ebx = k)",
    0x152BA: "redraw(1) + wait_ticks(1) 之後",
    0x11CAC: "redraw",
    0x1297D: "redraw 第 1 個呼叫",
    0x11EEE: "draw_terrain_layer",
    0x122DC: "draw_move_range_overlay",
    0x127A9: "單位層",
    0x1ACF3: "draw_map_hud",
    0x11EB0: "逐列複製(redraw 收尾送畫面;地形層 0x120fe 也呼叫)",
    0x17AA9: "wait_ticks",
    0x12117: "地形層 [0x51a93] == -1 分支(eax = tick)",
    0x12132: "推進 [0x53c1f]",
    0x12169: "取換色表之前(eax = 階)",
    0x4EEE0: "地形層 0x11f76 呼叫",
    0x4E016: "blit_tile24_rle_remap",
    0x4E22A: "24 × 24 貼圖(彩色)",
    0x4E1A6: "24 × 24 貼圖(灰階)",
    0x24D22: "地形層 0x120b1 呼叫",
    0x12E38: "地形層 0x12291 呼叫",
    0x127E0: "draw_unit_sprite",
    0x129EC: "單位層 0x127d9 呼叫",
    0x34894: "單位層 0x127c2 呼叫",
}


def wsl(cmd: str, timeout: int = 60) -> str:
    r = subprocess.run(["wsl", "-d", "Ubuntu", "-e", "bash", "-c", cmd], capture_output=True, text=True,
                       encoding="utf-8", errors="replace", timeout=timeout)
    return (r.stdout + r.stderr).strip()


def rd(L, lin: int, n: int, tag: str) -> bytes | None:
    """讀回記憶體;先刪舊檔,讀不到時印 helper 輸出並回 None(lc157d:mem dump 靜默失敗,舊檔可能冒充讀回)。"""
    import live  # noqa: E402
    f = L.out / f"rb_{tag}.bin"
    f.unlink(missing_ok=True)
    out = live.run(["mem", "dump", "--instance", L.i, "--selector", "0170", "--linear", f"{lin:x}",
                    "--bytecount", f"{n:x}", "--out", str(f)])
    if not f.exists() or f.stat().st_size != n:
        print(f"讀回失敗 {tag} @{lin:x}:", out.strip()[-400:])
        return None
    return f.read_bytes()


def expected(L) -> list[tuple[str, int, bytes]]:
    """第二輪擺法(lc130 arm + lc131 armC)寫入後應有的位元組。"""
    import struct
    exp = [("#11 xy", L.ua(11, 0), bytes([19, 14])), ("#11 slot2", L.ua(11, 0xE), bytes([0x00, 79])),
           ("#1 HP", L.ua(1, 0x40), struct.pack("<h", 782)), ("#0 f5", L.ua(0, 5), bytes([0]))]
    exp += [(f"#{i} f5", L.ua(i, 5), bytes([0x80])) for i in (1, 2, 3, 4)]
    exp += [("#5 xy", L.ua(5, 0), bytes([8, 7])), ("#10 xy", L.ua(10, 0), bytes([6, 9])),
            ("#0 HP", L.ua(0, 0x40), struct.pack("<h", 167)), ("#0 MV", L.ua(0, 0x3B), bytes([30]))]
    return exp


def verify(L) -> int:
    """已停住時逐欄讀回;全部相符回 0。"""
    bad = 0
    for tag, lin, want in expected(L):
        got = rd(L, lin, len(want), tag.replace("#", "u").replace(" ", "_"))
        ok = got == want
        bad += not ok
        print(f"  {'OK ' if ok else 'BAD'} {tag:10s} want {want.hex()} got {got.hex() if got else None}")
    return 1 if bad else 0


def arm_c(name: str) -> int:
    """lc130 arm → 停住 → armC 的四筆寫入 → 逐欄讀回;任何一步失敗都回非 0,不往下做。"""
    import struct
    import time
    import lc130  # noqa: E402
    import lc131  # noqa: E402
    rc = lc130.main(["arm", name])
    if rc:
        print("lc130 arm rc", rc)
        return rc
    time.sleep(7)
    L = lc131.live(name)
    if not L.halt():
        print("停不進遊戲內容")
        return 1
    try:
        for lin, data in ((L.ua(5, 0), bytes([8, 7])), (L.ua(10, 0), bytes([6, 9])),
                          (L.ua(0, 0x40), struct.pack("<h", 167)), (L.ua(0, 0x3B), bytes([30]))):
            L.sm(lin, data)
        return verify(L)
    finally:
        L.resume()


def check(name: str) -> int:
    """恢復執行後再停一次讀回(確認遊戲沒有把寫入蓋掉)。"""
    import lc131  # noqa: E402
    L = lc131.live(name)
    if not L.halt():
        print("停不進遊戲內容")
        return 1
    try:
        return verify(L)
    finally:
        L.resume()


def main(argv: list[str]) -> int:
    cmd = argv[0]
    if cmd == "entries":
        body = " ".join(f"{a + DELTA:x}" for a in sorted(NATIVE))
        print(wsl(f"mkdir -p {ENTRY_DIR} && printf '%s\\n' '{body}' > {ENTRY_FILE} && cat {ENTRY_FILE}"))
        return 0
    name = argv[1]
    wd = f"/home/kg701004/fd2-run-harness-{name}"
    if cmd == "launch":
        os.environ["FD2_HARNESS_DOSBOX_BIN"] = "/home/kg701004/fd2-dosbox-calllog/dosbox-x/src/dosbox-x"
        import cl  # noqa: E402  (cl 在 import 時設好 FD2_HARNESS_CALLLOG,下面覆寫)
        os.environ["FD2_HARNESS_CALLLOG"] = ENTRY_FILE
        os.environ["FD2_HARNESS_CALLLOG_CAP"] = "100000000"
        os.environ["FD2_HARNESS_CALLLOG_DUMP"] = "0"
        os.environ["FD2_HARNESS_CALLLOG_ICOUNT"] = "1"
        os.environ["FD2_HARNESS_CALLLOG_GATE"] = f"{GATE + DELTA:x}"
        extra = ("FD2_HARNESS_CALLLOG_CAP", "FD2_HARNESS_CALLLOG_DUMP", "FD2_HARNESS_CALLLOG_ICOUNT",
                 "FD2_HARNESS_CALLLOG_GATE")
        w = [x for x in os.environ.get("WSLENV", "").split(":") if x]
        os.environ["WSLENV"] = ":".join(w + [v for v in extra if v not in w])
        return cl.main(["battle", name, "1"])
    if cmd in ("hud", "arm", "endturn"):
        import lc130  # noqa: E402
        return lc130.main([cmd, name])
    if cmd == "armC":
        return arm_c(name)
    if cmd == "check":
        return check(name)
    if cmd == "laps":
        print(wsl(f"head -1 {wd}/CALLLOG.TXT; grep -c '^E [0-9]* {0x152BA + DELTA:08x} ' {wd}/CALLLOG.TXT; "
                  f"grep -c '^E [0-9]* {GATE + DELTA:08x} ' {wd}/CALLLOG.TXT; stat -c %s {wd}/CALLLOG.TXT"))
        return 0
    if cmd == "pull":
        import fd2_chapter_sweep as sw  # noqa: E402
        od = REPO / ".wsl_build" / "lc157_live"
        od.mkdir(parents=True, exist_ok=True)
        dst = od / f"{name}_redraw_icount.txt"      # 不用 *_CALLLOG.TXT(行尾有附加欄位,閘門解析器不收)
        print(wsl(f"cp {wd}/CALLLOG.TXT {sw.to_wsl_path(dst)} && sha256sum {wd}/CALLLOG.TXT {sw.to_wsl_path(dst)} "
                  f"&& ls -la {sw.to_wsl_path(dst)}"))
        return 0
    print(__doc__)
    return 2


if __name__ == "__main__":
    sys.exit(main(sys.argv[1:]))
