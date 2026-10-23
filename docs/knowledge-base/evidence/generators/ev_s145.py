"""續一百四十五證據:evidence/afterlock_live_title_transition_s145_20261021.json。

原版 FD2.EXE(md5 33464c81e6a364fd0660141139aa8e6e)開場「金鎖(ANI #0)之後」到主選單靜止,DOSBox-X 連拍 444 張
(.wsl_build/s145_afterlock/,t0 起 43.5–65.5 秒,不送按鍵)。續一百四十一 / 一百四十二的連拍在金鎖第 21 幀結束,
esi 24 → 0、esi == 10 的浮空城插播、esi == 0 的停留與之後的轉場都是 NOT TESTED;本證據補上這一段。

判準(同 ev_s141):
    絕對:實拍顏色 = 調色盤 6-bit 值以 (v << 2) | (v >> 4) 擴成 8-bit 後的 RGB,逐像素相等(遊戲區 640×400:水平兩點斷言相同,
    每個遊戲列取上面那條主機列;上下兩條主機列不同的遊戲列記 split_rows)。
    淡入淡出:調色盤在畫面掃描途中被改寫,一張實拍可能分成好幾段,每段一份調色盤。判準是「每一列裡同一個索引只顯示
    一個顏色」,把映射相容的相鄰列合併成段並記段數。單色畫面(全紅、全白、全黑)對任何索引圖都成立,不拿來判讀
    (退化樣本),另外以顏色本身判定。對照:同一張實拍配其他候選索引圖時,逐列一致的列數。
title_seq 的觸發與參數直接讀原版 EXE 位元組(位址綁 md5):
    esi == 0x19 → wrapper 0x1f81e 播 ANI #0,`play_afm` 回來後**沒有 ret**,直接落進 0x1f882(64 步淡出)。
    esi == 0xa → 0x1f73f(調色盤 #0x4c、圖 #0x4b):第一步就呼叫 0x1f882 淡出(0x1f74a),之後清黑、blit、淡入、停留、淡出、復原捲動。
    捲動每步 delay 0x1e ms;esi == 0 額外 delay 0x3e8 ms;之後 esi 0x28 → 0 每步呼叫 0x2df01(0, 0xff, esi, 0x3f, 0, 0)、delay 8 ms
    (全部 256 色往 (0x3f, 0, 0) 靠攏 = 淡成純紅);之後清畫面、播 ANI #1(logo)、標題圖 FDOTHER #7 sub0 + 調色盤 #8。

續一百四十六(sweep_literals 逃過 35 個常數,改判準、不釘量測值):
    撕裂幀改在主機列(400 列)判讀:每條主機列整列等於相鄰兩個 dy 之一、兩個都用得到,不寫死段數(44.02 是舊 / 新 / 舊三段);
    淡入淡出的候選圖改成全部 dy(原本只給時間上最近的兩個絕對捲動幀),對照拿到同樣的搜尋自由度;
    首末值改 min / max 並斷言時間嚴格遞增;捲動速率的區間改成「dy 0 停留之前」;轉場只輸出 EXE 的 esi 起點(步數只進斷言);
    目標色 G / B 也讀 EXE;rows_consistent / ani_match 開頭自我測試;純紅那張的 R / G / B 平均斷言 = 目標色。

續一百四十八(續一百四十五 not_covered 的兩項,既有實拍重算):
    0x2df01 逐索引重算:lo ≤ 索引 < hi 每個分量 = tgt + (src − tgt) × t / 0x28(idiv,向 0 截斷),src 是 [0x53a65] 的調色盤。
    紅閃光與白 → 標題兩段的每一條主機列,不是整列等於某一步,就是 DAC 由索引 0 往上寫到一半(索引 < k 是這一步、≥ k 是上一步);
    對照:同樣的搜尋改用向下取整。logo 末幀「變亮」那張是 0x11df2(0, 0xff, 0x40)(每個分量 + 0x40、超過 0x3f 截成 0x3f = 全白)
    在掃描途中生效:上半是 ANI #1 末幀、下半已經全白;白幀最後一條主機列已是 0x2df01 esi == 0 寫到一半。
    選單:0x1ff79(圖, 選中項, 項數) 依 EXE 的位置 / sub 號疊在標題上,項數由 FD2.SAV(解密後檢查碼)決定;整張逐像素相等,
    其他 (選中項, 項數) 組合都不相等。FD2.SAV 是 harness 從 ~/fd2-run 複製的那份(續一百四十八歸檔到連拍目錄)。
"""
from __future__ import annotations

import hashlib
import itertools
import json
import re
import struct
import sys

import numpy as np
from PIL import Image

from _evpaths import GAME, ROOT, TOOLS, out_path, rel, require_inputs  # noqa: E402
require_inputs(__file__)
sys.path.insert(0, str(TOOLS))
import decode_ani  # noqa: E402
import decode_sprite  # noqa: E402
import unpack_dat  # noqa: E402
from disasm_le import object_bytes  # noqa: E402
from le_xref import parse_le  # noqa: E402

SHOTS = ROOT / ".wsl_build/s145_afterlock/shots"
RAW = ROOT / "extracted/raw/FDOTHER"
ANI = ROOT / "extracted/raw/ANI"
EXE = GAME / "FD2.EXE"
OUT = out_path("afterlock_live_title_transition_s145_20261021.json")
SCROLL_FRAMES = [f"FDOTHER_{n:03d}.bin" for n in range(69, 74)]   # 捲動緩衝 #0x45–#0x49(ev_s141)
OX, OY = 192, 201          # 1024×768 根視窗裡遊戲區的左上角
MD5 = "33464c81e6a364fd0660141139aa8e6e"
MAX_DY = 80                # 這段只會出現 dy ≤ 0x19 + 撕裂;搜尋範圍放寬,不讓上界替結論做決定


def decode(body: bytes, w: int, h: int) -> np.ndarray:
    """四模式 RLE(dither 版,ev_s141 的 decode);透明 = 0。"""
    out = bytearray()
    total = w * h
    i = 0
    while len(out) < total and i < len(body):
        c = body[i]
        i += 1
        m, n = c >> 6, (c & 63) + 1
        if m == 0:
            out += bytes([body[i]]) * n
            i += 1
        elif m == 1:
            out += bytes([0, body[i]]) * n
            i += 1
        elif m == 2:
            out += body[i:i + n]
            i += n
        else:
            out += bytes(n)
    assert i == len(body) and len(out) == total, (i, len(body), len(out), total)
    return np.frombuffer(bytes(out), dtype=np.uint8).reshape(h, w)


def image(blob: bytes) -> np.ndarray:
    w, h = struct.unpack_from("<HH", blob, 0)
    assert (w, h) == (320, 200) or w == 320, (w, h)
    return decode(blob[4:], w, h)


def pal_arr(pal6: bytes) -> np.ndarray:
    """768 byte 的 6-bit 調色盤 → 256 × 3 的 6-bit 值。"""
    assert len(pal6) == 768, len(pal6)
    return np.frombuffer(bytes(pal6), dtype=np.uint8).reshape(256, 3).astype(np.int64)


def rgb_arr(a6: np.ndarray) -> np.ndarray:
    """256 × 3 的 6-bit 值 → 每個索引的 24-bit 顏色(DOSBox-X 的擴展)。"""
    a = (a6 << 2) | (a6 >> 4)
    return (a[:, 0] << 16) | (a[:, 1] << 8) | a[:, 2]


def rgb(pal6: bytes) -> np.ndarray:
    """768 byte 的 6-bit 調色盤 → 每個索引的 24-bit 顏色(DOSBox-X 的擴展)。"""
    return rgb_arr(pal_arr(pal6))


def expand(v6: int) -> int:
    return (v6 << 2) | (v6 >> 4)


def fade6(src: np.ndarray, tgt: tuple[int, int, int], t: int, div: int, hi: int, floor: bool = False) -> np.ndarray:
    """0x2df01 的一步:索引 < hi 每個分量 = tgt + (src − tgt) × t / div(idiv,向 0 截斷),其餘不動。

    floor=True 改成向下取整,只給對照用。
    """
    tg = np.array(tgt, dtype=np.int64)
    n = (src - tg) * t
    q = n // div if floor else np.sign(n) * (np.abs(n) // div)
    out = src.copy()
    out[:hi] = (q + tg)[:hi]
    return out


