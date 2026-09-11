#!/usr/bin/env python3
"""炎龍騎士團2 (Flame Dragon Knight 2) 通用 .DAT 容器解包工具。

第 1 輪逆向工程成果。漢堂國際 1995 年原版的所有 .DAT 資產檔共用同一個
簡單的歸檔(archive)容器格式:

    +0   6 bytes   magic = b"LLLLLL"  (0x4C x6)
    +6   uint32[N] little-endian offset 目錄
                   N = (offsets[0] - 6) // 4
                   每個 offset 指向一個 sub-resource 的起點(相對檔頭)
                   單調遞增;第 i 個資源的長度 = offsets[i+1] - offsets[i]
                   最後一個資源延伸到檔尾。

用法:
    python3 unpack_dat.py <檔案.DAT> [輸出目錄]      # 解包單一檔
    python3 unpack_dat.py --list <檔案.DAT>           # 只列目錄不解包
    python3 unpack_dat.py --all <FLAME2目錄> <輸出根目錄>  # 解包整個目錄

不依賴任何第三方套件,純標準函式庫。
"""
import os
import sys
import struct

if hasattr(sys.stdout, "reconfigure"):
    sys.stdout.reconfigure(encoding="utf-8")
    sys.stderr.reconfigure(encoding="utf-8")

MAGIC = b"LLLLLL"


class NotAContainer(Exception):
    pass


def parse_directory(data: bytes):
    """回傳 sub-resource 的 (offset, length) 清單;非本格式則丟 NotAContainer。"""
    if data[:6] != MAGIC:
        raise NotAContainer("缺少 LLLLLL magic")
    # 2026-09-10:magic 檢查放行後直接讀 offset 6 的 4 bytes,長度 6~9 的輸入
    # (magic 齊全但目錄第一格不完整)會丟出原始的 struct.error —— 正是本專案
    # 已知的「讀過頭」bug 類別,與 decode_lmi/dump_remap/decode_fdicon/render_map
    # 在 2026-09-08 一併修掉的是同一個形狀。這一支當時沒被一起修,而它是四個姊妹
    # 裡**唯一早就登錄在窮舉截斷測試裡**的那個 —— 之所以沒被抓到,是因為它的
    # 合法例外清單寫了 `"error"`,而 `struct.error.__name__` 就是 `"error"`,
    # 等於把要偵測的症狀本身列為合法。詳見 DECODERS 表上的說明。
    if len(data) < 10:
        raise NotAContainer(f"只有 {len(data)} bytes,不足以讀出目錄第一格")
    first = struct.unpack_from("<I", data, 6)[0]
    if first < 6 or first > len(data) or (first - 6) % 4 != 0:
        raise NotAContainer(f"目錄起點不合理: 0x{first:x}")
    n = (first - 6) // 4
    # first == 6 是合法通過上面所有檢查的,但會得到 n == 0,於是下面的 `offs[-1]`
    # 對空 list 取值丟 IndexError。截斷掃描沒抽中這個輸入,不代表它不存在。
    if n == 0:
        raise NotAContainer("目錄是空的(起點等於檔頭尾端)")
    offs = [struct.unpack_from("<I", data, 6 + 4 * i)[0] for i in range(n)]
    # 健全性檢查:單調遞增且都在範圍內
    for i in range(n - 1):
        if offs[i] > offs[i + 1]:
            raise NotAContainer(f"目錄非單調遞增 @#{i}")
    if offs[-1] > len(data):
        raise NotAContainer("目錄 offset 超出檔尾")
    bounds = offs + [len(data)]
    return [(bounds[i], bounds[i + 1] - bounds[i]) for i in range(n)]


def list_container(path: str):
    data = open(path, "rb").read()
    entries = parse_directory(data)
    print(f"{os.path.basename(path)}: {len(data)} bytes, {len(entries)} 個資源")
    print(f"  {'idx':>4}  {'offset':>10}  {'length':>10}")
    for i, (off, ln) in enumerate(entries):
        print(f"  {i:>4}  0x{off:08x}  {ln:>10}")


def unpack(path: str, out_dir: str):
    data = open(path, "rb").read()
    entries = parse_directory(data)
    base = os.path.splitext(os.path.basename(path))[0]
    dst = os.path.join(out_dir, base)
    os.makedirs(dst, exist_ok=True)
    width = max(3, len(str(len(entries) - 1)))
    for i, (off, ln) in enumerate(entries):
        name = f"{base}_{i:0{width}d}.bin"
        with open(os.path.join(dst, name), "wb") as f:
            f.write(data[off:off + ln])
    print(f"{os.path.basename(path):14} -> {dst}  ({len(entries)} 個資源)")
    return len(entries)


def _make_container(offsets, payloads, magic=MAGIC):
    """組一個合成容器,讓 selftest 能用手算的預期值檢查,而不是只跑真實檔案。"""
    body = b"".join(payloads)
    return magic + b"".join(struct.pack("<I", o) for o in offsets) + body


