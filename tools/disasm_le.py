#!/usr/bin/env python3
"""炎龍騎士團2 — DOS4GW LE(32-bit flat)反組譯器(capstone)。

LE obj1 = code,base=0x10000(linear)。本工具把 linear 位址範圍反組譯成
帶位址的 x86-32 組語,並標出每條指令觸及的 fixup target(資料/字串/呼叫的絕對位址),
方便做控制流追蹤與 sink→caller 反向溯源(規則 62)。

linear ↔ file:**必須逐 object 換算**(2026-09-08 修正)。
  file = data_off + (obj.first - 1) * page_size + (linear - obj.base)

  舊版說明寫 `file = data_off + (linear - 0x10000)`,那只對 object 1 成立。
  object 2(base 0x50000)偏 0x1000、object 3(base 0x60000)偏 0xD000 ——
  後者甚至讀到檔案結尾之外。**只影響資料段**;程式碼段(obj1)新舊公式等價。

fixup 表同樣**必須走完全部 object**(2026-09-11 修正)。`build_fixups` 原本寫死
只走 obj1 的頁,所以 `refs` 對任何**存放在資料段**的參照一律回**空結果** ——
本專案的間接跳表(`0x51b91`/`0x51d01`)全在 obj2,實測 412 筆 fixup 完全看不見,
「這四個函式沒有呼叫端」這個錯誤結論差點因此成立。空結果與「確實沒有」在輸出上
一模一樣,所以判斷絕對不能只看 `refs` 印不印得出東西:用一個**已知存在**的參照當
對照組(`refs 0x35854` 必須報 `0x51c79`),這一條現在釘在 selftest 第 (6) 題。

用法:
  python3 disasm_le.py <FD2.EXE> dis <linear_hex> [count]      反組譯 count 條指令
  python3 disasm_le.py <FD2.EXE> range <start_hex> <end_hex>   反組譯 linear 範圍
  python3 disasm_le.py <FD2.EXE> calls <target_hex>            找對 target 的相對 call/jmp 來源(linear)
  python3 disasm_le.py <FD2.EXE> refs <abs_hex>                找**全部 object** 中被 fixup 成 abs 的位置(xref)
  python3 disasm_le.py <FD2.EXE> data <linear_hex> <length>   印出同一 LE object 的 raw bytes/ASCII
"""
import hashlib
import os
import sys

# 2026-09-08:本檔的 docstring 含 cp950 編不出的字元(如 ↔),而無參數時會
# `print(__doc__)` —— 在本機 cp950 主控台上那一行直接 UnicodeEncodeError,
# 看起來像「工具壞了」。原本的偵測器只看 print 的字面字串,看不到這條路徑。
if hasattr(sys.stdout, "reconfigure"):
    sys.stdout.reconfigure(encoding="utf-8")
    sys.stderr.reconfigure(encoding="utf-8")
sys.path.insert(0, __file__.rsplit('/', 1)[0])
from le_xref import file_to_linear, parse_fixups, parse_le

# capstone 只有反組譯路徑需要,**匯入時不要求**。本檔的 `load_code`/`build_fixups`
# 是純位元組/fixup 操作,已被 `derive_ail_entry_points.py` 這類不反組譯的工具重用;
# 模組層 `sys.exit` 會讓那些工具在沒有 capstone 的直譯器(例如 WSL python3,正是
# `verify_everything` 的 wsl 軸所用)上整個掛掉,而它們根本不需要這個相依。
def _capstone():
    try:
        from capstone import Cs, CS_ARCH_X86, CS_MODE_32
    except ImportError:
        sys.exit("need capstone: run under docker uv (見 README)")
    return Cs(CS_ARCH_X86, CS_MODE_32)

CODE_BASE = 0x10000


