#!/usr/bin/env python3
"""匯出 map25 已閉合的格子事件 59／60／61 規則。"""

import hashlib
import json
import os
import sys

sys.path.insert(0, os.path.dirname(os.path.abspath(__file__)))
import safe_output  # noqa: E402

# 2026-09-03:改成同時支援兩個版本(見 extract_event_id_groups.py 的同名表)。
# 位移是分區段常數:handler 本體 +0x356,而資料表 0x5274e 兩版**相同**。
EDITIONS = {
    "b97caf2239a27a896069d03549d96e1e": {
        "label": "舊版(357074 B,已遺失)", "size": 357074, "handler_delta": 0},
    "33464c81e6a364fd0660141139aa8e6e": {
        "label": "新版(1998 重打包版,509158 B)", "size": 509158, "handler_delta": 0x356},
}


def main(argv):
    if len(argv) != 3:
        print(f"usage: {argv[0]} FD2.EXE output.json", file=sys.stderr)
        return 2
    data = open(argv[1], "rb").read()
    md5 = hashlib.md5(data).hexdigest()
    edition = EDITIONS.get(md5)
    if edition is None or len(data) != edition["size"]:
        raise SystemExit(
            f"FD2.EXE 不是任何已知版本(md5={md5}, size={len(data)}),"
            "禁止沿用固定 handler 位址;已知版本見本檔 EDITIONS")
    delta = edition["handler_delta"]
    result = {
        "source": {
            "file": os.path.basename(argv[1]),
            "size": len(data),
            "md5": md5,
            "sha256": hashlib.sha256(data).hexdigest(),
            "edition": edition["label"],
            "handler_delta": hex(delta),
        },
        "rules": [
            {
                "event_id": 59,
                "handler": hex(0x35641 + delta),
                "selector": 0,
                "trigger_gate": "record_byte6_nonzero",
                "set_mode_ranges": [{"start": 39, "end": 44, "mode": 0}],
            },
            {
                "event_id": 60,
                "handler": hex(0x35675 + delta),
                "selector": 0,
                "trigger_gate": "record_byte6_nonzero",
                "set_mode_ranges": [
                    {"start": 23, "end": 24, "mode": 0},
                    {"start": 53, "end": 56, "mode": 0},
                ],
            },
            {
                "event_id": 61,
                "handler": hex(0x356b7 + delta),
                "selector": 1,
                "once_state_index": 12,
                "required_item": 208,
                "consume_item": True,
                "spawn_group": 1,
                "join_character": 31,
                "text_indices": {"missing_item": 2, "success": 3, "final": 4},
                "presentation": {
                    "archive": "FDOTHER.DAT",
                    "resource": 45,
                    "frames": 59,
                    "helper": "0x2935b",
                    "destination_offset": 48356,
                    "stride": 320,
                    "transparent": -1,
                    "delay_helper": "0x17aa9",
                    "delay_ticks": 2,
                },
            },
            # 2026-09-03 補回:event 62 早在 commit c39db56b(「接通 event62 休眠回合列
            # 啟用」)就寫進 docs/data/native_field_event_rules.json,**但從未加進本工具**,
            # 所以那個檔案自那時起就無法由自己的產生器重現。這是本 repo 第三次出現同一種
            # 模式(另兩次:command_labels.json、unicode_to_glyph.json)。
            #
            # 數值當天以反組譯逐條複核(新版 handler 0x35bee):
            #   cmp byte ptr [eax + 0x11], 0   → once_state_index = 17(0x11)
            #   mov dl, [0x3bef]; inc dl       → turn_delta = 1(讀回合計數器後 +1)
            #   mov eax, [0x3a55]; mov [eax+3], dl  → 寫進 turn_events 的 turn 欄位
            #   mov byte ptr [eax + 0x11], 1   → 標記 once-state 已觸發
            # `event_id: 63` 與 `raw_camp: 0` **不是程式碼常數**——handler 只改寫 turn
            # 那個 byte,63/0 是 FDFIELD.DAT 裡既有的槽位資料,靠靜態反組譯搆不到。
            #
            # 未解:寫入位置是 [base+3],而本欄記為 slot 0。若 turn_events 是 3B/筆且
            # slot 0 從 +0 起,+3 會是 slot 1。可能是槽位佈局有前綴,也可能 slot 欄位
            # 記錯。沒有把握之前不改值,先誠實標記。
            {
                "event_id": 62,
                "handler": hex(0x35898 + delta),
                "selector": 0,
                "once_state_index": 17,
                "turn_activation": {
                    "slot": 0,
                    "event_id": 63,
                    "raw_camp": 0,
                    "turn_delta": 1,
                },
            },
        ],
    }
    # 2026-09-04:argv[2] 是任意輸出路徑,寫入前不讀它——與 extract_event_id_groups
    # 同一個危險形狀(當天真的因此覆寫掉參考 FD2.EXE)。
    try:
        safe_output.guard_json_output(argv[2])
    except safe_output.UnsafeOutputPath as exc:
        print(f"{exc}\n用法: extract_native_field_event_rules.py <FD2.EXE> <輸出.json>",
              file=sys.stderr)
        return 2
    with open(argv[2], "w", encoding="utf-8") as output:
        json.dump(result, output, ensure_ascii=False, indent=2)
        output.write("\n")
    return 0


if __name__ == "__main__":
    raise SystemExit(main(sys.argv))
