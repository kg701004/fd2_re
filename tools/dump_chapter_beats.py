#!/usr/bin/env python3
"""炎龍騎士團2 — 全 30 章「過場/劇情 handler」機械抽取成 beats JSON。

背景(doc47/48/49/50):序章 handler(0x3231b)已人工+機械雙重驗證出完整原語序列
(doc47 §3/§7),原語指令集在全部章節共用,只是參數不同——本工具把這套抽取法
套用到跳表 0x51d71(章節前)、0x51de9(phase-2 戰後)全 30 章 entry,產出機器可讀
beats JSON,供轉換器接手做成 remake cutscene 節點(doc50 §3 管線第 1 步)。

原語表(位址→(op 名, 參數個數)):參數個數 = 該 call 前「最近 N 個 push」,已用序章
handler 實際反組譯逐一核對過 push 順序與 doc47 記法一致(見下方 PRIM 註解)。
cdecl 從右到左 push,故「最近 N 個 push」reverse 後才是函式簽名的左到右參數順序。

用法:
  python3 dump_chapter_beats.py <EXE> ch0                  只跑序章(0x3231b),核對 doc47 §7
  python3 dump_chapter_beats.py <EXE> all <outdir>          全 30 章 pre/post,寫 outdir/chNN_{pre,post}.json
  python3 dump_chapter_beats.py <EXE> handler <hex> [end]   單支 handler(除錯用)
"""
import os
import sys
import json

sys.path.insert(0, __file__.rsplit('/', 1)[0])
from callgraph_le import CG, fixup_map

# 2026-09-08:本檔輸出含 cp950 編不出的符號(✓/✗/⚠)。在本機主控台(cp950)下,
# 第一個含該符號的 print 就會 UnicodeEncodeError 崩潰,而且崩得像「工具壞了」
# ——dump_exe_tables.py 與 safe_output.py 都真的因此整支不能用。全 repo 統一作法。
if hasattr(sys.stdout, "reconfigure"):
    sys.stdout.reconfigure(encoding="utf-8")
    sys.stderr.reconfigure(encoding="utf-8")

TABLE_PRE = 0x51d71   # 戰前/劇情 handler 跳表(章節 0~29 索引)
TABLE_POST = 0x51de9  # phase-2 戰後 handler 跳表
N_CHAPTERS = 30
OBJ1_END = 0x4EBD9    # obj1(code)結尾,handler 範圍上限保底(見 le meta objs[0])

