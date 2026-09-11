#!/usr/bin/env python3
"""炎龍騎士團2 — XMIDI 音樂解析與轉標準 MIDI(第 2 輪)。

原版用 Miles Sound System(AIL v3),音樂為 **XMIDI**(.XMI)格式,封裝於 FDMUS.DAT。
本工具:
  1. 解析 XMI 的 IFF chunk(FORM/XDIR/INFO/CAT/XMID/TIMB/EVNT)。
  2. 萃取每首曲的樂器(TIMB)、聲道、音符數、時長等「可分析」資訊。
  3. 把 EVNT 事件流轉成標準 MIDI(SMF type 0),處理 XMIDI 特有的:
       - 間隔延時(interval delay):連續 <0x80 的 byte 累加。
       - Note On 內嵌持續長度(VLQ)→ 轉成排程的 Note Off。
       - tempo / controller / program change / meta 直通。

XMIDI 與標準 MIDI 兩大差異:
  (a) 延時編碼不同(XMIDI 用累加間隔,非 MIDI 的 variable-length)。
  (b) Note On 自帶 duration,不發 Note Off。

用法:
    python3 xmi2mid.py <xmi資源.bin> <out.mid>      # 轉換 + 印分析
    python3 xmi2mid.py --info <xmi資源.bin>          # 只分析不輸出
    python3 xmi2mid.py --batch <FDMUS解包目錄> <out目錄>

時值:輸出 PPQN=60(多數 XMI 轉換器慣例);XMIDI 自帶 tempo meta 事件直通。
不依賴第三方套件。
"""
import sys
import os
import struct
import glob

PPQN = 60  # 輸出 MIDI 的每四分音符 tick 數(XMI 慣例)


def be32(d, o):
    return struct.unpack_from(">I", d, o)[0]


def iter_chunks(d, start, end):
    """走訪 IFF chunk;yield (tag, data_offset, length)。處理 FORM/CAT 的 type。"""
    i = start
    while i + 8 <= end:
        tag = d[i:i + 4]
        ln = be32(d, i + 4)
        body = i + 8
        if tag in (b"FORM", b"CAT ", b"LIST"):
            # next 4 = form type;遞迴交給呼叫端
            yield (tag, body, ln)
            i = body + ((ln + 1) & ~1)
        else:
            yield (tag, body, ln)
            i = body + ((ln + 1) & ~1)


def find_evnt_timb(d):
    """回傳 [(timb_bytes, evnt_off, evnt_len), ...](每首曲一組)。"""
    seqs = []
    # 掃描所有 EVNT;其前最近的 TIMB 視為該曲樂器表
    i = 0
    last_timb = b""
    n = len(d)
    while i + 8 <= n:
        tag = d[i:i + 4]
        if tag == b"TIMB":
            ln = be32(d, i + 4)
            last_timb = d[i + 8:i + 8 + ln]
            i += 8 + ((ln + 1) & ~1)
        elif tag == b"EVNT":
            ln = be32(d, i + 4)
            seqs.append((last_timb, i + 8, ln))
            last_timb = b""
            i += 8 + ((ln + 1) & ~1)
        else:
            i += 1  # XMI 內含非 chunk 對齊,逐 byte 找
    return seqs


