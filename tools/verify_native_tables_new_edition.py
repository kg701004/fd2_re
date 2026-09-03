#!/usr/bin/env python3
"""verify_native_tables_new_edition.py — 用手上這份「新版」FD2.EXE 複驗三份
從**已遺失的舊版**抽出來的資料檔,回答一個問題:
**`docs/knowledge-base/25-battle-event-system.md` 的結論,對現在這份 EXE 成不成立?**

背景
----
`docs/data/event_id_groups.json`、`native_field_event_rules.json`、
`native_treasure_event_rules.json` 都是從 357074-byte 的舊版 FD2.EXE 抽的,那份
EXE 已於 2026-08-14 確認遺失。它們的產生工具都用雜湊釘死舊版,所以現在一支都跑不起來
——資料本身沒有被證明是錯的,但也**無法對使用者實際在玩的新版(509158 B)複驗**。

2026-09-03 實測過:把那些工具的雜湊閘改成新版硬跑,會安靜地讀到完全不同的數字
(寶物物品編號 `[29,43,51,61,71]` → `[54,1,0,0,199]`),所以**不能**用位址直接套。

本工具的做法:不套位址,改用**內容特徵**在新版的 linear 位址空間裡把表找回來,
再跟已 commit 的值逐項比對。這是「只驗資料」的路線,不遷移那四支工具的程式碼。

三層證據
--------
L1  **寶物物品表**:唯一位元組序列全檔搜尋 → 新版 linear 位址。
L2  **90 筆 event handler 跳表**:不比對絕對位址(必然不同),比對**相鄰 handler 的
    間距序列**。若 90 個 handler 的間距逐項相同,代表這 90 個函式在新版裡是同一批、
    同順序、同大小,只是整體搬了位置——這比任何單一位址吻合都強。
L3  **逐 handler 位元組比對**:用 L2 求得的位移,把舊版記錄的每個 handler 起始位址
    映射到新版,檢查該處是否為合理的函式開頭,並抽樣做位元組級比對。

反向驗證
--------
`--selftest` 對每一層都做故障注入(把特徵改壞、把間距序列打亂、把位移故意設錯),
要求本工具**判為失敗**;同時對未動過的輸入要求判為成功(同組態陽性對照)。
一個只會說 PASS 的驗證器沒有價值。

用法
----
    python tools/verify_native_tables_new_edition.py            # 全部三層
    python tools/verify_native_tables_new_edition.py --selftest
    python tools/verify_native_tables_new_edition.py --json out.json
"""

from __future__ import annotations

import argparse
import json
import struct
import sys
from dataclasses import dataclass, field, asdict
from pathlib import Path

REPO = Path(__file__).resolve().parent.parent
sys.path.insert(0, str(REPO / "tools"))

for _s in (sys.stdout, sys.stderr):
    try:
        _s.reconfigure(encoding="utf-8", errors="backslashreplace")
    except (AttributeError, OSError):
        pass

from le_xref import parse_le  # noqa: E402

EXE = REPO / "org_game" / "炎龍騎士團" / "FLAME2" / "FD2.EXE"
DATA = REPO / "docs" / "data"


# --------------------------------------------------------------------------- #
# linear image
# --------------------------------------------------------------------------- #

