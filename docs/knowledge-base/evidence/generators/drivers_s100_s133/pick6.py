# 存檔:原 scratchpad 驅動腳本(續一百 ~ 一百三十三),路徑保留當時的工作環境,不保證能直接執行(見 README.md)。
"""cl6 出擊選人:讀 / 改旗標陣列(sortie_member_select 堆疊上,0x1f15e4,32 bytes)。

用法: python pick6.py peek | python pick6.py set HEX32
"""
from __future__ import annotations

import sys
import time
from pathlib import Path

sys.path.insert(0, str(Path(__file__).resolve().parent))
from live import Live, run  # noqa: E402

FLAGS = 0x1F15E4
L = Live("cl6", Path(__file__).resolve().parent / "cl" / "cl6_live")


def main(argv: list[str]) -> int:
    run(["enter-debugger", "--instance", "cl6"])
    time.sleep(3)
    try:
        b = L.dump(FLAGS, 32, "flags")
        print("flags", b.hex(), "nonzero(first 16)", sum(1 for x in b[:16] if x))
        if argv and argv[0] == "set":
            L.sm(FLAGS, bytes.fromhex(argv[1]))
            b = L.dump(FLAGS, 32, "flags")
            print("now  ", b.hex(), "nonzero(first 16)", sum(1 for x in b[:16] if x))
    finally:
        run(["resume", "--instance", "cl6"])
    return 0


if __name__ == "__main__":
    sys.exit(main(sys.argv[1:]))
