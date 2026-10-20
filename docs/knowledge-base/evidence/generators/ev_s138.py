"""續一百三十八證據:evidence/remaining_items_offline_s138_20261020.json。

續一百三十七「仍留的」逐項找離線做得到的部分:
(A) lc131a 在標題上選新遊戲的按鍵:標題序列 0x1f894 在選單前以 kbd_flush 清空 BIOS 鍵盤緩衝,選單以 int 16h AH=10h 阻塞讀鍵、
    沒有逾時,初值是第 0 項(START),只有 Enter / Space / 掃描碼 0xe0 / 0x52 會確認。所以戰鬥裡留在緩衝的鍵到不了選單。
    第二次結束回合時 find_empty_adjacent_tile 的清對話迴圈(每按一次 Return、等 0.6 秒、截一張)把整段拍了下來:
    第 9、10 張是 GAME OVER(= FDOTHER #79 的兩個影格,0x22e5c 畫的),第 17 張是靜止的標題選單(START 反白,與開機時同一畫面),
    第 18 張是同一畫面只換調色盤(確認後的淡出),第 19 張全黑,第 20 張起是新遊戲開場;之後的截圖對白是 FDTXT_033 的
    「多謝父王。」—— 這串字模在 35 份 FDTXT 裡只出現一次,而寫入 [0x53c03] = 0x20(借章節 32)只有新遊戲開場 0x3231b 一處。
(B) 其他章節的明暗:第 27 章(地圖 26)ch27sky_probe 的 7 張截圖,每張「和沒有明暗的參考幀整格不同」的格子都只能用
    FDOTHER_003 的某一階換色表解釋(0 個不符),其他階都有上千個不符;捲動錯一欄就解釋不了。
(C) 灰階版 0x4e1a6 在畫面上:3 張截圖找到已行動單位的灰階圖示((v & 7) + 0x18,每個灰階索引一色),但那兩張圖示都沒有模式 1。
(D) 2026-08-29 / 08-30 兩輪(地圖 29 那張與本輪 ch27sky)的 EXE:當時 harness 啟動時整個複製 ~/fd2-run;對話紀錄記下的
    ~/fd2-run/FD2.EXE 在 09-01、09-02 的 md5 是 72e36e47…,mtime 是 Aug 19 11:07,與參考版只差從檔案位移 502624 起 252 bytes
    (第 3 個物件的資料),09-02 才還原。
全部從 FD2.EXE、extracted/raw、.wsl_build 的截圖與呼叫紀錄、對話紀錄摘錄與 git 歷史重算;任何判準或預測不符就 assert 失敗。
"""
from __future__ import annotations

import json
import re
import struct
import sys

import numpy as np
from PIL import Image

from _evpaths import GAME, ROOT, git_blob, out_path, rel, require_inputs  # noqa: E402
require_inputs(__file__)
sys.path.insert(0, str(ROOT / "tools"))
import callgraph_le as cgm  # noqa: E402
import decode_text as dt  # noqa: E402
import disasm_le as dl  # noqa: E402

EXE_P, FDICON = GAME / "FD2.EXE", GAME / "FDICON.B24"
RAW = ROOT / "extracted/raw"
ENDT = ROOT / ".wsl_build/lc131a_endturn"
SKY = ROOT / ".wsl_build/ch27sky_probe/shots"
EXE_STATE = ROOT / ".wsl_build/s138_exe_state/fd2run_exe_checks.json"
OUT = out_path("remaining_items_offline_s138_20261020.json")
SWEEP_BLOB = "3ffc3dbae14bc9be58704ce84ee1b1e7f0316dea"     # tools/fd2_chapter_sweep.py,2026-09-12 起到 lc131a(10-17)沒改
HARNESS_BLOB = "aa950cd0f2384659bd77160d67cbaa767a623be3"   # tools/dosbox_harness.sh @ d994282e(08-24),下一次修改是 09-02
CELL, VW, VH = 24, 13, 8

_D = EXE_P.read_bytes()
META = dl.parse_le(_D)
CODE, BASE = dl.load_code(_D, META)
MD = dl._capstone()
FX = cgm.fixup_map(_D, META)


def insn(a: int):
    return next(MD.disasm(CODE[a - BASE:a - BASE + 15], a))


def text(a: int, b: int) -> list[str]:
    """[a, b) 逐指令的「位址: 助記符 運算元」。"""
    out = []
    while a < b:
        i = insn(a)
        out.append(f"{a:#x}: {i.mnemonic} {i.op_str}".rstrip())
        a += i.size
    return out


def e8_sites(target: int, lo: int, hi: int) -> list[int]:
    return [a for a in range(lo, hi - 5) if CODE[a - BASE] == 0xE8
            and a + 5 + struct.unpack_from("<i", CODE, a - BASE + 1)[0] == target]


def uniform2x(path) -> float:
    """2 × 2 放大區塊四點同色的比例(調色盤在截圖途中改變時,同一條掃描線放大出的兩列會不同)。"""
    b = np.array(Image.open(path).convert("RGB"))[201:601, 192:832].reshape(200, 2, 320, 2, 3)
    return float((b == b[:, :1, :, :1]).all(axis=(1, 3, 4)).mean())


def frame(path, strict: bool = True) -> np.ndarray:
    """1024 × 768 DOSBox-X 截圖 → 320 × 200 的 24 位元顏色(2 倍放大、原點 (192, 201),取每區塊左上那點)。"""
    a = np.array(Image.open(path).convert("RGB")).astype(np.int64)
    b = a[201:601, 192:832].reshape(200, 2, 320, 2, 3)
    assert not strict or (b == b[:, :1, :, :1]).all(), path
    v = b[:, 0, :, 0]
    return (v[..., 0] << 16) | (v[..., 1] << 8) | v[..., 2]


