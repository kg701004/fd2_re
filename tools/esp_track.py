#!/usr/bin/env python3
"""fd2_re — 追蹤函式內的 ESP 位移，把 `[esp+N]` 運算元正確解析成「第幾個參數」。

為什麼需要這支工具
------------------
本專案反覆遇到同一種錯誤：手算 `[esp+N]` 對應到哪個參數時，忘了把函式序言之後累積的
push/sub esp 位移算進去，於是把 param_1 誤讀成 param_2、或反過來。2026-09-07 的
worklist item 791 收尾就是卡在這裡（`0x55-param_1` 算出的差值最後落在 `0x15f0e`
六個引數的哪一格，手動追蹤沒追完，被誠實記錄為殘留）；同一天 item 857 的
`0x1366a(0x52)`、item 1511 的 `0x24bde` 也都需要同一種「引數到底是什麼」的解析。

Ghidra 的 decompile 在本專案 `-noanalysis` 設定下已知**不可靠地重建參數**（多次
記錄：憑空生出 param_5..param_8、或把明明有引數的函式標成 `(void)`），所以答案必須
從 raw disassembly 自己算。這支工具就是把那個算法寫死成可重複執行、可自檢的程式碼，
而不是每次靠人腦重算。

模型
----
以「函式進入點時的 ESP」為原點（記為 entry_esp）。此時 `[entry_esp+0]` 是回傳位址、
`[entry_esp+4]` 是 param_1、`[entry_esp+8]` 是 param_2 …依此類推。

工具逐指令累加 `esp_delta`（相對 entry_esp 的位移，恆為 0 或負值）：
  - `push X`           → -4
  - `pop X`            → +4
  - `sub esp, imm`     → -imm
  - `add esp, imm`     → +imm
  - `call`             → 0（呼叫本身在 callee 回來後不改變 ESP；cdecl 的清棧由呼叫端
                          自己的 `add esp, N` 表達，會被上一條規則吃到）
  - `ret`              → 停止

**Watcom stack-check 序言的特例**：本專案的 EXE 幾乎每個函式都以
`push <frame_size>; call 0x3702f` 開頭。`0x3702f` 是 stdcall 慣例、由 callee 自己
清掉那個 push（doc48/既有 trace_item_sfx_dispatch.py 的 `.object1` 盲區處理已依賴
這個事實），所以這兩條指令**淨效果為 0**，不能當成一般 push 累加。工具偵測到
`push imm` 緊接 `call <STACK_CHECK>` 時會把該 push 抵銷。

於是任何 `[esp + N]` 的絕對位移是 `abs = N + esp_delta`（esp_delta 為負），
再換算：`abs == 0` → 回傳位址、`abs >= 4 且 abs % 4 == 0` → `param_{abs//4}`、
`abs < 0` → 區域變數/被保存的暫存器。

用法
----
    # 解析單一函式裡所有 [esp+N] 的參數對應
    python tools/esp_track.py --entry 0x15f0e --length 118

    # 只看某個呼叫點之前推了哪些引數（cdecl：最後 push 的是 param_1）
    python tools/esp_track.py --entry 0x1f1cc --length 318 --call-site 0x1f288

    # 自檢（正向 4 筆 + 反向控制組）
    python tools/esp_track.py --selftest

自檢說明（正反雙向）
--------------------
**正向**：4 筆 pin 住的期望值，全部來自 2026-09-07 當天以人工逐指令推導、並且已經
寫進 worklist/doc57 的結論（`0x15f0e` 的 param_1/param_6、`0x1f1cc` 的 param_1、
`0x1f42d` 的 param_1/param_2）。工具算出來必須逐筆吻合。

**反向（兩組，都必須有鑑別力）**：

② **對立實作對照**：同時跑一份「天真版」——完全不追蹤 ESP、直接把 `[esp+N]` 的 N 當
   成絕對位移。若天真版在這些 pin 上給出**跟正確版一樣**的答案，代表這批 pin 根本
   分辨不出工具有沒有在做事，自檢就是裝飾性的。因此本項要求**每一筆 pin 上兩者都必須
   不同**，否則判定失敗。（這是照本專案 `degenerate-verification-sample` 的教訓設計：
   對立假說若預測同樣的觀察，檢查就沒有價值。）

   註：第一版曾用「進入點 +1 byte」當負對照，實測**無效**——x86 會自我重新同步，錯位
   反組譯很快回到同一條指令流，5 筆 pin 全部給出跟正確版相同的答案。該對照已移除，
   這個失敗過程本身記在此處，避免日後有人再寫一次同樣沒有鑑別力的對照。

③ **故障注入**：關掉 Watcom stack-check 序言的抵銷規則後重跑，pin 必須改變。這證明
   「序言淨效果為 0」這條規則真的參與了計算，而不是剛好不影響結果。
"""

