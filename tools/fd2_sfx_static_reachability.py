#!/usr/bin/env python3
"""fd2_sfx_static_reachability.py — 靜態判定哪些 SFX 呼叫點的「往回找 push」是可信的。

問題
----
`docs/data/sfx_index_callers.json` 是「從 `call play_sfx_a` 往回貪婪解析 `push`」產生的,
而 A.4(doc98 2026-09-04)用同一次 halt 的決定性證據推翻了其中一筆:`0x32307` 靜態解出
index 11、活體堆疊讀到 9,因為**執行流是從別處跳進那個 call 的,沒有經過它上面的 push**。

結果整張表(65/81)被降級成「候選清單」,而其餘 64 筆的處置寫成「需逐一活體確認」。
**那是把一個靜態可答的問題當成了活體問題。**

洞察
----
往回解析只在**「執行流可能不經過那個 push 就抵達 call」**時會錯。這件事靜態就查得到:
把整份程式碼的**所有分支目標**收集起來,再問「有沒有任何分支目標落在 (push, call] 這個
區間裡」。

* 沒有 → 要抵達 call 只能從 push 那裡 fall-through,歸屬**可信**。
* 有 → 存在一條繞過 push 的路徑,歸屬**存疑**,需要活體確認。

⚠ 這個判準的限制,必須跟結果一起讀
-----------------------------------
1. **只看得到靜態可解的分支目標。** 間接跳躍(`jmp [eax*4+table]`)的目標算不出來,
   所以「未被標記」**不等於證明安全**,只是「找不到繞過的路徑」。本專案已知有
   jump table(例如 doc11 記載的 `[eax*4+0x1D01]`),所以這個限制是真的,不是理論上的。

   ⚠ 實測時本工具回報「間接分支 **0** 個」。**那不是好消息,是可疑**:既然已知有跳表,
   掃不到任何間接分支,比較像是線性反組譯在資料區失步、把那些指令解成了別的東西。
   同一次掃描解出 111 個 `call play_sfx_a`、而資料檔只記載 65 個(且 65 全在其中),
   也指向同一件事。**所以完整性沒有被證明**,只有「已知的繞過路徑都被抓到了」。
2. 因此本工具的輸出是**分流**,不是判決:把 64 筆分成「可信」與「存疑」,
   讓活體確認的工作量集中到真正需要的那些。
3. 驗證方式:**已知答案的 `0x32307` 必須被標記為存疑**。抓不出它,這個方法就沒有鑑別力,
   結果一律不採用(本工具會自己檢查這一點並在失敗時拒絕輸出)。

用法
----
    python tools/fd2_sfx_static_reachability.py
    python tools/fd2_sfx_static_reachability.py --json out.json
"""

from __future__ import annotations

import argparse
import hashlib
import json
import os
import sys
from pathlib import Path

sys.path.insert(0, os.path.dirname(os.path.abspath(__file__)))

from capstone import CS_ARCH_X86, CS_MODE_32, Cs  # noqa: E402
from capstone.x86 import X86_OP_IMM  # noqa: E402

import safe_output  # noqa: E402


def load_code_region():
    """延遲載入程式碼區。

    `extract_event_id_groups` **在模組層就載入 EXE**,所以在 import 那一行做
    `from ... import base, code, end` 會讓本工具在缺少原版檔時**於 import 期間**炸掉——
    verify_all_tools 從空目錄執行時的 imports/cli 兩層都會 FAIL(2026-09-04 實測)。
    改成用到才載入,並把「請從 repo 根目錄執行」講清楚。
    """
    from extract_event_id_groups import base, code, end   # noqa: PLC0415
    return base, code, end

REPO = Path(__file__).resolve().parent.parent
CALLERS = REPO / "docs" / "data" / "sfx_index_callers.json"

PLAY_SFX_A = 0x25A96
# A.4 的決定性反例:靜態 11 / 活體 9。本工具必須能把它標成存疑。
KNOWN_MISATTRIBUTED = 0x32307

