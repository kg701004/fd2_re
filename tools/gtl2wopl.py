#!/usr/bin/env python3
"""炎龍騎士團2 — Miles AIL2 Global Timbre Library(.AD/.OPL)→ WOPL v3 bank 轉換器。

FD2 原生音效卡驅動預設是 **Sound Blaster**(見 `MDI.INI`:DRIVER=SBLASTER.MDI,IO 220h),
SBLASTER.MDI/ADLIB.MDI 走 OPL2、OPL3.MDI 走 OPL3;全域音色庫是 `SAMPLE.AD`(OPL2)/
`SAMPLE.OPL`(OPL3,本作與 .AD 位元組相同,無 4-op 樂器)。本工具把該音色庫轉成
libADLMIDI(adlmidiplay/ADLMIDI)可讀的 WOPL 格式,讓 XMI 音樂能用**遊戲自帶音色**
渲染成 FM(AdLib/Sound Blaster)版 BGM,而非套用通用 GM 音色包(會失真)。

格式依據(逐位元組核實,非猜測):
  - AIL GTL 來源格式(.AD/.OPL):
    OPL3BankEditor Specifications/AILBANK.TXT
    https://github.com/Wohlstand/OPL3BankEditor/blob/master/Specifications/AILBANK.TXT
  - WOPL v3 目的格式:libADLMIDI src/wopl/wopl_file.c 的
    WOPL_parseInstrument / WOPL_writeInstrument(實際消費端,非規格書猜測)
    https://github.com/Wohlstand/libADLMIDI/blob/master/src/wopl/wopl_file.c
  - Operator 順序(WOPL operators[0]=Carrier1 / [1]=Modulator1)對照
    OPL3BankEditor src/bank.h 的 #define CARRIER1 0 / MODULATOR1 1,
    與 src/FileFormats/format_ail2_gtl.cpp 的
    ins.setAVEKM(MODULATOR1, idata[1]) / ins.setAVEKM(CARRIER1, idata[7]) 交叉驗證
    (AIL op0=register 0x20 群組=傳統 OPL Modulator;AIL op1=register 0x23 群組=Carrier)。

AIL GTL 2-op 樂器 body(去掉 size+transpose 後,11 bytes):
  [0]op0_misc(0x20) [1]op0_scale(0x40) [2]op0_AD(0x60) [3]op0_SR(0x80) [4]op0_WF(0xE0)
  [5]feedbackConnection(0xC0)
  [6]op1_misc(0x23) [7]op1_scale(0x43) [8]op1_AD(0x63) [9]op1_SR(0x83) [10]op1_WF(0xE3)

FD2 的 SAMPLE.AD 全為 2-op(162 筆:bank0 melodic 128 筆全滿 + bank127 percussion 34 筆),
4-op 未在本作出現過,故本工具只實作 2-op 轉換(遇到 4-op 樂器會丟例外,不悄悄跳過)。

用法:
    python3 gtl2wopl.py <SAMPLE.AD 或 .OPL> <out.wopl>
"""
import struct
import sys

VOLUME_AIL = 7          # OPL3BankEditor src/bank.h enum VolumesScale::VOLUME_AIL
WOPL_INS_FIXED_NOTE = 0x40
WOPL_INS_IS_BLANK = 0x04


