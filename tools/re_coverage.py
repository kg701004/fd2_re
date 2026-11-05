#!/usr/bin/env python3
"""re_coverage.py —— 規格層逆向覆蓋率:三層固定分母,每一筆「已解析」都要拿得出可機器核對的證據。

為什麼有這支
------------
2026-11-05 使用者把目標定為「100% 逆向完成」(先規格層,之後再決定要不要做可重編譯原始碼)。
當時量得出來的只有函式清單(1356 / 1356 有名稱);資料區只有「位址字面上出現在文件裡」的
435 / 900(會把結構內欄位算成沒寫到,偏低),資源檔則完全沒有逐筆紀錄。沒有固定分母就
沒辦法說「還差多少」,這支工具補的就是分母與核對。

三層分母(全部由原版檔案現算,不讀任何「已完成」的自我宣稱)
------------------------------------------------------------
* 程式碼  `docs/data/function_inventory.json` 的 1356 個入口。
          遊戲函式(`function_names.json` 或 PRIM / DOC_OP_NAMES 有名稱)完成 = 它讀寫的每個全域位址都落在已登錄的資料區段;
          函式庫(AIL / Watcom 比對)完成 = 已辨識(第三方程式碼,辨識出來就夠)。
* 資料區  FD2.EXE 的 LE obj2、obj3(obj1 是程式碼)每一個 byte;另計程式碼引用的全域位址有幾個落在已登錄區段。
          登錄在 `docs/data/data_map.json`:區段不得重疊、不得跨出物件,每段至少一筆證據。
* 資源    (a) 遊戲目錄裡每一個原版檔案(大寫 8.3 檔名;玩家或分析留下的 png / md / py 不算);
          (b) 11 個 `.DAT` 容器裡的每一筆資源(`unpack_dat.parse_directory` 現算,1005 筆)。
          登錄在 `docs/data/resource_map.json`;資源以 sha1 釘住位元組,格式要通過本工具的 probe 才算「格式已驗」。

證據種類(每一種都會被核對,不是註記)
--------------------------------------
* `{"func": "0x....", "ref": "0x...."}`  函式必須在 inventory 裡;用於資料區段時,`ref`(省略則取任一個)必須是該函式
                                          實際引用的全域位址,而且省略 `ref` 時要落在區段內。
* `{"doc": "相對路徑", "quote": "..."}`   檔案必須在倉庫內且逐字含有 quote。
* `{"no_refs": true}`                     只用於資料區段:沒有任何函式引用、也沒有任何 fixup 指向區段內(例如對齊填充)。

資料區段的大小也會被核對(不是只看證據)
----------------------------------------
* 指令層存取:obj1 每個 fixup 對回所在指令的運算元(capstone),得到寬度與讀寫;線性掃描得到的指令起點
  還要在「從每個函式入口各自反組譯」的結果裡出現才採信。直接定址的存取 [目標, 目標+寬度) 碰到區段就必須
  整段落在那一段內 —— 大小登錄錯(3 byte 的 dword、吞進下一個 dword 的一半)會被抓。
* fields:區段內除了起點,每個被程式碼引用的位址都要在 `fields`({"0x偏移": "名稱"})有名稱 ——
  一段吞掉好幾個變數卻不說明會被抓。

格式 probe(只收「會說不」的檢查;沒有 probe 的格式只算「已宣稱」,不算已驗)
----------------------------------------------------------------------------
* `container`  巢狀 LLLLLL 容器,`unpack_dat.parse_directory` 必須接受。
* `empty`      長度 0。
新格式要先寫 probe、附一個會失敗的負向對照進 selftest,再拿來登錄。

用法
----
    python tools/re_coverage.py                    # 摘要(= --summary)
    python tools/re_coverage.py --check            # 登錄有任何錯誤就 exit 1(提交前閘門)
    python tools/re_coverage.py --gaps data --limit 30
    python tools/re_coverage.py --gaps globals | code | resources | files   # globals = 未登錄的被引用位址
    python tools/re_coverage.py --show-data 0x52397     # 該位址屬於哪個物件、哪些函式引用、登錄樣板
    python tools/re_coverage.py --show-resource TAI.DAT 4   # offset / 長度 / sha1 / 通過的 probe、登錄樣板
    python tools/re_coverage.py --selftest

遊戲目錄:`FD2_GAME_DIR`,否則 `org_game/炎龍騎士團/FLAME2`。FD2.EXE 與 `.DAT` 的 md5 必須與
`docs/data/fd2-reference-files.json` 相同,否則拒絕計算(別的版本的位址與資源編號不保證相同)。
"""
from __future__ import annotations

import argparse
import hashlib
import json
import os
import re
import struct
import sys
from pathlib import Path
from typing import Callable

if hasattr(sys.stdout, "reconfigure"):
    sys.stdout.reconfigure(encoding="utf-8")
    sys.stderr.reconfigure(encoding="utf-8")

ROOT = Path(__file__).resolve().parents[1]
sys.path.insert(0, str(ROOT / "tools"))

DATA_MAP = ROOT / "docs" / "data" / "data_map.json"
RESOURCE_MAP = ROOT / "docs" / "data" / "resource_map.json"
INVENTORY = ROOT / "docs" / "data" / "function_inventory.json"
REFERENCE_FILES = ROOT / "docs" / "data" / "fd2-reference-files.json"
DEFAULT_GAME = ROOT / "org_game" / "炎龍騎士團" / "FLAME2"

DATS = ("ANI.DAT", "BG.DAT", "DATO.DAT", "FDFIELD.DAT", "FDMUS.DAT", "FDOTHER.DAT",
        "FDSHAP.DAT", "FDTXT.DAT", "FIGANI.DAT", "TAI.DAT", "TITLE.DAT")
# 遊戲執行時會改寫的檔案:登錄時不釘 md5(fd2-reference-files.json 的 scope 也排除它們)
MUTABLE = frozenset({"FD2.SAV", "FD2.TMP"})
ORIGINAL_NAME = re.compile(r"^[A-Z0-9_]{1,8}\.[A-Z0-9]{1,3}$")
HEX_ADDR = re.compile(r"^0x[0-9a-f]+$")


# ---------------------------------------------------------------- 基本解析

def parse_addr(s: object) -> int:
    """`"0x52397"` -> int。只收小寫 0x 開頭的十六進位字串(與其他 docs/data 登錄一致)。

    Raises:
        ValueError: 不是這個格式。
    """
    if not isinstance(s, str) or not HEX_ADDR.match(s):
        raise ValueError(f"位址格式錯誤: {s!r}(要 0x 開頭的小寫十六進位字串)")
    return int(s, 16)


def nonempty_str(v: object) -> bool:
    return isinstance(v, str) and v.strip() != ""


# ---------------------------------------------------------------- 格式 probe

def probe_container(b: bytes) -> bool:
    import unpack_dat
    unpack_dat.parse_directory(b)   # 不是容器會丟 NotAContainer
    return True


def probe_empty(b: bytes) -> bool:
    return len(b) == 0


PROBES: dict[str, Callable[[bytes], bool]] = {"container": probe_container, "empty": probe_empty}