def split_k(idx: np.ndarray, host: np.ndarray, new: np.ndarray, old: np.ndarray) -> tuple[int, int] | None:
    """一條主機列 = DAC 由索引 0 往上寫到一半(索引 < k 已是 new、≥ k 仍是 old)時 k 的可行範圍;不成立回 None。"""
    bad_new = np.bincount(idx[new[idx] != host], minlength=256) > 0
    bad_old = np.bincount(idx[old[idx] != host], minlength=256) > 0
    kmin = int(np.flatnonzero(bad_old).max()) + 1 if bad_old.any() else 0
    kmax = int(np.flatnonzero(bad_new).min()) if bad_new.any() else 256
    return (kmin, kmax) if kmin <= kmax else None


def host_rows(path) -> np.ndarray:
    """遊戲區的 400 條主機列 × 320(水平兩點一律相同,斷言;垂直兩列在畫面更新途中可以不同)。"""
    a = np.asarray(Image.open(path).convert("RGB"), dtype=np.int64)[OY:OY + 400, OX:OX + 640]
    key = (a[..., 0] << 16) | (a[..., 1] << 8) | a[..., 2]
    assert (key[:, 0::2] == key[:, 1::2]).all(), path
    return key[:, 0::2]


def live(path) -> tuple[np.ndarray, list[int]]:
    """(320×200 的 24-bit 顏色(每個遊戲列取上面那條主機列), 上下兩條主機列不同的遊戲列 —— 撕裂 / 掃描途中換調色盤)。"""
    host = host_rows(path)
    return host[0::2], np.flatnonzero((host[0::2] != host[1::2]).any(axis=1)).tolist()


def rows_consistent(idx: np.ndarray, col: np.ndarray) -> tuple[int, int | None]:
    """(逐列「一個索引一個顏色」成立的列數, 全部成立時的段數;否則 None)。

    段:相鄰列的索引→顏色映射彼此相容(共有的索引顏色相同)就併成同一段。
    """
    r = np.repeat(np.arange(200, dtype=np.int64), 320)
    key = (r << 8) | idx.ravel().astype(np.int64)
    pair = np.unique((key << 24) | col.ravel())
    k = pair >> 24
    multi = np.unique(k[np.r_[False, k[1:] == k[:-1]]])          # 某列某索引出現 ≥ 2 色
    bad_rows = np.unique(multi >> 8)
    good = 200 - len(bad_rows)
    if good < 200:
        return good, None
    maps = [{} for _ in range(200)]
    for kk, cc in zip(k.tolist(), (pair & 0xFFFFFF).tolist()):
        maps[kk >> 8][kk & 255] = cc
    n, cur = 0, None
    for m in maps:
        if cur is None or any(cur.get(i, c) != c for i, c in m.items()):
            n += 1
            cur = dict(m)
        else:
            cur.update(m)
    return good, n


def ani_frames(fn: str) -> tuple[list[np.ndarray], list[np.ndarray]]:
    """tools/decode_ani.py 的 VM 逐幀執行:(每幀 24-bit 顏色, 每幀索引圖)。"""
    d = (ANI / fn).read_bytes()
    hd = decode_ani.parse_header(d)
    pal, fb = bytearray(768), bytearray(320 * 200)
    cols, idxs = [], []
    for _i, _cs, cc, _r0, _r1, sc in decode_ani.iter_frames(d, hd["frame_count"]):
        decode_ani.run_vm(sc, cc, pal, fb)
        ix = np.frombuffer(bytes(fb), dtype=np.uint8).reshape(200, 320).copy()
        idxs.append(ix)
        cols.append(rgb(pal)[ix])
    assert len(cols) == hd["frame_count"], (fn, len(cols))
    return cols, idxs


def ani_match(F: list[np.ndarray], col: np.ndarray) -> dict | None:
    """單幀完全相等的幀號;否則相鄰兩幀逐像素擇一(畫面正在更新)完全成立的那一對;都沒有回 None。"""
    hits = [k for k, f in enumerate(F) if bool((f == col).all())]
    if hits:
        return {"exact": hits}
    pairs = [k for k in range(len(F) - 1) if bool(((F[k] == col) | (F[k + 1] == col)).all())]
    return {"pair": [pairs[0], pairs[0] + 1]} if pairs else None


def _selftest() -> None:
    """小工具的已知答案:逐列一致的段數 / 壞列、ANI 相鄰兩幀。"""
    idx = np.zeros((200, 320), np.uint8)
    col = np.zeros((200, 320), np.int64)
    idx[0, :2], col[0, :2] = (1, 2), (0xA, 0xB)
    idx[1, 0], col[1, 0] = 1, 0xB                      # 第 1 列索引 1 換了顏色 → 第二段;之後全黑與第二段相容
    assert rows_consistent(idx, col) == (200, 2), rows_consistent(idx, col)
    idx[2:4, :2], col[2:4, :2] = 3, (0xC, 0xD)          # 第 2、3 列同一索引兩種顏色
    assert rows_consistent(idx, col) == (198, None), rows_consistent(idx, col)
    idx1, col1 = np.zeros((200, 320), np.uint8), np.zeros((200, 320), np.int64)
    idx1[0, 0], col1[0, 0] = 1, 0xA                   # 只有第 0 列有索引 1:一段(索引不能跟列號混在一起)
    assert rows_consistent(idx1, col1) == (200, 1), rows_consistent(idx1, col1)
    F = [np.full((1, 2), v, np.int64) for v in (1, 2, 3)]
    assert ani_match(F, np.array([[2, 2]])) == {"exact": [1]}
    assert ani_match(F, np.array([[2, 3]])) == {"pair": [1, 2]}
    assert ani_match(F, np.array([[1, 3]])) is None
    # 0x2df01 一步:(0 − 63) × 1 / 40 向 0 截斷 = −1 → 62;向下取整 = −2 → 61;索引 ≥ hi 不動
    src = np.zeros((256, 3), np.int64)
    assert fade6(src, (63, 0, 0), 1, 40, 255)[0].tolist() == [62, 0, 0]
    assert fade6(src, (63, 0, 0), 1, 40, 255, floor=True)[0].tolist() == [61, 0, 0]
    assert fade6(src, (63, 0, 0), 1, 40, 255)[255].tolist() == [0, 0, 0]
    # DAC 寫到一半:索引 0、1、2 的新 / 舊顏色
    new, old = np.full(256, -1, np.int64), np.full(256, -2, np.int64)
    new[:3], old[:3] = (10, 11, 12), (20, 21, 22)
    ix = np.array([0, 1, 2], np.uint8)
    assert split_k(ix, np.array([10, 21, 22]), new, old) == (1, 1)
    assert split_k(ix, np.array([10, 11, 22]), new, old) == (2, 2)
    assert split_k(ix, np.array([20, 21, 22]), new, old) == (0, 0)
    assert split_k(ix, np.array([10, 11, 12]), new, old) == (3, 256)          # 用到的索引都寫完了,k 的上界不受限
    assert split_k(ix, np.array([10, 21, 12]), new, old) is None


_selftest()

# ---- 原版 FD2.EXE:title_seq 的觸發常數與參數 ----
EXE_B = EXE.read_bytes()
assert hashlib.md5(EXE_B).hexdigest() == MD5, "只用原版 FD2.EXE"
LE = parse_le(EXE_B)


def code(lin: int, n: int) -> bytes:
    return object_bytes(EXE_B, LE, lin, n)


def call_target(lin: int) -> int:
    b = code(lin, 5)
    assert b[0] == 0xE8, (hex(lin), b.hex())
    return lin + 5 + struct.unpack("<i", b[1:])[0]


def imm(lin: int, op: bytes, fmt: str = "<I") -> int:
    """讀 lin 起的一條指令:opcode 必須是 op,回傳緊接在後的立即值(讀錯位址就對不上 opcode,不會悄悄讀到相鄰位元組)。"""
    b = code(lin, len(op) + struct.calcsize(fmt))
    assert b[:len(op)] == op, (hex(lin), b.hex())
    return struct.unpack(fmt, b[len(op):])[0]