# ================= (A) 標題選單的按鍵 =================
# 標題序列 0x1f894:開場動畫每圈以 kbd_buffer_has_key(只看 head != tail,不取走)決定要不要跳出
assert text(0x1FC59, 0x1FC66) == ["0x1fc59: call 0x10620", "0x1fc5e: test eax, eax", "0x1fc60: je 0x1fa8c"]
assert text(0x10620, 0x10640)[3:] == ["0x1062d: xor edx, edx", "0x1062f: mov eax, 0x41a", "0x10634: movsx eax, word ptr [eax]",
                                      "0x10637: mov dword ptr [esp], eax", "0x1063a: mov eax, 0x41c", "0x1063f: movsx eax, word ptr [eax]"]
# kbd_flush:tail([0x41c])= head([0x41a]);標題序列呼叫三次,最後一次在讀存檔與選單之前
KBD_FLUSH = text(0x4E381, 0x4E390)
assert KBD_FLUSH == ["0x4e381: push esi", "0x4e382: mov esi, 0x41a", "0x4e387: mov ax, word ptr [esi]",
                     "0x4e38a: mov word ptr [esi + 2], ax", "0x4e38e: pop esi", "0x4e38f: ret"], KBD_FLUSH
FLUSH_SITES = e8_sites(0x4E381, 0x1F894, 0x2000A)
assert FLUSH_SITES == [0x1FA57, 0x1FC9C, 0x1FD7C], [hex(a) for a in FLUSH_SITES]
assert insn(0x1F8B5).mnemonic == "xor" and insn(0x1F8B5).op_str == "ebp, ebp"      # 選擇的初值 0 = START
# 選單:int386(0x16) 以 AH = 0x10 阻塞讀鍵;0x48 / 0x50 上下(項數 1 時不動),Enter / Space / 掃描碼 0xe0 / 0x52 確認
MENU = text(0x1FE2C, 0x1FEF0)
assert MENU == [
    "0x1fe2c: cmp dword ptr [esp + 0x40], 0", "0x1fe31: jne 0x1fef0", "0x1fe37: push dword ptr [esp + 0x50]", "0x1fe3b: push ebp",
    "0x1fe3c: push dword ptr [esp + 0x50]", "0x1fe40: call 0x1ff79", "0x1fe45: add esp, 0xc", "0x1fe48: mov byte ptr [0x3a8e], 0x10",
    "0x1fe4f: push 0x3a8d", "0x1fe54: push 0x3a8d", "0x1fe59: push 0x16", "0x1fe5b: call 0x370f0", "0x1fe60: add esp, 0xc",
    "0x1fe63: movzx eax, byte ptr [0x3a8e]", "0x1fe6a: mov ebx, dword ptr [esp + 0x50]", "0x1fe6e: dec ebx", "0x1fe6f: cmp eax, 0x48",
    "0x1fe72: jne 0x1fe8f", "0x1fe74: push 1", "0x1fe76: push 2", "0x1fe78: push dword ptr [esp + 0x5c]", "0x1fe7c: call 0x25a96",
    "0x1fe81: add esp, 0xc", "0x1fe84: test ebp, ebp", "0x1fe86: jne 0x1fe8c", "0x1fe88: mov ebp, ebx", "0x1fe8a: jmp 0x1fe2c",
    "0x1fe8c: dec ebp", "0x1fe8d: jmp 0x1fe2c", "0x1fe8f: cmp eax, 0x50", "0x1fe92: jne 0x1feb2", "0x1fe94: push 1", "0x1fe96: push 2",
    "0x1fe98: push dword ptr [esp + 0x5c]", "0x1fe9c: call 0x25a96", "0x1fea1: add esp, 0xc", "0x1fea4: cmp ebp, ebx",
    "0x1fea6: jne 0x1feac", "0x1fea8: xor ebp, ebx", "0x1feaa: jmp 0x1fe2c", "0x1feac: inc ebp", "0x1fead: jmp 0x1fe2c",
    "0x1feb2: movzx ebx, byte ptr [0x3a8d]", "0x1feb9: cmp ebx, 0xd", "0x1febc: je 0x1fed3", "0x1febe: cmp ebx, 0x20",
    "0x1fec1: je 0x1fed3", "0x1fec3: cmp eax, 0xe0", "0x1fec8: je 0x1fed3", "0x1feca: cmp eax, 0x52", "0x1fecd: jne 0x1fe2c",
    "0x1fed3: push 1", "0x1fed5: push 1", "0x1fed7: push dword ptr [esp + 0x5c]", "0x1fedb: call 0x25a96", "0x1fee0: add esp, 0xc",
    "0x1fee3: mov dword ptr [esp + 0x40], 1", "0x1feeb: jmp 0x1fe2c"], MENU
ACCEPT = {"ascii": [int(s.split(", ")[1], 16) for s in MENU if s.startswith(("0x1feb9", "0x1febe"))],
          "scan": [int(s.split(", ")[1], 16) for s in MENU if s.startswith(("0x1fec3", "0x1feca"))]}
assert ACCEPT == {"ascii": [0x0D, 0x20], "scan": [0xE0, 0x52]}, ACCEPT
# 確認之後:4 次(不反白 0x50 ms、反白 0x50 ms)閃爍,再淡出(64 步、每步 delay 2);回傳選擇
BLINK = text(0x1FEF0, 0x1FF36)
assert BLINK[-4:] == ["0x1ff2b: inc esi", "0x1ff2c: cmp esi, 4", "0x1ff2f: jl 0x1fef4", "0x1ff31: call 0x1f882"], BLINK
assert len(BLINK) == 22 and BLINK[0] == "0x1fef0: xor esi, esi", BLINK
assert [s for s in BLINK if "0x3790a" in s or s.endswith("push 0x50")] == [
    "0x1ff06: push 0x50", "0x1ff08: call 0x3790a", "0x1ff21: push 0x50", "0x1ff23: call 0x3790a"], BLINK
