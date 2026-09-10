#!/usr/bin/env python3
"""fd2_re — 用 Miles AIL 自己的 AIL_DEBUG 追蹤字串,機械地命名整層音訊驅動函式。

為什麼需要這支
--------------
doc36 把 `play_sfx_a` 內的呼叫序列 `0x39805 -> 0x39521 -> 0x39694` 與初始化處的
`0x392d0` 標為「Miles AIL sample handle 的標準用法」,但自陳那是**由呼叫形狀推得**、
沒有逐指令證實到驅動內部,四個位址的本體也一直沒展開(該節的「誠實範圍」)。

本輪發現不需要展開本體:這份 binary 連進來的 Miles AIL 保留了它的 **AIL_DEBUG
追蹤設施**,每一個 API 進入點在做完標準前導之後,都會把**自己的名字**當格式字串
傳給追蹤函式 `0x3f46b`:

    0x39316  mov  edi, [esp + 0x10]
    0x3931a  push edi
    0x3931b  push 0x5078d              ; "AIL_allocate_sample_handle(0x%X)\\n"
    0x39320  mov  ebp, [0x54164]
    0x39326  push ebp
    0x39327  call 0x3f46b

也就是說**函式名是資料,不是推論**。本工具把這件事做成可重生的對照表。

機制(兩段,都不靠人工判讀)
----------------------------
A. **字串端**:掃 obj2 的資料段,找形如 `AIL_<identifier>(<fmt>)\\n` 的追蹤字串,
   記下每一條的絕對位址。

B. **程式端**:用 `le_xref.parse_le` 建立整份 image 的 fixup 表
   `{code_linear: target_abs}`,反查每條字串被哪個 `push imm32` 引用;再從該位置往前
   找**最近一次對 `0x54178` 的引用**——那是所有 AIL 進入點共用的前導
   (`mov edx,[0x54178]; inc edx; mov [0x54178],edx`,巢狀深度計數),`mov` 的
   opcode 在該引用位置前 2 個 byte;最後往前跨過連續的單 byte `push ebx/ebp/esi/edi`
   就是函式進入點。

判準與已知真值
--------------
`--selftest` 用四個**先以手工反組譯獨立確認過**的位址當真值:
`0x392d0`=AIL_allocate_sample_handle、`0x39521`=AIL_init_sample、
`0x39694`=AIL_set_sample_address、`0x39805`=AIL_stop_sample。四個都必須由本工具
純機械地重現。另有負向控制:把前導錨點換成一個**不是** `0x54178` 的全域,
對照表必須塌掉——否則「往前找最近的前導」這一步等於沒有內容。

用法:
    python tools/derive_ail_entry_points.py --exe <FD2.EXE>
    python tools/derive_ail_entry_points.py --exe <FD2.EXE> --json docs/data/ail_entry_points.json
    python tools/derive_ail_entry_points.py --selftest
"""
from __future__ import annotations

import argparse
import json
import re
import sys
from pathlib import Path

if hasattr(sys.stdout, "reconfigure"):
    sys.stdout.reconfigure(encoding="utf-8")
    sys.stderr.reconfigure(encoding="utf-8")

sys.path.insert(0, str(Path(__file__).resolve().parent))
from le_xref import parse_le                                    # noqa: E402
from disasm_le import build_fixups, load_code                   # noqa: E402

ROOT = Path(__file__).resolve().parents[1]
DEFAULT_EXE = ROOT / "org_game" / "炎龍騎士團" / "FLAME2" / "FD2.EXE"

