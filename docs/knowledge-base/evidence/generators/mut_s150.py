"""ev_s150.py 的變異測試:每個變異改一個判準 / 預測,或在 x86_pal_emu.py 放一個直譯器的錯,
必須讓 ev_s150.py 以 AssertionError 失敗(不能是其他例外)。變異版與輸出都在暫存目錄,不碰已提交的證據檔。"""
from __future__ import annotations

import sys

from _mutrun import run_mutants

EMU = "x86_pal_emu.py"
MUTANTS = [
    ("0x2df01 預期寫到 255", "if sorted(d) != list(range(255)):", "if sorted(d) != list(range(256)):"),
    ("0x11df2 飽和前多加 1", "min(int(v) + add, SAT)", "min(int(v) + add + 1, SAT)"),
    ("0x11d40 下限是 1", "max(int(v) - s, 0)", "max(int(v) - s, 1)"),
    ("對照不改向下取整", "check(REAL, floor=True, stop_first=True)", "check(REAL, floor=False, stop_first=True)"),
    ("注入改錯位址", "(0x2DF18, b\"\\x28\", b\"\\x29\")", "(0x2DF19, b\"\\x28\", b\"\\x29\")"),
    ("jl→jle 預期成值不同", '"0x2dfbd jl→jle": ("A", "index_set")', '"0x2dfbd jl→jle": ("A", "value")'),
    ("除數注入預期在 B", '"除數 0x28→0x29": ("A", "value")', '"除數 0x28→0x29": ("B", "value")'),
    ("紅閃光 t 往上數", "for t in range(T0, -1, -1)]", "for t in range(0, T0 + 1)]"),
    ("白 → 標題少了 0x11df2", "[(SUB, [0, 0xFF, 0]), (ADD, [0, 0xFF, W_ADD])]", "[(SUB, [0, 0xFF, 0]), (SUB, [0, 0xFF, 0])]"),
    # 直譯器的錯
    ("idiv 向下取整", "q = abs(num) // abs(d) * (1 if (num < 0) == (d < 0) else -1)", "q = num // d", EMU),
    ("jl 當成 jle", '"jl": f["sf"] != f["of"]', '"jl": f["zf"] == 1 or f["sf"] != f["of"]', EMU),
    ("sar 當成邏輯右移", "res = (s32(self.get(ops[0])) >> self.get(ops[1])) & M32",
     "res = (self.get(ops[0]) >> self.get(ops[1])) & M32", EMU),
    ("idiv 的 edx 當成有號再左移", "num = self.r[\"edx\"] << 32 | self.r[\"eax\"]",
     "num = s32(self.r[\"edx\"]) << 32 | self.r[\"eax\"]", EMU),
]

if __name__ == "__main__":
    sys.exit(run_mutants("ev_s150", MUTANTS))