def parse_gtl(path):
    """解析 GTL 索引(programNumber, bankNumber, fileOffset)三元組,直到 0xFF/0xFF 結束。"""
    with open(path, 'rb') as f:
        data = f.read()
    heads = []
    off = 0
    while off + 6 <= len(data):
        patch, bank = data[off], data[off + 1]
        foff = struct.unpack_from('<I', data, off + 2)[0]
        off += 6
        if patch == 0xFF and bank == 0xFF:
            break
        heads.append((patch, bank, foff))

    # 2026-09-08:原本沒有任何邊界檢查,結果有兩種壞行為。
    #   * 空檔或不足 6 bytes:迴圈一次都不跑,**靜默回空 dict** —— 呼叫端會以為
    #     這份 SAMPLE.AD 沒有樂器,而不是「檔案是壞的」。
    #   * 截斷檔:下面的 unpack_from 丟原始 struct.error(「需要至少 N bytes」),
    #     呼叫端無法分辨「不是 GTL」與「這支工具有 bug」。
    # 兩者都改成有意義的 ValueError。
    if not heads:
        raise ValueError(
            f"{path}: 解不出任何 GTL 索引項(檔案 {len(data)} bytes)——"
            "空的目錄幾乎必然代表檔案是壞的,不是這份素材真的沒有樂器")

    insts = {}
    for patch, bank, foff in heads:
        if foff + 2 > len(data):
            raise ValueError(
                f"{path}: patch={patch} bank={bank} 的 fileOffset {foff} "
                f"超出檔案大小 {len(data)}")
        size = struct.unpack_from('<H', data, foff)[0]
        if foff + size > len(data):
            raise ValueError(
                f"{path}: patch={patch} bank={bank} 宣稱 size={size},"
                f"從 {foff} 起超出檔案大小 {len(data)}")
        if size != 0x0E:
            raise NotImplementedError(
                f"4-op 樂器(size=0x{size:02x}, patch={patch} bank={bank})不在 FD2 SAMPLE.AD "
                "中出現過,未實作轉換 —— 別悄悄跳過,先確認這是不是新素材再擴充")
        body = data[foff + 2:foff + size]
        transpose = body[0]
        insts[(bank, patch)] = dict(transpose=transpose, raw=body[1:])  # raw: 11 bytes
    return insts