def probe_ok(fmt: str, b: bytes, probes: dict[str, Callable[[bytes], bool]]) -> bool | None:
    """True = probe 通過;False = probe 失敗(含丟例外);None = 這個格式沒有 probe。"""
    fn = probes.get(fmt)
    if fn is None:
        return None
    try:
        return fn(b) is True
    except Exception:
        return False


# ---------------------------------------------------------------- 證據核對

class Ctx:
    """核對時需要的外部事實:函式 -> 引用的全域位址、fixup 目標、讀文件、指令層存取。"""

    def __init__(self, funcs: dict[int, set[int]], fixup_targets: set[int],
                 read_doc: Callable[[str], str | None], accesses: tuple[Access, ...] = ()) -> None:
        self.funcs = funcs
        self.fixup_targets = fixup_targets
        self.read_doc = read_doc
        self.accesses = accesses


# ---------------------------------------------------------------- 指令層存取(區段大小的機器核對)

# (指令位址, 目標位址, 寬度 bytes, 讀寫 "r" / "w" / "rw" / "", 種類 "mem" / "addr", 有沒有 base / index 暫存器)
# "addr" = 只取位址(立即數、lea),沒有寬度。
Access = tuple[int, int, int, str, str, bool]


def decode_accesses(code: bytes, base: int, fx: dict[int, int],
                    anchors: set[int] | None = None) -> tuple[list[Access], list[int], list[int]]:
    """把 obj1 每個 fixup 對回它所在指令的運算元,得到存取寬度與讀寫。

    fixup 位置必須正好是記憶體運算元的 displacement(→ "mem")或立即數(→ "addr")的起點才算對上;
    對不上的(線性掃描錯位、跳表)放進 unresolved。anchors 是另一條解碼路徑(從每個函式入口反組譯)
    得到的指令起點:線性掃描得到、但 anchors 裡沒有的指令放進 unanchored,不參與大小核對。

    Returns:
        (accesses, unresolved fixup 位置, unanchored 指令位址)
    """
    from capstone import CS_AC_READ, CS_AC_WRITE, CS_ARCH_X86, CS_MODE_32, Cs
    from capstone.x86 import X86_OP_IMM, X86_OP_MEM
    import disasm_le

    md = Cs(CS_ARCH_X86, CS_MODE_32)
    md.detail = True
    out: list[Access] = []
    seen: set[int] = set()
    loose: list[int] = []
    for x in disasm_le.sweep_range(md, code, base, base, base + len(code)):
        if isinstance(x, tuple):
            continue
        for site in range(x.address, x.address + x.size):
            if site not in fx:
                continue
            off = site - x.address
            for op in x.operands:
                if op.type == X86_OP_MEM and x.disp_offset == off:
                    if x.mnemonic == "lea":
                        acc: Access = (x.address, fx[site], 0, "", "addr", False)
                    else:
                        rw = ("r" if op.access & CS_AC_READ else "") + ("w" if op.access & CS_AC_WRITE else "")
                        acc = (x.address, fx[site], op.size, rw, "mem", bool(op.mem.base or op.mem.index))
                elif op.type == X86_OP_IMM and x.imm_offset == off:
                    acc = (x.address, fx[site], 0, "", "addr", False)
                else:
                    continue
                out.append(acc)
                seen.add(site)
                if anchors is not None and x.address not in anchors:
                    loose.append(x.address)
                break
    return out, sorted(set(fx) - seen), sorted(set(loose))


def access_errors(spans: list[list], accesses: tuple[Access, ...] | list[Access]) -> list[str]:
    """直接定址(沒有 base / index)的存取 [目標, 目標+寬度) 碰到任何區段,就必須整段落在那一個區段內。

    違反的區段在 spans 裡標成不成立(spans 元素是 [start, end, 原紀錄, ok])。索引定址的目標是陣列基底,
    實際讀寫的 byte 由暫存器決定,這裡不核對。
    """
    errs: list[str] = []
    for ins, t, width, _rw, kind, indexed in accesses:
        if kind != "mem" or indexed:
            continue
        lo, hi = t, t + width
        for sp in spans:
            if lo < sp[1] and sp[0] < hi and not (sp[0] <= lo and hi <= sp[1]):
                errs.append(f"region {hex(sp[0])}..{hex(sp[1])}: {hex(ins)} 的 {width} byte 存取 "
                            f"{hex(lo)}..{hex(hi)} 跨出區段邊界")
                sp[3] = False
    return errs


def evidence_errors(ev: object, ctx: Ctx, where: str, region: tuple[int, int] | None = None) -> list[str]:
    """一筆登錄的證據清單;回傳錯誤字串(空 = 全部成立)。region 是資料區段 [start, end)。"""
    if not isinstance(ev, list) or not ev:
        return [f"{where}: 沒有證據"]
    errs: list[str] = []
    for i, e in enumerate(ev):
        tag = f"{where} 證據#{i}"
        if not isinstance(e, dict):
            errs.append(f"{tag}: 不是物件")
        elif "func" in e:
            try:
                fa = parse_addr(e["func"])
            except ValueError as x:
                errs.append(f"{tag}: {x}")
                continue
            if fa not in ctx.funcs:
                errs.append(f"{tag}: 函式 {e['func']} 不在 function_inventory")
                continue
            if region is None:
                continue
            g = ctx.funcs[fa]
            if "ref" in e:
                try:
                    ra = parse_addr(e["ref"])
                except ValueError as x:
                    errs.append(f"{tag}: {x}")
                    continue
                if ra not in g:
                    errs.append(f"{tag}: 函式 {e['func']} 沒有引用 {e['ref']}")
            elif not any(region[0] <= a < region[1] for a in g):
                errs.append(f"{tag}: 函式 {e['func']} 沒有引用區段內任何位址(區段外的基底請用 ref 指明)")
        elif "doc" in e:
            text = ctx.read_doc(e["doc"]) if isinstance(e["doc"], str) else None
            if text is None:
                errs.append(f"{tag}: 讀不到文件 {e['doc']!r}")
            elif not nonempty_str(e.get("quote")) or e["quote"] not in text:
                errs.append(f"{tag}: {e['doc']} 沒有逐字出現 quote")
        elif e.get("no_refs") is True:
            if region is None:
                errs.append(f"{tag}: no_refs 只能用在資料區段")
                continue
            hit = sorted(a for a in set().union(*ctx.funcs.values(), ctx.fixup_targets)
                         if region[0] <= a < region[1])
            if hit:
                errs.append(f"{tag}: 宣稱 no_refs,但 {hex(hit[0])} 被引用")
        else:
            errs.append(f"{tag}: 不認得的證據種類 {sorted(e)}")
    return errs


# ---------------------------------------------------------------- 資料區

