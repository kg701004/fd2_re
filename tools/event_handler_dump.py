#!/usr/bin/env python3
"""炎龍騎士團2 — 戰場事件 handler 反組譯 + 事件原語標註。

針對章節戰場事件跳表 0x51b19 的各章 handler(doc 25),遞迴反組譯單一 handler
(從入口跟隨 jcc/jmp 到 ret,不跟隨 call),並把已知事件原語標成可讀語意,
產出「條件→動作」序列,供 remake 改寫成資料驅動腳本(非 hardcoding)。

已知原語(doc 23/24/25):
  0x3453e(idx)         查單位 #idx 狀態 [0x53a45][idx+5]&1
  0x205be              共用 raw 三值結果規則
  0x205da              獨立的戰場重設／完整章節載入入口
  0x15f84              繪事件畫面(全螢幕圖)
  0x1088d              完整章節 loader（FDTXT + FDFIELD/roster/map）
  [0x53ecc]=N          設 raw pending/result code；高階語意依 caller
  [0x53ec8]            raw 累積量(clamp 99)，不是回合數
  [0x53a45]            戰場單位陣列基底(每單位 0x50B)
  [0x53c03]            目前章節

用法:
  python3 event_handler_dump.py <EXE> <handler_hex> [end_hex]    dump 單一 handler
  python3 event_handler_dump.py <EXE> table                       dump 0x51b19 全 30 章 handler
"""
import sys
sys.path.insert(0, __file__.rsplit('/', 1)[0])
from callgraph_le import CG, fixup_map

PRIM = {
    0x3453e: 'raw_record_byte5_bit0(idx)',
    0x205be: 'raw_result_code_0_1_2',
    0x205da: 'reset_and_load_chapter',
    0x15f84: '繪畫面', 0x1088d: '完整章節載入', 0x111ba: '載資源', 0x25977: 'play_bgm/scene',
    0x25a96: 'play_sfx', 0x36cd7: '__STK(舊版)', 0x3702f: '__STK',
    0x2cad7: '戰後raw_gate(舊版,現行位址未解)', 0x18890: '戰鬥行動',
    0x3453e: 'raw_record_byte5_bit0(idx)(舊版)', 0x34894: 'raw_record_byte5_bit0(idx)',
}

# 2026-09-08:上面 3 筆在現行參考版是**死位址**(呼叫端 0)。這與
# dump_chapter_beats.py 的 PRIM/SKIP 是同一類問題:表過期不會報錯,只會讓
# 註解安靜地標不出來。兩筆有明確對應(已加在上表),第三筆沒有:
#
#   0x3453e -> 0x34894   實測新位址 50 個呼叫端,且是合法 Watcom 入口
#   0x36cd7 -> 0x3702f   現行 stack-check,541 個呼叫端
#   0x2cad7 -> **未解**  已列於 docs/data/known_address_errata.json,與
#                        0x2ccb6/0x2fd93 同一類(改基準前的手動反組譯位址);
#                        該檔已載明 `+0x190` 只是局部有效的錨點、不是常數平移,
#                        所以這裡**不猜**。
#
# selftest 的規則因此是:每一筆 PRIM 位址要嘛在現行 EXE 解得開,要嘛列在
# KNOWN_STALE 裡並附理由 —— 新的死位址不能靜默混進來。
KNOWN_STALE = {
    0x36cd7: "舊版 __STK;現行為 0x3702f(同表已收錄)",
    0x3453e: "舊版 raw_record_byte5_bit0;現行為 0x34894(同表已收錄)",
    0x2cad7: "現行位址未解,見 docs/data/known_address_errata.json"
             "(與 0x2ccb6/0x2fd93 同類,+0x190 只是局部錨點)",
}
VAR = {0x53ecc: 'raw_pending_result_code', 0x53ec8: 'raw_accumulator', 0x53a45: '單位陣列', 0x53c03: '章節', 0x51a83: 'raw_overlay_selector'}


def annot(ins, fx):
    m, op = ins.mnemonic, ins.op_str
    note = ''
    # 相對 call/jmp:target 直接在 op_str(E8/E9 rel32 不經 fixup)
    if m == 'call' and op.startswith('0x'):
        t = int(op, 16)
        note = f'  ; ★{PRIM[t]}' if t in PRIM else f'  ; →動作 {hex(t)}'
    else:
        # 絕對資料引用走 fixup(disp32 被重定位)
        for o in range(ins.address, ins.address + ins.size):
            if o in fx:
                t = fx[o]
                if t in VAR:
                    note = f'  ; ⟨{VAR[t]}⟩'
                break
    return f'{ins.address:#08x}  {m:<6} {op}{note}'


