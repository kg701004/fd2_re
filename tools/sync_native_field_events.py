#!/usr/bin/env python3
"""把已證實的 FDFIELD 格子事件資料同步到可編輯 map.json。

只新增／更新：
* assets 根目錄 native_turn_event_controls.json：每張地圖控制段全部 16 筆
  原始 (turn, event_id, raw_camp)，包含 turn=0xff 的休眠列；它們不會被
  解讀成第 255 回合事件
* native_field_event_slots：每格 -1 或 0..15
* native_field_events：控制段 16 筆 (event_id, selector)

既有地圖、成本、寶箱、手動修正與單位資料均不改動。

> **2026-09-03 全工具驗證:本工具目前無作用對象。** 它寫入的 `<assets>/map*/map.json`
> 與 `<assets>/native_turn_event_controls.json` 都是 remake 端資產,而 `remake/` 已於
> 2026-09-02 依使用者指示整個移除。`assets` 是命令列參數(不是寫死路徑),所以工具
> 本身還能對任意目錄跑,只是沒有東西在等它的產出。
> EXE/FDFIELD 的身分驗證邏輯本身有效,已同步支援新舊兩版。
"""

import argparse
import glob
import hashlib
import json
import os
import struct

FDFIELD_SOURCE = {
    "file": "FDFIELD.DAT",
    "size": 243169,
    "md5": "ecdb0436d26adfe5d107f2713fa7e9a2",
    "sha256": "b0cf75d94f58603f091c7462c0494f0e83bd6edfb04c1acbf83ed4d938c7a513",
}
# 2026-09-03:改成同時支援兩個版本(與 extract_native_field_event_rules.py 一致)。
# 本工具只用 EXE 做身分驗證與讀取 round seed,不引用會隨版本移動的 handler 位址,
# 所以不需要 handler_delta。
FD2_EDITIONS = {
    "b97caf2239a27a896069d03549d96e1e": {
        "label": "舊版(357074 B,已遺失)", "size": 357074,
        "sha256": "222b7d067ad4450eb9c5f6e6bce1797d54bb050417ba39ced6067f8039f28c4f"},
    "33464c81e6a364fd0660141139aa8e6e": {
        "label": "新版(1998 重打包版,509158 B)", "size": 509158,
        "sha256": "8f4fdf4a86826b9e6a45a9464d30f313c2506febc67162d4a349094d566cb96b"},
}


def resource_index(path):
    return int(os.path.basename(path).split("_")[1].split(".")[0])


def tile_in_terrain(tile, terrain_len):
    """`tile` 這個 terrain 索引(每筆 4 bytes)是否落在 `terrain_len` bytes 範圍內。

    2026-09-11 從 `expected()` 的行內判準抽出來:原本的邊界(`tile * 4 >= terrain_len`)
    只被既有 selftest 用全 0 的合成 `tiles` 陣列間接測到,`tile` 恆為 0,乘 4 或乘 5
    結果都是 0,突變測不出差異。抽成函式後才能直接餵邊界值進來,不必先算出一份
    真實地圖裡剛好卡在門檻上的 tile 索引。
    """
    return not (tile < 0 or tile * 4 >= terrain_len)


def terrain_len_aligned(terrain_len: int) -> bool:
    """terrain 表是否由整數筆 4-byte 記錄組成。

    2026-09-11 從 `expected()` 的行內判準(`len(terrain) % 4`)抽出來:真實 terrain
    長度剛好同時是 4 與 5 的倍數,突變成 `% 5` 時真實資料測不出差異,只能直接餵值。
    """
    return terrain_len % 4 == 0


def source_paths(fields: list, shapes: list, map_index: int) -> tuple:
    """第 map_index 張圖的(構成, 控制, 地形)來源路徑。

    FDFIELD 每張圖 3 個資源、FDSHAP 每張 2 個(第 2 個是地形)。2026-09-11 抽出來:
    selftest 一直只用 map0,`map_index * 3` 與 `* 4`、`* 2 + 1` 與 `* 3 + 1` 對 0 算出
    同一個檔,選錯檔完全看不出來。
    """
    return fields[map_index * 3], fields[map_index * 3 + 1], shapes[map_index * 2 + 1]