# {call target linear: (op名, 參數個數)}。參數個數見上方檔頭說明。
PRIM = {
    0x135dd: ('pan', 2),       # (col,row) — 序章驗證:push(0x22,3)->reversed(3,0x22)=doc47 "(3,0x22)" ✓
    0x15f84: ('dialog', 2),    # (txtptr,idx) — 9 個 push,只取最近 2 個(前 7 個是固定視窗參數,見檔尾附註)
    0x1366a: ('act', 1),       # (id) — doc47 "0x1366a(0x63)" ✓
    0x10b4e: ('spawn', 1),     # (group) — doc47 "0x10b4e(1)" ✓
    0x112a5: ('join', 1),      # (char_id) — 序章尾 0/9/4/0x1e 四連呼 ✓
    0x25977: ('bgm', 2),       # (track,loop?) — push(0,-1)->reversed(-1,0)=doc47 "(-1,0)=停止" ✓
    0x13185: ('scroll_step', 1), # (unit_idx)往上逐格走並視需要跟焦；完整 body 0x13185..0x13314
    0x1f525: ('palfade', 0),   # 無參數；delta 64→0 共65次 0x11d40(0,255,delta)，每次 delay 2ms
    0x375b2: ('delay', 1),     # (ms) — doc47 "0x375b2(200ms)" ✓ **舊版位址**
    0x3790a: ('delay', 1),     # 同一函式在現行參考版的位址(見 EDITION_MOVED)
    0x32975: ('deactivate_unit', 1), # (unit_idx)直接設 unit[+5]=1；原版是死亡／隱藏／未啟用
    0x32999: ('spawn_intro', 1),   # (group)內部 call 0x10b4e 後做 FDOTHER #9 的 12-pass 轉場；acting 由 caller 另行呼叫
    0x134e4: ('reset_pose', 0),    # 所有 materialized units pose=down，然後 delay(20ms)
    0x12d7b: ('focus_unit', 1),    # (unit_idx)讀 unit X/Y，呼叫 0x12cea 捲到該格
    0x11506: ('sync_party', 0),    # 戰後 runtime unit→persistent roster，同 charID copy/清暫態/恢復資源
    0x1c220: ('grant_item', 1),    # (item_id) 掃 camp=2 runtime units，放入首個未滿的 8-slot inventory
    0x233c6: ('layout_units', 0),  # 依 call-site 的 X/Y/pose 陣列佈置單位；由 address-keyed binding script 化
    0x205da: ('loadch_call', 0),  # 章節載入呼叫本身 0 參數;章節號由前面 mov [0x3c03] 設定,見 loadch_var
    # 本輪(2026-07-04)unknown×既有原語表交叉補上(event_handler_dump.py PRIM/VAR + doc25/26):
    0x3453e: ('unit_inactive', 1), # (idx) 查 [0x53a45]+idx*0x50+5 bit0；1=死亡／隱藏，0=有效存活 **舊版位址**
    0x34894: ('unit_inactive', 1), # 同一函式在現行參考版的位址(見 EDITION_MOVED)
    0x33499: ('roster_has', 1),   # (char_id) 查我方名冊 [0x53bf7](doc26 已知)
    0x111ba: ('load_res', 0),     # 載資源(純 fopen/fseek/fread,doc47 §5 已知,參數個數未逐一核對)
    0x25a96: ('play_sfx', 1),     # 播音效(event_handler_dump.py 已知,參數個數未逐一核對)
    0x1088d: ('loadch', 0),      # 完整章節 loader：FDTXT + FDFIELD/roster/map，不是文字-only
    # 先釋放兩個全域輔助圖形緩衝區，再只對 raw chapter
    # 9/17/21–25/27–29 載入或展開章節專用 FDOTHER 資源。它不是完整
    # FDFIELD/FDSHAP 背景 loader；未知 runtime lowering 必須繼續阻擋。
    0x10652: ('prepare_chapter_aux_graphics', 0),
    0x11cac: ('redraw', 1),       # 主重繪函式,每幀呼叫(doc25 已知「每幀呼叫」)
}
# 2026-09-08:上面 PRIM 與下面 SKIP 原本**全部是舊版(357074 B,已遺失)位址**。
# 在現行參考版下它們指向的東西不存在,結果不是報錯,而是靜默降級——該被認出來的
# 原語變成 `op: unknown`,該被跳過的編譯器輔助函式變成一條假 beat。實測整批章節的
# unknown 數 82 → 222(+140),沒有任何錯誤訊息。
#
# 判定方式(每一項都實測過,不是照 delta 換算——delay 移了 0x358、unit_inactive 移了
# 0x356,**位移不是常數**):在現行 EXE 裡數呼叫端。舊位址全部是 0 個呼叫端;
# 新位址 delay=186、unit_inactive=50、stack-check=541。
#
# 對應關係是靠**同一個呼叫點**建立的(章節 handler 裡同一個位置,舊版呼叫舊位址、
# 新版呼叫新位址),不是靠位址算術。
EDITION_MOVED = {
    # op 名 -> (舊版位址, 現行參考版位址)
    'delay':         (0x375b2, 0x3790a),
    'unit_inactive': (0x3453e, 0x34894),
}
UNIT_INACTIVE_OPSTRS = {hex(a) for a in EDITION_MOVED['unit_inactive']}

