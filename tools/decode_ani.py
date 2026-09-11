#!/usr/bin/env python3
"""炎龍騎士團2 — ANI.DAT / AFM (Animation File Manager) 完整格式解碼器。

第 N 輪逆向工程成果。ANI.DAT 每個資源(共 9 個有效資源,見 unpack_dat.py --list)
都是一份完整的 AFM v1.00 檔案(作者 Lo Yuan Tsung,1993),結構如下:

資源(resource)結構:
    +0x00  80 bytes   版權橫幅 "AFM - Animation File Manager Version 1.00 ..."
    +0x50  1 byte      0x1A (SUB/EOF 標記,DOS 文字檔慣例)
    +0x51  0x50 bytes  標題欄位(space-padded ASCII,未設定時內容為 ".Empty Title. ")
    +0xA1  1 byte       0x00 (標題結尾 null)
    +0xA2  3 bytes      未知(版本/旗標相關,未逐位解出)
    +0xA5  uint16 LE     **frameCount**(反組譯證實:0x020421 讀 [buf+0xA5] 當幀數迴圈上界)
    +0xA7  uint16 LE     螢幕寬度(樣本恆為 320)      [推,本解碼器固定用 320,未讀此欄位]
    +0xA9  uint16 LE     螢幕高度(樣本恆為 200)      [推,本解碼器固定用 200,未讀此欄位]
    +0xAB  2 bytes       未知
    +0xAD  起            frameCount 個「幀記錄」,每筆:
             +0 uint16 LE  compSize   該幀 script 的壓縮位元組數(fread 用)
             +2 uint16 LE  cmdCount   該幀要執行的 VM 指令數
             +4 uint16 LE  (保留,樣本恆 0,用途未明)
             +6 uint16 LE  (保留,樣本恆 0,用途未明)
             +8 ... compSize bytes 的「AFM script」(見下方 VM)

反組譯位址(FD2.EXE linear):
    0x020421  播放器主函式(開 ANI.DAT → 讀資源 → 逐幀迴圈 → blit → 可按鍵跳過)
    0x036c9e  **VM 指令派發器**:逐位元組讀 opcode(0-9),查表 0x5276a(10 個函式指標),
              呼叫對應 handler,重複 cmdCount 次。
    0x036c7d  VM 狀態初始化:設定畫面寬度([0x52760])、framebuffer 指標([0x52762]
              = **恆為 0xA0000,即 VGA mode13h 顯示記憶體本身!**)、palette 暫存區
              指標([0x52766],malloc 768 bytes)。
    0x5276a   opcode 跳表(10 entries,第 11 項起是別的資料,故 opcode 只有 0-9)。

**關鍵發現**:AFM 不是逐幀獨立點陣圖,而是一個 **10-opcode 的增量式繪圖 VM**——
每幀是一段 script,對「上一幀遺留的 framebuffer/palette 狀態」疊加操作(填色/
RLE/局部貼圖/局部調色盤更新),不清空重畫。這是典型 1993 年「差分壓縮動畫」設計,
用小體積 script 驅動大螢幕輸出(96 幀僅 ~1MB,遠小於 96×64000=6MB 的全幀陣列)。

VM opcode 表(0-9,實測 x86 反組譯還原,見 docs/knowledge-base/39-ani-afm-format.md):
    0  palette 全填滿(1 byte 值 ×768)
    1  palette 整包字面載入(768 bytes)
    2  palette RLE 解壓(2-mode:高2bit==11→run,否則→literal;填滿 768 bytes)
    3  palette 局部貼補:N×(colorIdx, count, RGB...×count)  offset/length = idx×3
    4  framebuffer 全填滿(1 byte 值 × width,預設 width=64000=320×200)
    5  framebuffer 整包字面載入(width bytes)
    6  framebuffer RLE 解壓(同 opcode2 的 2-mode,填滿 width bytes)— 主力全螢幕解碼器
    7  N×(offset16, value8) 單點繪製(sparse pixel plot)
    8  N×(offset16, length8, value8) 區段填色(run-fill)
    9  N×(offset16, length8, rawBytes...) 區段貼圖(sparse block copy / patch)

用法:
    python3 decode_ani.py frames <ANI_NNN.bin> <out目錄>          # 每幀存一張 PNG
    python3 decode_ani.py info   <ANI_NNN.bin>                     # 印出幀數/欄位摘要
"""
import os
import sys
import struct

