#!/usr/bin/env python3
"""炎龍騎士團2 — 把一張戰場輸出成 Go/Ebiten 引擎用的資產(tileset 網格 PNG + 地圖 JSON)。

輸出:
  <out>/tileset.png  該 tileset 全部 24×24 圖塊排成網格(cols 欄)
  <out>/map.json     {"w","h","tileW","tileH","cols","tiles":[地形索引...],"cost":[移動成本...],"native_composition_event_bytes":[FDFIELD event low bytes...],"native_tile_blit_modes":[FDFIELD event high bytes...],"native_terrain_control":[raw FDSHAP control bytes...]}

引擎(remake/cmd/fd2)讀這兩個檔即可渲染地圖。資產屬遊戲著作權,只在本機,不入庫。

"cost" 陣列(第 8 輪新增,worklist「地形屬性接線」):per-tile 移動成本,由地形控制表的
「移動資訊」代碼(見 tools/dump_terrain_table.py、docs/knowledge-base/01-… §5)換算而來:
    0 正常          -> 1
    1 不可移動      -> BLOCKED_COST(99,遠大於任何 MV,Reachable/Path 天然擋停不用特判)
    2 森林·僅騎兵減速 -> 1(remake 尚無騎兵/步行/飛行兵種分類,見下方限制說明,先不罰步行)
    3 森林·全體減速   -> 1(同上;AP/DP 加成本身也還沒接,只接「可否通行」)
    4 沼澤·全體減速   -> 2(references/text/notes.md 玩家攻略「步行-2」直接對應)
    5 不可移動      -> BLOCKED_COST
    其他未知代碼     -> 1(保守,不無故擋路)
換算依據見 tools/dump_terrain_table.py 檔頭。**限制**:上表只用「步行」單位的移動力扣減,
notes.md 另有騎兵/飛行的差異扣減(如森林騎兵-2),remake Unit 尚無兵種欄位,之後要接的話
需在 battle.Unit 加 MoveType 並讓 MoveCost 依單位種類查不同係數,此處先留唯一步行成本。
若地圖 tile index 超出地形表格數(極少數 tileset 地形表格數 < tile count,如 map24),
cost 保守回退 1(不擋路,寧可錯放不錯擋)。

用法:
    python3 export_engine_assets.py <FDFIELD構成.bin> <FDSHAP_tileset.bin> <palette.bin> <out目錄> [cols] [FDSHAP_terrain.bin]
"""
import sys
import os
import json
import struct
from PIL import Image

sys.path.insert(0, os.path.dirname(__file__))
from render_map import decode_tileset, load_palette

BLOCKED_COST = 99

MOVE_CODE_TO_WALK_COST = {
    0: 1,
    1: BLOCKED_COST,
    2: 1,
    3: 1,
    4: 2,
    5: BLOCKED_COST,
}


def load_terrain_records(terrainp):
    """讀地形控制表(每格 4B)，回傳 (byte0 flags, 步行成本)。"""
    d = open(terrainp, "rb").read()
    n = len(d) // 4
    flags = [d[i * 4] for i in range(n)]
    costs = [MOVE_CODE_TO_WALK_COST.get(d[i * 4 + 1], 1) for i in range(n)]
    return flags, costs, d


