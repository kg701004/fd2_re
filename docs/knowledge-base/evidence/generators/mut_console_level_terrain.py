"""一次性變異測試:新加的交叉檢查在對應錯誤時必須失敗(AssertionError),未變異時必須通過。"""
import os
import sys
import tempfile
import traceback
from pathlib import Path

GEN = Path(__file__).resolve().parent
os.environ["FD2_EVIDENCE_OUT_DIR"] = tempfile.mkdtemp()
sys.path.insert(0, str(GEN))

MUTS = [
    ("ev_terrain_modifier.py", None, None, None),
    ("ev_terrain_modifier.py", "        unit_console[tag] = ",
     "        unit_console[{'T2': 'T3', 'T3': 'T2'}.get(tag, tag)] = ", "雙方欄位"),
    ("ev_terrain_modifier.py", "        unit_console[tag] = ",
     "        unit_console[{'T6': 'T5', 'T5': 'T6'}.get(tag, tag)] = ", "雙方欄位"),
    ("ev_terrain_types_3_5.py", None, None, None),
    ("ev_terrain_types_3_5.py", "        seg_info[tag] = ", "        seg_info[{'u3': 'u4', 'u4': 'u3'}.get(tag, tag)] = ", "雙方欄位"),
    ("ev_terrain_types_3_5.py", "        seg_info[tag] = (head_types, units)\n",
     "        pass\n", "首段(失敗)"),
    ("ev_level_up.py", '    prints.setdefault(tag, [])', '    prints.setdefault({"LA": "LB2", "LB2": "LA"}.get(tag, tag), [])', "攻方欄位 LA/LB2"),
    ("ev_level_up.py", None, None, None),
    ("ev_level_up.py", 'ALIAS = {"LB": "LA"}', "ALIAS = {}", "屬性指標"),
    ("ev_level_up.py", '    prints.setdefault(tag, [])', '    prints.setdefault({"LC": "LE", "LE": "LC"}.get(tag, tag), [])', "攻方欄位"),
    ("ev_level_up.py", "        if s[\"EIP\"] == 0x1CBAB9:", "        if s[\"EIP\"] == 0x1CBA9F:", "pending"),
    # 模擬「LB 那段其實是另一次升級」的兩種輸出:成長停點從 unit+0x37 開始、或含攻擊停點
    ("ev_level_up.py", "    st = GAIN_LINE.findall(text)\n",
     '    st = GAIN_LINE.findall(text.replace("(unit+0x46)", "(unit+0x37)"))\n', "併入段從頭開始"),
    ("ev_level_up.py", "for t_, before, text in alias_out:",
     'for t_, before, text in [(a, b, c + "\\nstop 1: EIP=001CBAB9 EAX=00000015") for a, b, c in alias_out]:', "併入段含攻擊"),
]
bad = 0
for fn, old, new, label in MUTS:
    src = (GEN / fn).read_text(encoding="utf-8")
    if old is not None:
        assert src.count(old) == 1, (fn, old)
        src = src.replace(old, new)
        if label == "首段(失敗)":
            src = src.replace("        if not st:  #", "        seg_info.setdefault(tag, (head_types, units))\n        if not st:  #")
    ns = {"__file__": str(GEN / fn), "__name__": "__mut__"}
    try:
        exec(compile(src, fn, "exec"), ns)
        res = "PASS-RUN"
    except AssertionError:
        tb = traceback.extract_tb(sys.exc_info()[2])[-1]
        res = f"AssertionError at line {tb.lineno}: {tb.line}"
    except Exception as e:  # noqa: BLE001
        res = f"{type(e).__name__}: {e}"
    ok = (old is None and res == "PASS-RUN") or (old is not None and res.startswith("AssertionError"))
    bad += not ok
    print("OK " if ok else "BAD", fn, label or "unmutated", "->", res[:160])
print("bad =", bad)