def field_errors(r: dict, start: int, end: int, refs: set[int], where: str) -> list[str]:
    """區段內除了起點,每個被程式碼引用的位址都要在 fields 有名稱(防止一段吞掉好幾個變數卻不說明)。

    fields = {"0x偏移": "名稱"};偏移必須在 (0, size) 內、名稱非空。沒人引用的偏移也可以列。
    """
    f = r.get("fields", {})
    if not isinstance(f, dict):
        return [f"{where}: fields 不是物件"]
    errs: list[str] = []
    offs: set[int] = set()
    for k, v in f.items():
        try:
            o = parse_addr(k)
        except ValueError as x:
            errs.append(f"{where}: fields {x}")
            continue
        if not 0 < o < end - start:
            errs.append(f"{where}: fields 偏移 {k} 不在 (0, size) 內")
        elif not nonempty_str(v):
            errs.append(f"{where}: fields {k} 缺名稱")
        else:
            offs.add(o)
    for a in sorted(a for a in refs if start < a < end):
        if a - start not in offs:
            errs.append(f"{where}: 區段內被引用的 {hex(a)}(+{hex(a - start)})沒有列在 fields")
    return errs


def check_regions(regions: object, objects: list[tuple[int, int]], ctx: Ctx
                  ) -> tuple[list[tuple[int, int, dict]], list[str]]:
    """核對 data_map 的 regions。回傳(成立的區段 [(start, end, 原紀錄)],錯誤)。

    objects 是資料物件 [(base, size)]。有錯的區段不算覆蓋,但仍參與重疊檢查(避免兩段互相掩護);
    重疊的兩段都不算覆蓋(否則同一批 byte 會被算兩次)。回傳的區段依 start 排序。
    """
    if not isinstance(regions, list):
        return [], ["data_map.regions 不是清單"]
    errs: list[str] = []
    spans: list[list] = []
    refs: set[int] = set().union(*ctx.funcs.values())
    for i, r in enumerate(regions):
        where = f"region#{i}"
        if not isinstance(r, dict):
            errs.append(f"{where}: 不是物件")
            continue
        try:
            start = parse_addr(r.get("start"))
        except ValueError as x:
            errs.append(f"{where}: {x}")
            continue
        size = r.get("size")
        if not isinstance(size, int) or isinstance(size, bool) or size <= 0:
            errs.append(f"{where} {hex(start)}: size 要是正整數")
            continue
        end = start + size
        where = f"region {hex(start)}..{hex(end)}"
        ok = True
        if not any(b <= start and end <= b + n for b, n in objects):
            errs.append(f"{where}: 不在任何資料物件內(或跨出物件)")
            ok = False
        for k in ("name", "type", "meaning"):
            if not nonempty_str(r.get(k)):
                errs.append(f"{where}: 缺 {k}")
                ok = False
        e = evidence_errors(r.get("evidence"), ctx, where, (start, end)) + field_errors(r, start, end, refs, where)
        errs += e
        spans.append([start, end, r, ok and not e])
    spans.sort(key=lambda t: t[0])
    for a, b in zip(spans, spans[1:]):
        if b[0] < a[1]:
            errs.append(f"region {hex(b[0])}..{hex(b[1])}: 與 {hex(a[0])}..{hex(a[1])} 重疊")
            a[3] = b[3] = False
    errs += access_errors(spans, ctx.accesses)
    return [(s, e, r) for s, e, r, ok in spans if ok], errs


def covered(addr: int, good: list[tuple[int, int, dict]]) -> bool:
    return any(s <= addr < e for s, e, _ in good)


def data_coverage(good: list[tuple[int, int, dict]], objects: list[tuple[int, int]],
                  funcs: dict[int, set[int]]) -> dict:
    """bytes 與被引用全域位址兩個比例,外加未覆蓋空隙 [(start, end, 引用數)] 與未覆蓋的被引用位址
    [(位址, 引用它的函式數)](都是引用多的排前面)。"""
    total = sum(n for _, n in objects)
    cov = sum(e - s for s, e, _ in good)
    refs: dict[int, int] = {}
    for g in funcs.values():
        for a in g:
            refs[a] = refs.get(a, 0) + 1
    in_obj = sorted(a for a in refs if any(b <= a < b + n for b, n in objects))
    spans: list[tuple[int, int]] = []
    for b, n in sorted(objects):
        cur = b
        for s, e, _ in good:            # check_regions 已依 start 排序
            if b <= s < b + n:
                if cur < s:
                    spans.append((cur, s))
                cur = e
        if cur < b + n:
            spans.append((cur, b + n))
    # 穩定排序:引用數相同時保持位址順序
    gaps = sorted(((s, e, sum(refs[a] for a in in_obj if s <= a < e)) for s, e in spans), key=lambda t: -t[2])
    uncovered = sorted(((a, refs[a]) for a in in_obj if not covered(a, good)), key=lambda t: -t[1])
    return {"bytes_total": total, "bytes_covered": cov, "uncovered": uncovered,
            "globals_total": len(in_obj), "globals_covered": sum(1 for a in in_obj if covered(a, good)),
            "gaps": gaps}


# ---------------------------------------------------------------- 程式碼

def code_coverage(funcs: dict[int, set[int]], game: set[int], library: set[int],
                  good: list[tuple[int, int, dict]]) -> dict:
    """遊戲函式:全部引用的全域位址都已登錄才算完成。函式庫:已辨識就算完成。

    兩者以外(沒有名稱也不是函式庫)的入口算 unnamed,一律未完成。
    """
    done: list[int] = []
    todo: list[tuple[int, int]] = []
    for a in sorted(funcs):
        if a in game:
            missing = sum(1 for g in funcs[a] if not covered(g, good))
            if missing == 0:
                done.append(a)
            else:
                todo.append((a, missing))
    todo.sort(key=lambda t: t[1])      # 穩定排序:缺得少的排前面,同數保持位址順序
    unnamed = sorted(a for a in funcs if a not in game and a not in library)
    return {"game_total": sum(1 for a in funcs if a in game), "game_done": len(done),
            "library_total": sum(1 for a in funcs if a in library and a not in game),
            "unnamed": unnamed, "todo": todo}


# ---------------------------------------------------------------- 資源

def check_resources(entries: object, live: dict[str, list[bytes]], ctx: Ctx,
                    probes: dict[str, Callable[[bytes], bool]]) -> tuple[dict[tuple[str, int], str], list[str]]:
    """核對 resource_map.resources。回傳({(dat, idx): 狀態},錯誤)。

    狀態:`complete`(probe 通過 + meaning + 證據)、`format`(probe 通過,用途未登錄)、
    `claimed`(格式沒有 probe)。有錯的那筆不給狀態。
    """
    if not isinstance(entries, list):
        return {}, ["resource_map.resources 不是清單"]
    errs: list[str] = []
    status: dict[tuple[str, int], str] = {}
    seen: set[tuple[str, int]] = set()
    for i, r in enumerate(entries):
        if not isinstance(r, dict):
            errs.append(f"resource#{i}: 不是物件")
            continue
        dat, idx = r.get("dat"), r.get("idx")
        where = f"{dat}#{idx}"
        if dat not in live:
            errs.append(f"{where}: 不認得的容器")
            continue
        if not isinstance(idx, int) or isinstance(idx, bool) or not 0 <= idx < len(live[dat]):
            errs.append(f"{where}: idx 超出範圍(0..{len(live[dat]) - 1})")
            continue
        if (dat, idx) in seen:
            errs.append(f"{where}: 重複登錄")
            continue
        seen.add((dat, idx))
        b = live[dat][idx]
        if r.get("sha1") != hashlib.sha1(b).hexdigest():
            errs.append(f"{where}: sha1 與原版位元組不同")
            continue
        fmt = r.get("format")
        if not nonempty_str(fmt):
            errs.append(f"{where}: 缺 format")
            continue
        p = probe_ok(fmt, b, probes)
        if p is False:
            errs.append(f"{where}: format {fmt!r} 的 probe 不通過")
            continue
        has_meaning = r.get("meaning") is not None
        if has_meaning:
            if not nonempty_str(r["meaning"]):
                errs.append(f"{where}: meaning 是空字串")
                continue
            e = evidence_errors(r.get("evidence"), ctx, where)
            if e:
                errs += e
                continue
        status[(dat, idx)] = "claimed" if p is None else ("complete" if has_meaning else "format")
    return status, errs