def selftest():
    """正向 + 5 種故障注入 + 真實檔案的配對控制。

    重點是**壞輸入必須明確失敗**。這個 parser 的每一條健全性檢查都對應一種
    「靜默解出垃圾」的失敗模式:magic 不對就當成容器解、目錄起點不合理就算出
    離譜的 n、目錄非單調遞增就切出負長度、最後一筆超出檔尾就讀到檔案外面。
    只驗「好輸入能解」證明不了任何一條。
    """
    fails = []

    print("(1) 正向:手算的合成容器必須解出預期的 (offset, length)")
    # 2 筆目錄 -> first = 6 + 2*4 = 14(0xe);payload 各 3、5 bytes
    data = _make_container([14, 17], [b"abc", b"defgh"])
    got = parse_directory(data)
    ok1 = got == [(14, 3), (17, 5)]
    print(f"    {'PASS' if ok1 else 'FAIL'}: {got}(預期 [(14, 3), (17, 5)])")
    if not ok1:
        fails.append(f"正向解析錯誤:{got}")

    print("\n(2) 故障注入:每一種壞輸入都必須丟 NotAContainer,不能靜默解出垃圾")
    cases = [
        ("magic 不對", _make_container([14, 17], [b"abc", b"defgh"], magic=b"XXXXXX")),
        ("目錄起點 < 6", MAGIC + struct.pack("<I", 4) + b"junkjunk"),
        ("目錄起點未對齊 4", MAGIC + struct.pack("<I", 15) + b"j" * 20),
        # 2026-09-11:原本寫 `_make_container([20, 14], ...)`——offs[0]=20 在
        # 走到單調遞增檢查**之前**就先被「目錄起點未對齊 4」那條規則擋下了
        # ((20-6)%4=2≠0),這一題其實從未測到 `range(n-1)` 那段迴圈。n=2 時
        # offs[0] 必須恰好等於 `6+4*len(offsets)`=14,才會真的走到單調遞增檢查。
        ("目錄非單調遞增", _make_container([14, 10], [b"", b""])),
        # n=1 時最後一筆就是 first,而 first<=len 前面已檢查過,那條規則永遠不會觸發
        # —— 必須用 n=2 才測得到。第一版寫成 n=1,這題白過了一次。
        ("最後一筆超出檔尾",
         MAGIC + struct.pack("<I", 14) + struct.pack("<I", 9999) + b"payload"),
    ]
    for label, blob in cases:
        try:
            parse_directory(blob)
            print(f"    FAIL: 「{label}」沒有被擋下")
            fails.append(f"{label} 沒有被擋下")
        except NotAContainer:
            print(f"    PASS: 「{label}」-> NotAContainer")
        except Exception as exc:                          # noqa: BLE001
            # 丟別的例外也算漏 —— 呼叫端接的是 NotAContainer(見 main 的 --all)
            print(f"    FAIL: 「{label}」丟出 {type(exc).__name__} 而非 NotAContainer")
            fails.append(f"{label} 丟出 {type(exc).__name__}")

    print("\n(3) 配對控制:真實 .DAT 要解得開,而真實的**非**容器檔要被擋下")
    root = os.path.dirname(os.path.dirname(os.path.abspath(__file__)))
    # 注意:`extracted/raw/` 放的是**已解包後**的子資源(ANI_000.bin 之類),
    # 本身不是容器 —— 拿它當正向樣本會讓這題永遠失敗。原始 .DAT 在 org_game。
    game = os.path.join(root, "org_game", "炎龍騎士團", "FLAME2")
    real, hit, miss = None, 0, None
    if os.path.isdir(game):
        for fn in sorted(os.listdir(game)):
            if not fn.upper().endswith(".DAT"):
                continue
            p2 = os.path.join(game, fn)
            try:
                hit = len(parse_directory(open(p2, "rb").read()))
                real = p2
                break
            except (NotAContainer, OSError, IndexError, struct.error):
                continue
    exe = os.path.join(root, "org_game", "炎龍騎士團", "FLAME2", "FD2.EXE")
    if os.path.isfile(exe):
        try:
            parse_directory(open(exe, "rb").read())
            miss = False           # EXE 不該被當成容器
        except NotAContainer:
            miss = True
    print(f"    真實資源檔 {os.path.basename(real) if real else '(找不到)'}: "
          f"{'解出 %d 筆' % hit if hit else '無法解析'}")
    print(f"    FD2.EXE 被擋下: {miss}")
    if miss is False:
        fails.append("FD2.EXE 被誤判為容器 —— magic 檢查沒有鑑別力")
    if not real or hit <= 0:
        fails.append("找不到任何解得開的真實容器 —— 這題的正向那半是空的,不算通過")

    print("\n(4) 邊界:單筆目錄的容器,長度必須一路吃到檔尾")
    one = MAGIC + struct.pack("<I", 10) + b"payload!!"
    got4 = parse_directory(one)
    ok4 = got4 == [(10, len(one) - 10)]
    print(f"    {'PASS' if ok4 else 'FAIL'}: {got4}")
    if not ok4:
        fails.append(f"單筆目錄邊界錯誤:{got4}")

    if fails:
        print("\nSELFTEST FAILED:")
        for f in fails:
            print("  -", f)
        return 1
    print("\n--selftest passed(手算正向 + 5 種故障注入 + 真實檔案配對控制 + 邊界)。")
    return 0


def main(argv):
    if len(argv) < 2:
        print(__doc__)
        return 1
    if argv[1] == "--selftest":
        return selftest()
    if argv[1] == "--list":
        list_container(argv[2])
        return 0
    if argv[1] == "--all":
        src, out = argv[2], argv[3]
        total_files = total_res = 0
        skipped = []
        for fn in sorted(os.listdir(src)):
            p = os.path.join(src, fn)
            if not os.path.isfile(p):
                continue
            try:
                total_res += unpack(p, out)
                total_files += 1
            except NotAContainer as e:
                skipped.append((fn, str(e)))
        print(f"\n完成: {total_files} 個容器, 共 {total_res} 個資源 -> {out}")
        if skipped:
            print("略過(非容器格式):")
            for fn, why in skipped:
                print(f"  {fn}: {why}")
        return 0
    path = argv[1]
    out = argv[2] if len(argv) > 2 else "extracted"
    unpack(path, out)
    return 0


if __name__ == "__main__":
    sys.exit(main(sys.argv))
