#!/usr/bin/env python3
"""篩出「摘要宣稱與實機紀錄矛盾」的函式,供人工逐筆核對(doc98 續一百零九)。

續一百零八的規格檔抓到 3 筆摘要錯誤(參數順序、回傳值),但規格只涵蓋 47 個函式;其餘有實機紀錄的
函式沒有人對過。本工具把摘要裡**不必人工整理就能機械比對**的部分全部掃一遍,列出矛盾的候選。

輸入都是已提交的檔,不必重讀 130 MB 的呼叫紀錄:
- `docs/data/function_names.json` 的摘要:開頭的參數列 `(a, b, c)` 與回傳句。
- `docs/data/function_call_profiles.json`:`verify_names_by_calllog.py --export` 的逐函式事實(參數 / 回傳 / 呼叫端)。
- 參考版 EXE:實機呼叫端 `call` 之後的 `add esp, N` = 實際推了 N / 4 個堆疊參數。
- `docs/data/summary_screen_review.json`:人工核對結論。

實機紀錄的四種篩選:
1. `param_count`:摘要參數列的個數 vs 實機直接呼叫端清掉的堆疊參數個數(所有呼叫端一致且 > 0 才比)。
   不用 inventory 的 argc:它是被呼叫端「本體從堆疊讀到第幾個參數」,是下界(可以不讀最後一個參數),而且
   續一百零九當時是線性掃描,兩個方向都錯(例 `defender_can_counter` 只讀 2 個、argc 記 5;續一百一十改成沿
   控制流)。呼叫端清堆疊是與它獨立的訊號。
2. `param_type`:參數名有型別意涵 —— unit / 單位 / attacker … 是單位序號或單位陣列指標;dst / src / buf … 是指標
   (NULL 可);x / y / idx / 長度 … 是小整數(含小負數)。該位置最常見的值(剖面最多 8 個)有 ≥ 80% 違反就列出。
3. `param_str`:參數名是字串(檔名 / 格式 / 名稱 …),該位置有非 NULL 值卻從未讀到可列印字串。
4. `ret_unlisted`:摘要把回傳值列舉完(兩個以上字面值,或有「否則 / 其餘 N」,且沒有「回傳筆數」這類非字面的回傳句),
   實機回傳的相異值全部已知(≤ 8 個)卻有列舉外的值。

續一百一十一補兩種,針對「指標對指標」的對調(型別篩選看不到):
5. `param_region`:參數名是來源(src / res / 圖 … 或字串),該位置最常見的值有 ≥ 50% 是 VGA 視訊記憶體(0xa0000 起)。
6. `param_role`(**靜態,不需要實機紀錄**,涵蓋沒執行到的函式):沿 `callee_argc` 的控制流追蹤「哪個暫存器裝著第 k 個
   參數」,看本體經由它是寫(stos / movs 的 edi、`mov [r], …`)還是讀(lods 的 esi、`mov …, [r]`)。目的參數只讀不寫、
   或來源參數被寫入就列出。dst / src 對調時兩個都觸發(selftest 以真實摘要角色全部對調當對照,須 ≥ 90% 觸發)。
   傳參方式:呼叫端清堆疊個數(EXE 全部 `call rel32`,`call_cleanups`)唯一且 == 參數列個數 -> 堆疊;沒有清堆疊時
   argc == 個數 -> 堆疊、argc 0 且 ≤ 4 個 -> Watcom 暫存器;其餘不比。

參數位置:呼叫端有清堆疊時取 [esp+4k](`s<k>`);否則依 inventory argc(`verify_names_by_calllog.param_slot`)。

這是篩選,不是判決。每個候選要人看反組譯,在 review 檔記:
- `fixed`:摘要已改正(附位元組證據);之後必須**不再觸發**,仍觸發 = FAIL(改正沒生效)。
- `not_error`:附理由(例:參數名本來就指 portrait 編號);必須仍對應一個現存候選,否則算過期 = FAIL。
rc 0 = 沒有未核對的候選、review 檔沒有錯誤;報告同時列各篩選的分母(可檢查的函式 / 參數數),不把「沒得比」算成通過。

用法:
    python tools/screen_summaries_by_calllog.py                 # 篩選 + 對照 review 檔
    python tools/screen_summaries_by_calllog.py --json OUT      # 另寫候選明細(含證據值、摘要、核對結論)
    python tools/screen_summaries_by_calllog.py --review JSON   # 換一份 review 檔
    python tools/screen_summaries_by_calllog.py --selftest
"""
from __future__ import annotations

import argparse
import json
import re
import sys
from dataclasses import dataclass, field
from pathlib import Path

ROOT = Path(__file__).resolve().parent.parent
sys.path.insert(0, str(ROOT / "tools"))

import derive_native_argcounts as DNA  # noqa: E402
import verify_names_by_calllog as VC  # noqa: E402
from verify_names_by_calllog import _skip_mov_eax, pushed_args  # noqa: E402,F401  續一百一十一移到 VC

NAMES_JSON = ROOT / "docs" / "data" / "function_names.json"
PROFILES_JSON = ROOT / "docs" / "data" / "function_call_profiles.json"
REVIEW_JSON = ROOT / "docs" / "data" / "summary_screen_review.json"
SCREENS = ("param_count", "param_type", "param_str", "ret_unlisted", "param_region", "param_role")
VERDICTS = ("fixed", "not_error")
VIOLATION_SHARE = 0.8      # 最常見值裡違反型別的比例門檻
MIN_COVERED = 3            # 最常見值的次數合計至少這麼多才判
MIN_RETURNED = 5           # 有返回紀錄至少這麼多次才比回傳值


# ---------------------------------------------------------------- 摘要解析

NPARAMS = re.compile(r"^(\d+) 個參數$")


def parse_sig(summary: str) -> tuple[list[str] | None, int | None]:
    """摘要開頭參數列 -> (參數名, 個數)。

    沒有參數列 -> (None, None);`()` -> ([], 0);`(3 個參數)` -> ([], 3);含 `...` / `..`(可變參數)或
    `eax = ptr` 這類暫存器寫法 -> (名稱, None),個數不比。
    """
    m = VC.PARAMS.match(summary or "")
    if not m:
        return None, None
    body = m.group(1).strip()
    if not body:
        return [], 0
    names = [p.strip() for p in body.split(",")]
    if len(names) == 1 and (n := NPARAMS.match(names[0])):
        return [], int(n.group(1))
    if any(p in ("...", "..") or "=" in p for p in names):
        return names, None
    return names, len(names)


UNIT_NAMES = frozenset({"unit", "單位", "attacker", "defender", "target", "caster", "攻方", "守方", "使用者"})
STR_NAMES = frozenset({"名稱", "模式字串", "檔名", "msg", "格式", "name", "file", "filename", "fmt", "path"})
PTR_NAMES = frozenset({
    "dst", "src", "out", "buf", "目的", "緩衝區", "輸出", "來源", "res", "anim", "img", "records", "units", "targets",
    "grid", "terrainTable", "FILE*", "項目表", "items", "work", "tmpl", "font", "list", "fp", "script", "ctx", "ptr",
    "圖", "單位清單", "資源", "畫面緩衝", "串流", "參數表", "精靈", "檔案影像", "列表", "路徑碼陣列", "costRow",
    "&輸出", "positions", "p"})
SMALL_NAMES = frozenset({
    "x", "y", "mode", "count", "item", "idx", "sel", "sell", "len", "id", "n", "spell", "selector", "value", "delta",
    "budget", "row", "kind", "slot", "res_idx", "originX", "originY", "class", "color", "w", "h", "cursorX",
    "cursorY", "startX", "startY", "tgtX", "tgtY", "寬", "高", "序號", "索引", "數量", "次數", "個數", "項數", "項目數",
    "店種", "陣營", "幀號", "動畫號", "道具", "事件號", "指令號", "stride", "目的跨距", "長度", "大小", "char_id",
    "amount", "camp", "line", "cmd", "glyph", "shadow", "bg", "off", "k", "r", "g", "選擇", "選中項", "階段", "列",
    "倍率", "選擇值", "距離門檻", "陣營篩選", "回復量"})