def check_files(entries: object, present: dict[str, str], ctx: Ctx) -> tuple[set[str], list[str]]:
    """核對 resource_map.files。present = {原版檔名: md5}。回傳(已登錄且成立的檔名,錯誤)。"""
    if not isinstance(entries, list):
        return set(), ["resource_map.files 不是清單"]
    errs: list[str] = []
    ok: set[str] = set()
    for i, r in enumerate(entries):
        name = r.get("file") if isinstance(r, dict) else None
        where = f"file {name!r}"
        if name not in present:
            errs.append(f"{where}: 遊戲目錄沒有這個原版檔案")
            continue
        if name in ok:
            errs.append(f"{where}: 重複登錄")
            continue
        if name in MUTABLE:
            if r.get("md5") is not None:
                errs.append(f"{where}: 執行時會改寫的檔案不釘 md5(請給 null)")
                continue
        elif r.get("md5") != present[name]:
            errs.append(f"{where}: md5 與遊戲目錄的檔案不同")
            continue
        if not nonempty_str(r.get("role")):
            errs.append(f"{where}: 缺 role")
            continue
        e = evidence_errors(r.get("evidence"), ctx, where)
        if e:
            errs += e
            continue
        ok.add(name)
    return ok, errs


# ---------------------------------------------------------------- 載入原版

def game_dir() -> Path:
    return Path(os.environ.get("FD2_GAME_DIR") or DEFAULT_GAME)


def _md5(b: bytes) -> str:
    return hashlib.md5(b).hexdigest()


def load_world() -> dict:
    """讀原版檔案與倉庫登錄,組出計算需要的全部事實。版本不符時丟 SystemExit。"""
    import le_xref
    import unpack_dat
    import function_inventory as FI

    gd = game_dir()
    ref = {f["file"]: f["md5"] for f in json.loads(REFERENCE_FILES.read_text(encoding="utf-8"))["files"]}
    exe = (gd / "FD2.EXE").read_bytes()
    if _md5(exe) != ref["FD2.EXE"]:
        raise SystemExit(f"FD2.EXE md5 {_md5(exe)} 不是參考版 {ref['FD2.EXE']}")
    meta = le_xref.parse_le(exe)
    objects = [(o["base"], o["vsize"]) for o in meta["objs"][1:]]
    fixups = set(le_xref.parse_fixups(exe, meta).values())

    inv = json.loads(INVENTORY.read_text(encoding="utf-8"))["entries"]
    funcs = {int(e["addr"], 16): {int(g, 16) for g in e["globals"]} for e in inv}

    # 指令層存取:線性掃描 + 從每個函式入口各自反組譯(第二條路徑)當錨點
    import disasm_le
    from capstone import CS_ARCH_X86, CS_MODE_32, Cs
    code, cbase = disasm_le.load_code(exe, meta)
    fx1 = disasm_le.build_fixups(exe, meta, {1})
    md = Cs(CS_ARCH_X86, CS_MODE_32)
    anchors = {x.address for e in inv
               for x in disasm_le.sweep_range(md, code, cbase, int(e["addr"], 16), int(e["addr"], 16) + e["span_upper"])
               if not isinstance(x, tuple)}
    accesses, unresolved, unanchored = decode_accesses(code, cbase, fx1, anchors)
    in_data = [s for s in unresolved if any(b <= fx1[s] < b + n for b, n in objects)]
    loose = set(unanchored)
    # 遊戲函式 = 有人讀過命名的入口:function_names.json(附摘要)、chapter_beats / event_handler 的 PRIM、
    # DOC_OP_NAMES。只有 AIL / Watcom 比對名稱的算函式庫(errata / verified_addresses 只記位址,不給名稱)。
    game = {int(n["addr"], 16) for n in FI.load_function_names() if nonempty_str(n.get("summary"))}
    # 只看來源是不是 PRIM / DOC_OP_NAMES;同址另有 function_names / Watcom 來源不影響判斷
    game |= {a for a, v in FI.load_names().items()
             if v["name"] and any(s.startswith(("PRIM(", "DOC_OP_NAMES")) for s in v["sources"])}
    library = set(FI.load_ail()) | set(FI.load_watcom())

    live: dict[str, list[bytes]] = {}
    for dat in DATS:
        b = (gd / dat).read_bytes()
        if _md5(b) != ref[dat]:
            raise SystemExit(f"{dat} md5 {_md5(b)} 不是參考版 {ref[dat]}")
        live[dat] = [b[o:o + n] for o, n in unpack_dat.parse_directory(b)]
    present = {p.name: _md5(p.read_bytes()) for p in sorted(gd.iterdir())
               if p.is_file() and ORIGINAL_NAME.match(p.name)}

    def read_doc(rel: str) -> str | None:
        p = (ROOT / rel).resolve()
        if ROOT not in p.parents or not p.is_file():
            return None
        return p.read_text(encoding="utf-8", errors="replace")

    # 錨點不成立的指令不參與大小核對(可能是錯位解碼),另行列出
    trusted = tuple(a for a in accesses if a[0] not in loose)
    # 錨點不成立、又指向資料區的存取種類(若有 "mem" 就代表大小核對漏看了真的存取)
    loose_kinds = {a[4] for a in accesses if a[0] in loose and any(b <= a[1] < b + n for b, n in objects)}
    return {"objects": objects, "funcs": funcs, "game": game, "library": library, "live": live,
            "present": present, "ctx": Ctx(funcs, fixups, read_doc, trusted),
            "unresolved_data": in_data, "unanchored": sorted(loose), "unanchored_kinds": loose_kinds}


def load_maps() -> tuple[dict, dict]:
    return (json.loads(DATA_MAP.read_text(encoding="utf-8")),
            json.loads(RESOURCE_MAP.read_text(encoding="utf-8")))


def evaluate(w: dict, dm: dict, rm: dict) -> dict:
    good, derr = check_regions(dm.get("regions"), w["objects"], w["ctx"])
    status, rerr = check_resources(rm.get("resources"), w["live"], w["ctx"], PROBES)
    fok, ferr = check_files(rm.get("files"), w["present"], w["ctx"])
    # 對不上指令的資料 fixup 代表大小核對看不到那次存取:不能當沒事
    uerr = [f"資料 fixup {hex(s)} 對不上任何指令運算元,大小核對不完整" for s in w["unresolved_data"]]
    return {"good": good, "errors": derr + rerr + ferr + uerr, "status": status, "files_ok": fok,
            "data": data_coverage(good, w["objects"], w["funcs"]),
            "code": code_coverage(w["funcs"], w["game"], w["library"], good)}


