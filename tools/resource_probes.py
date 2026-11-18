#!/usr/bin/env python3
"""resource_probes.py —— `.DAT` 資源的格式 probe(re_coverage.py 的 PROBES 由這裡提供)。

為什麼有這支
------------
`docs/data/resource_map.json` 登錄 11 個 `.DAT` 容器的 1005 筆資源;`format` 只有在 probe 通過時才算「格式已驗」。
2026-11-19 以前只有 `container` / `empty` 兩種 probe(40 筆)。這支收錄 20 種格式,每個 probe 都是結構不變量
(表頭宣告的長度 / 寬高 / 筆數與實際 byte 數恰好吻合、解碼恰好用完全部 byte、offset 表單調……),
不是「解碼器沒丟例外」。草稿由三個唯讀代理逐格式設計並對原版做負向對照(doc98 續二百八十六),
主 session 比對重疊格式後合併。

已知擋不住的(誠實列出)
------------------------
* 寬高互換(總像素數不變)、像素值 / 事件內容 / 合法範圍內的另一個值被改 —— 這些位元組沒有冗餘。
* `field_control`:表頭 +2 單位數改小、+0 / +1 改值(原版有 3 筆在 N 筆之後多帶記錄,只能要求 N ≤ 筆數)。
* `raw_image` 與 `rlec0_image` 都接受 FDOTHER 第 15 號(所有 byte ≤ 0xC0);登錄用 raw_image。

用法
----
    python tools/resource_probes.py --selftest   # 對原版 11 個 .DAT:每種格式接受的筆數、負向對照
"""
from __future__ import annotations

import struct
import sys
from typing import Callable

if hasattr(sys.stdout, "reconfigure"):
    sys.stdout.reconfigure(encoding="utf-8")
    sys.stderr.reconfigure(encoding="utf-8")

def _wh(b: bytes) -> tuple[int, int] | None:
    """u16 寬、u16 高(兩者都必須 > 0);長度不足 4 回 None。"""
    if len(b) < 4:
        return None
    w, h = struct.unpack_from("<HH", b, 0)
    if w == 0 or h == 0:
        return None
    return w, h

def _rle4_exact(body: bytes, target: int) -> bool:
    """4 模式 sprite RLE(FD2.EXE 0x4e98d / 0x4e22a / 0x4F43D 同一文法)恰好解出 target 個像素並用完 body。

    控制 byte c:高 2 bit = 模式,count = (c & 0x3F) + 1。
    00 run(讀 1 值,輸出 count)、01 隔位(讀 1 值,輸出 2×count)、10 literal(讀 count 個)、11 透明 skip(輸出 count)。
    任何一個 token 讓輸出超過 target、或 target 達成時 body 還有剩、或 token 讀到 body 之外,都回 False。
    """
    out = 0
    i = 0
    n = len(body)
    while out < target:
        if i >= n:
            return False                      # 像素不足
        c = body[i]
        i += 1
        mode = c >> 6
        cnt = (c & 0x3F) + 1
        if mode == 0 or mode == 1:
            if i >= n:
                return False                  # 值 byte 不在 body 內
            i += 1
            out += cnt if mode == 0 else 2 * cnt
        elif mode == 2:
            if i + cnt > n:
                return False                  # literal 讀過頭
            i += cnt
            out += cnt
        else:
            out += cnt
    return out == target and i == n           # 不許溢出,也不許剩 byte

def probe_rle4_image(b: bytes) -> bool:
    """`rle4_image`:u16 寬、u16 高,之後是 4 模式 sprite RLE,恰好解出 寬×高 個像素且恰好用完全部 byte。

    BG.DAT 戰鬥背景、TITLE.DAT、FDOTHER 全螢幕 / 半幅背景都是這個格式(blit_rle_image_at_xy 0x4e98d 繪製)。
    doc05 記的 2 模式 RLE(c >= 0x80 literal 最多 128)是它的子集:實測所有圖的 run / literal 都 <= 64,
    兩種文法解出同一結果;反過來有 4 模式才解得開的圖(用到 11 透明 skip 或 01 隔位,例:BG 第 36 號、
    FDOTHER 第 47 / 59 / 69..75 / 100 號、BG 的 7 byte 10×3 全透明小圖)。
    """
    wh = _wh(b)
    if wh is None:
        return False
    return _rle4_exact(b[4:], wh[0] * wh[1])

def probe_raw_image(b: bytes) -> bool:
    """`raw_image`:u16 寬、u16 高,之後恰好 寬×高 個未壓縮像素(blit_raw_image 0x4ed0b 的格式)。"""
    wh = _wh(b)
    return wh is not None and len(b) == 4 + wh[0] * wh[1]

def _rlec0_exact(body: bytes, target: int) -> bool:
    """c0 RLE(FD2.EXE 0x4ebff blit_rle_image / 0x4ebab blit_rle_c0_transparent)恰好解出 target 並用完 body。

    c <= 0xC0:c 本身是 1 個像素;c > 0xC0:run,長度 c - 0xC0,後跟 1 個值 byte。
    """
    out = 0
    i = 0
    n = len(body)
    while out < target:
        if i >= n:
            return False
        c = body[i]
        i += 1
        if c <= 0xC0:
            out += 1
        else:
            if i >= n:
                return False
            i += 1
            out += c - 0xC0
    return out == target and i == n

def probe_rlec0_image(b: bytes) -> bool:
    """`rlec0_image`:u16 寬、u16 高,之後是 c0 RLE(c <= 0xC0 單一像素、c > 0xC0 run),恰好解出 寬×高 且用完全部 byte。

    blit_rle_image 0x4ebff 的格式(DATO 頭像同一 codec)。
    """
    wh = _wh(b)
    if wh is None:
        return False
    return _rlec0_exact(b[4:], wh[0] * wh[1])

def probe_vga_palette(b: bytes) -> bool:
    """`vga_palette`:恰好 768 byte(256 × RGB),每個分量都是 6-bit(<= 0x3F),VGA DAC 的原生格式。"""
    return len(b) == 768 and max(b) <= 0x3F

def probe_tile_bank(b: bytes) -> bool:
    """`tile_bank`:u16 圖塊寬、u16 圖塊高、u16 張數 n,接 u32 offset 表,每張圖塊是 4 模式 sprite RLE。

    兩種 offset 表都收(都要恰好吻合):
      * n 格:offset[0] == 6 + 4n(FDSHAP 地形圖塊組、FDOTHER 第 1 號);
      * n + 1 格:offset[0] == 6 + 4(n + 1),最後一格 == 資源長度(結尾哨兵;FDOTHER 第 96 號)。
    offset 必須嚴格遞增、落在資源內;第 i 張 = [offset[i], offset[i+1])(最後一張到結尾),
    每張都要恰好解出 寬×高 且恰好用完自己那一段。
    """
    if len(b) < 6:
        return False
    tw, th, n = struct.unpack_from("<HHH", b, 0)
    if tw == 0 or th == 0 or n == 0 or len(b) < 6 + 4 * n:
        return False
    first = struct.unpack_from("<I", b, 6)[0]
    if first == 6 + 4 * n:
        slots = n
    elif first == 6 + 4 * (n + 1) and len(b) >= first:
        slots = n + 1
    else:
        return False
    offs = [struct.unpack_from("<I", b, 6 + 4 * i)[0] for i in range(slots)]
    if slots == n + 1:
        if offs[n] != len(b):
            return False
        bounds = offs
    else:
        bounds = offs + [len(b)]
    if any(bounds[i] >= bounds[i + 1] for i in range(n)) or bounds[n] > len(b):
        return False
    return all(_rle4_exact(b[bounds[i]:bounds[i + 1]], tw * th) for i in range(n))