# 非原語(編譯器插入的堆疊探測/輔助函式),線性掃描時直接跳過、清空 pushes 不記 beat:
# 0x36cd7 / 0x375c0 是舊版位址(現行 EXE 各 0 個呼叫端,保留只為讓舊資料仍可重現);
# 0x3702f 是現行版本的 Watcom stack-check(541 個呼叫端),缺了它每個 handler 的序頭
# 都會被記成一條假 beat。
SKIP = {0x36cd7, 0x375c0, 0x3702f}

# Official IDA Pro 9.4 data xrefs plus Docker Capstone direct-instruction
# validation close every writer of [0x53AFA].  These three chapter-handler
# calls are wrapped by set byte=1 / reset byte=0; every other chapter-handler
# 0x10B4E call reads zero.  Keep this call-site fact in the reproducible raw
# export instead of inferring it from the group number.
RAW_PLACEMENT_GATE_ONE_CALLS = {0x32E50, 0x331B2, 0x33419}


def _direct_target(ins):
    if ins.mnemonic == 'jmp' or ins.mnemonic.startswith('j'):
        if ins.op_str.startswith('0x'):
            return int(ins.op_str, 16)
    return None


def dump_range(cg, start, end, obj_end=OBJ1_END):
    """Walk one handler plus every explicitly reached shared-tail block.

    ``end`` is the next jump-table handler entry, so ordinary fallthrough must
    stop there. Watcom also de-duplicates handler suffixes: a local body can
    jump beyond that boundary (or backwards from a later handler) to a block
    which performs dialog/reset/focus and returns. Earlier extraction discarded
    those reachable blocks. Keep local instructions address-sorted for the
    existing structured-branch recognizer, then append external blocks in CFG
    discovery order so a backwards shared tail still executes after its caller.
    Calls are never followed.
    """
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
    local = [out[k] for k in sorted(out)]
    external = []
    queue = []
    for ins in local:
        target = _direct_target(ins)
        if target is not None and not (start <= target < end):
            queue.append(target)

    # A malformed target must not turn an exporter run into an unbounded code
    # walk. Real shared tails are tiny and terminate in RET/JMP; 4096 decoded
    # instructions is a deliberately generous fail-safe.
    budget = 4096
    while queue and budget > 0:
        a = queue.pop(0)
        while a is not None and a not in out and 0 <= a < obj_end and budget > 0:
            ins = cg._insn(a)
            if not ins:
                break
            out[a] = ins
            external.append(ins)
            budget -= 1
            m = ins.mnemonic
            nxt = a + ins.size
            if m in ('ret', 'retn', 'retf'):
                a = None
            elif m == 'jmp':
                a = _direct_target(ins)
            elif m.startswith('j'):
                target = _direct_target(ins)
                if target is not None and target not in out:
                    queue.append(target)
                a = nxt
            else:
                a = nxt
    return local + external


def _push_value(op):
    """解析 push 的運算元:立即值回傳 int,fixup 變數/暫存器回傳原字串。"""
    if op.startswith('dword ptr ['):
        return op
    try:
        return int(op, 16) if op.lstrip('-').startswith('0x') or op.startswith('-0x') else int(op)
    except ValueError:
        return op


def find_loop_hint(insns, call_idx, call_addr, lookahead=10):
    """best-effort 迴圈偵測:call 後 lookahead 條指令內,若有 jl/jle/jb 跳回早於
    call 的位址,視為「這個 call 在原始碼裡其實是迴圈重複執行」(如 0x13185 的 ×15/×13)。
    回傳 {'loop_back_to':hex, 'limit':int|None},抓不到 limit 就 None——本身是啟發式,
    不保證每章都能命中,命中率與正確性見回報。"""
    n = len(insns)
    for j in range(call_idx + 1, min(call_idx + lookahead, n)):
        m2, op2 = insns[j].mnemonic, insns[j].op_str
        if m2.startswith('j') and m2 != 'jmp' and op2.startswith('0x'):
            tgt = int(op2, 16)
            if tgt <= call_addr:
                limit = None
                for k in range(call_idx + 1, j):
                    mk, opk = insns[k].mnemonic, insns[k].op_str
                    if mk == 'cmp' and ',' in opk:
                        rhs = opk.split(',')[-1].strip()
                        try:
                            limit = int(rhs, 16) if rhs.startswith('0x') else int(rhs)
                        except ValueError:
                            pass
                return {'loop_back_to': hex(tgt), 'limit': limit}
    return None


