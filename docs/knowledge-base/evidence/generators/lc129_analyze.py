"""續一百二十九:指令表 0x51d01 第 0..9 格 —— 哪幾格在原版實機跑過、沒跑過的幾格與跑過的差在哪(STATIC ANALYSIS + 既有軌跡)。

只讀 FD2.EXE(md5 33464c81e6a364fd0660141139aa8e6e)、docs/data/live_exec_addresses.json 與兩份既有 evidence;不執行遊戲。
用法:lc129_analyze.py [--exe PATH] [--live PATH] [--json OUT]
原暫存 an129.py,續一百三十四移進倉庫;工具與 live_exec_addresses.json 取續一百二十九提交時的 git blob(_blobtools)。
每項印 PASS / FAIL;最後一行 "ALL PASS" 或 "FAIL n"。
"""
from __future__ import annotations

import argparse
import json
import sys
from pathlib import Path

import capstone

sys.path.insert(0, str(Path(__file__).resolve().parent))
from _evpaths import GAME, ROOT as REPO  # noqa: E402
sys.path.insert(0, str(REPO / "tools"))
from disasm_le import load_code  # noqa: E402
from le_xref import parse_le  # noqa: E402
from _blobtools import EDT, LIVE_JSON  # noqa: E402
CODE_BASE, read_table = EDT.CODE_BASE, EDT.read_table

CMD_BASE = 0x51D01
CHK = 0x3702F                     # __CHK
BODY_A_JOIN, BODY_B_JOIN = 0x2121A, 0x213AA   # 第 0 格 / 第 4 格裡「push [esp+0x10]」那一條(其他格跳進來的點)
BODY_A, BODY_B = 0x21227, 0x213B7            # command_generic_damage / command_generic_damage_type21
AI_DISPATCH = 0x1541F


def insns(code: bytes, addr: int, n: int) -> list[tuple[str, str, list[int]]]:
    md = capstone.Cs(capstone.CS_ARCH_X86, capstone.CS_MODE_32)
    out = []
    off = addr - CODE_BASE
    for i in md.disasm(code[off:off + 64], addr):
        out.append((i.mnemonic, i.op_str, list(i.bytes)))
        if len(out) == n:
            break
    return out


def stub_shape(ins: list[tuple[str, str, list[int]]]) -> tuple | None:
    """跳板的形狀:(push 0x14, call __CHK, push [esp+0xc] x2, push 立即值 k, jmp T) -> (k, T);不符回 None。"""
    if len(ins) < 6:
        return None
    exp = [("push", "0x14"), ("call", hex(CHK)), ("push", "dword ptr [esp + 0xc]"), ("push", "dword ptr [esp + 0xc]")]
    if [(m, o) for m, o, _ in ins[:4]] != exp or ins[4][0] != "push" or ins[5][0] != "jmp":
        return None
    try:
        return int(ins[4][1], 16), int(ins[5][1], 16)
    except ValueError:
        return None