def dump(cg, fx, start, end):
    """遞迴反組譯單一函式(跟隨 jcc/jmp 到 ret,不跟隨 call)。"""
    out = {}
    stack = [start]
    while stack:
        a = stack.pop()
        while a is not None and a not in out and start <= a < end:
            ins = cg._insn(a)
            if not ins:
                break
            out[a] = ins
            m, op = ins.mnemonic, ins.op_str
            nxt = a + ins.size
            if m in ('ret', 'retn', 'retf'):
                a = None
            elif m == 'jmp':
                a = int(op, 16) if op.startswith('0x') else None
            elif m.startswith('j'):
                if op.startswith('0x'):
                    t = int(op, 16)
                    if start <= t < end and t not in out:
                        stack.append(t)
                a = nxt
            else:
                a = nxt
    return [out[k] for k in sorted(out)]


def selftest():
    """規則:每一筆 PRIM 位址要嘛在現行 EXE 解得開,要嘛列在 KNOWN_STALE 並附理由。

    這是 `dump_chapter_beats` 那一輪的同一個 bug 類別 —— 位址表過期不會報錯,
    只會讓註解安靜地標不出來。差別在於這支有一筆(`0x2cad7`)的現行位址**至今
    未解**,已列在 `docs/data/known_address_errata.json`。所以檢查不能要求「全部
    解得開」(那會逼人去猜),但也不能默許 —— 折衷是明確列管,新的死位址仍會被抓到。

    VAR 那 5 筆是**資料位址**,不是 call 目標,拿呼叫端數判斷是退化檢查;
    改用 fixup map 驗證(第 3 題)。
    """
    import os
    if hasattr(sys.stdout, "reconfigure"):
        sys.stdout.reconfigure(encoding="utf-8")
        sys.stderr.reconfigure(encoding="utf-8")
    fails = []
    root = os.path.dirname(os.path.dirname(os.path.abspath(__file__)))
    exe = os.path.join(root, "org_game", "炎龍騎士團", "FLAME2", "FD2.EXE")
    if not os.path.isfile(exe):
        print("SKIP: 找不到 org_game 的 FD2.EXE")
        return 0
    cg = CG(exe)

    def call_sites(target):
        n = 0
        blob, lo = cg.code, cg.base
        for i in range(len(blob) - 5):
            if blob[i] != 0xE8:
                continue
            rel = int.from_bytes(blob[i + 1:i + 5], "little", signed=True)
            if lo + i + 5 + rel == target:
                n += 1
        return n

    print("(1) 每筆 PRIM 位址:解得開,或已列管為 KNOWN_STALE")
    unlisted = []
    for addr, name in sorted(PRIM.items()):
        n = call_sites(addr)
        if n == 0 and addr not in KNOWN_STALE:
            unlisted.append((hex(addr), name))
    ok1 = not unlisted
    print(f"    {'PASS' if ok1 else 'FAIL'}: {len(PRIM)} 筆,"
          f"未列管的死位址 {unlisted or '無'}")
    if not ok1:
        fails.append(f"新的死位址沒有列管:{unlisted}")

    print("\n(2) KNOWN_STALE 不得腐爛:列管的位址必須**真的**還是死的,且附理由")
    rotten = [hex(a) for a in KNOWN_STALE if call_sites(a) > 0]
    noreason = [hex(a) for a, r in KNOWN_STALE.items() if len(str(r)) < 10]
    ok2 = not rotten and not noreason
    print(f"    {'PASS' if ok2 else 'FAIL'}: {len(KNOWN_STALE)} 筆列管,"
          f"其實已復活 {rotten or '無'}、缺理由 {noreason or '無'}")
    if rotten:
        fails.append(f"列管項目其實已可解:{rotten} —— 應移出 KNOWN_STALE")
    if noreason:
        fails.append(f"列管項目缺理由:{noreason}")

    print("\n(3) 兩筆已知對應的新位址必須真的活著(否則等於換了一個死位址)")
    pairs = [(0x3453E, 0x34894, "raw_record_byte5_bit0"), (0x36CD7, 0x3702F, "__STK")]
    bad = [(hex(o), hex(n)) for o, n, _l in pairs if call_sites(n) == 0]
    ok3 = not bad and all(n in PRIM for _o, n, _l in pairs)
    print(f"    {'PASS' if ok3 else 'FAIL'}: "
          + "、".join(f"{l} {n:#x} 呼叫端 {call_sites(n)}" for _o, n, l in pairs))
    if not ok3:
        fails.append(f"新位址無效或未加入 PRIM:{bad}")

    print("\n(4) VAR 是資料位址:用 fixup map 驗證,不能用呼叫端數(那是退化檢查)")
    fx = fixup_map(cg.d, cg.meta)
    targets = set(fx.values())
    missing = [hex(a) for a in VAR if a not in targets]
    ok4 = not missing
    print(f"    {'PASS' if ok4 else 'FAIL'}: {len(VAR)} 筆,"
          f"不在 fixup target 中的 {missing or '無'}")
    if not ok4:
        fails.append(f"VAR 位址不是任何 fixup 的 target:{missing}")

    print("\n(5) 非恆真控制:一個亂編的位址必須既解不開、也不在 fixup target 裡")
    ok5 = call_sites(0x1234567) == 0 and 0x1234567 not in targets
    print(f"    {'PASS' if ok5 else 'FAIL'}: 亂編位址 0x1234567 -> "
          f"呼叫端 {call_sites(0x1234567)}、在 fixup target={0x1234567 in targets}")
    if not ok5:
        fails.append("亂編的位址竟然通過 —— 上面的檢查沒有鑑別力")

    if fails:
        print("\nSELFTEST FAILED:")
        for f in fails:
            print("  -", f)
        return 1
    print("\n--selftest passed(PRIM 列管規則 + KNOWN_STALE 不腐爛 + 新位址有效 + "
          "VAR 走 fixup + 非恆真控制)。")
    return 0


