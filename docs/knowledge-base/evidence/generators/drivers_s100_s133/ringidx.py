# 存檔:原 scratchpad 驅動腳本(續一百 ~ 一百三十三),路徑保留當時的工作環境,不保證能直接執行(見 README.md)。
"""python ringidx.py NAME:停機讀 [0x53c57](指令環選項)與 [0x53a45](單位陣列指標,判斷 selector 是否為遊戲的),再恢復執行。"""
import sys
import time

sys.path.insert(0, r"C:/Users/kg701/Desktop/GAME/fd2_re/tools")
import fd2_chapter_sweep as sw  # noqa: E402

name = sys.argv[1]
sw.enter_debugger(name)
time.sleep(2)
for _ in range(3):
    ptr = sw.read_mem(name, 0x53a45 + 0x19C000, 4)
    if ptr and int.from_bytes(ptr, "little") == 0x26BDC8:
        break
    sw.debugger_cmd(name, "RUN")
    time.sleep(1.5)
    sw.enter_debugger(name)
    time.sleep(2)
idx = sw.read_mem(name, 0x53C57 + 0x19C000, 4)
print("unit ptr", ptr.hex() if ptr else None, "ring idx [0x53c57]", idx.hex() if idx else None)
sw.debugger_cmd(name, "RUN")
time.sleep(1)
print("pane tail:", [x for x in sw.capture_pane(name).splitlines() if x.strip()][-1:])
