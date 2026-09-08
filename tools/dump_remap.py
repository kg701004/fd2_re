#!/usr/bin/env python3
"""炎龍騎士團2 — 調色 remap LUT 解析與套用(陣營 / 狀態著色)。

`FDOTHER.DAT` 資源 #3 = `"LMI1"` 容器,內含 23 張 256-byte remap LUT。
場景單位(24×24)繪製時(EXE `0x4EB52`)以 `LUT[原始像素索引]` 重新著色,
做出「已行動變灰、敵我染色、夜戰色調」等效果(見 10-sprite-rendering-camp-and-state)。

LMI1 格式: magic "LMI1"(4) + uint16 count + uint32[count] offset(相對檔頭) + 各 256-byte LUT。

用法:
    python3 dump_remap.py list  <FDOTHER_003.bin>
    python3 dump_remap.py apply <FDOTHER_003.bin> <palette.bin> <sprite像素.raw> <W> <H> <out目錄>
"""
import sys
import os
import struct
# 2026-09-08:PIL 延遲 import(parse_lmi 不需要 Pillow;模組層 hard import 會讓
# 整支工具在沒有 Pillow 的 WSL python3 下不可用)。

if hasattr(sys.stdout, "reconfigure"):
    sys.stdout.reconfigure(encoding="utf-8")
    sys.stderr.reconfigure(encoding="utf-8")


def parse_lmi(path):
    d = open(path, "rb").read()
    if d[:4] != b"LMI1":
        raise ValueError("非 LMI1 容器")
    n = struct.unpack_from("<H", d, 4)[0]
    # 2026-09-08:原本沒有這個檢查,目錄宣稱的筆數超出檔案大小時會丟出原始的
    # `struct.error: unpack_from requires a buffer of at least N bytes` ——
    # 呼叫端無法分辨「這不是 LMI 檔」與「這支工具有 bug」,訊息也看不出所以然。
    # decode_lmi.lmi_offsets 是同一件事的另一個實作,它丟的是有意義的 NotLMI。
    if 6 + n * 4 > len(d):
        raise ValueError(f"目錄宣稱 {n} 筆,超出檔案大小 {len(d)}")
    offs = [struct.unpack_from("<I", d, 6 + 4 * i)[0] for i in range(n)]
    luts = []
    for i in range(n):
        s = offs[i]
        e = offs[i + 1] if i + 1 < n else len(d)
        luts.append(d[s:e][:256])
    return luts