_TERRAIN_FLAG_BITS = 0x04 | 0x08 | 0x10 | 0x20 | 0x40 | 0x80

_BG_COUNT = 56

def probe_terrain_attr(b: bytes) -> bool:
    """`terrain_attr`:地形屬性表,每格 4 byte(byte0 旗標、byte1 移動代碼、byte2-3 u16 戰鬥背景號)。

    不變量:長度 > 0 且是 4 的倍數;byte1 移動代碼 0..5(doc01 §5 的值域);byte0 只用到已知旗標位元;
    戰鬥背景號 < BG.DAT 的非空資源數(56)。沒有表頭,所以「改表頭」這類對照改成改 byte1。
    """
    if not b or len(b) % 4:
        return False
    for k in range(0, len(b), 4):
        if b[k] & ~_TERRAIN_FLAG_BITS & 0xFF:
            return False
        if b[k + 1] > 5:
            return False
        if (b[k + 2] | b[k + 3] << 8) >= _BG_COUNT:
            return False
    return True

def _lmi_entries(b: bytes) -> list[bytes] | None:
    """LMI1:magic、u16 筆數 n、u32[n + 1] offset(最後一格是結尾哨兵 == 資源長度)。

    offset[0] 必須恰好 == 6 + 4(n + 1)、嚴格遞增。不合就回 None。
    """
    if len(b) < 10 or b[:4] != b"LMI1":
        return None
    n = struct.unpack_from("<H", b, 4)[0]
    if n == 0 or len(b) < 6 + 4 * (n + 1):
        return None
    offs = [struct.unpack_from("<I", b, 6 + 4 * i)[0] for i in range(n + 1)]
    if offs[0] != 6 + 4 * (n + 1) or offs[n] != len(b):
        return None
    if any(offs[i] >= offs[i + 1] for i in range(n)):
        return None
    return [b[offs[i]:offs[i + 1]] for i in range(n)]

def probe_lmi_lut_bank(b: bytes) -> bool:
    """`lmi_lut_bank`:LMI1 容器,每一筆都恰好 256 byte(換色表 LUT,doc10 / dump_remap.py)。"""
    ents = _lmi_entries(b)
    return ents is not None and all(len(e) == 256 for e in ents)

def probe_lmi_image_bank(b: bytes) -> bool:
    """`lmi_image_bank`:LMI1 容器,每一筆是 u16 寬、u16 高 + 像素,像素是下列三種之一且恰好吻合:
    未壓縮(長度 == 4 + 寬×高)、c0 RLE 恰好解出、4 模式 sprite RLE 恰好解出。

    三種 codec 對應三個讀取端(blit_raw_cell 0x1685c / draw_res_image_frame 0x15f0e 的 c0 透明 /
    blit_res_cell_sprite 0x16886 的 0x4e98d);同一容器內混用,所以每筆只要求其中一種恰好成立。
    """
    ents = _lmi_entries(b)
    if ents is None:
        return False
    for e in ents:
        wh = _wh(e)
        if wh is None:
            return False
        t = wh[0] * wh[1]
        body = e[4:]
        if not (len(body) == t or _rlec0_exact(body, t) or _rle4_exact(body, t)):
            return False
    return True

def probe_cell_table_raw(b: bytes) -> bool:
    """`cell_table_raw`:沒有表頭的 u32 offset 表(n = offset[0] / 4),每格 u16 寬、u16 高 + 恰好 寬×高 個未壓縮像素。

    offset 嚴格遞增,第 i 格 = [offset[i], offset[i+1]),最後一格到資源結尾(FDOTHER 第 2 號,
    ui_icon_cell_bank:第 i 格 = 基底 + dword[基底 + i × 4])。
    """
    if len(b) < 8:
        return False
    first = struct.unpack_from("<I", b, 0)[0]
    if first < 4 or first % 4 or first > len(b):
        return False
    n = first // 4
    offs = [struct.unpack_from("<I", b, 4 * i)[0] for i in range(n)] + [len(b)]
    if any(offs[i] >= offs[i + 1] for i in range(n)):
        return False
    for i in range(n):
        e = b[offs[i]:offs[i + 1]]
        wh = _wh(e)
        if wh is None or len(e) != 4 + wh[0] * wh[1]:
            return False
    return True

_GLYPHS = 1824

def probe_glyph_font16(b: bytes) -> bool:
    """`glyph_font16`:16×16 1bpp 字模表,每字 32 byte,恰好 1824 字(draw_glyph16 0x4ed7a 讀 font + glyph × 32)。

    沒有表頭,只能核對長度與字模數;另要求全部字模裡空白(32 byte 全 0)的不超過 1 個(實測只有第 181 號空白),
    擋掉長度剛好相同的全 0 / 填充資料。
    """
    if len(b) != 32 * _GLYPHS:
        return False
    blank = sum(1 for i in range(_GLYPHS) if not any(b[32 * i:32 * i + 32]))
    return blank <= 1

def probe_frame_anim(b: bytes) -> bool:
    """`frame_anim`:FIGANI 式幀容器。+0 u8 幀數 n(>= 1),+8 起 u32[n] 幀 offset,offset[0] 必須 == 8 + 4n;
    offset 嚴格遞增、落在資源內;每幀至少 13 byte(dx, dy, +4, +6, +8, u16 寬 +9、u16 高 +11),
    +13 起是 4 模式 sprite RLE,恰好解出 寬×高 且恰好用完這一幀的 byte。

    blit_anim_frame 0x2eb9f 的讀法(影格 = anim + dword[anim + idx*4 + 8],以影格 + 9 交給 0x4e98d)。
    +1..+7 的欄位(旗標、播放參數)在 FIGANI 有多種值,這裡不核對。
    """
    if len(b) < 12:
        return False
    n = b[0]
    if n == 0 or len(b) < 8 + 4 * n:
        return False
    offs = [struct.unpack_from("<I", b, 8 + 4 * i)[0] for i in range(n)]
    if offs[0] != 8 + 4 * n:
        return False
    bounds = offs + [len(b)]
    for i in range(n):
        if bounds[i] >= bounds[i + 1]:
            return False
        f = b[bounds[i]:bounds[i + 1]]
        if len(f) < 13:
            return False
        w, h = struct.unpack_from("<HH", f, 9)
        if w == 0 or h == 0 or not _rle4_exact(f[13:], w * h):
            return False
    return True

def probe_figani_stub(b: bytes) -> bool:
    """FIGANI.DAT 的 0 幀短資源:恰好 3 byte `00 00 0A`(幀數 0、旗標 0,沒有位移表、沒有幀)。"""
    return b == b"\x00\x00\x0a"