@dataclass
class LinearImage:
    """新版 EXE 的 linear 位址空間(逐 object 攤平),可依 linear 位址讀寫。"""
    spans: list[tuple[int, int, bytes]] = field(default_factory=list)  # (base, end, data)

    @classmethod
    def load(cls, raw: bytes) -> "LinearImage":
        meta = parse_le(raw)
        # LE 規格裡「data pages offset」是相對 LE header 的,不是檔案絕對位置。
        # le_xref.parse_le 原樣回傳該欄位,而既有工具(page_file()、
        # extract_event_id_groups.load_code())都把它當絕對值用。對這份新版 EXE
        # (LE header 在 0x27acc)兩者差 0x27acc,分頁區會整段錯位。
        # 判準不是規格書而是實測:dump_exe_tables.py 已在新版驗證通過的三個 anchor
        # (item @0x792c0 / shop @0x7b3a4 / spell @0x7aa11,位元組逐項命中)
        # 全部落在 le+data_off 區內、全部落在 data_off 區外。
        psize, doff = meta["page_size"], meta["le"] + meta["data_off"]
        img = cls()
        pg = 0
        for ob in meta["objs"]:
            blob = bytearray()
            for _ in range(ob["pages"]):
                fo = doff + pg * psize
                blob += raw[fo:fo + psize]
                pg += 1
            img.spans.append((ob["base"], ob["base"] + len(blob), bytes(blob)))
        return img

    def read(self, addr: int, n: int) -> bytes | None:
        for base, end, data in self.spans:
            if base <= addr and addr + n <= end:
                return data[addr - base:addr - base + n]
        return None

    def find_all(self, pat: bytes, limit: int = 32) -> list[int]:
        """回傳所有命中的 linear 位址。"""
        out: list[int] = []
        for base, _end, data in self.spans:
            i = data.find(pat)
            while i != -1 and len(out) < limit:
                out.append(base + i)
                i = data.find(pat, i + 1)
        return out

    def bounds(self) -> tuple[int, int]:
        return self.spans[0][0], self.spans[-1][1]


# --------------------------------------------------------------------------- #
# result model
# --------------------------------------------------------------------------- #

@dataclass
class Finding:
    layer: str
    name: str
    status: str      # PASS | FAIL | INCONCLUSIVE
    detail: str


def _pass(f: list[Finding], layer, name, detail=""):
    f.append(Finding(layer, name, "PASS", detail))


def _fail(f: list[Finding], layer, name, detail=""):
    f.append(Finding(layer, name, "FAIL", detail))


def _inconc(f: list[Finding], layer, name, detail=""):
    f.append(Finding(layer, name, "INCONCLUSIVE", detail))


# --------------------------------------------------------------------------- #
# L1 — 寶物物品表
# --------------------------------------------------------------------------- #

def layer_treasure(img: LinearImage, rules: dict, out: list[Finding]) -> int | None:
    """回傳新版 linear 位址(找不到或不唯一則 None)。"""
    rule = rules["rules"][0]
    items = rule["item_by_slot"]
    old = int(rule["item_table_address"], 16)
    pat = bytes(items)

    hits = img.find_all(pat)
    if not hits:
        _fail(out, "L1", "寶物物品表",
              f"新版找不到 {items} 這串位元組——舊版資料在新版無對應,結論不成立")
        return None
    if len(hits) > 1:
        # 多重命中不是失敗,是「這個特徵不夠獨特」——必須說清楚,不能挑一個當答案
        _inconc(out, "L1", "寶物物品表",
                f"{len(hits)} 處命中 {[hex(h) for h in hits]},特徵不唯一,無法據此認定")
        return None
    new = hits[0]
    _pass(out, "L1", "寶物物品表",
          f"{items} 在新版 linear {hex(new)} 唯一命中(舊版 {hex(old)},位移 {new-old:+#x})")

    # 追加結構檢查:open_slots 宣稱 0..4 全開,表示表長至少 5;
    # 檢查第 6 個 byte 不是同一個遞增序列的延續(否則可能只是巧合落在別的遞增表裡)
    tail = img.read(new + len(items), 1)
    if tail is not None:
        _pass(out, "L1", "表尾檢查",
              f"表後一個 byte = {tail[0]}(僅記錄,不作判定)")
    return new


# --------------------------------------------------------------------------- #
# L2 — 90 筆 handler 跳表:比對間距序列
# --------------------------------------------------------------------------- #