assert code(0x1fadd, 2) == b"\x83\xfe"
T_ANI = code(0x1fadd, 3)[2]                                         # = 0x19
assert code(0x1fae2, 6)[0::2] == b"\x6a\x6a\x6a" and call_target(0x1fae8) == 0x1f81e
ANI_INDEX = code(0x1fae6, 2)[1]                                     # = 0(金鎖)
# wrapper 0x1f81e:play_afm 回來、平衡堆疊之後沒有 ret,下一條就是 0x1f882 的開頭(落進淡出)
assert call_target(0x1f87a) == 0x20421 and code(0x1f87f, 3) == b"\x83\xc4\x0c"
FADE_FN = 0x1f87f + 3
assert code(FADE_FN, 5) == b"\x68\x14\x00\x00\x00"                 # 0x1f882 的開頭 push 0x14(guard-page 探測)
assert code(0x1fba4, 2) == b"\x83\xfe"
T_CASTLE = code(0x1fba4, 3)[2]                                      # = 0xa
assert code(0x1fbab, 4)[0::2] == b"\x6a\x6a" and call_target(0x1fbaf) == 0x1f73f
CASTLE_PAL, CASTLE_IMG = code(0x1fbab, 4)[1], code(0x1fbab, 4)[3]   # push 0x4c(idxA 調色盤);push 0x4b(idxB 圖)
FADE_FIRST = call_target(0x1f74a) == FADE_FN                        # 0x1f73f 第一個 call 就是淡出
assert code(0x1fc3a, 1) == b"\x6a" and code(0x1fc3c, 4) == b"\xff\x44\x24\x50" and call_target(0x1fc40) == 0x3790a
STEP_MS = code(0x1fc3a, 2)[1]                                       # 捲動每步 delay = 0x1e
assert code(0x1fc48, 2) == b"\x85\xf6" and code(0x1fc4c, 1) == b"\x68" and call_target(0x1fc51) == 0x3790a
HOLD_MS = struct.unpack("<I", code(0x1fc4d, 4))[0]                   # esi == 0 的停留 = 0x3e8
assert code(0x1fc66, 1) == b"\xbe" and code(0x1fc6b, 2) == b"\xeb\x21"                  # mov esi, imm32;jmp 0x1fc8e(先測條件)
assert code(0x1fc8d, 4) == b"\x4e\x85\xf6\x7d" and code(0x1fc91, 1) == b"\xdb"         # dec esi;test esi, esi;jge 0x1fc6d
TRANS_START = struct.unpack("<I", code(0x1fc67, 4))[0]                # esi 0x28 → 0,jge:esi == 0 那步也做
assert code(0x1fc6d, 4)[0::2] == b"\x6a\x6a" and code(0x1fc71, 1) == b"\x6a"            # push B;push G;push R
B6, G6 = code(0x1fc6d, 4)[1], code(0x1fc6d, 4)[3]                     # 最後 push 的是第一個參數:B 先 push
assert code(0x1fc73, 1) == b"\x56" and code(0x1fc74, 5) == b"\x68\xff\x00\x00\x00" and code(0x1fc79, 2) == b"\x6a\x00"
RED6 = code(0x1fc71, 2)[1]                                           # 目標顏色 R = 0x3f(G、B = 0)
assert call_target(0x1fc7b) == 0x2df01 and code(0x1fc83, 1) == b"\x6a"
TRANS_MS = code(0x1fc83, 2)[1]                                       # = 8
assert code(0x1fcb6, 1) == b"\x6a" and code(0x1fccf, 1) == b"\x6a"
TITLE_IMG, TITLE_PAL = code(0x1fcb6, 2)[1], code(0x1fccf, 2)[1]      # FDOTHER #7 / #8
assert code(0x1fd0e, 6)[0::2] == b"\x6a\x6a\x6a" and call_target(0x1fd14) == 0x20421
LOGO_ANI = code(0x1fd12, 2)[1]                                       # play_afm 第一個參數(最後 push)= 1
assert code(0x1f8c8, 5) == b"\xb9\x0f\x00\x00\x00" and code(0x1f8cf, 5) == b"\xbe\x4e\x20\x00\x00"
TABLE = list(struct.unpack("<15I", code(0x5204e, 60)))
PAL_FLASH, PAL_BASE = code(0x1fbd9, 2)[1], code(0x1fc0f, 2)[1]
FLASH_STEPS = code(0x1fc08, 5)[4]
assert TABLE[-1] == 1000 and T_ANI not in TABLE and T_CASTLE not in TABLE
FLASH_HITS = TABLE[:-1]                                              # 1000 是表尾標記,不是命中值
# 0x2df01(lo, hi, t, R, G, B):imul 之後 sar edx, 31 + idiv(有號、向 0 截斷),除數 mov ebp, 0x28;cmp ebx, hi / jl(hi 不含)
assert code(0x2df17, 1) == b"\xbd" and code(0x2df48, 3) == b"\x0f\xaf\xd7" and code(0x2df4d, 5) == b"\xc1\xfa\x1f\xf7\xfd"
FADE_DIV = struct.unpack("<I", code(0x2df18, 4))[0]                    # = 0x28
assert code(0x2dfb9, 4) == b"\x3b\x5c\x24\x18" and code(0x2dfbd, 2) == b"\x0f\x8c"
RED_HI = imm(0x1fc74, b"\x68")                                         # 紅閃光 hi = 0xff(索引 255 不動)
# 兩段轉場的 src 都是 [0x53a65]:捲動前 0x1fc0f 載入 #PAL_BASE,標題前 0x1fccf 載入 #TITLE_PAL(同一個指標)
PALPTR = code(0x1fc13, 4)
assert code(0x1fc11, 2) == b"\xff\x35" and code(0x1fc24, 5) == b"\xa3" + PALPTR
assert code(0x1fcd1, 6) == b"\xff\x35" + PALPTR and code(0x1fce4, 5) == b"\xa3" + PALPTR
# logo 之後:0x11df2(0, 0xff, 0x40) —— 每個分量 + 0x40,超過 0x3f 就 = 0x3f;cmp ebx, hi / jg(hi 含在內)
assert code(0x1fd2c, 1) == b"\x6a" and code(0x1fd2e, 5) == b"\x68\xff\x00\x00\x00" and code(0x1fd33, 2) == b"\x6a\x00"
assert call_target(0x1fd35) == 0x11df2 and code(0x11e1c, 4) == b"\x39\xfb\x0f\x8f"
assert code(0x11e43, 5) == b"\x01\xf0\x83\xf8\x3f" and code(0x11e48, 3) == b"\x7e\x05\xb8" and code(0x11e4b, 4) == code(0x11e47, 1) + bytes(3)
WHITE_ADD, SAT6 = imm(0x1fd2c, b"\x6a", "<B"), code(0x11e47, 1)[0]      # 0x40;0x3f
# 之後 blit 標題 sub0(0x1fd4a),esi 0 → 0x28(jle)每步 0x2df01(0, 0xff, esi, 0x38, 0x3c, 0x3f) + delay 8 ms:從淡藍白淡到標題調色盤
assert call_target(0x1fd4a) == 0x16886 and code(0x1fd52, 4) == b"\x31\xf6\xeb\x21"
assert code(0x1fd56, 6)[0::2] == b"\x6a\x6a\x6a" and code(0x1fd5c, 2) == b"\x56\x68" and code(0x1fd62, 2) == b"\x6a\x00"
W_B6, W_G6, W_R6 = code(0x1fd56, 6)[1::2]                               # 先 push B
W_HI = imm(0x1fd5d, b"\x68")
assert call_target(0x1fd64) == 0x2df01 and code(0x1fd6c, 1) == b"\x6a" and code(0x1fd76, 3) == b"\x46\x83\xfe" and code(0x1fd7a, 1) == b"\x7e"
W_END, W_MS = code(0x1fd79, 1)[0], imm(0x1fd6c, b"\x6a", "<B")         # esi 0 → 0x28;8 ms
W_START = 0                                                            # 0x1fd52 xor esi, esi(上面斷言);title_states 從這一步起
# 選單:0x1fe1b push n;push ebp(選中項);push 圖;call 0x1ff79。第 k 項:mov eax, 未選 sub;cmp [esp + 8], k;jne;mov eax, 選中 sub;
# push eax;push 圖;push 0x140;push 0xa0000 + y × 320 + x。第 1、2 項先 cmp [esp + 0xc], k;jle(項數 > k 才畫)
assert code(0x1fe1b, 9) == b"\xff\x74\x24\x50\x55\xff\x74\x24\x50" and call_target(0x1fe24) == 0x1ff79
MENU = []
for _m, _gate in ((0x1ff83, None), (0x1ffb2, 0x1ffab), (0x1ffe1, 0x1ffda)):
    _b = code(_m, 32)
    assert _b[0] == 0xB8 and _b[5:9] == b"\x83\x7c\x24\x08" and _b[10:13] == b"\x75\x05\xb8", hex(_m)
    assert _b[17:28] == b"\x50\xff\x74\x24\x08\x68\x40\x01\x00\x00\x68", hex(_m)
    _need = None
    if _gate is not None:
        _g = code(_gate, 6)
        assert _g[:4] == b"\x83\x7c\x24\x0c" and _g[5] == 0x7E, hex(_gate)
        _need = _g[4]
    _y, _x = divmod(struct.unpack("<I", _b[28:32])[0] - 0xA0000, 320)
    MENU.append({"k": _b[9], "unsel": struct.unpack("<I", _b[1:5])[0], "sel": struct.unpack("<I", _b[13:17])[0],
                 "drawn_if_n_gt": _need, "y": _y, "x": _x})