def probe_afm_anim(b: bytes) -> bool:
    """ANI.DAT 的 AFM v1.00 動畫檔:0xAD byte 檔頭 + 幀數筆「8 byte 幀記錄 + compSize byte VM script」。

    不變量(全部要成立):
    * 開頭是 `AFM - Animation File Manager` 橫幅、+0x50 = 0x1A、+0xA1 = 0。
    * +0xA5 有號幀數 ≥ 1;+0xA7 寬 × +0xA9 高 = +0xAB 畫面 byte 數 = 64000(VM 的 op 4/5/6 固定寫 64000)。
    * 每筆幀記錄的兩個保留 word = 0;script 不能超出檔尾。
    * 每個 script 恰好 cmdCount 個指令、opcode 都在 0..9、運算元都不讀出 script,
      而且執行完**恰好**用完 compSize byte;op 2 / 6 的 2-mode RLE 恰好填滿 768 / 64000
      (run 長度 ≠ 0、不寫過頭);op 3 的調色盤區段不超過 768;op 7 / 8 / 9 的區段不超過 64000。
    * 最後一幀的 script 結尾**恰好** = 檔尾。
    """
    n = len(b)
    if n < 0xAD or not b.startswith(b"AFM - Animation File Manager") or b[0x50] != 0x1A or b[0xA1] != 0:
        return False
    u16 = lambda p: b[p] | (b[p + 1] << 8)          # noqa: E731
    fc = u16(0xA5)
    if fc >= 0x8000 or fc == 0:                     # 有號:≥ 0x8000 是負數,原版一幀都不播
        return False
    fb = u16(0xAB)
    if fb != 64000 or u16(0xA7) * u16(0xA9) != fb:
        return False

    def rle(s: bytes, p: int, count: int) -> int:
        written, m = 0, len(s)
        while written < count:
            if p >= m:
                return -1
            c = s[p]
            p += 1
            if c & 0xC0 == 0xC0:
                k = c & 0x3F
                if k == 0 or p >= m or written + k > count:
                    return -1
                p += 1
                written += k
            else:
                written += 1
        return p

    pos = 0xAD
    for _ in range(fc):
        if pos + 8 > n:
            return False
        cs, cc, r0, r1 = u16(pos), u16(pos + 2), u16(pos + 4), u16(pos + 6)
        pos += 8
        if r0 or r1 or pos + cs > n:
            return False
        s = b[pos:pos + cs]
        p = 0
        for _ in range(cc):
            if p >= cs:
                return False
            op = s[p]
            p += 1
            if op in (0, 4):
                p += 1
            elif op == 1:
                p += 768
            elif op == 5:
                p += 64000
            elif op in (2, 6):
                p = rle(s, p, 768 if op == 2 else 64000)
                if p < 0:
                    return False
            elif op == 3:
                if p >= cs:
                    return False
                cnt_n = s[p]
                p += 1
                for _ in range(cnt_n):
                    if p + 2 > cs:
                        return False
                    idx, cnt = s[p], s[p + 1]
                    p += 2 + 3 * cnt
                    if idx * 3 + cnt * 3 > 768:
                        return False
            elif op in (7, 8, 9):
                if p + 2 > cs:
                    return False
                k = s[p] | (s[p + 1] << 8)
                p += 2
                for _ in range(k):
                    if p + 3 > cs:
                        return False
                    off = s[p] | (s[p + 1] << 8)
                    if op == 7:
                        p += 3
                        ln = 1
                    elif op == 8:
                        if p + 4 > cs:
                            return False
                        ln = s[p + 2]
                        p += 4
                    else:
                        ln = s[p + 2]
                        p += 3 + ln
                    if off + ln > fb:
                        return False
            else:
                return False
            if p > cs:
                return False
        if p != cs:
            return False
        pos += cs
    return pos == n

def probe_field_map(b: bytes) -> bool:
    """FDFIELD 第 3k 條:戰場地圖格。

    表頭 u16 寬 W、u16 高 H(皆 >= 1),之後恰好 W × H 格、每格 4 byte,長度必須恰好是
    4 + W × H × 4(多 / 少 1 byte、改寬或高都不成立)。每格第 4 byte(載入後緩衝 +7 的範圍
    標記,執行期才由 0x4df4c 寫成 0xff)在檔內必須是 0(實測 33 張圖 43734 格全是 0)。
    """
    if len(b) < 4:
        return False
    w, h = struct.unpack_from("<HH", b, 0)
    if w == 0 or h == 0 or len(b) != 4 + w * h * 4:
        return False
    return all(b[4 + k * 4 + 3] == 0 for k in range(w * h))

def probe_field_control(b: bytes) -> bool:
    """FDFIELD 第 3k+1 條:戰場控制段。

    固定表頭 0x83 bytes(+0 地形圖組號、+1 開戰我方數、+2 單位記錄數 N、+3 回合事件 16 × 3、
    +0x33 格子事件 16 × 2、+0x53 寶箱 16 × 3),之後是整數筆 26 byte 單位記錄。
    條件:(長度 − 0x83) 是 26 的倍數;記錄筆數不超過 80(長度 <= 0x8a3,save_load_restore
    malloc 的大小);表頭 N 不超過實際筆數(原版有 3 張圖在 N 筆之後多帶 1 / 1 / 10 筆);
    16 格格子事件的篩選 byte 只能是 0 或 1(field_event_lookup 的呼叫端只傳 0 / 1);
    啟用中的回合事件列(回合 != 0xff)陣營 <= 2;每筆單位記錄 +0 陣營 <= 2。
    """
    if len(b) < 0x83 or (len(b) - 0x83) % 26:
        return False
    rec = (len(b) - 0x83) // 26
    if rec > 80 or b[2] > rec:
        return False
    for s in range(16):
        turn, _event, camp = b[3 + s * 3:6 + s * 3]
        if turn != 0xFF and camp > 2:
            return False
    if any(b[0x33 + s * 2 + 1] not in (0, 1) for s in range(16)):
        return False
    return all(b[0x83 + k * 26] <= 2 for k in range(rec))

def probe_field_spawn(b: bytes) -> bool:
    """FDFIELD 第 3k+2 條:出場位置表。

    表頭 u16 筆數 N(>= 1),之後恰好 N 列 × 6 byte,長度必須恰好是 2 + 6N。每列是
    3 個 u16,field_unit_construct 0x10c94 / 0x10c9b 只以 byte 讀 +0(X)與 +2(Y),
    所以三個 u16 的高位 byte(+1 / +3 / +5)必須是 0(實測 33 張表全是 0)。
    """
    if len(b) < 2:
        return False
    n = struct.unpack_from("<H", b, 0)[0]
    if n == 0 or len(b) != 2 + 6 * n:
        return False
    return all(b[2 + k * 6 + j] == 0 for k in range(n) for j in (1, 3, 5))

GLYPH_COUNT = 0x720     # FDOTHER #4 字型 58368 / 32 = 1824 個字模