def field_event_slot(terrain: bytes, tile: int, event_word: int) -> int:
    """單一格的場上事件 slot(-1 = 無)。

    事件字低 5 位是 1-based slot;帶寶物旗標(0x60)的格子歸 sync_native_treasures,
    不算場上事件。2026-09-11 從迴圈裡抽出:selftest 的 tiles 全是 0,遮罩、`- 1`、
    stride 都沒被任何案例打到,只能用合成地形直接測。
    """
    if not tile_in_terrain(tile, len(terrain)):
        return -1
    raw_slot = event_word & 0x1F
    flags = terrain[tile * 4]
    return raw_slot - 1 if raw_slot and flags & 0x60 == 0 else -1


def expected(raw, map_index, map_data):
    fields = sorted(
        glob.glob(os.path.join(raw, "FDFIELD", "*.bin")),
        key=resource_index,
    )
    shapes = sorted(
        glob.glob(os.path.join(raw, "FDSHAP", "*.bin")),
        key=resource_index,
    )
    comp_path, control_path, terrain_path = source_paths(fields, shapes, map_index)
    comp = open(comp_path, "rb").read()
    control = open(control_path, "rb").read()
    terrain = open(terrain_path, "rb").read()
    w, h = struct.unpack_from("<HH", comp, 0)
    if map_data.get("w") != w or map_data.get("h") != h:
        raise ValueError(f"map{map_index}: dimensions differ")
    tiles = map_data.get("tiles")
    if len(tiles or []) != w * h or not terrain_len_aligned(len(terrain or [])):
        raise ValueError(f"map{map_index}: raw terrain provenance invalid")

    # 事件字依格子(cell)索引,構成檔每格 4 bytes,對合法檔永遠在範圍內;地形範圍的
    # 判定只在 field_event_slot 做一次(原本在這裡重複檢查,那份是冗餘的)。
    slots = [field_event_slot(terrain, tile, struct.unpack_from("<H", comp, 6 + cell * 4)[0])
             for cell, tile in enumerate(tiles)]

    turn_controls = [
        {
            "turn": control[3 + slot * 3],
            "event_id": control[3 + slot * 3 + 1],
            "raw_camp": control[3 + slot * 3 + 2],
        }
        for slot in range(16)
    ]
    offset = 3 + 16 * 3
    events = [
        {
            "event_id": control[offset + slot * 2],
            "selector": control[offset + slot * 2 + 1],
        }
        for slot in range(16)
    ]
    return (
        turn_controls,
        slots,
        events,
        os.path.basename(control_path),
        hashlib.sha256(control).hexdigest(),
    )