assert text(0x1F882, 0x1F894)[-2:] == ["0x1f88d: xor ebx, ebx", "0x1f88f: jmp 0x1f51e"]
assert text(0x1F513, 0x1F525) == ["0x1f513: push 2", "0x1f515: call 0x3790a", "0x1f51a: add esp, 4", "0x1f51d: inc ebx",
                                  "0x1f51e: cmp ebx, 0x40", "0x1f521: jl 0x1f503", "0x1f523: pop ebx", "0x1f524: ret"]
assert text(0x1FF72, 0x1FF79) == ["0x1ff72: mov eax, ebp", "0x1ff74: jmp 0x13994"]
CONFIRM_TO_FADE_END_MS = 4 * (0x50 + 0x50) + 0x40 * 2
# title_menu_dispatch:回傳 0 → 章節 0、戰前表第 0 格(新遊戲開場 0x3231b)
DISPATCH = text(0x25EC8, 0x25F17)
assert DISPATCH[:3] == ["0x25ec8: call 0x1f894", "0x25ecd: test eax, eax", "0x25ecf: jne 0x25f3f"], DISPATCH
assert DISPATCH[4] == "0x25ed6: mov dword ptr [0x3c03], 0" and DISPATCH[-1] == "0x25f10: call dword ptr [eax*4 + 0x1d71]"
assert FX[0x51D71] == 0x3231B
# 借章節 32(FDTXT #33)的寫入:全 EXE 只有新遊戲開場裡一處(fixup 欄位存「目標 − 物件基底」)
SET_CH32 = [BASE + m.start() for m in re.finditer(re.escape(bytes.fromhex("c705033c000020000000")), CODE)]
assert SET_CH32 == [0x32326] and text(0x32326, 0x32330) == ["0x32326: mov dword ptr [0x3c03], 0x20"], SET_CH32
# 0x22e5c(勝負碼 1):FDOTHER.DAT 第 0x4f 項,blit_anim_frame 畫第 0 格,淡入,再畫第 1 格
RES79 = text(0x22E82, 0x22EF1)
assert RES79[:4] == ["0x22e82: push 0x4f", "0x22e84: push 0", "0x22e86: push 0x1a4d", "0x22e8b: call 0x111ba"], RES79
assert len(RES79) == 33 and RES79[-1] == "0x22ef0: push ebx", RES79
assert [s for s in RES79 if "0x2eb9f" in s or s.endswith(("push 0", "push 1")) and RES79.index(s) > 4] == [
    "0x22e9a: push 0", "0x22eb5: push 0", "0x22eb8: call 0x2eb9f", "0x22edb: push 1", "0x22ede: call 0x2eb9f"], RES79
assert bytes(dl.object_bytes(_D, META, 0x51A4D, 12)) == b"FDOTHER.DAT\x00"

# ---- FDOTHER #79 的兩個影格 vs 截圖 ----
R79 = (RAW / "FDOTHER/FDOTHER_079.bin").read_bytes()
NFR = struct.unpack_from("<H", R79, 0)[0]
FOFF = [struct.unpack_from("<I", R79, 8 + 4 * k)[0] for k in range(NFR)] + [len(R79)]


def dec4(body: bytes, w: int, h: int) -> np.ndarray:
    """四模式 RLE(模式 1 = 先跳過再寫,續一百三十四);-1 = 不寫。"""
    out = np.full(w * h, -1, np.int16)
    i = pos = 0
    while pos < w * h and i < len(body):
        c = body[i]
        i += 1
        m, n = c >> 6, (c & 63) + 1
        if m == 0:
            out[pos:pos + n] = body[i]
            i += 1
            pos += n
        elif m == 1:
            out[pos + 1:pos + 2 * n:2] = body[i]
            i += 1
            pos += 2 * n
        elif m == 2:
            out[pos:pos + n] = list(body[i:i + n])
            i += n
            pos += n
        else:
            pos += n
    return out


GO = []
for k in range(NFR):
    f = R79[FOFF[k]:FOFF[k + 1]]
    x, y = struct.unpack_from("<HH", f, 0)
    w, h = struct.unpack_from("<HH", f, 9)
    GO.append((x, y, w, h, dec4(f[13:], w, h)))
assert NFR == 2 and [g[:4] for g in GO] == [(69, 61, 181, 75), (130, 141, 55, 8)], [g[:4] for g in GO]
assert [int((g[4] >= 0).sum()) for g in GO] == [9848, 263]


def go_fit(col: np.ndarray, dx: int = 0, dy: int = 0) -> list[tuple[int, int, int]]:
    """每個影格:(衝突數 = 同一索引出現幾種顏色 − 1 的總和, 不同顏色數, 不同索引數)。"""
    res = []
    for x, y, w, h, px in GO:
        blk = col[y + dy:y + dy + h, x + dx:x + dx + w].reshape(-1)
        mk = px >= 0
        a, b = px[mk].astype(np.int64), blk[mk]
        res.append((len(np.unique(a * (1 << 24) + b)) - len(np.unique(a)), len(np.unique(b)), len(np.unique(a))))
    return res