def probe_glyph_text(b: bytes) -> bool:
    """FDTXT 文字表:u16 offset 表 + u16 字碼串。

    長度為偶數;第一個 offset = 2N(N >= 1 條字串,即 offset 表本身的大小);N 個 offset
    嚴格遞增且最後一個 < 長度;第 i 條字串佔 [offset[i], offset[i+1])(最後一條到資源尾),
    每條恰好以一個 0xffff 結尾且中間沒有 0xffff;每個字碼是字模索引(< 0x720)或控制碼
    (0xff00 .. 0xfffe)。換言之整個資源被 N 條完整字串恰好用完。
    """
    if len(b) < 4 or len(b) % 2:
        return False
    first = struct.unpack_from("<H", b, 0)[0]
    if first < 2 or first % 2:
        return False
    n = first // 2
    if first >= len(b):
        return False
    offs = list(struct.unpack_from(f"<{n}H", b, 0))
    if any(offs[i] >= offs[i + 1] for i in range(n - 1)) or offs[-1] >= len(b):
        return False
    bounds = offs + [len(b)]
    for i in range(n):
        s, e = bounds[i], bounds[i + 1]
        if (e - s) % 2:
            return False
        words = struct.unpack_from(f"<{(e - s) // 2}H", b, s)
        if words[-1] != 0xFFFF or 0xFFFF in words[:-1]:
            return False
        if any(not (w < GLYPH_COUNT or w >= 0xFF00) for w in words):
            return False
    return True

def probe_portrait_rle4(b: bytes) -> bool:
    """DATO 頭像:4 幀(嘴型)RLE 圖。

    +0 是 4 個 u32 幀 offset,第一個必須是 0x10(表頭大小),嚴格遞增;第 k 幀佔
    [offset[k], offset[k+1])(第 4 幀到資源尾),開頭 u16 寬、u16 高(>= 1),之後是 RLE:
    byte <= 0xc0 是 1 個字面像素,> 0xc0 是 (byte − 0xc0) 個重複下一個 byte。
    每幀解出的像素數必須恰好 = 寬 × 高(最後一個 run 不得超出),而且恰好用完該幀的位元組
    (沒有剩餘、run 不缺值 byte)。
    """
    if len(b) < 16:
        return False
    offs = list(struct.unpack_from("<4I", b, 0))
    if offs[0] != 0x10 or any(offs[i] >= offs[i + 1] for i in range(3)) or offs[3] + 4 > len(b):
        return False
    bounds = offs + [len(b)]
    for k in range(4):
        s, e = bounds[k], bounds[k + 1]
        if e - s < 4:
            return False
        w, h = struct.unpack_from("<HH", b, s)
        total = w * h
        if total == 0:
            return False
        i, px = s + 4, 0
        while px < total:
            if i >= e:
                return False
            c = b[i]
            i += 1
            if c <= 0xC0:
                px += 1
            else:
                if i >= e:
                    return False
                i += 1
                px += c - 0xC0
        if px != total or i != e:
            return False
    return True

def _iff_chunks(b: bytes, o: int, end: int) -> list[tuple[bytes, int, int]] | None:
    """把 [o, end) 切成 IFF chunk:(tag, body 起點, 長度);長度為 big-endian,奇數長度補 1 byte。
    必須恰好切到 end,否則回 None。"""
    out = []
    while o < end:
        if o + 8 > end:
            return None
        tag, ln = b[o:o + 4], struct.unpack_from(">I", b, o + 4)[0]
        nxt = o + 8 + ln + (ln & 1)
        if nxt > end:
            return None
        out.append((tag, o + 8, ln))
        o = nxt
    return out if o == end else None

def _xmidi_evnt_ok(b: bytes, o: int, end: int) -> bool:
    """XMIDI 事件流:< 0x80 是間隔延時;0x8n..0xEn 通道訊息(0x9n 多一個 VLQ 音長,
    沒有 running status,資料 byte 必須 < 0x80);0xff 是 meta(型別、VLQ 長度、資料);
    0xf0 / 0xf7 是 sysex(VLQ 長度、資料);其他 status 不合法。必須以 ff 2f 00(曲終)
    恰好結束在 end。"""
    def vlq(p: int) -> int:
        """跳過一個最多 4 byte 的 VLQ,回傳下一個位置;超過 4 byte 或讀到 end 回 -1。"""
        for _ in range(4):
            if p >= end:
                return -1
            c = b[p]
            p += 1
            if not c & 0x80:
                return p
        return -1

    i = o
    while i < end:
        c = b[i]
        if c < 0x80:
            i += 1
            continue
        i += 1
        hi = c & 0xF0
        if hi in (0x80, 0x90, 0xA0, 0xB0, 0xE0):
            if i + 2 > end or b[i] >= 0x80 or b[i + 1] >= 0x80:
                return False
            i += 2
            if hi == 0x90:
                i = vlq(i)
                if i < 0:
                    return False
        elif hi in (0xC0, 0xD0):
            if i >= end or b[i] >= 0x80:
                return False
            i += 1
        elif c == 0xFF:
            if i >= end or b[i] >= 0x80:
                return False
            mtype = b[i]
            p = vlq(i + 1)
            if p < 0:
                return False
            ln = 0
            for q in range(i + 1, p):
                ln = (ln << 7) | (b[q] & 0x7F)
            i = p + ln
            if i > end:
                return False
            if mtype == 0x2F:
                # 原版的 EVNT 宣告長度一律是偶數:事件流長度是奇數時,宣告長度內含 1 個 0x00 填充
                # (實測 15 首中 10 首如此,5 首事件流本身就是偶數、沒有填充)
                return ln == 0 and (i == end or (i + 1 == end and b[i] == 0 and (i - o) % 2 == 1))
        elif c in (0xF0, 0xF7):
            p = vlq(i)
            if p < 0:
                return False
            ln = 0
            for q in range(i, p):
                ln = (ln << 7) | (b[q] & 0x7F)
            i = p + ln
            if i > end:
                return False
        else:
            return False
    return False        # 沒遇到 ff 2f 00 就用完

def probe_xmidi_form(b: bytes) -> bool:
    """FDMUS 樂曲:Miles XMIDI(IFF,長度 big-endian)。

    整個資源恰好是兩個頂層 chunk:`FORM`(型別 `XDIR`,內含恰好一個長度 2 的 `INFO`,
    值 = 序列數 N >= 1,u16 little-endian)與 `CAT `(型別 `XMID`),後者恰好結束在資源尾。
    `CAT ` 內恰好 N 個 `FORM`(型別 `XMID`),每個內含可選的 `TIMB`(長度 = 2 + 2 × u16 筆數)
    與恰好一個 `EVNT`(依序,不得有其他 chunk);`EVNT` 必須是合法事件流且以 ff 2f 00 結尾,
    之後只容許「事件流長度為奇數時補到偶數」的 1 個 0x00(含在 EVNT 宣告長度內)。
    """
    top = _iff_chunks(b, 0, len(b))
    if top is None or len(top) != 2:
        return False
    (t1, o1, l1), (t2, o2, l2) = top
    if t1 != b"FORM" or l1 < 4 or b[o1:o1 + 4] != b"XDIR":
        return False
    info = _iff_chunks(b, o1 + 4, o1 + l1)
    if info is None or len(info) != 1 or info[0][0] != b"INFO" or info[0][2] != 2:
        return False
    nseq = struct.unpack_from("<H", b, info[0][1])[0]
    if nseq == 0:
        return False
    if t2 != b"CAT " or l2 < 4 or b[o2:o2 + 4] != b"XMID":
        return False
    forms = _iff_chunks(b, o2 + 4, o2 + l2)
    if forms is None or len(forms) != nseq:
        return False
    for tag, o, ln in forms:
        if tag != b"FORM" or ln < 4 or b[o:o + 4] != b"XMID":
            return False
        sub = _iff_chunks(b, o + 4, o + ln)
        if sub is None:
            return False
        tags = [s[0] for s in sub]
        if tags not in ([b"EVNT"], [b"TIMB", b"EVNT"]):
            return False
        for stag, so, sl in sub:
            if stag == b"TIMB":
                if sl < 2 or sl != 2 + 2 * struct.unpack_from("<H", b, so)[0]:
                    return False
            elif not _xmidi_evnt_ok(b, so, so + sl):
                return False
    return True