BRANCH_MNEMONICS = {"jmp", "je", "jne", "jz", "jnz", "ja", "jae", "jb", "jbe",
                    "jg", "jge", "jl", "jle", "js", "jns", "jo", "jno",
                    "jp", "jnp", "jc", "jnc", "jecxz", "loop", "loope", "loopne"}
MAX_LOOKBACK = 0x40          # 往回找 push 的視窗;與原表產生器同量級


def collect_branch_targets(md: Cs, code: bytes, base: int) -> tuple[set[int], int]:
    """線性反組譯整段程式碼,收集所有**靜態可解**的分支目標。

    回傳 (targets, indirect_count)。`indirect_count` 是算不出目標的分支數量——
    它直接量化了上面第 1 點的限制有多大,所以要一起回報,不能只給 targets。
    """
    targets: set[int] = set()
    indirect = 0
    for ins in md.disasm(code, base):
        if ins.mnemonic not in BRANCH_MNEMONICS:
            continue
        ops = ins.operands
        if ops and ops[0].type == X86_OP_IMM:
            targets.add(ops[0].imm)
        else:
            indirect += 1
    return targets, indirect


def find_push_and_call_sites(md: Cs, code: bytes, base: int) -> list[dict]:
    """找出所有 `call play_sfx_a`,以及各自往回最近的 `push imm`。"""
    seq = list(md.disasm(code, base))
    by_addr = {ins.address: i for i, ins in enumerate(seq)}
    out = []
    for i, ins in enumerate(seq):
        if ins.mnemonic != "call":
            continue
        ops = ins.operands
        if not (ops and ops[0].type == X86_OP_IMM and ops[0].imm == PLAY_SFX_A):
            continue
        push_addr = push_val = None
        j = i - 1
        while j >= 0 and ins.address - seq[j].address <= MAX_LOOKBACK:
            p = seq[j]
            if p.mnemonic == "push" and p.operands and p.operands[0].type == X86_OP_IMM:
                push_addr, push_val = p.address, p.operands[0].imm
                break
            j -= 1
        out.append({"call": ins.address, "push": push_addr, "index": push_val})
    return out