# 選中項 = ebp(0x1f8b5 xor ebp, ebp);項數初值 1(0x1f8a5),FD2.SAV 讀得到且解密後檢查碼相符 → 2,
# 第 0x30c3 + 2 個位元組不是 0xff → 3
assert code(0x1f8b5, 2) == b"\x31\xed" and code(0x1f8a5, 4) == b"\xc7\x44\x24\x50"
SEL0, N0 = 0, imm(0x1f8a5, b"\xc7\x44\x24\x50")
assert code(0x1fdf4, 4) == code(0x1fe07, 4) == code(0x1f8a5, 4)
N_SAV, N_SAV3 = imm(0x1fdf4, b"\xc7\x44\x24\x50"), imm(0x1fe07, b"\xc7\x44\x24\x50")
assert code(0x1fd9d, 1) == b"\x68" and code(0x1fdd8, 2) == b"\x8d\xbe" and code(0x1fdec, 2) == b"\x3b\x86"
assert code(0x1fdfc, 3) == b"\x0f\xb6\x47" and code(0x1fe00, 5) == b"\x3d\xff\x00\x00\x00" and code(0x1fe05, 1) == b"\x74"
SAV_LEN, SAV_SUM_AT = struct.unpack("<I", code(0x1fd9e, 4))[0], struct.unpack("<I", code(0x1fdee, 4))[0]
SAV_N3_AT = imm(0x1fdd8, b"\x8d\xbe") + imm(0x1fdfc, b"\x0f\xb6\x47", "<B")
assert call_target(0x1fdd0) == 0x4df28 and call_target(0x1fde4) == 0x4df09
_dk = code(0x4df35, 16)                                                # mov dx, 0xa5;lodsb;add dx, 0x9014;rol dx, 3;xor al, dl
assert _dk[:2] == b"\x66\xba" and _dk[4:8] == b"\xac\x66\x81\xc2" and _dk[10:13] == b"\x66\xc1\xc2" and _dk[14:16] == b"\x32\xc2"
KEY0, KEY_ADD, KEY_ROL = struct.unpack("<H", _dk[2:4])[0], struct.unpack("<H", _dk[8:10])[0], _dk[13]
assert code(0x4df16, 3) == b"\x83\xe9\x04" and SAV_SUM_AT == SAV_LEN - code(0x4df18, 1)[0]   # 加總前 len − 4 個位元組


def in_flash(dy: int) -> bool:
    return any(h - FLASH_STEPS <= dy <= h for h in FLASH_HITS)


def strictly_flash(dy: int) -> bool:
    return any(h - FLASH_STEPS < dy < h for h in FLASH_HITS)


# ---- 解碼:捲動緩衝、浮空城、標題、ANI #0 / #1 ----
BUF = np.concatenate([image((RAW / fn).read_bytes()) for fn in SCROLL_FRAMES])
assert BUF.shape == (735, 320), BUF.shape
P_BASE = rgb((RAW / f"FDOTHER_{PAL_BASE:03d}.bin").read_bytes())
P_FLASH = rgb((RAW / f"FDOTHER_{PAL_FLASH:03d}.bin").read_bytes())
CASTLE = image((RAW / f"FDOTHER_{CASTLE_IMG:03d}.bin").read_bytes())
P_CASTLE = rgb((RAW / f"FDOTHER_{CASTLE_PAL:03d}.bin").read_bytes())
_t = (RAW / f"FDOTHER_{TITLE_IMG:03d}.bin").read_bytes()
_o, _n = unpack_dat.parse_directory(_t)[0]
TITLE = image(_t[_o:_o + _n])
P_TITLE = rgb((RAW / f"FDOTHER_{TITLE_PAL:03d}.bin").read_bytes())
A0, I0 = ani_frames(f"ANI_{ANI_INDEX:03d}.bin")
A1, I1 = ani_frames(f"ANI_{LOGO_ANI:03d}.bin")
RED = (expand(RED6) << 16) | (expand(G6) << 8) | expand(B6)
WHITE = 0xFFFFFF
P6_BASE = pal_arr((RAW / f"FDOTHER_{PAL_BASE:03d}.bin").read_bytes())
P6_TITLE = pal_arr((RAW / f"FDOTHER_{TITLE_PAL:03d}.bin").read_bytes())
_dir = unpack_dat.parse_directory(_t)
MENU_SUB = {}
for _s in sorted({v for it in MENU for v in (it["unsel"], it["sel"])}):
    _o, _n = _dir[_s]
    _w, _h = struct.unpack_from("<HH", _t, _o)
    _a = decode_sprite.decode_rle_sprite(_t[_o + 4:_o + _n], _w, _h, trans=0)
    assert _a == decode_sprite.decode_rle_sprite(_t[_o + 4:_o + _n], _w, _h, trans=1), _s   # 沒有透明像素:整塊蓋上
    MENU_SUB[_s] = np.frombuffer(_a, dtype=np.uint8).reshape(_h, _w)
    assert (MENU_SUB[_s] == decode(_t[_o + 4:_o + _n], _w, _h)).all(), _s


def sav_decrypt(b: bytes) -> bytes:
    """0x4df28:dx 從 KEY0 起,每個位元組 dx += KEY_ADD、rol dx, KEY_ROL,再 xor dx 的低位元組。"""
    dx, out = KEY0, bytearray()
    for c in b:
        dx = (dx + KEY_ADD) & 0xFFFF
        dx = ((dx << KEY_ROL) | (dx >> (16 - KEY_ROL))) & 0xFFFF
        out.append(c ^ (dx & 0xFF))
    return bytes(out)


SAV = SHOTS.parent / "FD2.SAV"
_sav = SAV.read_bytes()
assert len(_sav) == SAV_LEN, len(_sav)
_dec = sav_decrypt(_sav)
SAV_OK = (sum(_dec[:SAV_SUM_AT]) & 0xFFFFFFFF) == struct.unpack_from("<I", _dec, SAV_SUM_AT)[0]
assert (sum(_sav[:SAV_SUM_AT]) & 0xFFFFFFFF) != struct.unpack_from("<I", _sav, SAV_SUM_AT)[0]   # 對照:不解密就對不上
MENU_N = N0
if SAV_OK:
    MENU_N = N_SAV if _dec[SAV_N3_AT] == 0xFF else N_SAV3

META = json.loads((SHOTS.parent / "meta.json").read_text(encoding="utf-8"))
assert META["exe_md5"] == MD5, META["exe_md5"]
files = sorted(SHOTS.glob("shot_*.png"))
assert len(files) == META["shots"] == 444, (len(files), META["shots"])
T = [float(re.fullmatch(r"shot_(\d+\.\d+)\.png", p.name).group(1)) for p in files]
assert all(a < b for a, b in zip(T, T[1:])), "連拍時間要嚴格遞增"
_lv = [live(p) for p in files]
COLS = [c for c, _s in _lv]
SPLIT = [s for _c, s in _lv]
DT = float(np.median(np.diff(T)))                                    # 連拍間隔(取樣解析度)