W, H = 320, 200
FRAME_BYTES = W * H  # 64000


def rle_2mode(data, pos, dst, dst_off, count):
    """opcode 2 / 6 共用的 2-mode RLE:高2bit==0b11 → run,否則單一 literal。"""
    # 2026-09-08:這個迴圈的條件只看 `written < count`,**完全沒有位置邊界**——
    # 截斷或損壞的 script 會讓 `data[pos]` 直接 IndexError 整支崩掉。另外
    # `ctrl == 0xC0` 時 `n = 0`,written 不前進,只能靠讀到檔尾崩潰才停下來。
    # 兩者都改成「資料用完或無法前進就停」,把已寫入的部分交回給呼叫端。
    written = 0
    end_of_data = len(data)
    while written < count:
        if pos >= end_of_data:
            break
        ctrl = data[pos]; pos += 1
        if (ctrl & 0xC0) == 0xC0:
            n = ctrl & 0x3F
            if pos >= end_of_data:
                break
            val = data[pos]; pos += 1
            end = min(dst_off + written + n, dst_off + count)
            for i in range(dst_off + written, end):
                dst[i] = val
            if n == 0:
                # 0 長度的 run 不前進;照原樣會空轉到讀爆為止。當成資料結束。
                break
            written += n
        else:
            if dst_off + written >= len(dst):
                break
            dst[dst_off + written] = ctrl
            written += 1
    return pos


def selftest():
    """手算 2-mode RLE + 兩個剛修掉的缺陷的回歸測試。

    這個迴圈原本的終止條件**只看 written < count**,沒有任何位置邊界:截斷或
    損壞的 script 會讓 `data[pos]` 直接 IndexError;而 `ctrl == 0xC0` 時
    `n = 0`、written 不前進,只能靠讀到檔尾崩潰才停下來。兩者都要有回歸測試,
    否則下次重寫這個迴圈會再犯一次。
    """
    import sys as _sys
    if hasattr(_sys.stdout, "reconfigure"):
        _sys.stdout.reconfigure(encoding="utf-8")
        _sys.stderr.reconfigure(encoding="utf-8")
    fails = []

    print("(1) 手算:高 2 bit == 0b11 是 run(長度 = ctrl & 0x3F),否則單一 literal")
    dst = bytearray(8)
    pos = rle_2mode(b"\xC3\x77\x05\x06", 0, dst, 0, 5)
    ok1 = bytes(dst[:5]) == b"\x77\x77\x77\x05\x06" and pos == 4
    print(f"    {'PASS' if ok1 else 'FAIL'}: {bytes(dst[:5]).hex()} pos={pos}"
          f"(預期 777777 0506, pos=4)")
    if not ok1:
        fails.append(f"手算不符:{bytes(dst[:5]).hex()} pos={pos}")

    print("\n(2) 回歸:截斷的 script 以前會 IndexError —— 現在必須安全返回")
    for label, data, count in (("控制位元組後就沒了", b"\xC3", 5),
                               ("完全空的", b"", 5),
                               ("literal 中途截斷", b"\x01\x02", 8)):
        d2 = bytearray(16)
        try:
            p = rle_2mode(data, 0, d2, 0, count)
            print(f"    PASS: 「{label}」-> pos={p}")
        except Exception as exc:                              # noqa: BLE001
            print(f"    FAIL: 「{label}」丟出 {type(exc).__name__}")
            fails.append(f"{label} 丟出 {type(exc).__name__}")

    print("\n(3) 回歸:ctrl == 0xC0 是 0 長度的 run,written 不前進,以前只能讀爆才停")
    d3 = bytearray(16)
    try:
        p3 = rle_2mode(b"\xC0\x00" * 200, 0, d3, 0, 16)
        ok3 = True
        print(f"    PASS: 200 個 0 長度 run -> pos={p3},沒有空轉到讀爆")
    except Exception as exc:                                  # noqa: BLE001
        ok3 = False
        print(f"    FAIL: 丟出 {type(exc).__name__}")
        fails.append(f"0 長度 run 仍會 {type(exc).__name__}")

    print("\n(4) 不變量:永遠不會寫超出 dst,pos 永遠落在 [0, len(data)]")
    bad = []
    import random as _r
    rng = _r.Random(1234)
    for _ in range(300):
        data = bytes(rng.randrange(256) for _ in range(rng.randint(0, 40)))
        size = rng.randint(1, 32)
        d4 = bytearray(size)
        try:
            p = rle_2mode(data, 0, d4, 0, size)
            if not (0 <= p <= len(data)):
                bad.append((data[:6].hex(), size, p))
        except Exception as exc:                              # noqa: BLE001
            bad.append((data[:6].hex(), size, type(exc).__name__))
    ok4 = not bad
    print(f"    {'PASS' if ok4 else 'FAIL'}: 300 組隨機輸入"
          + ("" if ok4 else f",異常 {bad[:3]}"))
    if not ok4:
        fails.append(f"隨機輸入下的不變量被破壞:{bad[:3]}")

    print("\n(5) 非恆真控制:合法輸入必須真的寫進 dst,而不是每次都提早 break")
    d5 = bytearray(16)
    rle_2mode(b"\xCF\xAB", 0, d5, 0, 15)
    written = sum(1 for b in d5[:15] if b == 0xAB)
    ok5 = written == 15
    print(f"    {'PASS' if ok5 else 'FAIL'}: 0xCF(run 15) 寫入 {written}/15")
    if not ok5:
        fails.append(f"合法 run 只寫入 {written}/15 —— 守衛加得太嚴,把正常路徑也擋掉了")

    print("\n(6) 長度 1 的 run 之後必須繼續解(只有長度 0 才當成資料結束)")
    # 2026-09-11 窮舉突變測試:`n == 0` 改成 `n == 1` 逃掉 —— 沒有任何案例在長度 1 的
    # run 之後還有資料。
    d6 = bytearray(2)
    pos6 = rle_2mode(bytes([0xC1, 0x55, 0x07]), 0, d6, 0, 2)
    ok6 = bytes(d6) == b"\x55\x07" and pos6 == 3
    print(f"    {'PASS' if ok6 else 'FAIL'}: 寫出 {bytes(d6).hex()}(應 5507)、pos={pos6}(應 3)")
    if not ok6:
        fails.append(f"長度 1 的 run 之後就停了:{bytes(d6).hex()} / {pos6}")

    if fails:
        print("\nSELFTEST FAILED:")
        for f in fails:
            print("  -", f)
        return 1
    print("\n--selftest passed(手算 + 截斷回歸 + 0 長度 run 回歸 + "
          "隨機輸入不變量 + 非恆真控制)。")
    return 0


