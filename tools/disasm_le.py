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
import sys, struct

# 2026-09-08:本檔的 docstring 含 cp950 編不出的字元(如 ↔),而無參數時會
# `print(__doc__)` —— 在本機 cp950 主控台上那一行直接 UnicodeEncodeError,
# 看起來像「工具壞了」。原本的偵測器只看 print 的字面字串,看不到這條路徑。
if hasattr(sys.stdout, "reconfigure"):
    sys.stdout.reconfigure(encoding="utf-8")
    sys.stderr.reconfigure(encoding="utf-8")
sys.path.insert(0, __file__.rsplit('/', 1)[0])
from le_xref import parse_le

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
    """
    page_size = meta['page_size']
    fixpage = meta['fixpage']; fixrec = meta['fixrec']
    npages = total_pages(meta)
    fx = {}
    for pg in range(npages):
        obj, page_lin = page_owner(meta, pg)
        if obj is None:
            continue
        if objects is not None and meta['objs'].index(obj) + 1 not in objects:
            continue
        off0 = struct.unpack_from('<I', d, fixpage + pg * 4)[0]
        off1 = struct.unpack_from('<I', d, fixpage + (pg + 1) * 4)[0]
        p = fixrec + off0; end = fixrec + off1
        while p < end:
            src_type = d[p]; flags = d[p + 1]; p += 2
            srcoff = struct.unpack_from('<h', d, p)[0]; p += 2
            # target
            if flags & 0x40:
                objn = d[p]; p += 1
            else:
                objn = d[p]; p += 1
            if flags & 0x10:
                trgoff = struct.unpack_from('<I', d, p)[0]; p += 4
            else:
                trgoff = struct.unpack_from('<H', d, p)[0]; p += 2
            base = meta['objs'][objn - 1]['base'] if 1 <= objn <= len(meta['objs']) else 0
            tgt = base + trgoff
            lin = page_lin + srcoff
            if (src_type & 0x0f) in (7, 5, 0):  # 32-bit offset / 16-bit etc
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

    if fails:
        print("\nSELFTEST FAILED:")
        for f in fails:
            print("  -", f)
        return 1
    print("\n--selftest passed(資料段錨點回歸 + 跨工具逐位址對照 + 越界拒絕 + "
          "非恆真控制 + fixup 全物件涵蓋 + 已知真值配對負向控制 + 頁號歸屬)。")
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
        if cmd == 'dis':
            start = int(a[3], 16); cnt = int(a[4]) if len(a) > 4 else 40
            end = start + 0x400
        else:
            start = int(a[3], 16); end = int(a[4], 16); cnt = 10**9
        fx = build_fixups(d, meta)
        off = start - base
        n = 0
        for insn in md.disasm(code[off:off + (end - start)], start):
            tgt = ''
            for o2 in range(insn.address, insn.address + insn.size):
                if o2 in fx:
                    tgt = f'  ; ->{hex(fx[o2])}'
                    break
            print((
                f'{insn.address:#08x}  {insn.mnemonic:<7} '
                f'{insn.op_str}{tgt}'
            ).rstrip())
            n += 1
            if n >= cnt:
                break
        return 0

    if cmd == 'calls':
        tgt = int(a[3], 16)
        for insn in md.disasm(code, base):
            if insn.mnemonic in ('call', 'jmp') and insn.op_str.startswith('0x'):
                try:
                    if int(insn.op_str, 16) == tgt:
                        print(f'{insn.address:#08x}  {insn.mnemonic} {insn.op_str}')
                except ValueError:
                    pass
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
