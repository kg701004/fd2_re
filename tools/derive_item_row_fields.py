#!/usr/bin/env python3
"""fd2_re — 機械解出 `0x602ad` 道具效果列的欄位配置與消費端對照。

為什麼需要這支
--------------
worklist 1354 的殘留是「`0x602ad` table 真正邊界與未命名欄位語意」。邊界已於
2026-09-10 由兩個獨立方向定出(215 列);**欄位**這一半先前只知道 5 個
(`+0x00` type、`+0x0b`/`+0x0c` 傳給 `0x14818` 的兩個槽、`+0x0d` AI 過濾、
`+0x10` 效果型態),其餘記為「未命名」。

本工具用兩條互相獨立的機制把它補完,兩條都不靠人工判讀:

  A. **消費端掃描** — 全 image 找 `0x4e8bc`(列定址器 = `0x602ad + id*0x17`)的
     呼叫端,追蹤其回傳值流向的暫存器,收集 stride 內(`< 0x17`)的欄位讀取。
     這回答「哪些偏移真的被讀」。
  B. **跨產物欄位對映** — 把 `item.json`(獨立產出的 normalized 視圖)的每個純量
     欄位,對 effect_row 的每個 u8/u16 偏移做**全 215 列相符**的窮舉比對。
     這回答「哪個偏移是哪個欄位」。

判準是 215/215,不是「大致吻合」
--------------------------------
`ap` 一度得到 **191/215**。沒有採信——去看那 24 筆,全是 `ap > 255` 的道具,
高位元組落在 `+0x02`;改判為 u16 之後 215/215。這也順帶解釋了 `+0x02` 的值分佈
(`0×191, 1×24`,191+24=215)。**「大致吻合」不是對映**,這條門檻寫進 selftest 的
負向控制:把門檻放寬到 `>=85%`(u8 的實際符合率是 191/215 = 88.8%)時,`ap` 必須被對到錯誤的偏移。

兩個產出的獨立性
----------------
`item.json` 與 `native_item_effect_rows.json` 都由 `dump_exe_tables.py` 產生,但
**視圖不同且相差一個 byte**(前者自 record 起、後者自 record+1 起),欄位是各自
獨立解析的;`effect_row[0] == item.type` 在 215/215 成立正是這個位移關係的證據,
而不是自我比對。

用法
----
    python tools/derive_item_row_fields.py --json docs/data/item_row_field_consumers.json
    python tools/derive_item_row_fields.py --selftest
"""
from __future__ import annotations

import argparse
import json
import re
import struct
import sys
from pathlib import Path

sys.path.insert(0, str(Path(__file__).resolve().parent))

if hasattr(sys.stdout, "reconfigure"):
    sys.stdout.reconfigure(encoding="utf-8")
    sys.stderr.reconfigure(encoding="utf-8")

ROOT = Path(__file__).resolve().parent.parent
DEFAULT_EXE = ROOT / "org_game" / "炎龍騎士團" / "FLAME2" / "FD2.EXE"
ROW_ACCESSOR = 0x4E8BC        # 0x602ad + id*0x17,見 worklist 1354
STRIDE = 0x17
ROWS_JSON = ROOT / "docs" / "data" / "exe_tables" / "native_item_effect_rows.json"
ITEMS_JSON = ROOT / "docs" / "data" / "exe_tables" / "item.json"

# 已由**消費端反組譯**確立語意的偏移(不是本工具推的,各自附出處)。
CONSUMER_SEMANTICS = {
    0x0B: "Attack ring 路徑傳給 0x14818 的 radius 槽(worklist 1118 已否證『通用射程』解讀)",
    0x0C: "同上,mode 槽",
    0x0D: "AI 道具評分掃描的唯一過濾欄位,為 0 即跳過(worklist 541)",
    0x10: "效果型態;AI 側 >0xf 會被夾成 1(值域實測 {0,1,2,3,4,31})",
}


def load_tables():
    rows = [bytes.fromhex(r["raw"])
            for r in json.loads(ROWS_JSON.read_text(encoding="utf-8"))]
    items = json.loads(ITEMS_JSON.read_text(encoding="utf-8"))
    return rows, items


def scalar_fields(items):
    """item.json 裡可比對的純量欄位(含把 range 拆成兩個)。"""
    out = {}
    for k, v in items[0].items():
        if isinstance(v, int) and k != "id":
            out[k] = lambda it, k=k: it.get(k)
    if isinstance(items[0].get("range"), list):
        out["range_min"] = lambda it: it["range"][0]
        out["range_max"] = lambda it: it["range"][1]
    if isinstance(items[0].get("K"), list):
        for i in range(len(items[0]["K"])):
            out[f"K[{i}]"] = lambda it, i=i: it["K"][i]
    return out