from __future__ import annotations

import argparse
import re
import sys
from pathlib import Path

sys.path.insert(0, str(Path(__file__).resolve().parent))
import capstone_probe as cprobe  # noqa: E402

STACK_CHECK = 0x3702F
ESP_OPERAND = re.compile(r"\[esp(?:\s*\+\s*(0x[0-9a-f]+|\d+))?\]", re.I)


def _imm(text: str) -> int | None:
    text = text.strip()
    try:
        return int(text, 16) if text.lower().startswith("0x") else int(text)
    except ValueError:
        return None


def classify(abs_off: int) -> str:
    """把「相對 entry_esp 的絕對位移」翻譯成人看得懂的角色。"""
    if abs_off == 0:
        return "return_address"
    if abs_off > 0:
        if abs_off % 4:
            return f"param_area+0x{abs_off:x}(unaligned)"
        return f"param_{abs_off // 4}"
    return f"local(0x{-abs_off:x} below entry_esp)"


def track(entry: int, instructions: list[dict], *, cancel_stack_check: bool = True,
          ignore_esp_delta: bool = False) -> list[dict]:
    """逐指令回傳 [{address, text, esp_delta, esp_refs:[{n, abs, role}]}]。

    `cancel_stack_check=False` 供自檢③故障注入用（關掉序言抵銷規則）。
    `ignore_esp_delta=True` 是自檢②的「天真版對立實作」：完全不追蹤 ESP。
    兩個旗標都只給 --selftest 使用，正常解析不要動它們。
    """
    out: list[dict] = []
    esp_delta = 0
    ins_list = sorted(instructions, key=lambda i: int(i["address"], 16))
    for idx, ins in enumerate(ins_list):
        mnem = ins["mnemonic"].lower()
        ops = ins["operands"]
        addr = int(ins["address"], 16)

        # 讀取端要用「這條指令執行前」的 esp_delta
        refs = []
        for m in ESP_OPERAND.finditer(ops):
            n = _imm(m.group(1)) if m.group(1) else 0
            if n is None:
                continue
            abs_off = n if ignore_esp_delta else n + esp_delta
            refs.append({"n": n, "abs": abs_off, "role": classify(abs_off)})

        out.append({
            "address": ins["address"],
            "text": f"{mnem} {ops}".strip(),
            "esp_delta": esp_delta,
            "esp_refs": refs,
        })

        # 再套用這條指令對 ESP 的效果
        if mnem == "push":
            nxt = ins_list[idx + 1] if idx + 1 < len(ins_list) else None
            is_stack_check_prologue = cancel_stack_check and (
                _imm(ops) is not None
                and nxt is not None
                and nxt["mnemonic"].lower() == "call"
                and (_imm(nxt["operands"]) == STACK_CHECK)
            )
            if not is_stack_check_prologue:
                esp_delta -= 4
            else:
                out[-1]["text"] += "   ; watcom stack-check prologue (net 0)"
        elif mnem == "pop":
            esp_delta += 4
        elif mnem in ("sub", "add") and ops.lower().replace(" ", "").startswith("esp,"):
            v = _imm(ops.split(",", 1)[1])
            if v is not None:
                esp_delta += -v if mnem == "sub" else v
        elif mnem == "ret":
            break
    return out


