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
    +0xA5  int16 LE      **frameCount**(反組譯證實:0x020421 讀 [buf+0xA5] 當幀數迴圈上界;
                         **有號**,`0x0204ff` movsx + `0x020506` jge,≥ 0x8000 一幀都不播)
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
PALETTE_BYTES = 768  # 256 色 × RGB

# 續一百四十四:原版播放器 play_afm(0x020421)開檔後只做一件事判斷檔頭 ——
# `0x0204da` fread **0xAD** bytes,接著 `0x0204ea` 讀 [buf+0xA5] 當幀數。
# 它**不比對橫幅**:EXE 全檔沒有 "AFM" / "Animation File" / "Lo Yuan" 字串,
# 唯一的 "ANI.DAT" 字串(0x501c7)也只有 0x020498 這一處參照。所以「不是 ANI 檔」
# 的判準跟遊戲一樣只看長度:連 0xAD 檔頭都放不下的資料沒有任何欄位可讀。
HEADER_BYTES = 0xAD


class NotANI(Exception):
    """資料短於 0xAD 檔頭(遊戲 fread 的長度),不是 ANI 檔。"""


class TruncatedScript(ValueError):
    """幀 script 在 cmdCount 個指令執行完之前就用完了(資源被截短)。

    原版 play_afm 是先 fread compSize bytes 進固定緩衝區再交給 VM;檔案被截短時 fread
    讀不滿,VM 會接著執行緩衝區裡上一幀殘留的 bytes —— 沒有可以重現的「正確」畫面,
    所以這裡明確拒絕,而不是像 rle_2mode 那樣寫到哪算哪。繼承 ValueError,
    `cmd_frames` 原有的 `except (IndexError, ValueError)` 照樣接得到。
    """


class BadOpcode(ValueError):
    """opcode 不在 0-9。原版 `0x037012` 直接 `call [op*4 + 0x5276a]`,不檢查範圍。"""


