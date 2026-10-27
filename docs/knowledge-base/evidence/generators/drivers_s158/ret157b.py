# 存檔:原 scratchpad 驅動腳本(續一百五十八),路徑保留當時的工作環境,不保證能直接執行(見 README.md)。
"""續一百五十七第 5 項重跑(實機,使用者 2026-10-27 核准「未確認的部分依建議逐項自動處理」):GAME OVER 回標題後,
清對話迴圈的第幾次 Return 選了新遊戲,以及 delay 的校準。
只對原版 FD2.EXE(md5 33464c81e6a364fd0660141139aa8e6e)、WSL -d Ubuntu;只改模擬器記憶體(單位資料、索爾 HP),程式碼不動,
遊戲途中不下斷點。

呼叫紀錄(修補版 dosbox-x,FD2_CALLLOG_ICOUNT=1,閘門 = show_result_resource_79)記 NATIVE 列的 EIP;
主機端在 find_empty_adjacent_tile 的清對話迴圈裡記每次送鍵 / 截圖的起訖時間(包 fd2_chapter_sweep 的 send_keys / screenshot),
方向鍵搜尋拿掉(EMPTY_TILE_SEARCH_ORDER = []),其餘照 lc131a。

用法:
  python ret157b.py entries
  python ret157b.py launch NAME
  python lc157.py hud NAME ; python lc157.py arm NAME 0 11:1 12:2 13:5 14:7 15:3 16:6
  python ret157b.py sol1 NAME           # 停住、索爾 HP = 1(讀回比對)、確認沒有斷點、恢復
  python lc157.py endturn NAME
  python ret157b.py loop NAME           # 清對話迴圈 + 計時
  python ret157b.py post NAME           # 停住讀 [0x541b0]、[0x53c03]、恢復
  python ret157b.py pull NAME
"""
from __future__ import annotations

import json
import os
import struct
import subprocess
import sys
import time
from pathlib import Path

sys.stdout.reconfigure(encoding="utf-8", line_buffering=True)
HERE = Path(__file__).resolve().parent
ROOT = HERE.parent
sys.path.insert(0, str(HERE))
REPO = Path(r"C:/Users/kg701/Desktop/GAME/fd2_re")
sys.path.insert(0, str(REPO / "tools"))
OD = REPO / ".wsl_build" / "lc157_live"

ENTRY_DIR = "/home/kg701004/fd2-calllog-s157"
ENTRY_FILE = f"{ENTRY_DIR}/entries_title2.txt"
DELTA = 0x19C000
GATE = 0x22E5C
NATIVE = {
    0x22E5C: "show_result_resource_79(GAME OVER,閘門)",
    0x1F894: "title_seq 入口",
    0x10620: "kbd_buffer_has_key(R 記錄 eax = 有沒有鍵)",
    0x4E381: "kbd_flush",
    0x1FC66: "title_seq 開場迴圈:有鍵 → 跳出",
    0x1FD7C: "選單前 call kbd_flush",
    0x370F0: "讀鍵(int386 0x16)",
    0x1FE63: "選單:讀鍵之後(掃描碼 [0x53a8e]、字元 [0x53a8d])",
    0x1FED3: "選單:確認(Enter / Space / 0xe0 / 0x52)",
    0x1FEF0: "確認後:閃爍 4 次開始",
    0x1FF31: "閃爍完:call 0x1f882 淡出",
    0x1FF36: "淡出完:清畫面",
    0x3E01D: "delay 本體(s[1] = ms)",
    0x32326: "新遊戲開場:[0x53c03] = 0x20",
}


def wsl(cmd: str, timeout: int = 60) -> str:
    r = subprocess.run(["wsl", "-d", "Ubuntu", "-e", "bash", "-c", cmd], capture_output=True, text=True,
                       encoding="utf-8", errors="replace", timeout=timeout)
    return (r.stdout + r.stderr).strip()