def extract_beats(insns):
    beats = []
    pushes = []  # list of parsed push values,call 後清空
    for i, ins in enumerate(insns):
        m, op = ins.mnemonic, ins.op_str
        if m == 'push':
            pushes.append(_push_value(op))
        elif m == 'mov' and op.startswith('dword ptr [') and ',' in op:
            lhs, rhs = op.split(',', 1)
            if '0x3c03' in lhs:  # [0x53c03]=章節變數,LOADCH 的隱含參數
                beats.append({'op': 'loadch_var', 'addr': hex(ins.address), 'chapter': rhs.strip()})
        elif m == 'inc' and op.startswith('dword ptr [') and '0x3c03' in op:
            # 戰後 handler 通常以 ++[0x53c03] 推進章節。這是共同 merge
            # 尾的真實動作，不可因為沒有 call 就在 exporter 裡消失。
            beats.append({'op': 'increment_chapter', 'addr': hex(ins.address)})
        elif m == 'call' and op.startswith('0x'):
            t = int(op, 16)
            if t in SKIP:
                pushes = []
                continue
            if t in PRIM:
                name, nargs = PRIM[t]
                args = pushes[-nargs:] if nargs > 0 else []
                args = list(reversed(args))  # cdecl push 順序反過來才是函式簽名順序
                beat = {'op': name, 'addr': hex(ins.address), 'target': hex(t), 'args': args}
                if name in ('spawn', 'spawn_intro'):
                    beat['raw_placement_gate'] = (
                        1 if ins.address in RAW_PLACEMENT_GATE_ONE_CALLS else 0
                    )
            else:
                beat = {'op': 'unknown', 'addr': hex(ins.address), 'target': hex(t), 'args': list(pushes)}
            hint = find_loop_hint(insns, i, ins.address)
            if hint:
                beat['repeat_hint'] = hint
            beats.append(beat)
            pushes = []
    return beats


def _immediate(op):
    """Parse one integer operand, returning None for registers/expressions."""
    try:
        return int(op, 0)
    except (TypeError, ValueError):
        return None


