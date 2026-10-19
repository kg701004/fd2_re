"""續一百三十五證據:evidence/fdicon_mode1_vga_frames_20261019.json。

續一百三十四「仍留的」:長度大於 1 的模式 1 沒有在畫面上驗到。
(1) 資產:FDICON.B24 全部 818 個模式 1 run 長度都是 1;四模式 RLE 家族的另一份資產 FDSHAP(地形圖塊)只有 5 個長度 2,
    在 tileset 050 / 056 / 058(地圖 25 / 28 / 29),放在地圖上的只有地圖 25 的圖塊 38(7 格)與地圖 29 的圖塊 167(1 格),
    由地形繪製 0x4e016 / 0x4e0a2 畫;兩者的模式 1 與 0x4e22a 一樣是迴圈 `inc edi; stosb`(長度 k 就是這兩個指令重複 k 次)。
(2) 畫面:續一百二十二 ~ 一百二十四的 VGA 幀(320 × 200)上,地圖單位圖示在 (24·cx + 4, 24·cy − 2)(由盜賊 #11 的位置推得、唯一);
    以「先跳過再寫」畫 1455 個非空白 sprite,唯一全中 733 處、其中 75 處帶模式 1;以「先寫再跳過」或「兩格都寫」畫,
    唯一全中都只有 658 處、帶模式 1 的 0 處。比續一百三十四多驗到 sprite 360 ~ 362(另一組圖示)。
全部從 FD2.EXE、FDICON.B24、extracted/raw/FDSHAP、extracted/raw/FDFIELD 與 .wsl_build/lc12{2,3,4}_live/ 的 VGA 幀重算;
任何判準或預測不符就 assert 失敗。
"""
from __future__ import annotations

import hashlib
import json
import struct
import sys

import numpy as np

from _evpaths import GAME, ROOT, out_path, rel, require_inputs  # noqa: E402
require_inputs(__file__)
sys.path.insert(0, str(ROOT / "tools"))
import disasm_le as dl  # noqa: E402

EXE, FDICON = GAME / "FD2.EXE", GAME / "FDICON.B24"
SHAP, FIELD = ROOT / "extracted/raw/FDSHAP", ROOT / "extracted/raw/FDFIELD"
WSL = ROOT / ".wsl_build"
OUT = out_path("fdicon_mode1_vga_frames_20261019.json")
VGA_W, VGA_H, CELL = 320, 200, 24
VIEW_W, VIEW_H = 13, 8
UNIT_DY = -6                                     # 續一百三十四:地圖單位上移 6 列(0x75d8 = 0x8088 − 6 × 456)
MIN_KNOWN = 100                                  # 全中至少要有這麼多已知像素才算
ORDERS = ("skip_then_value", "value_then_skip", "value_both")
M1_LOOP = "c0e902fec12af92af9ac"                 # shr cl, 2;inc cl;sub bh, cl × 2;lodsb