def run_vm(script, cmd_count, palette, framebuf):
    """執行 cmd_count 個 AFM VM 指令,原地修改 palette(768B bytearray)與
    framebuf(64000B bytearray)。回傳消耗的 script 位元組數(除錯用)。"""
    pos = 0
    for _ in range(cmd_count):
        op = script[pos]; pos += 1
        if op == 0:  # palette fill
            v = script[pos]; pos += 1
            for i in range(768):
                palette[i] = v
        elif op == 1:  # palette literal load
            palette[0:768] = script[pos:pos + 768]
            pos += 768
        elif op == 2:  # palette RLE
            pos = rle_2mode(script, pos, palette, 0, 768)
        elif op == 3:  # palette 局部貼補
            n = script[pos]; pos += 1
            for _ in range(n):
                idx = script[pos]; pos += 1
                cnt = script[pos]; pos += 1
                off, length = idx * 3, cnt * 3
                palette[off:off + length] = script[pos:pos + length]
                pos += length
        elif op == 4:  # framebuffer fill
            v = script[pos]; pos += 1
            for i in range(FRAME_BYTES):
                framebuf[i] = v
        elif op == 5:  # framebuffer literal load
            framebuf[0:FRAME_BYTES] = script[pos:pos + FRAME_BYTES]
            pos += FRAME_BYTES
        elif op == 6:  # framebuffer RLE(主力全螢幕解碼)
            pos = rle_2mode(script, pos, framebuf, 0, FRAME_BYTES)
        elif op == 7:  # 單點繪製 ×N
            n = struct.unpack_from('<H', script, pos)[0]; pos += 2
            for _ in range(n):
                off = struct.unpack_from('<H', script, pos)[0]; pos += 2
                val = script[pos]; pos += 1
                if 0 <= off < FRAME_BYTES:
                    framebuf[off] = val
        elif op == 8:  # 區段填色 ×N
            n = struct.unpack_from('<H', script, pos)[0]; pos += 2
            for _ in range(n):
                off = struct.unpack_from('<H', script, pos)[0]; pos += 2
                length = script[pos]; pos += 1
                val = script[pos]; pos += 1
                end = min(off + length, FRAME_BYTES)
                for i in range(off, end):
                    framebuf[i] = val
        elif op == 9:  # 區段貼圖 ×N
            n = struct.unpack_from('<H', script, pos)[0]; pos += 2
            for _ in range(n):
                off = struct.unpack_from('<H', script, pos)[0]; pos += 2
                length = script[pos]; pos += 1
                end = min(off + length, FRAME_BYTES)
                framebuf[off:end] = script[pos:pos + (end - off)]
                pos += length
        else:
            raise ValueError(f"未知 opcode {op} @ script pos {pos - 1}")
    return pos