def type_of(name: str) -> str | None:
    """參數名 -> 'unit' / 'str' / 'ptr' / 'small' / None(沒有型別意涵,含 a2 這類佔位名:不在任何名單)。"""
    if name in UNIT_NAMES:
        return "unit"
    if name in STR_NAMES:
        return "str"
    if (name in PTR_NAMES or name.endswith(("*", "_ptr", "_out", "Buf")) or "指標" in name or "緩衝" in name):
        return "ptr"
    if name in SMALL_NAMES:
        return "small"
    return None


def violates(kind: str, v: int) -> bool:
    """值 v(32-bit 無號)是否與型別矛盾。"""
    small_neg = v >= 0xFFFF0000
    if kind == "unit":
        in_array = VC.UNIT_BASE <= v < VC.UNIT_BASE + 0x50 * 0x80 and (v - VC.UNIT_BASE) % 0x50 == 0
        return not (v <= 0x7F or in_array or small_neg)
    if kind in ("ptr", "str"):
        return 0 < v < 0x10000
    if kind == "small":
        return 0x100000 <= v and not small_neg
    raise ValueError(kind)


# 參數名的讀寫角色(續一百一十一):目的 = 函式寫進去;來源 = 函式從裡面讀。名單只收不含糊的名稱
# (buf / 緩衝區 在 dos_read 是寫、在 dos_write 是讀,不收)。字串參數一律是來源。
DST_ROLE = frozenset({"dst", "目的", "out", "輸出", "&輸出", "outBuf", "畫面緩衝"})
SRC_ROLE = frozenset({"src", "來源", "res", "img", "圖", "資源", "anim", "精靈", "font", "串流", "tmpl", "檔案影像",
                      "script"})
VGA_LO, VGA_HI = 0xA0000, 0xC0000   # VGA 視訊記憶體(DOS4GW 把低 1 MB 線性對映,畫面緩衝實機值 0xa0000)
REGION_SHARE = 0.5                   # 來源參數最常見值裡落在 VGA 的比例門檻


def role_of(name: str) -> str | None:
    """參數名 -> 'dst' / 'src' / None(角色不明)。"""
    if name in DST_ROLE or name.endswith(("_out", "輸出")):
        return "dst"
    if name in SRC_ROLE or type_of(name) == "str":
        return "src"
    return None


NUM = r"-?(?:0x[0-9a-fA-F]+|\d+)"
_NOT_RET_BEFORE = "返跳退送寫讀拿收來撤取換折輪迴撥找挑存設帶"
RET_HEAD = rf"(?<![{_NOT_RET_BEFORE}])(?:回傳|傳回|回)"
ELSE_HEAD = r"(?:否則|其餘|其他)(?:回傳|回)?"
_LIT_TAIL = r"(?![0-9A-Za-z_.])(?!\s*(?:時|則|就|的|者|且|個|次|格|筆|列|行|bytes|%|\+|\*|<|>|=))"
RET_LIT = re.compile(rf"(?P<head>{RET_HEAD}|{ELSE_HEAD})\s*(?P<vals>{NUM}(?:\s*(?:或|/|、)\s*{NUM})*){_LIT_TAIL}")
RET_WORD = re.compile(rf"{RET_HEAD}(?!\s*{NUM})(?!合|到|DOS|呼|應|復|饋|頭|去|來|顯|寫|存|收|放|圈|音|報|覆|歸|溯|退|程|路|點|位)")


def _lit(v: str) -> int:
    neg = v.startswith("-")
    n = int(v.lstrip("-"), 16) if "x" in v else int(v.lstrip("-"), 10)
    return (-n if neg else n) & 0xFFFFFFFF


def ret_claims(summary: str) -> tuple[set[int], bool]:
    """摘要的回傳字面值 -> (值集合(32-bit 無號), 是否列舉完)。

    「否則 / 其餘 N」只在同一句(以 。; 分句)前面已有「回 N」時才算回傳值 —— 否則「選中 0xc9 否則 0xcd」
    這種顏色、上限的「其餘 0x28」都會被當成回傳值。
    列舉完 = 有字面值、沒有非字面的回傳句(「回傳筆數」「回第一個…」),且字面值 ≥ 2 個或有「否則 / 其餘 N」。
    只有一個字面值(「…時回 1」)不算列舉完:C 的慣例是隱含的「否則 0」。
    """
    vals: set[int] = set()
    has_else = False
    for sent in re.split(r"[。;]", summary or ""):
        seen_ret = False
        for m in RET_LIT.finditer(sent):
            is_else = not m.group("head").startswith(("回", "傳"))
            if is_else and not seen_ret:
                continue
            vals |= {_lit(v) for v in re.findall(NUM, m.group("vals"))}
            has_else |= is_else
            seen_ret = True
    exhaustive = bool(vals) and not RET_WORD.search(summary or "") and (len(vals) >= 2 or has_else)
    return vals, exhaustive


# ---------------------------------------------------------------- 篩選

@dataclass
class Cand:
    addr: int
    name: str
    screen: str
    key: str
    detail: str
    evidence: list = field(default_factory=list)


@dataclass
class Screen:
    cands: list[Cand] = field(default_factory=list)
    denom: dict[str, int] = field(default_factory=dict)
    mixed_cleanup: list[int] = field(default_factory=list)


def _bump(sc: Screen, k: str) -> None:
    sc.denom[k] = sc.denom.get(k, 0) + 1


def screen(names: list[dict], profiles: dict[str, dict], code: bytes, base: int) -> Screen:
    """對每個有摘要、有實機剖面的函式跑實機紀錄的篩選(param_count / param_type / param_str / ret_unlisted / param_region)。"""
    sc = Screen()
    for x in names:
        a = int(x["addr"], 16)
        p = profiles.get(f"{a:#x}")
        if p is None:
            continue
        _bump(sc, "有摘要且被執行")
        summ, name = x.get("summary") or "", x["name"]
        params, n_sig = parse_sig(summ)
        sites = {int(c[1], 16): pushed_args(code, base, int(c[1], 16)) for c in p["callers"]
                 if c[1] and c[2] in ("direct", "thunk")}
        pushes = {v for v in sites.values() if v}
        pushed = pushes.pop() if len(pushes) == 1 else None
        if len(pushes) > 1:
            sc.mixed_cleanup.append(a)
        if params is not None:
            _bump(sc, "有參數列")
        # 1. 參數個數
        if n_sig is not None and pushed:
            _bump(sc, "param_count 可比")
            if n_sig != pushed:
                sc.cands.append(Cand(a, name, "param_count", "count",
                                     f"摘要參數列 {n_sig} 個,實機呼叫端都清 {pushed} 個堆疊參數",
                                     sorted(f"{s:#x}:{v}" for s, v in sites.items())))
        # 2 / 3. 參數型別、字串
        for k, pn in enumerate(params or [], 1):
            kind = type_of(pn)
            slot = (f"s{k}" if k <= pushed else None) if pushed else VC.param_slot(p["argc"], k)
            prm = p["params"].get(slot) if slot else None
            if kind is None or prm is None:
                continue
            _bump(sc, "param_type 可比")
            top = [(int(v, 16), c) for v, c in prm["top"]]
            covered = sum(c for _, c in top)
            bad = sum(c for v, c in top if violates(kind, v))
            if covered >= MIN_COVERED and bad >= VIOLATION_SHARE * covered:
                sc.cands.append(Cand(a, name, "param_type", slot,
                                     f"第 {k} 參數 {pn}({kind})在 {slot}:最常見值 {bad} / {covered} 次違反", prm["top"]))
            if kind == "str":
                _bump(sc, "param_str 可比")
                nonnull = sum(c for v, c in top if v)
                if nonnull >= MIN_COVERED and not prm.get("strings"):
                    sc.cands.append(Cand(a, name, "param_str", slot,
                                         f"第 {k} 參數 {pn}(字串)在 {slot}:{nonnull} 次非 NULL,從未讀到可列印字串",
                                         prm["top"]))
            if role_of(pn) == "src":
                _bump(sc, "param_region 可比")
                vga = sum(c for v, c in top if VGA_LO <= v < VGA_HI)
                if covered >= MIN_COVERED and vga >= MIN_COVERED and vga >= REGION_SHARE * covered:
                    sc.cands.append(Cand(a, name, "param_region", slot,
                                         f"第 {k} 參數 {pn}(來源)在 {slot}:最常見值 {vga} / {covered} 次是 VGA 視訊記憶體",
                                         prm["top"]))
        # 4. 回傳值
        vals, exhaustive = ret_claims(summ)
        if exhaustive and p["calls"]["returned"] >= MIN_RETURNED and p["ret"]["distinct"] <= 8:
            _bump(sc, "ret_unlisted 可比")
            obs = {int(v, 16) for v, _ in p["ret"]["top"]}
            extra = obs - vals
            if extra:
                sc.cands.append(Cand(a, name, "ret_unlisted", "ret",
                                     f"實機回傳 {sorted(hex(v) for v in extra)} 不在摘要列舉 {sorted(hex(v) for v in vals)}",
                                     p["ret"]["top"]))
    return sc


