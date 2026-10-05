"""把 tA/tB 兩輪在 0x149f0 的傾印整理成 repo 內的證據 JSON(doc98 續四十六)。"""
import json
import struct
from pathlib import Path

from _evpaths import GAME, GEN_DIR, ROOT, out_path, require_inputs  # noqa: E402,F401
require_inputs(__file__)
D = ROOT / ".wsl_build" / "ctr"
OUT = out_path("collect_targets_in_range_20260929.json")
W, H, N = 27, 21, 21

rounds = {}
for tag in ("tA", "tB"):
    stack = (D / f"{tag}_stack.bin").read_bytes()
    cells = (D / f"{tag}_map.bin").read_bytes()
    units = (D / f"{tag}_units.bin").read_bytes()
    out = (D / f"{tag}_out.bin").read_bytes()
    count, = struct.unpack_from("<I", stack, 0)
    ret, ox, oy, outp, rng, thr, sel = struct.unpack_from("<7I", stack, 0x14)
    mark = lambda x, y: cells[7 + 4 * (y * W + x)]
    rows, pred = [], []
    for i in range(N):
        r = units[i * 80:(i + 1) * 80]
        x, y, f5, side = r[0], r[1], r[5], r[6]
        m = mark(x, y)
        inc = not (f5 & 1) and m != 0xFF and side == 0
        rows.append({"unit": i, "x": x, "y": y, "side": side, "flags5": f5, "cell_mark": m,
                     "manhattan": abs(x - ox) + abs(y - oy), "predicted_in": inc})
        if inc:
            pred.append(i)
    rounds[tag] = {
        "return_address_live": hex(ret), "return_address_static": hex(ret - 0x19C000),
        "origin": [ox, oy], "out_buf_live": hex(outp), "range": rng, "threshold": thr, "selector": sel,
        "returned_count": count, "out_buf": list(out[:count]), "predicted": pred,
        "match": list(out[:count]) == pred, "units": rows,
        "marks_rows": [" ".join(".." if mark(x, y) == 0xFF else "%02x" % mark(x, y) for x in range(W)) for y in range(H)],
    }
    assert rounds[tag]["match"]
doc = {
    "note": "DOSBox-X 在 collect_targets_in_range 返回點 0x149f0(執行期 0x1b09f0)的記憶體傾印整理;FD2.EXE md5 33464c81e6a364fd0660141139aa8e6e。"
            "predicted 依『+5 bit0 未設、格子記號 != 0xff、+6 == 0』離線計算,out_buf 是程式寫出的清單。",
    "map": {"pointer_live": "0x21934c", "width": W, "height": H, "mark_offset": "4-byte 表頭後每格 4 bytes 的 byte3"},
    "rounds": rounds,
}
OUT.write_bytes((json.dumps(doc, ensure_ascii=False, indent=1) + "\n").encode("utf-8"))
print("ok", OUT.stat().st_size)