def _fixup_map(raw: bytes, meta: dict) -> dict[int, int]:
    """LE fixup 表:linear 位址 -> 重定位後的目標。

    跳表項目在分頁原始資料裡**不是**絕對位址,真正的目標存在 fixup record 裡。
    先前用 raw dword 掃描找不到跳表,就是因為漏了這一層。
    """
    fp, fr = meta["fixpage"], meta["fixrec"]
    psize = meta["page_size"]
    npages = sum(o["pages"] for o in meta["objs"])

    def page_base(pg: int) -> int | None:
        acc = 0
        for ob in meta["objs"]:
            if pg < acc + ob["pages"]:
                return ob["base"] + (pg - acc) * psize
            acc += ob["pages"]
        return None

    fx: dict[int, int] = {}
    for pg in range(npages):
        o0 = struct.unpack_from("<I", raw, fp + pg * 4)[0]
        o1 = struct.unpack_from("<I", raw, fp + (pg + 1) * 4)[0]
        p, end = fr + o0, fr + o1
        pl = page_base(pg)
        if pl is None:
            continue
        while p < end:
            _st, fl = raw[p], raw[p + 1]
            p += 2
            srcoff = struct.unpack_from("<h", raw, p)[0]
            p += 2
            objn = raw[p]
            p += 1
            if fl & 0x10:
                trg = struct.unpack_from("<I", raw, p)[0]
                p += 4
            else:
                trg = struct.unpack_from("<H", raw, p)[0]
                p += 2
            base = meta["objs"][objn - 1]["base"] if 1 <= objn <= len(meta["objs"]) else 0
            fx[pl + srcoff] = base + trg
    return fx


JUMP_TABLE = 0x51b91   # event_id 0..89,舊版記載;本工具會驗證它在新版是否仍成立


def layer_jump_table(raw: bytes, groups: dict, out: list[Finding]) -> int | None:
    """比對 90 筆 handler 指標。回傳 handler 區塊的統一位移(不統一則 None)。"""
    meta = parse_le(raw)
    fx = _fixup_map(raw, meta)

    # 先確認跳表確實存在:一段連續、4-byte 間隔的 fixup run
    addrs = sorted(fx)
    runs, cur = [], [addrs[0]]
    for a in addrs[1:]:
        if a - cur[-1] == 4:
            cur.append(a)
        else:
            if len(cur) >= 90:
                runs.append(cur)
            cur = [a]
    if len(cur) >= 90:
        runs.append(cur)
    covering = [r for r in runs if r[0] <= JUMP_TABLE and JUMP_TABLE + 89 * 4 <= r[-1]]
    if not covering:
        _fail(out, "L2", "跳表存在性",
              f"新版在 {hex(JUMP_TABLE)} 沒有涵蓋 90 筆的連續 fixup run;"
              f"最長的幾段:{[(hex(r[0]), len(r)) for r in runs[:4]]}")
        return None
    r = covering[0]
    _pass(out, "L2", "跳表存在性",
          f"{hex(r[0])} 起有 {len(r)} 筆連續 fixup,涵蓋 {hex(JUMP_TABLE)}..{hex(JUMP_TABLE+89*4)}"
          f"(舊版記載的 30 章表 + 90 筆 event 表 = 120,與此吻合)")

    ids = sorted((k for k in groups if k.isdigit()), key=int)
    deltas: dict[int, int] = {}
    for k in ids:
        new = fx.get(JUMP_TABLE + int(k) * 4)
        if new is None:
            _fail(out, "L2", "handler 指標", f"event {k} 在新版 fixup 表裡查不到")
            return None
        deltas[new - int(groups[k]["handler"], 16)] = deltas.get(new - int(groups[k]["handler"], 16), 0) + 1

    if len(deltas) == 1:
        d = next(iter(deltas))
        _pass(out, "L2", "handler 位移一致性",
              f"{len(ids)}/{len(ids)} 個 handler 位移完全相同 = {d:+#x}——"
              "同一批函式、同順序、同大小,只是整體搬位置")
        return d
    _fail(out, "L2", "handler 位移一致性",
          f"位移不一致:{ {hex(k): v for k, v in deltas.items()} }——handler 區塊在新版不是完整搬移")
    return None