def _need(script: bytes, pos: int, n: int) -> None:
    """script 從 pos 起還要讀 n bytes;不夠就丟 TruncatedScript。"""
    if pos + n > len(script):
        raise TruncatedScript(f"script 只有 {len(script)} bytes,@{pos} 還要讀 {n} bytes")


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

    print("\n(7) 續一百四十四:檔頭 / 幀記錄截斷 —— 短於 0xAD 丟 NotANI,其餘降級不崩")
    # 合成檔:每個欄位取不同的值(幀數 2、寬 320、高 200、兩段未知 byte、兩幀的四個欄位
    # 互不相同),否則讀錯位置的突變會因為兩個欄位剛好同值而逃掉(續一百四十)。
    hdr7 = bytearray(HEADER_BYTES)
    hdr7[0:0x50] = b"AFM - Animation File Manager Version 1.00".ljust(0x50, b" ")
    hdr7[0x50] = 0x1A
    hdr7[0x51:0xA1] = b".Empty Title.".ljust(0x50, b" ")
    hdr7[0xA2:0xA5] = b"\x11\x22\x33"
    struct.pack_into('<HHH', hdr7, 0xA5, 2, 320, 200)
    hdr7[0xAB:0xAD] = b"\x44\x55"
    s0, s1 = bytes(range(0x61, 0x66)), bytes(range(0x71, 0x75))
    syn7 = (bytes(hdr7) + struct.pack('<HHHH', 5, 3, 7, 9) + s0
            + struct.pack('<HHHH', 4, 1, 0x0B, 0x0D) + s1)
    fr0, fr1 = (0, 5, 3, 7, 9, s0), (1, 4, 1, 0x0B, 0x0D, s1)
    # (7a) 判準本身:每個前綴「丟 NotANI」若且唯若「長度 < 0xAD」(遊戲 fread 0xAD),
    #      其他例外一律不准。兩個方向都要成立:守衛太鬆會在 0xAC 放行,太嚴會在 0xAD 拒絕。
    bad7 = []
    for c in range(len(syn7) + 1):
        try:
            frames_bytes(syn7[:c])
            rejected = False
        except NotANI:
            rejected = True
        except Exception as exc:                              # noqa: BLE001
            bad7.append((c, type(exc).__name__))
            continue
        if rejected != (c < HEADER_BYTES):
            bad7.append((c, "NotANI" if rejected else "放行"))
    ok7a = not bad7
    print(f"    {'PASS' if ok7a else 'FAIL'}: {len(syn7) + 1} 個前綴,NotANI 恰好落在長度 0..0xAC"
          + ("" if ok7a else f",異常 {bad7[:4]}"))
    if not ok7a:
        fails.append(f"截斷前綴的拒絕 / 例外不符判準:{bad7[:4]}")
    # (7b) 正控制:截斷檔仍要交出讀得到的幀(守衛若把截斷檔一律回空,這題會抓到)。
    want7 = ((HEADER_BYTES, []),
             (HEADER_BYTES + 7, []),
             (HEADER_BYTES + 8, [fr0[:5] + (b"",)]),
             (HEADER_BYTES + 13, [fr0]),
             (HEADER_BYTES + 20, [fr0]),
             (HEADER_BYTES + 21, [fr0, fr1[:5] + (b"",)]),
             (len(syn7), [fr0, fr1]))
    def _try7(fn, blob):
        # 被測函式丟出的例外要變成 FAIL 而不是讓整個 selftest 崩掉(Traceback 不是判定)。
        try:
            return fn(blob)
        except Exception as exc:                              # noqa: BLE001
            return f"{type(exc).__name__}: {exc}"

    for c, want in want7:
        got = _try7(frames_bytes, syn7[:c])
        ok = got == want
        print(f"    {'PASS' if ok else 'FAIL'}: 截在 0x{c:X} -> "
              f"{len(got) if isinstance(got, list) else got} 幀(應 {len(want)})")
        if not ok:
            fails.append(f"截在 0x{c:X}:{got} != {want}")
    # 橫幅也要比:窮舉突變 `data[0:0x50]` 的 0->1(少了 "A")、0x50->0x51(把 0x1A 帶進來)原本都逃掉。
    h7 = _try7(parse_header, syn7)
    want7h = ("AFM - Animation File Manager Version 1.00", 2, 320, 200, ".Empty Title.")
    got7h = ((h7['banner'], h7['frame_count'], h7['width'], h7['height'], h7['title'])
             if isinstance(h7, dict) else h7)
    ok7h = got7h == want7h
    print(f"    {'PASS' if ok7h else 'FAIL'}: 檔頭欄位 {got7h}")
    if not ok7h:
        fails.append(f"檔頭欄位讀錯:{got7h}")
    # (7c) 判準不含橫幅:遊戲不比對橫幅(EXE 沒有 "AFM" 字串),橫幅換成垃圾也必須照常解。
    #      日後若有人「順手」加 magic 檢查,會拒絕遊戲照樣播放的檔,這題擋下。
    alt7 = b"X" * 0x50 + b"\x00" + syn7[0x51:]
    ok7c = _try7(frames_bytes, alt7) == [fr0, fr1]
    print(f"    {'PASS' if ok7c else 'FAIL'}: 橫幅與 0x1A 換成垃圾仍解出 2 幀")
    if not ok7c:
        fails.append("橫幅換掉就不解了 —— 判準比遊戲嚴")

    print("\n(8) 續一百四十五:run_vm 逐 opcode —— 完整 script 的效果、截短的丟 TruncatedScript")
    # 每個 opcode 一段最小 script(cmdCount = 1)。初始緩衝區每格的值都不同,寫錯位置看得出來;
    # op 3 / 7 / 8 / 9 都放 2 筆以上,第二筆的守衛才測得到;7 / 8 / 9 各有一筆貼在或越過畫面尾端。
    pal0 = bytes(i % 256 for i in range(768))
    fb0 = bytes(i % 251 for i in range(FRAME_BYTES))
    lit_pal = bytes((i * 7 + 3) % 256 for i in range(768))
    lit_fb = bytes((i * 13 + 5) % 256 for i in range(FRAME_BYTES))

    def _with(base, patches):
        b = bytearray(base)
        for off, val in patches:
            b[off:off + len(val)] = val
        return bytes(b)

    E = FRAME_BYTES
    ops8 = (  # (opcode, script, 預期 palette, 預期 framebuf)
        (0, b"\x00\x11", b"\x11" * 768, fb0),
        (1, b"\x01" + lit_pal, lit_pal, fb0),
        (2, b"\x02" + b"\xFF\x21" * 12 + b"\xCC\x22", b"\x21" * 756 + b"\x22" * 12, fb0),
        (3, b"\x03\x02\x01\x01ABC\xFF\x01DEF", _with(pal0, ((3, b"ABC"), (765, b"DEF"))), fb0),
        # 越過 palette 尾端:只寫 765..767,照樣跳過 6 bytes;palette 不准變長。
        (3, b"\x03\x01\xFF\x02GHIJKL", _with(pal0, ((765, b"GHI"),)), fb0),
        (4, b"\x04\x33", pal0, b"\x33" * E),
        (5, b"\x05" + lit_fb, pal0, lit_fb),
        (6, b"\x06" + b"\xFF\x44" * 1015 + b"\xF7\x45", pal0, b"\x44" * 63945 + b"\x45" * 55),
        (7, b"\x07" + struct.pack('<HHBHBHB', 3, 0, 0x76, E - 1, 0x77, E, 0x79),
         pal0, _with(fb0, ((0, b"\x76"), (E - 1, b"\x77")))),
        (8, b"\x08" + struct.pack('<HHBBHBB', 2, 100, 5, 0x88, E - 2, 5, 0x89),
         pal0, _with(fb0, ((100, b"\x88" * 5), (E - 2, b"\x89\x89")))),
        (9, b"\x09" + struct.pack('<HHB', 2, 200, 3) + b"\x91\x92\x93"
         + struct.pack('<HB', E - 1, 2) + b"\x94\x95",
         pal0, _with(fb0, ((200, b"\x91\x92\x93"), (E - 1, b"\x94")))),
        # 剛好放滿的 0 筆 / 0 長度:守衛要的長度多 1 就會把合法的 script 判成截短(窮舉突變第一輪
        # op 3 / 7 / 8 / 9 的筆數守衛、op 3 / 9 的每筆守衛 2->3、3->4 都逃掉 —— 沒有一段 script 在那裡結束)。
        (3, b"\x03\x00", pal0, fb0),
        (3, b"\x03\x01\x05\x00", pal0, fb0),
        (7, b"\x07" + struct.pack('<H', 0), pal0, fb0),
        (8, b"\x08" + struct.pack('<H', 0), pal0, fb0),
        (9, b"\x09" + struct.pack('<H', 0), pal0, fb0),
        (9, b"\x09" + struct.pack('<HHB', 1, 7, 0), pal0, fb0),
    )

    def _run8(script, cmd, pal, fb):
        # 同 _try7:被測函式的例外轉成字串判定,不讓 selftest 以 Traceback 收場。
        try:
            return run_vm(script, cmd, pal, fb)
        except Exception as exc:                              # noqa: BLE001
            return type(exc).__name__

    bad8 = []
    for op, sc, want_pal, want_fb in ops8:
        pal, fb = bytearray(pal0), bytearray(fb0)
        got = _run8(sc, 1, pal, fb)
        if got != len(sc) or bytes(pal) != want_pal or bytes(fb) != want_fb:
            bad8.append((op, "完整", got, len(sc)))
        # 截短:長度 0 連 opcode 都讀不到,一律 TruncatedScript;op 2 / 6 的 RLE 照 rle_2mode 的
        # 約定降級(停在資料尾、不丟例外),其餘 opcode 每個前綴都要丟 TruncatedScript。
        # 緩衝區長度一律不准變。op 5 / 6 每次要動 6 萬多格,只取頭尾截點。
        cuts = (range(len(sc)) if op not in (5, 6)
                else (0, 1, 2, 3, len(sc) - 2, len(sc) - 1))
        for c in cuts:
            pal, fb = bytearray(pal0), bytearray(fb0)
            got = _run8(sc[:c], 1, pal, fb)
            want = "TruncatedScript" if (c == 0 or op not in (2, 6)) else c
            if got != want or len(pal) != 768 or len(fb) != FRAME_BYTES:
                bad8.append((op, c, got, len(pal), len(fb)))
                break
    # 串起來:10 段接成一支(cmdCount = 10),pos 要跨指令正確累加,結果等於逐段執行。
    chain = b"".join(sc for _op, sc, _p, _f in ops8)
    pal_a, fb_a = bytearray(pal0), bytearray(fb0)
    got_c = _run8(chain, len(ops8), pal_a, fb_a)
    pal_b, fb_b = bytearray(pal0), bytearray(fb0)
    for _op, sc, _p, _f in ops8:
        _run8(sc, 1, pal_b, fb_b)
    # 長度也要看:逐段執行用的是同一個 run_vm,op 1 讀 769 bytes 之類的錯兩邊一起錯、彼此相等;
    # 只有串接時後面還有資料,多讀的那 1 byte 才會讓 palette 變長(窮舉突變第一輪 768->769 逃掉)。
    if (got_c != len(chain) or pal_a != pal_b or fb_a != fb_b
            or len(pal_a) != 768 or len(fb_a) != FRAME_BYTES):
        bad8.append(("串接", got_c, len(chain)))
    if _run8(chain[:-1], len(ops8), bytearray(pal0), bytearray(fb0)) != "TruncatedScript":
        bad8.append(("串接少 1 byte", "沒有 TruncatedScript"))
    # opcode 10 起沒有 handler;cmdCount 0 連 opcode 都不讀(原版 0x036ffa 先判 0 就跳過)。
    for op in (10, 0xFF):
        got = _run8(bytes([op, 0, 0]), 1, bytearray(768), bytearray(FRAME_BYTES))
        if got != "BadOpcode":
            bad8.append((op, "未知 opcode", got))
    if _run8(b"", 0, bytearray(768), bytearray(FRAME_BYTES)) != 0:
        bad8.append(("cmdCount 0", "不是回 0"))
    if not (issubclass(TruncatedScript, ValueError) and issubclass(BadOpcode, ValueError)):
        bad8.append("新例外不是 ValueError 子類,cmd_frames 的 except 接不到")
    ok8 = not bad8
    print(f"    {'PASS' if ok8 else 'FAIL'}: {len(ops8)} 段 script(10 個 opcode)的完整效果 + 截短前綴"
          " + 串接 + 未知 opcode"
          + ("" if ok8 else f",異常 {bad8[:4]}"))
    if not ok8:
        fails.append(f"run_vm 不符:{bad8[:4]}")

    print("\n(9) 續一百四十五:幀數是有號 16-bit(0x0204ff movsx + 0x020506 jge)")
    # 0x7FFF 仍是正數:讀到幀記錄用完為止(2 幀);0x8000 / 0xFFFF 是負數:原版一幀都不播。
    bad9 = []
    for raw, want_fc, want_fr in ((0x7FFF, 0x7FFF, [fr0, fr1]), (0x8000, -0x8000, []),
                                  (0xFFFF, -1, [])):
        blob9 = bytearray(syn7)
        struct.pack_into('<H', blob9, 0xA5, raw)
        h9 = _try7(parse_header, bytes(blob9))
        fc9 = h9['frame_count'] if isinstance(h9, dict) else h9
        fr9 = _try7(frames_bytes, bytes(blob9))
        if (fc9, fr9) != (want_fc, want_fr):
            bad9.append((hex(raw), fc9, fr9 if isinstance(fr9, str) else len(fr9)))
    ok9 = not bad9
    print(f"    {'PASS' if ok9 else 'FAIL'}: 0x7FFF -> 2 幀;0x8000 / 0xFFFF -> 負數、0 幀"
          + ("" if ok9 else f",異常 {bad9}"))
    if not ok9:
        fails.append(f"幀數的正負號與原版不符:{bad9}")

    if fails:
        print("\nSELFTEST FAILED:")
        for f in fails:
            print("  -", f)
        return 1
    print("\n--selftest passed(手算 + 截斷回歸 + 0 長度 run 回歸 + "
          "隨機輸入不變量 + 非恆真控制 + 檔頭 / 幀記錄截斷 + VM 逐 opcode 截短 + 有號幀數)。")
    return 0


