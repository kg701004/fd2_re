"""續一百五十七證據:evidence/live_items_s157_20261027.json(DOSBox-X 實機,使用者 2026-10-27 核准)。

續一百五十五 / 一百五十六列為「要實機」的 6 項裡,有結果的 4 項(第 5 項三次都沒走到 GAME OVER、第 6 項實機判定不了,不在這裡):
(A) 第 1 項 灰階版 0x4e1a6 的模式 1:兩份 VGA 記憶體傾印(grey1 / grey2)與單位圖快取([0x53a61] 指到的表)。
    畫面上每個活著、整格在視窗內的單位都照 draw_unit_sprite(0x127e0)的影格與畫法逐像素預測;灰階單位的模式 1 是
    「先跳過一格再寫」,值 (v & 7) + 0x18。單位 +2 是本場戰鬥的圖組槽位(查 [0x53a61]),不是 FDICON 組號。
(B) 第 3 項 指令表 0x51d01 第 1、2、5、7 格的入口:一份呼叫紀錄,[0x53af9] = 1 時六名敵人依序施放法術 1、2、5、7、3、6,
    各走到表上那一格的跳板、共用接續點與本體;[0x53af9] = 0 時同六名敵人施法,全部走場景路徑 0x153f2,沒有任何一格的入口。
(C) 第 4 項 索引 255 的 DAC:0x1fc7b 呼叫 0x2df01 的第 39 步,前後以除錯器讀硬體 DAC;調色盤緩衝的 255 事先改成 (1, 2, 3)。
    0 .. 254 等於 ev_s145 的 fade6,255 維持原值(寫了應是 (3, 1, 2))。
(D) 第 2 項 光束炮相位迴圈裡 redraw 的內部時間:修補版 dosbox-x 以 FD2_CALLLOG_ICOUNT 記指令數與模擬時間,
    lc157c / lc157d 是第一輪擺法、lc157e 是第二輪擺法。量之前寫下的預測 P1 .. P5(drivers_s157/pred157_item2.txt)逐項判定。
全部從 FD2.EXE、FDICON.B24、.wsl_build/lc157_live/ 與已提交的證據(ev_s145、續一百二十三、續一百二十九)重算;任何判準或預測不符就 assert 失敗。
"""
from __future__ import annotations

import ast
import hashlib
import json
import re
import statistics
import struct
import sys

import numpy as np

from _evpaths import EVIDENCE, GAME, GEN_DIR, ROOT, out_path, rel, require_inputs  # noqa: E402
require_inputs(__file__)
sys.path.insert(0, str(ROOT / "tools"))
import disasm_le as dl  # noqa: E402

EXE_P, FDICON = GAME / "FD2.EXE", GAME / "FDICON.B24"
RAW = ROOT / ".wsl_build" / "lc157_live"
DRV = GEN_DIR / "drivers_s157"
S145 = EVIDENCE / "afterlock_live_title_transition_s145_20261021.json"
S123 = EVIDENCE / "ai_item_action_item79_flow_20261013.json"
S129 = EVIDENCE / "cmd_table_0_9_coverage_lut_cycles_20261016.json"
S135 = EVIDENCE / "fdicon_mode1_vga_frames_20261019.json"
LUT = EVIDENCE / "lut_circle_ramp_at_unit_20261013.json"
SPELLS = ROOT / "docs" / "data" / "exe_tables" / "spell.json"
OUT = out_path("live_items_s157_20261027.json")
MD5 = "33464c81e6a364fd0660141139aa8e6e"
DELTA = 0x19C000                 # 原生 linear + DELTA = 執行期 EIP

_D = EXE_P.read_bytes()
assert hashlib.md5(_D).hexdigest() == MD5
META = dl.parse_le(_D)


def code(lin: int, n: int) -> bytes:
    return bytes(dl.object_bytes(_D, META, lin, n))


def sha(p) -> str:
    return hashlib.sha256(p.read_bytes()).hexdigest()


