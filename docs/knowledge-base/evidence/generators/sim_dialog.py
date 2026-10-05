"""續七十一:對白播放器 0x15f84 的字碼流模擬(只模擬控制流程,不畫圖)。

依 0x15f84 的反組譯(0x15fb9 起):
  起點 = table + movsx(word[table + idx*2])(有號 16 位元,不檢查 idx 是否超出偏移表)
  迴圈 0x1630d:c = movsx word[esi]
    -1 結束;-2 換行;-3 換頁(0x16c57(1));-4 / -5 巢狀播放 [0x53a7d] 的 [0x53ad9] / [0x53add] 條;
    -6 印數字 [0x53ae1];-0x11 / -0x12 開框(運算元 = char_id,0x12c60 找說話者);
    -0x13 / -0x14 開框(運算元 = 單位索引,直接取 [0x53a45] + 索引 * 0x50);其餘全部當字模(0x4ed7a,不檢查範圍)。
  -2 / -3 / 字模 esi += 2;開框 esi += 4。
輸出:每個控制碼的 (種類, 檔內位移, 運算元),以及兩個控制碼之間的字模數、超出字型範圍的字模數。

用法:python sim_dialog.py <FDTXT.bin> <idx> [font.bin] [--json out.json]
"""
from __future__ import annotations

import json
import struct
import sys
from pathlib import Path

CTRL = {-1: "end", -2: "newline", -3: "page", -4: "nested_53ad9", -5: "nested_53add", -6: "number_53ae1",
        -0x11: "open_char_top", -0x12: "open_char_bottom", -0x13: "open_unit_top", -0x14: "open_unit_bottom"}
GLYPH_BYTES = 32


def simulate(data: bytes, idx: int, n_glyphs: int | None = None, limit: int = 20000) -> dict:
    """依 0x15f84 的規則走一遍字碼流。

    Args:
        data: 整個 FDTXT 章節檔(執行期 [0x53a79] 指向的就是這份內容)。
        idx: 0x15f84 的第二個引數。
        n_glyphs: 字型的字模數;給了就統計超出範圍的字模。
        limit: 最多走幾個字碼(防止沒有結束碼時無限迴圈)。

    Returns:
        dict:起點、事件清單、統計。檔案外的位置記為 'past_file'(執行期讀到的是緩衝區之後的記憶體)。
    """
    tbl = struct.unpack_from("<h", data, 2 * idx)[0] if 2 * idx + 2 <= len(data) else None
    out = {"idx": idx, "table_entries": struct.unpack_from("<H", data, 0)[0] // 2, "table_word_offset": 2 * idx,
           "start": tbl, "start_odd": bool(tbl is not None and tbl % 2), "events": []}
    if tbl is None:
        out["error"] = "table word past file"
        return out
    p = tbl
    glyphs = bad = neg = 0
    steps = 0
    while steps < limit:
        steps += 1
        if p < 0 or p + 2 > len(data):
            out["events"].append({"kind": "past_file", "off": p, "glyphs_before": glyphs})
            break
        c = struct.unpack_from("<h", data, p)[0]
        if c in CTRL:
            ev = {"kind": CTRL[c], "off": p, "glyphs_before": glyphs, "out_of_font_before": bad}
            if c <= -0x11:
                ev["operand"] = struct.unpack_from("<H", data, p + 2)[0] if p + 4 <= len(data) else None
                p += 4
            else:
                p += 2
            out["events"].append(ev)
            glyphs = bad = 0
            if c == -1:
                break
            continue
        glyphs += 1
        if c < 0:
            neg += 1
        if n_glyphs is not None and not (0 <= c < n_glyphs):
            bad += 1
        p += 2
    out["codes_walked"] = steps
    out["negative_glyph_codes"] = neg
    out["trailing_glyphs"] = glyphs
    return out


def main(argv: list[str]) -> int:
    path, idx = Path(argv[1]), int(argv[2], 0)
    font = Path(argv[3]) if len(argv) > 3 and not argv[3].startswith("--") else None
    n = len(font.read_bytes()) // GLYPH_BYTES if font else None
    r = simulate(path.read_bytes(), idx, n)
    r["file"] = path.name
    r["font_glyphs"] = n
    kinds: dict[str, int] = {}
    for e in r["events"]:
        kinds[e["kind"]] = kinds.get(e["kind"], 0) + 1
    r["event_counts"] = kinds
    print(json.dumps({k: v for k, v in r.items() if k != "events"}, ensure_ascii=False))
    for e in r["events"][:80]:
        print(" ", e)
    if "--json" in argv:
        Path(argv[argv.index("--json") + 1]).write_text(json.dumps(r, ensure_ascii=False, indent=1), encoding="utf-8")
    return 0


if __name__ == "__main__":
    sys.exit(main(sys.argv))