def probe_space_crlf(b: bytes) -> bool:
    """FDMUS 的 3 byte 佔位資源:恰好是 20 0d 0a(空白 + CR + LF),不是 XMIDI。"""
    return b == b" \r\n"

PROBES: dict[str, Callable[[bytes], bool]] = {
    "rle4_image": probe_rle4_image,
    "raw_image": probe_raw_image,
    "rlec0_image": probe_rlec0_image,
    "vga_palette": probe_vga_palette,
    "tile_bank": probe_tile_bank,
    "terrain_attr": probe_terrain_attr,
    "lmi_lut_bank": probe_lmi_lut_bank,
    "lmi_image_bank": probe_lmi_image_bank,
    "cell_table_raw": probe_cell_table_raw,
    "glyph_font16": probe_glyph_font16,
    "frame_anim": probe_frame_anim,
    "figani_stub": probe_figani_stub,
    "afm_anim": probe_afm_anim,
    "field_map": probe_field_map,
    "field_control": probe_field_control,
    "field_spawn": probe_field_spawn,
    "glyph_text": probe_glyph_text,
    "portrait_rle4": probe_portrait_rle4,
    "xmidi_form": probe_xmidi_form,
    "space_crlf": probe_space_crlf,
}


def _ok(fn: Callable[[bytes], bool], b: bytes) -> bool:
    """probe 通過 = 回 True;丟例外算不通過(與 re_coverage.probe_ok 相同)。"""
    try:
        return fn(b) is True
    except Exception:
        return False


# 原版 1005 筆上每種格式接受的筆數(2026-11-19 實測;rle4_image 含 TAI 56 筆,frame_anim 含 FIGANI 264 筆)
EXPECTED_ACCEPT = {"rle4_image": 144, "raw_image": 2, "rlec0_image": 2, "vga_palette": 7, "tile_bank": 35, "terrain_attr": 33, "lmi_lut_bank": 1, "lmi_image_bank": 6, "cell_table_raw": 1, "glyph_font16": 1, "frame_anim": 292, "figani_stub": 144, "afm_anim": 9, "field_map": 33, "field_control": 33, "field_spawn": 33, "glyph_text": 34, "portrait_rle4": 136, "xmidi_form": 15, "space_crlf": 5}