def call_args(entry: int, instructions: list[dict], call_site: int) -> list[dict]:
    """回傳 call_site 之前連續 push 的引數，並標上 cdecl 的 param 編號
    （最後 push 的最靠近 ESP，是 callee 的 param_1）。

    **引數個數以呼叫端自己的清棧指令為準**：cdecl 由呼叫端在 call 之後用
    `add esp, N` 清掉 N/4 個引數，所以只取最近的 N/4 個 push。少了這個界限，
    往回掃會一路吃到函式序言存起來的暫存器 push，多報出根本不存在的
    param_7/param_8（2026-09-07 首次使用本工具時實際踩到，已修）。
    找不到清棧指令時（例如 callee 自己清棧的 stdcall）不設限，但會標記
    `bounded=False` 讓呼叫者知道這批引數個數未經確認。
    """
    tracked = track(entry, instructions)
    by_addr = {int(t["address"], 16): t for t in tracked}
    if call_site not in by_addr:
        raise SystemExit(f"call site 0x{call_site:x} 不在反組譯範圍內")

    # 找 call 之後的第一條 add esp, N
    limit = None
    after = [t for t in tracked if int(t["address"], 16) > call_site]
    for t in after[:3]:
        txt = t["text"].replace(" ", "")
        if txt.startswith("addesp,"):
            v = _imm(txt.split(",", 1)[1])
            if v is not None:
                limit = v // 4
            break

    ordered = [t for t in tracked if int(t["address"], 16) < call_site]
    pushes: list[dict] = []
    for t in reversed(ordered):
        head = t["text"].split()[0]
        if head == "push" and "stack-check" not in t["text"]:
            pushes.append(t)
            if limit is not None and len(pushes) >= limit:
                break
        elif head in ("call", "ret"):
            break
    return [{"param": i + 1, "address": p["address"], "text": p["text"],
             "bounded": limit is not None}
            for i, p in enumerate(pushes)]


# --------------------------------------------------------------------------
# 自檢
# --------------------------------------------------------------------------
# (entry, length, 指令位址, 期望角色) —— 全部來自 2026-09-07 人工逐指令推導的既有結論
_POSITIVE = [
    (0x15F0E, 118, 0x15F1F, "param_1"),   # mov esi, [esp+0x18]
    (0x15F0E, 118, 0x15F23, "param_6"),   # mov edi, [esp+0x2c]
    (0x1F1CC, 318, 0x1F208, "param_1"),   # push [esp+0x14]（轉給 0x1f42d）
    (0x1F42D, 214, 0x1F439, "param_2"),   # push [esp+0x10]
    (0x1F42D, 214, 0x1F444, "param_1"),   # sub ebx, [esp+0x14]
]


def _roles_at(entry: int, length: int, want_addr: int, cache: dict) -> list[str]:
    key = (entry, length)
    if key not in cache:
        data = cprobe.fetch_bytes(entry, length, quiet=True)
        cache[key] = cprobe.disassemble(entry, data)
    tracked = track(entry, cache[key])
    for t in tracked:
        if int(t["address"], 16) == want_addr:
            return [r["role"] for r in t["esp_refs"]]
    return []


def _tracked(entry: int, length: int, cache: dict, **kw) -> list[dict]:
    key = (entry, length)
    if key not in cache:
        data = cprobe.fetch_bytes(entry, length, quiet=True)
        cache[key] = cprobe.disassemble(entry, data)
    return track(entry, cache[key], **kw)


def _roles(entry: int, length: int, want: int, cache: dict, **kw) -> list[str]:
    for t in _tracked(entry, length, cache, **kw):
        if int(t["address"], 16) == want:
            return [r["role"] for r in t["esp_refs"]]
    return []