def main() -> int:
    ap = argparse.ArgumentParser(description=__doc__,
                                 formatter_class=argparse.RawDescriptionHelpFormatter)
    ap.add_argument("--json", help="輸出分流結果到 JSON")
    a = ap.parse_args()

    try:
        base, code, end = load_code_region()
    except FileNotFoundError as exc:
        print(f"{exc}", file=sys.stderr)
        print("用法: 從 repo 根目錄執行 python tools/fd2_sfx_static_reachability.py",
              file=sys.stderr)
        return 2

    md = Cs(CS_ARCH_X86, CS_MODE_32)
    md.detail = True
    print(f"程式碼區:{base:#x}..{end:#x}({len(code)} bytes)")

    targets, indirect = collect_branch_targets(md, code, base)
    print(f"靜態可解的分支目標 {len(targets)} 個;**目標算不出來的分支 {indirect} 個**"
          f"(這是本方法的盲區,見檔頭限制 1)")

    all_sites = find_push_and_call_sites(md, code, base)
    doc = json.loads(CALLERS.read_text(encoding="utf-8"))
    documented = {int(x, 16) for v in doc["index_to_callers"].values() for x in v}
    site2idx = {int(x, 16): int(k) for k, v in doc["index_to_callers"].items() for x in v}
    live_ok = {int(k, 16): v for k, v in doc["_meta"]["live_verified"].items()}

    # 線性反組譯會在資料區失步,decode 出不存在的 `call`。實測:掃到 111 個,
    # 而資料檔記載 65 個,**65 全部是我的子集、一個都沒漏**,多出來的 46 個是失步產物。
    # 所以只分析已記載的那 65 筆,不把失步產物混進結論。
    extra = len({s["call"] for s in all_sites}) - len(documented)
    print(f"`call {PLAY_SFX_A:#x}`:線性掃到 {len(all_sites)} 個,資料檔記載 {len(documented)} 個"
          f"(全部涵蓋);多出的 {extra} 個視為失步產物,不列入分析")
    sites = [s for s in all_sites if s["call"] in documented]

    trusted, suspect, nopush = [], [], []
    for s in sites:
        if s["push"] is None:
            nopush.append(s)
            continue
        # 落在 (push, call] 的分支目標 = 存在繞過 push 抵達 call 的路徑
        intruders = sorted(t for t in targets if s["push"] < t <= s["call"])
        s["intruding_targets"] = [hex(t) for t in intruders]
        (suspect if intruders else trusted).append(s)

    # ---- 方法自驗:已知答案的那一筆必須被標成存疑 -------------------------
    known = next((s for s in sites if s["call"] == KNOWN_MISATTRIBUTED), None)
    if known is None:
        print(f"\n✗ 找不到已知反例 {KNOWN_MISATTRIBUTED:#x} 的呼叫點——"
              f"位址或載入基準有問題,拒絕輸出結果")
        return 2
    caught = known in suspect
    print(f"\n方法自驗(A.4 的已知反例 {KNOWN_MISATTRIBUTED:#x}):"
          f"{'✓ 被標成存疑' if caught else '✗ **沒有被抓到**'}")
    if not caught:
        print("  這個方法對唯一已知答案沒有鑑別力,**結果一律不採用**。")
        print(f"  (該呼叫點的 push 在 {known['push'] and hex(known['push'])},"
              f"區間內分支目標:{known.get('intruding_targets')})")
        return 1

    # ---- 方法自驗之二:正對照 ------------------------------------------
    # 只有負對照不夠——一個「一律標成存疑」的判準也會通過負對照。
    # 已活體確認的呼叫點必須 (a) 全部落在可信,且 (b) 靜態解出的 index 與活體值一致。
    pos = [s for s in trusted if s["call"] in live_ok]
    pos_bad = [s for s in suspect if s["call"] in live_ok]
    val_bad = [s for s in pos if s["index"] != live_ok[s["call"]]]
    print(f"方法自驗(正對照,{len(live_ok)} 個已活體確認的呼叫點):"
          f"落在可信 {len(pos)}/{len(live_ok)}、被誤標存疑 {len(pos_bad)}、"
          f"靜態值與活體不符 {len(val_bad)}")
    if pos_bad or val_bad:
        print("  正對照失敗,**結果一律不採用**:",
              [hex(s["call"]) for s in pos_bad + val_bad][:6])
        return 1

    print(f"\n分流結果:可信 {len(trusted)}、存疑 {len(suspect)}、找不到 push {len(nopush)}")
    print("存疑清單(需活體確認):")
    for s in suspect[:20]:
        print(f"  call {s['call']:#x}  push@{s['push']:#x} index={s['index']}"
              f"  闖入目標={s['intruding_targets'][:3]}")
    if len(suspect) > 20:
        print(f"  ...(其餘 {len(suspect)-20} 筆)")

    if a.json:
        try:
            safe_output.guard_json_output(a.json)
        except safe_output.UnsafeOutputPath as exc:
            print(exc, file=sys.stderr)
            return 2
        payload = {
            "_meta": {
                "method": "收集全部靜態可解分支目標,檢查有無落在 (push, call] 區間",
                "limitation": f"間接分支 {indirect} 個目標未知,故『可信』是過濾不是證明",
                "self_check": f"A.4 已知反例 {KNOWN_MISATTRIBUTED:#x} 被正確標成存疑",
                "exe_md5": hashlib.md5(Path(
                    "org_game/炎龍騎士團/FLAME2/FD2.EXE").read_bytes()).hexdigest(),
            },
            "trusted": [{k: (hex(v) if isinstance(v, int) and k != "index" else v)
                         for k, v in s.items()} for s in trusted],
            "suspect": [{k: (hex(v) if isinstance(v, int) and k != "index" else v)
                         for k, v in s.items()} for s in suspect],
            "no_push_found": [{k: (hex(v) if isinstance(v, int) and k != "index" else v)
                               for k, v in s.items()} for s in nopush],
        }
        Path(a.json).write_text(json.dumps(payload, ensure_ascii=False, indent=1),
                                encoding="utf-8")
        print("->", a.json)
    return 0


if __name__ == "__main__":
    sys.exit(main())
