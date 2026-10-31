"""`cmd_episodes` 的 `lf = "-" if key[0] is None ...` int 0->1(第一個 key[0] 改 key[1])是否等價(續一百七十七 --exhaustive)。

`group_episodes` 只收完整的 episode;`episodes` 只在已看過遊戲 run 時才標完整(left_from = 那一段的 e1),
回到遊戲時才填 back_to —— 所以分組鍵兩格都不會是 None,`is None` 判斷看哪一格結果都一樣(都是 False)。
這裡在記憶體裡套突變(不碰檔案),對 .wsl_build 下 lc17* 的實際紀錄跑 `cmd_episodes`,比原版輸出;
對照突變(f-string 裡的 key[0] 改 key[1],印成回來的 EIP)必須在同一批紀錄上看得出差異,否則這份比對沒有鑑別力。
另外直接數完整 episode 的 left_from / back_to 有沒有 None。

紀錄在 .wsl_build/(不提交)。用法:python equiv_episodes.py
"""
from __future__ import annotations

import contextlib
import io
import sys
import types
from pathlib import Path

REPO = Path(__file__).resolve().parents[5]
SRC = (REPO / "tools" / "calllog_segments.py").read_text(encoding="utf-8")
LINE = '        lf = "-" if key[0] is None else f"{key[0]:08x}"\n'
assert SRC.count(LINE) == 1, "突變點那一行變了,這份探針要跟著改"
VARIANTS = {"orig": SRC,
            "mutant": SRC.replace(LINE, LINE.replace("key[0] is None", "key[1] is None")),
            "control": SRC.replace(LINE, LINE.replace('f"{key[0]:08x}"', 'f"{key[1]:08x}"'))}


def load(name: str, src: str) -> types.ModuleType:
    """把一份原始碼載成獨立模組(dataclass 要從 sys.modules 找得到所在模組)。"""
    m = types.ModuleType(name)
    m.__dict__["__file__"] = str(REPO / "tools" / "calllog_segments.py")
    sys.modules[name] = m
    exec(compile(src, name, "exec"), m.__dict__)
    return m


def main() -> int:
    mods = {k: load(f"cls_probe_{k}", v) for k, v in VARIANTS.items()}
    logs = sorted((REPO / ".wsl_build").glob("lc17*_live/*_CALLLOG.TXT"))
    diff_mut = diff_ctl = none_keys = eps_total = 0
    for p in logs:
        lg = mods["orig"]._read(str(p))
        comp = [e for e in mods["orig"].episodes(lg) if e.complete]
        eps_total += len(comp)
        none_keys += sum(e.left_from is None or e.back_to is None for e in comp)
        outs = {}
        for k, m in mods.items():
            b = io.StringIO()
            with contextlib.redirect_stdout(b):
                m.cmd_episodes(lg, 1)
            outs[k] = b.getvalue()
        diff_mut += outs["mutant"] != outs["orig"]
        diff_ctl += outs["control"] != outs["orig"]
        print(p.name, "complete eps", len(comp), "mutant==orig", outs["mutant"] == outs["orig"],
              "control==orig", outs["control"] == outs["orig"])
    print("logs", len(logs), "complete eps", eps_total, "None keys", none_keys,
          "mutant differs", diff_mut, "control differs", diff_ctl)
    ok = logs and none_keys == 0 and diff_mut == 0 and diff_ctl == len(logs)
    print("EQUIVALENT" if ok else "NOT SHOWN")
    return 0 if ok else 1


if __name__ == "__main__":
    sys.exit(main())