def _selftest_boundary_cases() -> list[tuple[str, bytes, bool, str]]:
    """人工構造的邊界輸入:(probe, bytes, 應否接受, 說明)。

    原版資料沒有出現的邊界(1×1 圖、1 筆的表、值域上下限、XMIDI 少用的 status)只能靠構造的輸入測。
    每個「不收」的例子都盡量配一個只差一個欄位、而且「要收」的對照,證明擋下它的是那個欄位。
    """
    import struct as st
    px1 = b"\x01\x00\x01\x00\x07"                 # 1×1 未壓縮 / c0 RLE 都是這 5 byte
    cases: list[tuple[str, bytes, bool, str]] = [
        ("raw_image", px1, True, "1×1 未壓縮圖"),
        ("raw_image", b"\x01\x00\x02\x00\x07\x08", True, "1×2 未壓縮圖"),
        ("raw_image", b"\x02\x00\x01\x00\x07\x08", True, "2×1 未壓縮圖"),
        ("raw_image", b"\x00\x00\x01\x00", False, "寬 0"),
        ("rlec0_image", px1, True, "1×1 c0 RLE(0x07 是單一像素)"),
        ("rlec0_image", b"\x01\x00\x01\x00\xc1\x07", True, "1×1 c0 RLE(0xc1 run 長 1)"),
        ("rle4_image", b"\x01\x00\x01\x00\xc0", True, "1×1 4 模式 RLE(透明 skip 1)"),
        ("tile_bank", st.pack("<HHHI", 1, 1, 1, 10) + b"\x00\x05", True, "1×1 圖塊 1 張"),
        ("tile_bank", st.pack("<HHHI", 1, 1, 0, 10) + b"\x00\x05", False, "張數 0"),
        ("terrain_attr", b"\x00\x05\x37\x00", True, "移動代碼 5、背景號 55(上限)"),
        ("terrain_attr", b"\x00\x06\x37\x00", False, "移動代碼 6"),
        ("terrain_attr", b"\x00\x05\x38\x00", False, "背景號 56(BG 只有 56 筆非空)"),
        ("lmi_image_bank", b"LMI1" + st.pack("<HII", 1, 14, 19) + px1, True, "LMI1 1 筆 1×1 圖"),
        ("lmi_lut_bank", b"LMI1" + st.pack("<HII", 1, 14, 270) + bytes(256), True, "LMI1 1 筆 LUT"),
        ("lmi_lut_bank", b"LMI1" + st.pack("<HII", 1, 14, 269) + bytes(255), False, "LUT 255 byte"),
        ("cell_table_raw", st.pack("<I", 4) + b"\x01\x00\x01\x00\x09", True, "1 格 1×1"),
        ("frame_anim", b"\x01" + bytes(7) + st.pack("<I", 12) + bytes(9) + st.pack("<HH", 1, 1) + b"\xc0", True,
         "1 幀 1×1"),
        ("frame_anim", b"\x01" + bytes(7) + st.pack("<I", 12) + bytes(9) + st.pack("<HH", 1, 0) + b"\xc0", False,
         "1 幀高 0"),
        ("field_map", b"\x01\x00\x01\x00\x05\x00\x00\x00", True, "1×1 戰場地圖"),
        ("field_map", b"\x01\x00\x01\x00\x05\x00\x00\x01", False, "1×1,範圍標記 byte 非 0"),
        ("field_spawn", b"\x01\x00\x03\x00\x04\x00\x00\x00", True, "1 列出場位置"),
        ("field_spawn", b"\x01\x00\x03\x01\x04\x00\x00\x00", False, "1 列,X 高位 byte 非 0"),
        ("portrait_rle4", st.pack("<4I", 0x10, 0x15, 0x1A, 0x1F) + px1 * 4, True, "4 幀 1×1 頭像"),
        ("portrait_rle4", st.pack("<4I", 0x10, 0x15, 0x1A, 0x1F) + px1 * 3 + b"\x00\x00\x01\x00\x07", False,
         "第 4 幀寬 0"),
        # 以下各筆讓每個「不收」分支至少被走到一次(原版資料一筆都走不到)
        ("tile_bank", st.pack("<HHHII", 1, 1, 2, 14, 14) + b"\x00\x05", False, "2 張圖塊的 offset 相同(不遞增)"),
        ("lmi_image_bank", b"LMI1" + st.pack("<HII", 1, 14, 17) + b"\x01\x00\x01", False, "LMI1 1 筆只有 3 byte(寬高不完整)"),
        ("frame_anim", b"\x02" + bytes(7) + st.pack("<II", 16, 16) + bytes(9) + st.pack("<HH", 1, 1) + b"\xc0", False,
         "2 幀的 offset 相同(不遞增)"),
        ("frame_anim", b"\x01" + bytes(7) + st.pack("<I", 12) + bytes(12), False, "幀只有 12 byte(不到 13 byte 幀頭)"),
        ("portrait_rle4", st.pack("<4I", 0x10, 0x12, 0x17, 0x1C) + b"\x01\x00" + px1 * 3, False, "第 0 幀只有 2 byte"),
    ]
    # field_control:0x83 byte 表頭(回合事件 16 × 3 從 +3、格子事件 16 × 2 從 +0x33)+ 26 byte 單位記錄
    def ctl(rec: int, n: int | None = None, turn0: tuple[int, int, int] = (0, 0, 0), camp0: int = 0) -> bytes:
        h = bytearray(0x83)
        h[2] = rec if n is None else n
        h[3:6] = bytes(turn0)
        body = bytearray(26 * rec)
        if rec:
            body[0] = camp0
        return bytes(h + body)
    cases += [
        ("field_control", ctl(0), True, "0 筆單位記錄(長度恰好 0x83)"),
        ("field_control", ctl(1), True, "1 筆單位記錄"),
        ("field_control", ctl(80), True, "80 筆(malloc 上限)"),
        ("field_control", ctl(81, 0), False, "81 筆"),
        ("field_control", ctl(1, 2), False, "表頭單位數 2 > 實際 1 筆"),
        ("field_control", ctl(1, turn0=(0xFF, 0, 3)), True, "停用的回合事件(回合 0xff)陣營 3 不檢查"),
        ("field_control", ctl(1, turn0=(1, 0, 2)), True, "啟用的回合事件陣營 2"),
        ("field_control", ctl(1, turn0=(1, 0, 3)), False, "啟用的回合事件陣營 3"),
        ("field_control", ctl(1, camp0=2), True, "單位記錄陣營 2"),
        ("field_control", ctl(1, camp0=3), False, "單位記錄陣營 3"),
        ("field_control", ctl(1)[:0x34] + b"\x02" + ctl(1)[0x35:], False, "第 0 格格子事件的篩選 byte 是 2"),
        ("field_control", ctl(1)[:0x34] + b"\x01" + ctl(1)[0x35:], True, "第 0 格格子事件的篩選 byte 是 1"),
    ]
    # glyph_text:u16 offset 表 + 以 0xffff 結尾的字碼串
    cases += [
        ("glyph_text", b"\x02\x00\xff\xff", True, "1 條字串,只有結尾 0xffff(最短 4 byte)"),
        ("glyph_text", b"\x02\x00\xff\xff\xff\xff", False, "字串中間有 0xffff"),
        ("glyph_text", b"\x02\x00" + st.pack("<HH", 0x71F, 0xFFFF), True, "字模索引 0x71f(最後一個字模)"),
        ("glyph_text", b"\x02\x00" + st.pack("<HH", 0x720, 0xFFFF), False, "字模索引 0x720(超出 1824 字)"),
        ("glyph_text", b"\x02\x00" + st.pack("<HH", 0xFF00, 0xFFFF), True, "控制碼 0xff00(下限)"),
        ("glyph_text", b"\x02\x00" + st.pack("<HH", 0xFEFF, 0xFFFF), False, "0xfeff 既不是字模也不是控制碼"),
        ("glyph_text", b"\x04\x00\x08\x00" + st.pack("<HH", 0x41, 0xFFFF) + st.pack("<H", 0xFFFF), True,
         "2 條字串"),
        ("glyph_text", b"\x04\x00\x07\x00" + b"\xff\xff\x00" + b"\xff\xff\xff", False, "第 0 條字串長 3 byte(奇數)"),
    ]
    # afm_anim:0xAD byte 檔頭 + 每幀「cs, cc, 0, 0」+ script
    def afm(frames: list[tuple[int, bytes]], fc: int | None = None, rsv: tuple[int, int] = (0, 0),
            whb: tuple[int, int, int] = (320, 200, 64000)) -> bytes:
        h = bytearray(0xAD)
        h[0:28] = b"AFM - Animation File Manager"
        h[0x50] = 0x1A
        st.pack_into("<HHHH", h, 0xA5, len(frames) if fc is None else fc, *whb)
        return bytes(h) + b"".join(st.pack("<HHHH", len(s), cc, *rsv) + s for cc, s in frames)
    pal_rle = b"\xff\x10" * 12 + b"\xcc\x10"            # 12 × 63 + 12 = 768
    script = (b"\x00\x05"                                   # op 0:1 byte 運算元
              + b"\x02" + pal_rle                            # op 2:調色盤 RLE 恰好 768
              + b"\x03\x01\x00\x01\x10\x20\x30"            # op 3:1 段,從 0 號、1 色
              + b"\x07\x01\x00" + st.pack("<H", 63999) + b"\x05"   # op 7:1 筆,寫最後一個像素
              + b"\x07\x00\x00")                            # op 7:0 筆,恰好結束在 script 尾
    op8 = b"\x08\x01\x00" + st.pack("<H", 0) + b"\x02\x07"   # op 8:1 筆 4 byte,恰好結束在 script 尾
    cases += [
        ("afm_anim", afm([(5, script), (1, op8)]), True, "op 0 / 2 / 3 / 7 / 8 各一,區段都貼齊上限"),
        ("afm_anim", afm([(1, b"\x00\x05")]), True, "1 幀"),
        ("afm_anim", afm([(1, b"\x00\x05")], rsv=(1, 0)), False, "幀記錄保留 word 0 = 1"),
        ("afm_anim", afm([(1, b"\x02" + pal_rle[:-2] + b"\xcb\x10")]), False, "op 2 調色盤 RLE 只有 767"),
        ("afm_anim", afm([(1, b"\x07\x01\x00" + st.pack("<H", 64000) + b"\x05")]), False, "op 7 寫到 64000(超出)"),
        ("afm_anim", afm([(1, b"\x03\x01\xff\x01\x10\x20\x30")]), True, "op 3 從 255 號寫 1 色(剛好 768)"),
        ("afm_anim", afm([(1, b"\x03\x01\x01\xff" + bytes(765))]), True, "op 3 從 1 號寫 255 色(剛好 768)"),
        ("afm_anim", afm([(1, b"\x03\x01\xff\x02" + bytes(6))]), False, "op 3 從 255 號寫 2 色(771,超出)"),
        ("afm_anim", afm([(1, b"\x03\x01\x00\x00")]), True, "op 3 1 段 0 色,段頭恰好結束在 script 尾"),
        ("afm_anim", afm([(0, b"")] * 0x7FFF), True, "幀數 0x7fff(有號最大),每幀空 script"),
        ("afm_anim", afm([(0, b"")] * 0x8000), False, "幀數 0x8000(有號是負數)"),
        ("afm_anim", afm([(1, b"\x00\x05")], whb=(320, 199, 64000)), False, "寬 × 高 = 63680 ≠ 畫面 byte 數"),
        ("afm_anim", afm([(1, b"\x00\x05")], whb=(320, 200, 63999)), False, "畫面 byte 數 63999"),
        ("afm_anim", afm([(1, b"\x02\xc0\x10" + pal_rle)]), False, "op 2 的 run 長度 0"),
        ("afm_anim", afm([(2, b"\x00\x05")]), False, "cmdCount 2,script 只有 1 個指令"),
        ("afm_anim", afm([(1, b"\x05" + bytes(64000))]), True, "op 5:64000 byte 整幅畫面"),
        ("afm_anim", afm([(1, b"\x05" + bytes(63999))]), False, "op 5 只有 63999 byte"),
        ("afm_anim", afm([(1, b"\x03")]), False, "op 3 沒有段數 byte"),
        ("afm_anim", afm([(1, b"\x03\x01\x00")]), False, "op 3 段頭只有 1 byte"),
        ("afm_anim", afm([(1, b"\x07\x01")]), False, "op 7 筆數只有 1 byte"),
        ("afm_anim", afm([(1, b"\x07\x01\x00\x00\x00")]), False, "op 7 的 1 筆只有 2 byte"),
        ("afm_anim", afm([(1, b"\x08\x01\x00\x00\x00\x02")]), False, "op 8 的 1 筆只有 3 byte"),
        ("afm_anim", afm([(1, b"\x0a")]), False, "opcode 10"),
        ("afm_anim", afm([(1, b"\x01" + bytes(10))]), False, "op 1 只有 10 byte(要 768)"),
        ("afm_anim", afm([(1, b"\x00\x05\x00")]), False, "script 執行完還剩 1 byte"),
    ]
    # xmidi_form:FORM XDIR(INFO)+ CAT XMID(FORM XMID(TIMB?, EVNT))
    def chunk(tag: bytes, body: bytes) -> bytes:
        return tag + st.pack(">I", len(body)) + body + (b"\x00" if len(body) & 1 else b"")
    def xmidi(ev: bytes, timb: bytes | None = None, info: bytes = b"\x01\x00", cat_type: bytes = b"XMID",
              forms: int = 1, form_type: bytes = b"XMID", sub: bytes | None = None) -> bytes:
        if len(ev) % 2:
            ev += b"\x00"                                  # 事件流奇數長時,EVNT 宣告長度內含 1 個 0x00
        if sub is None:
            sub = (chunk(b"TIMB", timb) if timb is not None else b"") + chunk(b"EVNT", ev)
        return (chunk(b"FORM", b"XDIR" + chunk(b"INFO", info))
                + chunk(b"CAT ", cat_type + chunk(b"FORM", form_type + sub) * forms))
    end = b"\xff\x2f\x00"
    cases += [
        ("xmidi_form", xmidi(end), True, "只有曲終"),
        ("xmidi_form", xmidi(end, st.pack("<H", 0)), True, "TIMB 0 筆(長度 2)"),
        ("xmidi_form", xmidi(end, st.pack("<H", 1) + b"\x00\x01"), True, "TIMB 1 筆(長度 4)"),
        ("xmidi_form", xmidi(b"\x80\x3c\x40" + end), True, "note off 0x80"),
        ("xmidi_form", xmidi(b"\xa0\x3c\x40" + end), True, "aftertouch 0xa0"),
        ("xmidi_form", xmidi(b"\xd0\x40" + end), True, "channel pressure 0xd0"),
        ("xmidi_form", xmidi(b"\x80\x90\x3c\x40\x10" + end), False, "0x80 後面接 status(沒有 running status)"),
        ("xmidi_form", xmidi(b"\xb0\x80\x00" + end), False, "controller 第 1 個資料 byte 0x80"),
        ("xmidi_form", xmidi(b"\xb0\x00\x80" + end), False, "controller 第 2 個資料 byte 0x80"),
        ("xmidi_form", xmidi(b"\xc0\x80" + end), False, "program change 資料 byte 0x80"),
        ("xmidi_form", xmidi(b"\xff\x80\x00" + end), False, "meta 型別 0x80"),
        ("xmidi_form", xmidi(b"\x90\x3c\x40\x81\x80\x80\x00" + end), True, "note on 音長 4 byte VLQ"),
        ("xmidi_form", xmidi(b"\x90\x3c\x40\x81\x80\x80\x80\x00" + end), False, "note on 音長 5 byte VLQ"),
        ("xmidi_form", xmidi(b"\xf0\x81\x00" + bytes(128) + end), True, "sysex 長度 2 byte VLQ(128)"),
        ("xmidi_form", xmidi(b"\xf0\x81\x00" + bytes(127) + end), False, "sysex 宣告 128 只有 127"),
        ("xmidi_form", xmidi(b"\xf7\x01\x00" + end), True, "sysex escape 0xf7"),
        ("xmidi_form", xmidi(b"\xf8" + end), False, "0xf8 不是合法 status"),
        ("xmidi_form", xmidi(b"\xff\x01\x81\x00" + bytes(128) + end), True, "meta 長度 2 byte VLQ(128)"),
        ("xmidi_form", xmidi(b"\xff\x01\x81\x00" + bytes(127) + end), False, "meta 宣告 128 只有 127"),
        ("xmidi_form", xmidi(b"\x90\x3c\x40\x81"), False, "note on 音長 VLQ 讀到事件流尾"),
        ("xmidi_form", xmidi(b"\xff\x01\x81\x81"), False, "meta 長度 VLQ 讀到事件流尾"),
        ("xmidi_form", xmidi(b"\xff\x01\x05\x00"), False, "meta 宣告 5 byte,事件流只剩 1 byte"),
        ("xmidi_form", xmidi(b"\xf0\x81\x81\x81"), False, "sysex 長度 VLQ 讀到事件流尾"),
        ("xmidi_form", xmidi(b"\xf0\x05\x00\x00"), False, "sysex 宣告 5 byte,事件流只剩 2 byte"),
        ("xmidi_form", xmidi(end, info=b"\x01\x00\x00\x00"), False, "INFO 長度 4"),
        ("xmidi_form", xmidi(end, info=b"\x00\x00"), False, "INFO 序列數 0"),
        ("xmidi_form", xmidi(end, cat_type=b"XMIX"), False, "CAT 型別不是 XMID"),
        ("xmidi_form", xmidi(end, info=b"\x02\x00"), False, "序列數 2,CAT 內只有 1 個 FORM"),
        ("xmidi_form", xmidi(end, info=b"\x02\x00", forms=2), True, "序列數 2,CAT 內 2 個 FORM"),
        ("xmidi_form", xmidi(end, form_type=b"XMIX"), False, "內層 FORM 型別不是 XMID"),
        ("xmidi_form", xmidi(end, sub=b"EVN"), False, "內層 FORM 的 chunk 檔頭不完整"),
        ("xmidi_form", xmidi(end, sub=chunk(b"EVNT", end + b"\x00") + chunk(b"TIMB", b"\x00\x00")), False,
         "EVNT 在 TIMB 前面"),
        ("xmidi_form", xmidi(end, st.pack("<H", 2) + b"\x00\x01"), False, "TIMB 宣告 2 筆,長度只有 4"),
    ]
    return cases


