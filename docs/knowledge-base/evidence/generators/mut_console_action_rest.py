"""agentD 交叉檢查的變異測試:竄改記憶體中的終端輸出,產生器必須在交叉檢查處以 AssertionError 失敗。"""
from __future__ import annotations

import os
import runpy
import sys
import tempfile
from pathlib import Path

GEN = Path(__file__).resolve().parent
sys.path.insert(0, str(GEN))
os.environ["FD2_EVIDENCE_OUT_DIR"] = tempfile.mkdtemp()
import _console  # noqa: E402

_orig = _console.load
CASES = [
    ("ev_ai_action_choice.py", None, None, None),  # 未竄改:必須通過
    ("ev_ai_action_choice.py", "stop 9: decide unit=13 bit40=0 P=8 S=8 I=0 spell=8 ptarget=2 d=441",
     "stop 9: decide unit=13 bit40=0 P=8 S=8 I=0 spell=8 ptarget=2 d=442", "CON_VALUES[n]"),
    ("ev_ai_action_choice.py", "stop 10: -> physical 0x1548e", "stop 10: -> spell 0x1548e", "_EXEC_ADDR"),
    ("ev_ai_action_choice.py", "stop 19: decide unit=16 bit40=64", "stop 19: decide unit=16 bit40=0", "pred == got"),
    ("ev_rest_recover.py", None, None, None),
    ("ev_rest_recover.py", "stop 10: rest-entry unit=13 ret=0x13c14 +25=0 +26=0 HP=9/28",
     "stop 10: rest-entry unit=13 ret=0x13c14 +25=0 +26=0 HP=9/29", "CON_ENTRY"),
    ("ev_rest_recover.py", "stop 11: rest-write newHP=14 max=28 maxHP/5=5", "stop 11: rest-write newHP=14 max=28 maxHP/5=6",
     "CON_WRITE"),
    ("ev_rest_recover.py", "stop 11: rest-write newHP=14 max=28 maxHP/5=5", "stop 11: rest-write newHP=15 max=28 maxHP/5=5",
     "pred == got"),
]
bad = 0
for gen, old, new, where in CASES:
    def load(stem, _old=old, _new=new):
        meta, text = _orig(stem)
        if _old is not None and _old in text:
            text = text.replace(_old, _new, 1)
        return meta, text
    _console.load = load
    try:
        runpy.run_path(str(GEN / gen), run_name="__main__")
        ok = old is None
        res = "PASS(run)"
    except AssertionError as e:
        import traceback
        line = traceback.extract_tb(e.__traceback__)[-1].line
        ok = old is not None and where in line
        res = f"AssertionError at: {line}"
    bad += not ok
    print("OK " if ok else "BAD", gen, where, "->", res)
print("all ok" if bad == 0 else f"{bad} BAD")