CLEAR = {k: frame(ENDT / f"findempty_clear_{k:03d}.png", strict=False) for k in range(1, 21)}
assert not (ENDT / "findempty_clear_021.png").exists()
UNI = {k: round(uniform2x(ENDT / f"findempty_clear_{k:03d}.png"), 4) for k in CLEAR}
UNI_LOW = {k: u for k, u in UNI.items() if u < 1.0}
assert UNI_LOW == {2: 0.9996, 15: 0.9998, 18: 0.9933}, UNI   # 淡入淡出途中的三張
GO_FIT = {k: go_fit(c) for k, c in CLEAR.items()}
# 判準:兩個影格都 0 衝突,而且顏色不是全部一樣(全黑幀的 0 衝突不算)
GAME_OVER = [k for k, r in GO_FIT.items() if all(c == 0 and nc >= 8 for c, nc, _ in r)]
assert GAME_OVER == [9, 10], GO_FIT
assert GO_FIT[8] == [(0, 1, 63), (0, 1, 9)] and GO_FIT[9] == GO_FIT[10] == [(0, 62, 63), (0, 9, 9)], GO_FIT          # 全黑幀:0 衝突但只有一色(判準要排除它)
GO_KEYS = [8, *GAME_OVER]
assert GO_KEYS == [8, 9, 10], GO_KEYS
GO_SHIFT = {f"{dx},{dy}": go_fit(CLEAR[9], dx, dy) for dx, dy in ((1, 0), (0, 1), (-1, 0))}
assert GO_SHIFT == {"1,0": [(279, 62, 63), (32, 10, 9)], "0,1": [(297, 62, 63), (35, 9, 9)],
                    "-1,0": [(282, 62, 63), (29, 8, 9)]}, GO_SHIFT

# ---- 標題選單的幀 ----
POLL = frame(ENDT / "_poll.png")          # 開機時第一次看到的選單(START 反白)
BOOT_DOWN = frame(ENDT / "title_menu.png")  # 開機時按過 Down(LOAD 反白)
dd = np.nonzero(POLL != BOOT_DOWN)
DD = (len(dd[0]), int(dd[1].min()), int(dd[0].min()), int(dd[1].max()), int(dd[0].max()))
DD_OUT = {"pixels": DD[0], "bbox_xyxy": list(DD[1:])}
assert DD_OUT == {"pixels": 344, "bbox_xyxy": [129, 164, 190, 179]}, DD
MENU_STATIC = [k for k, c in CLEAR.items() if (c == POLL).all()]
assert MENU_STATIC == [17], MENU_STATIC


def full(path) -> np.ndarray:
    """全解析度(640 × 400)的 24 位元顏色:淡出途中同一條掃描線放大出的兩列可能不同,逐列比要用原解析度。"""
    a = np.array(Image.open(path).convert("RGB")).astype(np.int64)[201:601, 192:832]
    return (a[..., 0] << 16) | (a[..., 1] << 8) | a[..., 2]


def rows_not_palette_only(a: np.ndarray, b: np.ndarray, rows) -> list[int]:
    """逐列:a 的每一色在 b 的同一列只對到一色;回傳不成立的列。"""
    return [y for y in rows if len(np.unique(a[y] * (1 << 24) + b[y])) != len(np.unique(a[y]))]


def rgb_mean(c: np.ndarray) -> float:
    return float(((c >> 16) + ((c >> 8) & 255) + (c & 255)).mean() / 3)


POLL_F, BOOT_F = full(ENDT / "_poll.png"), full(ENDT / "title_menu.png")
CLEAR_F = {k: full(ENDT / f"findempty_clear_{k:03d}.png") for k in CLEAR}
BLACK = [k for k, c in CLEAR_F.items() if (c == 0).all()]
BTN_ROWS = range(2 * 164, 2 * 179 + 2)                       # 三個按鈕的列(開機 START / LOAD 反白兩張的差異範圍)
# 淡出中的選單:不是全黑、不等於靜止選單,按鈕列全部是「START 反白」只換調色盤,整張至少 396 / 400 列成立
FADING = [k for k, c in CLEAR_F.items() if k not in BLACK and k not in MENU_STATIC
          and not rows_not_palette_only(POLL_F, c, BTN_ROWS) and len(rows_not_palette_only(POLL_F, c, range(400))) <= 4]
ROWS18 = rows_not_palette_only(POLL_F, CLEAR_F[18], range(400))
BTN18_LOAD = rows_not_palette_only(BOOT_F, CLEAR_F[18], BTN_ROWS)
RATIO18 = round(rgb_mean(CLEAR[18]) / rgb_mean(POLL), 3)
assert FADING == [18] and ROWS18 == [135, 159] and RATIO18 == 0.537, (FADING, ROWS18, RATIO18)
assert [k for k in BLACK if k > 10] == [16, 19], BLACK
# 對照:若反白的是 LOAD(開機按過 Down 那張),按鈕列有 10 列不成立
assert BTN18_LOAD == list(range(330, 340)), BTN18_LOAD

# 截圖迴圈:每次 Return → 0.6 秒 → 截圖(當時的工具原文)
SWEEP = git_blob(SWEEP_BLOB, "tools/fd2_chapter_sweep.py").decode("utf-8")
LOOP = ('            send_keys(name, "Return")\n            time.sleep(0.6)\n'
        '            shot = screenshot(name, shots_dir / f"findempty_clear_{clear_tap:03d}.png")\n')
assert SWEEP.count(LOOP) == 1
MAX_TAPS = int(re.search(r"^DIALOGUE_CLEAR_MAX_TAPS = (\d+)", SWEEP, re.M).group(1))
assert MAX_TAPS == 20 and sorted(CLEAR) == list(range(1, MAX_TAPS + 1)), MAX_TAPS
# 第 17 次 Return 之後 0.6 秒畫面仍是靜止選單;若是它確認,第 18 次 Return 再 0.6 秒(≥ 1.6 秒)時閃爍 + 淡出(合計
# CONFIRM_TO_FADE_END_MS)早已結束、畫面應已全黑;第 18 張還在淡出,所以確認的是第 18 次(推論,假定 delay 已校準)
assert CONFIRM_TO_FADE_END_MS == 768 and CONFIRM_TO_FADE_END_MS < 1600