def selftest() -> int:
    cache: dict = {}
    fails: list[str] = []

    print("(1) forward: 5 hand-verified parameter mappings")
    for entry, length, addr, expect in _POSITIVE:
        roles = _roles(entry, length, addr, cache)
        ok = expect in roles
        print(f"    {'PASS' if ok else 'FAIL'} 0x{addr:x} (entry 0x{entry:x}) -> "
              f"{roles or '(no esp operand)'}   expected {expect}")
        if not ok:
            fails.append(f"0x{addr:x}: expected {expect}, got {roles}")

    print("\n(2) rival-implementation control: a naive version that ignores esp_delta")
    print("    must DISAGREE on every pin, otherwise the pins cannot tell whether the")
    print("    tool is tracking anything at all")
    same = 0
    for entry, length, addr, expect in _POSITIVE:
        good = _roles(entry, length, addr, cache)
        naive = _roles(entry, length, addr, cache, ignore_esp_delta=True)
        agree = naive == good
        same += agree
        print(f"    {'FAIL(same)' if agree else 'ok(differs)'} 0x{addr:x}: correct={good} naive={naive}")
    if same:
        fails.append(f"rival control: naive version agreed on {same}/{len(_POSITIVE)} pins -- "
                     "those pins are decorative")
    else:
        print(f"    PASS: naive disagrees on all {len(_POSITIVE)} pins")

    print("\n(3) fault injection: disable the Watcom stack-check cancellation;")
    print("    pins that sit behind such a prologue must change")
    changed = 0
    for entry, length, addr, expect in _POSITIVE:
        good = _roles(entry, length, addr, cache)
        broken = _roles(entry, length, addr, cache, cancel_stack_check=False)
        if broken != good:
            changed += 1
        print(f"    {'ok(changed)' if broken != good else 'unchanged'} 0x{addr:x}: "
              f"correct={good} fault-injected={broken}")
    if changed == 0:
        fails.append("fault injection changed nothing -- the stack-check rule is untested")
    else:
        print(f"    PASS: {changed}/{len(_POSITIVE)} pins changed, so the rule is load-bearing")

    print("\n(4) invariant: esp_delta must be 0 right after the stack-check prologue")
    after = [t for t in _tracked(0x15F0E, 40, cache) if int(t["address"], 16) == 0x15F18]
    if after and after[0]["esp_delta"] == 0:
        print("    PASS: esp_delta == 0 at 0x15f18")
    else:
        got = after[0]["esp_delta"] if after else "N/A"
        fails.append(f"prologue cancellation: esp_delta at 0x15f18 = {got}, expected 0")
        print(f"    FAIL: esp_delta = {got}")

    if fails:
        print("\nSELFTEST FAILED:")
        for f in fails:
            print("  -", f)
        return 1
    print("\n--selftest passed (1 forward + 3 independent reverse checks).")
    return 0


def main() -> int:
    ap = argparse.ArgumentParser(description=__doc__,
                                 formatter_class=argparse.RawDescriptionHelpFormatter)
    ap.add_argument("--entry", type=lambda s: int(s, 0))
    ap.add_argument("--length", type=int, default=256)
    ap.add_argument("--call-site", type=lambda s: int(s, 0))
    ap.add_argument("--only-params", action="store_true", help="只印出有 [esp+N] 參數存取的行")
    ap.add_argument("--selftest", action="store_true")
    args = ap.parse_args()

    if args.selftest:
        return selftest()
    if args.entry is None:
        ap.error("需要 --entry（或 --selftest）")

    data = cprobe.fetch_bytes(args.entry, args.length, quiet=True)
    ins = cprobe.disassemble(args.entry, data)

    if args.call_site:
        for a in call_args(args.entry, ins, args.call_site):
            print(f"  param_{a['param']}  <- {a['address']}: {a['text']}")
        return 0

    for t in track(args.entry, ins):
        if args.only_params and not t["esp_refs"]:
            continue
        roles = "  ".join(f"[esp+0x{r['n']:x}]={r['role']}" for r in t["esp_refs"])
        print(f"{t['address']}: esp{t['esp_delta']:+#06x}  {t['text']:<44} {roles}")
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
