# 存檔:原 scratchpad 驅動腳本(續一百 ~ 一百三十三),路徑保留當時的工作環境,不保證能直接執行(見 README.md)。
"""續一百二十七:出戰選擇畫面,隊伍只有 12 名候選、目標 15 名時,在 0x2b0e3 cmp eax, ebp 把 EBP 改成已選人數。

只改暫存器(不改程式碼)。用法:python pick127.py INST
流程:進除錯器 → BP 0x2b0e3 → 恢復 → 送 Return(會切換游標所在那格) → 停下讀 EAX / EBP → SR EBP = EAX → 刪斷點 → 恢復。
"""
from __future__ import annotations

import sys
import time
from pathlib import Path

sys.stdout.reconfigure(encoding="utf-8", line_buffering=True)
sys.path.insert(0, str(Path(__file__).resolve().parent))
from live import DELTA, Live, run  # noqa: E402

CMP = 0x2B0E3


def main(inst: str) -> int:
    L = Live(inst, Path(__file__).resolve().parent / "cl" / f"{inst}_live")
    run(["enter-debugger", "--instance", inst])
    time.sleep(3)
    L.cmd(f"BP 0170:{CMP + DELTA:x}")
    L.resume()
    L.key("Return", 1.0)
    r = L.wait_stop(20, poll=1.0)
    if not r:
        print("沒有停在 0x2b0e3", r)
        return 1
    print("EIP", hex(r["EIP"] - DELTA), "EAX(已選)", r["EAX"], "EBP(目標)", r["EBP"])
    if r["EIP"] - DELTA != CMP:
        return 1
    L.cmd(f"SR EBP {r['EAX']:x}")
    r2 = L.regs()
    print("改後 EBP", r2.get("EBP"))
    L.cmd("BPDEL *")
    L.resume()
    time.sleep(3)
    print(L.shot("after_pick"))
    return 0 if r2.get("EBP") == r["EAX"] else 1


if __name__ == "__main__":
    sys.exit(main(sys.argv[1]))