def main() -> int:
    ap = argparse.ArgumentParser()
    ap.add_argument("--exe", default=str(GAME / "FD2.EXE"))
    ap.add_argument("--live", default=None)
    ap.add_argument("--json")
    a = ap.parse_args()
    data = Path(a.exe).read_bytes()
    meta = parse_le(data)
    code, cbase = load_code(data, meta)
    assert cbase == CODE_BASE, hex(cbase)
    tbl = read_table(data, meta, base=CMD_BASE, first=0, count=10)
    live = set((json.loads(Path(a.live).read_text(encoding="utf-8")) if a.live else LIVE_JSON)["addresses"])
    ev52 = json.loads((REPO / "docs/knowledge-base/evidence/ai_spell_path_20260929.json").read_text(encoding="utf-8"))
    ev55 = json.loads((REPO / "docs/knowledge-base/evidence/spell9_path_20260930.json").read_text(encoding="utf-8"))
    res: list[tuple[str, bool, str]] = []

    def chk(name: str, ok: bool, detail: str) -> None:
        res.append((name, bool(ok), detail))
        print("PASS" if ok else "FAIL", name, "|", detail)

    shapes = {i: stub_shape(insns(code, tbl[i], 6)) for i in range(10)}
    # 1. 第 1、2、3、8 格:push i 後跳進第 0 格的 0x2121a;第 5、6、7 格跳進第 4 格的 0x213aa
    for grp, join in (((1, 2, 3, 8), BODY_A_JOIN), ((5, 6, 7), BODY_B_JOIN)):
        got = {i: shapes[i] for i in grp}
        # 組員也要等於「push 自己格號再跳進這個 join」的全部格(續一百三十五 sweep_literals:寫成 (2, 2, 3, 8) 也照樣逐格通過)
        members = {i for i, s in shapes.items() if s == (i, join)}
        chk(f"stub_{''.join(map(str, grp))}", all(got[i] == (i, join) for i in grp) and set(grp) == members,
            ", ".join(f"{i}:{hex(tbl[i])}->{got[i] and (got[i][0], hex(got[i][1]))}" for i in grp))
    # 2. 第 0 / 4 格:前 5 條同形狀(push 0 / 4),第 6 條就是被跳進來的那一條,之後 call 本體
    for i, join, body in ((0, BODY_A_JOIN, BODY_A), (4, BODY_B_JOIN, BODY_B)):
        ins = insns(code, tbl[i], 7)
        addrs = []
        x = tbl[i]
        for _, _, b in ins:
            addrs.append(x)
            x += len(b)
        # capstone 把 < 10 的立即值印成十進位("0"、"4"),所以第 5 條比數值
        ok = ([(m, o) for m, o, _ in ins[:4]] == [("push", "0x14"), ("call", hex(CHK)), ("push", "dword ptr [esp + 0xc]"),
                                                     ("push", "dword ptr [esp + 0xc]")]
              and ins[4][0] == "push" and int(ins[4][1], 16) == i
              and addrs[5] == join and ins[6][0] == "call" and int(ins[6][1], 16) == body)
        chk(f"head_{i}", ok, f"{hex(tbl[i])}: 第 6 條 {hex(addrs[5])} {ins[5][0]} {ins[5][1]};第 7 條 {ins[6][0]} {ins[6][1]}")
    # 3. 對照:第 9 格(咒殺,自有本體)不是跳板
    chk("control_9_not_stub", shapes[9] is None, f"{hex(tbl[9])} shape={shapes[9]}")
    # 4. 軌跡:跑過的入口 = 0、3、4、6、9;兩個共用本體與 AI dispatch 都跑過
    ran = [i for i in range(10) if hex(tbl[i]) in live]
    chk("live_entries", ran == [0, 3, 4, 6, 9], f"跑過的格 {ran}")
    chk("live_bodies", all(hex(x) in live for x in (BODY_A_JOIN, BODY_B_JOIN, BODY_A, BODY_B, AI_DISPATCH)),
        "0x2121a、0x213aa、0x21227、0x213b7、0x1541f 都在軌跡裡")
    # 5. 既有 evidence:續五十二 C1 旗標 1、法術 8 -> spell_damage_resolve 返回 0x212a4(本體 A 內);續五十五 A2 旗標 1、法術 9 -> 0x214ad
    c1 = ev52["rounds"]["C1"]
    sdr = [s for s in c1["breakpoint_stops"] if s.get("function") == "spell_damage_resolve"]
    chk("ev52_C1_spell8", c1["flag_53af9"] == 1 and sdr and sdr[0]["return_static"] == "0x212a4" and sdr[0]["arg2"] == 8
        and BODY_A < 0x212A4 < 0x212B9, f"flag {c1['flag_53af9']} stop {sdr}")
    s55 = json.dumps(ev55, ensure_ascii=False)
    chk("ev55_A2_spell9", '"A2"' in s55 and "0x15426" in s55, "spell9_path_20260930.json 有 A2 與返回 0x15426")
    # 6. 沒跑過的 5 格(1、2、5、7、8)的入口確實不在軌跡裡(8 由續五十二的返回位址間接證實)
    chk("not_ran", all(hex(tbl[i]) not in live for i in (1, 2, 5, 7, 8)), "1、2、5、7、8 的入口不在軌跡")
    bad = sum(1 for _, ok, _ in res if not ok)
    print("ALL PASS" if bad == 0 else f"FAIL {bad}")
    if a.json:
        Path(a.json).write_text(json.dumps({"table": {i: hex(v) for i, v in tbl.items()},
                                            "shapes": {i: (s and [s[0], hex(s[1])]) for i, s in shapes.items()},
                                            "ran": ran, "checks": res}, ensure_ascii=False, indent=1),
                                encoding="utf-8", newline="\n")
    return 1 if bad else 0


if __name__ == "__main__":
    sys.stdout.reconfigure(encoding="utf-8")
    sys.exit(main())