def selftest():
    """`find_evnt_timb` 的危險在於它**逐 byte 掃描**找 tag(因為 XMI 內含非
    chunk 對齊),所以任何 4 個 byte 剛好等於 `TIMB`/`EVNT` 都會被當成 chunk。
    這種掃描器不會崩,只會安靜地多認或少認一首曲子。

    所以這裡驗的是:合成資料的手算結果、TIMB 只綁到**其後最近**的 EVNT、
    以及真實 FDMUS 的曲目數與 timb 長度。
    """
    import os
    if hasattr(sys.stdout, "reconfigure"):
        sys.stdout.reconfigure(encoding="utf-8")
        sys.stderr.reconfigure(encoding="utf-8")
    fails = []

    def chunk(tag, body):
        return tag + struct.pack(">I", len(body)) + body + (b"\x00" if len(body) & 1 else b"")

    print("(1) 手算:TIMB 之後的第一個 EVNT 取到那份 timb,第二個 EVNT 取不到")
    blob = (chunk(b"TIMB", b"\x01\x02\x03\x04")
            + chunk(b"EVNT", b"\xAA" * 6)
            + chunk(b"EVNT", b"\xBB" * 4))
    got = find_evnt_timb(blob)
    ok1 = (len(got) == 2 and got[0][0] == b"\x01\x02\x03\x04" and got[1][0] == b""
           and got[0][2] == 6 and got[1][2] == 4)
    print(f"    {'PASS' if ok1 else 'FAIL'}: {len(got)} 首,timb 長度 "
          f"{[len(t) for t, _o, _l in got]},evnt 長度 {[l for _t, _o, l in got]}")
    if not ok1:
        fails.append(f"TIMB/EVNT 綁定錯誤:{[(len(t), o, l) for t, o, l in got]}")

    print("\n(2) 手算:沒有前置 TIMB 的 EVNT,timb 必須是空的(不能沿用更早的)")
    blob2 = chunk(b"EVNT", b"\xCC" * 4) + chunk(b"TIMB", b"\x09") + chunk(b"EVNT", b"\xDD" * 2)
    got2 = find_evnt_timb(blob2)
    ok2 = len(got2) == 2 and got2[0][0] == b"" and got2[1][0] == b"\x09"
    print(f"    {'PASS' if ok2 else 'FAIL'}: timb 長度 {[len(t) for t, _o, _l in got2]}"
          f"(應為 [0, 1])")
    if not ok2:
        fails.append(f"無前置 TIMB 的處理錯誤:{[len(t) for t, _o, _l in got2]}")

    print("\n(2b) iter_chunks 的輸出本身 + find_evnt_timb 的位移、步長與尾端邊界")
    # 2026-09-11 窮舉突變測試:iter_chunks 只被 (3) 以「不崩潰」測過,**它產出的 chunk
    # 序列從來沒被斷言**;find_evnt_timb 也沒驗過 EVNT 的 body 位移。手算:
    #   FORM(4) @0 -> body 8;TIMB(3,奇數補 1) @12 -> body 20;EVNT(2) @24 -> body 32;
    #   ZERO(0) @34 -> body 42 = 檔尾(header 恰好占滿最後 8 bytes,釘住 `i + 8 <= end`)。
    ic = chunk(b"FORM", b"XMID") + chunk(b"TIMB", b"\x01\x02\x03") + chunk(b"EVNT", b"\xAA\xBB") \
        + chunk(b"ZERO", b"")
    got_ic = list(iter_chunks(ic, 0, len(ic)))
    want_ic = [(b"FORM", 8, 4), (b"TIMB", 20, 3), (b"EVNT", 32, 2), (b"ZERO", 42, 0)]
    b2 = {"iter_chunks 序列": got_ic == want_ic,
          # TIMB(4 bytes) 占 12 bytes,EVNT 的 body 在 12+8=20
          "EVNT body 位移": got[0][1] == 20,
          # 前面墊 1 byte 讓 tag 落在奇數位移:掃描步長若不是 1 就會整個跳過
          "奇數位移的 EVNT": [s[1] for s in find_evnt_timb(b"\x00" + chunk(b"EVNT", b"\xAA" * 4))] == [9],
          # 長度 0 的 EVNT 恰好是整個輸入:header 8 bytes 占滿,`i + 8 <= n` 的邊界
          "尾端恰 8 bytes 的 EVNT": len(find_evnt_timb(chunk(b"EVNT", b""))) == 1}
    ok2b = all(b2.values())
    print(f"    {'PASS' if ok2b else 'FAIL'}: " + "、".join(f"{k}={v}" for k, v in b2.items())
          + ("" if b2["iter_chunks 序列"] else f";實得 {got_ic}"))
    if not ok2b:
        fails.append(f"chunk 走訪/掃描不對:{[k for k, v in b2.items() if not v]}")

    print("\n(3) 截斷不得崩潰:逐一掃過每個前綴長度")
    bad = {}
    for cut in range(len(blob) + 1):
        try:
            find_evnt_timb(blob[:cut])
            list(iter_chunks(blob[:cut], 0, cut))
        except Exception as exc:                              # noqa: BLE001
            bad[type(exc).__name__] = bad.get(type(exc).__name__, 0) + 1
    ok3 = not bad
    print(f"    {'PASS' if ok3 else 'FAIL'}: {len(blob) + 1} 個前綴"
          + ("全部安全" if ok3 else f",例外 {bad}"))
    if not ok3:
        fails.append(f"截斷時丟出例外:{bad}")

    print("\n(4) 真實 FDMUS:有曲目的檔案必須各解出 1 首,且 timb 長度合理")
    root = os.path.dirname(os.path.dirname(os.path.abspath(__file__)))
    d = os.path.join(root, "extracted", "raw", "FDMUS")
    withseq = badlen = 0
    if os.path.isdir(d):
        for fn in sorted(os.listdir(d)):
            s = find_evnt_timb(open(os.path.join(d, fn), "rb").read())
            if not s:
                continue
            withseq += 1
            for timb, off, ln in s:
                if not (0 < len(timb) <= 256 and ln > 0):
                    badlen += 1
    ok4 = withseq > 10 and badlen == 0
    print(f"    {'PASS' if ok4 else 'FAIL'}: {withseq} 個檔案有曲目,"
          f"timb/evnt 長度異常 {badlen}")
    if not ok4:
        fails.append(f"真實 FDMUS:{withseq} 個有曲目、{badlen} 個長度異常")

    print("\n(5) 非恆真控制:純雜訊裡不應該憑空冒出曲目")
    noise = bytes((i * 71 + 13) & 0xFF for i in range(4096))
    n5 = len(find_evnt_timb(noise))
    ok5 = n5 == 0
    print(f"    {'PASS' if ok5 else 'FAIL'}: 4096 bytes 雜訊 -> {n5} 首(應為 0)")
    if not ok5:
        fails.append(f"雜訊中誤認 {n5} 首曲 —— 逐 byte 掃描的偽陽性")

    if fails:
        print("\nSELFTEST FAILED:")
        for f in fails:
            print("  -", f)
        return 1
    print("\n--selftest passed(TIMB/EVNT 綁定手算 ×2 + 截斷窮舉 + 真實 FDMUS + "
          "雜訊非恆真控制)。")
    return 0