def lin2file(meta, lin):
    """linear 位址 → 檔案位移。**必須逐 object 換算**,不能只用 obj1 的公式。

    2026-09-08 修正。原本寫死 `data_off + (lin - CODE_BASE)`,那只對 object 1
    成立(base 0x10000、first page 1)。object 2(base 0x50000、first page 64)
    與 object 3(base 0x60000、first page 68)各自有不同的頁起點,舊公式會:

        0x51b91 / 0x5274e (obj2)  偏 +0x1000 → 讀到全 0,不是真的表格位元組
        0x620a1           (obj3)  偏 +0xD000 → **直接讀到檔案結尾之外**

    **範圍限定(2026-09-08 自我更正)**:這**不是**既有記錄
    [[feedback_fd2_disasm_le_range_bug]](2026-08-14,症狀位址 `0x13a9f`)的根因。
    那個位址在 object 1,而新舊公式對 obj1 **完全等價**(實測整個 obj1 範圍內
    兩者差異位址數 = 0),所以本次修正在數學上不可能改變它。那個症狀是
    2026-09-03 的 `55988977`(le_xref 的 page mapping)修好的。
    本次修的是**另一個、只影響資料段的獨立 bug**。

    正確公式與 callgraph_le.page_base_linear / le_xref 的換算一致:
        data_off + (obj.first - 1) * page_size + (lin - obj.base)
    """
    for o in meta['objs']:
        if o['base'] <= lin < o['base'] + o['vsize']:
            return (meta['data_off'] + (o['first'] - 1) * meta['page_size']
                    + lin - o['base'])
    raise ValueError(f"linear 位址 {lin:#x} 不落在任何 object 內")


def load_code(d, meta):
    o = meta['objs'][0]
    start = lin2file(meta, o['base'])
    return d[start:start + o['vsize']], o['base']


def resync_sweep(md, code, base):
    """線性掃描整段 code;capstone 遇到無法解碼的位元組時跳 1 byte 接著掃。

    回傳 (指令清單, 續掃點 linear 清單)。

    2026-10-28 修正(續一百六十一):`md.disasm()` 碰到第一個無法解碼的位元組就
    **整個停下**,不報錯。FD2.EXE 的 obj1 程式碼到 0x4ef29,單次掃描卻停在
    0x3cae4,後段約 75 KB(AIL 計時與音效驅動全在這裡)的呼叫端因此一律找不到,
    `calls` 回的空結果與「確實沒有呼叫端」長得一模一樣。實測全段共 42 個續掃點。
    """
    insns, stops = [], []
    for x in sweep_range(md, code, base, base, base + len(code)):
        if isinstance(x, tuple):
            stops.append(x[0])
        else:
            insns.append(x)
    return insns, stops


def sweep_range(md, code, base, start, end):
    """線性反組譯 linear [start, end);capstone 停下的位置產生 `(linear, byte)` 後跳 1 byte 續掃。

    產出 capstone 指令,或 `(linear, byte)` 表示該位址無法解碼。起點在 end 之前的指令整條產出
    (可以跨過 end)。`resync_sweep`(calls)與 `range_lines`(dis / range)共用這一套續掃。
    """
    lim = min(end, base + len(code)) - base
    off = start - base
    while off < lim:
        nxt = off
        for insn in md.disasm(code[off:], base + off):
            if insn.address - base >= lim:
                return
            yield insn
            nxt = insn.address + insn.size - base
        if nxt >= lim:
            return
        yield (base + nxt, code[nxt])
        off = nxt + 1


def range_lines(md, code, base, fx, start, end, cnt):
    """`dis` / `range` 的輸出行;回傳 (行清單, 無法解碼的位元組數)。`cnt` 只算指令。

    2026-10-29 續一百六十二:原本直接 `md.disasm()`,碰到第一個無法解碼的位元組就安靜停下
    (`range 0x10000 0x50000` 停在 0x3cae3,後段約 75 KB 沒印也沒提示)。改用 `sweep_range`:
    無法解碼的位元組印成 `db` 行,跳 1 byte 續掃。
    """
    out, bad, n = [], 0, 0
    for x in sweep_range(md, code, base, start, end):
        if isinstance(x, tuple):
            out.append(f'{x[0]:#08x}  {"db":<7} {x[1]:#04x}  ; 無法解碼,跳 1 byte 續掃')
            bad += 1
            continue
        tgt = ''
        for o2 in range(x.address, x.address + x.size):
            if o2 in fx:
                tgt = f'  ; ->{hex(fx[o2])}'
                break
        out.append(f'{x.address:#08x}  {x.mnemonic:<7} {x.op_str}{tgt}'.rstrip())
        n += 1
        if n >= cnt:
            break
    return out, bad


