#!/usr/bin/env python3
"""把已證實的 FDFIELD/FDSHAP 寶物資料同步到既有可編輯資產。

本工具只更新 map.json 的 treasure_slots/treasure_hidden，以及同圖
mapN_units.json 的 chests。其他人工校正欄位保持不變。
"""

import argparse
import glob
import json
import os
import struct
import sys

if hasattr(sys.stdout, "reconfigure"):
    sys.stdout.reconfigure(encoding="utf-8")
    sys.stderr.reconfigure(encoding="utf-8")

import parse_field


def resource_index(path):
    return int(os.path.basename(path).split("_")[1].split(".")[0])


# FDFIELD 控制段的版面。拆成具名常數是為了讓 selftest 打得到 —— 2026-09-10
# 的突變測試指出這串算術「可達但無人看管」:selftest 只斷言 slots/hidden 的長度,
# 把 chests 印出來卻沒有斷言,於是 3/16/3/16/2 任何一個被改都照樣通過。
#
# 這兩個數字有**反組譯來源**,不是從本檔的算式反推的(那會是自我實現):
#   doc50 §692:寶箱 reward 必須用 slot 關聯 control `+0x53+slot*3`  -> 起點 0x53
#   doc25 §957:units 陣列在 `[0x53a55]+0x83 + k*0x1a`,並明寫
#              `0x83`=3+48+32+48=header+turn_events+保留+chests  -> 終點 0x83
# 兩份文件各自獨立地釘住這張表的起點與終點,而它們之間差 16*3 = 48。
CONTROL_HEADER_BYTES = 3
TURN_EVENT_ROWS = 16
TURN_EVENT_STRIDE = 3
RESERVED_ROWS = 16
RESERVED_STRIDE = 2
CHEST_ROWS = 16
CHEST_STRIDE = 3
CHEST_TABLE_OFFSET = (CONTROL_HEADER_BYTES
                      + TURN_EVENT_ROWS * TURN_EVENT_STRIDE
                      + RESERVED_ROWS * RESERVED_STRIDE)      # = 0x53
UNITS_ARRAY_OFFSET = CHEST_TABLE_OFFSET + CHEST_ROWS * CHEST_STRIDE   # = 0x83


def expected(raw, map_index, map_data):
    fields = sorted(
        glob.glob(os.path.join(raw, "FDFIELD", "*.bin")), key=resource_index
    )
    shapes = sorted(
        glob.glob(os.path.join(raw, "FDSHAP", "*.bin")), key=resource_index
    )
    composition = open(fields[map_index * 3], "rb").read()
    control = open(fields[map_index * 3 + 1], "rb").read()
    terrain = open(shapes[map_index * 2 + 1], "rb").read()
    w, h = struct.unpack_from("<HH", composition, 0)
    tiles = map_data.get("tiles")
    if (
        map_data.get("w") != w
        or map_data.get("h") != h
        or len(tiles or []) != w * h
        or len(terrain) % 4
    ):
        raise ValueError(f"map{map_index}: source dimensions/provenance invalid")

    slots = []
    hidden = []
    for cell, tile in enumerate(tiles):
        if tile < 0 or tile * 4 >= len(terrain):
            slots.append(-1)
            hidden.append(False)
            continue
        flags = terrain[tile * 4]
        if flags & 0x60:
            event_word = struct.unpack_from("<H", composition, 6 + cell * 4)[0]
            slots.append(event_word & 0x1F)
            hidden.append(bool(flags & 0x40))
        else:
            slots.append(-1)
            hidden.append(False)

    offset = CHEST_TABLE_OFFSET
    chests = []
    # 這裡原本重寫一次 `range(16)` 與 `slot * 3` 的字面值,與上面的具名常數各自為政:
    # 突變測試把這兩個字面值改掉時,(2b) 的版面斷言完全看不到(它管的是常數)。
    # 改用同一組常數,版面就只有一個來源。
    for slot in range(CHEST_ROWS):
        native_type = control[offset + slot * CHEST_STRIDE]
        value = struct.unpack_from("<H", control, offset + slot * CHEST_STRIDE + 1)[0]
        if native_type == 0xFF or value == 0:
            continue
        kind = parse_field.native_reward_kind(native_type)
        chests.append(
            {
                "slot": slot,
                "type": kind,
                "native_type": native_type,
                "value": value,
            }
        )
    return slots, hidden, chests