def selftest():
    """釘住 SAMPLE.AD 的目錄形狀 —— 那是一個**已記錄的 RE 結論**,不是隨便一個數字。

    doc16 曾沿用「TIMB 編號就是 MT-32 program number」的說法,後來實測推翻:
    SAMPLE.AD 是一張 162 筆的目錄,鍵是 `(bank<<8)|patch`,形狀是
    **bank 0 的 128 筆(patch 0..127)+ bank 127 的 34 筆(patch 35..75)**
    —— 一個 GM 形狀的空間。這裡把那個結論變成每次都會重跑的檢查。

    另外兩件事在同一輪修掉:空檔原本**靜默回空 dict**(呼叫端會以為這份素材
    沒有樂器,而不是檔案壞了),截斷檔丟原始 struct.error。
    """
    import collections
    import os
    import tempfile
    if hasattr(sys.stdout, "reconfigure"):
        sys.stdout.reconfigure(encoding="utf-8")
        sys.stderr.reconfigure(encoding="utf-8")
    fails = []
    root = os.path.dirname(os.path.dirname(os.path.abspath(__file__)))
    ad = os.path.join(root, "org_game", "炎龍騎士團", "FLAME2", "SAMPLE.AD")

    if os.path.isfile(ad):
        print("(1) 真實 SAMPLE.AD 的目錄形狀必須符合已記錄的 RE 結論")
        insts = parse_gtl(ad)
        banks = collections.Counter(b for b, _ in insts)
        lo = sorted(p for b, p in insts if b == 0)
        hi = sorted(p for b, p in insts if b == 127)
        ok1 = (len(insts) == 162 and banks.get(0) == 128 and banks.get(127) == 34
               and lo == list(range(128)) and min(hi) == 35 and max(hi) == 75)
        print(f"    {'PASS' if ok1 else 'FAIL'}: {len(insts)} 個樂器,"
              f"bank 分布 {dict(banks)},bank0 patch {lo[0]}..{lo[-1]},"
              f"bank127 patch {min(hi)}..{max(hi)}")
        if not ok1:
            fails.append(f"目錄形狀與記錄不符:{len(insts)} 個,{dict(banks)}")

        print("\n(2) 每個樂器的 raw 必須是 11 bytes(size=0x0E 的 2-op 格式)")
        badlen = [(k, len(v["raw"])) for k, v in insts.items() if len(v["raw"]) != 11]
        ok2 = not badlen
        print(f"    {'PASS' if ok2 else 'FAIL'}: {len(insts)} 個"
              + ("全部 11 bytes" if ok2 else f",長度異常 {badlen[:3]}"))
        if not ok2:
            fails.append(f"raw 長度異常:{badlen[:3]}")
    else:
        print("    SKIP: 找不到 org_game 的 SAMPLE.AD")

    print("\n(3) 回歸:空檔以前**靜默回空 dict**,現在必須丟有意義的錯")
    with tempfile.TemporaryDirectory() as td:
        for label, blob in (("空檔", b""), ("只有 3 bytes", b"\x00\x00\x00"),
                            ("只有結束標記", b"\xff\xff\x00\x00\x00\x00")):
            p = os.path.join(td, "e.ad")
            open(p, "wb").write(blob)
            try:
                got = parse_gtl(p)
                print(f"    FAIL: 「{label}」回傳 {got}(應丟錯)")
                fails.append(f"{label} 靜默回傳 {got}")
            except ValueError:
                print(f"    PASS: 「{label}」-> ValueError")
            except Exception as exc:                          # noqa: BLE001
                print(f"    FAIL: 「{label}」丟出 {type(exc).__name__}")
                fails.append(f"{label} 丟出 {type(exc).__name__}")

    print("\n(4) 回歸:fileOffset 超出檔尾必須丟 ValueError,而非原始 struct.error")
    with tempfile.TemporaryDirectory() as td:
        p = os.path.join(td, "oob.ad")
        # 一筆索引 patch=0 bank=0 指到 0x99999,接結束標記
        blob = (struct.pack("<BBI", 0, 0, 0x99999)
                + struct.pack("<BBI", 0xFF, 0xFF, 0))
        open(p, "wb").write(blob)
        try:
            parse_gtl(p)
            ok4, why = False, "沒有被擋下"
        except ValueError as exc:
            ok4, why = True, str(exc)[:60]
        except Exception as exc:                              # noqa: BLE001
            ok4, why = False, f"丟出 {type(exc).__name__}"
    print(f"    {'PASS' if ok4 else 'FAIL'}: {why}")
    if not ok4:
        fails.append(f"越界 fileOffset:{why}")

    print("\n(5) 非恆真控制:上面全都丟錯也會通過,所以確認合法檔仍解得出樂器")
    ok5 = os.path.isfile(ad) and len(parse_gtl(ad)) > 100
    print(f"    {'PASS' if ok5 else 'FAIL'}: 真實 SAMPLE.AD 解出 "
          f"{len(parse_gtl(ad)) if os.path.isfile(ad) else 0} 個")
    if not ok5:
        fails.append("合法檔案解不出樂器")

    print("\n(6) 索引掃描恰好 6 bytes、fileOffset 的 +2 邊界、transpose 取 body[0]")
    # 2026-09-11 窮舉突變測試:`off + 6 <= len`、`foff + 2 > len`、`body[0]` 改掉都逃掉 ——
    # 真實 SAMPLE.AD 沒有卡在這些邊界上,transpose 值也從沒被斷言。以錯誤訊息分辨
    # 是哪一道守衛擋下。
    import tempfile as _tf

    def gtl(blob):
        with _tf.NamedTemporaryFile(suffix=".ad", delete=False) as f:
            f.write(blob)
        try:
            return parse_gtl(f.name)
        except (ValueError, NotImplementedError) as exc:
            return str(exc)
        finally:
            os.unlink(f.name)
    end_mark = struct.pack("<BBI", 0xFF, 0xFF, 0)
    inst = struct.pack("<H", 0x0E) + bytes([7]) + bytes(range(11))
    good = gtl(struct.pack("<BBI", 1, 0, 12) + end_mark + inst)
    one_head = gtl(struct.pack("<BBI", 1, 0, 99))                      # 恰好 6 bytes 一筆
    size_edge = gtl(struct.pack("<BBI", 1, 0, 12) + end_mark + struct.pack("<H", 0x0E))
    b6 = {"transpose 與 raw": good == {(0, 1): {"transpose": 7, "raw": bytes(range(11))}},
          "恰好 6 bytes 的索引也要讀": isinstance(one_head, str) and "fileOffset" in one_head,
          "size 欄恰好在檔尾": isinstance(size_edge, str) and "宣稱 size" in size_edge}
    ok6 = all(b6.values())
    print(f"    {'PASS' if ok6 else 'FAIL'}: " + "、".join(f"{k}={v}" for k, v in b6.items()))
    if not ok6:
        fails.append(f"GTL 索引/邊界/transpose 不對:{[k for k, v in b6.items() if not v]}")

    if fails:
        print("\nSELFTEST FAILED:")
        for f in fails:
            print("  -", f)
        return 1
    print("\n--selftest passed(目錄形狀釘住已記錄結論 + raw 長度 + 空檔/越界回歸 + "
          "非恆真控制)。")
    return 0