# 所有 AIL 進入點共用的前導所遞增的巢狀深度計數。錨點必須是這一個。
NEST_DEPTH_GLOBAL = 0x54178
# 前導裡緊接在進入點之後的 callee-saved 單 byte push:ebx / ebp / esi / edi。
PUSH_OPCODES = {0x53, 0x55, 0x56, 0x57}
# `mov edx, dword ptr [disp32]` = 8B 15 <disp32>:fixup 記的是 disp32 的位置。
MOV_DISP_BACKSTEP = 2
# 前導對 NEST_DEPTH_GLOBAL 有**兩次**引用,不是一次:
#     8B 15 <disp>   mov edx, [0x54178]      <- 讀,disp 在 R
#     42             inc edx
#     89 15 <disp>   mov [0x54178], edx      <- 寫,disp 在 R+7
# 「往前找最近的一次」會抓到後面那個寫,算出來的進入點固定偏後 9~10 個 byte。
# 抓到寫之後要退回配對的讀,才是前導真正的開頭。
ANCHOR_PAIR_DELTA = 7
# 前導與「push 自己的名字」之間最多隔多遠(實測最遠 ~0x80)。放寬到 0x200 仍遠小於
# 相鄰兩個 AIL 進入點的距離,不會跨函式抓錯。
MAX_PREAMBLE_DISTANCE = 0x200

TRACE_STRING = re.compile(rb"AIL_[A-Za-z0-9_]{2,60}\([^\x00\n]{0,80}\)\n\x00")

# 手工反組譯獨立確認過的四個真值(doc36 的殘留正是這四個)。
GROUND_TRUTH = {
    0x392D0: "AIL_allocate_sample_handle",
    0x39521: "AIL_init_sample",
    0x39694: "AIL_set_sample_address",
    0x39805: "AIL_stop_sample",
}


def read_exe(exe: str | Path) -> tuple[bytes, dict]:
    data = Path(exe).read_bytes()
    return data, parse_le(data)


def object_bytes(data: bytes, meta: dict, index: int) -> tuple[bytes, int]:
    """回傳第 index 個 LE object 的位元組與其 base(逐 object 換算,不套 obj1 公式)。"""
    obj = meta["objs"][index]
    off = meta["data_off"] + (obj["first"] - 1) * meta["page_size"]
    return data[off:off + obj["vsize"]], obj["base"]


def trace_strings(data: bytes, meta: dict) -> dict[int, str]:
    """{絕對位址: AIL 函式名} —— 只取名字,丟掉格式參數部分。"""
    blob, base = object_bytes(data, meta, 1)          # obj2 = 資料
    out = {}
    for m in TRACE_STRING.finditer(blob):
        text = m.group().rstrip(b"\x00\n").decode("latin1")
        out[base + m.start()] = text.split("(", 1)[0]
    return out


def entry_for_reference(code: bytes, code_base: int, by_pos: dict[int, int],
                        ref_pos: int, anchor: int = NEST_DEPTH_GLOBAL) -> int | None:
    """從「push <字串>」的位置往回推函式進入點,見模組 docstring 的機制 B。"""
    anchors = [p for p in range(ref_pos - MAX_PREAMBLE_DISTANCE, ref_pos)
               if by_pos.get(p) == anchor]
    if not anchors:
        return None
    nearest = max(anchors)
    if nearest - ANCHOR_PAIR_DELTA in anchors:      # 抓到的是寫,退回配對的讀
        nearest -= ANCHOR_PAIR_DELTA
    entry = nearest - MOV_DISP_BACKSTEP
    while entry - 1 >= code_base and code[entry - 1 - code_base] in PUSH_OPCODES:
        entry -= 1
    return entry


def derive(exe: str | Path, anchor: int = NEST_DEPTH_GLOBAL) -> dict[int, str]:
    """{函式進入點: AIL 名稱}。"""
    data, meta = read_exe(exe)
    code, code_base = load_code(data, meta)
    by_pos = build_fixups(data, meta)
    strings = trace_strings(data, meta)
    refs: dict[int, list[int]] = {}
    for pos, tgt in by_pos.items():
        if tgt in strings:
            refs.setdefault(tgt, []).append(pos)
    out: dict[int, str] = {}
    for addr, name in strings.items():
        for pos in sorted(refs.get(addr, [])):
            entry = entry_for_reference(code, code_base, by_pos, pos, anchor)
            if entry is not None:
                out.setdefault(entry, name)
    return out