def pct(a: int, b: int) -> str:
    return f"{a}/{b} ({100.0 * a / b:.1f}%)" if b else f"{a}/0"


def print_summary(w: dict, r: dict) -> None:
    c, d, s = r["code"], r["data"], r["status"]
    nres = sum(len(v) for v in w["live"].values())
    vals = list(s.values())
    print("規格層逆向覆蓋率(分母由原版檔案現算)")
    print(f"  程式碼  遊戲函式(引用的全域位址全部已登錄)  {pct(c['game_done'], c['game_total'])}")
    print(f"          函式庫已辨識                          {pct(c['library_total'], c['library_total'])}")
    print(f"          沒有名稱也不是函式庫                  {len(c['unnamed'])}")
    print(f"  資料區  obj2+obj3 bytes                       {pct(d['bytes_covered'], d['bytes_total'])}")
    print(f"          被程式碼引用的全域位址                {pct(d['globals_covered'], d['globals_total'])}")
    print(f"          指令層存取(大小核對用)              {len(w['ctx'].accesses)} 筆;對不上指令的資料 fixup "
          f"{len(w['unresolved_data'])}、錨點不成立的指令 {len(w['unanchored'])}")
    print(f"  資源    原版檔案(用途已登錄)                {pct(len(r['files_ok']), len(w['present']))}")
    print(f"          .DAT 資源 格式已驗                    {pct(vals.count('format') + vals.count('complete'), nres)}")
    print(f"          .DAT 資源 完成(格式已驗 + 用途)       {pct(vals.count('complete'), nres)}")
    print(f"          .DAT 資源 只有宣稱(格式沒有 probe)    {vals.count('claimed')}")
    print(f"  登錄錯誤 {len(r['errors'])}")
    for e in r["errors"][:20]:
        print(f"    {e}")


def print_gaps(w: dict, r: dict, layer: str, limit: int) -> None:
    if layer == "data":
        for s, e, n in r["data"]["gaps"][:limit]:
            print(f"{hex(s)}..{hex(e)}  {e - s:6d} bytes  引用 {n}")
    elif layer == "globals":
        for a, n in r["data"]["uncovered"][:limit]:
            print(f"{hex(a)}  {n} 個函式引用")
    elif layer == "code":
        for a, m in r["code"]["todo"][:limit]:
            print(f"{hex(a)}  未登錄的全域位址 {m}")
        for a in r["code"]["unnamed"][:limit]:
            print(f"{hex(a)}  沒有名稱")
    elif layer == "resources":
        for dat in DATS:
            todo = [i for i in range(len(w["live"][dat])) if r["status"].get((dat, i)) != "complete"]
            print(f"{dat}: 未完成 {len(todo)}/{len(w['live'][dat])}  {todo[:limit]}")
    else:
        for name in sorted(set(w["present"]) - r["files_ok"])[:limit]:
            print(name)


def show_data(w: dict, addr: int) -> None:
    obj = [(b, n) for b, n in w["objects"] if b <= addr < b + n]
    print(f"{hex(addr)}  物件 {[(hex(b), hex(n)) for b, n in obj] or '不在資料物件內'}")
    users = sorted(f for f, g in w["funcs"].items() if addr in g)
    near = sorted({a for g in w["funcs"].values() for a in g if abs(a - addr) <= 0x40})
    print(f"  直接引用它的函式 {[hex(f) for f in users]}")
    print(f"  ±0x40 內被引用的位址 {[hex(a) for a in near]}")
    acc = [a for a in w["ctx"].accesses if a[1] == addr]
    kinds: dict[tuple, int] = {}
    for _i, _t, width, rw, kind, indexed in acc:
        k = (kind, width, rw, "索引" if indexed else "直接")
        kinds[k] = kinds.get(k, 0) + 1
    print(f"  指令層存取 {len(acc)} 筆:{sorted(kinds.items())}")
    writers = sorted(a[0] for a in acc if "w" in a[3])
    print(f"  寫入指令 {[hex(x) for x in writers]}")
    direct = [a[2] for a in acc if a[4] == "mem" and not a[5]]
    stub = {"start": hex(addr), "size": max(direct, default=1), "name": "", "type": "", "meaning": "",
            "evidence": [{"func": hex(users[0])}] if users else []}
    print(json.dumps(stub, ensure_ascii=False))


def show_resource(w: dict, dat: str, idx: int) -> None:
    b = w["live"][dat][idx]
    passed = [k for k in PROBES if probe_ok(k, b, PROBES)]
    print(f"{dat}#{idx}  長度 {len(b)}  sha1 {hashlib.sha1(b).hexdigest()}  前 16 bytes {b[:16].hex()}")
    print(f"  通過的 probe {passed}")
    stub = {"dat": dat, "idx": idx, "sha1": hashlib.sha1(b).hexdigest(),
            "format": passed[0] if passed else "", "meaning": None, "evidence": []}
    print(json.dumps(stub, ensure_ascii=False))


# ---------------------------------------------------------------- selftest

