"""變異測試:竄改終端輸出原始紀錄的一處,產生器必須以 AssertionError 失敗(證明解析與交叉核對會說不)。"""
from __future__ import annotations

import os
import runpy
import sys
import tempfile
from pathlib import Path

GEN = Path(__file__).resolve().parent
sys.path.insert(0, str(GEN))
os.environ["FD2_EVIDENCE_OUT_DIR"] = tempfile.mkdtemp()
os.chdir(GEN)
import _console  # noqa: E402

ORIG = _console.load
CASES = [
    # (產生器, stem 片段, 原字串, 竄改後, 說明)
    ("ev_ai_spell_score", "01RtUp9", "stop 7: score EAX=00000018 spell=8 count=1 ptr_ok=True targets=[2] cast=(22,13)",
     "stop 7: score EAX=00000018 spell=8 count=1 ptr_ok=True targets=[2] cast=(22,14)", "評分施放點 vs sc_call 傾印"),
    ("ev_ai_spell_score", "01RtUp9", "stop 13: exit 0x1598a unit=11 best(score,x,y,spell)=(24, 22, 13, 8)",
     "stop 13: exit 0x1598a unit=11 best(score,x,y,spell)=(24, 22, 13, 12)", "best vs sc_best 傾印"),
    ("ev_ai_spell_score", "01X9fQ3", "stop 8: score EAX=0000000C", "stop 8: score EAX=00000008", "EAX vs 重算"),
    ("ev_ai_spell_score", "019bDp4", "iter 16: EIP=001B146A [0x53ec8]=3", "iter 16: EIP=001B146A [0x53ec8]=4", "R6 讀值 vs sc_ec8 傾印"),
    ("ev_ai_spell_score", "01AxqLh", "  units -> sc_units_r3_10_2.bin", "  units -> sc_units_r3_10_3.bin", "單位表檔名 vs 入口停點"),
    ("ev_ai_heal_score", "01MqTS9", "stop 10: score EAX=00000006", "stop 10: score EAX=00000003", "EAX vs 重算"),
    ("ev_ai_heal_score", "0117Yr6", "stop 9: score EAX=00000006 spell=13 count=1 ptr_ok=True targets=[14]",
     "stop 9: score EAX=00000006 spell=13 count=1 ptr_ok=True targets=[17]", "目標 vs sc_call 傾印"),
    ("ev_ai_heal_score", "01KRBWL", "stop 33: entry 0x1598a ret=0x14f1a", "stop 33: entry 0x1598a ret=0x1d91f", "pass 返回位址"),
    ("ev_ai_heal_score", "01KRBWL", "stop 40: exit 0x1598a unit=11 best(score,x,y,spell)=(3, 13, 16, 13)",
     "stop 40: exit 0x1598a unit=11 best(score,x,y,spell)=(3, 15, 18, 13)", "best vs sc_best 傾印"),
    ("ev_ai_item_score", "01519Rp", "stop 6: item-score EAX=00000008", "stop 6: item-score EAX=00000003", "EAX vs 重算"),
    ("ev_ai_item_score", "01519Rp", "stop 41: decide unit=18 bit40=64 P=8", "stop 41: decide unit=18 bit40=64 P=9", "P vs it_g 傾印"),
    ("ev_ai_item_score", "01519Rp", "stop 42: -> physical 0x1548e", "stop 42: -> item 0x15055", "執行函式 vs 規則"),
    ("ev_ai_item_score", "01519Rp", "cast=(23,1) slot=2\nstop 19", "cast=(23,2) slot=2\nstop 19", "施放點 vs it_c 傾印"),
    ("ev_ai_item_score", "01519Rp", "stop 41: decide unit=18 bit40=64", "stop 41: decide unit=18 bit40=0", "bit40 vs 規則"),
]
bad = 0
for gen, frag, a, b, why in CASES:
    def load(stem: str, frag=frag, a=a, b=b):
        meta, text = ORIG(stem)
        if frag in stem:
            assert text.count(a) == 1, (stem, a)
            text = text.replace(a, b)
        return meta, text
    _console.load = load
    try:
        runpy.run_path(str(GEN / f"{gen}.py"), run_name="__mut__")
        print("SURVIVED", gen, why)
        bad += 1
    except (AssertionError, KeyError, StopIteration) as e:
        print("killed  ", gen, why, type(e).__name__)
    finally:
        _console.load = ORIG
print("survivors", bad)
sys.exit(1 if bad else 0)