def _blank_instrument():
    d = bytearray(66)
    d[39] = WOPL_INS_IS_BLANK
    return bytes(d)


def _build_instrument(entry, is_perc):
    b = entry['raw']
    transpose = entry['transpose']
    d = bytearray(66)
    if is_perc:
        # AILBANK.TXT:bank 127 的 transpose 語意是「絕對音高」(打擊樂器固定音高)
        # -> 對應 WOPL 的 percussion_key_number + Fixed-note flag。
        d[38] = transpose & 0xFF
        d[39] = WOPL_INS_FIXED_NOTE
    else:
        # 旋律樂器的 transpose 是相對音高位移 -> note_offset1(signed BE16)。
        note_offset1 = transpose if transpose < 128 else transpose - 256
        struct.pack_into('>h', d, 32, note_offset1)
    d[40] = b[5]   # fb_conn1_C0 <- AIL feedbackConnection(register 0xC0)
    d[41] = 0      # fb_conn2_C0:2-op 無第二聲部
    # operators[0]=Carrier1  <- AIL op1(register 0x23 群組, raw[6:11])
    d[42 + 0 * 5:42 + 0 * 5 + 5] = bytes(b[6:11])
    # operators[1]=Modulator1 <- AIL op0(register 0x20 群組, raw[0:5])
    d[42 + 1 * 5:42 + 1 * 5 + 5] = bytes(b[0:5])
    # operators[2]/[3](Carrier2/Modulator2):2-op 樂器不使用,留 0
    # delay_on_ms/delay_off_ms 留 0,交給 player 自動判斷
    return bytes(d)


def build_wopl(ad_path, out_path, bank_label="FD2 SAMPLE.AD (SB/AdLib OPL2)"):
    insts = parse_gtl(ad_path)

    melodic = [_blank_instrument() for _ in range(128)]
    percussion = [_blank_instrument() for _ in range(128)]
    n_mel = n_perc = 0
    for (bank, patch), entry in insts.items():
        if bank == 127:
            if 0 <= patch < 128:
                percussion[patch] = _build_instrument(entry, is_perc=True)
                n_perc += 1
        elif bank == 0:
            if 0 <= patch < 128:
                melodic[patch] = _build_instrument(entry, is_perc=False)
                n_mel += 1
        else:
            print(f"[警告] 忽略非 bank0/127 的樂器 bank={bank} patch={patch}"
                  "(FD2 未見過此 bank,若真出現需擴充多 bank 支援)", file=sys.stderr)

    out = bytearray()
    out += b"WOPL3-BANK\x00"
    out += struct.pack('<H', 3)        # version = 3
    out += struct.pack('>H', 1)        # melodic bank 數
    out += struct.pack('>H', 1)        # percussion bank 數
    out += bytes([0x03])               # opl_flags:deep tremolo + deep vibrato(AIL 音色庫慣例)
    out += bytes([VOLUME_AIL])         # volume_model = AIL

    def bank_meta(name):
        nb = name.encode('utf-8')[:31]
        return nb + b'\x00' * (32 - len(nb)) + bytes([0, 0])  # lsb=0, msb=0

    out += bank_meta(bank_label)
    out += bank_meta(bank_label + " -Percussion")
    for ins in melodic:
        out += ins
    for ins in percussion:
        out += ins

    with open(out_path, 'wb') as f:
        f.write(out)

    print(f"寫出 {out_path}:{len(out)} bytes,melodic 樂器 {n_mel}/128,percussion 樂器 {n_perc}/128")
    return n_mel, n_perc


if __name__ == '__main__':
    if len(sys.argv) == 2 and sys.argv[1] == '--selftest':
        sys.exit(selftest())
    if len(sys.argv) < 3:
        print(__doc__)
        sys.exit(1)
    build_wopl(sys.argv[1], sys.argv[2])