def selftest():
    """這支工具的消費端(`remake/assets`)已於 2026-09-02 刪除,但 `expected()`
    抽取原版資料的那一半仍然是有價值的知識,而且是純函式:給定 `extracted/raw`
    與一份 map 描述,它從 FDFIELD/FDSHAP 算出寶物格。

    所以這裡只驗**抽取側**:維度/來源檢查要真的擋、輸出形狀要對、旗標判定要有
    鑑別力。寫進 assets 的那一半沒有目標可寫,不在檢查範圍,理由記在這裡而不是
    默默略過。
    """
    import sys as _sys
    if hasattr(_sys.stdout, "reconfigure"):
        _sys.stdout.reconfigure(encoding="utf-8")
        _sys.stderr.reconfigure(encoding="utf-8")
    fails = []
    root = os.path.dirname(os.path.dirname(os.path.abspath(__file__)))
    raw = os.path.join(root, "extracted", "raw")

    print("(1) resource_index 必須從檔名取出正確的索引")
    cases = [("FDFIELD_000.bin", 0), ("FDFIELD_017.bin", 17), ("FDSHAP_123.bin", 123)]
    bad = [(n, resource_index(n)) for n, want in cases if resource_index(n) != want]
    ok1 = not bad
    print(f"    {'PASS' if ok1 else 'FAIL'}: {len(cases)} 個檔名"
          + ("全部正確" if ok1 else f",錯誤 {bad}"))
    if not ok1:
        fails.append(f"resource_index 解析錯誤:{bad}")

    if not os.path.isdir(os.path.join(raw, "FDFIELD")):
        print("\n    SKIP: 找不到 extracted/raw/FDFIELD,抽取側無法驗證")
        if fails:
            print("\nSELFTEST FAILED:")
            for f in fails:
                print("  -", f)
            return 1
        print("\n--selftest passed(僅檔名解析;缺原版資料)。")
        return 0

    print("\n(2) 用真實 FDFIELD 的維度組出 map_data,expected() 必須算出整張圖的格數")
    fields = sorted(glob.glob(os.path.join(raw, "FDFIELD", "*.bin")), key=resource_index)
    comp = open(fields[0], "rb").read()
    w, h = struct.unpack_from("<HH", comp, 0)
    md = {"w": w, "h": h, "tiles": [0] * (w * h)}
    slots, hidden, chests = expected(raw, 0, md)
    ok2 = len(slots) == w * h and len(hidden) == w * h
    print(f"    {'PASS' if ok2 else 'FAIL'}: map0 {w}x{h} -> slots {len(slots)}、"
          f"hidden {len(hidden)}、chests {len(chests)}")
    if not ok2:
        fails.append(f"輸出長度不等於 w×h:{len(slots)}/{len(hidden)} vs {w * h}")

    print("\n(2b) 寶箱表的版面算術必須對上兩份反組譯來源的文件值")
    # 上面的 (2) 只斷言 slots/hidden 的長度,chests 只印不驗 —— 於是
    # `3 + 16*3 + 16*2` 這串算術「可達但無人看管」,任一項被改都照樣通過。
    # 這裡用**文件記載的兩個位址**釘它,而不是拿本檔自己的算式當答案:
    #   doc50 §692 -> 起點 0x53;doc25 §957 -> units 起點 0x83(該文自己寫明
    #   0x83 = 3+48+32+48),兩者之差正好是 16*3 的寶箱表。
    ok2b = (CHEST_TABLE_OFFSET == 0x53 and UNITS_ARRAY_OFFSET == 0x83
            and UNITS_ARRAY_OFFSET - CHEST_TABLE_OFFSET == CHEST_ROWS * CHEST_STRIDE)
    print(f"    {'PASS' if ok2b else 'FAIL'}: 寶箱表 0x{CHEST_TABLE_OFFSET:02x}"
          f"(doc50 應為 0x53)-> units 0x{UNITS_ARRAY_OFFSET:02x}(doc25 應為 0x83)"
          f",相距 {UNITS_ARRAY_OFFSET - CHEST_TABLE_OFFSET}(應為 {CHEST_ROWS * CHEST_STRIDE})")
    if not ok2b:
        fails.append(f"控制段版面算術與文件不符:0x{CHEST_TABLE_OFFSET:02x}/"
                     f"0x{UNITS_ARRAY_OFFSET:02x}")

    print("\n(2c) 非平凡性:寶箱表確實被讀到,且讀出的欄位隨 slot 變動")
    # 沒有這一題,(2b) 只是在驗兩個常數彼此相等,可能整段程式碼根本沒用到它們。
    control = open(sorted(glob.glob(os.path.join(raw, "FDFIELD", "*.bin")),
                          key=resource_index)[1], "rb").read()
    row_bytes = {control[CHEST_TABLE_OFFSET + s * CHEST_STRIDE:
                         CHEST_TABLE_OFFSET + (s + 1) * CHEST_STRIDE]
                 for s in range(CHEST_ROWS)}
    ok2c = len(chests) > 0 and len(row_bytes) > 1
    print(f"    {'PASS' if ok2c else 'FAIL'}: map0 取出 {len(chests)} 個寶箱、"
          f"16 列原始位元組有 {len(row_bytes)} 種相異值(1 種代表讀到的是常數區)")
    if not ok2c:
        fails.append(f"寶箱表看起來沒被真的讀到:chests={len(chests)}、"
                     f"相異列={len(row_bytes)}")

    print("\n(3) 維度/來源檢查必須真的擋下不一致的 map_data(否則會算出垃圾)")
    for label, bad_md in (
        ("w 不符", {"w": w + 1, "h": h, "tiles": [0] * (w * h)}),
        ("h 不符", {"w": w, "h": h + 1, "tiles": [0] * (w * h)}),
        ("tiles 數不符", {"w": w, "h": h, "tiles": [0] * (w * h - 1)}),
    ):
        try:
            expected(raw, 0, bad_md)
            print(f"    FAIL: 「{label}」沒有被擋下")
            fails.append(f"{label} 沒有被擋下")
        except ValueError:
            print(f"    PASS: 「{label}」-> ValueError")

    print("\n(4) 非恆真控制:tile 索引全部越界時,每一格都必須是 -1/False")
    md_oob = {"w": w, "h": h, "tiles": [999999] * (w * h)}
    s2, h2, _c2 = expected(raw, 0, md_oob)
    ok4 = set(s2) == {-1} and set(h2) == {False}
    print(f"    {'PASS' if ok4 else 'FAIL'}: slots 唯一值 {sorted(set(s2))[:3]}、"
          f"hidden 唯一值 {sorted(set(h2))}")
    if not ok4:
        fails.append("越界 tile 沒有一致地落到 -1/False")

    if fails:
        print("\nSELFTEST FAILED:")
        for f in fails:
            print("  -", f)
        return 1
    print("\n--selftest passed(檔名解析 + 真實資料抽取 + 維度檢查 3 種 + 非恆真控制)。")
    return 0