def structure_control_flow(insns, beats):
    """Recover proven fixed-slot ``any inactive`` diamonds into structured IR.

    Watcom emits the ch01 post-battle test as a byte accumulator initialized
    to zero, a counted unit-slot loop testing ``unit+5 bit0``, and finally a
    ``test accumulator`` / ``jne then`` diamond.  Matching the instruction
    shape (rather than a handler address) keeps the recognizer reusable while
    leaving every unproven branch in the existing loss-visible linear output.
    """
    # Single-slot form used by post-battle handlers:
    #
    #   push slot; call unit_inactive; test eax,eax; je active_arm
    #   ... inactive arm ...; jmp merge
    # active_arm:
    #   ... active arm ...; jmp merge
    #
    # Match the reusable CFG/instruction shape, not a handler or branch address.
    # The raw predicate call is absorbed into the structured condition, and the
    # shared merge suffix is emitted once.
    for call_idx, call in enumerate(insns):
        # 2026-09-08:原本硬編 '0x3453e' 這個**舊版**位址,在現行參考版下這個
        # 條件永遠不成立——不會報錯,只是這整段結構化條件的處理靜默不執行。
        # 改成比對 EDITION_MOVED['unit_inactive'] 的整組別名。
        if call.mnemonic != 'call' or call.op_str not in UNIT_INACTIVE_OPSTRS:
            continue

        slot = None
        for previous in reversed(insns[max(0, call_idx - 3):call_idx]):
            if previous.mnemonic == 'push':
                slot = _immediate(previous.op_str)
                break
        if slot is None or slot < 0:
            continue

        test_idx = None
        result_reg = None
        branch_idx = None
        for j in range(call_idx + 1, min(call_idx + 7, len(insns))):
            candidate = insns[j]
            parts = [part.strip() for part in candidate.op_str.split(',')]
            if candidate.mnemonic == 'test' and len(parts) == 2 and parts[0] == parts[1]:
                test_idx, result_reg = j, parts[0]
                continue
            if test_idx is None:
                continue
            if (test_idx is not None and j == test_idx + 1 and
                    candidate.mnemonic in ('je', 'jz', 'jne', 'jnz') and
                    candidate.op_str.startswith('0x')):
                branch_idx = j
            break
        if branch_idx is None or result_reg is None:
            continue

        branch = insns[branch_idx]
        target_addr = int(branch.op_str, 16)
        if target_addr <= branch.address:
            continue

        # The fallthrough arm must explicitly jump past the taken arm.  Require
        # the taken arm to reach the same merge as well, so unrelated early
        # returns or nested branches cannot be flattened accidentally.
        fallthrough_jumps = [
            ins for ins in insns
            if branch.address < ins.address < target_addr and
            ins.mnemonic == 'jmp' and ins.op_str.startswith('0x') and
            int(ins.op_str, 16) > target_addr
        ]
        if not fallthrough_jumps:
            continue
        merge_addr = int(fallthrough_jumps[-1].op_str, 16)
        if not any(ins.mnemonic == 'jmp' and ins.op_str == hex(merge_addr)
                   for ins in insns if target_addr <= ins.address < merge_addr):
            continue

        prefix = [beat for beat in beats if int(beat['addr'], 16) < call.address]
        fallthrough = [beat for beat in beats
                       if branch.address < int(beat['addr'], 16) < target_addr]
        taken = [beat for beat in beats
                 if target_addr <= int(beat['addr'], 16) < merge_addr]
        suffix = [beat for beat in beats if int(beat['addr'], 16) >= merge_addr]
        if not fallthrough or not taken:
            continue

        # JE/JZ takes the zero (=active) arm, so inactive is fallthrough.  JNE/JNZ
        # takes the nonzero (=inactive) arm and therefore reverses the two lists.
        if branch.mnemonic in ('je', 'jz'):
            inactive, active = fallthrough, taken
        else:
            inactive, active = taken, fallthrough
        conditional = {
            'op': 'if',
            'addr': hex(branch.address),
            'target': hex(target_addr),
            'condition': {
                'op': 'any_unit_inactive',
                'unit_slots': [slot],
            },
            'then': inactive,
            'else': active,
        }
        return prefix + [conditional] + suffix

    for i in range(2, len(insns)):
        branch = insns[i]
        if branch.mnemonic not in ('jne', 'jnz') or not branch.op_str.startswith('0x'):
            continue
        movzx, test_result = insns[i - 2], insns[i - 1]
        if movzx.mnemonic != 'movzx' or test_result.mnemonic != 'test':
            continue
        mov_parts = [part.strip() for part in movzx.op_str.split(',')]
        test_parts = [part.strip() for part in test_result.op_str.split(',')]
        if len(mov_parts) != 2 or test_parts != [mov_parts[0], mov_parts[0]]:
            continue
        accumulator = mov_parts[1]

        start_idx = None
        counter = None
        start_slot = None
        end_slot = None
        saw_inactive_test = False
        saw_accumulator_set = False
        for j in range(max(0, i - 48), i - 1):
            ins = insns[j]
            parts = [part.strip() for part in ins.op_str.split(',')]
            if ins.mnemonic == 'xor' and parts == [accumulator, accumulator]:
                start_idx = j
            elif start_idx is not None and ins.mnemonic == 'mov' and len(parts) == 2:
                value = _immediate(parts[1])
                if value is not None and parts[0] != accumulator and counter is None:
                    counter, start_slot = parts[0], value
                if parts == [accumulator, '1']:
                    saw_accumulator_set = True
            elif (start_idx is not None and counter is not None and
                  ins.mnemonic == 'cmp' and len(parts) == 2 and parts[0] == counter):
                end_slot = _immediate(parts[1])
            elif (start_idx is not None and ins.mnemonic == 'test' and len(parts) == 2 and
                  parts[0].startswith('byte ptr [') and '+ 5]' in parts[0] and parts[1] == '1'):
                saw_inactive_test = True
        if (start_idx is None or counter is None or start_slot is None or end_slot is None or
                start_slot < 0 or end_slot <= start_slot or not saw_inactive_test or
                not saw_accumulator_set):
            continue
        if not any(ins.mnemonic == 'inc' and ins.op_str == counter
                   for ins in insns[start_idx:i]):
            continue

        then_addr = int(branch.op_str, 16)
        false_jump = None
        merge_addr = None
        for ins in insns[i + 1:]:
            if ins.address >= then_addr:
                break
            if ins.mnemonic == 'jmp' and ins.op_str.startswith('0x'):
                target = int(ins.op_str, 16)
                if target > then_addr:
                    false_jump, merge_addr = ins.address, target
        if false_jump is None or merge_addr is None:
            continue

        prefix = [beat for beat in beats if int(beat['addr'], 16) < branch.address]
        otherwise = [beat for beat in beats
                     if branch.address < int(beat['addr'], 16) < then_addr]
        matched = [beat for beat in beats
                   if then_addr <= int(beat['addr'], 16) < merge_addr]
        suffix = [beat for beat in beats if int(beat['addr'], 16) >= merge_addr]
        if not otherwise or not matched:
            continue
        conditional = {
            'op': 'if',
            'addr': hex(branch.address),
            'target': hex(then_addr),
            'condition': {
                'op': 'any_unit_inactive',
                'unit_slots': list(range(start_slot, end_slot)),
            },
            'then': matched,
            'else': otherwise,
        }
        return prefix + [conditional] + suffix
    return beats