def build(exe: str | Path) -> dict:
    mapping = derive(exe)
    data, meta = read_exe(exe)
    strings = trace_strings(data, meta)
    return {
        "_source": "fd2_re — 以 Miles AIL 自身的 AIL_DEBUG 追蹤字串命名音訊驅動進入點。",
        "_generator": "tools/derive_ail_entry_points.py",
        "_method": "追蹤字串(資料)+ LE fixup 反查 + 共用前導錨點 0x54178;函式名是資料不是推論。",
        "_trace_strings_found": len(strings),
        "_entry_points_resolved": len(mapping),
        "entry_points": {f"{addr:#07x}": name for addr, name in sorted(mapping.items())},
    }


def selftest() -> int:
    fails = []
    exe = DEFAULT_EXE
    if not exe.exists():
        print(f"SKIP:找不到 {exe}(本檢查需要原版 EXE)")
        return 0

    print("(1) 追蹤字串必須抓得到,且數量與 Miles AIL 的 API 規模相符")
    data, meta = read_exe(exe)
    strings = trace_strings(data, meta)
    ok1 = len(strings) >= 100
    print(f"    {'PASS' if ok1 else 'FAIL'}: 找到 {len(strings)} 條 AIL_* 追蹤字串")
    if not ok1:
        fails.append(f"追蹤字串只找到 {len(strings)} 條")

    print("\n(2) 四個**手工反組譯獨立確認過**的位址必須被純機械地重現")
    mapping = derive(exe)
    wrong = {f"{a:#07x}": (want, mapping.get(a)) for a, want in GROUND_TRUTH.items()
             if mapping.get(a) != want}
    ok2 = not wrong
    print(f"    {'PASS' if ok2 else 'FAIL'}: 真值 {len(GROUND_TRUTH)} 筆;不符 {wrong or '無'}")
    if not ok2:
        fails.append(f"已知真值對不上:{wrong}")

    print("\n(3) 進入點必須互不相同 —— 同一個位址不得對到兩個名字")
    ok3 = len(mapping) == len(set(mapping.values()))
    dupes = [n for n in set(mapping.values()) if list(mapping.values()).count(n) > 1]
    print(f"    {'PASS' if ok3 else 'FAIL'}: {len(mapping)} 個進入點 / "
          f"{len(set(mapping.values()))} 個名字;重複 {dupes or '無'}")
    if not ok3:
        fails.append(f"名字重複:{dupes}")

    print("\n(4) 負向控制:把前導錨點換成別的全域,對照表必須塌掉")
    # 若不換錨點也能得到同一張表,代表「往前找最近的前導」這一步沒有做事,
    # (2) 就會變成平凡通過。錨點換成 0x54174(前導裡另一個被讀的全域,但**不是**
    # 被 inc 的那個),解析結果必須明顯變少或對不上真值。
    other = derive(exe, anchor=0x54174)
    ok4 = other != mapping and any(other.get(a) != want for a, want in GROUND_TRUTH.items())
    print(f"    {'PASS' if ok4 else 'FAIL'}: 換錨點後解析出 {len(other)} 個進入點"
          f"(原本 {len(mapping)}),與真值一致者 "
          f"{sum(1 for a, w in GROUND_TRUTH.items() if other.get(a) == w)}/{len(GROUND_TRUTH)}")
    if not ok4:
        fails.append("換掉錨點結果不變,(2) 因此是平凡的")

    if fails:
        print("\nSELFTEST FAILED:")
        for f in fails:
            print("  -", f)
        return 1
    print("\n--selftest passed(追蹤字串抓取 + 四筆手工真值機械重現 + 進入點唯一性 + "
          "換錨點的負向控制)。")
    return 0


def main() -> int:
    ap = argparse.ArgumentParser(description=__doc__,
                                 formatter_class=argparse.RawDescriptionHelpFormatter)
    ap.add_argument("--exe", default=str(DEFAULT_EXE))
    ap.add_argument("--json")
    ap.add_argument("--selftest", action="store_true")
    a = ap.parse_args()
    if a.selftest:
        return selftest()
    data = build(a.exe)
    text = json.dumps(data, ensure_ascii=False, indent=1) + "\n"
    if a.json:
        Path(a.json).write_text(text, encoding="utf-8")
        print(f"-> {a.json}")
    else:
        print(text)
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