def main():
    if len(sys.argv) == 2 and sys.argv[1] == "--selftest":
        return selftest()
    parser = argparse.ArgumentParser()
    parser.add_argument("raw")
    parser.add_argument("assets")
    parser.add_argument(
        "--rules",
        default="docs/data/native_treasure_event_rules.json",
    )
    mode = parser.add_mutually_exclusive_group(required=True)
    mode.add_argument("--check", action="store_true")
    mode.add_argument("--write", action="store_true")
    args = parser.parse_args()
    with open(args.rules, encoding="utf-8") as source:
        rules = json.load(source)["rules"]

    maps = sorted(
        glob.glob(os.path.join(args.assets, "map*", "map.json")),
        key=lambda path: int(os.path.basename(os.path.dirname(path))[3:]),
    )
    changed = 0
    for map_path in maps:
        map_dir = os.path.dirname(map_path)
        map_index = int(os.path.basename(map_dir)[3:])
        units_path = os.path.join(map_dir, f"map{map_index}_units.json")
        with open(map_path, encoding="utf-8") as source:
            map_data = json.load(source)
        with open(units_path, encoding="utf-8") as source:
            units_data = json.load(source)
        slots, hidden, chests = expected(args.raw, map_index, map_data)
        event_ids = {chest["value"] for chest in chests if chest["type"] == "event"}
        map_rules = [rule for rule in rules if rule["event_id"] in event_ids]
        rules_mismatch = (
            units_data.get("native_treasure_event_rules", []) != map_rules
            or (not map_rules and "native_treasure_event_rules" in units_data)
        )
        mismatch = (
            map_data.get("treasure_slots") != slots
            or map_data.get("treasure_hidden") != hidden
            or units_data.get("chests") != chests
            or rules_mismatch
        )
        if mismatch:
            changed += 1
            if args.write:
                map_data["treasure_slots"] = slots
                map_data["treasure_hidden"] = hidden
                units_data["chests"] = chests
                if map_rules:
                    units_data["native_treasure_event_rules"] = map_rules
                else:
                    units_data.pop("native_treasure_event_rules", None)
                with open(map_path, "w", encoding="utf-8") as output:
                    json.dump(map_data, output, ensure_ascii=False, separators=(",", ":"))
                    output.write("\n")
                with open(units_path, "w", encoding="utf-8") as output:
                    json.dump(units_data, output, ensure_ascii=False, separators=(",", ":"))
                    output.write("\n")
        state = "更新" if mismatch and args.write else "缺少" if mismatch else "已驗證"
        print(f"map{map_index}: {state}；寶物格 {sum(slot >= 0 for slot in slots)}")
    if args.check and changed:
        raise SystemExit(f"{changed} 張地圖的寶物資料尚未同步")
    print(f"{len(maps)} 張地圖；異動 {changed}")


if __name__ == "__main__":
    # 2026-09-10:原本是裸呼叫 `main()`,回傳值被丟掉,於是 `--selftest` 即使
    # 印出 SELFTEST FAILED 也**照樣 exit 0**。任何以離開碼判斷的呼叫端
    # (verify_all_tools 的 selftest 層、突變測試的基準與捕捉判定)都只會看到通過
    # —— 這也正是這支工具長期被判 WEAK 的原因:它的 selftest 不可能失敗。
    raise SystemExit(main())