def map_fields(rows, items, threshold: float = 1.0):
    """欄位 -> [符合的偏移描述]。`threshold` 只給 selftest 的負向控制用。"""
    need = len(items) * threshold
    out: dict[str, list[str]] = {}
    for name, get in scalar_fields(items).items():
        hits = []
        for off in range(STRIDE):
            if sum(1 for it in items if get(it) == rows[it["id"]][off]) >= need:
                hits.append(f"u8 @+{off:#04x}")
            if off <= STRIDE - 2 and sum(
                    1 for it in items
                    if get(it) == struct.unpack_from("<H", rows[it["id"]], off)[0]) >= need:
                hits.append(f"u16 @+{off:#04x}")
        out[name] = hits
    return out


def consumer_map(exe: str):
    """偏移 -> 讀它的呼叫端清單。只掃呼叫端之後、下一個 call 之前的線性區段。"""
    from callgraph_le import CG
    cg = CG(exe)
    code, base = cg.code, cg.base
    sites = [base + i for i in range(len(code) - 5)
             if code[i] == 0xE8 and
             base + i + 5 + struct.unpack_from("<i", code, i + 1)[0] == ROW_ACCESSOR]
    found: dict[int, set[str]] = {}
    for s in sites:
        holders = {"eax"}
        for ins in cg.md.disasm(code[s - base:s - base + 120], s):
            if ins.address == s:
                continue
            parts = [p.strip() for p in ins.op_str.split(",")]
            if (ins.mnemonic == "mov" and len(parts) == 2
                    and parts[1] == "eax" and parts[0].isalpha()):
                holders.add(parts[0])
            if ins.mnemonic == "call":
                break
            for r in holders:
                for m in re.finditer(rf"\[{r}(?: \+ (0x[0-9a-f]+))?\]", ins.op_str):
                    off = int(m.group(1), 16) if m.group(1) else 0
                    if off < STRIDE:
                        found.setdefault(off, set()).add(hex(s))
    return sites, found


def mirrored_offsets(rows):
    """在全部列上值完全相等的偏移對——鏡像欄位的機械偵測。"""
    out = []
    for a in range(STRIDE):
        for b in range(a + 1, STRIDE):
            if all(r[a] == r[b] for r in rows):
                out.append((a, b))
    return out


def constant_offsets(rows):
    return [o for o in range(STRIDE) if len({r[o] for r in rows}) == 1]


def build(exe: str) -> dict:
    rows, items = load_tables()
    sites, found = consumer_map(exe)
    fields = map_fields(rows, items)
    named = {}
    for name, hits in fields.items():
        for h in hits:
            off = int(h.split("+")[1], 16)
            named.setdefault(off, []).append(f"{name} ({h.split(' ')[0]})")
    # u16 欄位的高位元組會落在下一個偏移上。不標出來的話,它們在配置表裡看起來
    # 像「未命名」——那是把**已知欄位的續接位元組**誤報成未知,和「缺列被當成
    # 沒問題」是同一種錯。
    continuation = {}
    for name, hits in fields.items():
        for h in hits:
            if h.startswith("u16"):
                continuation[int(h.split("+")[1], 16) + 1] = name
    layout = {}
    for off in range(STRIDE):
        bits = []
        if off in named:
            bits.append(" / ".join(named[off]))
        elif off in continuation:
            bits.append(f"**{continuation[off]} 的高位元組**(u16 @+{off - 1:#04x} 的續接)")
        if off in CONSUMER_SEMANTICS:
            bits.append(CONSUMER_SEMANTICS[off])
        if off in constant_offsets(rows):
            bits.append(f"全 {len(rows)} 列恆為 {rows[0][off]}")
        layout[f"+{off:#04x}"] = "; ".join(bits) if bits else "**未命名**"
    return {
        "_source": __doc__.strip().splitlines()[0],
        "_generator": "tools/derive_item_row_fields.py",
        "_base": hex(0x602AD), "_stride": hex(STRIDE), "_rows": len(rows),
        "_accessor": hex(ROW_ACCESSOR), "_call_sites": len(sites),
        "_threshold": "欄位對映一律要求全部列相符;191/215 那種『大致吻合』不採信",
        "layout": layout,
        "field_matches": fields,
        "consumers": {f"+{o:#04x}": sorted(v) for o, v in sorted(found.items())},
        # 全零欄位彼此當然「相等」,那是平凡的。把它們分開,否則讀者會把三組
        # 平凡鏡像和唯一一組實質鏡像(+0x11/+0x15)一起當成發現。
        "mirrored_pairs_nontrivial": [
            f"+{a:#04x} == +{b:#04x}(全 {len(rows)} 列相等,且兩者皆非常數欄位)"
            for a, b in mirrored_offsets(rows)
            if a not in constant_offsets(rows) and b not in constant_offsets(rows)],
        "mirrored_pairs_trivial_constant": [
            f"+{a:#04x} == +{b:#04x}(兩者皆為恆定欄位,相等是平凡的)"
            for a, b in mirrored_offsets(rows)
            if a in constant_offsets(rows) and b in constant_offsets(rows)],
    }