def selftest() -> int:
    fails: list[str] = []

    def check(name: str, cond: bool) -> None:
        print(("PASS " if cond else "FAIL ") + name)
        if not cond:
            fails.append(name)

    def has(errs: list[str], frag: str) -> bool:
        return any(frag in e for e in errs)

    docs = {"d.md": "表格在 0x60000,四個 byte"}
    funcs = {0x10000: {0x50010, 0x50080}, 0x10100: {0x60004}, 0x10200: set(), 0x10300: {0x500f0},
             0x10400: {0x60004}}
    ctx = Ctx(funcs, {0x500e0}, docs.get)
    objects = [(0x50000, 0x100), (0x60000, 0x40)]
    base = [{"start": "0x50010", "size": 0x10, "name": "a", "type": "u8[16]", "meaning": "m",
             "evidence": [{"func": "0x10000"}]},
            {"start": "0x60000", "size": 4, "name": "b", "type": "u32", "meaning": "m",
             "evidence": [{"doc": "d.md", "quote": "四個 byte"}]}]

    # (1) 對照組:合法登錄 0 錯誤,數字逐一核對
    good, errs = check_regions(base, objects, ctx)
    check("(1a) 合法登錄沒有錯誤", errs == [] and len(good) == 2)
    d = data_coverage(good, objects, funcs)
    check("(1b) bytes 0x14 / 0x140", (d["bytes_covered"], d["bytes_total"]) == (0x14, 0x140))
    check("(1c) 全域位址 1 / 4(0x60004 在區段尾端之外,不算)",
          (d["globals_covered"], d["globals_total"]) == (1, 4))
    check("(1d) 空隙依引用數排序、邊界正確",
          d["gaps"] == [(0x50020, 0x50100, 2), (0x60004, 0x60040, 2), (0x50000, 0x50010, 0)])
    check("(1d2) 未覆蓋位址依引用數排序", d["uncovered"] == [(0x60004, 2), (0x50080, 1), (0x500f0, 1)])
    c = code_coverage(funcs, {0x10000, 0x10100, 0x10200}, {0x10300, 0x10200}, good)
    check("(1e) 只有沒引用全域位址的遊戲函式算完成",
          (c["game_done"], c["game_total"], c["todo"]) == (1, 3, [(0x10000, 1), (0x10100, 1)]))
    check("(1f) 函式庫只算不在遊戲名單的;沒有名稱的入口列出",
          (c["library_total"], c["unnamed"]) == (1, [0x10400]))
    c2 = code_coverage(funcs, {0x10000}, set(), good)
    check("(1g) 既沒名稱也不是函式庫的入口算 unnamed", c2["unnamed"] == [0x10100, 0x10200, 0x10300, 0x10400])

    # (2) 故障注入:每一種都要被抓到,邊界旁的合法值不得誤報
    def regions_with(extra: dict) -> list[str]:
        return check_regions(base + [extra], objects, ctx)[1]

    r = {"name": "x", "type": "t", "meaning": "m", "evidence": [{"doc": "d.md", "quote": "四個"}]}
    check("(2a) 重疊被抓", has(regions_with({**r, "start": "0x5001f", "size": 1}), "重疊"))
    check("(2a2) 重疊訊息指出後面那段與包住它的那段",
          regions_with({**r, "start": "0x50012", "size": 1})
          == ["region 0x50012..0x50013: 與 0x50010..0x50020 重疊"])
    ov = check_regions(base + [{**r, "start": "0x50012", "size": 1}], objects, ctx)[0]
    check("(2a3) 重疊的兩段都不算覆蓋", [s for s, _, _ in ov] == [0x60000])
    check("(2b) 緊鄰不算重疊", regions_with({**r, "start": "0x50020", "size": 1}) == [])
    check("(2c) 跨出物件被抓", has(regions_with({**r, "start": "0x500ff", "size": 2}), "不在任何資料物件"))
    check("(2c2) 跨出物件的區段不算覆蓋",
          check_regions([{**r, "start": "0x500ff", "size": 2}], objects, ctx)[0] == [])
    check("(2d) 物件最後一個 byte 合法", regions_with({**r, "start": "0x500ff", "size": 1}) == [])
    check("(2e) 物件之前的位址被抓", has(regions_with({**r, "start": "0x4ffff", "size": 1}), "不在任何資料物件"))
    check("(2f) size 0 被抓", has(regions_with({**r, "start": "0x50030", "size": 0}), "size"))
    check("(2g) size 用 bool 被抓", has(regions_with({**r, "start": "0x50030", "size": True}), "size"))
    check("(2h) 位址不是 0x 小寫字串被抓", has(regions_with({**r, "start": "50030", "size": 1}), "位址格式"))
    check("(2i) 缺 meaning 被抓", has(regions_with({**r, "start": "0x50030", "size": 1, "meaning": " "}), "缺 meaning"))
    check("(2i2) 缺 meaning 的區段不算覆蓋",
          check_regions([{**r, "start": "0x50030", "size": 1, "meaning": ""}], objects, ctx)[0] == [])
    check("(2j) 沒有證據被抓", has(regions_with({**r, "start": "0x50030", "size": 1, "evidence": []}), "沒有證據"))
    bad_func = check_regions([{**base[0], "evidence": [{"func": "0x19999"}]}], objects, ctx)
    check("(2k) 證據函式不存在被抓,且該段不算覆蓋",
          has(bad_func[1], "不在 function_inventory") and bad_func[0] == [])
    check("(2l) 函式沒引用區段內位址被抓",
          has(regions_with({**r, "start": "0x50030", "size": 1, "evidence": [{"func": "0x10100"}]}), "沒有引用區段內"))
    check("(2m) ref 是函式真的引用的位址就成立(區段外基底)",
          regions_with({**r, "start": "0x50030", "size": 1,
                        "evidence": [{"func": "0x10000", "ref": "0x50080"}]}) == [])
    check("(2n) ref 不是函式引用的位址被抓",
          has(regions_with({**r, "start": "0x50030", "size": 1,
                            "evidence": [{"func": "0x10000", "ref": "0x50081"}]}), "沒有引用 0x50081"))
    check("(2o) quote 不在文件被抓",
          has(regions_with({**r, "start": "0x50030", "size": 1,
                            "evidence": [{"doc": "d.md", "quote": "五個"}]}), "沒有逐字出現"))
    check("(2p) 文件不存在被抓",
          has(regions_with({**r, "start": "0x50030", "size": 1,
                            "evidence": [{"doc": "x.md", "quote": "四個"}]}), "讀不到文件"))
    check("(2q) no_refs 成立(沒人引用的空隙)",
          regions_with({**r, "start": "0x50030", "size": 0x10, "evidence": [{"no_refs": True}]}) == [])
    check("(2r) no_refs 但有函式引用被抓",
          has(regions_with({**r, "start": "0x500f0", "size": 1, "evidence": [{"no_refs": True}]}), "0x500f0 被引用"))
    check("(2s) no_refs 但有 fixup 指向被抓",
          has(regions_with({**r, "start": "0x500e0", "size": 1, "evidence": [{"no_refs": True}]}), "0x500e0 被引用"))
    check("(2t) 不認得的證據種類被抓",
          has(regions_with({**r, "start": "0x50030", "size": 1, "evidence": [{"guess": 1}]}), "不認得"))
    check("(2u) regions 不是清單被抓", check_regions({}, objects, ctx)[1] == ["data_map.regions 不是清單"])

    # (3) 資源:三種狀態與每一種錯誤
    cont = b"LLLLLL" + struct.pack("<I", 10) + b"ab"
    live = {"A.DAT": [cont, b"", b"xyz"]}
    sha = [hashlib.sha1(x).hexdigest() for x in live["A.DAT"]]
    ents = [{"dat": "A.DAT", "idx": 0, "sha1": sha[0], "format": "container", "meaning": "巢狀",
             "evidence": [{"func": "0x10000"}]},
            {"dat": "A.DAT", "idx": 1, "sha1": sha[1], "format": "empty", "meaning": None},
            {"dat": "A.DAT", "idx": 2, "sha1": sha[2], "format": "pcm", "meaning": None}]
    st, errs = check_resources(ents, live, ctx, PROBES)
    check("(3a) 合法登錄:complete / format / claimed",
          errs == [] and st == {("A.DAT", 0): "complete", ("A.DAT", 1): "format", ("A.DAT", 2): "claimed"})

    def res_err(e: dict) -> list[str]:
        return check_resources([e], live, ctx, PROBES)[1]

    check("(3b) sha1 不同被抓", has(res_err({**ents[0], "sha1": sha[2]}), "sha1"))
    check("(3c) idx 超出範圍被抓,訊息給出合法範圍", res_err({**ents[0], "idx": 3}) == ["A.DAT#3: idx 超出範圍(0..2)"])
    check("(3d) 負 idx 被抓", has(res_err({**ents[0], "idx": -1}), "超出範圍"))
    check("(3e) 不認得的容器被抓", has(res_err({**ents[0], "dat": "B.DAT"}), "不認得的容器"))
    check("(3f) 重複登錄被抓", has(check_resources([ents[0], ents[0]], live, ctx, PROBES)[1], "重複"))
    check("(3g) container probe 對非容器說不",
          has(res_err({**ents[2], "format": "container"}), "probe 不通過"))
    check("(3h) empty probe 對非空資源說不", has(res_err({**ents[2], "format": "empty"}), "probe 不通過"))
    check("(3i) 缺 format 被抓", has(res_err({**ents[0], "format": ""}), "缺 format"))
    check("(3j) meaning 有字但證據不成立被抓",
          has(res_err({**ents[0], "evidence": [{"func": "0x19999"}]}), "不在 function_inventory"))
    check("(3k) meaning 空字串被抓", has(res_err({**ents[0], "meaning": ""}), "空字串"))
    check("(3l) no_refs 不能當資源證據", has(res_err({**ents[0], "evidence": [{"no_refs": True}]}), "只能用在資料區段"))
    check("(3m) idx 用 bool 被抓", has(res_err({**ents[0], "idx": True}), "超出範圍"))

    # (4) 原版檔案
    present = {"FD2.EXE": "aa", "FD2.SAV": "bb"}
    fe = [{"file": "FD2.EXE", "md5": "aa", "role": "主程式", "evidence": [{"doc": "d.md", "quote": "四個"}]},
          {"file": "FD2.SAV", "md5": None, "role": "存檔", "evidence": [{"func": "0x10000"}]}]
    ok, errs = check_files(fe, present, ctx)
    check("(4a) 合法檔案登錄", errs == [] and ok == {"FD2.EXE", "FD2.SAV"})
    check("(4b) md5 不同被抓", has(check_files([{**fe[0], "md5": "ab"}], present, ctx)[1], "md5 與遊戲目錄"))
    check("(4c) 會被改寫的檔案釘 md5 被抓", has(check_files([{**fe[1], "md5": "bb"}], present, ctx)[1], "不釘 md5"))
    check("(4d) 目錄沒有的檔案被抓", has(check_files([{**fe[0], "file": "X.DAT"}], present, ctx)[1], "沒有這個原版檔案"))
    check("(4e) 重複登錄被抓", has(check_files([fe[0], fe[0]], present, ctx)[1], "重複"))
    check("(4f) 缺 role 被抓", has(check_files([{**fe[0], "role": ""}], present, ctx)[1], "缺 role"))
    check("(4g) 檔案證據不成立被抓",
          has(check_files([{**fe[0], "evidence": []}], present, ctx)[1], "沒有證據"))

    # (5) 小工具
    check("(5a) 原版檔名判準:大寫 8.3 才算",
          [bool(ORIGINAL_NAME.match(n)) for n in ("FD2.EXE", "SAMPLE.AD", "TITLE_decoded.png", "11.txt", "ABCDEFGHI.DAT")]
          == [True, True, False, False, False])
    check("(5b) probe 丟例外算失敗、沒有 probe 回 None",
          probe_ok("container", b"xx", PROBES) is False and probe_ok("pcm", b"", PROBES) is None)
    check("(5c) pct", (pct(1, 4), pct(0, 0)) == ("1/4 (25.0%)", "0/0"))
    check("(5d) covered 是半開區間", (covered(0x5001f, good), covered(0x50020, good)) == (True, False))

    # (7) 指令層存取:合成機器碼逐條核對寬度 / 讀寫 / 索引 / 取址,錯位的 fixup 與錨點不成立的指令要分出來
    try:
        import capstone  # noqa: F401
        have_cs = True
    except ImportError:
        have_cs = False
    if have_cs:
        z4 = b"\0\0\0\0"
        code = (b"\xa1" + z4                 # 0x10000 mov eax, [abs]           disp @0x10001
                + b"\xc6\x05" + z4 + b"\x01"  # 0x10005 mov byte [abs], 1        disp @0x10007
                + b"\x8b\x04\x85" + z4       # 0x1000c mov eax, [eax*4 + abs]   disp @0x1000f
                + b"\x68" + z4               # 0x10013 push abs                 imm  @0x10014
                + b"\xff\x05" + z4           # 0x10018 inc dword [abs]          disp @0x1001a
                + b"\x8d\x05" + z4           # 0x1001e lea eax, [abs]           disp @0x10020
                + b"\xb8" + z4               # 0x10024 mov eax, imm             fixup 錯位 @0x10026
                + b"\x66\x89\x05" + z4)      # 0x10029 mov word [abs], ax       disp @0x1002c
        fx = {0x10001: 0x50010, 0x10007: 0x50020, 0x1000f: 0x50030, 0x10014: 0x50040,
              0x1001a: 0x50050, 0x10020: 0x50060, 0x10026: 0x50070, 0x1002c: 0x50080}
        starts = {0x10000, 0x10005, 0x1000c, 0x10013, 0x1001e, 0x10024, 0x10029}   # 故意缺 0x10018
        acc, unres, loose = decode_accesses(code, 0x10000, fx, starts)
        check("(7a) 每一種運算元的寬度 / 讀寫 / 索引 / 種類", acc == [
            (0x10000, 0x50010, 4, "r", "mem", False), (0x10005, 0x50020, 1, "w", "mem", False),
            (0x1000c, 0x50030, 4, "r", "mem", True), (0x10013, 0x50040, 0, "", "addr", False),
            (0x10018, 0x50050, 4, "rw", "mem", False), (0x1001e, 0x50060, 0, "", "addr", False),
            (0x10029, 0x50080, 2, "w", "mem", False)])
        check("(7b) 錯位的 fixup 列為 unresolved", unres == [0x10026])
        check("(7c) 錨點裡沒有的指令列為 unanchored", loose == [0x10018])
        check("(7d) 不給錨點就不判 unanchored", decode_accesses(code, 0x10000, fx)[2] == [])
    else:
        print("SKIP (7) 沒有 capstone")

    # (8) fields:區段內被引用的位址(起點除外)都要有名稱
    fr = {**r, "start": "0x500e0", "size": 0x20}
    check("(8a) 區段內被引用的位址沒列在 fields 被抓,訊息逐字",
          regions_with(fr) == ["region 0x500e0..0x50100: 區段內被引用的 0x500f0(+0x10)沒有列在 fields"])
    check("(8b) 列進 fields 就成立", regions_with({**fr, "fields": {"0x10": "y"}}) == [])
    check("(8c) fields 偏移 0 與 size 被抓、1 與 size-1 合法",
          has(regions_with({**fr, "fields": {"0x10": "y", "0x0": "z"}}), "偏移 0x0 不在")
          and has(regions_with({**fr, "fields": {"0x10": "y", "0x20": "z"}}), "偏移 0x20 不在")
          and regions_with({**fr, "fields": {"0x10": "y", "0x1f": "z", "0x1": "w"}}) == [])
    check("(8d) fields 名稱空白被抓", has(regions_with({**fr, "fields": {"0x10": " "}}), "0x10 缺名稱"))
    check("(8e) fields 不是物件被抓", has(regions_with({**fr, "fields": ["0x10"]}), "fields 不是物件"))
    check("(8f) fields 偏移格式錯被抓", has(regions_with({**fr, "fields": {"16": "y"}}), "位址格式"))
    check("(8g) fields 不成立的區段不算覆蓋", [s_ for s_, _, _ in check_regions([fr], objects, ctx)[0]] == [])

    def acc_errs(*accs: Access) -> tuple[list, list[str]]:
        return check_regions(base, objects, Ctx(funcs, set(), docs.get, accs))

    ok_acc = acc_errs((0x10000, 0x50012, 4, "r", "mem", False), (0x10001, 0x5000c, 4, "w", "mem", False),
                      (0x10002, 0x50020, 4, "r", "mem", False), (0x10003, 0x5001e, 4, "r", "mem", True),
                      (0x10004, 0x5001f, 0, "", "addr", False))
    check("(7e) 區段內、緊鄰兩側、索引定址、取址都不算跨界", ok_acc[1] == [] and len(ok_acc[0]) == 2)
    tail = acc_errs((0x10000, 0x5001e, 4, "w", "mem", False))
    check("(7f) 尾端跨界被抓,訊息逐字,該段不算覆蓋",
          tail[1] == ["region 0x50010..0x50020: 0x10000 的 4 byte 存取 0x5001e..0x50022 跨出區段邊界"]
          and [s for s, _, _ in tail[0]] == [0x60000])
    check("(7g) 頭端跨界被抓", has(acc_errs((0x10000, 0x5000e, 4, "r", "mem", False))[1], "0x5000e..0x50012"))
    check("(7h) 包住整段的大存取被抓",
          has(acc_errs((0x10000, 0x5fffe, 8, "r", "mem", False))[1], "region 0x60000..0x60004"))

    # (6) 原版檔案(有遊戲目錄時):分母由原版現算,數字要與已知事實相同;倉庫登錄必須 0 錯誤
    if (game_dir() / "FD2.EXE").is_file():
        w = load_world()
        check("(6a) 資料物件 = obj2 0x50000+0x56b0、obj3 0x60000+0x34d2",
              w["objects"] == [(0x50000, 0x56B0), (0x60000, 0x34D2)])
        check("(6b) 1356 個入口全部是遊戲函式或函式庫",
              len(w["funcs"]) == 1356 and w["funcs"].keys() <= (w["game"] | w["library"]))
        check("(6c) 已知有名稱的遊戲函式與函式庫都在對的一邊",
              {0x10620, 0x10652, 0x111ba} <= w["game"] and 0x10620 not in w["library"])
        check("(6d) 11 個容器共 1005 筆資源;TAI.DAT 57 筆",
              sum(len(v) for v in w["live"].values()) == 1005 and len(w["live"]["TAI.DAT"]) == 57)
        check("(6e) 原版檔案 49 個,分析留下的檔案不算",
              len(w["present"]) == 49 and "FD2.EXE" in w["present"] and "TITLE_decoded.png" not in w["present"])
        check("(6f) fixup 目標含已知跳表 0x51b91 的分派目標 0x35854", 0x35854 in w["ctx"].fixup_targets)
        check("(6g) read_doc 讀得到倉庫文件、拒絕倉庫外路徑",
              "FD2.EXE" in (w["ctx"].read_doc("AGENTS.md") or "") and w["ctx"].read_doc("../x") is None
              and w["ctx"].read_doc("docs/data/none.json") is None)
        r = evaluate(w, *load_maps())
        check("(6h) 倉庫的 data_map / resource_map 0 錯誤", r["errors"] == [])
        check("(6i) 函式庫與遊戲函式加總 = 1356",
              r["code"]["game_total"] + r["code"]["library_total"] == 1356 and r["code"]["unnamed"] == [])
        check("(6j) 資料 fixup 全部對得上指令;錨點不成立的只有 AIL 區 5 條,指向資料區的都只是取址(不含寬度)",
              w["unresolved_data"] == [] and w["unanchored"] == [0x40102, 0x40112, 0x42112, 0x4211D, 0x45672]
              and w["unanchored_kinds"] == {"addr"})
        check("(6j2) 錨點不成立的指令不進大小核對",
              not {a[0] for a in w["ctx"].accesses} & set(w["unanchored"]))
        a45 = [a for a in w["ctx"].accesses if a[1] == 0x53A45]
        check("(6k) [0x53a45] 262 筆全是 4 byte 直接定址,10 筆寫入的位置已知",
              len(a45) == 262 and {(a[2], a[4], a[5]) for a in a45} == {(4, "mem", False)}
              and sorted(a[0] for a in a45 if "w" in a[3])
              == [0x102C3, 0x109DB, 0x1FA80, 0x26196, 0x2634C, 0x26356, 0x267E1, 0x267EB, 0x26810, 0x26985])
        # 原版上的負向對照:把 0x53a45 登錄成錯的大小,三種錯法各被一條規則抓到
        # (不讀倉庫登錄,自己組一段,倉庫怎麼改都不影響這題)
        reg = {"start": "0x53a45", "name": "x", "type": "t", "meaning": "m", "evidence": [{"func": "0x10010"}]}

        def sized(n: int) -> list[str]:
            return evaluate(w, {"regions": [{**reg, "size": n}]}, {"resources": [], "files": []})["errors"]

        check("(6l) 0x53a45 登錄 3 / 5 / 8 byte 都被抓;4 byte 成立",
              has(sized(3), "0x53a45..0x53a49 跨出區段邊界") and has(sized(5), "0x53a49..0x53a4d 跨出區段邊界")
              and has(sized(8), "0x53a49(+0x4)沒有列在 fields") and sized(4) == [])
    else:
        print("SKIP (6) 找不到遊戲目錄")

    print("selftest", "PASS" if not fails else f"FAIL {len(fails)}")
    return 0 if not fails else 1