# 標題靜止畫面:最後一張。與 #7 sub0 / #8 不同的像素只准落在一個小方框(選單文字,另外疊上去的 sub1–6)
diff = P_TITLE[TITLE] != COLS[-1]
ys, xs = np.nonzero(diff)
MY0, MY1, MX0, MX1 = int(ys.min()), int(ys.max()), int(xs.min()), int(xs.max())
menu_mask = np.zeros((200, 320), bool)
menu_mask[MY0:MY1 + 1, MX0:MX1 + 1] = True
assert diff.sum() < 0.02 * diff.size and menu_mask.sum() < 0.1 * diff.size, (MY0, MY1, MX0, MX1)


def abs_scroll(col: np.ndarray) -> tuple[int, str] | None:
    for dy in range(MAX_DY + 1):
        ix = BUF[dy:dy + 200]
        for k, P in (("base", P_BASE), ("flash", P_FLASH)):
            if bool((P[ix] == col).all()):
                return dy, k
    return None


def torn_scroll(path) -> dict | None:
    """撕裂幀(主機列解析度):每條主機列整列等於相鄰兩個 dy(#0x65)之一,而且兩個都用得到;不寫死段數。

    回 {dy: 較小的 dy(= 較新,捲動往 dy 小的方向), dy_pair, runs: 只有一個 dy 成立的主機列連成的段, lab}。
    """
    host = host_rows(path)
    M = np.array([(P_BASE[np.repeat(BUF[d:d + 200], 2, axis=0)] == host).all(axis=1) for d in range(MAX_DY + 1)])
    pairs = [(d, d + 1) for d in range(MAX_DY)]
    hits = [p for p in pairs if (M[p[0]] | M[p[1]]).all() and not M[p[0]].all() and not M[p[1]].all()]
    if not hits:
        return None
    assert len(hits) == 1, hits
    a, b = hits[0]
    lab = {y: (a if M[a, y] else b) for y in range(len(host)) if M[a, y] != M[b, y]}
    runs = [f"{min(g)}-{max(g)}:dy{k}" for k, g in
            ((k, [y for y, _ in grp]) for k, grp in itertools.groupby(lab.items(), key=lambda u: u[1]))]
    return {"dy": min(a, b), "dy_pair": [a, b], "runs": runs, "lab": lab}