def selftest() -> int:
    fails = []
    rows, items = load_tables()

    print("(1) 列數與 stride 必須與已定出的邊界一致")
    ok1 = len(rows) == 215 and STRIDE == 0x17
    print(f"    {'PASS' if ok1 else 'FAIL'}: {len(rows)} 列 / stride {STRIDE:#x}")
    if not ok1:
        fails.append(f"列數或 stride 變了:{len(rows)}/{STRIDE:#x}")

    print("\n(2) 跨產物對映:每個 item.json 欄位都要對到偏移,且 type 必須是 +0x00")
    fields = map_fields(rows, items)
    unmatched = [k for k, v in fields.items() if not v]
    ok2 = not unmatched and any(h.endswith("+0x00") for h in fields.get("type", []))
    print(f"    {'PASS' if ok2 else 'FAIL'}: 對不到偏移的欄位 {unmatched or '無'};"
          f"type -> {fields.get('type')}")
    if not ok2:
        fails.append(f"跨產物對映不成立:{unmatched}")

    print("\n(3) 門檻是 215/215:`ap` 必須是 u16,u8 版本必須**對不上**")
    ap = fields.get("ap", [])
    ok3 = ap == ["u16 @+0x01"]
    print(f"    {'PASS' if ok3 else 'FAIL'}: ap -> {ap}(應只有 u16 @+0x01)")
    if not ok3:
        fails.append(f"ap 的寬度判定錯誤:{ap}")

    print("\n(4) 負向控制:把門檻放寬到 85%,`ap` 就會多對上錯誤的 u8 偏移")
    # 85% 不是隨手挑的:u8 @+0x01 的實際符合率是 191/215 = 88.8%,所以控制必須設在
    # 它之下。第一版設 90%,這一題不會觸發——那樣的控制看起來有寫、實際上是空的,
    # 正是本專案一再記錄的「裝飾性檢查」。
    loose = map_fields(rows, items, threshold=0.85)["ap"]
    ok4 = "u8 @+0x01" in loose and "u8 @+0x01" not in ap
    print(f"    {'PASS' if ok4 else 'FAIL'}: 放寬後 ap -> {loose}")
    if not ok4:
        fails.append(f"放寬門檻沒有造成誤配,(3) 因此是平凡的:{loose}")

    print("\n(5) 鏡像與常數欄位的機械偵測必須非空且可解釋")
    mir, const = mirrored_offsets(rows), constant_offsets(rows)
    ok5 = (0x11, 0x15) in mir and 0x16 in const
    print(f"    {'PASS' if ok5 else 'FAIL'}: 鏡像對 {[(hex(a), hex(b)) for a, b in mir]};"
          f"恆定偏移 {[hex(c) for c in const]}")
    if not ok5:
        fails.append(f"鏡像/常數偵測不符預期:{mir} / {const}")

    if fails:
        print("\nSELFTEST FAILED:")
        for f in fails:
            print("  -", f)
        return 1
    print("\n--selftest passed(邊界一致 + 跨產物全列對映 + 寬度判定 + "
          "放寬門檻的負向控制 + 鏡像/常數偵測)。")
    return 0


def main() -> int:
    ap = argparse.ArgumentParser(description=__doc__,
                                 formatter_class=argparse.RawDescriptionHelpFormatter)
    ap.add_argument("--exe", default=str(DEFAULT_EXE))
    ap.add_argument("--json")
    ap.add_argument("--selftest", action="store_true")
    a = ap.parse_args()
    if a.selftest:
        return selftest()
    data = build(a.exe)
    text = json.dumps(data, ensure_ascii=False, indent=1) + "\n"
    if a.json:
        Path(a.json).write_text(text, encoding="utf-8")
        print(f"-> {a.json}")
    else:
        print(text)
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