def find_rel_callers(md, code, base, tgt):
    """找 call/jmp 立即數目標 == tgt 的指令。

    回傳 ([(linear, 助記符, 運算元, 對齊)], 續掃點)。`對齊` 為 False 表示線性掃描
    在該處錯位、只有 E8/E9 rel32 位元組掃描命中:續掃後全段仍有 8 條這種邊
    (例如 0x4d68c `ret` + 兩個 00 填充後的 `jmp 0x4dc3a`,掃描把 00 E9 讀成
    `add cl, ch`)。位元組掃描在資料區可能誤中,所以另外標出,不混進對齊結果。
    """
    insns, stops = resync_sweep(md, code, base)
    hits = []
    for insn in insns:
        if insn.mnemonic in ('call', 'jmp') and insn.op_str.startswith('0x'):
            try:
                if int(insn.op_str, 16) == tgt:
                    hits.append((insn.address, insn.mnemonic, insn.op_str, True))
            except ValueError:
                pass
    seen = {h[0] for h in hits}
    for off in range(len(code) - 4):
        if code[off] in (0xE8, 0xE9) and base + off not in seen:
            rel = int.from_bytes(code[off + 1:off + 5], 'little', signed=True)
            if base + off + 5 + rel == tgt:
                hits.append((base + off, 'call' if code[off] == 0xE8 else 'jmp', hex(tgt), False))
    hits.sort()
    return hits, stops


def object_bytes(d, meta, start, length):
    """LE-linear 位址範圍 -> raw bytes,**逐 object 換算**(不可套 obj1 的公式)。

    2026-09-11 從 `dump_data` 抽出:`derive_ail_entry_points.py` 與
    `verify_event_dispatch_table.py` 都要讀 obj2 的資料表,先前各自複製了同一段
    位移計算。抽出來之後只有這一份,而且受本檔 --selftest 的資料段錨點回歸保護。
    """
    if length < 0 or length > 0x10000:
        raise ValueError("length must be in 0..0x10000")
    obj = next((o for o in meta['objs'] if o['base'] <= start and start + length <= o['base'] + o['vsize']), None)
    if obj is None:
        raise ValueError("range outside one LE object")
    foff = meta['data_off'] + (obj['first'] - 1) * meta['page_size'] + (start - obj['base'])
    return d[foff:foff + length]


def dump_data(d, meta, start, length):
    """Print a bounded, reproducible LE-linear hexdump for data/table RE."""
    raw = object_bytes(d, meta, start, length)
    for i in range(0, len(raw), 16):
        row = raw[i:i + 16]
        hexes = " ".join(f"{b:02x}" for b in row)
        text = "".join(chr(b) if 0x20 <= b < 0x7f else "." for b in row)
        print(f"{start + i:#08x}  {hexes:<47}  |{text}|")


def page_owner(meta, pg):
    """0-based 全域頁號 -> (物件, 該頁的 linear 起點);不屬於任何物件則回 (None, None)。

    LE 的 fixup page table 是**整個映像**的頁號索引(1-based),不是每個物件各自從 0 起算。
    物件 N 佔 `first .. first+pages-1` 這段全域頁號。
    """
    for obj in meta['objs']:
        lo = obj['first'] - 1
        if lo <= pg < lo + obj['pages']:
            return obj, obj['base'] + (pg - lo) * meta['page_size']
    return None, None


def object_index(meta, lin):
    """linear 位址落在第幾個 object(1-based);不在任何 object 內回 None。"""
    for k, o in enumerate(meta['objs'], 1):
        if o['base'] <= lin < o['base'] + o['vsize']:
            return k
    return None