def walk_beats(beats):
    """Yield structured raw beats recursively for statistics/diagnostics."""
    for beat in beats:
        yield beat
        if beat.get('op') == 'if':
            yield from walk_beats(beat.get('then', []))
            yield from walk_beats(beat.get('else', []))


def resolve_table(fx, table_addr, n):
    """跳表[i] = fx.get(table_addr + i*4);回傳 [(chapter, handler_addr)]。"""
    out = []
    for i in range(n):
        t = fx.get(table_addr + i * 4)
        if t:
            out.append((i, t))
    return out


def handler_beats(cg, fx, entries, uniq_sorted, obj_end):
    """entries: [(chapter, handler_addr)];回傳 {chapter: beats_list},handler 結果快取共用。"""
    cache = {}
    out = {}
    for ch, h in entries:
        if h not in cache:
            later = [u for u in uniq_sorted if u > h]
            end = min(later) if later else obj_end
            insns = dump_range(cg, h, end)
            cache[h] = structure_control_flow(insns, extract_beats(insns))
        out[ch] = {'handler': hex(h), 'beats': cache[h]}
    return out


def cmd_ch0(cg, fx):
    """只跑序章(戰前跳表 entry 0),核對 doc47 §7 的 73-call 序列。"""
    entries = resolve_table(fx, TABLE_PRE, N_CHAPTERS)
    uniq = sorted(set(h for _, h in entries))
    result = handler_beats(cg, fx, [entries[0]], uniq, OBJ1_END)
    ch0 = result[0]
    print(f"序章 handler = {ch0['handler']}")
    print(f"beats 總數 = {len(ch0['beats'])}")
    call_beats = [b for b in ch0['beats'] if b['op'] != 'loadch_var']
    print(f"call 類 beats(排除 loadch_var 這種純 mov 記錄) = {len(call_beats)}")
    unknown = [b for b in ch0['beats'] if b['op'] == 'unknown']
    print(f"unknown 原語數 = {len(unknown)}: {sorted(set(b['target'] for b in unknown))}")
    print()
    for b in ch0['beats']:
        print(' ', json.dumps(b, ensure_ascii=False))
    return ch0