def selftest():
    """與 `sync_native_treasures` 同形狀,但**不是同一套斷言**。

    這支回傳 5 個東西(turn_controls / slots / events / 來源檔名 / control 的
    sha256),而且控制段固定 16 筆(含 turn=0xff 的休眠列)——那是這支特有的不變量,
    直接照抄另一支的檢查會變成沒有內容的形式主義。

    寫入側(remake/assets)已於 2026-09-02 刪除,不在檢查範圍;抽取側是純函式,
    仍是有價值的原版知識。
    """
    import sys as _sys
    if hasattr(_sys.stdout, "reconfigure"):
        _sys.stdout.reconfigure(encoding="utf-8")
        _sys.stderr.reconfigure(encoding="utf-8")
    fails = []
    root = os.path.dirname(os.path.dirname(os.path.abspath(__file__)))
    raw = os.path.join(root, "extracted", "raw")
    if not os.path.isdir(os.path.join(raw, "FDFIELD")):
        print("SKIP: 找不到 extracted/raw/FDFIELD")
        return 0

    fields = sorted(glob.glob(os.path.join(raw, "FDFIELD", "*.bin")), key=resource_index)
    comp = open(fields[0], "rb").read()
    w, h = struct.unpack_from("<HH", comp, 0)
    md = {"w": w, "h": h, "tiles": [0] * (w * h)}

    print("(1) 控制段固定 16 筆(含 turn=0xff 的休眠列)—— 這是這支特有的不變量")
    controls, slots, events, srcname, digest = expected(raw, 0, md)
    ok1 = len(controls) == 16
    print(f"    {'PASS' if ok1 else 'FAIL'}: turn_controls {len(controls)} 筆(應為 16)")
    if not ok1:
        fails.append(f"控制段 {len(controls)} 筆,應為 16")

    print("\n(2) 來源必須自我標示:回傳的檔名要對得上,sha256 要等於該檔的雜湊")
    want_name = os.path.basename(fields[1])
    want_hash = hashlib.sha256(open(fields[1], "rb").read()).hexdigest()
    ok2 = srcname == want_name and digest == want_hash
    print(f"    {'PASS' if ok2 else 'FAIL'}: {srcname}(應 {want_name})、"
          f"sha256 {'相符' if digest == want_hash else '不符'}")
    if not ok2:
        fails.append(f"來源標示不符:{srcname} vs {want_name}")

    print("\n(3) 維度/來源檢查必須真的擋下不一致的 map_data")
    for label, bad_md in (("w 不符", {"w": w + 1, "h": h, "tiles": [0] * (w * h)}),
                          ("tiles 數不符", {"w": w, "h": h, "tiles": [0] * (w * h - 1)})):
        try:
            expected(raw, 0, bad_md)
            print(f"    FAIL: 「{label}」沒有被擋下")
            fails.append(f"{label} 沒有被擋下")
        except ValueError:
            print(f"    PASS: 「{label}」-> ValueError")

    print("\n(4) 非恆真控制:slots 長度必須等於格數,且不是全部同一個值")
    ok4 = len(slots) == w * h
    print(f"    {'PASS' if ok4 else 'FAIL'}: slots {len(slots)}(應 {w * h})、"
          f"相異值 {len(set(map(str, slots)))} 種")
    if not ok4:
        fails.append(f"slots 長度 {len(slots)} 不等於 {w * h}")

    print("\n(5) 與 sync_native_treasures 對照:同一張圖的維度來源必須一致")
    _sys.path.insert(0, os.path.dirname(os.path.abspath(__file__)))
    try:
        from sync_native_treasures import expected as t_expected
        t_slots, _t_hidden, _t_chests = t_expected(raw, 0, md)
        ok5 = len(t_slots) == len(slots)
        print(f"    {'PASS' if ok5 else 'FAIL'}: treasures {len(t_slots)} vs "
              f"field_events {len(slots)}")
        if not ok5:
            fails.append(f"兩支對同一張圖算出的格數不同:{len(t_slots)} vs {len(slots)}")
    except ImportError as exc:
        print(f"    SKIP: 無法 import sync_native_treasures({exc})")

    print("\n(6) tile_in_terrain 的邊界必須**恰好是** ×4,不能是 ×5")
    # 突變測試發現:原本的判準只被全 0 的合成 tiles 間接測到,tile 恆為 0,
    # ×4 與 ×5 算出同一個結果(都是 0),測不出差異。直接餵邊界值。
    ok6 = (tile_in_terrain(24, 100) and not tile_in_terrain(25, 100)
          and not tile_in_terrain(-1, 100))
    print(f"    {'PASS' if ok6 else 'FAIL'}: terrain_len=100 時,"
          f"tile=24(24*4=96<100)在範圍內={tile_in_terrain(24, 100)}、"
          f"tile=25(25*4=100>=100)不在範圍內={not tile_in_terrain(25, 100)}")
    if not ok6:
        fails.append("tile_in_terrain 的邊界不是 ×4")

    print("\n(6b) terrain 長度對齊判準必須**恰好是** % 4,不能是 % 5")
    # 突變測試量到 `len(terrain) % 4` 改成 `% 5` 逃掉:真實 terrain 長度同時是 4 與 5
    # 的倍數,兩者都判合法。8(%4=0、%5=3)與 10(%4=2、%5=0)正好方向相反。
    ok6b = terrain_len_aligned(8) and not terrain_len_aligned(10)
    print(f"    {'PASS' if ok6b else 'FAIL'}: 8 bytes 合法={terrain_len_aligned(8)}、"
          f"10 bytes 不合法={not terrain_len_aligned(10)}")
    if not ok6b:
        fails.append("terrain 長度對齊判準不是 % 4")

    print("\n(7) 指令/選擇器段的起點 offset 必須**恰好是** 3+16*3=51,"
          "用獨立算出的絕對位置反查同一份 control bytes")
    # 突變測試發現:`offset = 3 + 16 * 3`裡任一個 3 或 16 被改掉,既有題目都測不到——
    # events[]/selector 從來沒有跟獨立算出的絕對 byte 位置對照過。
    control_bytes = open(fields[1], "rb").read()
    want_offset = 3 + 16 * 3
    ok7 = (want_offset == 51
          and events[0]["event_id"] == control_bytes[want_offset]
          and events[0]["selector"] == control_bytes[want_offset + 1]
          and events[15]["event_id"] == control_bytes[want_offset + 15 * 2])
    print(f"    {'PASS' if ok7 else 'FAIL'}: 手算 offset={want_offset},"
          f"events[0]/[15] 與獨立讀出的 bytes 逐一相符={ok7}")
    if not ok7:
        fails.append(f"events[] 讀到的內容與獨立算出的 offset={want_offset} 對不上")

    print("\n(7b) turn_controls 三欄與 16 個 selector/event_id,逐筆對獨立算出的絕對位移")
    # 2026-09-11 窮舉突變測試:turn_controls 的 `3 + slot * 3 (+1/+2)` 與 selector 的
    # `+ 1` 從來沒被對照過((7) 只看 events[0]/[15] 的 event_id 與 events[0] 的 selector,
    # slot 0 時 `slot * 3` 與 `slot * 4` 同值)。前提:各列位元組不全相同,否則位移算錯
    # 也可能碰巧相等 —— 一併印出並斷言。
    fields7 = ("turn", "event_id", "raw_camp")
    tc_bad = [(k, f) for k in range(16) for j, f in enumerate(fields7)
              if controls[k][f] != control_bytes[3 + 3 * k + j]]
    ev_bad = [k for k in range(16)
              if (events[k]["event_id"], events[k]["selector"])
              != (control_bytes[want_offset + 2 * k], control_bytes[want_offset + 2 * k + 1])]
    distinct = len({bytes(control_bytes[3 + 3 * k:6 + 3 * k]) for k in range(16)})
    ok7b = (len(controls) == 16 and len(events) == 16 and not tc_bad and not ev_bad
            and distinct > 1)
    print(f"    {'PASS' if ok7b else 'FAIL'}: 16 列 × 3 欄不符 {tc_bad[:4]}、16 筆事件不符 "
          f"{ev_bad[:4]}、控制列相異值 {distinct} 種(前提 >1)、筆數 {len(controls)}/{len(events)}")
    if not ok7b:
        fails.append(f"turn_controls/events 位移不對:{tc_bad[:4]} / {ev_bad[:4]} / 相異 {distinct}")

    print("\n(8) 來源檔選擇:非 0 的 map 才分辨得出 `map_index * 3` 等算式")
    comp1 = open(fields[3], "rb").read()
    w1, h1 = struct.unpack_from("<HH", comp1, 0)
    _c1, _s1, _e1, src1, dig1 = expected(raw, 1, {"w": w1, "h": h1, "tiles": [0] * (w1 * h1)})
    b8 = {"source_paths map2": (source_paths(list("abcdefghij"), list("ABCDEFGH"), 2)
                                == ("g", "h", "F")),
          "真實 map1 的控制檔": (src1 == os.path.basename(fields[4]) and dig1
                              == hashlib.sha256(open(fields[4], "rb").read()).hexdigest())}
    ok8 = all(b8.values())
    print(f"    {'PASS' if ok8 else 'FAIL'}: " + "、".join(f"{k}={v}" for k, v in b8.items()))
    if not ok8:
        fails.append(f"來源檔選擇不對:{[k for k, v in b8.items() if not v]}")

    print("\n(9) field_event_slot:遮罩、1-based、寶物旗標、stride、tile 0 與越界")
    # tile0 旗標 0、tile1 帶寶物旗標、tile2 只有 bit0(遮罩不得放寬成 0x61)。
    # tile0 的第 1 個 byte 放 0x20:不影響 tile0,但 stride 若被改成 5,tile1 會讀到別處。
    terrain9 = bytes([0x00, 0x20, 0, 0,
                      0x20, 0x00, 0, 0,
                      0x01, 0x00, 0, 0])
    cases9 = [(0, 0x25, 4, "低 5 位 = 5 -> slot 4,bit5 必須被遮掉"),
              (0, 0x20, -1, "低 5 位 = 0 -> 無事件"),
              (1, 0x05, -1, "寶物格不算場上事件"),
              (2, 0x03, 2, "只有 bit0 的地形仍可放事件"),
              (3, 0x05, -1, "tile 超出地形表"),
              (-1, 0x05, -1, "負的 tile")]
    bad9 = [(t, ew, field_event_slot(terrain9, t, ew), want, why)
            for t, ew, want, why in cases9 if field_event_slot(terrain9, t, ew) != want]
    ok9 = not bad9
    print(f"    {'PASS' if ok9 else 'FAIL'}: {len(cases9)} 個合成案例"
          + ("全部正確" if ok9 else f",不符 {bad9}"))
    if not ok9:
        fails.append(f"field_event_slot 判定不對:{bad9}")

    if fails:
        print("\nSELFTEST FAILED:")
        for f in fails:
            print("  -", f)
        return 1
    print("\n--selftest passed(16 筆控制段不變量 + 來源自我標示 + 維度檢查 + "
          "非恆真控制 + 跨工具對照 + terrain 邊界 + offset 絕對位置反查)。")
    return 0