def run_vm(script, cmd_count, palette, framebuf):
    """執行 cmd_count 個 AFM VM 指令,原地修改 palette(768B bytearray)與
    framebuf(64000B bytearray)。回傳消耗的 script 位元組數(除錯用)。

    script 不夠讀時丟 TruncatedScript、opcode 不在 0-9 時丟 BadOpcode;兩者都在改動
    緩衝區之前丟出,palette / framebuf 的長度永遠不變。op 2 / 6 的 RLE 例外:
    照 rle_2mode 的約定寫到哪算哪(續一百四十五)。
    """
    # 續一百四十五:原本每個讀取都沒有邊界。截短的 script 會 IndexError(`script[pos]`)、
    # struct.error(op 7/8/9 的 unpack_from,不是 ValueError,`cmd_frames` 接不到),
    # 更糟的是 op 1 / 3 / 5 / 9 的切片指派拿到較短的切片會**靜默改變 bytearray 長度**
    # (9 份資源各幀前 120 個前綴裡有 36 次 framebuf 變短而沒有任何例外)。
    pos = 0
    for _ in range(cmd_count):
        _need(script, pos, 1)
        op = script[pos]; pos += 1
        if op == 0:  # palette fill
            _need(script, pos, 1)
            v = script[pos]; pos += 1
            for i in range(PALETTE_BYTES):
                palette[i] = v
        elif op == 1:  # palette literal load
            _need(script, pos, PALETTE_BYTES)
            palette[0:PALETTE_BYTES] = script[pos:pos + PALETTE_BYTES]
            pos += PALETTE_BYTES
        elif op == 2:  # palette RLE
            pos = rle_2mode(script, pos, palette, 0, PALETTE_BYTES)
        elif op == 3:  # palette 局部貼補
            _need(script, pos, 1)
            n = script[pos]; pos += 1
            for _ in range(n):
                _need(script, pos, 2)
                idx = script[pos]; pos += 1
                cnt = script[pos]; pos += 1
                off, length = idx * 3, cnt * 3
                _need(script, pos, length)
                # 續一百四十五:idx * 3 + cnt * 3 可以超過 768(損壞資料;原版是寫過 malloc(768) 的尾端)。
                # 照 op 8 / 9 截在 FRAME_BYTES 的做法截在 PALETTE_BYTES,否則切片指派會把 palette 撐長。
                end = min(off + length, PALETTE_BYTES)
                palette[off:end] = script[pos:pos + (end - off)]
                pos += length
        elif op == 4:  # framebuffer fill
            _need(script, pos, 1)
            v = script[pos]; pos += 1
            for i in range(FRAME_BYTES):
                framebuf[i] = v
        elif op == 5:  # framebuffer literal load
            _need(script, pos, FRAME_BYTES)
            framebuf[0:FRAME_BYTES] = script[pos:pos + FRAME_BYTES]
            pos += FRAME_BYTES
        elif op == 6:  # framebuffer RLE(主力全螢幕解碼)
            pos = rle_2mode(script, pos, framebuf, 0, FRAME_BYTES)
        elif op == 7:  # 單點繪製 ×N
            _need(script, pos, 2)
            n = struct.unpack_from('<H', script, pos)[0]; pos += 2
            for _ in range(n):
                _need(script, pos, 3)
                off = struct.unpack_from('<H', script, pos)[0]; pos += 2
                val = script[pos]; pos += 1
                if 0 <= off < FRAME_BYTES:
                    framebuf[off] = val
        elif op == 8:  # 區段填色 ×N
            _need(script, pos, 2)
            n = struct.unpack_from('<H', script, pos)[0]; pos += 2
            for _ in range(n):
                _need(script, pos, 4)
                off = struct.unpack_from('<H', script, pos)[0]; pos += 2
                length = script[pos]; pos += 1
                val = script[pos]; pos += 1
                end = min(off + length, FRAME_BYTES)
                for i in range(off, end):
                    framebuf[i] = val
        elif op == 9:  # 區段貼圖 ×N
            _need(script, pos, 2)
            n = struct.unpack_from('<H', script, pos)[0]; pos += 2
            for _ in range(n):
                _need(script, pos, 3)
                off = struct.unpack_from('<H', script, pos)[0]; pos += 2
                length = script[pos]; pos += 1
                # 貼圖被畫面尾端截掉時照樣跳過 length bytes,所以要的是 length 而不是 end - off。
                _need(script, pos, length)
                end = min(off + length, FRAME_BYTES)
                framebuf[off:end] = script[pos:pos + (end - off)]
                pos += length
        else:
            raise BadOpcode(f"未知 opcode {op} @ script pos {pos - 1}")
    return pos


