# 存檔:原 scratchpad 驅動腳本(續一百 ~ 一百三十三),路徑保留當時的工作環境,不保證能直接執行(見 README.md)。
"""續一百零四:s104 停在開機,BPINT 21 4B 逐次 RUN,DS:DX 是 FD2.EXE 時刪斷點、LOGC 7FFFFFFF(會恢復執行)。"""
import os
import re
import sys
import time
import importlib.util
from pathlib import Path

os.environ["S103_NAME"] = "s104"
here = Path(__file__).resolve().parent
spec = importlib.util.spec_from_file_location("drv", here / "s103.py")
drv = importlib.util.module_from_spec(spec)
sys.argv = ["x"]
spec.loader.exec_module(drv)

drv.dbg("BPINT 21 4B")
for i in range(8):
    drv.dbg("RUN")
    time.sleep(3)
    if not drv.wait_halt(60):
        print("did not halt; abort")
        sys.exit(1)
    drv.dbg("D DS:DX")
    time.sleep(1)
    pane = drv.pane()
    m = re.search(r"Data view.*?\n([0-9A-F]{4}:[0-9A-F]{8}[^\n]*)", pane, re.S)
    line = m.group(1) if m else "?"
    print(i, line[-20:])
    if "FD2.EXE" in line:
        drv.dbg("BPDEL 0")
        drv.dbg("BPLIST")
        print("\n".join(drv.pane().splitlines()[-4:]))
        drv.dbg("LOGC 7FFFFFFF")
        time.sleep(3)
        print("running", drv.running(), drv.wsl(f"stat -c %s {drv.WD}/LOGCPU.TXT"))
        sys.exit(0)
print("FD2.EXE EXEC not seen")
sys.exit(1)