def selftest():
    """與 `decode_lmi.lmi_offsets` 的跨工具對照 —— 同一個容器格式的兩個獨立實作。

    這種重複實作最容易出的問題不是兩邊都錯,是**其中一邊少了某個檢查**,平常看不出來,
    直到餵進一個壞檔案。實測就是如此:這支原本沒有目錄邊界檢查,壞輸入丟的是原始
    `struct.error` 而不是有意義的錯誤。
    """
    import os
    import sys as _sys
    import tempfile
    if hasattr(_sys.stdout, "reconfigure"):
        _sys.stdout.reconfigure(encoding="utf-8")
        _sys.stderr.reconfigure(encoding="utf-8")
    fails = []
    here = os.path.dirname(os.path.abspath(__file__))
    _sys.path.insert(0, here)
    root = os.path.dirname(here)

    print("(1) 跨工具對照:真實 LMI1 檔的 sub-resource 筆數必須與 decode_lmi 一致")
    from decode_lmi import lmi_offsets, NotLMI
    d = os.path.join(root, "extracted", "raw", "FDOTHER")
    same = diff = 0
    bad = []
    if os.path.isdir(d):
        for fn in sorted(os.listdir(d)):
            fp = os.path.join(d, fn)
            try:
                a = lmi_offsets(open(fp, "rb").read())
            except (NotLMI, OSError, struct.error):
                continue
            try:
                b = parse_lmi(fp)
            except Exception as exc:                          # noqa: BLE001
                diff += 1
                bad.append((fn, type(exc).__name__))
                continue
            if len(a) == len(b):
                same += 1
            else:
                diff += 1
                bad.append((fn, f"{len(a)} vs {len(b)}"))
    ok1 = same > 0 and diff == 0
    print(f"    {'PASS' if ok1 else 'FAIL'}: 一致 {same} / 不一致 {diff}"
          + (f" {bad[:3]}" if bad else ""))
    if same == 0:
        fails.append("找不到任何真實 LMI1 檔 —— 這題是空的,不算通過")
    elif diff:
        fails.append(f"與 decode_lmi 不一致:{bad[:3]}")

    print("\n(2) 回歸:目錄宣稱的筆數超出檔案大小,必須丟有意義的錯而非原始 struct.error")
    with tempfile.TemporaryDirectory() as td:
        p = os.path.join(td, "bad.bin")
        with open(p, "wb") as f:
            f.write(b"LMI1" + struct.pack("<H", 9999) + b"\x00" * 8)
        try:
            parse_lmi(p)
            ok2, why = False, "沒有被擋下"
        except ValueError as exc:
            ok2, why = True, str(exc)[:50]
        except Exception as exc:                              # noqa: BLE001
            ok2, why = False, f"丟出 {type(exc).__name__} 而非 ValueError"
    print(f"    {'PASS' if ok2 else 'FAIL'}: {why}")
    if not ok2:
        fails.append(f"壞目錄的錯誤型別不對:{why}")

    print("\n(3) 非 LMI1 檔必須被擋下")
    with tempfile.TemporaryDirectory() as td:
        p = os.path.join(td, "notlmi.bin")
        with open(p, "wb") as f:
            f.write(b"XXXX" + b"\x00" * 64)
        try:
            parse_lmi(p)
            ok3 = False
        except ValueError:
            ok3 = True
        except Exception:                                     # noqa: BLE001
            ok3 = False
    print(f"    {'PASS' if ok3 else 'FAIL'}: 非 LMI1 -> {'ValueError' if ok3 else '未擋下或型別不對'}")
    if not ok3:
        fails.append("非 LMI1 檔沒有被擋下")

    print("\n(4) 非恆真控制:合法檔案必須真的解出 LUT,而不是每次都丟錯")
    ok4 = False
    if os.path.isdir(d):
        for fn in sorted(os.listdir(d)):
            try:
                luts = parse_lmi(os.path.join(d, fn))
            except Exception:                                 # noqa: BLE001
                continue
            if luts and any(len(l) > 0 for l in luts):
                ok4 = True
                print(f"    PASS: {fn} 解出 {len(luts)} 個 LUT,首個 {len(luts[0])} bytes")
                break
    if not ok4:
        print("    FAIL: 沒有任何檔案解出非空 LUT")
        fails.append("合法檔案沒有解出 LUT")

    if fails:
        print("\nSELFTEST FAILED:")
        for f in fails:
            print("  -", f)
        return 1
    print("\n--selftest passed(跨工具對照 + 壞目錄回歸 + 非 LMI1 攔截 + 非恆真控制)。")
    return 0


def load_palette(path):
    raw = open(path, "rb").read()[:768]
    pal = []
    for i in range(256):
        r, g, b = raw[i*3], raw[i*3+1], raw[i*3+2]
        pal += [(r << 2) | (r >> 4), (g << 2) | (g >> 4), (b << 2) | (b >> 4)]
    return pal


def main(argv):
    if len(argv) == 2 and argv[1] == '--selftest':
        return selftest()
    if len(argv) < 3:
        print(__doc__); return 1
    if argv[1] == "list":
        luts = parse_lmi(argv[2])
        print(f"{len(luts)} 張 LUT(256-byte each)")
        for i, l in enumerate(luts):
            diff = sum(1 for k in range(min(256, len(l))) if l[k] != k)
            print(f"  LUT{i:2}: 非 identity 項={diff}/256  樣本[64:72]={list(l[64:72])}")
        return 0
    if argv[1] == "apply":
        lmi, palp, rawp, w, h, out = argv[2], argv[3], argv[4], int(argv[5]), int(argv[6]), argv[7]
        luts = parse_lmi(lmi); pal = load_palette(palp)
        base = open(rawp, "rb").read()[:w*h]
        os.makedirs(out, exist_ok=True)
        for i, lut in enumerate(luts):
            if len(lut) < 256:
                continue
            px = bytes(lut[p] for p in base)
            from PIL import Image
            im = Image.frombytes("P", (w, h), px); im.putpalette(pal)
            im.convert("RGB").save(os.path.join(out, f"lut{i:02d}.png"))
        print(f"{len(luts)} 張著色結果 -> {out}")
        return 0
    print(__doc__); return 1


if __name__ == "__main__":
    sys.exit(main(sys.argv))