# ---------------------------------------------------------------- 參數讀寫角色(靜態,續一百一十一)

_MEM = re.compile(r"\[([a-z]{2,3})")
_STK = re.compile(r"\[(esp|ebp) \+ (0x[0-9a-f]+|\d+)\]")
_SUBREG = {"al": "eax", "ah": "eax", "ax": "eax", "bl": "ebx", "bh": "ebx", "bx": "ebx", "cl": "ecx", "ch": "ecx",
           "cx": "ecx", "dl": "edx", "dh": "edx", "dx": "edx", "si": "esi", "di": "edi", "bp": "ebp"}
_REG32 = frozenset({"eax", "ebx", "ecx", "edx", "esi", "edi", "ebp"})
_FIRST_READ = frozenset({"cmp", "test", "push", "call", "jmp", "bt", "out"})
_PTR_ARITH = frozenset({"add", "sub", "inc", "dec"})      # 指標加減常數 / 索引後仍指向同一塊
_STRING_OPS = ("stos", "movs", "lods", "cmps", "scas")


def _writes_first(m: str) -> bool:
    """指令 m 會不會寫第一個運算元。FPU 只有 fst / fist 類寫記憶體(fld [x] 是讀)。"""
    if m.startswith("f"):
        return m.startswith(("fst", "fist", "fbstp", "fnst", "fsave", "fnsave"))
    return m not in _FIRST_READ and not m.startswith(("j", "loop"))


def _stack_param(o: str, delta: int, ebp: int | None) -> int | None:
    """運算元 o 是堆疊參考 -> 第幾個參數(回傳位址 / 區域變數為 0);不是堆疊參考 -> None。

    `[ebp+X]` 只在 `mov ebp, esp` 之後(ebp 是框架)才算堆疊;ebp 當一般暫存器時是記憶體運算元。
    """
    m = _STK.search(o)
    if not m or (m.group(1) == "ebp" and ebp is None):
        return None
    off = int(m.group(2), 0) - (delta if m.group(1) == "esp" else ebp)
    return off // 4 if off >= 4 else 0


def param_uses(cg, target: int, entries: list[int], n: int, regconv: bool) -> dict[int, dict[str, int]] | None:
    """被呼叫端本體經由第 k 個參數(指標)讀 / 寫記憶體的次數 -> {k: {"r": 次, "w": 次}};走不出本體回 None。

    沿 `derive_native_argcounts.callee_argc` 走到的指令(附 ESP 位移與 ebp 框架基底),依位址順序追蹤
    「哪個暫存器目前裝著第 k 個參數」:
    - 載入:`mov r, [esp+X]` / `[ebp+X]` 換算成第 k 個(堆疊傳參);暫存器傳參時入口 eax / edx / ebx / ecx
      依序是第 1..n 個(Watcom)。`mov r2, r1` 複製;`add / sub / inc / dec r` 保留(指標移動);其他寫入 r 就失效;
      `call` 之後 eax / ecx / edx 失效;`popal` 全部失效。
    - 寫:`stos` / `movs` 的 edi,或第一個運算元是 `[r…]` 且指令會寫它。讀:`lods` / `movs` / `cmps` 的 esi、
      `cmps` / `scas` 的 edi,或其他 `[r…]` 運算元。`lea` 不算存取。
    依位址順序是近似(合流處不合併狀態);這是篩選,候選要人看反組譯。
    """
    trace: dict[int, tuple[int, int | None]] = {}
    if DNA.callee_argc(cg, target, entries, trace)[0] is None or not trace:
        return None
    state: dict[str, int] = {r: k for k, r in enumerate(VC.REG_ARGS[:n], 1)} if regconv else {}
    uses: dict[int, dict[str, int]] = {}

    def use(reg: str, kind: str) -> None:
        k = state.get(reg)
        if k:
            uses.setdefault(k, {"r": 0, "w": 0})[kind] += 1

    for a in sorted(trace):
        delta, ebp = trace[a]
        i = cg._insn(a)
        m = i.mnemonic.split()[-1]                     # `rep movsb` -> movsb
        ops = [o.strip() for o in i.op_str.split(",")] if i.op_str else []
        if m.startswith(_STRING_OPS) and not m.startswith(("movsx", "movzx")):
            if m.startswith(("stos", "movs")):
                use("edi", "w")
            if m.startswith(("lods", "movs", "cmps")):
                use("esi", "r")
            if m.startswith(("cmps", "scas")):
                use("edi", "r")
            if m.startswith("lods"):
                state.pop("eax", None)
            continue
        if m != "lea":
            for idx, o in enumerate(ops):
                mm = _MEM.search(o)
                if mm and _stack_param(o, delta, ebp) is None:
                    use(mm.group(1), "w" if idx == 0 and _writes_first(m) else "r")
        if m == "call":
            for r in ("eax", "ecx", "edx"):
                state.pop(r, None)
        elif m == "popal":
            state.clear()
        elif m in ("mul", "div", "idiv", "cdq") or (m == "imul" and len(ops) == 1):
            state.pop("eax", None)
            state.pop("edx", None)
        elif ops and _writes_first(m) and not _MEM.search(ops[0]):
            d = _SUBREG.get(ops[0], ops[0])
            src = ops[1] if len(ops) > 1 else ""
            k = _stack_param(src, delta, ebp) if m == "mov" else None
            if k is not None:
                if k and not regconv and k <= n:
                    state[d] = k
                else:
                    state.pop(d, None)
            elif m == "mov" and src in state:
                state[d] = state[src]
            elif m == "xchg" and src in _REG32 and d in _REG32:
                sv, dv = state.pop(src, None), state.pop(d, None)
                if sv:
                    state[d] = sv
                if dv:
                    state[src] = dv
            elif not (m in _PTR_ARITH and d == ops[0]):
                state.pop(d, None)
    return uses


def call_cleanups(code: bytes, base: int, entries: set[int]) -> dict[int, set[int]]:
    """EXE 裡所有 `call rel32`(目標是已知入口)的清堆疊個數 -> {目標: {非 0 個數}}。

    與實機剖面無關:未執行的函式也有。逐位元組找 E8 可能落在指令中段,只收目標是已知入口的。
    """
    out: dict[int, set[int]] = {}
    for i in range(len(code) - 5):
        if code[i] != 0xE8:
            continue
        t = (base + i + 5 + int.from_bytes(code[i + 1:i + 5], "little", signed=True)) & 0xFFFFFFFF
        if t in entries:
            n = pushed_args(code, base, base + i)
            if n:
                out.setdefault(t, set()).add(n)
    return out


