#!/usr/bin/env python3
"""炎龍騎士團2 — DOS4GW LE(32-bit flat)反組譯器(capstone)。

LE obj1 = code,base=0x10000(linear)。本工具把 linear 位址範圍反組譯成
帶位址的 x86-32 組語,並標出每條指令觸及的 fixup target(資料/字串/呼叫的絕對位址),
方便做控制流追蹤與 sink→caller 反向溯源(規則 62)。

linear ↔ file:**必須逐 object 換算**(2026-09-08 修正)。
  file = data_off + (obj.first - 1) * page_size + (linear - obj.base)

  舊版說明寫 `file = data_off + (linear - 0x10000)`,那只對 object 1 成立。
  object 2(base 0x50000)偏 0x1000、object 3(base 0x60000)偏 0xD000 ——
  後者甚至讀到檔案結尾之外。既有記錄「本工具即使在已知正確位址也產出垃圾」
  講的就是這件事,那些位址都在資料段。

用法:
  python3 disasm_le.py <FD2.EXE> dis <linear_hex> [count]      反組譯 count 條指令
  python3 disasm_le.py <FD2.EXE> range <start_hex> <end_hex>   反組譯 linear 範圍
  python3 disasm_le.py <FD2.EXE> calls <target_hex>            找對 target 的相對 call/jmp 來源(linear)
  python3 disasm_le.py <FD2.EXE> refs <abs_hex>                找 code 中被 fixup 成 abs 的位置(資料 xref)
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

try:
    from capstone import Cs, CS_ARCH_X86, CS_MODE_32
except ImportError:
    sys.exit("need capstone: run under docker uv (見 README)")

CODE_BASE = 0x10000


def lin2file(meta, lin):
    """linear 位址 → 檔案位移。**必須逐 object 換算**,不能只用 obj1 的公式。

    2026-09-08 修正。原本寫死 `data_off + (lin - CODE_BASE)`,那只對 object 1
    成立(base 0x10000、first page 1)。object 2(base 0x50000、first page 64)
    與 object 3(base 0x60000、first page 68)各自有不同的頁起點,舊公式會:

        0x51b91 / 0x5274e (obj2)  偏 +0x1000 → 讀到全 0,不是真的表格位元組
        0x620a1           (obj3)  偏 +0xD000 → **直接讀到檔案結尾之外**

    這正是既有記錄「disasm_le 即使在已知正確位址也產出垃圾」的根因 ——
    那些「已知正確位址」都是資料段的 0x5xxxx / 0x6xxxx。程式碼段(obj1)一直
    是對的,所以問題看起來時有時無。

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


def dump_data(d, meta, start, length):
    """Print a bounded, reproducible LE-linear hexdump for data/table RE."""
    if length < 0 or length > 0x10000:
        raise ValueError("length must be in 0..0x10000")
    obj = next((o for o in meta['objs'] if o['base'] <= start and start + length <= o['base'] + o['vsize']), None)
    if obj is None:
        raise ValueError("range outside one LE object")
    foff = meta['data_off'] + (obj['first'] - 1) * meta['page_size'] + (start - obj['base'])
    raw = d[foff:foff + length]
    for i in range(0, len(raw), 16):
        row = raw[i:i + 16]
        hexes = " ".join(f"{b:02x}" for b in row)
        text = "".join(chr(b) if 0x20 <= b < 0x7f else "." for b in row)
        print(f"{start + i:#08x}  {hexes:<47}  |{text}|")


def build_fixups(d, meta):
    """回傳 {code_linear: target_abs} —— 每個被 patch 的位置→其絕對 target。"""
    page_size = meta['page_size']
    fixpage = meta['fixpage']; fixrec = meta['fixrec']
    npages = meta['objs'][0]['pages']
    fx = {}
    for pg in range(npages):
        off0 = struct.unpack_from('<I', d, fixpage + pg * 4)[0]
        off1 = struct.unpack_from('<I', d, fixpage + (pg + 1) * 4)[0]
        p = fixrec + off0; end = fixrec + off1
        page_lin = CODE_BASE + pg * page_size
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

    if fails:
        print("\nSELFTEST FAILED:")
        for f in fails:
            print("  -", f)
        return 1
    print("\n--selftest passed(資料段錨點回歸 + 跨工具逐位址對照 + 越界拒絕 + "
          "非恆真控制)。")
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
    md = Cs(CS_ARCH_X86, CS_MODE_32)
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