def selftest():
    """`MOVE_CODE_TO_WALK_COST` 與 `docs/data/exe_tables/terrain.json` 的
    `move_code_meaning` 是**兩份獨立維護的資料**,講的是同一件事。它們一旦不同步,
    不會報錯,只會讓地圖的可通行判定悄悄變成另一套規則。

    另一個風險是 `.get(code, 1)`:沒收錄的 move code 會被**靜默當成可通行**。
    所以第 (3) 題把真實地形控制表裡實際出現的 code 全掃一遍,要求它們都在表內。
    """
    import collections
    import json
    if hasattr(sys.stdout, "reconfigure"):
        sys.stdout.reconfigure(encoding="utf-8")
        sys.stderr.reconfigure(encoding="utf-8")
    fails = []
    root = os.path.dirname(os.path.dirname(os.path.abspath(__file__)))
    tj = os.path.join(root, "docs", "data", "exe_tables", "terrain.json")

    print("(1) 跨資料對照:兩邊涵蓋的 move code 必須完全相同")
    if os.path.isfile(tj):
        meaning = json.load(open(tj, encoding="utf-8"))["move_code_meaning"]
        theirs = {int(k) for k in meaning}
        mine = set(MOVE_CODE_TO_WALK_COST)
        ok1 = mine == theirs
        print(f"    {'PASS' if ok1 else 'FAIL'}: 對照表 {sorted(mine)} vs "
              f"terrain.json {sorted(theirs)}")
        if not ok1:
            fails.append(f"code 集合不同:{sorted(mine ^ theirs)}")

        print("\n(2) 語意一致:被標為「不可移動」的 code 必須對應 BLOCKED_COST,反之亦然")
        blocked_doc = {int(k) for k, v in meaning.items() if "不可移動" in v}
        blocked_code = {k for k, v in MOVE_CODE_TO_WALK_COST.items() if v == BLOCKED_COST}
        ok2 = blocked_doc == blocked_code
        print(f"    {'PASS' if ok2 else 'FAIL'}: terrain.json 標不可移動 {sorted(blocked_doc)}"
              f" vs 對照表 BLOCKED {sorted(blocked_code)}")
        if not ok2:
            fails.append(f"不可移動的 code 不一致:{sorted(blocked_doc ^ blocked_code)}")
    else:
        print("    SKIP: 找不到 terrain.json")

    print("\n(3) 真實地形控制表用到的 code 必須全部在表內"
          "(否則 .get(code, 1) 會靜默當成可通行)")
    d = os.path.join(root, "extracted", "raw", "FDSHAP")
    codes = collections.Counter()
    if os.path.isdir(d):
        for fn in sorted(os.listdir(d)):
            b = open(os.path.join(d, fn), "rb").read()
            if len(b) != 1200:          # 1200B = 該 tileset 的地形控制表(300×4)
                continue
            for i in range(len(b) // 4):
                codes[b[i * 4 + 1]] += 1
    unknown = {k: v for k, v in codes.items() if k not in MOVE_CODE_TO_WALK_COST}
    ok3 = bool(codes) and not unknown
    print(f"    {'PASS' if ok3 else 'FAIL'}: 實際出現 {dict(sorted(codes.items()))},"
          f"未收錄 {unknown or '無'}")
    if not codes:
        fails.append("掃不到任何地形控制表 —— 這題是空的,不算通過")
    elif unknown:
        fails.append(f"未收錄的 move code 會被靜默當成可通行:{unknown}")

    print("\n(4) load_terrain_records:回傳長度必須等於 len(d)//4,且 flags 取 byte0")
    import tempfile
    with tempfile.TemporaryDirectory() as td:
        p = os.path.join(td, "t.bin")
        # 3 筆:flags 0xAA/0xBB/0xCC,move code 0/1/4
        open(p, "wb").write(bytes([0xAA, 0, 0, 0, 0xBB, 1, 0, 0, 0xCC, 4, 0, 0]))
        flags, costs, raw = load_terrain_records(p)
        ok4 = (flags == [0xAA, 0xBB, 0xCC]
               and costs == [1, BLOCKED_COST, 2] and len(raw) == 12)
        print(f"    {'PASS' if ok4 else 'FAIL'}: flags {flags}、costs {costs}")
        if not ok4:
            fails.append(f"load_terrain_records 手算不符:{flags} / {costs}")

    print("\n(5) 非恆真控制:不同 move code 必須真的算出不同成本")
    ok5 = len({MOVE_CODE_TO_WALK_COST[c] for c in (0, 1, 4)}) == 3
    print(f"    {'PASS' if ok5 else 'FAIL'}: code 0/1/4 -> "
          f"{[MOVE_CODE_TO_WALK_COST[c] for c in (0, 1, 4)]}")
    if not ok5:
        fails.append("不同 move code 算出相同成本 —— 對照表沒有鑑別力")

    if fails:
        print("\nSELFTEST FAILED:")
        for f in fails:
            print("  -", f)
        return 1
    print("\n--selftest passed(跨資料 code 集合 + 不可移動語意 + 真實資料涵蓋 + "
          "手算 + 非恆真控制)。")
    return 0


def main(argv):
    if len(argv) == 2 and argv[1] == "--selftest":
        return selftest()
    if len(argv) < 5:
        print(__doc__); return 1
    fieldp, shapp, palp, out = argv[1], argv[2], argv[3], argv[4]
    cols = int(argv[5]) if len(argv) > 5 else 16
    terrainp = argv[6] if len(argv) > 6 else None
    os.makedirs(out, exist_ok=True)
    pal = load_palette(palp)
    tw, th, tiles, masks = decode_tileset(shapp, with_masks=True)
    rows = (len(tiles) + cols - 1) // cols
    sheet = Image.new("RGBA", (cols * tw, rows * th), (0, 0, 0, 0))
    for i, (px, mask) in enumerate(zip(tiles, masks)):
        tile = Image.frombytes("P", (tw, th), px)
        tile.putpalette(pal)
        tile = tile.convert("RGBA")
        tile.putalpha(Image.frombytes("L", (tw, th), mask))
        sheet.alpha_composite(tile, ((i % cols) * tw, (i // cols) * th))
    sheet.save(os.path.join(out, "tileset.png"))

    d = open(fieldp, "rb").read()
    w, h = struct.unpack_from("<HH", d, 0)
    tilesidx = [struct.unpack_from("<H", d, 4 + i * 4)[0] for i in range(w * h)]
    event_words = [struct.unpack_from("<H", d, 6 + i * 4)[0] for i in range(w * h)]
    meta = {"w": w, "h": h, "tileW": tw, "tileH": th, "cols": cols, "tiles": tilesidx}
    # 0x4e040 addresses each FDFIELD composition entry at +7: its [ebx-1]
    # flag is therefore entry+2, the low byte of this event word.  Preserve it
    # separately; it is not terrain-control byte0 or remake movement cost.
    meta["native_composition_event_bytes"] = [word & 0xFF for word in event_words]
    # Native terrain renderer 0x11eee uses composition entry byte+3 (the
    # high byte of this event word) to choose raw 0x4deda versus LUT-aware
    # 0x4dcc6. Preserve it; alpha alone cannot represent the latter's mode-3
    # "remap existing destination" operation.
    meta["native_tile_blit_modes"] = [(word >> 8) & 0xFF for word in event_words]
    if terrainp:
        terrain_flags, costs, terrain_raw = load_terrain_records(terrainp)
        # Keep the original four-byte records for the strict 0x11eee renderer
        # adapter. "cost" is only a normalized movement approximation.
        meta["native_terrain_control"] = list(terrain_raw)
        oob = 0
        cost_arr = []
        treasure_slots = []
        treasure_hidden = []
        native_field_event_slots = []
        for ti, event_word in zip(tilesidx, event_words):
            if 0 <= ti < len(costs):
                cost_arr.append(costs[ti])
                flags = terrain_flags[ti]
                if flags & 0x60:  # 0x20=普通寶箱、0x40=隱藏物品
                    treasure_slots.append(event_word & 0x1F)
                    treasure_hidden.append(bool(flags & 0x40))
                    native_field_event_slots.append(-1)
                else:
                    treasure_slots.append(-1)
                    treasure_hidden.append(False)
                    raw_slot = event_word & 0x1F
                    native_field_event_slots.append(raw_slot - 1 if raw_slot else -1)
            else:
                cost_arr.append(1)
                treasure_slots.append(-1)
                treasure_hidden.append(False)
                native_field_event_slots.append(-1)
                oob += 1
        meta["cost"] = cost_arr
        # 與 tiles/cost 同為 row-major 陣列。slot0 合法，-1 才表示非寶箱格。
        meta["treasure_slots"] = treasure_slots
        meta["treasure_hidden"] = treasure_hidden
        # 0x13a44 只在地形 control byte 不含 0x60 時，把 low5 視為
        # 1-based 格子事件 slot；-1 明確表示該格不進入 native event table。
        meta["native_field_event_slots"] = native_field_event_slots
        if oob:
            print(f"警告:{oob} 格 tile index 超出地形表範圍({len(costs)} 格),已回退 cost=1")
    json.dump(meta, open(os.path.join(out, "map.json"), "w"), separators=(",", ":"))
    tail = " + cost[]" if terrainp else "(無地形表,未加 cost)"
    print(f"tileset.png ({cols}×{rows} 圖塊) + map.json ({w}×{h}){tail} -> {out}")
    return 0


if __name__ == "__main__":
    sys.exit(main(sys.argv))
