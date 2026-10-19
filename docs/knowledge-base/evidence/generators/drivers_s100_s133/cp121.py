# 存檔:原 scratchpad 驅動腳本(續一百 ~ 一百三十三),路徑保留當時的工作環境,不保證能直接執行(見 README.md)。
"""續一百二十一(第 3 項):copy_protection_password_check 的比對迴圈是否恆通過 —— DOSBox-X 實機(只對原版 FD2.EXE,只改模擬器記憶體)。

用法(instance 固定 cp121):
  python cp121.py state            # 停住,印 0x118a3 的 16 bytes、[0x51a42]、[0x53a44],恢復
  python cp121.py arm              # 停住:0x118aa 的 EB 改 75(續四十的正向對照同一個 byte)、[0x51a42] 設 0、設 4 個斷點,恢復
  python cp121.py wait [秒]        # 等斷點;停在比對迴圈就印 答案 3 bytes / 已輸入 3 bytes
  python cp121.py resume
  python cp121.py bpdel
斷點(native 位址):0x34228 比對一格、0x34235 記「有不一樣」(靜態說跳不到)、0x34243 答錯的路、0x342af 答對的路。
"""
from __future__ import annotations

import sys
import time
from pathlib import Path

sys.path.insert(0, str(Path(__file__).resolve().parent))
from live import DELTA, Live, run  # noqa: E402

INST = "cp121"
L = Live(INST, Path(__file__).resolve().parent / "cl" / f"{INST}_live")
BPS = {0x34228: "比對一格", 0x34235: "記「有不一樣」", 0x34243: "答錯的路", 0x342AF: "答對的路"}


def state() -> None:
    print("0x118a3:", L.dump(0x118A3 + DELTA, 16, "jb").hex(" "))
    print("[0x51a42] =", L.dump(0x51A42 + DELTA, 1, "ctr").hex(), " [0x53a44] =", L.dump(0x53A44 + DELTA, 1, "ok").hex())


def report_stop(r: dict[str, int] | None) -> None:
    if r is None:
        print("沒有停(逾時)")
        return
    eip = r.get("EIP", 0)
    nat = eip - DELTA
    print("停在 EIP", hex(eip), "native", hex(nat), BPS.get(nat, "(不是設的斷點)"),
          {k: hex(v) for k, v in r.items() if k in ("EAX", "EBX", "EDX", "EDI", "ESP")})
    if nat in (0x34228, 0x34235, 0x34243, 0x342AF):
        ans = L.dump(r["EDI"], 3, "ans") if nat == 0x34228 else b""
        esp = r["ESP"]
        print("  已輸入 [esp+0x30..0x32] =", L.dump(esp + 0x30, 3, "inp").hex(" "), " 旗標 [esp+0x34] =", L.dump(esp + 0x34, 1, "flag").hex(),
              " 答錯次數 [esp+0x3c] =", L.dump(esp + 0x3C, 1, "tries").hex(), (" 答案 [edi..] = " + ans.hex(" ")) if ans else "")
        print("  [0x53a44] =", L.dump(0x53A44 + DELTA, 1, "ok").hex())


def main(argv: list[str]) -> int:
    cmd = argv[0]
    if cmd == "resume":
        L.resume()
    elif cmd == "wait":
        report_stop(L.wait_stop(float(argv[1]) if len(argv) > 1 else 30))
    elif cmd == "bpdel":
        for a in BPS:
            print(L.cmd(f"BPDEL 0170:{a + DELTA:x}")[-80:].strip())
    elif cmd in ("state", "arm"):
        if not L.halt():
            print("停不進遊戲內容")
            return 1
        try:
            state()
            if cmd == "arm":
                L.sm(0x118AA + DELTA, b"\x75")
                L.sm(0x51A42 + DELTA, b"\x00")
                for a in BPS:
                    L.cmd(f"BP 0170:{a + DELTA:x}")
                time.sleep(0.5)
                print("-- 改完:")
                state()
                print(L.cmd("BPLIST")[-400:])
        finally:
            L.resume()
    elif cmd == "raw":
        print(run(argv[1:]))
    else:
        print(__doc__)
        return 2
    return 0


if __name__ == "__main__":
    sys.exit(main(sys.argv[1:]))
