"""續一百二十八(靜態):`0x1541f`(AI)與 `0x1d479`(玩家)兩處 `call [eax*4+0x51d01]` 的索引上限。

從 FD2.EXE 的位元組讀出每個判斷的立即值,推出兩處能送進表的索引集合,
再對照指令表長度(verify_event_dispatch_table 由 dispatch 基底切出的第一段)。
用法:lc128_analyze.py [突變名]   突變只改記憶體裡的映像副本,用來證明檢查會失敗。
原暫存 an128.py,續一百三十四移進倉庫;verify_event_dispatch_table 由 _blobtools 從續一百二十八提交時的 git blob 載入。
"""
from __future__ import annotations

import sys
from pathlib import Path

sys.path.insert(0, str(Path(__file__).resolve().parent))
from _evpaths import GAME, ROOT as REPO  # noqa: E402
sys.path.insert(0, str(REPO / "tools"))
from le_xref import parse_le  # noqa: E402
from disasm_le import build_fixups, lin2file  # noqa: E402
from _blobtools import EDT  # noqa: E402

EXE = GAME / "FD2.EXE"
N_SPELLS = 40          # unit_list_bits_1a:+0x1a 起 5 bytes 共 40 個 bit(已學法術)

# 突變:(檔案內的 linear 位址, 新的位元組)
MUTANTS = {
    "player_upper_1c": (0x1D420, b"\x1c"),     # cmp eax, 0x1b -> 0x1c
    "player_lower_0": (0x1D416, b"\x00"),      # cmp eax, 9 -> 0(不影響上限:應仍符合)
    "player_skip_18_off": (0x1D41C, b"\xeb"),  # je -> jmp(0x18 以外也走場景;上限仍 27,應仍符合)
    "ai_guard_0": (0x15355, b"\x00"),          # cmp [0x53c23], 6 -> 0
    "score_last_1c": (0x15D82, b"\x1c"),       # cmp spell, 0x1b -> 0x1c
    "score_16_to_1d": (0x15D34, b"\x1d"),      # cmp spell, 0x16 -> 0x1d
    "writer_extra": (0x14FC9, b"\xa3"),        # 0x14fc8 那個讀 [0x53c2f] 的 disp 前一個 byte 改成 mov [moffs], eax 的 opcode
}
EXPECT_STILL_PASS = {"player_lower_0", "player_skip_18_off"}

results: list[dict] = []


def check(name: str, ok: bool, detail: str, control: bool = False) -> None:
    results.append({"name": name, "ok": ok, "detail": detail, "control": control})


