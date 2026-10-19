"""從 git blob 載入某一版的 tools/ 模組(證據記錄的是當時那版工具的行為,之後改工具不影響重算)。

續一百二十八的證據(dispatch_index_bounds_table_split)用 verify_event_dispatch_table.py 在續一百二十八提交(43027554)時的版本;
續一百二十九(cmd_table_0_9_coverage_lut_cycles)用同一版工具(之後沒有改過)與當時的 live_exec_addresses.json。
"""
from __future__ import annotations

import json
import sys
import types

from _evpaths import ROOT, git_blob

EDT_BLOB = "d10e8783e8f54e2635370369c134b27a19393afb"     # tools/verify_event_dispatch_table.py @ 43027554
EDT_PATH = ROOT / "tools" / "verify_event_dispatch_table.py"
EDT_SRC = git_blob(EDT_BLOB, "tools/verify_event_dispatch_table.py").decode("utf-8")


def load_module(name: str, src: str, path: str) -> types.ModuleType:
    """以真實路徑當 __file__ 執行原始碼,回傳模組(工具內以 __file__ 算的相對路徑照常可用)。

    Args:
        name: 模組名稱(登記在 sys.modules)。
        src: 原始碼。
        path: 當作 __file__ 的路徑。

    Returns:
        執行完的模組。
    """
    mod = types.ModuleType(name)
    mod.__file__ = path
    sys.modules[name] = mod
    if str(ROOT / "tools") not in sys.path:
        sys.path.insert(0, str(ROOT / "tools"))
    exec(compile(src, path, "exec"), mod.__dict__)
    return mod


EDT = load_module("verify_event_dispatch_table_s128", EDT_SRC, str(EDT_PATH))

# 續一百二十九的證據(cmd_table_0_9_coverage_lut_cycles)讀的實機軌跡入口表:續一百二十九提交(f2ca8d60)時的版本
LIVE_BLOB = "cbf668cca1abf97678a5cfb7e1a7dcc5436c9118"    # docs/data/live_exec_addresses.json @ f2ca8d60
LIVE_JSON = json.loads(git_blob(LIVE_BLOB, "docs/data/live_exec_addresses.json"))