def selftest() -> int:
    """對原版 .DAT 核對:每種格式接受的筆數恰好等於 EXPECTED_ACCEPT;接受的每一筆截斷 1 byte、尾端多 1 byte
    都要不通過;每種格式至少有一種改表頭的對照不通過;沒有任何一筆被 0 個 probe 以外的格式誤收到別的 .DAT。"""
    import os
    from pathlib import Path

    fails: list[str] = []

    def check(name: str, cond: bool) -> None:
        print(f"  {'PASS' if cond else 'FAIL'}  {name}")
        if not cond:
            fails.append(name)

    sys.path.insert(0, str(Path(__file__).resolve().parent))
    import unpack_dat
    root = Path(__file__).resolve().parents[1]
    gd = Path(os.environ.get("FD2_GAME_DIR") or root / "org_game" / "炎龍騎士團" / "FLAME2")
    dats = ["ANI.DAT", "BG.DAT", "DATO.DAT", "FDFIELD.DAT", "FDMUS.DAT", "FDOTHER.DAT", "FDSHAP.DAT",
            "FDTXT.DAT", "FIGANI.DAT", "TAI.DAT", "TITLE.DAT"]
    res: dict[tuple[str, int], bytes] = {}
    for dat in dats:
        b = (gd / dat).read_bytes()
        for i, (o, n) in enumerate(unpack_dat.parse_directory(b)):
            res[(dat, i)] = b[o:o + n]
    check("原版 11 個 .DAT 共 1005 筆", len(res) == 1005)
    acc = {k: {r for r, b in res.items() if _ok(fn, b)} for k, fn in PROBES.items()}
    for k in PROBES:
        n = len(acc[k])
        check(f"{k} 在原版接受 {EXPECTED_ACCEPT[k]} 筆(實得 {n})", n == EXPECTED_ACCEPT[k])
        cut = [r for r in acc[k] if _ok(PROBES[k], res[r][:-1])]
        ext0 = [r for r in acc[k] if _ok(PROBES[k], res[r] + b"\x00")]
        extf = [r for r in acc[k] if _ok(PROBES[k], res[r] + b"\xff")]
        check(f"{k} 截斷 1 byte / 尾端補 0x00 / 補 0xff 全部不通過", not cut and not ext0 and not extf)
    # 改表頭:前 4 byte 之一 +1(多數格式是寬 / 高 / 筆數 / 長度);每種格式至少擋下一半
    # 前 4 byte 不是表頭欄位的格式,用專屬對照,而且每一筆都要擋下:
    #   vga_palette 第一個值改成 0x40(超出 6 bit);glyph_font16 第 0 字改成全 0(空白字模最多 1 個);
    #   frame_anim 幀數 ±1;field_control 表頭 +2 單位數改成 255(超過實際筆數)
    special = {
        "vga_palette": [lambda b: b"\x40" + b[1:]],
        "glyph_font16": [lambda b: bytes(32) + b[32:]],
        "frame_anim": [lambda b: bytes([(b[0] + 1) & 0xFF]) + b[1:], lambda b: bytes([(b[0] - 1) & 0xFF]) + b[1:]],
        "field_control": [lambda b: b[:2] + b"\xff" + b[3:]],
    }
    for k, muts in special.items():
        kept = [(r, i) for r in sorted(acc[k]) for i, mu in enumerate(muts) if _ok(PROBES[k], mu(res[r]))]
        check(f"{k} 專屬表頭對照擋下全部 {len(acc[k]) * len(muts)} 筆(漏 {len(kept)})", not kept)
    for k in PROBES:
        if k in ("space_crlf", "figani_stub") or k in special:
            continue
        tried = blocked = 0
        for r in sorted(acc[k])[:40]:
            b = bytearray(res[r])
            if len(b) < 4:
                continue
            for pos in range(4):
                m = bytearray(b)
                m[pos] = (m[pos] + 1) & 0xFF
                tried += 1
                blocked += not _ok(PROBES[k], bytes(m))
        check(f"{k} 表頭前 4 byte 各 +1:擋下 {blocked}/{tried}(至少一半)", tried == 0 or blocked * 2 >= tried)
    # 固定內容的格式:別的值不收
    check("space_crlf 只收 20 0d 0a", _ok(PROBES["space_crlf"], b" \r\n") and not _ok(PROBES["space_crlf"], b" \n\r"))
    check("figani_stub 只收 00 00 0a", _ok(PROBES["figani_stub"], b"\x00\x00\x0a")
          and not _ok(PROBES["figani_stub"], b"\x00\x00\x0b") and not _ok(PROBES["figani_stub"], b"\x01\x00\x0a"))
    # 空資料與隨機資料
    import random
    rnd = random.Random(20261119)
    junk = [bytes(rnd.randrange(256) for _ in range(rnd.randrange(1, 600))) for _ in range(300)]
    check("空 bytes 沒有任何 probe 收", not [k for k, fn in PROBES.items() if _ok(fn, b"")])
    check("300 筆隨機 bytes 沒有任何 probe 收", not [k for k, fn in PROBES.items() for j in junk if _ok(fn, j)])
    # 跨格式:除了已知的 raw_image / rlec0_image 共收 FDOTHER 第 15 號,每筆最多一個 probe 接受
    multi = {r: [k for k in PROBES if r in acc[k]] for r in res}
    over = {r: v for r, v in multi.items() if len(v) > 1}
    check("只有 FDOTHER 第 15 號同時被 raw_image 與 rlec0_image 接受",
          over == {("FDOTHER.DAT", 15): ["raw_image", "rlec0_image"]})
    none = sorted(r for r, v in multi.items() if not v)
    check("沒有 probe 收的 40 筆正好是 11 筆空資源 + FDOTHER 29 個巢狀容器",
          len(none) == 40 and all(len(res[r]) == 0 or res[r][:6] == b"LLLLLL" for r in none))
    cases = _selftest_boundary_cases()
    bad = [f"{k} {note}" for k, b, want, note in cases if _ok(PROBES[k], b) != want]
    check(f"人工邊界輸入 {len(cases)} 筆全部判對(錯 {bad[:3]})", not bad)
    print(f"selftest: {'PASS' if not fails else 'FAIL'}({len(fails)} 項失敗)")
    return 1 if fails else 0


if __name__ == "__main__":
    if sys.argv[1:] == ["--selftest"]:
        sys.exit(selftest())
    print(__doc__)
    sys.exit(0)
