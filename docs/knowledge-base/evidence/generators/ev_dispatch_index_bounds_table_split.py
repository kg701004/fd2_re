"""續一百二十八證據:evidence/dispatch_index_bounds_table_split_20261015.json(全部靜態,沒有執行遊戲)。

0x1541f(AI)與 0x1d479(玩家)兩處 dispatch 的索引上限,與 0x51d01 起 88 格的分段。原本由暫存的 mk_evidence128.py
+ an128.py + mut_an128.py + mut128.py 產生(續一百二十八);續一百三十四移進倉庫:分析是 lc128_analyze.py,
映像突變是 lc128_mut_image.py、工具突變是 lc128_mut_tool.py(都以子行程重跑,輸出原樣寫進證據)。
verify_event_dispatch_table.py 與 docs/data/event_dispatch_table_58_89.json 都取續一百二十八提交(43027554)時的
git blob(_blobtools.py),之後改了工具或資料,這份證據仍照當時的版本重算。
"""
from __future__ import annotations

import contextlib
import hashlib
import io
import json
import subprocess
import sys

from _evpaths import GAME, GEN_DIR, git_blob, out_path, require_inputs  # noqa: E402
require_inputs(__file__)
import lc128_analyze as an128  # noqa: E402
from _blobtools import EDT  # noqa: E402

OUT = out_path("dispatch_index_bounds_table_split_20261015.json")
EXE_MD5 = "33464c81e6a364fd0660141139aa8e6e"
assert hashlib.md5((GAME / "FD2.EXE").read_bytes()).hexdigest() == EXE_MD5
TABLES_BLOB = "d000f9b963dfd5ce186341a638e03ce50a6c4369"     # docs/data/event_dispatch_table_58_89.json @ 43027554


def run(script: str) -> subprocess.CompletedProcess:
    return subprocess.run([sys.executable, str(GEN_DIR / script)], capture_output=True, text=True, encoding="utf-8", cwd=GEN_DIR)


_buf = io.StringIO()
with contextlib.redirect_stdout(_buf):
    _rc = an128.main(["an128.py"])
assert _rc == 0 and "PASS" in _buf.getvalue(), _buf.getvalue()[-1500:]
res = list(an128.results)
m1 = run("lc128_mut_image.py")
assert m1.returncode == 0 and "不符預期 0" in m1.stdout and "Traceback (most recent" not in m1.stdout + m1.stderr, m1.stdout + m1.stderr
m2 = run("lc128_mut_tool.py")
assert m2.returncode == 0 and "漏掉 0" in m2.stdout and "Traceback (most recent" not in m2.stdout + m2.stderr, m2.stdout + m2.stderr
# 工具 selftest 的 (11)(12):當時是以子行程執行 tools/verify_event_dispatch_table.py --selftest;這裡在行程內執行同一版原始碼
_st = io.StringIO()
with contextlib.redirect_stdout(_st):
    _st_rc = EDT.selftest()
lines = _st.getvalue().splitlines()
assert _st_rc == 0 and any(x.startswith("(11)") for x in lines) and any(x.startswith("(12)") for x in lines), lines[-20:]
i11 = next(i for i, x in enumerate(lines) if x.startswith("(11)"))
st_block = lines[i11:i11 + 6]
# 這一段 = (11)、(12) 兩項各「標題、PASS、空行」;下一行是別的項目或輸出結束
assert [x[:4] for x in st_block[::3]] == ["(11)", "(12)"] and st_block[2::3] == ["", ""] \
    and all(x.strip().startswith("PASS") for x in st_block[1::3]) \
    and lines[i11 + len(st_block)].startswith(("(", "--selftest passed")), st_block
tables = json.loads(git_blob(TABLES_BLOB, "docs/data/event_dispatch_table_58_89.json"))["tables"]
out = {
    "date": "2026-10-15", "exe_md5": EXE_MD5,
    "method": "靜態:FD2.EXE 的位元組與 LE fixup 表(STATIC ANALYSIS);沒有執行遊戲。",
    "dispatch_split": {k: tables[k]["dispatch"] for k in ("event", "command")},
    "dispatch_truth_path": "capstone 線性反組譯整個 obj1(disasm_le.py range 0x10000 0x50000),"
                           "搜 call dword ptr [eax*4 + 表內位址];與工具的 fixup + 位元組樣式路徑一致。",
    "index_bounds": {
        "player_0x1d479": "索引 = 已選法術;9 <= x <= 0x1b 且 x != 0x18 才進表,其餘走 spell_cast_scene(0x1d414..0x1d421)。",
        "ai_0x1541f": "索引 = [0x53c2f],唯一寫入端 0x15b12(ai_spell_candidate_select 分數大於 / 等於目前最高分時);"
                      "ai_spell_execute 在 0x1534f 要求 [0x53c23] >= 6;ai_spell_target_score 只對 0..0x16、0x1a、0x1b 可能回非 0。",
        "max_index": 27, "command_table_len": 28,
        "unreached_by_both": [24],
        "entry_24_note": "第 24 格與第 16 格同為 0x22153(command_handler_16)。",
    },
    "analysis": {"script": "an128.py(暫存)", "items": res},
    "mutation_image": {"script": "mut_an128.py(暫存)", "stdout": m1.stdout.strip().splitlines()},
    "mutation_tool": {"script": "mut128.py(暫存)", "stdout": m2.stdout.strip().splitlines()},
    "tool_selftest_11_12": st_block,
}

# 結論釘住:9 項預測符合、1 個對照判為不符合;index_bounds 的手寫數字與分析一致;突變全部符合預期
assert [r["ok"] for r in res if not r["control"]] == [True] * 9 and [r["ok"] for r in res if r["control"]] == [False], res
by = {r["name"]: r["detail"] for r in res}
assert by["兩處都到不了的格只有 24(0x18)"] == str(out["index_bounds"]["unreached_by_both"])
assert by["兩處都不會讀到戰前章節表(索引 < 指令表長度)"] == f"最大 {out['index_bounds']['max_index']};指令表 {out['index_bounds']['command_table_len']} 格"
assert (out["mutation_image"]["stdout"][-1], out["mutation_tool"]["stdout"][-1]) == ("突變 7 個,符合預期 7,不符預期 0", "突變 13 個,抓到 13,漏掉 0")
assert [(d["base"], d["count"]) for d in out["dispatch_split"]["command"]] == [("0x51d01", 28), ("0x51d71", 30), ("0x51de9", 30)], out["dispatch_split"]


def write() -> None:
    js = (json.dumps(out, ensure_ascii=False, indent=1) + "\n").encode("utf-8")
    assert b"\r" not in js
    OUT.write_bytes(js)
    print("ok", OUT.name, len(js))


if __name__ == "__main__":
    write()
