"""ev_s159.py 的變異測試:每個變異改一個判準 / 解讀,必須讓 ev_s159.py 以 AssertionError 失敗(不能是其他例外)。
變異版與輸出都在暫存目錄,不碰已提交的證據檔;先跑未變異的對照(見 _mutrun.py)。"""
from __future__ import annotations

import sys

from _mutrun import run_mutants

MUTANTS = [
    # (A) PASS.DAT 的解析與位址換算
    ("COMP 記錄數 3", "assert len(RECS) == 2, RECS", "assert len(RECS) == 3, RECS"),
    ("全部差異門檻 2", "assert len(RECS) < 10 ", "assert len(RECS) < 2 "),
    ("逐字比對只比前段", "for m in _REC.finditer(PASS)) == PASS, PASS", "for m in _REC.finditer(PASS)) == PASS[:50], PASS"),
    ("第一處位址 0x118AB", "SITES = (0x118AA, 0x34233)", "SITES = (0x118AB, 0x34233)"),
    ("位移差 0x26013", "== [0x26014, 0x26014]", "== [0x26013, 0x26014]"),
    ("file1 預期 75", "== [0xEB, 0xEB]     # file1", "== [0x75, 0xEB]     # file1"),
    # (B) 重建的原版與語意
    ("原版只差 1 byte", "assert sum(a != b for a, b in zip(ORIG, _D)) == 2", "assert sum(a != b for a, b in zip(ORIG, _D)) == 1"),
    ("目標相同改不同", "assert jp[1] == \"jmp\" and jp[2] == jo[2]", "assert jp[1] == \"jmp\" and jp[2] != jo[2]"),
    ("0x118aa 原版預期 je", "\"0x118a3 cmp byte ptr [0x3a44], 0\", \"0x118aa jne 0x118b3\"",
     "\"0x118a3 cmp byte ptr [0x3a44], 0\", \"0x118aa je 0x118b3\""),
    ("0x34233 原版預期 jne", "\"0x34231 cmp eax, ebx\", \"0x34233 je 0x3421e\"", "\"0x34231 cmp eax, ebx\", \"0x34233 jne 0x3421e\""),
    ("防拷呼叫目標 + 1", "f\"0x118ac call {COPYPROT:#x}\"", "f\"0x118ac call {COPYPROT + 1:#x}\""),
    ("s137 兩值對調", "== {0x118AA: 0x75, 0x34233: 0x74}, S137", "== {0x118AA: 0x74, 0x34233: 0x75}, S137"),
    # (C) 快照、時間序、掃描
    ("PLAY.BAT 只有 LF", "== b\"fd2\\r\\n\"", "== b\"fd2\\n\""),
    ("FD2_USB 時間改 07-14", "(MD5, \"1995-07-07 14:52:16\")", "(MD5, \"1995-07-14 22:16:52\")"),
    ("APK 的 FD2.EXE 當參考版", "(APK_MD5, \"2004-10-23 01:49:48\")", "(MD5, \"2004-10-23 01:49:48\")"),
    ("原版在磁碟上", "assert ORIG_MD5 not in {", "assert ORIG_MD5 in {"),
    ("只在 APK 的檔少 PASS.DAT", "== [\"FD2_old.EXE\", \"PASS.DAT\", \"PLAY.BAT\", \"SETUP.BAT\"], ONLY_APK",
     "== [\"FD2_old.EXE\", \"PLAY.BAT\", \"SETUP.BAT\"], ONLY_APK"),
    ("修補檔晚於 COMP 紀錄", "assert T[\"FD2_old.EXE\"] < T[\"PASS.DAT\"]", "assert T[\"FD2_old.EXE\"] > T[\"PASS.DAT\"]"),
    ("COMP 紀錄日 07-14", "== \"1995-07-15\"", "== \"1995-07-14\""),
    ("排除名單加 FD2.SAV", "== [\"DIG.INI\", \"MDI.INI\"]", "== [\"DIG.INI\", \"FD2.SAV\", \"MDI.INI\"]"),
    ("共同檔數 43", "assert len(COMMON) == 42", "assert len(COMMON) == 43"),
    ("EXE 之後沒有資料檔", "assert after == [\"FIGANI.DAT\"]", "assert after == []"),
    ("資料檔最早 06-07", "== [\"1995-06-06 09:27:28\", \"1995-07-07 17:20:04\"]", "== [\"1995-06-07 09:27:28\", \"1995-07-07 17:20:04\"]"),
    ("掃描筆數 6", "and len(HITS) == 5, HITS", "and len(HITS) == 6, HITS"),
    # (D) 第 5 項第 5 次的截圖判讀
    ("Up 那格之後是草地", "assert CELL_UP[\"after\"][\"grey\"] > 20 * CELL_UP[\"after\"][\"green\"]",
     "assert CELL_UP[\"after\"][\"green\"] > 20 * CELL_UP[\"after\"][\"grey\"]"),
    ("Up 那格原本是單位", "assert CELL_UP[\"before\"][\"green\"] > 2 * CELL_UP[\"before\"][\"grey\"]",
     "assert CELL_UP[\"before\"][\"grey\"] > 2 * CELL_UP[\"before\"][\"green\"]"),
    ("索爾還在原位", "and CELL_SOL[\"after\"][\"blue\"] == 0", "and CELL_SOL[\"after\"][\"blue\"] > 0"),
    ("捲動一致門檻 0.95", "assert SCROLL_SAME > 0.9 and", "assert SCROLL_SAME > 0.95 and"),
    ("對照門檻 0.3", "and max(SCROLL_CTRL) < 0.6", "and max(SCROLL_CTRL) < 0.3"),
    ("一致度改最少見顏色", "sum(c.most_common(1)[0][1] for c in m.values())", "sum(c.most_common()[-1][1] for c in m.values())"),
]

if __name__ == "__main__":
    sys.exit(run_mutants("ev_s159", MUTANTS))