def rd(L, lin: int, n: int, tag: str) -> bytes | None:
    """讀回記憶體;先刪舊檔,讀不到回 None(lc157d 的教訓:舊檔會冒充讀回)。"""
    import live  # noqa: E402
    f = L.out / f"rb5_{tag}.bin"
    f.unlink(missing_ok=True)
    out = live.run(["mem", "dump", "--instance", L.i, "--selector", "0170", "--linear", f"{lin:x}",
                    "--bytecount", f"{n:x}", "--out", str(f)])
    if not f.exists() or f.stat().st_size != n:
        print(f"讀回失敗 {tag} @{lin:x}:", out.strip()[-400:])
        return None
    return f.read_bytes()


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
        sys.path.insert(0, str(ROOT))
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
    if cmd == "pull":
        OD.mkdir(parents=True, exist_ok=True)
        import fd2_chapter_sweep as sw  # noqa: E402
        dst = OD / f"{name}_title_calllog.txt"
        print(wsl(f"md5sum {wd}/FD2.EXE; cp {wd}/CALLLOG.TXT {sw.to_wsl_path(dst)} && ls -la {sw.to_wsl_path(dst)}; "
                  f"head -1 {wd}/CALLLOG.TXT", timeout=180))
        return 0
    if cmd == "loop":
        import fd2_chapter_sweep as sw  # noqa: E402
        shots = OD / f"{name}_title_loop"
        shots.mkdir(parents=True, exist_ok=True)
        assert not any(shots.iterdir()), f"{shots} 不是空的"
        rec: list[dict] = []
        o_send, o_shot = sw.send_keys, sw.screenshot

        def send(n: str, *keys: str) -> None:
            t0 = time.time()
            o_send(n, *keys)
            rec.append({"op": "send", "keys": list(keys), "t0": t0, "t1": time.time()})

        def shot(n: str, out: Path) -> Path:
            t0 = time.time()
            p = o_shot(n, out)
            rec.append({"op": "shot", "png": Path(out).name, "t0": t0, "t1": time.time()})
            return p

        sw.send_keys, sw.screenshot = send, shot
        sw.EMPTY_TILE_SEARCH_ORDER = []  # 只跑清對話迴圈;方向鍵會在選單上改選項
        log: list[str] = []
        t_start = time.time()
        found, last = sw.find_empty_adjacent_tile(name, shots, log)
        out = {"t_start": t_start, "t_end": time.time(), "found": found, "last": Path(last).name,
               "log": log, "events": rec, "clear_max": sw.DIALOGUE_CLEAR_MAX_TAPS}
        (OD / f"{name}_title_loop.json").write_text(json.dumps(out, indent=1, ensure_ascii=False), encoding="utf-8")
        print("\n".join(log))
        print("sends", sum(e["op"] == "send" for e in rec), "shots", sum(e["op"] == "shot" for e in rec))
        return 0
    from live import Live  # noqa: E402
    L = Live(name, HERE / "cl" / f"{name}_live")
    if not L.halt():
        print("停不進遊戲內容")
        return 1
    try:
        if cmd == "sol1":
            a = L.ua(0, 0x40)
            L.sm(a, struct.pack("<h", 1))
            b = rd(L, a, 4, "solhp")
            assert b is not None and struct.unpack("<hh", b)[0] == 1, b
            print("Sol HP/max", struct.unpack("<hh", b))
            L.cmd("BPLIST")
            time.sleep(0.5)
            print("bps", [x for x in L.pane().splitlines() if "BP " in x and "BPLIST" not in x])
        elif cmd == "post":
            c = rd(L, 0x541B0 + DELTA, 4, "calib")
            ch = rd(L, 0x53C03 + DELTA, 4, "c03")
            res = {"calib_541b0": struct.unpack("<i", c)[0] if c else None,
                   "c03": struct.unpack("<i", ch)[0] if ch else None, "t_host": time.time()}
            (OD / f"{name}_post.json").write_text(json.dumps(res), encoding="utf-8")
            print(res)
    finally:
        L.resume()
    return 0


if __name__ == "__main__":
    sys.exit(main(sys.argv[1:]))
