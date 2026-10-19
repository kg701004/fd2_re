"""續一百二十四證據:evidence/rest_and_item79_branch_20261014.json。

lc124 三輪實機紀錄(休息、item_effect_dispatch 的 0x14 / 0x18 分支)逐項對靜態預測。原本由暫存的 mk_evidence124.py
+ an124.py + mut_an124.py 產生(續一百二十四);續一百三十四移進倉庫:分析是 lc124_analyze.py、突變是 lc124_mut.py
(以子行程重跑,輸出原樣寫進證據),原始紀錄在 .wsl_build/lc124_live/。
兩張對照圖在這裡由傾印重畫,與已提交的 PNG 逐像素比對(文字標籤不比,只比貼上的畫面)。
"""
from __future__ import annotations

import contextlib
import hashlib
import io
import json
import subprocess
import sys

from PIL import Image, ImageChops

from _evpaths import EVIDENCE, GAME, GEN_DIR, ROOT, out_path, require_inputs  # noqa: E402
require_inputs(__file__)
import lc124_analyze as an124  # noqa: E402

D = ROOT / ".wsl_build" / "lc124_live"
OUT = out_path("rest_and_item79_branch_20261014.json")
EXE_MD5 = "33464c81e6a364fd0660141139aa8e6e"
assert hashlib.md5((GAME / "FD2.EXE").read_bytes()).hexdigest() == EXE_MD5
KEEP = (0, 3, 5, 10, 11)
WHAT = {
    "r1": "第 1 回合。arm 時索爾 HP 設 3、敵 #11 搬到 (19,14)、slot2 = 道具 79;索爾沒移動就休息。ai_item_action 入口把索爾 HP 改回 823。"
          "道具 79 打到 #5、#10(友軍 NPC),兩個都命中。",
    "r2": "第 2 回合。法術列 3 的命中率在記憶體裡改成 0(執行期線性 0x1f3a14);索爾滿血休息。打到 #0 索爾與 #3,兩個都沒命中。",
    "r3": "第 3 回合。命中率改回 85(0x55);索爾 HP 設 3,先往上移一格再休息。只打到 #3,亂數 91 >= 85 沒命中。"
          "收尾第 9 幀之後 WSL 虛擬機停掉(原因不明,發生在使用者暫停期間),instance 隨之消失;之後的站沒有錄到。",
}


def trim(s: dict) -> dict:
    s = dict(s)
    if "units" in s:
        s["units"] = [{k: u[k] for k in ("i", "x", "y", "f5", "camp", "f7", "cls", "lv", "hp", "mhp")} for u in s["units"] if u["i"] in KEEP]
    if "row" in s and isinstance(s["row"], dict):
        s["row"] = {k: s["row"][k] for k in ("i", "x", "y", "f5", "camp", "f7", "cls", "lv", "poison", "para", "hp", "mhp")}
    return s