def main(argv: list[str]) -> int:
    data = bytearray(EXE.read_bytes())
    meta = parse_le(bytes(data))
    mut = argv[1] if len(argv) > 1 else None
    if mut:
        lin, b = MUTANTS[mut]
        o = lin2file(meta, lin)
        data[o:o + len(b)] = b
    data_b = bytes(data)

    def at(lin: int, n: int) -> bytes:
        o = lin2file(meta, lin)
        return data_b[o:o + n]

    # 指令表長度:由 dispatch 基底切段(工具的同一個函式)
    segs = EDT.split_by_dispatch(0x51D01, 88, EDT.dispatch_sites(data_b, meta, 0x51D01, 88))
    cmd_len = segs[0]["count"] if segs[0]["base"] == "0x51d01" else None
    check("指令表(第一段)28 格", cmd_len == 28, f"{[(s['base'], s['count']) for s in segs]}")

    # 玩家 0x1d407..0x1d421:cmp eax,lo / jl 場景;cmp eax,x / je 場景;cmp eax,hi / jle 進表
    p = at(0x1D414, 0x0F)
    shape = (p[0:2] == b"\x83\xf8" and p[3] == 0x7C and p[5:7] == b"\x83\xf8" and p[8] in (0x74, 0xEB)
             and p[10:12] == b"\x83\xf8" and p[13] == 0x7E)
    lo, x, hi = p[2], p[7], p[12]
    skip_all = p[8] == 0xEB                     # je 變成 jmp:lo 以上全部走場景
    player = set() if skip_all else {i for i in range(N_SPELLS) if lo <= i <= hi and i != x}
    check("玩家路徑的指令形狀", shape, p.hex())
    check("玩家可進表的索引 <= 27", shape and (max(player, default=-1) <= 27),
          f"lo={lo:#x} 排除={x:#x} hi={hi:#x} -> {sorted(player)}")

    # AI:ai_spell_execute 入口後 cmp dword [0x53c23], 6 / jl 返回
    g = at(0x1534F, 13)
    fx = build_fixups(data_b, meta, objects={1})
    guard_shape = g[0:2] == b"\x83\x3d" and fx.get(0x15351) == 0x53C23 and g[7:9] == b"\x0f\x8c"
    thr = g[6]
    check("AI 的分數門檻形狀", guard_shape, g.hex())

    # ai_spell_target_score:各分支的 cmp spell, imm;最後兩個是 0x1a、0x1b,其餘回 0
    imms = {a: at(a + 4, 1)[0] for a in (0x15BA0, 0x15C21, 0x15CB0, 0x15CF9, 0x15D30, 0x15D71, 0x15D7E)}
    shapes = all(at(a, 4) == b"\x83\x7c\x24\x24" for a in imms)
    tail_zero = at(0x15D83, 2) == b"\x75\x13" and at(0x15B8C, 2) == b"\x31\xff"   # jne -> mov eax, edi;edi = 0
    scored = set(range(0, imms[0x15D30] + 1)) | {imms[0x15D71], imms[0x15D7E]}
    ai = set(range(N_SPELLS)) if thr <= 0 else scored   # 門檻 <= 0 時 0 分的法術也可能被選
    check("AI 評分分支的形狀", shapes and tail_zero, {hex(k): hex(v) for k, v in imms.items()}.__repr__())

    # [0x53c2f] 只有 0x15b12 一個寫入端(且在「分數大於 / 等於目前最高分」的區塊裡)
    writers = []
    for src, tgt in fx.items():
        if tgt == 0x53C2F and at(src - 1, 1) == b"\xa3":
            writers.append(hex(src - 1))
    check("[0x53c2f] 只有一個寫入端 0x15b12", writers == ["0x15b12"], f"{writers}")
    check("AI 可進表的索引 <= 27", guard_shape and shapes and tail_zero and max(ai) <= 27,
          f"門檻 {thr};可得分的法術 {sorted(ai)}")

    both = player | ai
    check("兩處都不會讀到戰前章節表(索引 < 指令表長度)",
          cmd_len is not None and max(both) < cmd_len, f"最大 {max(both)};指令表 {cmd_len} 格")
    unreached = sorted(set(range(cmd_len or 0)) - both)
    check("兩處都到不了的格只有 24(0x18)", unreached == [24], f"{unreached}")

    # 對照:只用 unit_list_bits_1a 的 40 個 bit 當上限(不看兩處的判斷)必須判為不符合
    naive = set(range(N_SPELLS))
    check("對照:只看已學法術 bit 數的上限", cmd_len is not None and max(naive) < cmd_len,
          f"最大 {max(naive)}", control=True)

    real = [r for r in results if not r["control"]]
    ctl = [r for r in results if r["control"]]
    for r in results:
        tag = ("C " if r["control"] else "  ") + ("符合" if r["ok"] else "不符合")
        print(f"{tag} {r['name']}: {r['detail']}")
    bad = [r["name"] for r in real if not r["ok"]] + [f"{r['name']}(對照沒有判為不符合)" for r in ctl if r["ok"]]
    if bad:
        print("FAIL", bad)
        return 1
    print(f"PASS {len(real)} 項;對照 {len(ctl)} 項判為不符合")
    return 0


if __name__ == "__main__":
    sys.stdout.reconfigure(encoding="utf-8")
    sys.exit(main(sys.argv))