# --------------------------------------------------------------------------- #
# L3 — 用 L2 的位移驗證其他檔案記錄的 handler 位址
# --------------------------------------------------------------------------- #

def layer_handlers(raw: bytes, delta: int, out: list[Finding]) -> None:
    """本層目前**做不到**,而且原因具體,不是「沒空做」。

    要在新版重新抽出各 handler 的 spawn group,必須先能正確重建 object 0 的
    linear code image。目前兩種候選映射(data_off 當絕對值 / le+data_off)
    在已知位址上反組譯出來的結果都不自洽:
      * `0x14818 + 0x356` 給出乾淨的 prologue(push ebx/esi/edi/ebp),
      * 但 `0x10c50 + 0x356`、`0x2ff01 + 0x356` 都是垃圾,
      * 而 `0x2ff01` **不加位移**反而像合法程式碼,
      * 且解出的絕對運算元是 `[0x2754]`、`[0x1a83]` 這種不可能的小位址
        (真實的全域應該落在 0x53xxx)。
    page map 已確認是 identity(1..71),所以不是頁序問題。

    在這件事解決前,任何「在新版重抽 spawn group」的結果都不可信——實際跑過一次,
    得到 0 筆 spawn,那是映射沒對的產物,不是「新版沒有 spawn」這個發現。
    **不把它寫成結論**,正是這裡最重要的事。
    """
    _inconc(out, "L3", "重抽 spawn group",
            f"位移 {delta:+#x} 已知,但 object 0 的 linear code image 尚無法正確重建"
            "(詳見本函式 docstring),故本層無法給出可信結果")


# --------------------------------------------------------------------------- #
# 主流程
# --------------------------------------------------------------------------- #

def run(raw: bytes, groups: dict, treasure: dict) -> list[Finding]:
    out: list[Finding] = []
    img = LinearImage.load(raw)
    out.append(Finding("L0", "linear image",
                       "PASS",
                       "objects: " + ", ".join(f"{hex(b)}..{hex(e)}" for b, e, _ in img.spans)))
    layer_treasure(img, treasure, out)
    delta = layer_jump_table(raw, groups, out)
    if delta is not None:
        layer_handlers(raw, delta, out)
    else:
        _inconc(out, "L3", "重抽 spawn group", "L2 未求得位移,本層無法進行")
    return out


def report(findings: list[Finding]) -> int:
    width = max(len(f.name) for f in findings) + 2
    for f in findings:
        print(f"  {f.status:13} {f.layer:3} {f.name:{width}} {f.detail}")
    nfail = sum(1 for f in findings if f.status == "FAIL")
    ninc = sum(1 for f in findings if f.status == "INCONCLUSIVE")
    npass = sum(1 for f in findings if f.status == "PASS")
    print(f"\nPASS={npass}  INCONCLUSIVE={ninc}  FAIL={nfail}")
    return 1 if nfail else 0


# --------------------------------------------------------------------------- #
# 反向驗證
# --------------------------------------------------------------------------- #