def parse_evnt(d, off, ln):
    """解析一段 EVNT → 絕對時間事件清單。回傳 (events, stats)。
    events: list of (abs_tick, midi_bytes)。"""
    i = off
    end = off + ln
    t = 0
    events = []
    pending_off = []  # (abs_tick, [note_off bytes])
    stats = {"notes": 0, "channels": set(), "programs": {}, "max_tick": 0}

    def read_vlq(p):
        v = 0
        while True:
            b = d[p]; p += 1
            v = (v << 7) | (b & 0x7f)
            if not (b & 0x80):
                break
        return v, p

    while i < end:
        # XMIDI 間隔延時:連續 <0x80 累加
        while i < end and d[i] < 0x80:
            t += d[i]
            i += 1
        if i >= end:
            break
        status = d[i]; i += 1
        hi = status & 0xF0
        ch = status & 0x0F
        if hi == 0x90:  # Note On + duration
            note = d[i]; vel = d[i + 1]; i += 2
            dur, i = read_vlq(i)
            events.append((t, [status, note, vel]))
            pending_off.append((t + dur, [0x80 | ch, note, 0x40]))
            stats["notes"] += 1
            stats["channels"].add(ch)
        elif hi in (0x80, 0xA0, 0xB0, 0xE0):  # 2 data bytes
            events.append((t, [status, d[i], d[i + 1]])); i += 2
            stats["channels"].add(ch)
        elif hi in (0xC0, 0xD0):  # 1 data byte
            events.append((t, [status, d[i]]))
            if hi == 0xC0:
                stats["programs"][ch] = d[i]
            i += 1
        elif status == 0xFF:  # meta
            mtype = d[i]; i += 1
            mlen, i = read_vlq(i)
            mdata = d[i:i + mlen]; i += mlen
            events.append((t, [0xFF, mtype, mlen] + list(mdata)))
            if mtype == 0x2F:
                break
        elif status in (0xF0, 0xF7):  # sysex
            slen, i = read_vlq(i)
            events.append((t, [status, slen] + list(d[i:i + slen]))); i += slen
        else:
            # 未知,停止以免亂解
            break
    # 併入 note-off
    for tick, mb in pending_off:
        events.append((tick, mb))
    events.sort(key=lambda e: e[0])
    stats["max_tick"] = events[-1][0] if events else 0
    stats["channels"] = sorted(stats["channels"])
    return events, stats