# ---- 新遊戲開場的對白 ----
FONT = (RAW / "FDOTHER/FDOTHER_004.bin").read_bytes()


def glyph(g: int) -> np.ndarray:
    b = np.frombuffer(FONT[g * 32:(g + 1) * 32], np.uint8)
    return np.unpackbits(b).reshape(16, 16).astype(bool)


TXT_X, TXT_Y = 111, 119


def glyph_at(col: np.ndarray, g: int, x: int, y: int) -> bool:
    """字模的 1 全是同一色,而且那一色不出現在字模的 0。"""
    blk, m = col[y:y + 16, x:x + 16], glyph(g)
    on = blk[m]
    return bool(m.any() and (on == on[0]).all() and not (blk[~m] == on[0]).any())


STRS = {p.name: dt.parse_strings(str(p)) for p in sorted((RAW / "FDTXT").glob("FDTXT_*.bin"))}
assert len(STRS) == 35
USED = sorted({g for ss in STRS.values() for s in ss for g in s if g < 0xFF00})
DLG = {}
for name in ("post_end_turn.png", "after_end3.png"):
    col = frame(ENDT / name)
    ok_at = [{g for g in USED if glyph_at(col, g, TXT_X + 16 * q, TXT_Y)} for q in range(6)]
    win = [(fn, si, j) for fn, ss in STRS.items() for si, s in enumerate(ss) for j in range(len(s) - 5)
           if all(s[j + q] in ok_at[q] for q in range(6))]
    DLG[name] = {"windows": win, "candidates_per_position": [len(o) for o in ok_at],
                 "shift_x1_first_glyph": sum(glyph_at(col, g, TXT_X + 1, TXT_Y) for g in USED)}
assert all(v["windows"] == [("FDTXT_033.bin", 0, 50)] for v in DLG.values()), DLG
assert all(v["shift_x1_first_glyph"] == 0 for v in DLG.values()), DLG
GLYPHS = STRS["FDTXT_033.bin"][0][50:56]
assert GLYPHS == [0x46, 0x52, 0x45E, 0x133, 0x246, 0x231], [hex(g) for g in GLYPHS]
assert all(v["candidates_per_position"] == [1] * len(GLYPHS) for v in DLG.values()), DLG

A = {"title_seq_flush_sites": [hex(a) for a in FLUSH_SITES], "kbd_flush": KBD_FLUSH, "opening_skip_check": "0x1fc59 kbd_buffer_has_key",
     "menu_loop": MENU, "accept": {k: [hex(v) for v in vs] for k, vs in ACCEPT.items()}, "initial_selection": "0x1f8b5 xor ebp, ebp",
     "confirm_blink_fade": BLINK, "confirm_to_fade_end_ms": CONFIRM_TO_FADE_END_MS, "dispatch": DISPATCH,
     "set_chapter32_sites": [hex(a) for a in SET_CH32], "result1_resource79": RES79,
     "fdother79_frames": [list(g[:4]) for g in GO], "game_over_fit_per_shot": {str(k): GO_FIT[k] for k in GO_KEYS},
     "game_over_shots": GAME_OVER, "game_over_shift_control": GO_SHIFT,
     "uniform_2x2_below_1": {str(k): u for k, u in UNI_LOW.items()}, "menu_static_shots": MENU_STATIC, "menu_fading_shots": FADING, "fade_brightness_ratio_18": RATIO18,
     "rows_not_palette_only_18": ROWS18, "button_rows_fail_if_load_highlighted": BTN18_LOAD, "black_shots": BLACK,
     "boot_menu_down_vs_start_diff": DD_OUT,
     "driver": {"blob": SWEEP_BLOB, "loop": LOOP, "max_taps": MAX_TAPS},
     "dialogue": {k: {"windows": [list(w) for w in v["windows"]], "candidates_per_position": v["candidates_per_position"],
                      "shift_x1_first_glyph": v["shift_x1_first_glyph"]} for k, v in DLG.items()},
     "dialogue_glyphs": [hex(g) for g in GLYPHS], "dialogue_xy": [TXT_X, TXT_Y],
     "shots": rel(ENDT),
     "conclusion": "LOG CONFIRMED(DOSBox-X 截圖)+ STATIC ANALYSIS:勝負碼 1 的畫面是 GAME OVER(FDOTHER #79),之後標題選單停在 START,"
                   "確認後進新遊戲開場。確認的鍵是 find_empty_adjacent_tile 清對話迴圈的 Return;是第 18 次(推論:第 17 張是靜止選單、"
                   "第 18 張在淡出,若第 17 次就確認,第 18 張時淡出早已結束)。戰鬥中留在緩衝的鍵在選單前被 kbd_flush 清掉。"}

# ================= (B) 第 27 章(地圖 26)的明暗 =================


def split_tiles(blob: bytes) -> list[np.ndarray]:
    """地形圖塊:模式 0 / 2 的索引,其餘 -1(模式 1 的像素不用,避免依賴次序)。"""
    w, h, n = struct.unpack_from("<HHH", blob, 0)
    assert (w, h) == (CELL, CELL)
    off = [struct.unpack_from("<I", blob, 6 + i * 4)[0] for i in range(n)] + [len(blob)]
    out = []
    for s in range(n):
        b = blob[off[s]:off[s + 1]]
        px = np.full(576, -1, np.int16)
        i = pos = 0
        while pos < 576 and i < len(b):
            c = b[i]
            i += 1
            mm, k = c >> 6, (c & 63) + 1
            if mm == 0:
                px[pos:pos + k] = b[i]
                i += 1
                pos += k
            elif mm == 1:
                i += 1
                pos += 2 * k
            elif mm == 2:
                px[pos:pos + k] = list(b[i:i + k])
                i += k
                pos += k
            else:
                pos += k
        out.append(px)
    return out