def main(av):
    if len(av) == 2 and av[1] == '--selftest':
        return selftest()
    if len(av) < 3:
        print(__doc__); return 1
    cg = CG(av[1]); fx = fixup_map(cg.d, cg.meta)
    if av[2] == 'table':
        hs = []
        for i in range(30):
            t = fx.get(0x51b19 + i * 4)
            if t:
                hs.append((i, t))
        uniq = sorted(set(t for _, t in hs))
        by = {}
        for i, t in hs:
            by.setdefault(t, []).append(i)
        for t in uniq:
            end = min([u for u in uniq if u > t] + [t + 0x300])
            chs = by[t]
            tag = '(default raw result rule)' if t == 0x205b4 else ''
            print(f'\n=== handler {hex(t)}  章節 {chs} {tag} ===')
            for ins in dump(cg, fx, t, end):
                m, op = ins.mnemonic, ins.op_str
                keep = m in ('call', 'cmp', 'test') \
                    or (m == 'mov' and ('0x3ec' in op or '0x3a45' in op)) \
                    or (m == 'push' and op.startswith('0x') and not op.startswith('0x5'))
                if keep:
                    print(' ', annot(ins, fx))
        return 0
    if av[2] == 'json':
        import json
        SKIP = {0x36cd7, 0x205be, 0x205da, 0x1088d, 0x111ba, 0x375c0, 0x37416, 0x37244}
        COND = {0x3453e: 'raw_record_byte5_bit0', 0x33499: 'roster_has'}  # 條件查詢原語(非動作)
        # 0x3453e(idx) = ([0x53a45]+idx*0x50+5)&1；高階語意依 caller。
        hs = [(i, fx.get(0x51b19 + i * 4)) for i in range(30)]
        uniq = sorted(set(t for _, t in hs if t))
        cache = {}
        out = []
        for i, t in hs:
            if not t:
                continue
            if t not in cache:
                end = min([u for u in uniq if u > t] + [t + 0x300])
                units, codes, draw, acts, conds = [], [], False, [], []
                lastpush = None
                for ins in dump(cg, fx, t, end):
                    m, op = ins.mnemonic, ins.op_str
                    if m == 'push' and op.startswith('0x'):
                        lastpush = int(op, 16)
                    elif m == 'call' and op.startswith('0x'):
                        tt = int(op, 16)
                        if tt == 0x3453e and lastpush is not None and lastpush < 0x100:
                            units.append(lastpush)
                        elif tt in COND:
                            conds.append(COND[tt])
                        elif tt == 0x15f84:
                            draw = True
                        elif tt not in SKIP:
                            acts.append(hex(tt))
                    elif m == 'mov' and '[0x3ecc],' in op:
                        v = op.split(',')[-1].strip()
                        if v.lstrip('-').isdigit():
                            codes.append(int(v))
                cache[t] = {
                    'handler': hex(t),
                    'is_default': t == 0x205b4,
                    'trigger_units_flag': sorted(set(units)),  # 0x3453e 查的單位 idx(+5 bit0 狀態旗標)
                    'result_codes': sorted(set(codes)),         # raw pending/result codes
                    'draw_scene': draw,                          # 是否繪事件畫面(0x15f84)
                    'extra_conditions': sorted(set(conds)),      # 其他條件查詢原語
                    'action_fns': sorted(set(acts)),             # 真動作函式(經修正後多為空)
                }
            out.append({'chapter': i, **cache[t]})
        print(json.dumps(out, ensure_ascii=False, indent=1))
        return 0
    start = int(av[2], 16)
    end = int(av[3], 16) if len(av) > 3 else start + 0x300
    for ins in dump(cg, fx, start, end):
        print(annot(ins, fx))
    return 0


if __name__ == '__main__':
    sys.exit(main(sys.argv))