# 靜態:四個繪製函式的模式 1 分支(位元組逐一釘住)
CODE = {
    0x4E25D: M1_LOOP + "47aae2fc",                 # 0x4e22a blit_tile24_rle:inc edi; stosb; loop
    0x4E1E1: M1_LOOP + "22c402c247aae2fc",         # 0x4e1a6 灰階版:and al, ah; add al, dl; inc edi; stosb; loop
    0x4E052: M1_LOOP + "8a44050047aae2fc",         # 0x4e016 地形(換色表):mov al, [ebp + eax]; inc edi; stosb; loop
    0x4E0DE: M1_LOOP + "8a44050047aae2fc",         # 0x4e0a2 地圖格重畫(換色表):同上
}
_D = EXE.read_bytes()
_M = dl.parse_le(_D)
for a, hx in CODE.items():
    got = bytes(dl.object_bytes(_D, _M, a, len(hx) // 2)).hex()
    assert got == hx, (hex(a), got)
# 迴圈本體只有 inc edi; stosb 兩個指令(loop 跳回 inc edi):長度 k 的 run 就是「跳一格、寫一格」重複 k 次
for a, hx in CODE.items():
    body = bytes.fromhex(hx[-8:])
    assert body[:2] == b"\x47\xaa" and body[2] == 0xE2 and body[3] == 0x100 - 4, hex(a)


# ================= 資產:模式 1 長度分布 =================
def parse(blob: bytes) -> tuple[int, list[list[tuple[int, int, int, int]]]]:
    """24 × 24 四模式 RLE 圖組:回傳 (張數, 每張的 run 清單 (模式, 起點, k, 值));模式 1 涵蓋 2k 格。"""
    w, h, n = struct.unpack_from("<HHH", blob, 0)
    assert (w, h) == (CELL, CELL), (w, h)
    off = [struct.unpack_from("<I", blob, 6 + i * 4)[0] for i in range(n)] + [len(blob)]
    out = []
    for s in range(n):
        b = blob[off[s]:off[s + 1]]
        rs = []
        i = pos = 0
        while pos < 576 and i < len(b):
            c = b[i]
            i += 1
            m, k = c >> 6, (c & 63) + 1
            v = -1
            if m in (0, 1):
                v = b[i]
                i += 1
            elif m == 2:
                i += k
            rs.append((m, pos, k, v))
            pos += 2 * k if m == 1 else k
        assert pos == 576, (s, pos)
        out.append(rs)
    return n, out


def m1_dist(runs: list[list[tuple[int, int, int, int]]]) -> dict[int, int]:
    d: dict[int, int] = {}
    for rs in runs:
        for m, _p, k, _v in rs:
            if m == 1:
                d[k] = d.get(k, 0) + 1
    return dict(sorted(d.items()))


_fi = FDICON.read_bytes()
N, RUNS = parse(_fi)
assert N == 1680
fdicon_m1 = m1_dist(RUNS)
assert fdicon_m1 == {1: 818}, fdicon_m1                      # 圖示沒有長度 > 1 的模式 1

shap_files = sorted(SHAP.glob("FDSHAP_*.bin"))
assert len(shap_files) == 67, len(shap_files)
tilesets: dict[str, dict] = {}
shap_sha: dict[str, str] = {}
long_runs = []
for p in shap_files:
    b = p.read_bytes()
    shap_sha[p.name] = hashlib.sha256(b).hexdigest()
    if len(b) < 6 or struct.unpack_from("<HH", b, 0) != (CELL, CELL):
        continue                                             # 地形控制表(1200 B)與空資源
    n, rs = parse(b)
    tilesets[p.name] = {"tiles": n, "mode1": m1_dist(rs)}
    long_runs += [{"tileset": p.name, "tile": s, "cell_xy": [pos % CELL, pos // CELL], "k": k, "value": v}
                  for s, r in enumerate(rs) for m, pos, k, v in r if m == 1 and k > 1]
assert len(tilesets) == 33, len(tilesets)
shap_total: dict[int, int] = {}
for t in tilesets.values():
    for k, c in t["mode1"].items():
        shap_total[k] = shap_total.get(k, 0) + c
assert dict(sorted(shap_total.items())) == {1: 325, 2: 5}, shap_total
assert [(r["tileset"], r["tile"]) for r in long_runs] == [
    ("FDSHAP_050.bin", 38), ("FDSHAP_050.bin", 40), ("FDSHAP_056.bin", 218), ("FDSHAP_058.bin", 167),
    ("FDSHAP_058.bin", 219)], long_runs

# 這幾塊放在地圖哪裡:地圖 m 用 FDSHAP 解包序 2m、FDFIELD 解包序 3m(構成:u16 W, u16 H, 每格 (u16 地形索引, u16 事件))
field_sha: dict[str, str] = {}
for r in long_runs:
    m = int(r["tileset"][7:10]) // 2
    fp = FIELD / f"FDFIELD_{3 * m:03d}.bin"
    fb = fp.read_bytes()
    field_sha[fp.name] = hashlib.sha256(fb).hexdigest()
    w, h = struct.unpack_from("<HH", fb, 0)
    assert len(fb) == 4 + 4 * w * h, (fp.name, len(fb), w, h)          # 構成資源:大小剛好 = 標頭 + 每格 4 bytes
    idx =[struct.unpack_from("<H", fb, 4 + 4 * k)[0] for k in range(w * h)]
    assert max(idx) < tilesets[r["tileset"]]["tiles"], (fp.name, max(idx))
    r["map"] = m
    r["map_cells"] = [[k % w, k // w] for k, t in enumerate(idx) if t == r["tile"]]
placed = {f'{r["map"]}:{r["tile"]}': len(r["map_cells"]) for r in long_runs}
assert placed == {"25:38": 7, "25:40": 0, "28:218": 0, "29:167": 1, "29:219": 0}, placed


# ================= VGA 幀 =================
def render(rs: list[tuple[int, int, int, int]], blob_tile: bytes, order: str) -> np.ndarray:
    """依 run 畫 576 格;-1 = 不寫。模式 2 的字面值從原始資料取。"""
    px = np.full(576, -1, np.int16)
    i = 0
    for m, p, k, v in rs:
        i += 1
        if m == 0:
            px[p:p + k] = v
            i += 1
        elif m == 1:
            i += 1
            for j in range(k):
                if order == "skip_then_value":
                    px[p + 2 * j + 1] = v
                elif order == "value_then_skip":
                    px[p + 2 * j] = v
                else:
                    px[p + 2 * j] = px[p + 2 * j + 1] = v
        elif m == 2:
            px[p:p + k] = list(blob_tile[i:i + k])
            i += k
    return px


_off = [struct.unpack_from("<I", _fi, 6 + i * 4)[0] for i in range(N)] + [len(_fi)]
SPR = {o: np.stack([render(RUNS[s], _fi[_off[s]:_off[s + 1]], o) for s in range(N)]) for o in ORDERS}
KNOWN = {o: SPR[o] >= 0 for o in ORDERS}
HAS_M1 = np.array([any(r[0] == 1 for r in RUNS[s]) for s in range(N)])
NONBLANK = KNOWN["skip_then_value"].any(axis=1)
assert int(NONBLANK.sum()) == 1455 and int(HAS_M1.sum()) == 450
# 沒有模式 1 的 sprite 三種畫法相同:對手假說只需重算帶模式 1 的 450 張
assert all((SPR[o][~HAS_M1] == SPR["skip_then_value"][~HAS_M1]).all() for o in ORDERS)

frame_files = sorted(p for d in ("lc122_live", "lc123_live", "lc124_live") for p in (WSL / d).glob("*.bin")
                     if p.stat().st_size == VGA_W * VGA_H)
assert len(frame_files) == 185, len(frame_files)
frames: dict[str, np.ndarray] = {}
frame_sha: dict[str, str] = {}
for p in frame_files:
    b = p.read_bytes()
    h = hashlib.sha256(b).hexdigest()
    if h in frame_sha.values():
        continue
    k = p.relative_to(WSL).as_posix()
    frame_sha[k] = h
    frames[k] = np.frombuffer(b, np.uint8).reshape(VGA_H, VGA_W).astype(np.int16)
assert len(frames) == 154, len(frames)


def match(patch: np.ndarray, order: str) -> list[int]:
    """這一塊 24 × 24 在某個畫法下全中的非空白 sprite。"""
    bad = ((SPR[order] != patch[None]) & KNOWN[order]).sum(axis=1)
    return [int(s) for s in np.where((bad == 0) & NONBLANK)[0]]


# 位置:lc122 ai79 幀的盜賊 #11(地圖格與捲動來自同一次記錄),在 ±4 / ±12 範圍內只有一個偏移全中
_ai79 = json.loads((WSL / "lc122_live" / "ai79.json").read_text(encoding="utf-8"))["entry"]
assert (_ai79["unit"], _ai79["unit_xy"], _ai79["scroll"]) == (11, [19, 14], [8, 8]), _ai79
_f0 = frames["lc122_live/ai79_entry.bin"]
_cx, _cy = _ai79["unit_xy"][0] - _ai79["scroll"][0], _ai79["unit_xy"][1] - _ai79["scroll"][1]
probe = []
for oy in range(-12, 13):
    for ox in range(-4, 5):
        x, y = CELL * _cx + ox, CELL * _cy + oy
        hit = match(_f0[y:y + CELL, x:x + CELL].reshape(576), "skip_then_value")
        if len(hit) == 1 and KNOWN["skip_then_value"][hit[0]].sum() >= MIN_KNOWN:
            probe.append((ox, oy, hit[0]))
assert probe == [(4, -2, 1163)], probe
OX, OY = probe[0][0], probe[0][1]
VIEW_X0, VIEW_Y0 = OX, OY - UNIT_DY                 # 視窗原點 (4, 4)
assert (VIEW_X0, VIEW_Y0) == (4, 4)

# 地形佐證:同一幀以 (4, 4) 為原點,第 1 章戰場的格子與 FDSHAP_002 的全不透明圖塊全中(換色表當恆等);錯一格就幾乎對不上
_t2n, _t2r = parse((SHAP / "FDSHAP_002.bin").read_bytes())
_b2 = (SHAP / "FDSHAP_002.bin").read_bytes()
_o2 = [struct.unpack_from("<I", _b2, 6 + i * 4)[0] for i in range(_t2n)] + [len(_b2)]
T2 = np.stack([render(_t2r[s], _b2[_o2[s]:_o2[s + 1]], "skip_then_value") for s in range(_t2n)])
T2 = T2[(T2 >= 0).all(axis=1)]


def terrain_hits(x0: int, y0: int) -> int:
    n = 0
    for cy in range(VIEW_H):
        for cx in range(VIEW_W):
            x, y = x0 + CELL * cx, y0 + CELL * cy
            if x + CELL > VGA_W or y + CELL > VGA_H:
                continue
            n += bool((T2 == _f0[y:y + CELL, x:x + CELL].reshape(576)[None]).all(axis=1).any())
    return n


terrain = {f"{dx},{dy}": terrain_hits(VIEW_X0 + dx, VIEW_Y0 + dy) for dx, dy in ((0, 0), (1, 0), (0, 1), (-1, 0), (0, -1))}
assert terrain["0,0"] == 94 and max(v for k, v in terrain.items() if k != "0,0") <= 10, terrain
assert tilesets["FDSHAP_002.bin"]["mode1"] == {}                # 第 1 章戰場的圖塊組沒有模式 1
assert terrain == {"0,0": 94, "1,0": 0, "0,1": 0, "-1,0": 0, "0,-1": 0}, terrain

# 每一幀、每一格:三種畫法各自的唯一全中
hits: dict[str, list] = {o: [] for o in ORDERS}
for name, f in frames.items():
    for cy in range(VIEW_H + 1):
        for cx in range(VIEW_W):
            x, y = OX + CELL * cx, OY + CELL * cy
            if y < 0 or y + CELL > VGA_H or x + CELL > VGA_W:
                continue
            patch = f[y:y + CELL, x:x + CELL].reshape(576)
            base = ((SPR["skip_then_value"] != patch[None]) & KNOWN["skip_then_value"]).sum(axis=1)
            for o in ORDERS:
                bad = base.copy()
                if o != "skip_then_value":
                    bad[HAS_M1] = ((SPR[o][HAS_M1] != patch[None]) & KNOWN[o][HAS_M1]).sum(axis=1)
                ok = np.where((bad == 0) & NONBLANK)[0]
                if len(ok) == 1 and KNOWN[o][ok[0]].sum() >= MIN_KNOWN:
                    hits[o].append((name, cx, cy, int(ok[0])))
summary = {o: {"unique_hits": len(h), "with_mode1": sum(bool(HAS_M1[s]) for *_x, s in h),
               "sprites": len({s for *_x, s in h})} for o, h in hits.items()}
assert summary == {
    "skip_then_value": {"unique_hits": 733, "with_mode1": 75, "sprites": 24},
    "value_then_skip": {"unique_hits": 658, "with_mode1": 0, "sprites": 19},
    "value_both": {"unique_hits": 658, "with_mode1": 0, "sprites": 19}}, summary
# 判準:對手假說找到的全中是「先跳過再寫」全中的子集(差的正好是帶模式 1 的那 75 處)
skip_set = set(hits["skip_then_value"])
assert all(set(hits[o]) <= skip_set for o in ORDERS[1:])
assert all(len(skip_set - set(hits[o])) == 75 for o in ORDERS[1:])

# 模式 1 的逐格檢查:寫入格 = 值;跳過格 ≠ 值(否則那一處沒有鑑別力)
m1_runs: dict[str, dict] = {}
for name, cx, cy, s in hits["skip_then_value"]:
    if not HAS_M1[s]:
        continue
    patch = frames[name][OY + CELL * cy:OY + CELL * cy + CELL, OX + CELL * cx:OX + CELL * cx + CELL].reshape(576)
    for m, p, k, v in RUNS[s]:
        if m != 1:
            continue
        assert k == 1
        wrote, skipped = int(patch[p + 1]), int(patch[p])
        assert wrote == v, (name, s, p)
        e = m1_runs.setdefault(f"{s}:{p % 24},{p // 24}", {"value": v, "places": 0, "discriminating": 0, "skipped_values": []})
        e["places"] += 1
        e["discriminating"] += skipped != v
        if skipped not in e["skipped_values"]:
            e["skipped_values"].append(skipped)
assert sorted(m1_runs) == ["1609:20,22", "1610:20,21", "360:0,19", "360:21,18", "361:0,20", "362:0,18"], sorted(m1_runs)
assert all(e["discriminating"] == e["places"] > 0 for e in m1_runs.values()), m1_runs
assert {k: e["places"] for k, e in m1_runs.items()} == {
    "1609:20,22": 13, "1610:20,21": 12, "360:0,19": 3, "360:21,18": 3, "361:0,20": 35, "362:0,18": 12}, m1_runs
assert sum(e["places"] for e in m1_runs.values()) == 78 and {e["value"] for e in m1_runs.values()} == {254}
for e in m1_runs.values():
    e["skipped_values"].sort()

# 灰階版 0x4e1a6:像素 = (v & 7) + 0x18;全中只有一處,而且那張 sprite 沒有模式 1
GREY = np.where(SPR["skip_then_value"] >= 0, (SPR["skip_then_value"] & 7) + 0x18, -1)
grey_hits = []
for name, f in frames.items():
    for cy in range(VIEW_H + 1):
        for cx in range(VIEW_W):
            x, y = OX + CELL * cx, OY + CELL * cy
            if y < 0 or y + CELL > VGA_H or x + CELL > VGA_W:
                continue
            patch = f[y:y + CELL, x:x + CELL].reshape(576)
            ok = np.where((((GREY != patch[None]) & KNOWN["skip_then_value"]).sum(axis=1) == 0) & NONBLANK)[0]
            if len(ok) and KNOWN["skip_then_value"][ok[0]].sum() >= MIN_KNOWN:
                grey_hits.append([name, cx, cy, [int(s) for s in ok]])
assert grey_hits == [["lc122_live/s11_ref.bin", 11, 1, [386]]], grey_hits
assert not HAS_M1[386]

ev = {
    "_meta": {"topic": "續一百三十五:四模式 RLE 長度 > 1 的模式 1 在資產裡的分布,與 VGA 幀上模式 1 次序的再驗證",
              "exe": rel(EXE), "exe_md5": hashlib.md5(_D).hexdigest(),
              "assets": {rel(FDICON): hashlib.sha256(_fi).hexdigest()},
              "fdshap_sha256": shap_sha, "fdfield_sha256": field_sha,
              "vga_frames_sha256": frame_sha,
              "generator": "evidence/generators/ev_s135.py(變異測試 mut_s135.py)",
              "harness": "VGA 幀是續一百二十二 ~ 一百二十四的 DOSBox-X 傾印(線性 0xa0000 起 64000 bytes,185 個檔、154 個不同);本輪沒有開新的 instance"},
    "static_code": {hex(a): hx for a, hx in CODE.items()},
    "fdicon_mode1_lengths": fdicon_m1,
    "fdshap_mode1_lengths_total": dict(sorted(shap_total.items())),
    "fdshap_tilesets": tilesets,
    "fdshap_long_mode1_runs": long_runs,
    "vga_unit_offset_probe": {"unit": _ai79["unit"], "cell_in_view": [_cx, _cy], "hits": probe, "view_origin": [VIEW_X0, VIEW_Y0]},
    "terrain_fdshap_002_hits_by_shift": terrain,
    "vga_unique_hits": summary,
    "mode1_runs_on_screen": m1_runs,
    "grey_hits": grey_hits,
    "status": {
        "long_mode1_assets": "CODE + 資產 CONFIRMED:FDICON 的 818 個模式 1 run 長度全是 1,所以地圖單位、HUD 圖示(0x4e22a / 0x4e1a6)"
                             "不會遇到長度 > 1 的模式 1。整個家族的資產裡只有 FDSHAP 5 個長度 2(tileset 050 / 056 / 058),"
                             "放在地圖上的是地圖 25 的圖塊 38(7 格)與地圖 29 的圖塊 167(1 格),由 0x4e016 / 0x4e0a2 畫。",
        "long_mode1_order": "CODE CONFIRMED:四個函式的模式 1 迴圈本體都只有 inc edi; stosb(loop 跳回 inc edi),長度 k 就是同一對指令"
                            "重複 k 次;長度 1 的次序已在畫面上驗到,長度 2 的 5 個 run 沒有在畫面上出現(要地圖 25 / 29 的實機畫面)。",
        "mode1_order_vga": "LOG CONFIRMED:VGA 幀上以先跳過再寫畫,唯一全中 733 處、帶模式 1 的 75 處(sprite 360 ~ 362、1609、1610,"
                           "6 個 run、78 處,跳過格全部 ≠ 值);先寫再跳過、兩格都寫都只有 658 處、帶模式 1 的 0 處,且是前者的子集。",
        "vga_geometry": "INFERRED → 由像素定:地圖單位圖示在 VGA (24·cx + 4, 24·cy − 2),視窗原點 (4, 4);"
                        "地形以 (4, 4) 為原點有 94 / 104 格與 FDSHAP_002 全中,錯一格 0 格。",
        "grey": "灰階版 0x4e1a6 在 VGA 幀上只有一處全中(s11_ref,索爾的格子,sprite 386),該張沒有模式 1:灰階版的模式 1 仍只有靜態證據。",
        "terrain_mode1": "第 1 章戰場的圖塊組 FDSHAP_002 沒有模式 1;地形繪製 0x4e016 / 0x4e0a2 的模式 1 在畫面上沒有驗到。",
    },
}


def write() -> None:
    OUT.write_text(json.dumps(ev, ensure_ascii=False, indent=1) + "\n", encoding="utf-8", newline="\n")
    print("ok", OUT.name, len(OUT.read_bytes()))


if __name__ == "__main__":
    write()