def main():
    import sys
    if len(sys.argv) == 2 and sys.argv[1] == "--selftest":
        return selftest()
    parser = argparse.ArgumentParser()
    parser.add_argument("raw")
    parser.add_argument("assets")
    parser.add_argument(
        "--field-archive",
        default="org_game/炎龍騎士團/FLAME2/FDFIELD.DAT",
    )
    parser.add_argument(
        "--exe",
        default="org_game/炎龍騎士團/FLAME2/FD2.EXE",
    )
    parser.add_argument(
        "--rules",
        default="docs/data/native_field_event_rules.json",
    )
    mode = parser.add_mutually_exclusive_group(required=True)
    mode.add_argument("--check", action="store_true")
    mode.add_argument("--write", action="store_true")
    args = parser.parse_args()
    with open(args.field_archive, "rb") as source:
        field_archive = source.read()
    if (
        len(field_archive) != FDFIELD_SOURCE["size"]
        or hashlib.md5(field_archive).hexdigest() != FDFIELD_SOURCE["md5"]
        or hashlib.sha256(field_archive).hexdigest() != FDFIELD_SOURCE["sha256"]
    ):
        raise SystemExit("FDFIELD.DAT 與固定參考版本不符；禁止重生 native controls")
    with open(args.exe, "rb") as source:
        executable = source.read()
    exe_md5 = hashlib.md5(executable).hexdigest()
    exe_edition = FD2_EDITIONS.get(exe_md5)
    if (
        exe_edition is None
        or len(executable) != exe_edition["size"]
        or hashlib.sha256(executable).hexdigest() != exe_edition["sha256"]
    ):
        raise SystemExit(
            f"FD2.EXE 不是任何已知版本(md5={exe_md5}, size={len(executable)});"
            "禁止重生 native round seed;已知版本見本檔 FD2_EDITIONS")
    with open(args.rules, encoding="utf-8") as source:
        rules = json.load(source)["rules"]

    maps = sorted(
        glob.glob(os.path.join(args.assets, "map*", "map.json")),
        key=lambda path: int(os.path.basename(os.path.dirname(path))[3:]),
    )
    changed = 0
    referenced_event_ids = set()
    turn_control_maps = []
    for path in maps:
        map_index = int(os.path.basename(os.path.dirname(path))[3:])
        with open(path, encoding="utf-8") as source:
            data = json.load(source)
        turn_controls, slots, events, control_resource, control_sha256 = expected(
            args.raw, map_index, data
        )
        turn_control_maps.append({
            "map": map_index,
            "control_resource": control_resource,
            "control_sha256": control_sha256,
            "controls": turn_controls,
        })
        event_ids = {
            events[slot]["event_id"]
            for slot in slots
            if slot >= 0 and events[slot]["event_id"] != 0xFF
        }
        map_rules = [rule for rule in rules if rule["event_id"] in event_ids]
        rules_mismatch = (
            data.get("native_field_event_rules", []) != map_rules
            or (not map_rules and "native_field_event_rules" in data)
        )
        referenced_event_ids.update(
            events[slot]["event_id"]
            for slot in slots
            if slot >= 0 and events[slot]["event_id"] != 0xFF
        )
        mismatch = (
            data.get("native_field_event_slots") != slots
            or data.get("native_field_events") != events
            or rules_mismatch
        )
        if mismatch:
            changed += 1
            if args.write:
                data["native_field_event_slots"] = slots
                data["native_field_events"] = events
                if map_rules:
                    data["native_field_event_rules"] = map_rules
                else:
                    data.pop("native_field_event_rules", None)
                with open(path, "w", encoding="utf-8") as output:
                    json.dump(data, output, ensure_ascii=False, separators=(",", ":"))
                    output.write("\n")
        print(f"map{map_index}: {'更新' if mismatch and args.write else '缺少' if mismatch else '已驗證'}")
    catalog_path = os.path.join(args.assets, "native_turn_event_controls.json")
    catalog = {
        "schema_version": 1,
        "source": FDFIELD_SOURCE,
        "round_seed": {
            "value": 1,
            "writer": "0x2066e",
            "source": {
                "file": "FD2.EXE",
                "size": exe_edition["size"],
                "md5": exe_md5,
                "sha256": exe_edition["sha256"],
                "edition": exe_edition["label"],
            },
        },
        "maps": turn_control_maps,
    }
    try:
        with open(catalog_path, encoding="utf-8") as source:
            catalog_mismatch = json.load(source) != catalog
    except (FileNotFoundError, json.JSONDecodeError):
        catalog_mismatch = True
    if catalog_mismatch:
        changed += 1
        if args.write:
            with open(catalog_path, "w", encoding="utf-8") as output:
                json.dump(catalog, output, ensure_ascii=False, indent=2)
                output.write("\n")
    print(
        "turn controls: "
        + ("更新" if catalog_mismatch and args.write else "缺少" if catalog_mismatch else "已驗證")
    )
    if args.check and changed:
        raise SystemExit(f"{changed} 張 map.json 尚未同步")
    print(f"{len(maps)} 張地圖；異動 {changed}")
    print(
        "實際格子引用 event_id："
        + ",".join(str(event_id) for event_id in sorted(referenced_event_ids))
    )


if __name__ == "__main__":
    # 2026-09-10:與 sync_native_treasures.py 同一個洞 —— 裸呼叫會丟掉 main() 的
    # 回傳值,`--selftest` 印出 SELFTEST FAILED 仍然 exit 0,以離開碼判斷的呼叫端
    # 全都只看得到通過。
    raise SystemExit(main())
