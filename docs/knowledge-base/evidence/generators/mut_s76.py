"""ev_s76.py 的變異測試:每個變異改一個判準 / 預測,必須讓 ev_s76.py 以 AssertionError 失敗(不能是其他例外)。
變異版與輸出都在暫存目錄,不碰已提交的證據檔;先跑未變異的對照(見 _mutrun.py)。"""
from __future__ import annotations

import sys

from _mutrun import run_mutants

MUTANTS = [
    ("中斷閘先查 present 再查權限", "assert i_priv < i_np_in < i_np_same < i_bad", "assert i_np_in < i_priv"),
    ("例外是 #NP", 'assert predicted == "GP(13)", (v, o)', 'assert predicted == "NP(11)", (v, o)'),
    ("預測函式:DPL 門檻寫錯", 'predicted = "GP(13)" if o["dpl"] > cpl', 'predicted = "GP(13)" if o["dpl"] > 3'),
    ("CPL 是 3", "cpl = 0x0170 & 3", "cpl = 3"),
    ("關機碼是 0x0A(reset vector)", '"CMOS Shutdown byte 0x09 says to do INT 15 block move reset 0823:09db. "',
     '"CMOS Shutdown byte 0x0a says to jump to reset vector 0823:09db. "'),
    ("重置框架沒有 FLAGS", "frame_bytes = 2 * len(pops) + 6", "frame_bytes = 2 * len(pops) + 4"),
    ("錯誤訊息只印一次", 'assert t == (MSG + "|~") * 2, (v, t)', 'assert t == (MSG + "|~") * 1, (v, t)'),
    ("0C5C 段對到別的檔案位移", "SEG = 0x1DD0", "SEG = 0x1DC0"),
    ("XMS 清理先釋放再解鎖", "b40dff1eec0ab40aff1eec0a", "b40aff1eec0ab40dff1eec0a"),
    ("重置後沒有 jmp 0018:0334", "between == [e2 - 1]", "between == []"),
    ("不存在的閘預測成 #GP", 'pred = "NP" if not d18["p"] else "gate"', 'pred = "GP" if not d18["p"] else "gate"'),
    ("g1(0x24)是 #NP", '"g1": ("0070", "0x24", ["CPU_Exception: Exception 13', '"g1": ("0070", "0x24", ["CPU_Exception: Exception 11'),
    ("g3 是 #GP", '"g3": ("0018", "0x54", ["CPU_Exception: Exception 11', '"g3": ("0018", "0x54", ["CPU_Exception: Exception 13'),
    ("g3 沒有 E_Exit", '               "E_Exit: JMP Illegal descriptor type 14"),', '               None),'),
    ("g4 也印出 v11 那一句", '"g4": ("0018", "0x24", [], "E_Exit: Illegal descriptor type 1F for int D")',
     '"g4": ("0018", "0x24", [], "E_Exit: JMP Illegal descriptor type 14")'),
    ("關機碼不是 DOS/4GW 自己寫的 9", '"ds:[000010EE]=0109"', '"ds:[000010EE]=0105"'),
    ("g3 最後一條是 IRQ 往下切的 jmp 0018:092C", 'h3[-1].startswith("0C5C:0000032D  jmp  0018:0334")',
     'h3[-1].startswith("0070:00000477  jmp  0018:092C")'),
    ("g3 與 v21 的重置後路徑不同", "assert p21[: len(p3)] == p3 and", "assert p21[: len(p3)] != p3 and"),
    ("E_Exit 只在實際模式也會發生", 'assert "if (!cpu.pmode || (reg_flags & FLAG_VM)) {" in jmp',
     'assert "if (!cpu.pmode || (reg_flags & FLAG_VM)) {" not in jmp'),
]

if __name__ == "__main__":
    sys.exit(run_mutants("ev_s76", MUTANTS))
