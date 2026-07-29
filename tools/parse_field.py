#!/usr/bin/env python3
"""炎龍騎士團2 — FDFIELD 戰場定義解析(構成 / 控制 / 出場 三段)。

FDFIELD.DAT 每 3 資源 = 一張戰場:
  資源 3N+0 構成: u16 W, u16 H, 每格 (u16 地形索引, u16 事件/寶箱)
  資源 3N+1 控制: u8 地圖編號, u8 己方可出場數, u8 敵友出場總數,
                  回合事件[16]×3B(回合 u8, 全域事件id u8, 陣營 u8:0敵/1友/2特殊),
                  格子事件[16]×2B(全域事件id u8, selector u8),
                  寶箱[16]×3B(型態u8:0物品/1金錢, 內容u16),
                  出場人物[敵友總數]×26B(陣營,肖像,種族,職業,等級,物品×8,
                  initial-command-mask×4,其餘未解 bytes×4,group(波次),drop×4)
    註:單位 b21=group(出場波次,turn_events 觸發);增援單位的座標在 3N+2 出場位置段(地圖角落)。
    事件腳本「在 FDFIELD.DAT 資料」(非 EXE);EXE handler 只管勝負判定。remake 重新設計可擴充 DSL,不照搬本格式。
  資源 3N+2 出場位置: u16 人數, 每組 (u16 X, u16 Y, u16 肖像;0=己方)

用法:
    python3 parse_field.py <raw解包根> <map編號>        # 印該圖定義(JSON 摘要)
    python3 parse_field.py --all <raw解包根> <out.json>  # 全 33 圖 metadata → JSON
"""
import sys
import os
import json
import struct
import glob


def parse_map(raw, m):
    fld = sorted(glob.glob(os.path.join(raw, "FDFIELD", "*.bin")))
    comp = open(fld[m * 3], "rb").read()
    ctl = open(fld[m * 3 + 1], "rb").read()
    spw = open(fld[m * 3 + 2], "rb").read()
    w, h = struct.unpack_from("<HH", comp, 0)
    info = {"map": m, "w": w, "h": h,
            "own_deploy": ctl[1], "enemy_ally_total": ctl[2]}
    # 回合事件:(turn, 全域事件id, 陣營 0敵/1友/2特殊)
    o = 3
    info["turn_events"] = [{"turn": ctl[o+i*3], "event_id": ctl[o+i*3+1],
                            "camp": ["enemy", "ally", "special"][ctl[o+i*3+2]] if ctl[o+i*3+2] < 3 else ctl[o+i*3+2]}
                           for i in range(16) if ctl[o+i*3] != 0xFF]
    o += 16*3
    # 0x13a44 以地圖構成 event-word low5 的 1-based slot 查這張表；
    # 第一 byte 寫入 [0x51a8f]，第二 byte 必須等於 caller selector。
    info["field_events"] = [
        {"slot": i, "event_id": ctl[o+i*2], "selector": ctl[o+i*2+1]}
        for i in range(16)
    ]
    o += 16*2
    info["chests"] = []
    for i in range(16):
        t = ctl[o+i*3]; v = struct.unpack_from("<H", ctl, o+i*3+1)[0]
        if t != 0xFF and v != 0:
            # 地圖構成每格第二個 word 的低 5 bit 直接索引這個 slot。
            # slot 0 是合法值（map10 星之眼即 slot0），不可用 truthiness 丟掉。
            info["chests"].append({"slot": i, "type": "gold" if t == 1 else "item", "value": v})
    o += 16*3
    units = []
    for k in range(ctl[2]):
        b = ctl[o+k*26:o+(k+1)*26]
        if len(b) < 26:
            break
        death_type = b[22]
        death_value = b[23] | (b[24] << 8) | (b[25] << 16)
        units.append({"camp": ["enemy", "ally", "own"][b[0]] if b[0] < 3 else b[0],
                      # 0x10ec1/0x10ef5 copy this raw byte to runtime +6,
                      # while 0x10ed6 passes it to 0x11019 before writing the
                      # returned FDICON cache slot to +2. Keep the raw key
                      # separate from the human-readable camp label.
                      "native_map_selector_key": b[0],
                      # 0x10ec1/0x10ef5 copy the same FDFIELD b0 directly to
                      # runtime record +6. Preserve this raw provenance; it
                      # is not a normalized camp synonym.
                      "native_record_byte6": b[0],
                      "portrait": b[1], "race": b[2], "cls": b[3], "lv": b[4],
                      "inventory": [item for item in b[5:13] if item != 0xFF],
                      "inventory_slots": list(b[5:13]),
                      # Constructor 0x10f7f copies exactly b[13:17] to runtime
                      # unit+0x1a..+0x1d, then clears byte +0x1e.  Do not turn
                      # these bits into spell IDs here: they are native command
                      # inventory and individual ID effects remain unresolved.
                      "initial_command_mask": list(b[13:17]),
                      # Constructor 0x10fb6..0x10fc5 copies these exact source
                      # bytes to runtime +0x34/+0x35/+0x36.  Only +0x34 low
                      # nibble is the 0x13a9f dispatch mode; preserve all bits.
                      "native_record_byte34": b[17],
                      "native_record_byte35": b[18],
                      "native_record_byte36": b[19],
                      "group": b[21],
                      # 0=item、1=gold 已由原攻略確認；2/3 是特殊死亡效果，
                      # 語意未全解前保留原值，不猜成一般掉落物。
                      "death_effect": None if death_type == 0xFF else {
                          "type": death_type, "value": death_value,
                      }})   # b21=出場波次 group;b22-25=死亡效果
    info["units"] = units
    n = struct.unpack_from("<H", spw, 0)[0]
    info["positions"] = [list(struct.unpack_from("<HHH", spw, 2+k*6)) for k in range(n)]
    return info


def main(argv):
    if len(argv) < 3:
        print(__doc__); return 1
    if argv[1] == "--all":
        raw, out = argv[2], argv[3]
        fld = sorted(
            glob.glob(os.path.join(raw, "FDFIELD", "*.bin")),
            key=lambda p: int(os.path.basename(p).split("_")[1].split(".")[0]),
        )
        maps = []
        for m in range(len(fld)//3):
            try:
                maps.append(parse_map(raw, m))
            except Exception as e:
                maps.append({"map": m, "error": str(e)})
        json.dump(maps, open(out, "w", encoding="utf-8"), ensure_ascii=False, indent=1)
        print(f"{len(maps)} 張戰場 metadata -> {out}")
        return 0
    info = parse_map(argv[1] if False else argv[1], int(argv[2]))
    print(json.dumps(info, ensure_ascii=False, indent=1))
    return 0


if __name__ == "__main__":
    sys.exit(main(sys.argv))