def total_pages(meta):
    return sum(o['pages'] for o in meta['objs'])


def build_fixups(d, meta, objects=None):
    """回傳 {src_linear: target_abs} —— 每個被 patch 的位置→其絕對 target。

    `objects` 為 None 時走**全部物件**;給一個 1-based 物件編號集合則只走那些。

    2026-09-11 修正:這裡原本寫死 `npages = meta['objs'][0]['pages']`、
    `page_lin = CODE_BASE + pg * page_size`,也就是**只走 object 1(程式碼段)**。
    後果不是報錯,是 `refs` 對任何存放在資料段的參照回傳**空結果**——本專案的
    間接跳表(`0x51b91`/`0x51d01`)全在 obj2,實測曾讓「這四個函式沒有呼叫端」
    這個結論差點成立。空結果與「確實沒有」在輸出上長得一模一樣。
    對照組見 selftest 第 (3) 題:`0x35854` 已知登記在 `0x51c79`,必須掃得到。

    2026-10-28(續一百六十一):記錄解析改由 `le_xref.parse_fixups` 做。本檔原本另有一份手寫解析器,
    16 位元物件編號(flag 0x40)的兩個分支一模一樣、外部目標(EXT_ORD / EXT_NAME)與清單型記錄都不處理;
    le_xref 那份 2026-08-14 已對照 Open Watcom 的 wdfix.c 修正。改之前在 FD2.EXE 上逐筆比過:
    objects = None / {1} / {2} / {3} / {1, 2} 分別 7948 / 7536 / 285 / 127 / 7821 筆,全部相同。
    """
    fx = {}
    for f, tgt in parse_fixups(d, meta).items():
        lin = file_to_linear(meta, f)
        if lin is None:
            continue
        if objects is not None and object_index(meta, lin) not in objects:
            continue
        fx[lin] = tgt
    return fx