def sheet_tiles_match(tag: str, committed: Image.Image) -> bool:
    """對照圖(當時 sheet124.py):目標附近裁切、放大 2 倍,三列(動畫 / 閃爍 / 收尾);每格畫面區與傾印重畫逐像素相同。"""
    cw0, ch0, z = 112, 84, 2
    st = json.loads((D / f"{tag}.json").read_text(encoding="utf-8"))["stops"]
    call = next(s for s in st if s["at"] == "0x20f80")
    sx, sy = call["g"]["scroll_x"], call["g"]["scroll_y"]
    disp = next(s for s in st if s["at"] == "0x20c6f")
    pos = {u["i"]: (u["x"], u["y"]) for u in disp["units"]}
    tg = list(bytes.fromhex(call["targets"]))
    vis = [t for t in tg if sy <= pos[t][1] < sy + 8 and sx <= pos[t][0] < sx + 13]
    xs = [4 + (pos[t][0] - sx) * 24 for t in vis]
    ys = [4 + (pos[t][1] - sy) * 24 - 6 for t in vis]
    cx, cy = (min(xs) + max(xs)) // 2 + 12, (min(ys) + max(ys)) // 2 + 15
    w = max(cw0, max(xs) - min(xs) + 72)
    box = (max(0, cx - w // 2), max(0, cy - ch0 // 2), min(320, cx + w // 2), min(200, cy + ch0 // 2))
    nfin = len([s for s in st if s["at"] == "0x1dfd7"])
    rows = [[f"{tag}_pre00"] + [f"{tag}_anim{k:02d}" for k in range(8)],
            [f"{tag}_ret20f85_00"] + [f"{tag}_flash{k:02d}" for k in range(10)],
            [f"{tag}_ret20fa0_00"] + [f"{tag}_fin{k:02d}" for k in range(0, nfin, 2)]]
    cw, ch = (box[2] - box[0]) * z, (box[3] - box[1]) * z
    ncol = max(len(r) for r in rows)
    if committed.size != (ncol * (cw + 4) + 4, len(rows) * (ch + 18) + 4):
        return False
    p = bytes(min(255, (v & 0x3F) * 255 // 63) for v in (D / f"{tag}_pal.bin").read_bytes())
    for r, names in enumerate(rows):
        for c, nm in enumerate(names):
            im = Image.frombytes("P", (320, 200), (D / f"{nm}.bin").read_bytes())
            im.putpalette(p)
            im = im.convert("RGB").crop(box).resize((cw, ch), Image.NEAREST)
            x, y = 4 + c * (cw + 4), 4 + r * (ch + 18) + 14
            if ImageChops.difference(committed.crop((x, y, x + cw, y + ch)), im).getbbox() is not None:
                return False
    return True


an124.results.clear()
_buf = io.StringIO()
with contextlib.redirect_stdout(_buf):
    _rc = an124.main()
assert _rc == 0, _buf.getvalue()[-2000:]
res = list(an124.results)
real = [r for r in res if not r["control"]]
ctl = [r for r in res if r["control"]]
mut = subprocess.run([sys.executable, str(GEN_DIR / "lc124_mut.py")], capture_output=True, text=True, encoding="utf-8")
assert mut.returncode == 0 and "漏掉 0" in mut.stdout, mut.stdout + mut.stderr
out: dict = {
    "date": "2026-10-14", "exe_md5": EXE_MD5,
    "method": "DOSBox-X 除錯器斷點,第 1 章戰場,連續 3 個回合(只改模擬器記憶體裡的單位資料與法術列 3 的命中率,程式碼不動)。"
              "休息:0x19077(指令環 cmp [esp+0xa0], 0)、0x13fd4 入口、0x1410a 寫 HP、0x19087 返回。"
              "0x14 / 0x18 分支:0x20c6f、0x20f80 / 0x20f85(play_map_effect_animation)、0x1c640(每幀)、0x20f9b / 0x20fa0(flash)、"
              "0x1cd8e(每幀)、0x1c75e / 0x1c7ed / 0x1c7fe / 0x1c816 / 0x1c81f / 0x1c87f / 0x1c897 / 0x20fd0(傷害)、0x20fae / 0x20fdb(跳字)、"
              "0x20fe5、0x1dfd7(action_finish_effect 每幀)、0x20ff4、0x21062 / 0x21067 / 0x21072 / 0x2107a、0x152f5、0x152fd。"
              "分支斷點在 ai_item_action 入口停下之後才設,避免別的動作也停。每幀傾印線性 0xa0000 起 64000 bytes。",
    "runs": [],
    "analysis": {"script": "an124.py(暫存)", "checks": len(real), "pass": sum(bool(r["ok"]) for r in real),
                 "controls": len(ctl), "controls_fail_as_expected": sum(r["ok"] is False for r in ctl),
                 "controls_not_applicable": sum(r["ok"] is None for r in ctl), "items": res},
    "mutation": {"script": "mut_an124.py(暫存)", "stdout": mut.stdout.strip().splitlines()},
    "files": {},
}
for tag in an124.RUNS:
    st = json.loads((D / f"{tag}.json").read_text(encoding="utf-8"))["stops"]
    dumps = sorted(p.stem for p in D.glob(f"{tag}_*.bin") if p.stat().st_size == 64000)
    out["runs"].append({"tag": tag, "what": WHAT[tag], "stops": [trim(s) for s in st],
                        "vga_dump_md5": {n: hashlib.md5((D / f"{n}.bin").read_bytes()).hexdigest() for n in dumps}})

# 結論釘住:全部檢查通過、對照全部有效或不適用(沒有對照判成 PASS)、9 個突變全部抓到
a = out["analysis"]
assert a["pass"] == a["checks"] and a["controls_fail_as_expected"] + a["controls_not_applicable"] == a["controls"], a
assert (a["checks"], a["controls"], a["controls_not_applicable"]) == (44, 26, 3), a
assert out["mutation"]["stdout"][-1] == "突變 9 漏掉 0" and sum(x.startswith("抓到") for x in out["mutation"]["stdout"]) == 9

# 已提交的 PNG:對照圖由傾印重畫後畫面區逐像素相同
FILES = {"r1": "item_effect_dispatch_item79_branch_hit_20261014.png", "r2": "item_effect_dispatch_item79_branch_miss_20261014.png"}
for tag, dst in FILES.items():
    assert sheet_tiles_match(tag, Image.open(EVIDENCE / dst).convert("RGB")), dst
out["files"] = {dst: hashlib.md5((EVIDENCE / dst).read_bytes()).hexdigest() for dst in FILES.values()}


def write() -> None:
    js = (json.dumps(out, ensure_ascii=False, indent=1) + "\n").encode("utf-8")
    assert b"\r" not in js
    OUT.write_bytes(js)
    print("ok", OUT.name, len(js))


if __name__ == "__main__":
    write()
