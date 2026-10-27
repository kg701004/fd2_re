# 存檔:原 scratchpad 驅動腳本(續一百五十七),路徑保留當時的工作環境,不保證能直接執行(見 README.md)。
"""續一百五十七(實機,使用者 2026-10-27 核准):0x2df01(0, 0xff, t, R, G, B) 是否寫 DAC 索引 255。
只對原版 FD2.EXE、WSL -d Ubuntu;只改模擬器記憶體(索爾 HP、調色盤緩衝 [0x53a65] 的索引 255),程式碼不動。

做法:在兩個呼叫點 0x1fc7b / 0x1fd64 下斷點;索爾 HP 設 1、結束回合讓敵方打倒 → GAME OVER → 回標題流程。
停在呼叫點時讀硬體 DAC(除錯器 VGA DACPAL)與調色盤緩衝,把緩衝的索引 255 改成 (1, 2, 3),在返回位址再停一次讀 DAC。
寫了 255 → DAC[255] = 由 (1, 2, 3) 算的值;沒寫 → DAC[255] 不變。索引 0..254 對照 fade6。

用法:python dac157.py NAME arm | run
"""
from __future__ import annotations

import json
import re
import struct
import subprocess
import sys
import time
from pathlib import Path

sys.stdout.reconfigure(encoding="utf-8", line_buffering=True)
HERE = Path(__file__).resolve().parent
sys.path.insert(0, str(HERE))
from live import DELTA, Live  # noqa: E402

REPO = Path(r"C:/Users/kg701/Desktop/GAME/fd2_re")
OD = REPO / ".wsl_build" / "lc157_live"
SITES = (0x1FC7B, 0x1FD64)
NAME, CMD = sys.argv[1], sys.argv[2]
L = Live(NAME, HERE / "cl" / f"{NAME}_live")


def tmux(*a: str) -> str:
    r = subprocess.run(["wsl", "-d", "Ubuntu", "tmux", "-L", "fd2harness", *a], capture_output=True, text=True,
                       encoding="utf-8", errors="replace")
    return r.stdout


def dacpal() -> list[list[int]]:
    """除錯器 VGA DACPAL(分頁,逐頁按 Enter)→ 256 組 (R, G, B)。"""
    L.cmd("VGA DACPAL")
    rows: dict[int, list[list[int]]] = {}
    for _ in range(40):
        time.sleep(0.8)
        p = tmux("capture-pane", "-t", f"harness-{NAME}", "-p")
        for ln in p.splitlines():
            m = re.match(r"^([0-9a-f]{2}): ((?:[0-9a-f]{6}[ -]){7}[0-9a-f]{6})", ln.strip())
            if m:
                rows[int(m.group(1), 16)] = [[int(h[k:k + 2], 16) for k in (0, 2, 4)] for h in re.split(r"[ -]", m.group(2))]
        if 0xF8 in rows:
            break
        if "Paged content" in p:
            tmux("send-keys", "-t", f"harness-{NAME}", "Enter")
    tail = tmux("capture-pane", "-t", f"harness-{NAME}", "-p")
    if "Paged content" in tail:
        tmux("send-keys", "-t", f"harness-{NAME}", "q")
    assert sorted(rows) == list(range(0, 256, 8)), sorted(rows)
    return [c for k in range(0, 256, 8) for c in rows[k]]


def main() -> int:
    OD.mkdir(parents=True, exist_ok=True)
    if CMD == "arm":
        assert L.halt(), "halt"
        try:
            L.sm(L.ua(0, 0x40), struct.pack("<h", 1))
            for s in SITES:
                L.cmd(f"BP 0170:{s + DELTA:x}")
            print("Sol HP", struct.unpack("<h", L.dump(L.ua(0, 0x40), 2, "hp"))[0])
            L.cmd("BPLIST")
            time.sleep(0.5)
            print("\n".join(L.pane().splitlines()[-6:]))
        finally:
            L.resume()
        return 0
    if CMD == "bp":  # 只下兩個呼叫點的斷點
        assert L.halt(), "halt"
        try:
            for s in SITES:
                L.cmd(f"BP 0170:{s + DELTA:x}")
        finally:
            L.resume()
        return 0
    if CMD == "run":  # 已停在呼叫點(由外面送鍵直到停下)
        r = L.regs()
        eip = r["EIP"] - DELTA
        assert eip in SITES, hex(r["EIP"])
        while r["ESI"] >= 0x28:  # t = 除數那一步 DAC 本來就等於緩衝,沒有判別力:跳到下一步
            L.resume()
            r = L.wait_stop(30, 0.5)
            assert r and r["EIP"] - DELTA == eip, r
        rec = {"site": hex(eip), "regs_at_call": {k: hex(v) for k, v in r.items()}}
        rec["stack"] = struct.unpack("<6i", L.dump(r["ESP"], 24, "stk")) if False else None
        before = dacpal()
        ptr = L.d32(0x53A65 + DELTA)
        buf = L.dump(ptr, 768, "pal")
        L.sm(ptr + 255 * 3, bytes([1, 2, 3]))
        buf2 = L.dump(ptr, 768, "pal2")
        assert buf2[:765] == buf[:765] and buf2[765:] == bytes([1, 2, 3])
        L.cmd(f"BP 0170:{eip + 5 + DELTA:x}")
        L.resume()
        r2 = L.wait_stop(60, 1.0)
        assert r2 and r2["EIP"] - DELTA == eip + 5, r2
        after = dacpal()
        rec.update({"t_esi": r["ESI"], "pal_ptr": hex(ptr), "dac_before": before, "dac_after": after,
                    "pal_buf_before_edit": list(buf), "pal_buf_255_set_to": [1, 2, 3], "regs_after": {k: hex(v) for k, v in r2.items()}})
        out = OD / f"dac255_{eip:x}.json"
        out.write_text(json.dumps(rec), encoding="utf-8")
        print("saved", out, "t", r["ESI"], "DAC255 before", before[255], "after", after[255],
              "DAC254 before", before[254], "after", after[254], "buf254", list(buf[762:765]))
        L.cmd("BPDEL *")
        L.resume()
        return 0
    return 2


if __name__ == "__main__":
    sys.exit(main())