def selftest():
    """釘住 lin2file 的逐 object 換算 —— 這支剛修好一個會安靜讀錯段的 bug。

    第 (2) 題是**跨工具對照**:與 callgraph_le / le_xref 用的同一條逐 object
    公式逐位址比對,而不是拿本檔自己的實作驗自己。
    """
    import os
    fails = []
    root = os.path.dirname(os.path.dirname(os.path.abspath(__file__)))
    exe = os.path.join(root, "org_game", "炎龍騎士團", "FLAME2", "FD2.EXE")
    if not os.path.isfile(exe):
        print("SKIP: 找不到 org_game 的 FD2.EXE")
        return 0
    d = open(exe, "rb").read()
    meta = parse_le(d)

    print("(1) 回歸:資料段的已知錨點必須讀出正確位元組,而不是全 0 或越界")
    for label, lin, want in (
            ("跳表 0x51b91 index 58(obj2)", 0x51B91 + 58 * 4, "54580200"),
            ("寶物表 0x5274e(obj2)", 0x5274E, "1d2b333d"),
            ("成長表 0x620a1(obj3)", 0x620A1, "06080406"),
            ("程式碼 0x35854 序頭(obj1)", 0x35854, "68440000")):
        off = lin2file(meta, lin)
        got = d[off:off + 4].hex() if 0 <= off < len(d) else "越界"
        ok = got == want
        print(f"    {'PASS' if ok else 'FAIL'}: {label} -> file+{off:#x} = {got}"
              + ("" if ok else f"(預期 {want})"))
        if not ok:
            fails.append(f"{label}: {got} != {want}")

    print("\n(2) 跨工具對照:與 callgraph_le/le_xref 的逐 object 公式逐位址一致")
    def reference(lin):
        for o in meta["objs"]:
            if o["base"] <= lin < o["base"] + o["vsize"]:
                return (meta["data_off"] + (o["first"] - 1) * meta["page_size"]
                        + lin - o["base"])
        return None
    bad = [hex(lin) for o in meta["objs"]
           for lin in (o["base"], o["base"] + 1, o["base"] + o["vsize"] - 1,
                       o["base"] + o["vsize"] // 2)
           if lin2file(meta, lin) != reference(lin)]
    ok2 = not bad
    print(f"    {'PASS' if ok2 else 'FAIL'}: {len(meta['objs'])} 個 object × 4 個位址"
          + ("全部一致" if ok2 else f",不符 {bad}"))
    if bad:
        fails.append(f"與參考換算不一致:{bad}")

    print("\n(3) 不在任何 object 內的位址必須丟錯,不能算出看似合理的位移")
    for lin in (0x0, 0x4FFFF, 0x70000):
        try:
            got = lin2file(meta, lin)
            print(f"    FAIL: {lin:#x} 沒有被擋下,算出 {got:#x}")
            fails.append(f"{lin:#x} 沒有被擋下")
        except ValueError:
            print(f"    PASS: {lin:#x} -> ValueError")

    print("\n(4) 非恆真控制:各 object 的換算基準必須互不相同")
    # 若三個 object 用同一個基準,就等於又退回舊的單一公式。
    bases = {o["base"]: lin2file(meta, o["base"]) - o["base"] for o in meta["objs"]}
    ok4 = len(set(bases.values())) == len(meta["objs"])
    print(f"    {'PASS' if ok4 else 'FAIL'}: {[hex(v) for v in bases.values()]}")
    if not ok4:
        fails.append("各 object 換算基準相同 —— 逐 object 換算沒有生效")

    print("\n(5) fixup 表必須走完**全部** object,不能只走 object 1")
    # 這題是為一個會安靜回空結果的缺陷設的:`refs` 建在 build_fixups 上,而它
    # 原本寫死只走 obj1 的頁,所以任何**存放在資料段**的參照都掃不到。空結果
    # 與「確實沒有」在輸出上一模一樣,實測差點讓「這四個函式沒有呼叫端」成立。
    fx_all = build_fixups(d, meta)
    fx_o1 = build_fixups(d, meta, objects={1})
    pages_seen = total_pages(meta)
    ok5a = pages_seen == sum(o["pages"] for o in meta["objs"]) and len(fx_all) > len(fx_o1)
    print(f"    {'PASS' if ok5a else 'FAIL'}: 全域頁數 {pages_seen},"
          f"fixup 全物件 {len(fx_all)} > 只 obj1 {len(fx_o1)}")
    if not ok5a:
        fails.append(f"fixup 沒有走完全部 object:{len(fx_all)} vs {len(fx_o1)}")

    print("\n(6) 已知真值 + 配對的負向控制:0x35854 必須掃得到、且該證據只在 obj2")
    # 0x35854 是事件 58 的 handler,已知登記在 obj2 的跳表 0x51c79。
    hits_all = sorted(l for l, t in fx_all.items() if t == 0x35854)
    hits_o1 = sorted(l for l, t in fx_o1.items() if t == 0x35854)
    ok6 = hits_all == [0x51C79] and hits_o1 == []
    print(f"    {'PASS' if ok6 else 'FAIL'}: 全物件 -> {[hex(h) for h in hits_all]}"
          f"(應為 ['0x51c79']);限定 obj1 -> {[hex(h) for h in hits_o1]}(應為空)")
    if not ok6:
        fails.append(f"已知真值對照失敗:全物件 {hits_all},obj1 {hits_o1}")

    print("\n(7) 頁號歸屬必須逐頁落在正確的 object,且沒有頁被漏掉")
    owned = [page_owner(meta, pg)[0] for pg in range(pages_seen)]
    ok7 = (all(o is not None for o in owned)
           and page_owner(meta, pages_seen)[0] is None
           and page_owner(meta, meta["objs"][1]["first"] - 1)[1] == meta["objs"][1]["base"])
    print(f"    {'PASS' if ok7 else 'FAIL'}: {pages_seen} 頁全部有歸屬、"
          f"超出範圍回 None、obj2 首頁 linear = {hex(meta['objs'][1]['base'])}")
    if not ok7:
        fails.append("頁號→object 歸屬不正確")

    print("\n(8) calls 必須掃完整個 obj1:已知呼叫端 0x3f3b9 → 0x3ec17 落在單次掃描停點之後")
    # 前提先釘住:單次 md.disasm 確實停在這個呼叫端之前,否則本題就不鑑別。
    # 0x3f3b9 是 AIL set_period(0x3f398)裡的 `call 0x3ec17`(取最小週期),位元組可逐一核對。
    try:
        md = _capstone()
    except SystemExit:
        md = None
    if md is None:
        print("    FAIL: 沒有 capstone,無法驗 calls")
        fails.append("沒有 capstone")
    else:
        md.detail = False
        code, base = load_code(d, meta)
        single_end = base
        for insn in md.disasm(code, base):
            single_end = insn.address + insn.size
        hits, stops = find_rel_callers(md, code, base, 0x3EC17)
        raw = d[lin2file(meta, 0x3F3B9):lin2file(meta, 0x3F3B9) + 5]
        sweep_insns = resync_sweep(md, code, base)[0]
        ok8 = (single_end <= 0x3F3B9 and stops and stops[0] == single_end
               and len(stops) == 42 and stops == sorted(set(stops))
               and sweep_insns[0].address == base
               and hits == [(0x3F3B9, 'call', '0x3ec17', True)]
               and raw[0] == 0xE8
               and 0x3F3B9 + 5 + int.from_bytes(raw[1:], 'little', signed=True) == 0x3EC17)
        print(f"    {'PASS' if ok8 else 'FAIL'}: 單次掃描停在 {single_end:#x};續掃 {len(stops)} 處;"
              f"命中 {[hex(h[0]) for h in hits]}(應含 0x3f3b9)")
        if not ok8:
            fails.append(f"calls 漏掉後段呼叫端:停在 {single_end:#x},命中 {hits}")

        print("\n(8b) 線性掃描錯位處要靠位元組掃描補上,且標成未對齊")
        # 0x4d68c 是 `ret`,後面兩個 00 填充;線性掃描把 00 E9 讀成 `add cl, ch`,
        # 真正的 `jmp 0x4dc3a` 在 0x4d690。前提:掃描結果裡 0x4d690 不是指令起點。
        starts = {i.address for i in resync_sweep(md, code, base)[0]}
        hits_b, _ = find_rel_callers(md, code, base, 0x4DC3A)
        # 另兩條錯位的邊:往前跳的 jmp(rel32 是負數)與 call(E8,不是 E9)
        hits_j, _ = find_rel_callers(md, code, base, 0x4A104)
        hits_c, _ = find_rel_callers(md, code, base, 0x365DA)
        ok8b = (0x4D690 not in starts and code[0x4D68C - base] == 0xC3
                and hits_b == [(0x4D690, 'jmp', '0x4dc3a', False)]
                and (0x4AC65, 'jmp', '0x4a104', False) in hits_j and 0x4AC65 not in starts
                and (0x40118, 'call', '0x365da', False) in hits_c and 0x40118 not in starts)
        print(f"    {'PASS' if ok8b else 'FAIL'}: 0x4dc3a 的來源 {[(hex(h[0]), h[3]) for h in hits_b]};"
              f"0x4a104 未對齊 {[hex(h[0]) for h in hits_j if not h[3]]}(共 {len(hits_j)} 處);"
              f"0x365da 未對齊 {[hex(h[0]) for h in hits_c if not h[3]]}(共 {len(hits_c)} 處)")
        if not ok8b:
            fails.append(f"錯位處沒有補上或沒有標記:{hits_b} {hits_j} {hits_c}")

        print("\n(8c) 合成碼:最後一個能放下 rel32 的位置也要掃到")
        # `cmp al, 0xe8` 吃掉 E8,線性掃描看不到這個 call;E8 在 len - 5,是位元組掃描範圍的最後一格
        syn = bytes([0x3C, 0xE8, 0x10, 0x00, 0x00, 0x00])
        hits_s, _ = find_rel_callers(md, syn, 0x1000, 0x1000 + 1 + 5 + 0x10)
        ok8c = hits_s == [(0x1001, 'call', hex(0x1016), False)]
        print(f"    {'PASS' if ok8c else 'FAIL'}: {hits_s}")
        if not ok8c:
            fails.append(f"位元組掃描漏掉最後一格:{hits_s}")

        print("\n(8d) dis / range 遇到無法解碼的位元組印 db 行續掃,不安靜停下(續一百六十二)")
        # 合成:nop / FE F8(FE /7 無效)/ clc / mov eax, 1(fixup 在第 2 個 imm byte)/ ret
        c8 = b"\x90\xfe\xf8\xb8\x01\x00\x00\x00\xc3"
        L = ['0x001000  nop', '0x001001  db      0xfe  ; 無法解碼,跳 1 byte 續掃', '0x001002  clc',
             '0x001003  mov     eax, 1  ; ->0x2000', '0x001008  ret']
        got8d = [range_lines(md, c8, 0x1000, {0x1004: 0x2000}, s, e, n)
                 for s, e, n in ((0x1000, 0x1009, 10**9), (0x1000, 0x1008, 10**9), (0x1000, 0x1004, 10**9),
                                 (0x1000, 0x1001, 10**9), (0x1000, 0x2000, 2), (0x1002, 0x2000, 10**9))]
        want8d = [(L, 1), (L[:4], 1), (L[:4], 1), (L[:1], 0), (L[:3], 1), (L[2:], 0)]
        # 真 EXE:0x3cae4 是第一個停點(原本 range 停在這裡);全段的 db 行數 = calls 的續掃點數
        lines_r, bad_r = range_lines(md, code, base, {}, 0x3CAD6, 0x3CAE8, 10**9)
        full, bad_f = range_lines(md, code, base, {}, base, base + len(code), 10**9)
        db_f = [ln[:8] for ln in full if ln[10:12] == 'db']
        ok8d = (got8d == want8d and bad_r == 1
                and [ln[:8] for ln in lines_r] == ['0x03cad6', '0x03cadb', '0x03cadc', '0x03cae1', '0x03cae3',
                                                   '0x03cae4', '0x03cae5', '0x03cae6', '0x03cae7']
                and bad_f == 42 and db_f == [f'{s:#08x}' for s in stops]
                and full[-1] == '0x04ef28  ret' and len(full) == len(sweep_insns) + 42)
        print(f"    {'PASS' if ok8d else 'FAIL'}: 合成 {len(got8d)} 組;0x3cad6..0x3cae8 {[ln[:8] for ln in lines_r]};"
              f"全段 {len(full)} 行、db {bad_f} 行、最後 {full[-1]!r}")
        if not ok8d:
            fails.append(f"dis / range 續掃不對:{got8d} {lines_r} db {bad_f}")

    print("\n(9) le_xref.find_callers 的掃描範圍必須由 LE 表頭推出,涵蓋新版 obj1 後段")
    from le_xref import find_callers, code_file_range
    lo, hi = code_file_range(meta)
    tf, cf = lin2file(meta, 0x3EC17), lin2file(meta, 0x3F3B9)
    got9 = find_callers(d, tf, meta)
    # 前提:這個呼叫端在舊的寫死範圍(file 0x10000..0x4ec00)之外。
    ok9 = (lo == lin2file(meta, meta['objs'][0]['base']) and hi - lo == meta['objs'][0]['vsize']
           and cf >= 0x4EC00 and cf in got9)
    print(f"    {'PASS' if ok9 else 'FAIL'}: 範圍 file {lo:#x}..{hi:#x};"
          f"0x3ec17(file {tf:#x})的呼叫端 {[hex(c) for c in got9]}(應含 {cf:#x})")
    if not ok9:
        fails.append(f"le_xref.find_callers 範圍錯:{lo:#x}..{hi:#x},命中 {got9}")

    print("\n(10) build_fixups 的物件過濾 = 全物件結果限定在該物件的 linear 範圍;object_index 的邊界")
    per_obj = {k: build_fixups(d, meta, objects={k}) for k in (1, 2, 3)}
    ok10 = (len(fx_all) == 7948 and all(per_obj.values())
            and all(per_obj[k] == {a: t for a, t in fx_all.items()
                                   if meta['objs'][k - 1]['base'] <= a < meta['objs'][k - 1]['base'] + meta['objs'][k - 1]['vsize']}
                    for k in per_obj)
            and [object_index(meta, a) for a in (0x10000, 0x4EF28, 0x4EF29, 0x50000, 0x60000, 0xFFFF)]
            == [1, 1, None, 2, 3, None])
    print(f"    {'PASS' if ok10 else 'FAIL'}: 全物件 {len(fx_all)} 筆;各物件 {[len(v) for v in per_obj.values()]}")
    if not ok10:
        fails.append("build_fixups 的物件過濾或 object_index 不正確")

    if fails:
        print("\nSELFTEST FAILED:")
        for f in fails:
            print("  -", f)
        return 1
    print("\n--selftest passed(資料段錨點回歸 + 跨工具逐位址對照 + 越界拒絕 + "
          "非恆真控制 + fixup 全物件涵蓋 + 已知真值配對負向控制 + 頁號歸屬 + "
          "calls 全段涵蓋與錯位補掃 + dis / range 續掃 + le_xref 掃描範圍)。")
    return 0


def main(a):
    if len(a) == 2 and a[1] == '--selftest':
        return selftest()
    if len(a) < 3:
        print(__doc__); return 1
    d = open(a[1], 'rb').read()
    print(
        "# 來源檔案 "
        f"{os.path.basename(a[1])}；大小 {len(d)} 位元組；"
        f"MD5 {hashlib.md5(d).hexdigest()}；"
        f"SHA-256 {hashlib.sha256(d).hexdigest()}",
        file=sys.stderr,
    )
    meta = parse_le(d)
    code, base = load_code(d, meta)
    md = _capstone()
    md.detail = False
    cmd = a[2]

    if cmd == 'data':
        if len(a) != 5:
            print(__doc__); return 1
        try:
            dump_data(d, meta, int(a[3], 16), int(a[4], 0))
        except ValueError as e:
            print(f"data: {e}", file=sys.stderr)
            return 1
        return 0

    if cmd in ('dis', 'range'):
        start = int(a[3], 16)
        if cmd == 'dis':
            cnt = int(a[4]) if len(a) > 4 else 40
            end = base + len(code)   # 原本固定看 0x400 bytes,count 超過也會安靜截斷
        else:
            end = int(a[4], 16); cnt = 10**9
        if not base <= start < base + len(code):
            print(f"{cmd}: {start:#x} 不在 obj1 程式碼 {base:#x}..{base + len(code):#x}", file=sys.stderr)
            return 1
        lines, bad = range_lines(md, code, base, build_fixups(d, meta), start, end, cnt)
        for ln in lines:
            print(ln)
        if bad:
            print(f"# {cmd}:{bad} 個無法解碼的位元組,印成 db 行後各跳 1 byte 續掃", file=sys.stderr)
        return 0

    if cmd == 'calls':
        tgt = int(a[3], 16)
        hits, stops = find_rel_callers(md, code, base, tgt)
        for addr, mnem, op, aligned in hits:
            print(f'{addr:#08x}  {mnem} {op}'
                  + ('' if aligned else '  ; 只有位元組掃描命中(線性掃描在此錯位)'))
        # 續掃點數印到 stderr:不改 stdout 格式,但讓「掃描曾中斷」不再是無聲的。
        print(f"# calls:線性掃描遇到 {len(stops)} 處無法解碼的位元組,各跳 1 byte 後續掃"
              f"(掃到 {base + len(code):#x})", file=sys.stderr)
        return 0

    if cmd == 'refs':
        abs_ = int(a[3], 16)
        fx = build_fixups(d, meta)
        for lin, t in sorted(fx.items()):
            if t == abs_:
                print(f'{lin:#08x} -> {hex(t)}')
        return 0

    print(__doc__); return 1


if __name__ == '__main__':
    sys.exit(main(sys.argv))