def cmd_handler(cg, fx, start, end):
    insns = dump_range(cg, start, end)
    for b in structure_control_flow(insns, extract_beats(insns)):
        print(json.dumps(b, ensure_ascii=False))


def cmd_all(cg, fx, outdir, quiet=False):
    import os
    os.makedirs(outdir, exist_ok=True)
    pre_entries = resolve_table(fx, TABLE_PRE, N_CHAPTERS)
    post_entries = resolve_table(fx, TABLE_POST, N_CHAPTERS)
    pre_uniq = sorted(set(h for _, h in pre_entries))
    post_uniq = sorted(set(h for _, h in post_entries))
    pre = handler_beats(cg, fx, pre_entries, pre_uniq, OBJ1_END)
    post = handler_beats(cg, fx, post_entries, post_uniq, OBJ1_END)

    stats = []
    all_unknown = {}
    for ch in range(N_CHAPTERS):
        for tag, table in (('pre', pre), ('post', post)):
            if ch not in table:
                continue
            data = table[ch]
            path = os.path.join(outdir, f'ch{ch:02d}_{tag}.json')
            with open(path, 'w', encoding='utf-8') as f:
                json.dump(data, f, ensure_ascii=False, indent=1)
            ops = {}
            for b in walk_beats(data['beats']):
                ops[b['op']] = ops.get(b['op'], 0) + 1
            for b in walk_beats(data['beats']):
                if b['op'] == 'unknown':
                    all_unknown.setdefault(b['target'], 0)
                    all_unknown[b['target']] += 1
            stats.append({'chapter': ch, 'tag': tag, 'handler': data['handler'],
                           'n_beats': len(data['beats']), 'ops': ops})

    with open(os.path.join(outdir, '_stats.json'), 'w', encoding='utf-8') as f:
        json.dump({'per_chapter': stats, 'unknown_targets': all_unknown}, f, ensure_ascii=False, indent=1)

    if not quiet:
        print(f"寫出 {len(stats)} 個 chNN_{{pre,post}}.json 到 {outdir}")
        print(f"unknown 原語(位址→出現次數,依次數排序):")
        for addr, cnt in sorted(all_unknown.items(), key=lambda kv: -kv[1]):
            print(f"  {addr}: {cnt}")
    return stats, all_unknown


DEFAULT_EXE = os.path.join(os.path.dirname(os.path.dirname(os.path.abspath(__file__))),
                           'org_game', '炎龍騎士團', 'FLAME2', 'FD2.EXE')
# 2026-09-08 實測值(修好位址表之後)。這是天花板不是目標:允許往下,不允許悄悄變多。
UNKNOWN_CEILING = 110


def resolvable(cg, addr):
    """這個位址在**當前這份 EXE** 裡有沒有人呼叫。

    位址表過期不會報錯,只會靜默降級(認得的原語變 unknown、該跳過的變假 beat)。
    唯一可靠的訊號就是「現行 image 裡有沒有 call 指到它」——舊位址一律 0。
    """
    n = 0
    for lo, blob in ((cg.base, cg.code),):
        for i in range(len(blob) - 5):
            if blob[i] != 0xE8:
                continue
            rel = int.from_bytes(blob[i + 1:i + 5], 'little', signed=True)
            if lo + i + 5 + rel == addr:
                n += 1
    return n