def role_convention(n: int, cleanups: set[int], argc: int | None) -> str | None:
    """摘要 n 個參數的傳法 -> 'stack' / 'reg' / None(對不上或不明,不比)。

    呼叫端清的個數唯一且 == n -> 堆疊;沒有清堆疊資訊時,本體讀 n 個堆疊參數 -> 堆疊、一個都不讀且 n ≤ 4 ->
    Watcom 暫存器。其他(個數矛盾、混合傳參)不猜 —— 個數矛盾由 param_count 處理。
    """
    if len(cleanups) > 1:
        return None
    if cleanups:
        return "stack" if next(iter(cleanups)) == n else None
    if argc == n and n:
        return "stack"
    if argc == 0 and 0 < n <= 4:
        return "reg"
    return None


def screen_roles(sc: Screen, names: list[dict], cg, entries: list[int], argc: dict[int, int | None],
                 cleanups: dict[int, set[int]]) -> None:
    """`param_role`:參數名是目的,本體經由它只讀不寫;或參數名是來源,本體經由它寫入 -> 候選。

    不需要實機紀錄:涵蓋所有有參數列的函式(含沒執行到的)。dst / src 對調時兩個參數都會觸發。
    """
    for x in names:
        params, n = parse_sig(x.get("summary") or "")
        roles = {k: role_of(pn) for k, pn in enumerate(params or [], 1)}
        if not n or not any(roles.values()):
            continue
        a = int(x["addr"], 16)
        conv = role_convention(n, cleanups.get(a, set()), argc.get(a))
        uses = param_uses(cg, a, entries, n, conv == "reg") if conv else None
        if uses is None:
            continue
        _bump(sc, "param_role 函式")
        for k, role in roles.items():
            u = uses.get(k)
            if not role or not u:
                continue
            _bump(sc, "param_role 可比")
            pn = params[k - 1]
            if role == "dst" and not u["w"]:
                sc.cands.append(Cand(a, x["name"], "param_role", f"p{k}",
                                     f"第 {k} 參數 {pn}(目的):本體經由它讀 {u['r']} 次、從未寫入", [u]))
            elif role == "src" and u["w"]:
                sc.cands.append(Cand(a, x["name"], "param_role", f"p{k}",
                                     f"第 {k} 參數 {pn}(來源):本體經由它寫入 {u['w']} 次", [u]))


# ---------------------------------------------------------------- 核對結論

def load_review(doc: dict, names: dict[int, str]) -> tuple[dict[tuple[int, str, str], dict], list[str]]:
    """review 檔 -> ({(addr, screen, key): 條目}, 錯誤)。有錯的條目不採用。"""
    out: dict[tuple[int, str, str], dict] = {}
    errs: list[str] = []
    for i, r in enumerate(doc.get("reviews", [])):
        try:
            a = int(r["addr"], 16)
            k = (a, r["screen"], r["key"])
            verdict, reason = r["verdict"], r["reason"]
        except (KeyError, TypeError, ValueError) as ex:
            errs.append(f"#{i}:欄位不全或格式錯({ex!r})")
            continue
        if r["screen"] not in SCREENS:
            errs.append(f"#{i} {r['addr']}:screen {r['screen']!r} 不認得")
        elif verdict not in VERDICTS:
            errs.append(f"#{i} {r['addr']}:verdict {verdict!r} 不認得")
        elif not str(reason).strip():
            errs.append(f"#{i} {r['addr']}:沒有理由")
        elif a not in names:
            errs.append(f"#{i} {r['addr']}:不在 function_names.json")
        elif r.get("name") != names.get(a):
            errs.append(f"#{i} {r['addr']}:name {r.get('name')!r} 與登錄 {names.get(a)!r} 不同")
        elif k in out:
            errs.append(f"#{i} {r['addr']} {r['screen']} {r['key']}:重複")
        else:
            out[k] = r
    return out, errs


def reconcile(cands: list[Cand], reviews: dict[tuple[int, str, str], dict]) -> tuple[list[Cand], list[str], int]:
    """(未核對的候選, 錯誤, 已核對 not_error 數)。fixed 仍觸發、not_error 沒有對應候選都算錯誤。"""
    keys = {(c.addr, c.screen, c.key) for c in cands}
    pending, errs, ok = [], [], 0
    for c in cands:
        r = reviews.get((c.addr, c.screen, c.key))
        if r is None:
            pending.append(c)
        elif r["verdict"] == "fixed":
            errs.append(f"{c.addr:#x} {c.name} {c.screen} {c.key}:review 記已改正,仍觸發({c.detail})")
        else:
            ok += 1
    for (a, s, k), r in sorted(reviews.items()):
        if r["verdict"] == "not_error" and (a, s, k) not in keys:
            errs.append(f"{a:#x} {r['name']} {s} {k}:review 記 not_error,但已沒有這個候選(過期,請刪)")
    return pending, errs, ok


# ---------------------------------------------------------------- 主程式

def run(review_path: Path) -> tuple[Screen, list[Cand], list[str], dict, list[dict]]:
    st = VC.load_static()
    names = json.loads(NAMES_JSON.read_text(encoding="utf-8"))["names"]
    profiles = json.loads(PROFILES_JSON.read_text(encoding="utf-8"))["functions"]
    sc = screen(names, profiles, st.code, st.base)
    from callgraph_le import CG
    import verify_address_claim_coverage as CC
    screen_roles(sc, names, CG(CC.EXE), st.entries, st.argc, call_cleanups(st.code, st.base, set(st.entries)))
    reviews, errs = load_review(json.loads(review_path.read_text(encoding="utf-8")),
                                {int(x["addr"], 16): x["name"] for x in names})
    pending, rerrs, _ = reconcile(sc.cands, reviews)
    return sc, pending, errs + rerrs, reviews, names


def report(sc: Screen, pending: list[Cand], errs: list[str], reviews: dict) -> list[str]:
    lines = ["分母:" + "、".join(f"{k} {v}" for k, v in sc.denom.items())]
    by = {s: sum(c.screen == s for c in sc.cands) for s in SCREENS}
    lines.append("候選:" + "、".join(f"{s} {n}" for s, n in by.items()) + f"(共 {len(sc.cands)})")
    nfix = sum(r["verdict"] == "fixed" for r in reviews.values())
    lines.append(f"review:已改正 {nfix}、核對後非錯誤 {sum(r['verdict'] == 'not_error' for r in reviews.values())};"
                 f"未核對 {len(pending)}")
    if sc.mixed_cleanup:
        lines.append(f"呼叫端清堆疊個數不一致(param_count 不比):{len(sc.mixed_cleanup)} 個函式")
    for c in pending:
        lines.append(f"PENDING {c.screen} {c.addr:#x} {c.name} [{c.key}]:{c.detail}")
    for e in errs:
        lines.append(f"FAIL review:{e}")
    return lines


def exit_code(pending: list[Cand], errs: list[str]) -> int:
    """rc:有未核對的候選或 review 錯誤 -> 1,否則 0。"""
    return 1 if pending or errs else 0


def cand_doc(sc: Screen, reviews: dict, names: list[dict]) -> list[dict]:
    summ = {int(x["addr"], 16): x.get("summary") for x in names}
    return [{"addr": f"{c.addr:#x}", "name": c.name, "screen": c.screen, "key": c.key, "detail": c.detail,
             "evidence": c.evidence, "summary": summ.get(c.addr),
             "review": reviews.get((c.addr, c.screen, c.key))} for c in sc.cands]


# ---------------------------------------------------------------- selftest