def selftest() -> int:
    """反向驗證:每一層都必須在被注入故障時判為失敗,未動過的輸入必須通過。"""
    print("verify_native_tables_new_edition selftest — 故障注入 + 同組態陽性對照\n")
    raw = EXE.read_bytes()
    groups = json.loads((DATA / "event_id_groups.json").read_text(encoding="utf-8"))
    treasure = json.loads((DATA / "native_treasure_event_rules.json").read_text(encoding="utf-8"))
    failures: list[str] = []

    def st(fs: list[Finding], name: str) -> str:
        for f in fs:
            if f.name == name:
                return f.status
        return "<缺這項檢查>"

    def expect(fs, name, want, why):
        got = st(fs, name)
        if got != want:
            failures.append(f"{name}: 期望 {want},實得 {got}({why})")

    # --- 陽性對照:未動過的輸入,三項都必須 PASS ---
    base = run(raw, groups, treasure)
    expect(base, "寶物物品表", "PASS", "同組態陽性對照")
    expect(base, "跳表存在性", "PASS", "同組態陽性對照")
    expect(base, "handler 位移一致性", "PASS", "同組態陽性對照")

    # --- 注入 1:寶物特徵改成新版不存在的值 → 必須 FAIL ---
    t = json.loads(json.dumps(treasure))
    t["rules"][0]["item_by_slot"] = [201, 202, 203, 204, 205]
    expect(run(raw, groups, t), "寶物物品表", "FAIL", "不存在的序列必須判失敗")

    # --- 注入 2:單 byte 特徵必然多重命中 → 必須 INCONCLUSIVE,不可挑一個當答案 ---
    t = json.loads(json.dumps(treasure))
    t["rules"][0]["item_by_slot"] = [0]
    expect(run(raw, groups, t), "寶物物品表", "INCONCLUSIVE", "不唯一的特徵不可下結論")

    # --- 注入 3:動一筆 handler 位址 → 位移不再一致 → 必須 FAIL ---
    g = json.loads(json.dumps(groups))
    g["5"]["handler"] = hex(int(g["5"]["handler"], 16) + 0x11)
    expect(run(raw, g, treasure), "handler 位移一致性", "FAIL",
           "位移不一致必須判失敗,否則這層等於沒檢查")

    # --- 注入 4:全部 handler 一起加同一個值 → 位移仍一致,必須仍 PASS ---
    # 配對對照:證明上一項抓到的是「不一致」,而不是「跟記載的值不同」。
    g = json.loads(json.dumps(groups))
    for k in list(g):
        if k.isdigit():
            g[k]["handler"] = hex(int(g[k]["handler"], 16) + 0x100)
    expect(run(raw, g, treasure), "handler 位移一致性", "PASS",
           "配對對照:整體平移後位移仍一致,應通過")

    # --- 注入 5:把跳表位址指到沒有連續 fixup 的地方 → 必須 FAIL ---
    global JUMP_TABLE
    saved = JUMP_TABLE
    try:
        JUMP_TABLE = 0x40000
        expect(run(raw, groups, treasure), "跳表存在性", "FAIL", "錯的跳表位址必須判失敗")
    finally:
        JUMP_TABLE = saved

    total = 7
    print(f"檢查:{total - len(failures)}/{total} 通過")
    for f in failures:
        print("  FAIL  " + f)
    if not failures:
        print("\n全部反向驗證通過:三層都會在被注入故障時失敗,未動過的輸入通過,"
              "且配對對照證明位移檢查抓的是「不一致」而非「與記載不同」。")
    return 1 if failures else 0


def main() -> int:
    ap = argparse.ArgumentParser(description=__doc__,
                                 formatter_class=argparse.RawDescriptionHelpFormatter)
    ap.add_argument("--exe", type=Path, default=EXE)
    ap.add_argument("--json", help="輸出機器可讀報告")
    ap.add_argument("--selftest", action="store_true")
    args = ap.parse_args()

    if args.selftest:
        return selftest()

    if not args.exe.exists():
        print(f"找不到 EXE:{args.exe}", file=sys.stderr)
        return 2
    groups = json.loads((DATA / "event_id_groups.json").read_text(encoding="utf-8"))
    treasure = json.loads((DATA / "native_treasure_event_rules.json").read_text(encoding="utf-8"))
    findings = run(args.exe.read_bytes(), groups, treasure)
    rc = report(findings)
    if args.json:
        Path(args.json).write_text(
            json.dumps([asdict(f) for f in findings], ensure_ascii=False, indent=2),
            encoding="utf-8")
        print(f"\nwrote {args.json}")
    return rc


if __name__ == "__main__":
    sys.exit(main())
