#!/usr/bin/env python3
"""炎龍騎士團2 — 全 30 章「過場/劇情 handler」機械抽取成 beats JSON。

背景(doc47/48/49/50):序章 handler(0x3231b)已人工+機械雙重驗證出完整原語序列
(doc47 §3/§7),原語指令集在全部章節共用,只是參數不同——本工具把這套抽取法
套用到跳表 0x51d71(章節前)、0x51de9(phase-2 戰後)全 30 章 entry,產出機器可讀
beats JSON,供轉換器接手做成 remake cutscene 節點(doc50 §3 管線第 1 步)。

原語表(位址→(op 名, 參數個數)):參數個數 = 該 call 前「最近 N 個 push」,已用序章
handler 實際反組譯逐一核對過 push 順序與 doc47 記法一致(見下方 PRIM 註解)。
cdecl 從右到左 push,故「最近 N 個 push」reverse 後才是函式簽名的左到右參數順序。

未收錄在 PRIM 的呼叫目標(2026-09-09):
  * **參數個數**取自 `derive_native_argcounts`,而且只採信 CONFIRMED;WEAK/LIKELY
    維持原始 push 並標記 `args_are_raw_pushes`,因為猜錯個數比留著原樣更糟。
  * **op 名稱**另走一條獨立的路:`derive_native_argcounts.DOC_OP_NAMES` 只收 repo
    文件裡已反組譯、且引文可逐字定位(位址須在引文 ±3 行內)的名稱,命中時把
    `op` 換掉並附 `op_name_source: doc-anchored`。19 個名稱共命中 84 條 beat,
    unknown 101 -> 17。
  * 兩者**不互相帶動**:`0x22253` 有名稱但參數個數判 LIKELY,args 仍是原始 push。

人工註記(`docs/data/chapter_beats_notes.json`):
  2026-09-06 手寫進已提交 chapter_beats 的 12 條反組譯註記,依 (檔名, 呼叫端位址)
  索引。`all` 匯出時貼回對應 beat;**貼不上就整批丟錯**——重生會整檔覆蓋,沒有這個
  機制,某次重生就會把這些證據安靜刪掉而沒人發現。

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


_ARGC_CACHE: dict[int, int] | None = None


def _confirmed_argc(target: int):
    """未收錄原語的參數個數,只在 derive_native_argcounts 判定 CONFIRMED 時回傳。

    延遲 import 是刻意的:`derive_native_argcounts` 會 import 本檔取 PRIM 與跳表
    位址,模組層互相 import 會成環。整批只算一次。
    """
    global _ARGC_CACHE
    if _ARGC_CACHE is None:
        try:
            import derive_native_argcounts as DA
            cg, _ = DA.build_graph(str(DA.DEFAULT_EXE))
            _ARGC_CACHE = {}
            for t in DA.UNKNOWN_TARGETS:
                d = DA.derive(DA.collect_wide(cg, t))
                if d["verdict"] == "CONFIRMED" and d["argc"] is not None:
                    _ARGC_CACHE[t] = d["argc"]
        except Exception:                                   # noqa: BLE001
            # 推導不可用(例如缺 EXE)時退回原本的行為,不要讓整批抽取失敗。
            _ARGC_CACHE = {}
    return _ARGC_CACHE.get(target)


def _doc_op_name(target: int):
    """未收錄原語的 op 名稱,只在 repo 文件裡有可逐字定位的反組譯記載時回傳。

    名稱與參數個數是**兩種不同的主張**,所以這條路徑與 `_confirmed_argc` 完全獨立:
    有名稱不代表 args 可以切(0x22253 就是有名稱但判定 LIKELY,args 仍保留原始
    push);沒名稱也不影響已經可切的 args。錨點每次都會重驗,文件被改掉就自動失效。
    """
    try:
        import derive_native_argcounts as DA
        return DA.doc_op_name(target)
    except Exception:                                       # noqa: BLE001
        return None


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
                # 2026-09-09:未收錄的原語原本記 `list(pushes)`——**沒有依參數個數
                # 切,也沒有 reversed()**,而上面已收錄的那一支兩件都做了。後果是
                # 同一個檔案裡兩種 beat 的 args 順序相反:cdecl 由右到左 push,所以
                # 未反轉的就是簽名順序的倒序。實測 `0x11d40` 記成 [64, 255, 0],
                # 而 doc 記載的簽名是 `0x11d40(0, 0xff, esi*6)`——**反轉後
                # [0, 255, 64] 才對得上**,這是獨立的佐證,不是推論。101 個 unknown
                # beat 裡有 59 個 args>=2、順序有意義。
                #
                # 參數個數改用 derive_native_argcounts 推導(呼叫端的 `add esp,N`
                # 與緊鄰 push 數兩個獨立訊號,再與 15 個文件簽名核對過),**只採信
                # CONFIRMED 的**;WEAK/LIKELY 維持原本的「全部 push」行為並標記,
                # 因為在那些目標上猜錯個數比留著原樣更糟。
                nargs = _confirmed_argc(t)
                if nargs is None:
                    beat = {'op': 'unknown', 'addr': hex(ins.address),
                            'target': hex(t), 'args': list(pushes),
                            'args_are_raw_pushes': True}
                else:
                    a = pushes[-nargs:] if nargs > 0 else []
                    beat = {'op': 'unknown', 'addr': hex(ins.address),
                            'target': hex(t), 'args': list(reversed(a))}
                # 名稱獨立於參數個數:文件裡有可逐字定位的反組譯記載才換掉 'unknown',
                # 並且一定留下出處,消費端才分得出「原生表收錄的」與「文件錨定的」。
                doc_name = _doc_op_name(t)
                if doc_name:
                    beat['op'] = doc_name
                    beat['op_name_source'] = 'doc-anchored'
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
        # 被跳往的那一臂也必須抵達同一個 merge —— 但**落下去和跳過去一樣算抵達**。
        # 2026-09-09:原本只認顯式 `jmp merge`,於是 ch06_post 整個 diamond 認不出來:
        # 它的 taken 臂結尾是 `0x233b7 add esp,0x24`,下一個位址就是 merge `0x233ba`,
        # 編譯器沒有理由多發一條跳到下一條指令的 jmp。判準比它想測的性質嚴,結果不是
        # 報錯而是靜默降級成扁平 beats——而該章的手工 IR 早就把這個結構寫對了。
        # 收緊的意圖(不要把不相關的提前返回/巢狀分支壓平)仍然保留:落下去只在
        # 最後一條指令**剛好結束於** merge、而且它不是無條件轉移時才算。
        tail = sorted((ins for ins in insns if target_addr <= ins.address < merge_addr),
                      key=lambda x: x.address)
        reaches = any(ins.mnemonic == 'jmp' and ins.op_str == hex(merge_addr)
                      for ins in tail)
        if not reaches and tail:
            last = tail[-1]
            reaches = (last.address + last.size == merge_addr
                       and last.mnemonic not in ('jmp', 'ret', 'retf', 'iret'))
        if not reaches:
            continue

        # 共用 else = 短路條件,單一判準的 `if` 會是**不完整的條件主張**。
        # 2026-09-09,放寬落下去判準後立刻踩到:ch06_post 的 `0x2332a jne 0x23393`
        # 與 `0x23338 jne 0x23393` **跳到同一個位址**——那是 `if (A && B)` 的編譯結果,
        # 兩個判準共用一個 else 臂。只認後面那個 diamond 的話,產出的
        # `if any_unit_inactive([43])` 會斷言「只要 43 號單位還活著就執行」,而真實
        # 條件還要求事件旗標 `[0x3ad5]+0x11 == 1`(該位元組實測由戰鬥事件 handler
        # 以 `mov byte [eax+0x11],1` 設定,共 5 處)。**假的結構比扁平更糟**:扁平
        # 至少看得出有損,假結構會被下游當成完整條件。所以維持扁平,留給
        # 「條件是連接詞」這件事單獨處理。
        if any(ins.mnemonic in ('je', 'jz', 'jne', 'jnz')
               and ins.op_str == hex(target_addr)
               and ins.address < branch.address
               for ins in insns):
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


NOTES_FILE = os.path.join(os.path.dirname(os.path.dirname(os.path.abspath(__file__))),
                          'docs', 'data', 'chapter_beats_notes.json')


def load_notes(path=NOTES_FILE):
    """人工加在 beat 上的反組譯註記,依 (檔名, 呼叫端位址) 索引。

    這些是 2026-09-06 手寫進已提交 chapter_beats 的 RE 證據(例如「`0x24bde` 是
    doc25 `roster_has(id)` 原語的第二個獨立編譯實例」)。重生會覆蓋整個檔案,所以
    註記另外存一份、匯出時貼回去——否則每次重生都會安靜地把證據刪掉。
    """
    if not os.path.exists(path):
        return {}
    with open(path, encoding='utf-8') as f:
        return json.load(f).get('notes', {})


def attach_notes(basename, beats, notes):
    """把註記貼回對應位址的 beat;貼不上就丟錯,不讓註記靜默消失。"""
    want = dict(notes.get(basename, {}))
    for b in walk_beats(beats):
        n = want.pop(b.get('addr'), None)
        if n is not None:
            b['note'] = n
    if want:
        raise KeyError(f"{basename}:註記位址在重生結果裡找不到 {sorted(want)}")
    return beats


def cmd_all(cg, fx, outdir, quiet=False):
    import os
    os.makedirs(outdir, exist_ok=True)
    notes = load_notes()
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
            attach_notes(f'ch{ch:02d}_{tag}.json', data['beats'], notes)
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
# 2026-09-09:doc 錨定的 op 名稱上線後實測 17(101 -> 49 -> 40 -> 17),天花板隨之收緊到 20。
UNKNOWN_CEILING = 20
# 這 19 個名稱在全 30 章實際命中的 beat 數(實測值)。第 (3d) 題用它擋「名稱加了卻
# 一個都沒對上」——那代表位址認錯,而錯名比留 unknown 更糟,正是本項的原始警語。
DOC_NAMED_BEATS = 84
# 2026-09-06 手寫進已提交 chapter_beats 的反組譯註記數(現存於 chapter_beats_notes.json)。
NOTE_COUNT = 12


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

    print("\n(2b) diamond 辨識:落下去抵達 merge 算抵達,但共用 else 必須維持扁平")
    # 兩題成對,缺任一題都會過:
    #   放寬前——只認顯式 `jmp merge`,ch06_post 的 diamond 靜默認不出來(它的 taken
    #   臂結尾 `add esp,0x24` 的下一個位址就是 merge,編譯器不會多發一條 jmp)。
    #   只放寬——ch06_post 會產出 `if any_unit_inactive([43])`,那是**假的結構主張**:
    #   真實條件是 `0x2332a jne 0x23393` 與 `0x23338 jne 0x23393` 兩個判準跳到同一個
    #   else,即短路 AND;外層還要求事件旗標 `[0x3ad5]+0x11 == 1`(該位元組實測由戰鬥
    #   事件 handler 以 `mov byte [eax+0x11],1` 設定,全 image 5 處)。假結構會被下游
    #   當成完整條件,比扁平更糟——扁平至少看得出有損。
    class _I:                                               # noqa: N801
        def __init__(self, a, m, o='', sz=1):
            self.address, self.mnemonic, self.op_str, self.size = a, m, o, sz

    def _stream(extra=()):
        return list(extra) + [
            _I(0x100, 'call', '0x11506'), _I(0x101, 'push', '6'),
            _I(0x102, 'call', '0x34894'), _I(0x103, 'add', 'esp, 4'),
            _I(0x104, 'test', 'eax, eax'), _I(0x105, 'je', '0x120'),
            _I(0x106, 'push', '7'), _I(0x107, 'push', 'dword ptr [0x3a79]'),
            _I(0x108, 'call', '0x15f84'), _I(0x109, 'jmp', '0x140'),
            _I(0x120, 'push', '8'), _I(0x121, 'call', '0x1366a'),
            _I(0x122, 'add', 'esp, 4', 0x1e),               # 剛好結束於 merge 0x140
            _I(0x140, 'call', '0x11506')]

    plain = _stream()
    shared = _stream([_I(0x0f0, 'jne', '0x120')])            # 更早的條件跳,同一個 else
    got_plain = [b['op'] for b in structure_control_flow(plain, extract_beats(plain))]
    got_shared = [b['op'] for b in structure_control_flow(shared, extract_beats(shared))]
    ok2b = 'if' in got_plain and 'if' not in got_shared
    print(f"    {'PASS' if ok2b else 'FAIL'}: 落下去 -> {got_plain}、共用 else -> {got_shared}")
    if not ok2b:
        fails.append(f"diamond 辨識的兩極不成立:落下去={got_plain}、共用 else={got_shared}")

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

    print("\n(3b) 未收錄原語的 args 必須與已收錄的同一套規則:切到參數個數再反轉")
    # 2026-09-09 找到的 bug:已收錄的 op 會 `pushes[-nargs:]` 再 `reversed()`,
    # 未收錄的直接 `list(pushes)`——同一個檔案裡兩種 beat 的 args 順序相反。
    # 驗證錨點不是我自己算的:doc 記載 `0x11d40(0, 0xff, esi*6)`,而修正前記成
    # [64, 255, 0]、修正後是 [0, 255, 64],**反轉後才對得上簽名**。
    argc_11d40 = _confirmed_argc(0x11D40)
    ok3b = argc_11d40 == 3
    print(f"    {'PASS' if ok3b else 'FAIL'}: 0x11d40 推導參數個數 = {argc_11d40}"
          f"(應 3,與 doc 簽名 `0x11d40(0, 0xff, esi*6)` 的三個參數相符)")
    if not ok3b:
        fails.append(f"未收錄原語的參數個數推導失效:0x11d40 -> {argc_11d40}")

    print("\n(3c) 只採信 CONFIRMED:WEAK 的目標必須保留原始 push 並標記")
    # 0x1f882 有合併清理風險(judged WEAK),它的「args」實測是 ebx/esi/edi ——
    # 那是被呼叫端的暫存器保存,不是參數。猜錯個數比留著原樣更糟,所以不動它,
    # 但要標記出來,讓消費端知道那一筆的 args 不是簽名順序。
    weak = _confirmed_argc(0x1F882)
    ok3c = weak is None
    print(f"    {'PASS' if ok3c else 'FAIL'}: 0x1f882(WEAK)-> {weak}(應 None,不採信)")
    if not ok3c:
        fails.append(f"WEAK 的目標被採信了:0x1f882 -> {weak}")

    print("\n(4) unknown 數量不得悄悄變多(天花板 %d)" % UNKNOWN_CEILING)
    import tempfile
    named: dict[str, int] = {}
    raw_push_named = []
    got_notes = 0
    with tempfile.TemporaryDirectory() as td:
        _stats, unknown = cmd_all(cg, fx, td, quiet=True)
        for fn in sorted(os.listdir(td)):
            if not fn.endswith('.json'):
                continue
            with open(os.path.join(td, fn), encoding='utf-8') as fh:
                doc = json.load(fh)
            stack = [doc]
            while stack:
                o = stack.pop()
                if isinstance(o, dict):
                    if o.get('op_name_source') == 'doc-anchored':
                        named[o['op']] = named.get(o['op'], 0) + 1
                        if o.get('args_are_raw_pushes'):
                            raw_push_named.append(o['target'])
                    if 'note' in o and 'addr' in o:
                        got_notes += 1
                    stack.extend(o.values())
                elif isinstance(o, list):
                    stack.extend(o)
    n = sum(unknown.values())
    ok4 = n <= UNKNOWN_CEILING
    print(f"    {'PASS' if ok4 else 'FAIL'}: unknown {n} 個(上限 {UNKNOWN_CEILING})")
    if not ok4:
        fails.append(f"unknown 從 {UNKNOWN_CEILING} 增加到 {n} —— 很可能又有位址表過期")

    print("\n(4b) 每一個 doc 錨定的名稱都必須真的命中,不能加了名稱卻一個都沒對上")
    import derive_native_argcounts as DA
    want_names = {nm for nm, _a, _d, _q in DA.DOC_OP_NAMES.values()}
    missing = sorted(want_names - set(named))
    tot = sum(named.values())
    ok4b = not missing and tot >= DOC_NAMED_BEATS
    print(f"    {'PASS' if ok4b else 'FAIL'}: {len(named)}/{len(want_names)} 個名稱有命中,"
          f"共 {tot} 條 beat(應 >= {DOC_NAMED_BEATS})" + (f",沒命中的 {missing}" if missing else ""))
    if not ok4b:
        fails.append(f"doc 錨定名稱沒有全部命中:missing={missing}、beats={tot}")

    print("\n(4c) 獨立性控制:有名稱**不等於**參數個數可信,兩種主張不得互相帶動")
    # 0x22253 是這條規則的實例:doc31/doc35 反組譯出它的 5 參數 ABI(所以有名稱),
    # 但呼叫端母體擴大後一致度掉到 1.0 以下、判定 LIKELY,所以 args 仍須保留原始
    # push 並標記。若哪天名稱一上去就順手把 args 切了,這一題會失敗。
    ok4c = ('unit_present' in named and _confirmed_argc(0x22253) is None
            and hex(0x22253) in raw_push_named)
    print(f"    {'PASS' if ok4c else 'FAIL'}: 0x22253 有名稱={('unit_present' in named)}、"
          f"參數個數採信={_confirmed_argc(0x22253)}(應 None)、"
          f"args 仍標記為原始 push={hex(0x22253) in raw_push_named}")
    if not ok4c:
        fails.append("名稱與參數個數兩種主張沒有保持獨立(0x22253)")

    print("\n(4d) 人工註記必須全部貼回,而且貼不上要立刻失敗(不能安靜消失)")
    # 12 條 2026-09-06 手寫進已提交檔的 RE 註記。重生會整檔覆蓋,所以它們另存一份;
    # 沒有這一題,某次重生就會把證據刪掉而沒人發現。
    notes = load_notes()
    want_notes = sum(len(v) for v in notes.values())
    ok4d = want_notes >= NOTE_COUNT and got_notes == want_notes
    print(f"    {'PASS' if ok4d else 'FAIL'}: 登錄 {want_notes} 條(應 >= {NOTE_COUNT})、"
          f"實際貼回 {got_notes} 條")
    if not ok4d:
        fails.append(f"人工註記沒有全部貼回:登錄 {want_notes}、貼回 {got_notes}")

    print("\n(4e) 負向控制:註記位址對不上時必須丟錯,而不是默默略過")
    # 沒有這一題,attach_notes 就算整段 pop 寫錯、一條都貼不上,第 (4d) 題也只會看到
    # 「貼回 0 條」而不知道是機制壞了還是登錄檔空的。
    try:
        attach_notes('ch00_pre.json', [{'op': 'x', 'addr': '0x1'}],
                     {'ch00_pre.json': {'0xdeadbeef': '不存在的位址'}})
        ok4e = False
    except KeyError:
        ok4e = True
    print(f"    {'PASS' if ok4e else 'FAIL'}: 對不上的位址{'有' if ok4e else '沒有'}丟錯")
    if not ok4e:
        fails.append("attach_notes 對不上的位址沒有丟錯 —— 註記會安靜消失")

    print("\n(5) 非空控制:必須真的抽出 30 章 × pre/post")
    ok5 = len(_stats) == 60
    print(f"    {'PASS' if ok5 else 'FAIL'}: 抽出 {len(_stats)} 筆(應為 60)")
    if not ok5:
        fails.append(f"只抽出 {len(_stats)} 筆")

    print("\n(6) 重生漂移:全 30 章重生一次,必須與已提交的 chapter_beats 逐檔相同")
    # 2026-09-10 加。突變測試指出三個「可達但無人看管」的判準:切分前綴的
    # `int(beat['addr'],16) < call.address`、迴圈辨識的 `parts[0] != accumulator`、
    # 以及 `test byte [x+5], 1` 的 `parts[1] == '1'`。上面每一題都只驗某個局部性質,
    # 沒有任何一題會因為這三個判準被改而失敗。
    #
    # 實測三者各自都會讓**恰好一個章節檔**的內容改變(ch02_post / ch01_post /
    # ch01_post),所以「重生並逐檔比對」就是能同時釘住三者的最小檢查 ——
    # 而且全 30 章重生只要 1.3 秒,沒有理由不放進 selftest。
    #
    # 這與 `verify_generated_artifacts` 做的是同一個比對,但那是另一支工具的另一個軸;
    # 放在這裡的意義是**讓這支工具自己的 selftest 有能力失敗**,突變測試才量得到它。
    import tempfile as _tf
    from pathlib import Path as _P
    committed = _P(os.path.dirname(os.path.dirname(os.path.abspath(__file__)))) \
        / "docs" / "data" / "chapter_beats"
    drift: list[str] = []
    if not committed.is_dir():
        print("    SKIP: 找不到已提交的 chapter_beats,無法比對(不計為通過)")
    else:
        with _tf.TemporaryDirectory() as td:
            # main() 吃的是完整 sys.argv,argv[0] 是程式名。
            main(["dump_chapter_beats.py", str(DEFAULT_EXE), "all", td])
            for q in sorted(committed.glob("*.json")):
                fresh = _P(td) / q.name
                if not fresh.exists():
                    drift.append(f"{q.name}(重生時沒產生)")
                elif json.loads(fresh.read_text(encoding="utf-8")) != \
                        json.loads(q.read_text(encoding="utf-8")):
                    drift.append(q.name)
        ok6 = not drift
        print(f"    {'PASS' if ok6 else 'FAIL'}: 比對 {len(list(committed.glob('*.json')))} 檔,"
              f"相異 {len(drift)}{'' if ok6 else ' -> ' + str(drift[:5])}")
        if not ok6:
            fails.append(f"重生結果與已提交檔不同:{drift[:5]}")

    if fails:
        print("\nSELFTEST FAILED:")
        for f in fails:
            print("  -", f)
        return 1
    print("\n--selftest passed(位址表可解 + stack-check 在 SKIP + 故障注入 + 未收錄原語的"
          "參數個數與 WEAK 不採信 + unknown 天花板 + doc 錨定名稱的命中率與獨立性控制 + "
          "非空控制 + 全 30 章重生逐檔比對)。")
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