def write_vlq(v):
    out = [v & 0x7f]
    v >>= 7
    while v:
        out.insert(0, (v & 0x7f) | 0x80)
        v >>= 7
    return bytes(out)


def events_to_smf(events):
    track = bytearray()
    last = 0
    for tick, mb in events:
        delta = tick - last
        last = tick
        track += write_vlq(delta)
        track += bytes(b & 0xFF for b in mb)
    if not (events and events[-1][1][:2] == [0xFF, 0x2F]):
        track += write_vlq(0) + bytes([0xFF, 0x2F, 0x00])
    hdr = b"MThd" + struct.pack(">IHHH", 6, 0, 1, PPQN)
    trk = b"MTrk" + struct.pack(">I", len(track)) + bytes(track)
    return hdr + trk


def convert(d, out_path=None, verbose=True):
    seqs = find_evnt_timb(d)
    results = []
    for idx, (timb, eo, el) in enumerate(seqs):
        events, stats = parse_evnt(d, eo, el)
        # TIMB:每 2 byte = (patch, bank) 或 (patch, ch);記錄用到的樂器
        instruments = [timb[j] for j in range(0, len(timb), 2)] if timb else []
        dur_beats = stats["max_tick"] / PPQN
        results.append({"seq": idx, "notes": stats["notes"],
                        "channels": stats["channels"], "programs": stats["programs"],
                        "instruments": instruments, "ticks": stats["max_tick"],
                        "beats": round(dur_beats, 1)})
        if out_path:
            smf = events_to_smf(events)
            p = out_path if len(seqs) == 1 else out_path.replace(".mid", f"_{idx}.mid")
            open(p, "wb").write(smf)
    if verbose:
        for r in results:
            print(f"  曲#{r['seq']}: 音符={r['notes']} 聲道={r['channels']} "
                  f"樂器數={len(r['instruments'])} 長度={r['beats']}拍")
    return results


def main(argv):
    if len(argv) == 2 and argv[1] == '--selftest':
        return selftest()
    if len(argv) < 2:
        print(__doc__); return 1
    if argv[1] == "--info":
        d = open(argv[2], "rb").read()
        print(os.path.basename(argv[2]), f"({len(d)} B)")
        convert(d, None)
        return 0
    if argv[1] == "--batch":
        src, out = argv[2], argv[3]
        os.makedirs(out, exist_ok=True)
        ntracks = 0
        for f in sorted(glob.glob(os.path.join(src, "*.bin"))):
            d = open(f, "rb").read()
            if d[:4] != b"FORM":
                continue
            base = os.path.splitext(os.path.basename(f))[0]
            print(base)
            r = convert(d, os.path.join(out, base + ".mid"))
            ntracks += len(r)
        print(f"\n共輸出 {ntracks} 首 MIDI -> {out}")
        return 0
    d = open(argv[1], "rb").read()
    out = argv[2] if len(argv) > 2 else None
    convert(d, out)
    if out:
        print(f"-> {out}")
    return 0


if __name__ == "__main__":
    sys.exit(main(sys.argv))