# 靜態:位元組逐一釘住(FD2.EXE;資料區位址是未重定位值)
PIN = {
    # ai_spell_execute:法術 [0x53c2f] < 10 時讀 [0x53af9];0 → 0x153f2 場景路徑(call 0x2ff01),否則 0x1540a 地圖路徑:
    # call [法術 × 4 + 0x51d01],返回位址 0x15426
    0x153DE: "833d2f3c00000a7d230fb605f93a000085c0751889e05057ff352f3c0000ff74244ce8fcaa010083c410eb24e8bc800000"
             "a12f3c000089e656ff742430ff742448ff1485011d000083c40ce8c8800000",
    # draw_unit_sprite:時脈 = +4 == 0 ? [0x53c0b] : [0x53c07],3 當 1,+0x26 != 0 時 0;影格 = +2 × 12 + +3 × 3 + 時脈,
    # 取 [0x53a61] 表的位移加表基底;位置 + 0x75d8;+5 bit 7 → 0x4e1a6(灰階),否則 0x4e22a;stride 0x1c8
    0x128F5: "837c24040075088b150b3c0000eb068b15073c000083fa037505ba010000000fb6402685c0740231d26bff0c89f0c1e00229f0"
             "01f801d08b15613a00008b048201d081c3d875000085db0f8c01e2fffff6042480751668c80100008b15493a000001d35350"
             "e8cbb80300eb1468c80100008b15493a000001da5250e831b8030083c40c",
    # draw_unit_sprite 的視窗裁切:x ∈ [sx − 1, sx + [0x51a87]]、y ∈ [sy − 1, sy + [0x51a8b] + 1]
    0x1284E: "4a39d50f8cefe2ffff8b15a93a00000315871a000039d50f8fdbe2ffff8b15ad3a00004a39d30f8ccce2ffff8b15ad3a0000"
             "03158b1a00004239d30f8fb7e2ffff",
    # 0x4e1a6 的灰階值:(v & 7) + 0x18(續一百三十四 / 一百三十八釘住的同一段)
    0x4E1BA: "b407b218b318b718",
}
for _a, _hx in PIN.items():
    assert code(_a, len(_hx) // 2).hex() == _hx, (hex(_a), code(_a, len(_hx) // 2).hex())


def call_target(lin: int) -> int:
    b = code(lin, 5)
    assert b[0] == 0xE8, (hex(lin), b.hex())
    return lin + 5 + struct.unpack("<i", b[1:])[0]


def d32(lin: int) -> int:
    return struct.unpack_from("<i", _D, dl.lin2file(META, lin))[0]


# ================= (A) 第 1 項:灰階版 0x4e1a6 的模式 1 =================
FPS = code(0x1291E, 3)[2]                                   # imul edi, edi, 0xc:每個槽位 12 格
assert code(0x1291E, 3)[:2] == b"\x6b\xff" and code(0x12921, 7) == bytes.fromhex("89f0c1e00229f0")
DIRS = (1 << code(0x12923, 3)[2]) - 1                       # +3 × (4 − 1):每個方向 3 格
assert code(0x1290A, 3) == b"\x83\xfa\x03" and code(0x1290F, 1) == b"\xba"
CLK_FROM, CLK_TO = code(0x1290A, 3)[2], struct.unpack("<I", code(0x12910, 4))[0]     # 時脈 3 當 1
assert code(0x12937, 2) == b"\x81\xc3" and code(0x1294B, 1) == b"\x68" and code(0x12945, 3) == b"\xf6\x04\x24"
POS_OFF = struct.unpack("<I", code(0x12939, 4))[0]          # 0x75d8
STRIDE = struct.unpack("<I", code(0x1294C, 4))[0]           # 0x1c8 = 456
GREY_BIT = code(0x12948, 1)[0]                              # test byte [esp](= +5), 0x80
assert call_target(0x1295A) == 0x4E22A and call_target(0x12970) == 0x4E1A6
GREY_MASK, GREY_BASE = code(0x4E1BA, 2)[1], code(0x4E1BA, 4)[3]
VW, VH = d32(0x51A87), d32(0x51A8B)                         # 視窗格數(初值;裁切用同兩格)
ORIGIN_OFF = 0x8088                                         # redraw 傳給各層的 dst = 緩衝 + 0x8088(ev_s132 的 ORIGIN)
assert (POS_OFF - ORIGIN_OFF) % STRIDE == 0
UNIT_DY = (POS_OFF - ORIGIN_OFF) // STRIDE                  # 單位圖比格子上移 6 列
CELL = code(0x128D9, 3)[2]                                  # imul ebp, ebp, 0x18
assert code(0x128D9, 2) == b"\x6b\xed"
VIEW_XY = tuple(json.loads(S135.read_text(encoding="utf-8"))["vga_unit_offset_probe"]["view_origin"])   # 續一百三十五由 VGA 幀定的視窗原點
assert (FPS, DIRS, CLK_FROM, CLK_TO, GREY_BIT, CELL, UNIT_DY) == (12, 3, 3, 1, 0x80, 24, -6)

# 單位圖快取:[0x53a61] 指到的表,前面是位移(從表基底起算),第一個 0 為止
SPRTAB = (RAW / "sprtab.bin").read_bytes()
OFFS: list[int] = []
while (_v := struct.unpack_from("<I", SPRTAB, 4 * len(OFFS))[0]) != 0:
    assert 4 * len(OFFS) < _v < len(SPRTAB), (len(OFFS), _v)
    OFFS.append(_v)
assert len(OFFS) % FPS == 0
NSLOT = len(OFFS) // FPS
ORDERS = ("skip_then_write", "write_then_skip", "write_both")
REF = ORDERS[0]                                             # 判定用的畫法(另兩種是對照)


def dec4(buf: bytes, pos0: int, order: str) -> tuple[np.ndarray, np.ndarray, int]:
    """四模式 RLE 解一張 24 × 24;回傳 (像素(-1 = 不寫), 模式 1 寫到的位置, 用掉的 byte 數)。order 只影響模式 1。"""
    out = np.full(CELL * CELL, -1, np.int16)
    m1 = np.zeros(CELL * CELL, bool)
    i, pos = pos0, 0
    while pos < CELL * CELL:
        c = buf[i]
        i += 1
        m, n = c >> 6, (c & 63) + 1
        if m == 0:
            out[pos:pos + n] = buf[i]
            i += 1
            pos += n
        elif m == 1:
            sl = {"skip_then_write": slice(pos + 1, pos + 2 * n, 2), "write_then_skip": slice(pos, pos + 2 * n, 2),
                  "write_both": slice(pos, pos + 2 * n)}[order]
            out[sl] = buf[i]
            m1[sl] = True
            i += 1
            pos += 2 * n
        elif m == 2:
            out[pos:pos + n] = list(buf[i:i + n])
            i += n
            pos += n
        else:
            pos += n
    assert pos == CELL * CELL, pos
    return out.reshape(CELL, CELL), m1.reshape(CELL, CELL), i - pos0


# 快取裡的每一格對到 FDICON 的哪一張(內容逐 byte 相同;FDICON 有內容相同的 sprite,全部列出)
_fi = FDICON.read_bytes()
_nspr = struct.unpack_from("<H", _fi, 4)[0]
_fo = [struct.unpack_from("<I", _fi, 6 + 4 * k)[0] for k in range(_nspr)] + [len(_fi)]
_by_body: dict[bytes, list[int]] = {}
for _s in range(_nspr):
    _by_body.setdefault(_fi[_fo[_s]:_fo[_s + 1]], []).append(_s)
SLOT_FDICON: list[list[list[int]]] = []
for _slot in range(NSLOT):
    row = []
    for _f in range(FPS):
        _o = OFFS[_slot * FPS + _f]
        _n = dec4(SPRTAB, _o, REF)[2]
        row.append(_by_body.get(SPRTAB[_o:_o + _n], []))
    SLOT_FDICON.append(row)
assert all(ss for row in SLOT_FDICON for ss in row), "快取裡有對不到 FDICON 的格"
SLOT_GROUPS = [sorted({s // FPS for ss in row for s in ss}) for row in SLOT_FDICON]


def predict(slot: int, frame: int, grey: bool, order: str, fdicon_group: bool = False) -> tuple[np.ndarray, np.ndarray]:
    """draw_unit_sprite 畫出的 24 × 24(-1 = 透明)。fdicon_group=True 是對照:把 +2 當 FDICON 組號。"""
    if fdicon_group:
        s = slot * FPS + frame
        px, m1, _ = dec4(_fi, _fo[s], order)
    else:
        px, m1, _ = dec4(SPRTAB, OFFS[slot * FPS + frame], order)
    if grey:
        px = np.where(px >= 0, (px & GREY_MASK) + GREY_BASE, -1)
    return px, m1


# draw_map_hud 的資訊框:x = [0x51a0c](初值 1;游標在右側時 0x1ad3c 寫 0xf2)、列 0x9d(0x1ad64 imul edi 的列數);
# 大小 69 × 34 是 FDOTHER #5 第 130 格的檔頭(續一百五十五)。x 1 時的框必須等於續一百五十五證據記的框(含兩端)。
assert code(0x1AD3C, 6) == bytes.fromhex("c7050c1a0000") and code(0x1AD64, 2) == bytes.fromhex("69c7")
HUD_X_RIGHT, HUD_ROW = struct.unpack("<I", code(0x1AD42, 4))[0], struct.unpack("<I", code(0x1AD66, 4))[0]
HUD_W, HUD_H = 69, 34


def hud_rect(x0: int) -> tuple[int, int, int, int]:
    """資訊框的螢幕座標(左上含、右下不含);x0 = [0x51a0c]。"""
    return VIEW_XY[0] + x0, VIEW_XY[1] + HUD_ROW, VIEW_XY[0] + x0 + HUD_W, VIEW_XY[1] + HUD_ROW + HUD_H


_hl = hud_rect(d32(0x51A0C))
assert [_hl[0], _hl[1], _hl[2] - 1, _hl[3] - 1] == json.loads(LUT.read_text(encoding="utf-8"))["runs"][0]["excluded_rects"][0], _hl


GREY_DUMPS = {"grey1": "lc157.py grey lc157 0:6:1 2:38:1 1:6:0(#0 +2 = 6 已行動、#2 +2 = 38 已行動、#1 +2 = 6 未行動)",
              "grey2": "lc157.py grey lc157 0:12:1 2:5:1 12:12:0(#0 +2 = 12 已行動、#2 +2 = 5 已行動、#12 +2 = 12 未行動)"}
A_ROWS: dict[str, dict] = {}
BAD_PX: dict[tuple[str, int], list[tuple[int, int]]] = {}
for tag, how in GREY_DUMPS.items():
    scr = np.frombuffer((RAW / f"{tag}_vga.bin").read_bytes(), np.uint8).reshape(200, 320).astype(np.int16)
    meta = json.loads((RAW / f"{tag}_meta.json").read_text(encoding="utf-8"))
    ub = (RAW / f"{tag}_units.bin").read_bytes()
    assert len(ub) == 80 * meta["count"]
    sx, sy = meta["scroll"]
    # 視窗格數的第二個來源:左右各留視窗原點那麼寬、剛好排滿 320;列數排到第 VH 格時還在 200 列內、再多一格就超出
    assert 2 * VIEW_XY[0] + VW * CELL == scr.shape[1] and VIEW_XY[1] + VH * CELL <= scr.shape[0] < VIEW_XY[1] + (VH + 1) * CELL
    rows = {}
    for u in range(meta["count"]):
        r = ub[u * 80:(u + 1) * 80]
        x, y, slot, d, mv, f5 = r[0], r[1], r[2], r[3], r[4], r[5]
        hp = struct.unpack_from("<h", r, 0x40)[0]
        cx, cy = x - sx, y - sy
        if hp <= 0 or not (0 <= cx < VW and 0 <= cy < VH):
            continue
        row = {"xy": [x, y], "cell": [cx, cy], "slot": slot, "f5": f5, "hp": hp}
        if slot >= NSLOT:
            row["result"] = f"槽位 {slot} 超出快取表({NSLOT} 組),畫的是表外的資料,不判"
            rows[u] = row
            continue
        assert mv == 0 and r[0x26] == 0, (tag, u)            # 沒有走動、沒有 +0x26:時脈 = [0x53c0b]
        clk = CLK_TO if meta["c0b"] == CLK_FROM else meta["c0b"]
        frame = d * DIRS + clk
        grey = bool(f5 & GREY_BIT)
        x0, y0 = VIEW_XY[0] + CELL * cx, VIEW_XY[1] + CELL * cy + UNIT_DY
        ys = slice(max(y0, 0) - y0, CELL)
        blk = np.full((CELL, CELL), -2, np.int16)
        blk[ys] = scr[max(y0, 0):y0 + CELL, x0:x0 + CELL]
        res = {}
        for order in ORDERS:
            px, m1 = predict(slot, frame, grey, order)
            vis = px >= 0
            res[order] = [int((vis & (blk == px)).sum()), int(vis.sum()), int((m1 & (blk == px)).sum()), int(m1.sum())]
        row.update({"frame": slot * FPS + frame, "fdicon": SLOT_FDICON[slot][frame], "drawn_by": "0x4e1a6" if grey else "0x4e22a",
                    "hits_visible_mode1": res})
        px, _ = predict(slot, frame, grey, REF)
        BAD_PX[(tag, u)] = [(int(by) + y0, int(bx) + x0) for by, bx in np.argwhere((px >= 0) & (blk != px))]
        row["mismatch_px"] = len(BAD_PX[(tag, u)])
        # 對照:+2 當 FDICON 組號(續一百三十八的讀法)、同一槽位的其他 11 格裡最好的一格、灰階 / 彩色對調
        ctl = {}
        cp, _ = predict(slot, frame, grey, REF, fdicon_group=True)
        ctl["plus2_as_fdicon_group"] = [int(((cp >= 0) & (blk == cp)).sum()), int((cp >= 0).sum())]
        others = []
        for f2 in range(FPS):
            if f2 != frame:
                cp, _ = predict(slot, f2, grey, REF)
                others.append([int(((cp >= 0) & (blk == cp)).sum()), int((cp >= 0).sum())])
        ctl["best_other_frame_same_slot"] = max(others, key=lambda hn: hn[0] - hn[1])
        assert all(o[1] - o[0] >= ctl["best_other_frame_same_slot"][1] - ctl["best_other_frame_same_slot"][0] for o in others)
        cp, _ = predict(slot, frame, not grey, REF)
        ctl["grey_colour_swapped"] = [int(((cp >= 0) & (blk == cp)).sum()), int((cp >= 0).sum())]
        row["controls"] = ctl
        rows[u] = row
    A_ROWS[tag] = {"setup": how, "scroll": [sx, sy], "clock_0x53c0b": meta["c0b"], "units": rows}

FULL = {t: sorted(u for u, r in v["units"].items() if "hits_visible_mode1" in r
                  and r["hits_visible_mode1"][REF][0] == r["hits_visible_mode1"][REF][1]) for t, v in A_ROWS.items()}
assert all((not BAD_PX[(t, u)]) == (u in us) for t, us in FULL.items() for u in A_ROWS[t]["units"] if (t, u) in BAD_PX)
assert FULL == {"grey1": [0, 11, 12, 14, 15, 16], "grey2": [0, 2, 11, 12, 14, 15, 16]}, FULL
# 沒有全中的:逐點看落在哪裡 —— 視窗上緣之外(第 0 列的單位圖上移 6 列,那幾列不送畫面),或之後畫的資訊框裡
# (游標在右側,[0x51a0c] = 0xf2;兩個可能值都試)
WHERE: dict[str, dict[int, str]] = {}
for t, v in A_ROWS.items():
    WHERE[t] = {}
    for u in sorted(set(v["units"]) - set(FULL[t])):
        if (t, u) not in BAD_PX:
            continue
        pts = BAD_PX[(t, u)]
        if all(q[0] < VIEW_XY[1] for q in pts):
            WHERE[t][u] = "above_window"
            v["units"][u]["mismatch_where"] = f"全部在視窗上緣(列 < {VIEW_XY[1]})之外"
        for x0h in (d32(0x51A0C), HUD_X_RIGHT):
            hx0, hy0, hx1, hy1 = hud_rect(x0h)
            if all(hy0 <= q[0] < hy1 and hx0 <= q[1] < hx1 for q in pts):
                WHERE[t][u] = f"hud_x{x0h:#x}"
                v["units"][u]["mismatch_where"] = f"全部在資訊框 x [{hx0}, {hx1})、列 [{hy0}, {hy1}) 內([0x51a0c] = {x0h:#x})"
assert WHERE == {t: {13: f"hud_x{HUD_X_RIGHT:#x}", 17: "above_window"} for t in A_ROWS}, WHERE
assert HUD_X_RIGHT == 0xF2 and all(v["units"][17]["cell"][1] == 0 for v in A_ROWS.values())
assert sorted(set(A_ROWS["grey1"]["units"]) - set(FULL["grey1"]) - set(WHERE["grey1"])) == [2]
assert sorted(set(A_ROWS["grey2"]["units"]) - set(FULL["grey2"]) - set(WHERE["grey2"])) == []
assert A_ROWS["grey1"]["units"][2]["slot"] >= NSLOT
# 全中的單位:每一個對照都不是全中
for t, us in FULL.items():
    for u in us:
        assert all(h < n for h, n in A_ROWS[t]["units"][u]["controls"].values()), (t, u, A_ROWS[t]["units"][u]["controls"])
# 帶模式 1 的只有槽位 12、5 這兩組(grey2 的 #0、#2 灰階,#12 彩色正對照);模式 1 像素「先跳過再寫」全中,另兩種次序都不中
G2 = A_ROWS["grey2"]["units"]
M1_UNITS = {u: G2[u]["hits_visible_mode1"] for u in FULL["grey2"] if G2[u]["hits_visible_mode1"][REF][3]}
assert sorted(M1_UNITS) == [0, 2, 12], M1_UNITS
assert [G2[u]["drawn_by"] for u in (0, 2, 12)] == ["0x4e1a6", "0x4e1a6", "0x4e22a"]
for u, h in M1_UNITS.items():
    sw, ws, both = h[REF], h[ORDERS[1]], h[ORDERS[2]]
    assert sw[2] == sw[3] > 0 and ws[2] == 0 and ws[3] == sw[3], (u, h)
    assert both[3] == 2 * sw[3] and both[2] == sw[2], (u, h)    # 兩格都寫:多寫的那一半都不中(露出的是底下的地形)
assert [M1_UNITS[u][REF][3] for u in (0, 2, 12)] == [8, 1, 8]
assert all(r["hits_visible_mode1"][REF][3] == 0 for t in A_ROWS for u, r in A_ROWS[t]["units"].items()
           if "hits_visible_mode1" in r and not (t == "grey2" and u in M1_UNITS))
# +2 是槽位:grey1 的 #0(+2 = 6)若當 FDICON 第 6 組會畫成 grey2 #0 那張(槽位 12 = FDICON 第 6 組),實測不是
assert SLOT_GROUPS[12] == [6] and SLOT_GROUPS[6] != [6]
A = {"method": "DOSBox-X 記憶體傾印(線性 0xa0000 起 64000 bytes、[0x53a65] 調色盤、單位表、[0x53a61] 單位圖快取 262144 bytes)+ FD2.EXE 反組譯",
     "draw_unit_sprite": {"frame": f"[0x53a61] 表第 +2 × {FPS} + +3 × {DIRS} + 時脈 項;時脈 = [0x53c0b](+4 == 0)或 [0x53c07],{CLK_FROM} 當 {CLK_TO},+0x26 != 0 時 0",
                          "position": f"視窗原點 {list(VIEW_XY)} + 格 × {CELL},上移 {-UNIT_DY} 列({hex(POS_OFF)} − {hex(ORIGIN_OFF)} = {UNIT_DY} × {STRIDE})",
                          "grey": f"+5 & {hex(GREY_BIT)} → 0x4e1a6,值 (v & {GREY_MASK}) + {hex(GREY_BASE)};否則 0x4e22a",
                          "view_cells": [VW, VH]},
     "sprite_cache": {"entries": len(OFFS), "slots": NSLOT, "slot_fdicon_groups": SLOT_GROUPS, "raw_sha256": sha(RAW / "sprtab.bin")},
     "dumps": A_ROWS, "fully_matched_units": FULL,
     "mode1_units_grey2": M1_UNITS,
     "conclusion": "灰階版 0x4e1a6 的模式 1 與彩色版相同:先跳過一格再寫,值 (v & 7) + 0x18;單位 +2 是 [0x53a61] 快取的槽位,不是 FDICON 組號"}

# ================= (B) 第 3 項:指令表第 1、2、5、7 格的入口 =================
LOG3 = RAW / "cells_1257_calllog.txt"
TABLE = {k: struct.unpack_from("<I", _D, dl.lin2file(META, 0x51D01) + 4 * k)[0] + dl.CODE_BASE for k in range(10)}
S129C = json.loads(S129.read_text(encoding="utf-8"))["cmd_table_0_9"]
assert {int(k): int(v, 16) for k, v in S129C["table_0x51d01_0_9"].items()} == TABLE     # 續一百二十九的靜態解析是第二個來源
STUB = {int(k): (v[0], int(v[1], 16)) for k, v in S129C["stub_shape"]["rows"].items() if v}
BODY = {0x2121A: call_target(0x2121E), 0x213AA: call_target(0x213AE)}           # 共用接續點 → 本體
assert BODY == {0x2121A: 0x21227, 0x213AA: 0x213B7}
RET_1541F = 0x1541F + 7                                                          # call [eax*4 + 0x51d01] 是 7 bytes
E_SPELL, E_SCENE, E_MAP, E_CALL = 0x153E7, 0x153F2, 0x1540A, 0x1541F


def parse3(path) -> tuple[str, list[dict]]:
    header, recs = None, []
    for ln in path.read_text(encoding="ascii").split("\n"):
        p = ln.split(" ")
        if p[0] == "H":
            header = ln
        elif p[0] == "E":
            st = next(x for x in p if x.startswith("s="))[2:].split(",")
            recs.append({"seq": int(p[1]), "eip": int(p[2], 16) - DELTA, "ret": int(p[3], 16) - DELTA, "eax": int(p[6], 16),
                         "stack": [int(v, 16) for v in st if v]})
    assert header is not None and "entries=14 " in header and "dump=0 " in header, header
    assert [r["seq"] for r in recs] == list(range(1, len(recs) + 1))
    return header, recs


HEADER3, REC3 = parse3(LOG3)
NEG = (RAW / "units_after_neg.txt").read_text(encoding="utf-8")
UBASE = int(re.search(r"^ubase (0x[0-9a-f]+) count (\d+)$", NEG, re.M).group(1), 16)
UNITS_NEG = {int(m.group(1)): {"mp": int(m.group(2)), "mmp": int(m.group(3)), "spells": json.loads(m.group(4))}
             for m in re.finditer(r"^#\s*(\d+) .* mp=(\d+)/(\d+) w=[0-9a-f]+ spells=(\[[0-9, ]*\])$", NEG, re.M)}
assert len(UNITS_NEG) == int(re.search(r"count (\d+)", NEG).group(1))
SPELL_MP = {s["id"]: s["mp"] for s in json.loads(SPELLS.read_text(encoding="utf-8"))}

casts, cur = [], None
for r in REC3:
    if r["eip"] == E_SPELL:
        cur = {"caster_ptr": r["stack"][1], "records": []}
        casts.append(cur)
    cur["records"].append(r)
B_ROWS = []
for c in casts:
    u = (c["caster_ptr"] - UBASE) // 80
    assert UBASE + 80 * u == c["caster_ptr"]
    eips = [r["eip"] for r in c["records"]]
    row = {"caster": u, "spells_known": UNITS_NEG[u]["spells"], "path": [hex(e) for e in eips]}
    if eips[1] == E_MAP:
        spell = c["records"][2]["eax"]
        assert eips[2] == E_CALL and c["records"][1]["eax"] == 1, row                # [0x53af9] = 1
        stub, kind, body = TABLE[spell], STUB[spell][1], BODY[STUB[spell][1]]
        assert c["records"][3]["ret"] == RET_1541F and STUB[spell][0] == spell, row
        assert eips[3:] == [stub, kind, body], row
        assert c["records"][4]["eax"] == spell, row                                   # 接續點收到的就是跳板 push 的 k
        row.update({"af9": 1, "spell": spell, "cell_entry": hex(stub), "join": hex(kind), "body": hex(body)})
    else:
        assert eips == [E_SPELL, E_SCENE] and c["records"][1]["eax"] == 0, row          # [0x53af9] = 0:只有場景路徑
        row.update({"af9": 0, "mp_spent": UNITS_NEG[u]["mmp"] - UNITS_NEG[u]["mp"]})
    assert len(UNITS_NEG[u]["spells"]) == 1, row
    B_ROWS.append(row)
POS = [r for r in B_ROWS if r["af9"] == 1]
NEG_ROWS = [r for r in B_ROWS if r["af9"] == 0]
assert [r["spell"] for r in POS] == [1, 2, 5, 7, 3, 6] and [r["spells_known"] == [r["spell"]] for r in POS] == [True] * 6
assert [r["caster"] for r in POS] == [r["caster"] for r in NEG_ROWS] == [11, 12, 13, 14, 15, 16]
assert B_ROWS == POS + NEG_ROWS                                                     # 先 [0x53af9] = 1 一輪、再 = 0 一輪
# [0x53af9] = 0 那輪確實施了法:每人扣的 MP = 法術表(docs/data/exe_tables/spell.json)的消耗
assert all(r["mp_spent"] == SPELL_MP[r["spells_known"][0]] for r in NEG_ROWS), NEG_ROWS
TARGETS = {1, 2, 5, 7}
seen_entries = {r["eip"] for r in REC3} & set(TABLE.values())
assert {k for k, a in TABLE.items() if a in seen_entries} == {1, 2, 3, 5, 6, 7}
B = {"method": "DOSBox-X 呼叫紀錄(修補版 dosbox-x,只列 14 個 EIP,途中沒有斷點)+ FD2.EXE 反組譯 + 法術表",
     "raw_sha256": sha(LOG3), "header": HEADER3, "table_0x51d01_cast": {k: hex(TABLE[k]) for k in sorted({r["spell"] for r in POS})},
     "setup": "lc157.py arm:敵 #11 .. #16 各只會一個法術(1、2、5、7、3、6)、MP 999、卸武器、搬到索爾旁;我方 HP 999;[0x53af9] 先設 1、結束回合,再設 0、結束回合",
     "casts": B_ROWS,
     "conclusion": "[0x53af9] = 1 時法術 1、2、5、7 由 0x1541f 進第 1、2、5、7 格的跳板,再到 0x2121a / 0x213aa 與本體;= 0 時同樣施法(扣 MP = 法術表)但只走 0x153f2"}
assert TARGETS <= {r["spell"] for r in POS}

# ================= (C) 第 4 項:索引 255 的 DAC =================
_src145 = (GEN_DIR / "ev_s145.py").read_text(encoding="utf-8")
_defs = [n for n in ast.parse(_src145).body if isinstance(n, ast.FunctionDef) and n.name == "fade6"]
assert len(_defs) == 1
_ns: dict = {"np": np}
exec(compile(ast.Module(_defs, []), "ev_s145.py", "exec"), _ns)
fade6 = _ns["fade6"]
C145 = json.loads(S145.read_text(encoding="utf-8"))["exe_constants"]
DIV = C145["fade_0x2df01"]["div"]
HI = C145["fade_0x2df01"]["hi_exclusive"][0]                  # 0x1fc7b 那一處 push 0xff:索引 < 0xff
RED_TGT = tuple(C145["transition_target_rgb6"])
SITE = 0x1FC7B
assert call_target(SITE) == 0x2DF01
DAC = json.loads((RAW / "dac255_1fc7b.json").read_text(encoding="utf-8"))
assert DAC["site"] == hex(SITE) and int(DAC["regs_at_call"]["EIP"], 16) == SITE + DELTA
assert int(DAC["regs_after"]["EIP"], 16) == SITE + 5 + DELTA                   # 停在 call 之後那一條
T = DAC["t_esi"]
assert int(DAC["regs_at_call"]["ESI"], 16) == T == int(DAC["regs_after"]["ESI"], 16)
before, after = np.array(DAC["dac_before"], np.int64), np.array(DAC["dac_after"], np.int64)
buf = np.frombuffer(bytes(DAC["pal_buf_before_edit"]), np.uint8).reshape(256, 3).astype(np.int64)
assert before.shape == after.shape == buf.shape == (256, 3)
EDIT = tuple(DAC["pal_buf_255_set_to"])
src = buf.copy()
src[255] = EDIT
HI_MODEL = HI                                                                   # 模型的上界(不含)= EXE push 的 0xff
pred = fade6(src, RED_TGT, T, DIV, HI_MODEL)
pred_if_written = fade6(src, RED_TGT, T, DIV, HI + 1)[255]                     # 對照:hi 含 255
# 模型:索引 < hi 照 fade6,其餘 DAC 保留前一個值 —— 256 個索引整組比
model = pred.copy()
model[HI_MODEL:] = before[HI_MODEL:]
assert (after == model).all(), np.argwhere(after != model)[:5]
assert tuple(after[255]) == tuple(before[255]) != tuple(pred_if_written), (after[255], before[255], pred_if_written)
# 不改緩衝也分得出來:緩衝原本的 255 = (63, 63, 63),第 39 步寫了也會變;改成 (1, 2, 3) 是讓差距更大
pred_if_written_unedited = fade6(buf, RED_TGT, T, DIV, HI + 1)[255]
assert tuple(pred_if_written) == (3, 1, 2) and tuple(pred_if_written_unedited) == (63, 61, 61)   # 63 + (v − 63) × 39 / 40 等向 0 截斷
assert tuple(pred_if_written_unedited) != tuple(after[255]), pred_if_written_unedited
assert (before[:HI] == fade6(buf, RED_TGT, T + 1, DIV, HI)[:HI]).all()           # 上一步(t + 1 = 除數)DAC 就是緩衝本身
assert T + 1 == DIV
floor_bad = int((fade6(src, RED_TGT, T, DIV, HI, floor=True)[:HI] != after[:HI]).any(axis=1).sum())
assert floor_bad > 0                                                            # 對照:向下取整對不上
changed = int((before[:HI] != after[:HI]).any(axis=1).sum())
C = {"method": "DOSBox-X 除錯器:斷點停在 0x1fc7b(call 0x2df01)與返回處,VGA DACPAL 讀硬體 DAC、讀 [0x53a65] 緩衝;緩衝索引 255 改成 (1, 2, 3)",
     "raw_sha256": sha(RAW / "dac255_1fc7b.json"), "site": hex(SITE), "t": T, "div": DIV, "hi_exclusive": HI, "target_rgb6": list(RED_TGT),
     "buf_255_edit": list(EDIT), "dac255_before": before[255].tolist(), "dac255_after": after[255].tolist(),
     "dac255_if_written": [int(v) for v in pred_if_written],
     "dac255_if_written_without_edit": [int(v) for v in pred_if_written_unedited], "indices_0_254_equal_fade6": True, "indices_changed_by_step": changed,
     "control_floor_mismatch_indices": floor_bad,
     "why_t_39": "t = 除數(40)那一步 DAC 本來就等於緩衝,改了 255 也分不出寫沒寫;第一次量在那一步,改量第 39 步",
     "conclusion": "0x2df01(0, 0xff, t, …) 實機上不寫 DAC 索引 255,0 .. 254 逐筆等於 fade6(續一百五十的模擬一致)"}

# ================= (D) 第 2 項:相位迴圈 redraw 的內部時間 =================
RUNS2 = {"lc157c": "第一輪擺法(lc130 arm)", "lc157d": "第一輪擺法(lc131 armC 的記憶體寫入沒有落地:讀回的 mem dump 沒產生檔,驅動腳本當成成功)",
         "lc157e": "第二輪擺法(lc130 arm + armC:#5 → (8, 7)、#10 → (6, 9)、索爾 HP 167、MV 30;寫入後停兩次逐欄讀回 12 / 12 相符)"}
# lc157e 的擺法:armC 寫入後停住逐欄讀回(lc157e_armC.out),恢復後再停一次讀回(lc157e_check.out);兩次 12 欄全部 OK
READBACK = {}
for _tag in ("armC", "check"):
    _rb = re.findall(r"^  (OK |BAD) (#\d+ \w+)\s+want ([0-9a-f]+) got (\S+)$", (RAW / f"lc157e_{_tag}.out").read_text(encoding="utf-8"), re.M)
    READBACK[_tag] = {f: [w, g] for ok, f, w, g in _rb}
    assert len(_rb) == len(READBACK[_tag]) == 12 and all(ok == "OK " and w == g for ok, _, w, g in _rb), (_tag, _rb)
assert READBACK["armC"] == READBACK["check"]
assert (READBACK["armC"]["#5 xy"][0], READBACK["armC"]["#10 xy"][0]) == (bytes([8, 7]).hex(), bytes([6, 9]).hex())
assert READBACK["armC"]["#0 HP"][0] == struct.pack("<h", 167).hex() and READBACK["armC"]["#0 MV"][0] == bytes([30]).hex()
CHILD = {0x1297D: "r_1297d", 0x11EEE: "terrain", 0x122DC: "overlay", 0x127A9: "units", 0x1ACF3: "hud", 0x11EB0: "rowcopy"}
E_LAP, E_END, E_REDRAW, E_WAIT, E_TICK, E_ADV, E_PHASE, E_GATE = 0x152A0, 0x152BA, 0x11CAC, 0x17AA9, 0x12117, 0x12132, 0x12169, 0x15055
E_SPRITE, BLITS = 0x127E0, (0x4E22A, 0x4E1A6)


ICOUNT = re.compile(r" i=(?P<i>\d+) n=(?P<n>\d+) t=(?P<t>[0-9.]+)$")


def kv(ln: str) -> dict[str, float]:
    """行尾的 i= n= t=(FD2_CALLLOG_ICOUNT=1 的格式);E / R / A 都必須有。"""
    m = ICOUNT.search(ln.rstrip())
    assert m, ln[:120]
    return {k: float(v) for k, v in m.groupdict().items()}


def parse2(path) -> tuple[str, dict]:
    """E / R / A 依序重建呼叫樹;每個 E 記父節點、入口與離開的 i / t。"""
    header, nodes, stack = None, {}, []
    for ln in path.read_text(encoding="ascii").split("\n"):
        p = ln.split(" ")
        if p[0] == "H":
            header = ln
        elif p[0] == "E":
            st = next(x for x in p if x.startswith("s="))[2:].split(",")
            seq = int(p[1])
            nodes[seq] = {"eip": int(p[2], 16) - DELTA, "eax": int(p[6], 16), "ebx": int(p[7], 16), "arg0": int(st[0], 16),
                          "parent": stack[-1] if stack else None, **{"e" + k: v for k, v in kv(ln).items()}}
            stack.append(seq)
        elif p[0] in ("R", "A") and int(p[1]) in nodes:
            seq = int(p[1])
            assert seq in stack, (path.name, ln)
            while stack.pop() != seq:
                pass
            nodes[seq].update({"r" + k: v for k, v in kv(ln).items()}, kind=p[0])
    assert header is not None and " icount=1 " in header and f"gate={E_GATE + DELTA:08x}" in header, header
    return header, nodes


# ev_s132 的判準(推進 ⇔ tick − 上次推進 > 2),由原始碼抽出那一個函式執行
_src132 = (GEN_DIR / "ev_s132.py").read_text(encoding="utf-8")
_j = [n for n in ast.parse(_src132).body if isinstance(n, ast.FunctionDef) and n.name == "judge"]
assert len(_j) == 1
_ns132: dict = {}
exec(compile(ast.Module(_j, []), "ev_s132.py", "exec"), _ns132)
judge132 = _ns132["judge"]

RUN_A, RUN_B = ([r["phase_read_at_stop"] for r in run["strip"]["rows"]] for run in json.loads(S123.read_text(encoding="utf-8"))["runs"])
D_RUNS: dict[str, dict] = {}
for name in RUNS2:
    path = RAW / f"{name}_redraw_icount.txt"
    header, N = parse2(path)
    order = sorted(N)
    laps = [s for s in order if N[s]["eip"] == E_LAP]
    # 第一筆 E 就是閘門(ai_item_action 入口);0x152a0 / 0x152ba 是迴圈裡的標籤,不是函式,紀錄裡一路疊著、最後才一起 A
    assert len(laps) == 8 and order[0] == 1 and N[1]["eip"] == E_GATE and N[1]["parent"] is None
    pre_adv_ticks = [N[s]["eax"] & 0xFFFF for s in order if s < laps[0] and N[s]["eip"] == E_TICK]
    last_adv = None
    for s in order:
        if s >= laps[0]:
            break
        if N[s]["eip"] == E_TICK:
            tick = N[s]["eax"] & 0xFFFF
        elif N[s]["eip"] == E_ADV:
            last_adv = tick
    rows, loop_rd = [], []
    for k, a in enumerate(laps, 1):
        nxt = laps[k] if k < 8 else next(s for s in order if s > a and N[s]["eip"] == E_END) + 1
        inside = [s for s in order if a < s < nxt]
        end = [s for s in inside if N[s]["eip"] == E_END]
        rd = [s for s in inside if N[s]["eip"] == E_REDRAW]
        wt = [s for s in inside if N[s]["eip"] == E_WAIT]
        assert len(end) == len(rd) == len(wt) == 1, (name, k)
        end, rd, wt = end[0], rd[0], wt[0]
        assert rd < wt < end and N[rd]["kind"] == N[wt]["kind"] == "R"
        sub = [s for s in inside if s < end]
        ticks = [N[s]["eax"] & 0xFFFF for s in sub if N[s]["eip"] == E_TICK]
        kids = {nm: [s for s in sub if N[s]["eip"] == e and N[s]["parent"] == rd] for e, nm in CHILD.items()}
        assert all(len(v) == 1 for v in kids.values()), (name, k, {n: len(v) for n, v in kids.items()})
        unit_layer = kids["units"][0]
        sprites = [s for s in sub if N[s]["eip"] == E_SPRITE and N[s]["parent"] == unit_layer]
        blitted = [N[s]["arg0"] for s in sprites if any(N[b]["eip"] in BLITS and N[b]["parent"] == s for b in sub)]
        loop_rd.append(rd)
        rows.append({"k": N[a]["ebx"], "ticks": ticks, "adv": sum(N[s]["eip"] == E_ADV for s in sub),
                     "drawn": [N[s]["eax"] for s in sub if N[s]["eip"] == E_PHASE],
                     "tick_after": N[end]["eax"] & 0xFFFF, "k_after": N[end]["ebx"],
                     "redraw_ms": N[rd]["rt"] - N[rd]["et"], "redraw_insn": int(N[rd]["ri"] - N[rd]["ei"]),
                     "wait_ms": N[wt]["rt"] - N[wt]["et"], "wait_return_t": N[wt]["rt"],
                     "child_ms": {n: N[v[0]]["rt"] - N[v[0]]["et"] for n, v in kids.items()},
                     "child_insn": {n: int(N[v[0]]["ri"] - N[v[0]]["ei"]) for n, v in kids.items()},
                     "unit_sprite_calls": len(sprites), "units_blitted": blitted})
    # 迴圈外的一般重畫(閘門之後、不在 8 圈裡)
    out_rd = [N[s]["rt"] - N[s]["et"] for s in order if N[s]["eip"] == E_REDRAW and s not in loop_rd and "rt" in N[s]]
    D_RUNS[name] = {"rows": rows, "last_adv_before_loop": last_adv, "pre_loop_tick_reads": len(pre_adv_ticks),
                    "header": header, "raw_sha256": sha(path), "out_of_loop_redraw_ms": out_rd}

# 每圈:跨 tick(ev_s132 的算法:收尾 tick − 1 − 畫地形時的 tick)、推進、畫的階
R_OUT: dict[str, dict] = {}
for name, d in D_RUNS.items():
    rows = d["rows"]
    loop = [{"k": r["k"], "k_after": r["k_after"], "ticks": r["ticks"], "adv": r["adv"], "drawn": r["drawn"]} for r in rows]
    drawn = [r["drawn"][0] for r in rows]
    j = judge132(loop, d["last_adv_before_loop"], drawn)
    assert all(j.values()), (name, j)
    cross = [r["tick_after"] - 1 - r["ticks"][0] for r in rows]
    R_OUT[name] = {"arrangement": RUNS2[name], "raw_sha256": d["raw_sha256"], "header": d["header"], "drawn": drawn,
                   "adv": [r["adv"] for r in rows], "tick_at_draw": [r["ticks"][0] for r in rows],
                   "tick_after": [r["tick_after"] for r in rows], "redraw_tick_crossings": cross,
                   "loop_ticks": rows[-1]["tick_after"] - rows[0]["ticks"][0],
                   "redraw_ms": [round(r["redraw_ms"], 3) for r in rows], "wait_ms": [round(r["wait_ms"], 3) for r in rows],
                   "redraw_game_insn": [r["redraw_insn"] for r in rows],
                   "child_ms_median": {n: round(statistics.median(r["child_ms"][n] for r in rows), 3) for n in CHILD.values()},
                   "child_insn_median": {n: statistics.median(r["child_insn"][n] for r in rows) for n in CHILD.values()},
                   "units_ms": [round(r["child_ms"]["units"], 3) for r in rows],
                   "units_insn": [r["child_insn"]["units"] for r in rows],
                   "rowcopy_insn": sorted({r["child_insn"]["rowcopy"] for r in rows}),
                   "unit_sprite_calls": sorted({r["unit_sprite_calls"] for r in rows}),
                   "units_blitted": sorted({tuple(r["units_blitted"]) for r in rows}),
                   "redraw_ms_median": round(statistics.median(r["redraw_ms"] for r in rows), 3),
                   "redraw_insn_median": statistics.median(r["redraw_insn"] for r in rows),
                   "out_of_loop_redraw_ms": {"count": len(d["out_of_loop_redraw_ms"]),
                                             "min_median_max": [round(f(d["out_of_loop_redraw_ms"]), 3) for f in (min, statistics.median, max)]},
                   "judge_ev_s132": j}
c, dd, e = R_OUT["lc157c"], R_OUT["lc157d"], R_OUT["lc157e"]
assert [r["redraw_tick_crossings"] for r in (c, dd, e)] == [[1, 0, 0, 0, 0, 0, 0, 0], [1, 0, 0, 0, 0, 0, 1, 0],
                                                            [1, 0, 1, 0, 1, 1, 1, 1]]
# 跨 tick 與 wait 長短一致:跨了的圈 wait 都比沒跨的長(redraw 收尾落在下一個邊界之後,要等將近一整個 tick)
for nm, r in R_OUT.items():
    w_cross = [w for w, x in zip(r["wait_ms"], r["redraw_tick_crossings"]) if x]
    w_none = [w for w, x in zip(r["wait_ms"], r["redraw_tick_crossings"]) if not x]
    assert min(w_cross) > max(w_none), (nm, r["wait_ms"], r["redraw_tick_crossings"])
assert [r["loop_ticks"] for r in (c, dd, e)] == [9, 10, 14]
# 單位層:三份都呼叫 draw_unit_sprite 21 次;第一輪只有 #10 貼了圖,第二輪 7 個
assert c["unit_sprite_calls"] == dd["unit_sprite_calls"] == e["unit_sprite_calls"] == [21]
assert c["units_blitted"] == dd["units_blitted"] == [(10,)] and e["units_blitted"] == [(0, 1, 2, 3, 4, 6, 11)]

# 量之前寫下的預測 P1 .. P5
PRED = DRV / "pred157_item2.txt"
_ptext = PRED.read_text(encoding="utf-8")
assert all(re.search(rf"^P{i} ", _ptext, re.M) for i in range(1, 6))
P = {}
P["P1"] = c["drawn"] == RUN_A and e["drawn"] == RUN_B
assert dd["drawn"] == RUN_A[:7] + [RUN_A[7] + 1]                                 # lc157d 第 7 圈跨 tick,第 8 圈多推進一次
# P2:每圈推進 ⇔ 該圈 redraw 跨 tick
P["P2"] = all(r["adv"] == r["redraw_tick_crossings"] for r in (c, dd, e))
p2_mismatch = {nm: [k + 1 for k, (a, x) in enumerate(zip(r["adv"], r["redraw_tick_crossings"])) if a != x] for nm, r in R_OUT.items()}
assert p2_mismatch == {"lc157c": [3, 6], "lc157d": [3, 6, 7, 8], "lc157e": [1, 2, 3, 4, 5, 7]}, p2_mismatch
# P3:第二輪 redraw 中位數 > 第一輪
P["P3"] = e["redraw_ms_median"] > max(c["redraw_ms_median"], dd["redraw_ms_median"])
# P4:差距的一半以上落在同一個子呼叫
share = {}
for nm, r in (("lc157c", c), ("lc157d", dd)):
    diff = {n: e["child_ms_median"][n] - r["child_ms_median"][n] for n in CHILD.values()}
    top = max(diff, key=diff.get)
    share[nm] = {"top_child": top, "child_diff_ms": round(diff[top], 3),
                 "redraw_diff_ms": round(e["redraw_ms_median"] - r["redraw_ms_median"], 3),
                 "insn_diff": {"redraw": e["redraw_insn_median"] - r["redraw_insn_median"],
                               "units": e["child_insn_median"]["units"] - r["child_insn_median"]["units"],
                               "terrain": e["child_insn_median"]["terrain"] - r["child_insn_median"]["terrain"]}}
P["P4"] = all(v["top_child"] == "units" and v["child_diff_ms"] > v["redraw_diff_ms"] / 2 for v in share.values())
# 單位層的範圍不重疊;地形層的範圍重疊(差距不在地形)
assert min(e["units_ms"]) > max(c["units_ms"] + dd["units_ms"])
_terr = {nm: [round(rw["child_ms"]["terrain"], 3) for rw in D_RUNS[nm]["rows"]] for nm in RUNS2}
assert min(_terr["lc157e"]) < max(_terr["lc157c"] + _terr["lc157d"])
# P5:送畫面(0x11eb0)兩輪相同 —— 三份的中位數差距比任何一份自己 8 圈的起伏還小。
# 指令數每圈不同(10718 .. 13360):遊戲選擇子的指令數含途中進來的計時器中斷,所以不拿指令數判
_rc_ms = {nm: [rw["child_ms"]["rowcopy"] for rw in D_RUNS[nm]["rows"]] for nm in RUNS2}
_rc_med = [statistics.median(v) for v in _rc_ms.values()]
P["P5"] = max(_rc_med) - min(_rc_med) < min(max(v) - min(v) for v in _rc_ms.values())
assert len(set(c["rowcopy_insn"] + dd["rowcopy_insn"] + e["rowcopy_insn"])) > 1
assert P == {"P1": True, "P2": False, "P3": True, "P4": True, "P5": True}, P
# 第一輪 redraw 超過名目 tick 卻沒跨:BIOS tick 的實際間隔不是固定 54.925 ms(wait_ticks 連續兩次返回、差 1 tick 的間隔)
TICK_MS = 1000 * 65536 / 1193182
gaps = {}
for nm, d in D_RUNS.items():
    rws = d["rows"]
    gaps[nm] = [round(b["wait_return_t"] - a["wait_return_t"], 3) for a, b in zip(rws, rws[1:]) if b["tick_after"] - a["tick_after"] == 1]
long_nocross = [(nm, k + 1, r["redraw_ms"][k]) for nm, r in R_OUT.items() for k in range(8)
                if r["redraw_ms"][k] > TICK_MS and r["redraw_tick_crossings"][k] == 0]
assert long_nocross and all(max(gaps[nm]) > TICK_MS for nm in RUNS2), (long_nocross, gaps)
assert ("lc157c", 2, 59.015) in long_nocross
D = {"method": "DOSBox-X 呼叫紀錄(修補版 dosbox-x,FD2_CALLLOG_ICOUNT=1:每筆附遊戲選擇子指令數 i、全部指令數 n、PIC_FullIndex 模擬時間 t ms;"
               "FD2_CALLLOG_GATE = ai_item_action 0x15055,之前不寫 E;途中沒有斷點)+ FD2.EXE 反組譯",
     "runs": R_OUT, "lc157e_readback": READBACK, "predictions_file": rel(PRED), "predictions_sha256": sha(PRED), "predictions": P,
     "P2_mismatch_laps": p2_mismatch, "P4_share": share, "terrain_ms": _terr,
     "redraw_over_nominal_tick_without_crossing": long_nocross,
     "consecutive_wait_return_gaps_1tick_ms": gaps,
     "conclusion": "第二輪擺法 redraw 比較久(中位數 56.1 vs 52.6 / 52.5 ms),差距在單位層:第一輪 21 次 draw_unit_sprite 只有 #10 貼圖,"
                   "第二輪 7 個單位貼圖;地形層的範圍重疊、送畫面的指令數相同。推進仍照 ev_s132 的規則(tick − 上次推進 > 2),"
                   "不是「該圈跨 tick 就推進」(P2 不成立)。"}

out = {"date": "2026-10-27", "exe_md5": MD5, "approval": "使用者 2026-10-27 核准這 6 項實機;第 2 項第二輪擺法 lc157e 另經核准重跑",
       "inputs_dir": rel(RAW), "drivers": rel(DRV),
       "item1_grey_mode1": A, "item3_cells_1_2_5_7": B, "item4_dac_index255": C, "item2_redraw_time": D,
       "not_here": {"item5_new_game_return_18": "FAIL:三次都沒讓索爾倒下、沒走到 GAME OVER(沒有可用的紀錄)",
                    "item6_copy_protection_patch_author": "BLOCKED:磁碟上沒有未修改的版本可比,實機判定不了"}}
OUT.write_bytes((json.dumps(out, ensure_ascii=False, indent=1) + "\n").encode("utf-8"))
print("wrote", OUT.name, "| A full", FULL, "| B", [r.get("spell") for r in POS], "| C t", T, "changed", changed, "| D", P)