def load_map(m: int) -> tuple[list[np.ndarray], list[int], int, int]:
    tl = split_tiles((RAW / f"FDSHAP/FDSHAP_{2 * m:03d}.bin").read_bytes())
    fb = (RAW / f"FDFIELD/FDFIELD_{3 * m:03d}.bin").read_bytes()
    w, h = struct.unpack_from("<HH", fb, 0)
    return tl, [struct.unpack_from("<H", fb, 4 + 4 * k)[0] for k in range(w * h)], w, h


def cellpx(col: np.ndarray, cx: int, cy: int) -> np.ndarray:
    return col[4 + CELL * cy:4 + CELL * cy + CELL, 4 + CELL * cx:4 + CELL * cx + CELL].reshape(576)


def tile_ok(px: np.ndarray, scr: np.ndarray) -> bool:
    """模式 0 / 2 的像素:索引與顏色一對一。"""
    mk = px >= 0
    if mk.sum() < 300:
        return False
    a, b = px[mk].astype(np.int64), scr[mk]
    return len(np.unique(a * (1 << 24) + b)) == len(np.unique(a)) == len(np.unique(b))


def scroll_of(col: np.ndarray, tl, idx, w, h) -> tuple[int, int, int, int]:
    sc = sorted(((sum(tile_ok(tl[idx[(sy + cy) * w + sx + cx]], cellpx(col, cx, cy)) for cy in range(VH) for cx in range(VW)), sx, sy)
                 for sy in range(h - VH + 1) for sx in range(w - VW + 1)), reverse=True)
    return sc[0][1], sc[0][2], sc[0][0], sc[1][0]


def color_map(col: np.ndarray, tl, idx, w, sx: int, sy: int) -> dict[int, int]:
    cm: dict[int, set[int]] = {}
    for cy in range(VH):
        for cx in range(VW):
            px, scr = tl[idx[(sy + cy) * w + sx + cx]], cellpx(col, cx, cy)
            if tile_ok(px, scr):
                for i in np.nonzero(px >= 0)[0]:
                    cm.setdefault(int(px[i]), set()).add(int(scr[i]))
    assert all(len(v) == 1 for v in cm.values())
    return {k: next(iter(v)) for k, v in cm.items()}


F3 = (RAW / "FDOTHER/FDOTHER_003.bin").read_bytes()
N_ENT = struct.unpack_from("<H", F3, 4)[0]
OFFS = [struct.unpack_from("<I", F3, 6 + 4 * i)[0] for i in range(N_ENT)]
assert all(OFFS[i + 1] - OFFS[i] == 0x100 for i in range(N_ENT - 1)) and OFFS[-1] + 0x100 == len(F3)
TRI = list(bytes(dl.object_bytes(_D, META, 0x51A97, 20)))
assert TRI == [min(i, 20 - i) for i in range(20)], TRI
TAB = [np.frombuffer(F3[OFFS[lv]:OFFS[lv] + 256], np.uint8).astype(np.int64) for lv in range(max(TRI) + 1)]

M26 = 26
TL26, IDX26, W26, H26 = load_map(M26)
REF_NAME = "11_after_select2.png"
REF = frame(SKY / REF_NAME)
SX26, SY26, NOK26, RUN26 = scroll_of(REF, TL26, IDX26, W26, H26)
assert (SX26, SY26, NOK26, RUN26) == (9, 49, 77, 31), (SX26, SY26, NOK26, RUN26)
CM26 = color_map(REF, TL26, IDX26, W26, SX26, SY26)
assert len(CM26) == 45


def level_fit(col: np.ndarray, sx: int, sy: int, cm: dict[int, int]) -> tuple[list[tuple[int, int]], dict[int, tuple[int, int]]]:
    """和參考幀整格不同的格:每一階的(符合, 不符)像素數(顏色由參考幀的「索引 → 顏色」表預測)。"""
    region = [(cx, cy) for cy in range(VH) for cx in range(VW) if (cellpx(col, cx, cy) != cellpx(REF, cx, cy)).all()]
    per = {}
    for lv, tab in enumerate(TAB):
        g = m = 0
        for cx, cy in region:
            px, scr = TL26[IDX26[(sy + cy) * W26 + sx + cx]], cellpx(col, cx, cy)
            for i in np.nonzero(px >= 0)[0]:
                c = cm.get(int(tab[px[i]]))
                if c is not None:
                    g += c == scr[i]
                    m += c != scr[i]
        per[lv] = (int(g), int(m))
    return region, per


CH_DIR = f"ch{M26 + 1:02d}"
assert CH_DIR == "ch27" and CH_DIR in SKY.parent.name, (CH_DIR, SKY)
SKY_SHOTS = {"10_after_select.png": 0, "08_cycle_settled.png": 3, "atk1_01_after_select.png": 4, "09_captain0_teleported.png": 5,
             "hudcheck_allyact_selected.png": 9, "allyact_after_move_confirm.png": 8, "12_after_right.png": 2}
B_ROWS = {}
for name, want in SKY_SHOTS.items():
    col = frame(SKY / name)
    assert scroll_of(col, TL26, IDX26, W26, H26)[:2] == (SX26, SY26), name
    region, per = level_fit(col, SX26, SY26, CM26)
    zero = [lv for lv, (g, m) in per.items() if m == 0 and g > 0]
    runner = min(m for lv, (g, m) in per.items() if lv != want)
    same = sum((cellpx(col, cx, cy) == cellpx(REF, cx, cy)).all() for cy in range(VH) for cx in range(VW))
    B_ROWS[name] = {"level": want, "levels_with_zero_mismatch": zero, "region_cells": len(region), "identical_cells": int(same),
                    "fit": list(per[want]), "runner_up_mismatch": int(runner)}
    assert zero == [want] and per[want][0] > 20000 and runner > 2000, (name, per)