# ---------------------------------------------------------------- CLI

def main(argv: list[str]) -> int:
    ap = argparse.ArgumentParser(description="規格層逆向覆蓋率(程式碼 / 資料區 / 資源)")
    ap.add_argument("--summary", action="store_true")
    ap.add_argument("--check", action="store_true", help="登錄有任何錯誤就 exit 1")
    ap.add_argument("--gaps", choices=("data", "globals", "code", "resources", "files"))
    ap.add_argument("--limit", type=int, default=30)
    ap.add_argument("--show-data", metavar="ADDR")
    ap.add_argument("--show-resource", nargs=2, metavar=("DAT", "IDX"))
    ap.add_argument("--selftest", action="store_true")
    a = ap.parse_args(argv)
    if a.selftest:
        return selftest()
    w = load_world()
    if a.show_data:
        show_data(w, parse_addr(a.show_data))
        return 0
    if a.show_resource:
        show_resource(w, a.show_resource[0], int(a.show_resource[1]))
        return 0
    dm, rm = load_maps()
    r = evaluate(w, dm, rm)
    if a.gaps:
        print_gaps(w, r, a.gaps, a.limit)
        return 0
    print_summary(w, r)
    return 1 if a.check and r["errors"] else 0


if __name__ == "__main__":
    sys.exit(main(sys.argv[1:]))