def selftest():
    fails = []
    cg = CG(DEFAULT_EXE)
    fx = fixup_map(cg.d, cg.meta)

    print("(1) 位址表必須在當前 EXE 裡解得開 —— 過期不會報錯,只會靜默降級")
    dead_prim = sorted(a for a in PRIM if resolvable(cg, a) == 0)
    dead_skip = sorted(a for a in SKIP if resolvable(cg, a) == 0)
    # 舊版位址刻意保留(讓舊資料仍可重現),所以只要求「每個 op 至少有一個活的位址」。
    live_ops = {}
    for a, (op, _n) in PRIM.items():
        live_ops[op] = live_ops.get(op, False) or resolvable(cg, a) > 0
    starved = sorted(op for op, live in live_ops.items() if not live)
    ok1 = not starved
    print(f"    {'PASS' if ok1 else 'FAIL'}: {len(live_ops)} 個 op,完全解不開的 {starved or '無'}")
    print(f"    (參考:PRIM 中 {len(dead_prim)} 個舊版位址、SKIP 中 {len(dead_skip)} 個,"
          f"皆為刻意保留)")
    if not ok1:
        fails.append(f"這些 op 在當前 EXE 完全沒有可用位址:{starved}")

    print("\n(2) stack-check 必須在 SKIP 裡,否則每個 handler 序頭都會變成一條假 beat")
    sc = [a for a in SKIP if resolvable(cg, a) > 100]
    ok2 = bool(sc)
    print(f"    {'PASS' if ok2 else 'FAIL'}: SKIP 中高呼叫量(>100)的項目 {[hex(a) for a in sc]}")
    if not ok2:
        fails.append("SKIP 裡沒有任何一個看起來像 stack-check 的項目")

    print("\n(3) 故障注入:把某個 op 的所有位址換成解不開的,第 (1) 項必須失敗")
    keep = dict(PRIM)
    try:
        for a, (op, n) in list(PRIM.items()):
            if op == 'delay':
                del PRIM[a]
        PRIM[0xDEAD00] = ('delay', 1)
        live = any(resolvable(cg, a) > 0 for a, (op, _) in PRIM.items() if op == 'delay')
        ok3 = not live
        print(f"    {'PASS' if ok3 else 'FAIL'}: 注入後 delay 仍有可用位址={live}(應為 False)")
        if not ok3:
            fails.append("故障注入沒有生效,第 (1) 項是白過的")
    finally:
        PRIM.clear()
        PRIM.update(keep)

    print("\n(4) unknown 數量不得悄悄變多(天花板 %d)" % UNKNOWN_CEILING)
    import tempfile
    with tempfile.TemporaryDirectory() as td:
        _stats, unknown = cmd_all(cg, fx, td, quiet=True)
    n = sum(unknown.values())
    ok4 = n <= UNKNOWN_CEILING
    print(f"    {'PASS' if ok4 else 'FAIL'}: unknown {n} 個(上限 {UNKNOWN_CEILING})")
    if not ok4:
        fails.append(f"unknown 從 {UNKNOWN_CEILING} 增加到 {n} —— 很可能又有位址表過期")

    print("\n(5) 非空控制:必須真的抽出 30 章 × pre/post")
    ok5 = len(_stats) == 60
    print(f"    {'PASS' if ok5 else 'FAIL'}: 抽出 {len(_stats)} 筆(應為 60)")
    if not ok5:
        fails.append(f"只抽出 {len(_stats)} 筆")

    if fails:
        print("\nSELFTEST FAILED:")
        for f in fails:
            print("  -", f)
        return 1
    print("\n--selftest passed(位址表可解 + stack-check 在 SKIP + 故障注入 + "
          "unknown 天花板 + 非空控制)。")
    return 0


def main(argv):
    if len(argv) == 2 and argv[1] == '--selftest':
        return selftest()
    if len(argv) < 3:
        print(__doc__)
        return 1
    exe = argv[1]
    cg = CG(exe)
    fx = fixup_map(cg.d, cg.meta)
    cmd = argv[2]
    if cmd == 'ch0':
        cmd_ch0(cg, fx)
    elif cmd == 'handler':
        start = int(argv[3], 16)
        end = int(argv[4], 16) if len(argv) > 4 else start + 0x2000
        cmd_handler(cg, fx, start, end)
    elif cmd == 'all':
        outdir = argv[3] if len(argv) > 3 else 'docs/data/chapter_beats'
        cmd_all(cg, fx, outdir)
    else:
        print(__doc__)
        return 1
    return 0


if __name__ == '__main__':
    sys.exit(main(sys.argv))