def selftest() -> int:
    fails: list[str] = []

    def chk(label: str, got, want) -> None:
        ok = got == want
        print(f"    {'PASS' if ok else 'FAIL'}: {label}" + ("" if ok else f"  got={got!r} want={want!r}"))
        if not ok:
            fails.append(label)

    print("[1] 參數列")
    chk("一般", parse_sig("(dst, stride, res):…"), (["dst", "stride", "res"], 3))
    chk("空參數列", parse_sig("():…"), ([], 0))
    chk("N 個參數", parse_sig("(3 個參數) …"), ([], 3))
    chk("可變參數不比個數", parse_sig("(fmt, ...) …")[1], None)
    chk("暫存器寫法不比個數", parse_sig("(eax = ptr, edx = 段) …")[1], None)
    chk("沒有參數列", parse_sig("讀 BIOS 計時器。無參數。"), (None, None))
    chk("參數列不在開頭不算", parse_sig("Watcom CRT 近堆配置(size)")[0], None)

    print("[2] 參數名型別")
    chk("unit", type_of("單位"), "unit")
    chk("str 先於 ptr", type_of("檔名"), "str")
    chk("ptr 名單", type_of("dst"), "ptr")
    chk("ptr 字尾 *", type_of("線性位址*"), "ptr")
    chk("ptr 字尾 _ptr", type_of("stat_ptr"), "ptr")
    chk("ptr 含「緩衝」", type_of("調色盤緩衝"), "ptr")
    chk("small", type_of("x"), "small")
    chk("佔位名 a3 不判", type_of("a3"), None)
    chk("不認得的不判", type_of("portrait"), None)

    print("[3] 型別違反")
    U = VC.UNIT_BASE
    chk("unit:序號 0x19 可", violates("unit", 0x19), False)
    chk("unit:0x7f 可(上限含)", violates("unit", 0x7F), False)
    chk("unit:0x80 違反", violates("unit", 0x80), True)
    chk("unit:陣列第 3 筆可", violates("unit", U + 3 * 0x50), False)
    chk("unit:陣列內未對齊違反", violates("unit", U + 3 * 0x50 + 4), True)
    chk("unit:畫面緩衝違反", violates("unit", 0x245018), True)
    chk("unit:-1 可", violates("unit", 0xFFFFFFFF), False)
    chk("ptr:NULL 可", violates("ptr", 0), False)
    chk("ptr:0xffff 違反", violates("ptr", 0xFFFF), True)
    chk("ptr:0x10000 可", violates("ptr", 0x10000), False)
    chk("small:0xfffff 可", violates("small", 0xFFFFF), False)
    chk("small:0x100000 違反", violates("small", 0x100000), True)
    chk("small:-2 可", violates("small", 0xFFFFFFFE), False)

    print("[4] 回傳句")
    chk("回 0 或 1 -> 列舉完", ret_claims("相等回 0 或 1。"), ({0, 1}, True))
    chk("回 1,否則 0 -> 列舉完", ret_claims("出現在前 6 bytes 內回 1,否則 0"), ({0, 1}, True))
    chk("單一字面值不算列舉完", ret_claims("head != tail 時回 1;不取走按鍵"), ({1}, False))
    chk("否則 -1 算列舉完", ret_claims("條件成立回 1,否則回 -1"), ({1, 0xFFFFFFFF}, True))
    chk("有「回傳筆數」-> 不算列舉完", ret_claims("沒有回 0、有回 1,回傳筆數")[1], False)
    chk("回第一個… -> 不算列舉完", ret_claims("回第一個符合的單位索引,沒有回 -1")[1], False)
    chk("返回 0x1234 不是回傳", ret_claims("返回 0x1234 後")[0], set())
    chk("設回 1 不是回傳", ret_claims("再設回 1")[0], set())
    chk("被呼叫端「回 0 的」不算", ret_claims("且 unit_inactive 回 0 的單位數")[0], set())
    chk("…回 0 時 是條件不算", ret_claims("load_res 回 0 時跳過")[0], set())
    chk("公式 0x61646 + … 不算", ret_claims("回傳 0x61646 + selector*0x14")[0], set())
    chk("回合 不算", ret_claims("第 3 回合")[0], set())
    chk("十六進位", ret_claims("a==b 回 0x1f、a<b 回 0x2a、a>b 回 0x77")[0], {0x1F, 0x2A, 0x77})
    chk("沒有回傳的「否則 0xcd」不算", ret_claims("選中 0xc9 否則 0xcd")[0], set())
    chk("別句的回傳不帶「其餘」", ret_claims("找到回 1。上限 0x63,其餘 0x28")[0], {1})

    print("[5] 清堆疊個數")
    code = bytes.fromhex("e800000000" "83c408" "e800000000" "81c410000000" "e800000000" "90" "c3" "ff15" "00000000"
                         "e800000000" "89c2" "83c40c"                 # 0x1020:mov edx, eax 後清 3 個
                         "e800000000" "89c2" "8944241c" "83c418"      # 0x102a:兩條 mov 後清 6 個
                         "e800000000" "89c2" "89c3" "89c1" "83c404"   # 0x1038:三條 mov,超過 2 條不跳 -> 0
                         "e800000000" "89e5" "83c408"                 # 0x1046:mov ebp, esp 會動到 esp 的讀法,不跳
                         + "90" * 32)
    chk("add esp, 8 -> 2", pushed_args(code, 0x1000, 0x1000), 2)
    chk("add esp, imm32 0x10 -> 4", pushed_args(code, 0x1000, 0x1008), 4)
    chk("沒有清堆疊 -> 0", pushed_args(code, 0x1000, 0x1013), 0)
    chk("不是 E8 -> None", pushed_args(code, 0x1000, 0x101A), None)
    chk("超出範圍 -> None", pushed_args(code, 0x1000, 0x0FFF), None)
    chk("跳過 mov edx, eax", pushed_args(code, 0x1000, 0x1020), 3)
    chk("跳過 mov r, eax 與 mov [esp+d8], eax", pushed_args(code, 0x1000, 0x102A), 6)
    chk("最多跳 2 條", pushed_args(code, 0x1000, 0x1038), 0)
    chk("mov ebp, esp 不跳", pushed_args(code, 0x1000, 0x1046), 0)

    print("[6] 篩選(合成剖面)")
    ccode = bytearray(b"\x90" * 0x80)
    for at, n in ((0x00, 8), (0x10, 8), (0x20, 12), (0x30, 0)):
        ccode[at:at + 5] = b"\xe8\0\0\0\0"
        if n:
            ccode[at + 5:at + 8] = bytes((0x83, 0xC4, n))

    def prof(callers, params, ret_top, returned=50, argc=2):
        return {"argc": argc, "callers": callers, "params": params,
                "calls": {"returned": returned}, "ret": {"distinct": len(ret_top), "top": ret_top}}

    two = [[None, "0x2000", "direct", 5], [None, "0x2010", "direct", 5]]
    names = [{"addr": "0x100", "name": "f_swap", "summary": "(x, dst):…"},
             {"addr": "0x200", "name": "f_count", "summary": "(a, b, c):…"},
             {"addr": "0x300", "name": "f_ok", "summary": "(dst, x):…回 0 或 1"},
             {"addr": "0x400", "name": "f_ret", "summary": "(dst, x):成功回 1,否則 0"},
             {"addr": "0x500", "name": "f_str", "summary": "(檔名, x):…"},
             {"addr": "0x600", "name": "f_mixed", "summary": "(a, b, c):…"},
             {"addr": "0x700", "name": "f_border", "summary": "(x, y):…"},
             {"addr": "0x800", "name": "f_unrun", "summary": "(x, dst):…"}]
    ptr_top, small_top = [["0x245018", 10]], [["0x140", 10]]
    profiles = {
        "0x100": prof(two, {"s1": {"top": ptr_top}, "s2": {"top": small_top}}, [["0x0", 50]]),
        "0x200": prof(two, {"s1": {"top": small_top}, "s2": {"top": small_top}}, [["0x0", 50]]),
        "0x300": prof(two, {"s1": {"top": ptr_top}, "s2": {"top": small_top}}, [["0x0", 25], ["0x1", 25]]),
        "0x400": prof(two, {"s1": {"top": ptr_top}, "s2": {"top": small_top}}, [["0x0", 25], ["0xffffffff", 25]]),
        "0x500": prof(two, {"s1": {"top": ptr_top}, "s2": {"top": small_top}}, [["0x0", 50]]),
        "0x600": prof([[None, "0x2000", "direct", 1], [None, "0x2020", "direct", 1]],
                      {"s1": {"top": small_top}}, [["0x0", 50]]),
        # 4 / 5 違反 = 80%(門檻剛好成立)與 x 第 2 參數 3 / 4 = 75%(不成立)
        "0x700": prof(two, {"s1": {"top": [["0x245018", 4], ["0x1", 1]]},
                            "s2": {"top": [["0x245018", 3], ["0x1", 1]]}}, [["0x0", 50]]),
    }
    sc = screen(names, profiles, bytes(ccode), 0x2000)
    got = sorted((c.addr, c.screen, c.key) for c in sc.cands)
    want = sorted([(0x100, "param_type", "s1"), (0x100, "param_type", "s2"), (0x200, "param_count", "count"),
                   (0x400, "ret_unlisted", "ret"), (0x500, "param_str", "s1"), (0x700, "param_type", "s1")])
    chk("候選恰為預期(順序對調 2、個數 1、列舉外回傳 1、無字串 1、門檻邊界 1)", got, want)
    chk("呼叫端清堆疊不一致的不比個數,另列", sc.mixed_cleanup, [0x600])
    sc6 = screen([{"addr": "0x200", "name": "f", "summary": "(a, b, c):…"}],
                 {"0x200": prof(two + [[None, "0x2030", "direct", 1]], {}, [["0x0", 9]])}, bytes(ccode), 0x2000)
    chk("沒清堆疊的呼叫端(0)不算不一致,取唯一的非 0 值", ([c.screen for c in sc6.cands], sc6.mixed_cleanup),
        (["param_count"], []))
    chk("未執行的函式不進分母", sc.denom.get("有摘要且被執行"), 7)
    chk("param_count 分母 = 呼叫端一致且 > 0 的(0x600 除外)", sc.denom.get("param_count 可比"), 6)
    sc2 = screen(names, {"0x300": prof(two, {"s1": {"top": ptr_top}}, [["0x0", 2], ["0x5", 2]], returned=4)},
                 bytes(ccode), 0x2000)
    chk("返回次數 < 5 不比回傳", [c.screen for c in sc2.cands], [])
    nine = [[f"{v:#x}", 5] for v in range(9)]
    sc3 = screen(names, {"0x400": prof(two, {}, nine)}, bytes(ccode), 0x2000)
    chk("回傳相異值 > 8(不完整)不比", [c.screen for c in sc3.cands], [])
    sc4 = screen([{"addr": "0x100", "name": "f", "summary": "(x, dst):…"}],
                 {"0x100": prof([[None, "0x2030", "direct", 5]], {"eax": {"top": ptr_top}}, [["0x0", 9]], argc=0)},
                 bytes(ccode), 0x2000)
    chk("沒清堆疊、argc 0 -> 用暫存器位置", [(c.screen, c.key) for c in sc4.cands], [("param_type", "eax")])
    sc5 = screen([{"addr": "0x500", "name": "f", "summary": "(檔名):…"}],
                 {"0x500": prof(two[:1], {"s1": {"top": ptr_top, "strings": [["A.DAT", 10]]}}, [["0x0", 9]])},
                 bytes(ccode), 0x2000)
    chk("有字串就不報 param_str", [c.screen for c in sc5.cands if c.screen == "param_str"], [])
    sc7 = screen([{"addr": "0x500", "name": "f", "summary": "(檔名, x):…"}],
                 {"0x500": prof(two[:1], {"s1": {"top": [["0x0", 9]]}, "s2": {"top": [["0x245018", 2]]}}, [["0x0", 9]])},
                 bytes(ccode), 0x2000)
    chk("字串參數全是 NULL 不報 param_str;違反次數 2 < 3 不判型別", [c.screen for c in sc7.cands], [])

    print("[7] review 對照")
    nm = {0x100: "f_swap", 0x200: "f_count", 0x900: "f_gone"}
    doc = {"reviews": [
        {"addr": "0x100", "name": "f_swap", "screen": "param_type", "key": "s1", "verdict": "not_error", "reason": "r"},
        {"addr": "0x100", "name": "f_swap", "screen": "param_type", "key": "s2", "verdict": "fixed", "reason": "r"},
        {"addr": "0x900", "name": "f_gone", "screen": "param_type", "key": "s1", "verdict": "not_error", "reason": "r"},
        {"addr": "0x200", "name": "f_count", "screen": "param_count", "key": "count", "verdict": "maybe", "reason": "r"},
        {"addr": "0x200", "name": "f_count", "screen": "param_count", "key": "count", "verdict": "fixed", "reason": " "},
        {"addr": "0x200", "name": "wrong", "screen": "param_count", "key": "count", "verdict": "fixed", "reason": "r"},
        {"addr": "0x300", "name": "x", "screen": "param_count", "key": "count", "verdict": "fixed", "reason": "r"},
        {"addr": "0x200", "name": "f_count", "screen": "nope", "key": "count", "verdict": "fixed", "reason": "r"},
        {"addr": "0x100", "name": "f_swap", "screen": "param_type", "key": "s1", "verdict": "fixed", "reason": "r"},
        {"addr": "0x100", "screen": "param_type"},
    ]}
    rv, errs = load_review(doc, nm)
    chk("load_review 錯誤 7 筆(verdict、理由、名稱、不在登錄、screen、重複、欄位)", len(errs), 7)
    chk("不在登錄的報「不在 function_names.json」", sum("不在 function_names.json" in e for e in errs), 1)
    chk("採用 3 筆", sorted(rv), [(0x100, "param_type", "s1"), (0x100, "param_type", "s2"), (0x900, "param_type", "s1")])
    pend, rerrs, ok = reconcile(sc.cands, rv)
    chk("not_error 對上的不算未核對", ok, 1)
    chk("未核對 = 其他 4 個候選", len(pend), 4)
    chk("fixed 仍觸發 -> 錯誤", any("仍觸發" in e for e in rerrs), True)
    chk("not_error 沒有候選 -> 過期錯誤", any("過期" in e and "0x900" in e for e in rerrs), True)
    chk("reconcile 錯誤恰 2 筆", len(rerrs), 2)
    lines = report(sc, pend, errs + rerrs, rv)
    chk("報告列出 PENDING 行", sum(ln.startswith("PENDING") for ln in lines), 4)
    chk("報告列出 FAIL 行", sum(ln.startswith("FAIL") for ln in lines), 9)
    chk("rc:有未核對 -> 1", exit_code(pend, []), 1)
    chk("rc:只有 review 錯誤 -> 1", exit_code([], ["x"]), 1)
    chk("rc:都沒有 -> 0", exit_code([], []), 0)

    print("[8] 真實檔")
    real_names = json.loads(NAMES_JSON.read_text(encoding="utf-8"))["names"]
    _, real_errs = load_review(json.loads(REVIEW_JSON.read_text(encoding="utf-8")),
                               {int(x["addr"], 16): x["name"] for x in real_names})
    chk("review 檔結構零錯誤", real_errs, [])
    st = VC.load_static()
    real_prof = json.loads(PROFILES_JSON.read_text(encoding="utf-8"))["functions"]
    # draw_stat_bar 0x18795 的兩個呼叫端(0x18cde / 0x18cfa)之後都是 add esp, 0x14
    chk("真實 EXE:draw_stat_bar 呼叫端清 5 個參數",
        {pushed_args(st.code, st.base, int(c[1], 16)) for c in real_prof["0x18795"]["callers"]}, {5})
    real = screen(real_names, real_prof, st.code, st.base)
    chk("真實篩選:分母非零(有東西可比)", all(real.denom.get(k, 0) > 0 for k in
                                         ("param_count 可比", "param_type 可比", "param_str 可比", "ret_unlisted 可比",
                                          "param_region 可比")), True)
    chk("真實篩選:VGA 來源命中 decode_image_with_header 的 s4(畫面擷取,review 記 not_error)",
        [(c.addr, c.key) for c in real.cands if c.screen == "param_region"], [(0x4ECBF, "s4")])

    print("[9] 參數讀寫角色:名稱與運算元")
    chk("dst 名單", role_of("目的"), "dst")
    chk("字尾 _out", role_of("idx_out"), "dst")
    chk("字尾 輸出", role_of("結尾指標輸出"), "dst")
    chk("src 名單", role_of("精靈"), "src")
    chk("字串參數是來源", role_of("檔名"), "src")
    chk("buf 不判", role_of("buf"), None)
    chk("fld 是讀", _writes_first("fld"), False)
    chk("fstp 是寫", _writes_first("fstp"), True)
    chk("cmp 是讀", _writes_first("cmp"), False)
    chk("jne 不寫", _writes_first("jne"), False)
    chk("mov 是寫", _writes_first("mov"), True)
    chk("[esp+8] 位移 4 -> 第 1 個", _stack_param("dword ptr [esp + 8]", 4, None), 1)
    chk("[esp+4] 位移 8 -> 區域變數 0", _stack_param("dword ptr [esp + 4]", 8, None), 0)
    chk("[ebp+0xc] 框架基底 0 -> 第 3 個", _stack_param("dword ptr [ebp + 0xc]", 0, 0), 3)
    chk("ebp 不是框架 -> 不是堆疊", _stack_param("byte ptr [ebp + 0x20]", 0, None), None)
    chk("一般記憶體 -> 不是堆疊", _stack_param("byte ptr [eax + 4]", 0, None), None)

    print("[10] 參數讀寫角色:合成本體")

    class _I:
        def __init__(self, address: int, mnemonic: str, op_str: str) -> None:
            self.address, self.mnemonic, self.op_str, self.size = address, mnemonic, op_str, 1

    class _G:
        def __init__(self, bodies: dict[int, list[tuple[str, str]]]) -> None:
            self.m = {at + k: _I(at + k, mn, op) for at, body in bodies.items() for k, (mn, op) in enumerate(body)}

        def _insn(self, a: int):
            return self.m.get(a)

    def U(body: list[tuple[str, str]], n: int = 2, regconv: bool = False):
        return param_uses(_G({0: body}), 0, [], n, regconv)

    P1, P2 = ("mov", "edi, dword ptr [esp + 4]"), ("mov", "esi, dword ptr [esp + 8]")
    RET = ("ret", "")
    W1, R1 = {"r": 0, "w": 1}, {"r": 1, "w": 0}
    chk("rep movsb:edi 寫、esi 讀", U([P1, P2, ("rep movsb", "byte ptr es:[edi], byte ptr [esi]"), RET]), {1: W1, 2: R1})
    chk("push 後換算位移", U([("push", "ebx"), ("mov", "eax, dword ptr [esp + 8]"), ("mov", "byte ptr [eax], 1"),
                         ("pop", "ebx"), RET]), {1: W1})
    chk("暫存器複製", U([("mov", "eax, dword ptr [esp + 4]"), ("mov", "edx, eax"), ("mov", "ecx, dword ptr [edx + 4]"),
                    RET]), {1: R1})
    chk("覆寫後失效", U([("mov", "eax, dword ptr [esp + 4]"), ("mov", "eax, 5"), ("mov", "byte ptr [eax], 1"), RET]), {})
    chk("寫子暫存器也失效", U([("mov", "eax, dword ptr [esp + 4]"), ("mov", "al, 1"), ("mov", "byte ptr [eax], 0"), RET]), {})
    chk("add 常數保留(指標移動)", U([("mov", "esi, dword ptr [esp + 4]"), ("add", "esi, 4"),
                                ("mov", "al, byte ptr [esi]"), RET]), {1: R1})
    chk("shl 失效", U([("mov", "esi, dword ptr [esp + 4]"), ("shl", "esi, 2"), ("mov", "al, byte ptr [esi]"), RET]), {})
    chk("call 之後 eax 失效", U([("mov", "eax, dword ptr [esp + 4]"), ("call", "0x9999"), ("mov", "byte ptr [eax], 1"),
                            RET]), {})
    chk("call 之後 esi 保留", U([("mov", "esi, dword ptr [esp + 4]"), ("call", "0x9999"), ("mov", "byte ptr [esi], 1"),
                            RET]), {1: W1})
    chk("ebp 框架 [ebp+8] 是第 1 個", U([("push", "ebp"), ("mov", "ebp, esp"), ("mov", "edi, dword ptr [ebp + 8]"),
                                     ("stosb", "byte ptr es:[edi], al"), ("pop", "ebp"), RET]), {1: W1})
    chk("ebp 當一般暫存器:[ebp+0x20] 是記憶體", U([("mov", "ebp, dword ptr [esp + 4]"),
                                               ("mov", "byte ptr [ebp + 0x20], 1"), RET]), {1: W1})
    chk("暫存器傳參:入口 eax / edx 是第 1 / 2 個", U([("mov", "byte ptr [edx], 1"), ("mov", "cl, byte ptr [eax]"), RET],
                                               regconv=True), {1: R1, 2: W1})
    chk("暫存器傳參時堆疊載入不對應", U([("mov", "esi, dword ptr [esp + 4]"), ("mov", "byte ptr [esi], 1"), RET],
                                  n=1, regconv=True), {})
    chk("lea 不算存取、cmp 是讀", U([("mov", "eax, dword ptr [esp + 4]"), ("lea", "ecx, [eax + 4]"),
                                ("cmp", "byte ptr [eax], 0"), RET]), {1: R1})
    chk("xchg 交換", U([("mov", "eax, dword ptr [esp + 4]"), ("xchg", "eax, ebx"), ("mov", "byte ptr [ebx], 1"), RET]),
        {1: W1})
    chk("popal 全部失效", U([("mov", "edi, dword ptr [esp + 4]"), ("popal", ""), ("stosb", "byte ptr es:[edi], al"), RET]),
        {})
    chk("lods 之後 eax 失效", U([("mov", "eax, dword ptr [esp + 4]"), ("lodsb", "al, byte ptr [esi]"),
                             ("mov", "byte ptr [eax], 1"), RET]), {})
    chk("fld 讀、fstp 寫", U([("mov", "eax, dword ptr [esp + 4]"), ("fld", "dword ptr [eax]"),
                          ("fstp", "dword ptr [eax + 4]"), RET]), {1: {"r": 1, "w": 1}})
    chk("超過 n 的參數不對應", U([("mov", "eax, dword ptr [esp + 8]"), ("mov", "byte ptr [eax], 1"), RET], n=1), {})
    chk("區域變數不對應", U([("sub", "esp, 8"), ("mov", "eax, dword ptr [esp + 4]"), ("mov", "byte ptr [eax], 1"),
                       ("add", "esp, 8"), RET]), {})
    chk("mul 之後 eax 失效", U([("mul", "ebx"), ("mov", "byte ptr [eax], 1"), RET], regconv=True), {})
    chk("cmpsb 兩邊都讀", U([P2, P1, ("repe cmpsb", "byte ptr [esi], byte ptr es:[edi]"), RET]), {1: R1, 2: R1})
    chk("movsx 不是字串指令", U([P2, P1, ("movsx", "eax, byte ptr [esi]"), RET]), {2: R1})
    chk("沒有乾淨出口 -> None", U([("mov", "eax, dword ptr [esp + 4]"), ("push", "eax"), RET]), None)

    print("[11] 傳參方式、清堆疊、篩選")
    chk("清 4 個、摘要 4 個 -> 堆疊", role_convention(4, {4}, 2), "stack")
    chk("清 3 個、摘要 4 個 -> 不比", role_convention(4, {3}, 4), None)
    chk("清堆疊個數不一致 -> 不比", role_convention(2, {2, 3}, 2), None)
    chk("無清堆疊、argc == n -> 堆疊", role_convention(4, set(), 4), "stack")
    chk("無清堆疊、argc 0、n 2 -> 暫存器", role_convention(2, set(), 0), "reg")
    chk("argc 0 但 n 5 -> 不比", role_convention(5, set(), 0), None)
    chk("argc 不明 -> 不比", role_convention(2, set(), None), None)
    chk("argc 3、n 2 -> 不比", role_convention(2, set(), 3), None)
    cc = bytearray(b"\x90" * 0x40)
    for at, rel, n in ((0x00, 0x3B, 8), (0x10, 0x2B, 0), (0x20, 0x10, 12)):
        cc[at:at + 5] = b"\xe8" + rel.to_bytes(4, "little")
        if n:
            cc[at + 5:at + 8] = bytes((0x83, 0xC4, n))
    # 0x1000 -> 0x1040(入口,清 2)、0x1010 -> 0x1040(不清)、0x1020 -> 0x1035(不是入口)
    chk("call_cleanups:只收已知入口、只收非 0", call_cleanups(bytes(cc), 0x1000, {0x1040}), {0x1040: {2}})
    body = [P1, P2, ("rep movsb", "byte ptr es:[edi], byte ptr [esi]"), RET]
    rmw = [P1, ("mov", "al, byte ptr [edi]"), ("mov", "byte ptr [edi + 1], al"), RET]   # 目的先讀後寫
    g = _G({0x0: body, 0x100: body, 0x200: body, 0x400: rmw})
    rnames = [{"addr": "0x0", "name": "f_ok", "summary": "(dst, src):…"},
              {"addr": "0x100", "name": "f_swap", "summary": "(src, dst):…"},
              {"addr": "0x200", "name": "f_skip", "summary": "(dst, src):…"},
              {"addr": "0x300", "name": "f_norole", "summary": "(x, y):…"},
              {"addr": "0x400", "name": "f_rmw", "summary": "(dst):…"}]
    rsc = Screen()
    screen_roles(rsc, rnames, g, [0x0, 0x100, 0x200, 0x300, 0x400], {0x0: 2, 0x100: 2, 0x200: 2, 0x400: 1},
                 {0x200: {3}})
    chk("對調的兩個參數都觸發、正確的與先讀後寫的目的不觸發", sorted((c.addr, c.key) for c in rsc.cands),
        [(0x100, "p1"), (0x100, "p2")])
    chk("param_role 分母(清堆疊個數對不上的不比)", (rsc.denom.get("param_role 函式"), rsc.denom.get("param_role 可比")), (3, 5))
    vga_names = [{"addr": "0x100", "name": "f", "summary": "(src, dst):…"}]

    def vga_prof(src_top, dst_top):
        return {"0x100": prof(two, {"s1": {"top": src_top}, "s2": {"top": dst_top}}, [["0x0", 9]])}

    def vga_keys(src_top, dst_top=(("0xa0000", 9),)):
        return [c.key for c in screen(vga_names, vga_prof([list(t) for t in src_top], [list(t) for t in dst_top]),
                                      bytes(ccode), 0x2000).cands if c.screen == "param_region"]

    chk("來源 6 / 10 在 VGA -> 候選;目的在 VGA 不算", vga_keys((("0xa0000", 6), ("0x245018", 4))), ["s1"])
    chk("來源 5 / 10(門檻剛好)-> 候選", vga_keys((("0xa0000", 5), ("0x245018", 5))), ["s1"])
    chk("來源 4 / 10 -> 不報", vga_keys((("0xa0000", 4), ("0x245018", 6))), [])
    chk("VGA 次數 2 < 3 -> 不報", vga_keys((("0xa0000", 2),)), [])
    chk("合計 3 次、VGA 2 次(比例 67%)-> 不報", vga_keys((("0xa0000", 2), ("0x245018", 1))), [])
    chk("0xbffff 算 VGA", vga_keys((("0xbffff", 9),)), ["s1"])
    chk("0xc0000 不算 VGA", vga_keys((("0xc0000", 9),)), [])
    chk("0xa0000 算 VGA、0x9ffff 不算", (vga_keys((("0xa0000", 9),)), vga_keys((("0x9ffff", 9),))), (["s1"], []))

    print("[12] 參數讀寫角色:真實 EXE")
    from callgraph_le import CG
    import verify_address_claim_coverage as CC
    rcg = CG(CC.EXE)
    su = param_uses(rcg, 0x400CC, st.entries, 2, False) or {}
    s1, s2 = su.get(1, {"r": 0, "w": 0}), su.get(2, {"r": 0, "w": 0})
    chk("strcpy(目的, 來源):第 1 個只寫、第 2 個只讀", (s1["w"] > 0, s1["r"], s2["r"] > 0, s2["w"]), (True, 0, True, 0))
    clean = call_cleanups(st.code, st.base, set(st.entries))
    rsc2 = Screen()
    screen_roles(rsc2, real_names, rcg, st.entries, st.argc, clean)
    n_cmp = rsc2.denom.get("param_role 可比", 0)
    chk("真實 param_role 可比 ≥ 50", n_cmp >= 50, True)

    def flip(x: dict) -> dict:
        ps, _ = parse_sig(x.get("summary") or "")
        if not ps:
            return x
        swap = {"dst": "src", "src": "dst"}
        new = [swap[role_of(p)] if role_of(p) else p for p in ps]
        rest = (x.get("summary") or "")[VC.PARAMS.match(x["summary"]).end():]
        return {**x, "summary": "(" + ", ".join(new) + ")" + rest}

    rsc3 = Screen()
    screen_roles(rsc3, [flip(x) for x in real_names], rcg, st.entries, st.argc, clean)
    hit = sum(c.screen == "param_role" for c in rsc3.cands)
    print(f"    (角色全部對調的對照:{hit} / {rsc3.denom.get('param_role 可比', 0)} 觸發;原本 {len(rsc2.cands)})")
    chk("對照:角色全部對調後 ≥ 90% 觸發(篩選分得出讀寫)", hit >= 0.9 * rsc3.denom.get("param_role 可比", 1), True)
    run_sc = run(REVIEW_JSON)[0]
    chk("run() 有接上角色篩選(分母與單獨跑相同)", run_sc.denom.get("param_role 可比"), n_cmp)

    print()
    print("--selftest OK" if not fails else f"--selftest FAILED: {fails}")
    return 1 if fails else 0


def main(argv: list[str] | None = None) -> int:
    if hasattr(sys.stdout, "reconfigure"):
        sys.stdout.reconfigure(encoding="utf-8")
        sys.stderr.reconfigure(encoding="utf-8")
    ap = argparse.ArgumentParser(description="篩出摘要宣稱與實機紀錄矛盾的函式")
    ap.add_argument("--json", metavar="OUT", type=Path, help="寫候選明細(證據值、摘要、核對結論)")
    ap.add_argument("--review", metavar="JSON", type=Path, default=REVIEW_JSON,
                    help="review 檔(預設 docs/data/summary_screen_review.json)")
    ap.add_argument("--selftest", action="store_true")
    a = ap.parse_args(argv)
    if a.selftest:
        return selftest()
    sc, pending, errs, reviews, names = run(a.review)
    for ln in report(sc, pending, errs, reviews):
        print(ln)
    if a.json:
        a.json.write_bytes((json.dumps(cand_doc(sc, reviews, names), ensure_ascii=False, indent=1) + "\n").encode("utf-8"))
        print(f"候選明細 -> {a.json}")
    rc = exit_code(pending, errs)
    print("結果:" + ("FAIL" if rc else "PASS"))
    return rc


if __name__ == "__main__":
    sys.exit(main())