def parse_header(data):
    # 續一百四十四:原本沒有長度檢查,短於檔頭的輸入(含 ANI.DAT 第 10 項、長度 0 的
    # 終止符 ANI_009.bin)丟原始 struct.error,呼叫端分不出「不是 ANI 檔」與「工具有 bug」。
    if len(data) < HEADER_BYTES:
        raise NotANI(f"只有 {len(data)} bytes,放不下 0x{HEADER_BYTES:X} 檔頭")
    banner = data[0:0x50].decode('ascii', 'replace')
    title = data[0x51:0xA1].decode('ascii', 'replace').strip()
    # 續一百四十五:幀數是**有號** 16-bit —— 原版 `0x0204ff` `movsx eax, word [esp+0x10]`、
    # `0x020506` `jge` 有號比較,≥ 0x8000 的值是負數、一幀都不播;range(負數) 同樣是空的。
    frame_count = struct.unpack_from('<h', data, 0xA5)[0]
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
    # 續一百四十四:幀記錄被截在檔尾時原本丟 struct.error。改成讀不到 8-byte 記錄就停
    # (降級、不崩,同 decode_figani.parse_anim);記錄讀得到而 script 被截短的那一幀照舊交出
    # 截短的 script,由 run_vm 的呼叫端處理。不另算「最多幾幀」的上限 —— 那種算式在格式正確的
    # 檔上看不出差別,窮舉突變會留下等價突變(續一百四十三)。
    pos = start
    for i in range(frame_count):
        try:
            comp_size, cmd_count, r0, r1 = struct.unpack_from('<HHHH', data, pos)
        except struct.error:
            return
        pos += 8
        script = data[pos:pos + comp_size]
        pos += comp_size
        yield i, comp_size, cmd_count, r0, r1, script


def frames_bytes(data: bytes) -> list[tuple]:
    """解檔頭並把幀記錄全部讀出來(bytes 進、串列出)。

    `verify_truncation_robustness` 的登錄表只收吃 bytes、呼叫即執行的函式;
    `iter_frames` 是 generator,只呼叫不迭代等於什麼都沒跑。

    Args:
        data: 一份 ANI 資源(AFM 檔)的完整內容。

    Returns:
        `iter_frames` 逐幀交出的 tuple 組成的串列;幀記錄被截斷時只含讀得到的幀。

    Raises:
        NotANI: 資料短於 0xAD 檔頭。
    """
    hdr = parse_header(data)
    return list(iter_frames(data, hdr['frame_count']))


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
    try:
        if argv[1] == 'info':
            cmd_info(argv[2])
        elif argv[1] == 'frames':
            cmd_frames(argv[2], argv[3])
        else:
            print(__doc__)
            return 1
    except NotANI as e:
        print(f"{argv[2]}: 不是 ANI 檔({e})")
        return 1
    return 0


if __name__ == '__main__':
    sys.exit(main(sys.argv))