rows = []
for t, col, sp, path in zip(T, COLS, SPLIT, files):
    u = np.unique(col)
    r = {"t": t, "nonblack": int((col != 0).sum()), "split_rows": sp}
    if len(u) == 1:
        r["kind"], r["colour"] = "solid", f"#{int(u[0]):06x}"
    elif (m := ani_match(A0, col)):
        r["kind"], r["ani0"] = "ani0", m
    elif (m := ani_match(A1, col)):
        r["kind"], r["ani1"] = "ani1", m
    elif (s := abs_scroll(col)):
        r["kind"], r["dy"], r["pal"] = "scroll", s[0], s[1]
    elif (d := torn_scroll(path)) is not None:
        lab = d.pop("lab")
        # 上下兩條主機列不同的遊戲列,剛好是兩條都只有一個 dy 成立、而且 dy 不同的遊戲列
        assert sp == sorted(y // 2 for y in lab if y % 2 == 0 and y + 1 in lab and lab[y] != lab[y + 1]), (t, sp)
        r["kind"] = "scroll_torn"
        r.update(d)
    elif bool((P_CASTLE[CASTLE] == col).all()):
        r["kind"] = "castle"
    elif bool((P_TITLE[TITLE] == col)[~menu_mask].all()):
        r["kind"] = "title"
    else:
        r["kind"] = "?"
    rows.append(r)
# 單一畫面、單一調色盤的幀,上下兩條主機列一定相同
assert all(not r["split_rows"] for r in rows
           if r["kind"] in ("scroll", "castle", "title") or "exact" in r.get(r["kind"], {})), "乾淨幀有 split_rows"

# 淡入淡出的候選索引圖:浮空城、標題、兩支 ANI 的末幀,以及捲動緩衝的每一個 dy(對照與答案同樣的搜尋自由度)
CANDS = {"castle": CASTLE, "title": TITLE, "ani0_last": I0[-1], "ani1_last": I1[-1]}
CANDS.update({f"dy{d}": BUF[d:d + 200] for d in range(MAX_DY + 1)})
for i, r in enumerate(rows):
    if r["kind"] != "?":
        continue
    res = {k: rows_consistent(m, COLS[i]) for k, m in CANDS.items()}
    full = [(k, v[1]) for k, v in res.items() if v[0] == 200]
    if len(full) == 1:
        r["kind"], r["fade_of"], r["bands"] = "fade", full[0][0], full[0][1]
        r["control_rows"] = max(v[0] for k, v in res.items() if k != full[0][0])
    elif len(full) > 1:
        full_keys = {k for k, _ in full}
        dy_keys = [k for k in CANDS if k.startswith("dy")]
        r["kind"], r["ambiguous"] = "fade_ambiguous", [k for k in CANDS if k in full_keys and k not in dy_keys]
        r["ambiguous_every_dy"] = all(k in full_keys for k in dy_keys)
        assert r["ambiguous_every_dy"] or not any(k in full_keys for k in dy_keys), (r["t"], sorted(full_keys))

# ---- 依時間分段 ----
def label(r: dict) -> str:
    k = r["kind"]
    if k == "solid":
        return {0: "black", RED: "red", WHITE: "white"}.get(int(r["colour"][1:], 16), "solid_other")
    if k in ("scroll", "scroll_torn"):
        return "scroll"
    if k == "fade":
        return "fade:" + ("dy" if r["fade_of"].startswith("dy") else r["fade_of"])
    return k


segs = []
for i, r in enumerate(rows):
    if r["kind"] in ("?", "fade_ambiguous"):
        continue                                   # 單張過渡幀另計(下面 unexplained),不切斷分段
    lb = label(r)
    if segs and segs[-1]["label"] == lb:
        segs[-1]["rows"].append(r)
    else:
        segs.append({"label": lb, "rows": [r]})
for s in segs:
    s["t"] = [s["rows"][0]["t"], s["rows"][-1]["t"]]
    s["n"] = len(s["rows"])
seq = [s["label"] for s in segs]

# 單張的「?」只准是兩段之間的過渡幀(同時換調色盤又換畫面),不得連續出現
unexplained = [r["t"] for r in rows if r["kind"] in ("?", "fade_ambiguous")]
ux = [i for i, r in enumerate(rows) if r["kind"] in ("?", "fade_ambiguous")]
assert all(b - a > 1 for a, b in zip(ux, ux[1:])) and len(ux) <= 3, unexplained

# 預期的順序(doc39 §10.5 觸發表 + 本版 EXE;位置固定,下面依位置取段)
# 兩處過渡只有一張:金鎖前 dy 0x19 那一張(每列一致但只剩部分列有內容 —— 清黑途中或淡出,分不出機制,只記狀態),
# 以及 logo 末幀「變亮」(續一百四十八:0x11df2 在掃描途中生效,見下面 9)。
EXPECT = ["scroll", "fade:dy", "black", "ani0", "fade:ani0_last", "black", "fade:dy", "scroll", "fade:dy", "black",
          "fade:castle", "castle", "fade:castle", "black", "fade:dy", "scroll", "fade:dy", "red", "black",
          "ani1", "fade:ani1_last", "white", "fade:title", "title"]
assert seq == EXPECT, seq
S = {k: segs[i]["rows"] for i, k in enumerate(["pre_scroll", "dyT_out", "black_a", "ani0", "ani0_out", "black_b",
                                               "dyT_in", "scroll_mid", "dyC_out", "black_c", "castle_in", "castle",
                                               "castle_out", "black_d", "dyC_in", "scroll_end", "red_fade", "red",
                                               "black_e", "ani1", "ani1_out", "white", "title_in", "title"])}
assert all(r["fade_of"] == f"dy{T_ANI}" for r in S["dyT_out"]), S["dyT_out"]
assert [r["dy"] for r in S["pre_scroll"] if r["kind"] == "scroll"][-1] > T_ANI


def lum(r: dict) -> float:
    c = COLS[rows.index(r)]
    return float((((c >> 16) & 255) + ((c >> 8) & 255) + (c & 255)).mean())


assert lum(S["ani1_out"][-1]) > lum(S["ani1"][-1]), (lum(S["ani1_out"][-1]), lum(S["ani1"][-1]))   # 往白變亮

# 1. 金鎖:幀號只增不減,播到最後兩幀以內;播完直接落進淡出(wrapper 沒有 ret)
k0 = [min(r["ani0"].get("exact", r["ani0"].get("pair"))) for r in S["ani0"]]
assert all(x <= y for x, y in zip(k0, k0[1:])), k0
assert max(k0) >= len(A0) - 2, (max(k0), len(A0))
assert FADE_FN == 0x1f882 and all(r["fade_of"] == "ani0_last" for r in S["ani0_out"])

# 2. 金鎖之後恢復捲動:淡入的索引圖是觸發列,第一張絕對捲動幀的 dy 也是
assert all(r["fade_of"] == f"dy{T_ANI}" for r in S["dyT_in"]), S["dyT_in"]
scroll_after = min((r for r in S["scroll_mid"] if r["kind"] == "scroll"), key=lambda r: r["t"])
assert scroll_after["dy"] == T_ANI, scroll_after

# 3. 捲動中的閃光(ev_s141 同一判準):#0x66 只出現在命中值之後 FLASH_STEPS 步內,區間內部不准是 #0x65
for r in rows:
    if r["kind"] == "scroll":
        if r["pal"] == "flash":
            assert in_flash(r["dy"]), r
        else:
            assert not strictly_flash(r["dy"]), r
flash_dys = sorted({r["dy"] for r in rows if r["kind"] == "scroll" and r["pal"] == "flash"})
HITS = [h for h in FLASH_HITS if h < T_ANI]                     # 這段(dy < 0x19)會經過的命中值
assert flash_dys and all(any(h - FLASH_STEPS <= d <= h for h in HITS) for d in flash_dys), (flash_dys, HITS)

# 4. 浮空城插播:觸發列先淡出(0x1f74a 第一個 call 就是淡出),黑、浮空城淡入、整張相等、淡出、黑、同一列淡入復原
assert FADE_FIRST
assert all(r["fade_of"] == f"dy{T_CASTLE}" for r in S["dyC_out"] + S["dyC_in"]), (S["dyC_out"], S["dyC_in"])
nb_out = [r["nonblack"] for r in S["dyC_out"]]
nb_in = [r["nonblack"] for r in S["castle_in"]]
assert nb_out[0] > nb_out[-1] and nb_in[0] < nb_in[-1], (nb_out, nb_in)    # 淡出非黑變少、淡入變多
assert [r["dy"] for r in S["scroll_mid"] if r["kind"] == "scroll"][-1] > T_CASTLE
assert S["scroll_end"][0]["kind"] == "scroll" and S["scroll_end"][0]["dy"] == T_CASTLE, S["scroll_end"][0]
castle_n = len(S["castle"])
assert castle_n >= 3, castle_n


# 5. esi == 0 的停留:dy 0 整張相等的時間長度。對照:dy 1 只停一步
d0 = [r["t"] for r in rows if r["kind"] == "scroll" and r["dy"] == 0]
d1 = [r["t"] for r in rows if r["kind"] == "scroll" and r["dy"] == 1]
hold = max(d0) - min(d0)
one = (max(d1) - min(d1)) if d1 else 0.0
assert hold + 2 * DT >= HOLD_MS / 1000 > one + 2 * DT, (hold, one, DT)
assert hold <= HOLD_MS / 1000 + 0.25, hold
# 捲動速率(浮空城之後到 dy 0 停留之前),對照續一百四十一無負載的 23.6 列 / 秒:每步比它自己的 delay 長
s10 = [(r["t"], r["dy"]) for r in S["scroll_end"] if r["kind"] == "scroll" and r["t"] < min(d0)]
s10_t, s10_dy = [t for t, _ in s10], [d for _, d in s10]
assert all(a >= b for a, b in zip(s10_dy, s10_dy[1:])) and max(s10_dy) == T_CASTLE, s10
rate = (max(s10_dy) - min(s10_dy)) / (max(s10_t) - min(s10_t))
assert 1000 / rate > STEP_MS, rate

# 6. 紅閃光:dy 0 的畫面逐張往純紅靠攏(R 平均只升、G / B 平均只降),然後整張 = (0x3f, 0, 0) 擴成 8-bit
red_fade = S["red_fade"]
assert all(r["fade_of"] == "dy0" for r in red_fade), red_fade


def means(col: np.ndarray) -> tuple[float, float, float]:
    return float(((col >> 16) & 255).mean()), float(((col >> 8) & 255).mean()), float((col & 255).mean())


rgbm = [means(COLS[rows.index(r)]) for r in red_fade]
assert all(a[0] < b[0] and a[1] > b[1] and a[2] > b[2] for a, b in zip(rgbm, rgbm[1:])), rgbm
assert all(r["colour"] == f"#{RED:06x}" for r in S["red"])
assert means(COLS[rows.index(S["red"][0])]) == tuple(float(expand(v)) for v in (RED6, G6, B6))
red_span = min(r["t"] for r in S["red"]) - min(r["t"] for r in red_fade)
assert red_span + DT >= (TRANS_START + 1) * TRANS_MS / 1000, (red_span, TRANS_START, TRANS_MS)
assert len(red_fade) >= 5, len(red_fade)                             # 不是一幀硬切(doc23 §2.4⑤ 原寫法)

# 7. logo 與標題:ANI #1 幀號只增不減;之後整張白、從白淡到標題調色盤、標題靜止到連拍結束
k1 = [min(r["ani1"].get("exact", r["ani1"].get("pair"))) for r in S["ani1"]]
assert all(x <= y for x, y in zip(k1, k1[1:])), k1
assert all(r["fade_of"] == "title" for r in S["title_in"])
# 標題段:選單方框以外都等於 #7 sub0 + #8;選單文字之後才出現,從第一張與最後一張整張相同起到連拍結束都不再變
eq_last = [bool((COLS[rows.index(r)] == COLS[-1]).all()) for r in S["title"]]
first_still = eq_last.index(True)
assert all(eq_last[first_still:]) and len(eq_last) - first_still >= 100, (first_still, len(eq_last))
title_still = S["title"][first_still:]
t_red0, t_title = min(r["t"] for r in red_fade), min(r["t"] for r in title_still)

# 8. 淡入淡出幀的對照:配其他候選圖時沒有一張是逐列全部一致
fades = [r for r in rows if r["kind"] == "fade"]
assert fades and all(r["control_rows"] < 200 for r in fades)
# 調色盤在掃描途中被改寫:至少有一張淡入淡出幀分成多段(只用整張一致判準會把這些幀全部判成解釋不了)
assert max(r["bands"] for r in fades) > 1


# 9. 續一百四十八:0x2df01 逐索引重算、logo 末幀 → 白 → 標題、選單文字
def fade_rows(path, idx_img: np.ndarray, states: dict, prev: dict) -> list[tuple[str, list]]:
    """每條主機列:整列等於某個 DAC 狀態(single),或從 prev[s] 寫到 s 的途中(split,列出可行的 s);都不是記 none。"""
    host = host_rows(path)
    idx = np.repeat(idx_img, 2, axis=0)
    M = {k: (c[idx] == host).all(axis=1) for k, c in states.items()}
    out = []
    for y in range(len(host)):
        single = [k for k in states if M[k][y]]
        if single:
            out.append(("single", single))
            continue
        sp = [k for k in states if prev.get(k) in states and split_k(idx[y], host[y], states[k], states[prev[k]]) is not None]
        out.append(("split", sp) if sp else ("none", []))
    return out


def tally(rr: list[tuple[str, list]]) -> dict:
    t = {k: sum(1 for kk, _ in rr if kk == k) for k in ("single", "split", "none")}
    assert sum(t.values()) == len(rr), (t, len(rr))
    return t


def red_states(floor: bool) -> dict:
    return {t: rgb_arr(fade6(P6_BASE, (RED6, G6, B6), t, FADE_DIV, RED_HI, floor)) for t in range(TRANS_START + 1)}


def title_states(floor: bool) -> dict:
    st = {t: rgb_arr(fade6(P6_TITLE, (W_R6, W_G6, W_B6), t, FADE_DIV, W_HI, floor)) for t in range(W_START, W_END + 1)}
    st[-1] = rgb_arr(np.minimum(P6_TITLE + WHITE_ADD, SAT6))            # -1 = 0x11df2 之後的全白
    return st


RED_ST, TITLE_ST = red_states(False), title_states(False)
assert TRANS_START == FADE_DIV and (RED_ST[TRANS_START] == P_BASE).all()     # 第一步 t = 0x28 = 原色(不變)
assert (RED_ST[0][:RED_HI] == RED).all() and W_END == FADE_DIV and (TITLE_ST[W_END] == P_TITLE).all()
assert (TITLE_ST[-1] == WHITE).all()                                    # + 0x40 對每個 6-bit 值都飽和
RED_PREV = {t: t + 1 for t in range(TRANS_START)}                        # esi 往下數:上一步是 t + 1
TITLE_PREV = {t: t - 1 for t in range(W_START, W_END + 1)}                        # esi 往上數;t = 0 的上一個狀態是全白(-1)
RED_IDX, TITLE_IDX = BUF[0:200], TITLE
idx255 = {"red": bool((RED_IDX == 255).any()), "title": bool((TITLE_IDX == 255).any())}


def fade_frames(rs: list, idx_img: np.ndarray, states: dict, prev: dict) -> list[dict]:
    out = []
    for r in rs:
        rr = fade_rows(files[rows.index(r)], idx_img, states, prev)
        steps = sorted({k for kk, ks in rr if kk == "single" for k in ks})
        out.append({"t": r["t"], **tally(rr), "single_steps": steps})
    return out


red_rows = fade_frames(red_fade, RED_IDX, RED_ST, RED_PREV)
title_rows = fade_frames(S["white"] + S["title_in"], TITLE_IDX, TITLE_ST, TITLE_PREV)
for fr in (red_rows, title_rows):
    assert all(f["none"] == 0 and f["single_steps"] for f in fr), fr
assert all(min(a["single_steps"]) >= max(b["single_steps"]) for a, b in zip(red_rows, red_rows[1:])), red_rows
assert all(max(a["single_steps"]) <= min(b["single_steps"]) for a, b in zip(title_rows, title_rows[1:])), title_rows
assert title_rows[0]["single_steps"] == [-1] and title_rows[0]["split"] >= 1      # 白幀:底下已開始寫 esi == 0
assert sum(f["split"] for f in red_rows) > 0 and sum(f["split"] for f in title_rows) > 0
# 對照:同樣的搜尋(單一步 + 寫到一半)改用向下取整


def floor_control(rs: list, idx_img: np.ndarray, states: dict, prev: dict) -> tuple[int, int]:
    """向下取整的對照:(解釋得了的主機列數, 主機列總數)。"""
    rrs = [fade_rows(files[rows.index(r)], idx_img, states, prev) for r in rs]
    return sum(len(rr) - tally(rr)["none"] for rr in rrs), sum(len(rr) for rr in rrs)


floor_red, floor_red_n = floor_control(red_fade, RED_IDX, red_states(True), RED_PREV)
floor_title, floor_title_n = floor_control(S["title_in"], TITLE_IDX, title_states(True), TITLE_PREV)  # 白幀的全白跟除法無關,不算進對照
assert floor_red < 200 * len(red_fade) and floor_title < 200 * len(S["title_in"]), (floor_red, floor_title)

# logo 末幀「變亮」那張:每條主機列 = ANI #1 末幀,或從末幀寫成全白的途中 / 之後;一旦不是末幀,下面的列也不會回到末幀
ANI1_LAST = np.full(256, -1, np.int64)
ANI1_LAST[I1[-1].ravel()] = A1[-1].ravel()
assert (ANI1_LAST[I1[-1]] == A1[-1]).all()
assert len(S["ani1_out"]) == 1
lw = fade_rows(files[rows.index(S["ani1_out"][0])], I1[-1], {"ani1_last": ANI1_LAST, "white": TITLE_ST[-1]}, {"white": "ani1_last"})
lw_lab = [k if k != "single" else ("either" if len(ks) == 2 else ks[0]) for k, ks in lw]   # either:兩個狀態在這列同色
assert "none" not in lw_lab and lw_lab[0] == "ani1_last" and lw_lab[-1] in ("split", "white"), lw_lab
lw_cut = min(y for y, x in enumerate(lw_lab) if x in ("split", "white"))
assert "ani1_last" not in lw_lab[lw_cut:], lw_lab
lw_spans = [(g[0], g[-1], k) for k, g in ((k, [y for y, _ in grp]) for k, grp in
                                          itertools.groupby(enumerate(lw_lab), key=lambda u: u[1]))]
assert lw_spans[0][0] == 0 and lw_spans[-1][1] == len(lw_lab) - 1, lw_spans      # 各段頭尾相接、蓋滿全部主機列
assert all(a[1] + 1 == b[0] for a, b in zip(lw_spans, lw_spans[1:])), lw_spans
lw_runs = [f"{a}-{b}:{k}" for a, b, k in lw_spans]

# 選單:依 EXE 的位置 / sub 號疊在標題 sub0 上,整張逐像素相等;其他 (選中項, 項數) 組合都不相等


def menu_items(sel: int, n: int) -> list[tuple[dict, np.ndarray]]:
    """畫出來的項與各自的 sub(第 0 項一定畫;其餘要項數 > drawn_if_n_gt)。"""
    return [(it, MENU_SUB[it["sel"] if sel == it["k"] else it["unsel"]]) for it in MENU
            if it["drawn_if_n_gt"] is None or n > it["drawn_if_n_gt"]]


def menu_img(sel: int, n: int) -> np.ndarray:
    img = TITLE.copy()
    for it, a in menu_items(sel, n):
        img[it["y"]:it["y"] + a.shape[0], it["x"]:it["x"] + a.shape[1]] = a
    return img


MENU_FULL = P_TITLE[menu_img(SEL0, MENU_N)]
assert all(bool((COLS[rows.index(r)] == MENU_FULL).all()) for r in title_still)
menu_ctrl = {f"sel{s}_n{n}": int((P_TITLE[menu_img(s, n)] != COLS[-1]).sum())
             for s in range(len(MENU)) for n in range(1, len(MENU) + 1) if (s, n) != (SEL0, MENU_N)}
assert min(menu_ctrl.values()) > 0 and len(menu_ctrl) == len(MENU) ** 2 - 1, menu_ctrl   # 其他全部 (選中項, 項數) 組合
_drawn = menu_items(SEL0, MENU_N)
MENU_BOX = (min(it["y"] for it, _a in _drawn), max(it["y"] + a.shape[0] - 1 for it, a in _drawn),
            min(it["x"] for it, _a in _drawn), max(it["x"] + a.shape[1] - 1 for it, a in _drawn))
_mask = np.zeros(TITLE.shape, bool)                                     # 對照算法:畫到的範圍塗成 True 再取外框
for it, a in _drawn:
    _mask[it["y"]:it["y"] + a.shape[0], it["x"]:it["x"] + a.shape[1]] = True
_my, _mx = np.nonzero(_mask.any(axis=1))[0], np.nonzero(_mask.any(axis=0))[0]
assert MENU_BOX == (_my.min(), _my.max(), _mx.min(), _mx.max()), (MENU_BOX, _my, _mx)
assert MENU_BOX[0] <= MY0 and MY1 <= MENU_BOX[1] and MENU_BOX[2] <= MX0 and MX1 <= MENU_BOX[3], (MENU_BOX, MY0, MY1, MX0, MX1)

ev = {
    "note": "續一百四十五證據:evidence/afterlock_live_title_transition_s145_20261021.json。",
    "inputs": {"shots": rel(SHOTS), "shots_n": len(files), "meta": META, "exe": rel(EXE), "exe_md5": MD5,
               "scroll_buffer": [rel(RAW / fn) for fn in SCROLL_FRAMES], "ani": [f"ANI_{ANI_INDEX:03d}.bin", f"ANI_{LOGO_ANI:03d}.bin"],
               "castle": [f"FDOTHER_{CASTLE_IMG:03d}.bin", f"FDOTHER_{CASTLE_PAL:03d}.bin"],
               "title": [f"FDOTHER_{TITLE_IMG:03d}.bin sub0", f"FDOTHER_{TITLE_PAL:03d}.bin"],
               "sav": rel(SAV), "sav_md5": hashlib.md5(_sav).hexdigest(),
               "sav_note": "harness 啟動時從 ~/fd2-run 複製(mtime 在 t0 之前),續一百四十八歸檔到連拍目錄"},
    "exe_constants": {"ani_trigger_esi": T_ANI, "ani_index": ANI_INDEX, "ani_wrapper_falls_into_fade": f"{FADE_FN:#x}",
                      "castle_trigger_esi": T_CASTLE, "castle_img_pal": [CASTLE_IMG, CASTLE_PAL], "castle_fades_out_first": FADE_FIRST,
                      "scroll_step_ms": STEP_MS, "hold_ms": HOLD_MS, "transition_esi_start": TRANS_START, "transition_step_ms": TRANS_MS,
                      "transition_target_rgb6": [RED6, G6, B6], "logo_ani": LOGO_ANI, "title_img_pal": [TITLE_IMG, TITLE_PAL],
                      "flash_table_0x5204e": TABLE, "flash_steps": FLASH_STEPS, "flash_base_pal": [PAL_FLASH, PAL_BASE],
                      "fade_0x2df01": {"div": FADE_DIV, "division": "idiv(向 0 截斷)", "hi_exclusive": [RED_HI, W_HI]},
                      "white_0x11df2_add": WHITE_ADD, "white_saturate": SAT6,
                      "title_fade": {"target_rgb6": [W_R6, W_G6, W_B6], "esi": [W_START, W_END], "step_ms": W_MS},
                      "menu_0x1ff79": MENU, "menu_init": {"sel": SEL0, "n": N0, "n_sav_ok": N_SAV, "n_sav_byte_not_ff": N_SAV3},
                      "sav": {"len": SAV_LEN, "sum_at": SAV_SUM_AT, "n3_byte_at": SAV_N3_AT, "key": [KEY0, KEY_ADD, KEY_ROL]}},
    "criterion": {"absolute": "實拍顏色 = 6-bit 調色盤 (v<<2)|(v>>4) 逐像素相等",
                  "fade": "每一列同一索引只顯示一個顏色;相容的相鄰列併成段;單色畫面不拿來判讀",
                  "title": f"FDOTHER #{TITLE_IMG} sub0 + #{TITLE_PAL} 逐像素相等(選單方框 rows {MY0}–{MY1}, cols {MX0}–{MX1} 除外,{int(diff.sum())} px)",
                  "torn": "主機列解析度:每條主機列整列等於相鄰兩個 dy 之一,兩個都用得到;runs 只列只有一個 dy 成立的主機列",
                  "fade_candidates": "浮空城、標題、兩支 ANI 末幀、捲動緩衝每一個 dy;control_rows = 其他候選裡逐列一致的最多列數",
                  "fade_formula": "主機列整列等於 0x2df01 某一步,或 DAC 由索引 0 往上寫到一半(索引 < k 這一步、≥ k 上一步);對照改向下取整",
                  "menu": "標題 sub0 疊上 0x1ff79 的各項 sub(位置、sub 號讀 EXE;項數由 FD2.SAV 決定),整張逐像素相等"},
    "sample_interval_s": round(DT, ndigits=4),
    "segments": [{"label": s["label"], "t": s["t"], "n": s["n"]} for s in segs],
    "measurements": {
        "ani0_frames_seen": [min(k0), max(k0)], "ani0_frame_count": len(A0),
        "scroll_resumes_at_dy": scroll_after["dy"], "flash_palette_dys": flash_dys,
        "castle_exact_shots": castle_n, "castle_pre_fade_shots": len(S["dyC_out"]),
        "hold_dy0_s": round(hold, ndigits=3), "dy1_s": round(one, ndigits=3), "scroll_rows_per_s": round(rate, ndigits=1),
        "red_fade_shots": len(red_fade), "red_fade_to_solid_s": round(red_span, ndigits=3),
        "red_fade_rgb_means": [[round(x, ndigits=1) for x in m] for m in rgbm],
        "ani1_frames_seen": [min(k1), max(k1)], "ani1_frame_count": len(A1),
        "red_start_to_title_still_s": round(t_title - t_red0, ndigits=3),
        "fade_shots": len(fades), "fade_bands_max": max(r["bands"] for r in fades),
        "fade_control_rows_max": max(r["control_rows"] for r in fades),
        "unexplained_t": unexplained,
        "red_fade_rows": red_rows, "white_title_fade_rows": title_rows,
        "fade_formula_floor_control_rows": {"red": floor_red, "red_total": floor_red_n,
                                            "title": floor_title, "title_total": floor_title_n},
        "index_255_used": idx255,
        "logo_last_to_white_runs": lw_runs,
        "menu": {"sav_checksum_ok": SAV_OK, "n": MENU_N, "sel": SEL0, "box": list(MENU_BOX), "control_diff_px": menu_ctrl}},
    "rows": rows,
    "conclusion": [
        f"金鎖播到第 {max(k0)} 幀(共 {len(A0)}),wrapper 0x1f81e 沒有 ret,播完直接落進 0x1f882 淡出;捲動在 dy {T_ANI}(觸發列)淡入恢復",
        f"捲動中的閃光:#0x{PAL_FLASH:x} 只出現在 dy {min(flash_dys)}–{max(flash_dys)}(表值 {min(FLASH_HITS)} 之後 {FLASH_STEPS} 步內)",
        f"esi == {T_CASTLE}:dy {T_CASTLE} 先淡出(0x1f73f 的第一個 call 就是 0x1f882,doc23 §2.4⑥ 步驟表漏了),再黑、浮空城 #{CASTLE_IMG}(調色盤 #{CASTLE_PAL})淡入、整張相等 {castle_n} 張、淡出、黑、dy {T_CASTLE} 淡入",
        f"dy 0 停留 {hold:.2f} 秒(EXE {HOLD_MS} ms;dy 1 只 {one:.2f} 秒),捲動 {rate:.1f} 列 / 秒",
        f"紅閃光是 {len(red_fade)} 張、{red_span:.2f} 秒的漸變(0x2df01 esi 0x{TRANS_START:x} → 0 每步 {TRANS_MS} ms 往 (0x{RED6:x},0x{G6:x},0x{B6:x})),不是一幀硬切;之後整張 #{RED:06x}、黑、ANI #{LOGO_ANI}、整張白、淡到標題",
        f"紅閃光開始到標題靜止 {t_title - t_red0:.2f} 秒(doc23 §2.4⑤ 寫約 1.4 秒,那一輪是 docker dosbox 0.74 的較粗取樣)",
        f"0x2df01 逐索引重算(idiv 向 0 截斷):紅閃光 {len(red_fade)} 張、白 → 標題 {len(title_rows)} 張的每一條主機列都是某一步或 DAC 寫到一半;"
        f"向下取整的對照只解釋 {floor_red} / {floor_red_n}、{floor_title} / {floor_title_n} 列",
        f"logo 末幀「變亮」是 0x11df2(0, 0xff, 0x{WHITE_ADD:x})(+ 0x{WHITE_ADD:x} 飽和成全白)在掃描途中生效:{', '.join(lw_runs)};"
        f"之後 blit 標題,esi {W_START} → 0x{W_END:x} 從 (0x{W_R6:x},0x{W_G6:x},0x{W_B6:x}) 淡到標題調色盤",
        f"選單 {MENU_N} 項、選中第 {SEL0} 項(FD2.SAV 檢查碼{'相符' if SAV_OK else '不符'}),整張逐像素相等;其他組合最少差 {min(menu_ctrl.values())} px",
    ],
    "not_covered": ["BGM / 音效",
                    "0x2df01 / 0x11df2 的索引上界(255 不含 / 含):兩張索引圖都沒用到索引 255,實拍判讀不了,只有 EXE 位元組"],
}
OUT.write_bytes((json.dumps(ev, ensure_ascii=False, indent=1) + "\n").encode("utf-8"))
print("ok", len(rows), len(segs), max(k0), round(hold, 3), len(red_fade), round(t_title - t_red0, 3), len(unexplained))