assert sorted(v["region_cells"] for v in B_ROWS.values()) == [46, 46, 58, 58, 60, 61, 61], B_ROWS
# 對照:同一幀錯一欄(格子對到旁邊的圖塊)就沒有任何一階解釋得了
_, PER_SHIFT = level_fit(frame(SKY / "10_after_select.png"), SX26 + 1, SY26, CM26)
assert min(m for _, m in PER_SHIFT.values()) == 6780, PER_SHIFT
B = {"map": M26, "chapter_dir": CH_DIR, "scroll": [SX26, SY26], "ref": REF_NAME, "ref_cells_consistent": NOK26, "ref_runner_up": RUN26,
     "ref_color_map_indices": len(CM26), "shots": B_ROWS, "control_shift_x1_min_mismatch": min(m for _, m in PER_SHIFT.values()),
     "remap_levels_tri_0x51a97": TRI, "shots_dir": rel(SKY),
     "exe_note": "2026-08-29 這一輪的 EXE 見 (D):參考版 + 成長表 252 bytes(資料物件),繪製程式碼與 FDOTHER.DAT 相同"}

# ================= (C) 灰階版 0x4e1a6 在畫面上 =================
_fi = FDICON.read_bytes()
_tw, _th, NSPR = struct.unpack_from("<HHH", _fi, 0)
assert (_tw, _th, NSPR) == (24, 24, 1680)
_fo = [struct.unpack_from("<I", _fi, 6 + i * 4)[0] for i in range(NSPR)] + [len(_fi)]
SPR = [dec4(_fi[_fo[s]:_fo[s + 1]], 24, 24) for s in range(NSPR)]
GREY = [np.where(p >= 0, (p & 7) + 0x18, -1) for p in SPR]          # 0x4e1a6 的 (v & 7) + 0x18(續一百三十四釘住的位元組)
assert bytes(dl.object_bytes(_D, META, 0x4E1BA, 8)).hex() == "b407b218b318b718"


def mode1_runs(body: bytes) -> int:
    i = pos = runs = 0
    while pos < 576 and i < len(body):
        c = body[i]
        i += 1
        m, n = c >> 6, (c & 63) + 1
        runs += m == 1
        if m in (0, 1):
            i += 1
            pos += n * (2 if m == 1 else 1)
        elif m == 2:
            i += n
            pos += n
        else:
            pos += n
    return runs


M1 = [mode1_runs(_fi[_fo[s]:_fo[s + 1]]) for s in range(NSPR)]
NONBLANK = [s for s in range(NSPR) if (SPR[s] >= 0).sum() >= 150]
UNIT_DY = -6                                                        # 地圖單位畫在格子上方 6 列(0x75d8 = 0x8088 − 6 × 456)
_draw = bytes(dl.object_bytes(_D, META, 0x1291E, 90)).hex()
assert _draw.count("81c3d8750000") == 1 and (0x75D8 - 0x8088) // 456 == UNIT_DY    # add ebx, 0x75d8


def grey_units(col: np.ndarray) -> list[tuple[int, int, int, int]]:
    """每一格(上移 6 列):灰階畫法下「每個灰階索引一色」而且顏色至少 4 種的圖示。"""
    hits = []
    for cy in range(1, VH):
        for cx in range(VW):
            y0, x0 = 4 + CELL * cy + UNIT_DY, 4 + CELL * cx
            scr = col[y0:y0 + 24, x0:x0 + 24].reshape(576)
            for s in NONBLANK:
                px = GREY[s]
                mk = px >= 0
                a, b = px[mk].astype(np.int64), scr[mk]
                if len(np.unique(a * (1 << 24) + b)) == len(np.unique(a)) and len(np.unique(b)) >= 4:
                    hits.append((cx, cy, s, int(mk.sum())))
    return hits


GREY_SHOTS = {".wsl_build/mvcheck/mv17.png": 0, ".wsl_build/chapter_sweep/ch02/shots/allyact_after_wait_confirm.png": 1,
              ".wsl_build/round_ch23retest_cli/ch23/shots/allyact_after_wait_confirm.png": 22}
C_ROWS = {}
for path, m in GREY_SHOTS.items():
    col = frame(ROOT / path)
    tl, idx, w, h = load_map(m)
    sx, sy, nok, run = scroll_of(col, tl, idx, w, h)
    hits = grey_units(col)
    C_ROWS[path] = {"map": m, "scroll": [sx, sy], "cells_consistent": nok, "runner_up": run,
                    "grey_hits": [[sx + cx, sy + cy, s, n] for cx, cy, s, n in hits],
                    "mode1_runs_in_hit_sprites": [M1[s] for _, _, s, _ in hits]}
assert {p: [tuple(h[:3]) for h in v["grey_hits"]] for p, v in C_ROWS.items()} == {
    ".wsl_build/mvcheck/mv17.png": [(7, 14, 1)],
    ".wsl_build/chapter_sweep/ch02/shots/allyact_after_wait_confirm.png": [(20, 13, 385)],
    ".wsl_build/round_ch23retest_cli/ch23/shots/allyact_after_wait_confirm.png": [(19, 34, 385)]}, C_ROWS
assert all(v["mode1_runs_in_hit_sprites"] == [0] for v in C_ROWS.values())
# 對照:彩色畫法下不同的原索引大多是不同色;畫面上的顏色數等於灰階索引數、少於原索引數 —— 確實是灰階版畫的
COLOR_CTL = {}
for path, (cx, cy, s) in ((".wsl_build/mvcheck/mv17.png", (7, 1, 1)),
                          (".wsl_build/chapter_sweep/ch02/shots/allyact_after_wait_confirm.png", (11, 1, 385))):
    _c0 = frame(ROOT / path)
    _scr = _c0[4 + CELL * cy + UNIT_DY:4 + CELL * cy + UNIT_DY + 24, 4 + CELL * cx:4 + CELL * cx + 24].reshape(576)
    _mk = SPR[s] >= 0
    COLOR_CTL[path] = {"raw_indices": len(np.unique(SPR[s][_mk])), "grey_indices": len(np.unique(GREY[s][_mk])),
                       "screen_colors": len(np.unique(_scr[_mk]))}