def parse_header(data):
    banner = data[0:0x50].decode('ascii', 'replace')
    title = data[0x51:0xA1].decode('ascii', 'replace').strip()
    frame_count = struct.unpack_from('<H', data, 0xA5)[0]
    width = struct.unpack_from('<H', data, 0xA7)[0]
    height = struct.unpack_from('<H', data, 0xA9)[0]
    return {
        'banner': banner.strip(),
        'title': title,
        'frame_count': frame_count,
        'width': width,
        'height': height,
    }


def iter_frames(data, frame_count, start=0xAD):
    """逐幀 yield (compSize, cmdCount, scriptBytes)。"""
    pos = start
    for i in range(frame_count):
        comp_size, cmd_count, r0, r1 = struct.unpack_from('<HHHH', data, pos)
        pos += 8
        script = data[pos:pos + comp_size]
        pos += comp_size
        yield i, comp_size, cmd_count, r0, r1, script


def cmd_info(path):
    data = open(path, 'rb').read()
    hdr = parse_header(data)
    print(f"{os.path.basename(path)}: {len(data)} bytes")
    print(f"  banner: {hdr['banner']}")
    print(f"  title : {hdr['title']!r}")
    print(f"  frame_count(@0xA5) = {hdr['frame_count']}")
    print(f"  width(@0xA7)={hdr['width']}  height(@0xA9)={hdr['height']}")
    total = 0
    for i, comp_size, cmd_count, r0, r1, script in iter_frames(data, hdr['frame_count']):
        total += 8 + comp_size
        if i < 10 or i >= hdr['frame_count'] - 3:
            print(f"  frame {i:3d}: compSize={comp_size:6d} cmdCount={cmd_count:3d} "
                  f"reserved=({r0},{r1}) first_op={script[0] if script else '-'}")
    print(f"  幀資料總長度 = {total} (+ header 0xAD = {total + 0xAD}, 資源實長 {len(data)})")


def cmd_frames(path, out_dir):
    from PIL import Image
    data = open(path, 'rb').read()
    hdr = parse_header(data)
    os.makedirs(out_dir, exist_ok=True)
    palette = bytearray(768)
    framebuf = bytearray(FRAME_BYTES)
    base = os.path.splitext(os.path.basename(path))[0]
    n_ok = 0
    for i, comp_size, cmd_count, r0, r1, script in iter_frames(data, hdr['frame_count']):
        try:
            run_vm(script, cmd_count, palette, framebuf)
        except (IndexError, ValueError) as e:
            print(f"  frame {i}: 解碼中斷 ({e}),已停止,前面幀已輸出")
            break
        pal8 = bytearray(768)
        for j in range(256):
            r, g, b = palette[j * 3], palette[j * 3 + 1], palette[j * 3 + 2]
            pal8[j * 3 + 0] = (r << 2) | (r >> 4)
            pal8[j * 3 + 1] = (g << 2) | (g >> 4)
            pal8[j * 3 + 2] = (b << 2) | (b >> 4)
        im = Image.frombytes('P', (W, H), bytes(framebuf))
        im.putpalette(bytes(pal8))
        im.convert('RGB').save(os.path.join(out_dir, f"{base}_f{i:03d}.png"))
        n_ok += 1
    print(f"{base}: 輸出 {n_ok}/{hdr['frame_count']} 幀 -> {out_dir}")


def main(argv):
    if len(argv) == 2 and argv[1] == "--selftest":
        return selftest()
    if len(argv) < 3:
        print(__doc__)
        return 1
    if argv[1] == 'info':
        cmd_info(argv[2])
    elif argv[1] == 'frames':
        cmd_frames(argv[2], argv[3])
    else:
        print(__doc__)
        return 1
    return 0


if __name__ == '__main__':
    sys.exit(main(sys.argv))