assert all(v["screen_colors"] == v["grey_indices"] < v["raw_indices"] for v in COLOR_CTL.values()), COLOR_CTL
assert C_ROWS[".wsl_build/mvcheck/mv17.png"]["scroll"] == [0, 13]
KEYS_POSE0_M1 = [k for k in range(NSPR // 12) if any(M1[s] for s in range(k * 12, k * 12 + 3))]
assert len(KEYS_POSE0_M1) == 35 and 0 not in KEYS_POSE0_M1 and 32 not in KEYS_POSE0_M1, KEYS_POSE0_M1
C = {"shots": C_ROWS, "color_count_control": COLOR_CTL, "keys_whose_pose0_sprites_have_mode1": KEYS_POSE0_M1,
     "note": "找到的灰階圖示是第 0 號鍵(圖示 1)與索爾(第 32 號鍵,圖示 385)的姿勢 0,這兩組姿勢 0 都沒有模式 1;"
             "灰階版的模式 1 次序仍只有靜態證據(續一百三十四釘住的 0x4e1e1 位元組)。"}

# ================= (D) 08-29 / 08-30 兩輪的 EXE =================
EX = json.loads(EXE_STATE.read_text(encoding="utf-8"))["rows"]
assert [r["use_ts"] for r in EX] == ["2026-09-01T15:22:04.824Z", "2026-09-01T15:22:26.910Z", "2026-09-02T15:56:33.503Z",
                                     "2026-09-02T15:56:53.660Z"]
CMP = EX[0]["result"].split("\n")
DIFF_N, DIFF_OFFS = int(CMP[0]), [int(CMP[2].split()[0]), int(CMP[-1].split()[0])]
assert CMP[0].strip() == "252" and DIFF_N == 252 and DIFF_OFFS == [502624, 503139], CMP
assert "72e36e47f1f7d77dc102839262956480  /home/kg701004/fd2-run/FD2.EXE" in EX[1]["result"]
assert "33464c81e6a364fd0660141139aa8e6e  /home/kg701004/fd2-run/FD2.EXE.pristine_bak" in EX[1]["result"]
LS = [ln for ln in EX[2]["result"].split("\n") if ln.startswith("-rw") and ln.endswith("/home/kg701004/fd2-run/FD2.EXE")]
assert len(LS) == 1 and " Aug 19 11:07 " in LS[0] and "72e36e47f1f7d77dc102839262956480" in EX[2]["result"], EX[2]["result"]
assert "cp -v FD2.EXE.pristine_bak FD2.EXE" in EX[3]["command"] and "33464c81e6a364fd0660141139aa8e6e  FD2.EXE\n" in EX[3]["result"]
HARN = git_blob(HARNESS_BLOB, "tools/dosbox_harness.sh").decode("utf-8")
assert 'SOURCE_GAME_DIR="${FD2_HARNESS_SOURCE_DIR:-$HOME/fd2-run}"' in HARN and 'cp -r "$SOURCE_GAME_DIR"/. "$workdir"/' in HARN
# cmp 的位移(1 起算)502624 .. 503139 在第 3 個物件(資料)的檔案範圍裡
PSZ, DOFF = META["page_size"], META["data_off"]
ranges, f0 = [], DOFF
for o in META["objs"]:
    ranges.append((f0, f0 + o["pages"] * PSZ, o["base"]))
    f0 += o["pages"] * PSZ
obj = [r[2] for r in ranges if r[0] <= 502624 - 1 and 503139 <= r[1]]
assert obj == [0x60000], (obj, ranges)
D = {"exe_md5_then": "72e36e47f1f7d77dc102839262956480", "diff_bytes": DIFF_N,
     "diff_file_offsets_1based": DIFF_OFFS,
     "diff_object": hex(obj[0]), "mtime_shown_on_0902": "Aug 19 11:07", "restored_utc": EX[3]["result_ts"],
     "harness_blob": HARNESS_BLOB, "transcript_rows": rel(EXE_STATE),
     "conclusion": "INFERRED(對話紀錄 + git 歷史):08-19 到 09-02 之間 ~/fd2-run/FD2.EXE 沒有寫入(09-02 顯示的 mtime 仍是 08-19),"
                   "md5 72e36e47…;harness 當時固定整個複製 ~/fd2-run,驅動腳本沒有改來源。所以 08-29 ch27sky 與 08-30 地圖 29 那張的 EXE "
                   "是參考版 + 資料物件裡 252 bytes 的成長表修改,程式碼物件相同。"}

ev = {"note": "FD2.EXE md5 33464c81e6a364fd0660141139aa8e6e(參考版)。(A)(C) DOSBox-X 截圖 + 靜態分析;(B) DOSBox-X 截圖 + 資產解析;"
              "(D) 對話紀錄摘錄 + git 歷史。",
      "A_title_key_after_game_over": A, "B_move_range_remap_ch27_on_screen": B, "C_grey_units_on_screen": C,
      "D_exe_of_0829_0830_rounds": D}
OUT.write_bytes((json.dumps(ev, ensure_ascii=False, indent=1) + "\n").encode("utf-8"))
print("ok", "A", GAME_OVER, MENU_STATIC, FADING, "B", {k: v["level"] for k, v in B_ROWS.items()},
      "C", {k[-30:]: v["grey_hits"] for k, v in C_ROWS.items()}, "D", D["exe_md5_then"])
