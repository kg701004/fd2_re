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

續一百一十二(殘留風險查證):
- `param_count` 加靜態版:實機沒比過個數的函式(沒有紀錄、或紀錄裡沒有直接呼叫端)改比 EXE 全部呼叫端的清堆疊個數;
  沒有呼叫端清堆疊時只在本體 argc 比參數列多時列出。以值傳的 double 佔 2 格;`(三個參數)` 這類讀不出個數的不比。
- `param_role` 追轉交:參數原樣推給被呼叫端(或 call 當下放在暫存器)時,取被呼叫端對該引數的讀寫(最多 4 層);
  `add` / `lea` 算出的指標也算同一個參數。

續一百一十三(續一百一十二的殘留風險):
- 沿控制流:`param_uses` 與呼叫點值流改用 `cfg_states`(合流取聯集、做到不動點),取代依位址順序的近似。
  另追 `mov [esp+X], r` 預先放的引數、參數暫存到區域變數再讀回、`push` / `pop` 搬運。
- `param_flow`(**靜態,不需要受測函式的實機紀錄**):實機型別篩選沒比到的參數(沒有紀錄的函式),改看
  1. 呼叫端:EXE 每個呼叫點推的值 —— 常數(位址常數套 fixup 換成執行期值)、byte / word 載入(小整數)、
     區域變數位址、呼叫者的參數(呼叫者有實機紀錄就代入它的實機值,否則再往上追)、回傳值(被呼叫者的實機回傳值);
  2. 被呼叫端:參數原樣推給有實機紀錄的函式時,該引數位置的實機值。
  與實機型別篩選同一條 `violates` 規則;違反的呼叫點 / 被呼叫端 ≥ 80% 才列出。selftest 以真實紀錄校準:
  呼叫點值流對實機值零矛盾、有紀錄的參數上靜態判決零誤報、歷史上實機抓到的型別錯誤用舊摘要能重現。

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
SCREENS = ("param_count", "param_type", "param_str", "ret_unlisted", "param_region", "param_role", "param_flow")
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
    if any(p in ("...", "..") or "=" in p or "個參數" in p for p in names):
        return names, None      # 「三個參數照轉」這類寫法讀不出個數,不可當成 1 個參數
    return names, len(names)


def slot_starts(params: list[str]) -> list[int]:
    """每個參數從第幾個堆疊格開始(1 起)。以值傳的 double 佔 2 格(8 bytes),`double*` 是指標佔 1 格。"""
    out, s = [], 1
    for p in params:
        out.append(s)
        s += 2 if p == "double" else 1
    return out


def n_slots(params: list[str] | None, n: int | None) -> int | None:
    """參數列佔的堆疊格數;`(N 個參數)` 沒有名稱時就是 N。"""
    if n is None:
        return None
    return n + sum(p == "double" for p in params or [])


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
    count_checked: set[int] = field(default_factory=set)   # 已由實機呼叫端比過個數的函式
    type_checked: set[tuple[int, int]] = field(default_factory=set)   # 實機比過型別的 (函式, 第 k 個參數)


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
        # 1. 參數個數(以堆疊格數比:double 佔 2 格)
        slots = n_slots(params, n_sig)
        if slots is not None and pushed:
            _bump(sc, "param_count 可比")
            sc.count_checked.add(a)
            if slots != pushed:
                sc.cands.append(Cand(a, name, "param_count", "count",
                                     f"摘要參數列 {slots} 格,實機呼叫端都清 {pushed} 個堆疊參數",
                                     sorted(f"{s:#x}:{v}" for s, v in sites.items())))
        # 2 / 3. 參數型別、字串
        starts = slot_starts(params or [])
        for k, pn in enumerate(params or [], 1):
            kind = type_of(pn)
            j = starts[k - 1]
            slot = (f"s{j}" if j <= pushed else None) if pushed else VC.param_slot(p["argc"], j)
            prm = p["params"].get(slot) if slot else None
            if kind is None or prm is None:
                continue
            _bump(sc, "param_type 可比")
            sc.type_checked.add((a, k))
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


def screen_static_count(sc: Screen, names: list[dict], cleanups: dict[int, set[int]],
                        argc: dict[int, int | None]) -> None:
    """`param_count` 的靜態版(續一百一十二):實機沒比過個數的函式(沒有紀錄、或紀錄裡沒有直接呼叫端)。

    - EXE 全部 `call rel32` 呼叫端清的堆疊個數唯一 -> 與參數列格數比,不同即候選。
    - 沒有任何呼叫端清堆疊時,本體讀到第 argc 個堆疊參數;argc 是下界(可以不讀最後一個),只有 argc 比格數**多**
      才是候選(摘要漏列參數)。argc 0 是暫存器傳參或沒有參數,不比。
    清堆疊個數有兩種以上(可變參數)不比。候選與實機版共用 (addr, param_count, count) 鍵:之後錄到實機紀錄時
    由實機版接手,review 不必改。
    """
    for x in names:
        a = int(x["addr"], 16)
        if a in sc.count_checked:
            continue
        params, n = parse_sig(x.get("summary") or "")
        slots = n_slots(params, n)
        if slots is None:
            continue
        c = cleanups.get(a, set())
        ag = argc.get(a)
        if len(c) == 1:
            _bump(sc, "param_count 可比(靜態清堆疊)")
            v = next(iter(c))
            if v != slots:
                sc.cands.append(Cand(a, x["name"], "param_count", "count",
                                     f"摘要參數列 {slots} 格,EXE 全部呼叫端都清 {v} 個堆疊參數(靜態)", sorted(c)))
        elif not c and ag:
            _bump(sc, "param_count 可比(靜態 argc)")
            if ag > slots:
                sc.cands.append(Cand(a, x["name"], "param_count", "count",
                                     f"摘要參數列 {slots} 格,本體讀到第 {ag} 個堆疊參數(靜態,無呼叫端清堆疊)", [ag]))


# ---------------------------------------------------------------- 參數讀寫角色(靜態,續一百一十一)

_MEM = re.compile(r"\[([a-z]{2,3})")
_STK = re.compile(r"\[(esp|ebp)(?: ([+-]) (0x[0-9a-f]+|\d+))?\]")
_SUBREG = {"al": "eax", "ah": "eax", "ax": "eax", "bl": "ebx", "bh": "ebx", "bx": "ebx", "cl": "ecx", "ch": "ecx",
           "cx": "ecx", "dl": "edx", "dh": "edx", "dx": "edx", "si": "esi", "di": "edi", "bp": "ebp"}
_REG32 = frozenset({"eax", "ebx", "ecx", "edx", "esi", "edi", "ebp"})
_FIRST_READ = frozenset({"cmp", "test", "push", "call", "jmp", "bt", "out"})
_PTR_ARITH = frozenset({"add", "sub", "inc", "dec"})      # 指標加減常數 / 索引後仍指向同一塊
_STRING_OPS = ("stos", "movs", "lods", "cmps", "scas")
_LEA_REG = re.compile(r"\b(e(?:ax|bx|cx|dx|si|di|bp))\b(\*\d)?")
_GLOBAL = re.compile(r"^(?:(?:byte|word|dword) ptr )?\[(0x[0-9a-f]+)\]$")


def _gslot(o: str, fix: int | None = None) -> tuple[str, int] | None:
    """`dword ptr [0x…]`(全域 dword)-> 狀態鍵 ("g", 位址);其他 -> None。參數暫存到全域再讀回用(組語核心常見)。

    位址取該指令的 fixup 目標(`fix`,native):反組譯印的是物件內位移,不同物件的同一個位移是不同變數
    (`draw_glyph16` 的 [0x27ac] 是 obj3 0x627ac、`heap_grow` 的是 obj2 0x527ac)。沒有 fixup 資訊(合成測試)才用印出的值。"""
    g = _GLOBAL.match(o)
    if not g or not o.startswith("dword"):
        return None
    return ("g", fix if fix is not None else int(g.group(1), 16))


def _mem_fix(i, fixups: dict[int, int] | None) -> int | None:
    """指令裡第一個 fixup 的目標(記憶體位移在立即值之前編碼,所以有位移時就是它);沒有 -> None。"""
    if not fixups:
        return None
    return next((fixups[a] for a in range(i.address, i.address + i.size) if a in fixups), None)


def _cg_fixups(cg) -> dict[int, int]:
    """cg(callgraph_le.CG)的 fixup 表 {位置: 目標},算一次存在 cg 上;合成的 cg 沒有 EXE -> {}。"""
    fm = getattr(cg, "_s113_fixups", None)
    if fm is None:
        if hasattr(cg, "d") and hasattr(cg, "meta"):
            from callgraph_le import fixup_map
            fm = fixup_map(cg.d, cg.meta)
        else:
            fm = {}
        cg._s113_fixups = fm
    return fm



def _writes_first(m: str) -> bool:
    """指令 m 會不會寫第一個運算元。FPU 只有 fst / fist 類寫記憶體(fld [x] 是讀)。"""
    if m.startswith("f"):
        return m.startswith(("fst", "fist", "fbstp", "fnst", "fsave", "fnsave"))
    return m not in _FIRST_READ and not m.startswith(("j", "loop"))


def _stack_param(o: str, delta: int, ebp: int | None) -> int | None:
    """運算元 o 是堆疊參考 -> 第幾個參數(回傳位址 / 區域變數為 0);不是堆疊參考 -> None。

    `[ebp+X]` 只在 `mov ebp, esp` 之後(ebp 是框架)才算堆疊;ebp 當一般暫存器時是記憶體運算元。
    """
    d = _depth(o, delta, ebp)
    if d is None:
        return None
    return -d // 4 if d <= -4 else 0


def _depth(o: str, delta: int, ebp: int | None) -> int | None:
    """堆疊運算元 o 指到的位置 -> 深度(入口 ESP 往下幾個 byte;回傳位址在 0..-3,第 k 個參數在 -4k);
    不是堆疊參考 -> None。`[ebp+X]` 只在 ebp 是框架時算。"""
    m = _STK.search(o)
    if not m or (m.group(1) == "ebp" and ebp is None):
        return None
    disp = int(m.group(3) or "0", 0)
    return (delta if m.group(1) == "esp" else ebp) - (-disp if m.group(2) == "-" else disp)


CAP = 8                    # 合流後同一位置最多記幾個可能值;超過就當作不明
_TOP = "*"                 # 不明(與任何集合合流仍是不明 -> 單調,不動點必停)
UNK = frozenset({None})    # 值流:來源不明


def _join(a: dict, b: dict, missing: frozenset) -> dict:
    """兩個狀態合流:每個位置取聯集;只有一邊有的位置,另一邊以 missing 代入(參數追蹤 = 空集合、值流 = 不明)。"""
    out = {}
    for k in a.keys() | b.keys():
        v = a.get(k, missing) | b.get(k, missing)
        if _TOP in v or len(v) > CAP:
            v = frozenset({_TOP})
        if v != missing:
            out[k] = v
    return out


def _succs(i, nodes: set[int], orphans: list[int]) -> list[int]:
    """指令 i 在本體內的後繼。ret 沒有;`jmp imm` 跳到本體內才有(跳出 = 尾端呼叫);間接 jmp(跳表)-> 沒有直接
    前驅的指令段;條件跳躍 / loop 兩邊;其他(含 call)落到下一個指令。"""
    m, op = i.mnemonic, i.op_str
    if m.startswith("ret") or m == "iretd":
        return []
    if m == "jmp":
        if op.startswith("0x"):
            return [int(op, 16)] if int(op, 16) in nodes else []
        return list(orphans)
    nxt = i.address + i.size
    out = [nxt] if nxt in nodes else []
    if m.startswith(("j", "loop")) and op.startswith("0x") and int(op, 16) in nodes:
        out.append(int(op, 16))
    return out


def cfg_states(cg, target: int, entries: list[int], init: dict, step, missing: frozenset
               ) -> tuple[dict[int, dict], dict[int, tuple[int, int | None]], dict] | None:
    """沿控制流算每個指令**進入時**的狀態(合流取聯集,做到不動點)-> (狀態, trace, 指令);走不出本體回 None。

    節點 = `callee_argc` 走到的指令(附 ESP 位移與 ebp 基底);第一個走到的是本體起點,狀態 = init。
    `callee_argc` 判不出參數個數、但本體以 `jmp` 跳到本體外的共用收尾段(AIL API 包裝 `call 實作; jmp 0x382ca`、
    事件處理)時仍照走 —— 那裡位移不為 0 只是收尾段替它清堆疊,本體內的位移是對的(續一百一十三,141 個判不出的有 115 個)。
    跳表的 case 段沒有直接前驅,當作間接 jmp 的後繼;仍走不到的(本體沒有間接 jmp)依位址順序以空狀態起算。
    `step(指令, (位移, ebp), 狀態) -> 新狀態`,不可改動傳入的 dict。
    續一百一十三取代依位址順序的近似:共用尾段(兩條路徑各推不同的引數再 jmp 進來)依位址順序只看得到落入的
    那條 —— 呼叫點值流對實機值的 33 筆矛盾,主因就是這個(另一個是位址常數沒套 fixup)。
    """
    trace: dict[int, tuple[int, int | None]] = {}
    got = DNA.callee_argc(cg, target, entries, trace)
    if not trace:
        return None
    nodes = set(trace)
    ins = {a: cg._insn(a) for a in nodes}
    if got[0] is None and not (got[1] == "leaf without clean ret" and any(
            i.mnemonic == "jmp" and i.op_str.startswith("0x") and int(i.op_str, 16) not in nodes for i in ins.values())):
        return None
    start = next(iter(trace))
    reached: set[int] = set()
    for a in nodes:
        reached.update(_succs(ins[a], nodes, []))
    orphans = sorted(a for a in nodes if a not in reached and a != start)
    sin: dict[int, dict] = {start: dict(init)}
    work = [start]
    while True:
        while work:
            a = work.pop()
            out = step(ins[a], trace[a], sin[a])
            for t in _succs(ins[a], nodes, orphans):
                if t not in sin:
                    sin[t] = out
                    work.append(t)
                else:
                    j = _join(sin[t], out, missing)
                    if j != sin[t]:
                        sin[t] = j
                        work.append(t)
        rest = [a for a in sorted(nodes) if a not in sin]
        if not rest:
            return sin, trace, ins
        sin[rest[0]] = {}
        work.append(rest[0])


def _ks(s: dict, key) -> frozenset:
    """狀態裡某位置(暫存器名或堆疊深度)可能裝著的參數序號(去掉不明)。"""
    return frozenset(k for k in s.get(key, ()) if k != _TOP)


def _addr_ks(s: dict, o: str) -> frozenset:
    """位址運算式 o(`[base + idx + X]`)裡不帶倍率的暫存器可能裝著的參數(聯集)。索引在前、指標在後
    (`[esi + ebx]`,ebx 是輸出參數)也算 —— 續一百一十三前只看第一個暫存器,3 個參數因此零存取。"""
    return frozenset().union(*(_ks(s, r) for r, scale in _LEA_REG.findall(o[o.find("["):]) if not scale))


# int 21h 以 DS:EDX 傳緩衝的功能 -> DOS 對該緩衝讀('r')或寫('w')
_DOS_EDX = {0x09: "r", 0x39: "r", 0x3A: "r", 0x3B: "r", 0x3C: "r", 0x3D: "r", 0x3F: "w", 0x40: "r", 0x41: "r",
            0x43: "r", 0x4E: "r", 0x5A: "r", 0x5B: "r"}


def _dos_ah(prev: list) -> int | None:
    """`int 0x21` 之前(依位址順序,近的在後)最近一個設定 AH 的 `mov ah / ax / eax, imm` -> AH;中間有其他寫
    eax 的指令或找不到 -> None。"""
    for i in reversed(prev):
        ops = [o.strip() for o in i.op_str.split(",")] if i.op_str else []
        if not ops or _SUBREG.get(ops[0], ops[0]) != "eax" or ops[0] == "al":
            continue
        if i.mnemonic == "mov" and len(ops) == 2 and re.match(r"^(?:0x[0-9a-f]+|\d+)$", ops[1]):
            v = int(ops[1], 0)
            return v if ops[0] == "ah" else (v >> 8) & 0xFF
        return None
    return None


def _live_slots(s: dict, delta: int) -> dict:
    """去掉已彈掉(深度大於目前位移)的堆疊格。"""
    return {k: v for k, v in s.items() if not (isinstance(k, int) and k > delta)}


def _param_step(i, td: tuple[int, int | None], s: dict, n: int, regconv: bool, exact: bool = False,
                fm: dict[int, int] | None = None) -> dict:
    """param_uses 的狀態轉移:{暫存器名 或 堆疊深度: 可能裝著的參數序號}。

    exact:只追「值不變」的參數(複製、加減常數);`add r, 非常數`、`lea` 的多暫存器 / 索引運算式使 r 失效。
    型別證據用 —— `base + x` 是指標,不能算到 x 頭上。"""
    delta, ebp = td
    s = _live_slots(s, delta)
    m = i.mnemonic.split()[-1]
    ops = [o.strip() for o in i.op_str.split(",")] if i.op_str else []

    def src_ks(o: str) -> frozenset:
        if o in _REG32:
            return _ks(s, o)
        if (g := _gslot(o, _mem_fix(i, fm))) is not None:
            return _ks(s, g)
        d = _depth(o, delta, ebp)
        if d is None:
            return frozenset()
        if d <= -4:                                    # 堆疊參數(暫存器傳參的函式沒有)
            return frozenset({-d // 4}) if not regconv and -d // 4 <= n else frozenset()
        return _ks(s, d) if d > 0 else frozenset()     # 區域變數 / 推入的引數

    if m == "push" and ops:
        ks = src_ks(ops[0])
        if ks:
            s[delta + 4] = ks
        else:
            s.pop(delta + 4, None)
        return s
    if m.startswith(_STRING_OPS) and not m.startswith(("movsx", "movzx")):
        if m.startswith("lods"):
            s.pop("eax", None)
        return s
    if ops and _writes_first(m) and "[" in ops[0]:
        d0 = _depth(ops[0], delta, ebp)
        key = d0 if d0 is not None and d0 > 0 else _gslot(ops[0], _mem_fix(i, fm))
        if key is not None:                            # 寫區域變數 / 預先放引數的 `mov [esp+X], r` / 全域槽
            ks = src_ks(ops[1]) if m == "mov" and len(ops) > 1 else frozenset()
            if ks:
                s[key] = ks
            else:
                s.pop(key, None)
        return s
    if m == "call":
        for r in ("eax", "ecx", "edx"):
            s.pop(r, None)
    elif m == "popal":
        s = {k: v for k, v in s.items() if not isinstance(k, str)}
    elif m in ("mul", "div", "idiv", "cdq") or (m == "imul" and len(ops) == 1):
        s.pop("eax", None)
        s.pop("edx", None)
    elif m == "pop" and ops and ops[0] in _REG32:
        ks = _ks(s, delta)                             # 從堆疊頂取回(push / pop 搬運、保存再還原)
        if ks:
            s[ops[0]] = ks
        else:
            s.pop(ops[0], None)
    elif ops and _writes_first(m):
        d = _SUBREG.get(ops[0], ops[0])
        src = ops[1] if len(ops) > 1 else ""
        if m == "mov":
            ks = src_ks(src) if d == ops[0] else frozenset()
            if ks:
                s[d] = ks
            else:
                s.pop(d, None)
        elif m == "add" and d == ops[0] and d in _REG32:
            ks = src_ks(src)
            if exact:
                if not _IMM.match(src):
                    s.pop(d, None)
            elif ks:                                   # 指標 + 參數:兩邊都可能是那塊記憶體(聯集)
                s[d] = _ks(s, d) | ks
        elif m == "lea" and d in _REG32:
            regs = _LEA_REG.findall(src)
            if exact:
                ks = _ks(s, regs[0][0]) if len(regs) == 1 and not regs[0][1] else frozenset()
            else:
                ks = _addr_ks(s, src)
            if ks:
                s[d] = ks
            else:
                s.pop(d, None)
        elif m == "xchg" and src in _REG32 and d in _REG32:
            sv, dv = s.pop(src, None), s.pop(d, None)
            if sv:
                s[d] = sv
            if dv:
                s[src] = dv
        elif not (m in _PTR_ARITH and d == ops[0] and (not exact or m in ("inc", "dec") or _IMM.match(src))):
            s.pop(d, None)
    return s


def param_uses(cg, target: int, entries: list[int], n: int, regconv: bool,
               fwd: list[tuple[int, int, int | str, int]] | None = None,
               init: dict | None = None, exact: bool = False) -> dict[int, dict[str, int]] | None:
    """被呼叫端本體經由第 k 個參數(指標)讀 / 寫記憶體的次數 -> {k: {"r": 次, "w": 次}};走不出本體回 None。

    沿控制流(`cfg_states`,續一百一十三;原本依位址順序)追蹤「哪個暫存器 / 堆疊格可能裝著第 k 個參數」:
    - 載入:`mov r, [esp+X]` / `[ebp+X]` 換算成第 k 個(堆疊傳參);暫存器傳參時入口 eax / edx / ebx / ecx
      依序是第 1..n 個(Watcom)。`mov r2, r1` 複製;`add / sub / inc / dec r` 保留(指標移動);其他寫入 r 就失效;
      `call` 之後 eax / ecx / edx 失效;`popal` 暫存器全部失效。寫子暫存器(`mov al, …`)使整個暫存器失效。
    - 堆疊格:`push r` 與 `mov [esp+X], r`(預先放引數、暫存到區域變數)記到該深度,`mov r, [esp+X]` / `pop r`
      再讀回;深度大於目前位移(已彈掉)的在每個指令開頭就忘掉。全域 dword `mov [0x…], r` 也記,讀回同一位址
      就還原(`draw_glyph16` 把參數全部存到全域再讀);`call` 之後仍保留(`grid_path_search` 存到全域、
      呼叫內部子程式後再讀)。
    - 寫:`stos` / `movs` 的 edi,或第一個運算元是 `[r…]` 且指令會寫它。讀:`lods` / `movs` / `cmps` 的 esi、
      `cmps` / `scas` 的 edi,或其他 `[r…]` 運算元。`[r1 + r2]` 兩個(不帶倍率的)暫存器裝的參數都算。`lea` 不算存取。
      `int 21h`:依前面設定的 AH,DS:EDX 緩衝是 DOS 讀(開檔 / 建檔 / 刪檔的檔名、0x40 寫檔的資料)或寫(0x3f 讀檔)。
    合流處取聯集(「可能裝著」):某條路徑上裝著第 k 個的暫存器,經由它的存取就算第 k 個的。這是篩選,候選要人看反組譯。

    `fwd`(續一百一十二):給一個 list 就收「第 k 個參數在 `call 0xT` 當下位於第 j 個引數位置」-> (k, T, j, 呼叫點),
    j = (位移 - 深度) / 4 + 1;`call` 當下裝著第 k 個參數的暫存器 / 全域槽也記下 -> (k, T, 暫存器名 或 ("g", 位址), 呼叫點)。

    指標衍生(續一百一十二):`add r, X` / `lea r, [...]` 算出的 r,X(暫存器或堆疊參數)或 lea 裡不帶倍率的暫存器
    裝著第 k 個,r 也算第 k 個 —— `dst + y*stride + x` 的結果仍指向 dst 那塊。續一百一十三起取聯集:r 原本裝的參數
    保留、兩個參數相加兩個都算(原本只取唯一一個,`draw_box_frame_grid` 的 `高 + dst` 因此丟掉 dst)。
    `init` 給定時以它當入口的暫存器對應(追暫存器轉交用),取代 regconv 的 eax / edx / ebx / ecx。
    存進全域槽(`mov dword ptr [0x…], r`,r 裝著第 k 個)另記 -> (k, None, ("g", 位址), 指令位址),由 role_uses 找讀該槽的函式。
    `exact`:見 `_param_step`(型別證據用,只追值不變的參數)。
    """
    if init is not None:
        init0 = {r: frozenset({k}) for r, k in init.items()}
    else:
        init0 = {r: frozenset({k}) for k, r in enumerate(VC.REG_ARGS[:n], 1)} if regconv else {}
    fm = _cg_fixups(cg)
    res = cfg_states(cg, target, entries, init0, lambda i, td, st: _param_step(i, td, st, n, regconv, exact, fm),
                     frozenset())
    if res is None:
        return None
    sin, trace, ins = res
    uses: dict[int, dict[str, int]] = {}

    def use(st: dict, reg: str, kind: str) -> None:
        use_ks(_ks(st, reg), kind)

    def use_ks(ks: frozenset, kind: str) -> None:
        for k in ks:
            uses.setdefault(k, {"r": 0, "w": 0})[kind] += 1

    order = sorted(sin)
    for n_i, a in enumerate(order):
        delta, ebp = trace[a]
        st = _live_slots(sin[a], delta)
        i = ins[a]
        m = i.mnemonic.split()[-1]                     # `rep movsb` -> movsb
        ops = [o.strip() for o in i.op_str.split(",")] if i.op_str else []
        if fwd is not None and m == "call" and ops and ops[0].startswith("0x"):
            t = int(ops[0], 16)
            fwd.extend((k, t, (delta - h) // 4 + 1, a) for h, ks in sorted(x for x in st.items() if isinstance(x[0], int))
                       if (delta - h) % 4 == 0 for k in sorted(ks - {_TOP}))
            fwd.extend((k, t, r, a) for r, ks in sorted((x for x in st.items() if not isinstance(x[0], int)), key=str)
                       for k in sorted(ks - {_TOP}))
        if m.startswith(_STRING_OPS) and not m.startswith(("movsx", "movzx")):
            if m.startswith(("stos", "movs")):
                use(st, "edi", "w")
            if m.startswith(("lods", "movs", "cmps")):
                use(st, "esi", "r")
            if m.startswith(("cmps", "scas")):
                use(st, "edi", "r")
            continue
        if fwd is not None and m == "mov" and len(ops) == 2 and (g := _gslot(ops[0], _mem_fix(i, fm))) is not None:
            fwd.extend((k, None, g, a) for k in sorted(_ks(st, ops[1]) if ops[1] in _REG32 else ()))
        if m == "int" and ops == ["0x21"]:
            kind = _DOS_EDX.get(_dos_ah([ins[b] for b in order[max(0, n_i - 6):n_i]]))
            if kind:
                use(st, "edx", kind)                   # DOS 讀檔名 / 寫入緩衝(DS:EDX)
            continue
        if m != "lea":
            for idx, o in enumerate(ops):
                if _MEM.search(o) and _stack_param(o, delta, ebp) is None:
                    use_ks(_addr_ks(st, o), "w" if idx == 0 and _writes_first(m) else "r")
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


FWD_DEPTH = 4      # 轉交最多追幾層被呼叫端


def _global_readers(cg, entries: list[int], memo: dict) -> dict[int, set[int]]:
    """{全域 dword 位址: 本體讀它(`mov r, dword ptr [X]` / `push dword ptr [X]`)的入口};存在 memo 裡只建一次。"""
    if ("greaders",) not in memo:
        fm = _cg_fixups(cg)
        out: dict[int, set[int]] = {}
        for e in entries:
            trace: dict[int, tuple[int, int | None]] = {}
            DNA.callee_argc(cg, e, entries, trace)
            for a in trace:
                i = cg._insn(a)
                ops = [o.strip() for o in i.op_str.split(",")] if i.op_str else []
                src = ops[1] if i.mnemonic == "mov" and len(ops) == 2 else ops[0] if i.mnemonic == "push" and ops else ""
                if (g := _gslot(src, _mem_fix(i, fm))) is not None:
                    out.setdefault(g[1], set()).add(e)
        memo[("greaders",)] = out
    return memo[("greaders",)]


def role_uses(cg, code: bytes | None, base: int, entries: list[int], target: int, n: int, regconv: bool,
              memo: dict, depth: int = 0, known: set[int] | None = None,
              init: dict[str, int] | None = None) -> dict[int, dict[str, int]] | None:
    """本體直接存取(r / w)加上原樣轉交給被呼叫端後、被呼叫端對該引數的存取(fr / fw,遞迴)。

    被呼叫端的引數個數取該呼叫點清的堆疊個數(`pushed_args`),以它當 n 重算;轉交到第 j 個而呼叫點清不到 j 個自然查不到
    (prologue 存起來的暫存器不是引數)。呼叫點後面沒有清堆疊(交給共用收尾段,AIL API 包裝)時改取被呼叫端本體讀到的
    個數(`callee_argc`,續一百一十三)。被呼叫端一律以堆疊傳參看待(呼叫端推了引數)。`code` 是 None 時不追轉交。
    `known` 是已知入口的集合(預設由 entries 建);不是已知入口的呼叫目標不追。
    暫存器 / 全域槽轉交:被呼叫端以 `init = {暫存器 或 ("g", 位址): 1}` 重算,取它對第 1 個(入口值)的存取。
    存進全域槽(續一百一十三,`anim_vm_set_context` 這類「設定」函式):讀該槽的其他函式以 `init = {("g", 位址): 1}`
    重算,存取算進 fr / fw(一樣佔一層深度)。
    memo 的總計鍵含 depth:同一個函式在較深處被截斷的結果不可給較淺處重用(否則結果依走訪順序而變);
    本體的直接存取與轉交清單與 depth 無關,另以 ("direct", …) 鍵共用。
    """
    known = set(entries) if known is None else known
    sig = (target, n, regconv, tuple(sorted((init or {}).items())))
    key = sig + (depth,)
    if key in memo:
        return memo[key]
    memo[key] = None                                   # 遞迴循環時當作走不出
    dkey = ("direct",) + sig
    if dkey not in memo:
        fl: list[tuple[int, int, int | str, int]] | None = [] if code is not None else None
        memo[dkey] = (param_uses(cg, target, entries, n, regconv, fl, init), fl)
    direct, fwd = memo[dkey]
    if direct is None:
        return None
    out = {k: {"r": u["r"], "w": u["w"], "fr": 0, "fw": 0} for k, u in direct.items()}
    if depth < FWD_DEPTH:
        for k, t, j, site in fwd or []:
            if t is None:                              # 存進全域槽:改看讀這個槽的其他函式
                for c in sorted(_global_readers(cg, entries, memo).get(j[1], set()) - {target}):
                    su = (role_uses(cg, code, base, entries, c, 0, False, memo, depth + 1, known, {j: 1}) or {}).get(1)
                    if su:
                        o = out.setdefault(k, {"r": 0, "w": 0, "fr": 0, "fw": 0})
                        o["fr"] += su["r"] + su["fr"]
                        o["fw"] += su["w"] + su["fw"]
                continue
            if t not in known:
                continue
            if not isinstance(j, int):                 # 暫存器或全域槽
                sub = role_uses(cg, code, base, entries, t, 0, False, memo, depth + 1, known, {j: 1})
                su = (sub or {}).get(1)
            else:
                nt = pushed_args(code, base, site) or DNA.callee_argc(cg, t, entries)[0]
                if not nt:
                    continue
                sub = role_uses(cg, code, base, entries, t, nt, False, memo, depth + 1, known)
                su = (sub or {}).get(j)
            if su:
                o = out.setdefault(k, {"r": 0, "w": 0, "fr": 0, "fw": 0})
                o["fr"] += su["r"] + su["fr"]
                o["fw"] += su["w"] + su["fw"]
    memo[key] = out
    return out


def screen_roles(sc: Screen, names: list[dict], cg, entries: list[int], argc: dict[int, int | None],
                 cleanups: dict[int, set[int]], code: bytes | None = None, base: int = 0) -> None:
    """`param_role`:參數名是目的,本體經由它只讀不寫;或參數名是來源,本體經由它寫入 -> 候選。

    不需要實機紀錄:涵蓋所有有參數列的函式(含沒執行到的)。dst / src 對調時兩個參數都會觸發。
    續一百一十二:給 `code` 就把「原樣轉交給被呼叫端」的存取算進來(`role_uses`)—— 只轉交、本體不碰的參數
    (畫圖函式把 dst 傳給 blit)原本沒得比。double 參數佔 2 格,第 k 個參數取它開始的那一格。
    """
    memo: dict = {}
    known = set(entries)
    for x in names:
        params, n = parse_sig(x.get("summary") or "")
        roles = {k: role_of(pn) for k, pn in enumerate(params or [], 1)}
        if not n or not any(roles.values()):
            continue
        a = int(x["addr"], 16)
        slots = n_slots(params, n)
        starts = slot_starts(params or [])
        conv = role_convention(slots, cleanups.get(a, set()), argc.get(a))
        if conv == "reg" and slots != n:
            conv = None                                # double 走暫存器的配置不猜
        uses = role_uses(cg, code, base, entries, a, slots, conv == "reg", memo, 0, known) if conv else None
        if uses is None:
            continue
        _bump(sc, "param_role 函式")
        for k, role in roles.items():
            u = uses.get(starts[k - 1])
            if not role or not u or not any(u.values()):
                continue
            _bump(sc, "param_role 可比")
            if u["fr"] or u["fw"]:
                _bump(sc, "param_role 可比(含轉交)")
            pn = params[k - 1]
            r, w = u["r"] + u["fr"], u["w"] + u["fw"]
            how = f"本體讀 {u['r']}、寫 {u['w']};轉交後讀 {u['fr']}、寫 {u['fw']}"
            if role == "dst" and not w:
                sc.cands.append(Cand(a, x["name"], "param_role", f"p{k}",
                                     f"第 {k} 參數 {pn}(目的):讀 {r} 次、從未寫入({how})", [u]))
            elif role == "src" and w:
                sc.cands.append(Cand(a, x["name"], "param_role", f"p{k}",
                                     f"第 {k} 參數 {pn}(來源):寫入 {w} 次({how})", [u]))


# ---------------------------------------------------------------- 呼叫點值流與 param_flow(靜態,續一百一十三)

_IMM = re.compile(r"^(?:0x[0-9a-f]+|\d+)$")
_SMALL = frozenset({("small",)})
FLOW_DEPTH = 3     # 來源是呼叫者的參數而呼叫者沒有實機紀錄時,最多再往上追幾層


def _runtime(native: int) -> int:
    """fixup 目標(native)-> 執行期位址(obj3 位移不同)。"""
    return native + (VC.OBJ3_DELTA if native >= 0x60000 else VC.DELTA)


def call_conv(f: int, cleanups: dict[int, set[int]], argc: dict[int, int | None]) -> str | None:
    """f 的傳參方式(不看摘要):呼叫端清堆疊個數唯一、或沒有清堆疊但本體讀堆疊參數 -> 'stack';都沒有且 argc 0 ->
    'reg'(Watcom 暫存器,含沒有參數的函式);其他(可變參數、不明)-> None。"""
    c = cleanups.get(f, set())
    if len(c) == 1 or (not c and argc.get(f)):
        return "stack"
    if not c and argc.get(f) == 0:
        return "reg"
    return None


def _value_step(i, td: tuple[int, int | None], s: dict, c: int, fixups: dict[int, int], known: set[int]) -> dict:
    """呼叫點值流的狀態轉移:{暫存器名 或 堆疊深度: 可能的來源集合}。來源:("imm", 值) / ("param", 函式, k) /
    ("ret", 被呼叫者) / ("small",) / ("stack",) / ("load", 全域位址);None = 不明。"""
    delta, ebp = td
    s = _live_slots(s, delta)
    m = i.mnemonic.split()[-1]
    ops = [o.strip() for o in i.op_str.split(",")] if i.op_str else []
    fx = fixups.get(i.address + i.size - 4)            # 立即值 / 單一位移在指令最後 4 bytes;那裡有 fixup 才重定位

    def desc(o: str) -> frozenset:
        if o in _REG32:
            return s.get(o, UNK)
        if _IMM.match(o):
            return frozenset({("imm", _runtime(fx) if fx is not None else int(o, 0) & 0xFFFFFFFF)})
        d = _depth(o, delta, ebp)
        if d is not None:
            if d <= -4:
                return frozenset({("param", c, -d // 4)})
            return s.get(d, UNK) if d > 0 else UNK
        if o.startswith(("byte ptr", "word ptr")):
            return _SMALL
        if (gs := _gslot(o, _mem_fix(i, fixups))) is not None and gs in s:
            return s[gs]
        g = _GLOBAL.match(o)
        if g:
            return frozenset({("load", fx if fx is not None else int(g.group(1), 16))})
        return UNK

    def put(key, v: frozenset) -> None:
        if v == UNK:
            s.pop(key, None)
        else:
            s[key] = v

    if m == "push" and ops:
        put(delta + 4, desc(ops[0]))
        return s
    if m == "pop" and ops:
        if ops[0] in _REG32:
            put(ops[0], s.get(delta, UNK))
        return s
    if m == "call":
        for r in ("eax", "ecx", "edx"):
            s.pop(r, None)
        if ops and ops[0].startswith("0x") and int(ops[0], 16) in known:
            s["eax"] = frozenset({("ret", int(ops[0], 16))})
        return s
    if m == "popal":
        return {k: v for k, v in s.items() if not isinstance(k, str)}
    if m.startswith(_STRING_OPS) and not m.startswith(("movsx", "movzx")):
        for r in ("eax", "esi", "edi") if m.startswith("lods") else ("esi", "edi"):
            s.pop(r, None)
        return s
    if not ops:
        for r in ("eax", "edx"):                       # cdq / cwde / cbw
            s.pop(r, None)
        return s
    if m in ("mul", "div", "idiv") or (m == "imul" and len(ops) == 1):
        s.pop("eax", None)
        s.pop("edx", None)
        return s
    if not _writes_first(m):
        return s
    if "[" in ops[0]:
        d0 = _depth(ops[0], delta, ebp)
        key = d0 if d0 is not None and d0 > 0 else _gslot(ops[0], _mem_fix(i, fixups))
        if key is not None:
            put(key, desc(ops[1]) if m == "mov" and len(ops) > 1 else UNK)
        return s
    d = _SUBREG.get(ops[0], ops[0])
    if d not in _REG32:
        return s
    src = ops[1] if len(ops) > 1 else ""
    if d != ops[0] or m.startswith("set"):
        # 寫子暫存器:原本是小整數(或常數 < 0x10000)才仍是小整數,否則不明
        old = s.get(d, UNK)
        small = all(x is not None and x != _TOP and (x[0] == "small" or (x[0] == "imm" and x[1] < 0x10000))
                    for x in old)
        put(d, _SMALL if small or m == "xor" and src == ops[0] else UNK)
    elif m == "mov":
        put(d, desc(src))
    elif m in ("movzx", "movsx"):
        s[d] = _SMALL
    elif m == "xor" and src == ops[0]:
        s[d] = frozenset({("imm", 0)})
    elif m == "lea":
        g = re.match(r"^\[(0x[0-9a-f]+)\]$", src)
        if g:
            s[d] = frozenset({("imm", _runtime(fx) if fx is not None else int(g.group(1), 16))})
        elif _depth(src, delta, ebp) is not None:
            s[d] = frozenset({("stack",)})
        else:
            s.pop(d, None)
    elif m == "and" and _IMM.match(src) and fx is None and int(src, 0) < 0x10000:
        s[d] = _SMALL
    else:
        s.pop(d, None)
    return s


def arg_sources(cg, entries: list[int], code: bytes, base: int, fixups: dict[int, int], thunk_of: dict[int, int],
                cleanups: dict[int, set[int]], argc: dict[int, int | None]) -> dict[int, dict[int, tuple[int, dict]]]:
    """EXE 每個已知入口本體裡的 `call rel32`(目標是已知入口)-> {目標: {呼叫點: (呼叫者, {j 或暫存器: 來源集合})}}。

    堆疊引數取該呼叫點清的個數(`pushed_args`;沒有清堆疊時取被呼叫端的 argc),第 j 個在深度 位移 - 4(j - 1);暫存器引數取 call 當下的
    eax / edx / ebx / ecx。呼叫 thunk(`jmp` 到真正入口)的也算真正入口的呼叫點。暫存器傳參的呼叫者,入口的
    eax / edx / ebx / ecx 是它的第 1..4 個參數。
    """
    known = set(entries)
    inv = {x: t for t, x in thunk_of.items()}
    out: dict[int, dict[int, tuple[int, dict]]] = {}
    for c in entries:
        init = ({r: frozenset({("param", c, k)}) for k, r in enumerate(VC.REG_ARGS, 1)}
                if call_conv(c, cleanups, argc) == "reg" else {})
        res = cfg_states(cg, c, entries, init, lambda i, td, st, c=c: _value_step(i, td, st, c, fixups, known), UNK)
        if res is None:
            continue
        sin, trace, ins = res
        for a, st in sin.items():
            i = ins[a]
            if i.mnemonic != "call" or not i.op_str.startswith("0x") or int(i.op_str, 16) not in known:
                continue
            t = int(i.op_str, 16)
            delta = trace[a][0]
            st = _live_slots(st, delta)
            nargs = pushed_args(code, base, a) or argc.get(t) or 0      # 沒有 add esp(共用收尾段清)-> 被呼叫端讀到的個數
            args: dict = {j: st.get(delta - 4 * (j - 1), UNK) for j in range(1, nargs + 1)}
            args.update({r: st.get(r, UNK) for r in VC.REG_ARGS})
            for tt in {t, inv.get(t, t)}:
                out.setdefault(tt, {})[a] = (c, args)
    return out


def _live(profiles: dict[str, dict], f: int, slot: int | str) -> set[int] | None:
    """f 在 slot(堆疊第 j 個、暫存器名或 'ret')的實機值(剖面最常見的值);沒有 -> None。"""
    p = profiles.get(f"{f:#x}")
    if not p:
        return None
    prm = p["ret"] if slot == "ret" else p["params"].get(f"s{slot}" if isinstance(slot, int) else slot)
    vals = {int(v, 16) for v, _ in (prm or {}).get("top", [])}
    return vals or None


def flow_values(sources: dict, profiles: dict[str, dict], cleanups: dict[int, set[int]],
                argc: dict[int, int | None], f: int, slot: int | str, exclude: int,
                depth: int = 0, seen: frozenset = frozenset()) -> dict[int, set | None]:
    """f 的引數位置 slot 在每個靜態呼叫點可能的值 -> {呼叫點: 值集合 或 None(解不出)}。

    值:int(具體值)、'small'(byte / word 載入、小遮罩)、'stack'(區域變數位址)。來源是呼叫者的參數時,呼叫者有
    實機紀錄就代入它該位置的實機值,否則沿它的呼叫點再往上追(最多 FLOW_DEPTH 層);回傳值代入被呼叫者的實機回傳值。
    全域變數的載入、不明的來源解不出。`exclude` 的實機值不用(受測函式自己 —— 校準時把有紀錄的函式當成沒有)。
    """
    def resolve(d) -> set | None:
        if d is None or d == _TOP or d[0] == "load":
            return None
        if d[0] == "imm":
            return {d[1]}
        if d[0] in ("small", "stack"):
            return {d[0]}
        if d[0] == "ret":
            return _live(profiles, d[1], "ret") if d[1] != exclude else None
        cf, m = d[1], d[2]
        conv = call_conv(cf, cleanups, argc)
        sl = m if conv == "stack" else VC.REG_ARGS[m - 1] if conv == "reg" and m <= 4 else None
        if sl is None:
            return None
        lv = _live(profiles, cf, sl) if cf != exclude else None
        if lv:
            return lv
        if depth >= FLOW_DEPTH or cf in seen:
            return None
        sub = flow_values(sources, profiles, cleanups, argc, cf, sl, exclude, depth + 1, seen | {f})
        if not sub or any(v is None for v in sub.values()):
            return None
        return set().union(*sub.values())

    out: dict[int, set | None] = {}
    for site, (_, args) in sources.get(f, {}).items():
        vals: set | None = set()
        for d in args.get(slot, UNK):
            v = resolve(d)
            if v is None:
                vals = None
                break
            vals |= v
        out[site] = vals or None
    return out


def _flow_violates(kind: str, v) -> bool:
    if v == "small":
        return kind in ("ptr", "str")
    if v == "stack":
        return kind in ("unit", "small")
    return violates(kind, v)


def flow_verdict(kind: str, site_vals: dict[int, set | None]) -> tuple[str | None, int, int]:
    """呼叫點值流 -> (判決 'viol' / 'ok' / None, 可判呼叫點數, 違反呼叫點數)。

    呼叫點違反 = 它所有可能的值都違反;違反的呼叫點 ≥ 80% 可判呼叫點才是 'viol'。"""
    det = [v for v in site_vals.values() if v]
    if not det:
        return None, 0, 0
    bad = sum(all(_flow_violates(kind, x) for x in v) for v in det)
    return ("viol" if bad >= VIOLATION_SHARE * len(det) else "ok"), len(det), bad


def down_verdict(kind: str, fwds: list[tuple[int, int, int]], profiles: dict[str, dict], code: bytes | None,
                 base: int) -> tuple[str | None, int, int]:
    """參數原樣推給被呼叫端 T 的第 j 個(堆疊)引數 -> 以 T 該位置的實機值判型別 -> (判決, 可判被呼叫端數, 違反數)。

    每個 (T, j, 呼叫點) 套實機型別篩選的規則(最常見值合計 ≥ MIN_COVERED、≥ 80% 違反);呼叫點清不到 j 個的不算。
    暫存器轉交不用:被呼叫端入口暫存器的實機值也含其他呼叫端留下的無關值。"""
    res = []
    for t, j, site in fwds:
        if code is None or j > (pushed_args(code, base, site) or 0):
            continue
        p = profiles.get(f"{t:#x}")
        prm = p["params"].get(f"s{j}") if p else None
        if not prm:
            continue
        top = [(int(v, 16), c) for v, c in prm["top"]]
        cov = sum(c for _, c in top)
        if cov < MIN_COVERED:
            continue
        res.append(sum(c for v, c in top if violates(kind, v)) >= VIOLATION_SHARE * cov)
    if not res:
        return None, 0, 0
    return ("viol" if sum(res) >= VIOLATION_SHARE * len(res) else "ok"), len(res), sum(res)


def flow_param_verdicts(x: dict, cg, entries: list[int], sources: dict, profiles: dict[str, dict],
                        cleanups: dict[int, set[int]], argc: dict[int, int | None], code: bytes | None, base: int
                        ) -> list[tuple[int, str, str, tuple, tuple]]:
    """摘要 x 每個有型別的參數 -> (k, 名稱, 型別, 呼叫端判決, 被呼叫端判決);傳參方式對不上參數列的回 []。"""
    params, n = parse_sig(x.get("summary") or "")
    if not params or n is None:
        return []
    a = int(x["addr"], 16)
    slots = n_slots(params, n)
    starts = slot_starts(params)
    conv = role_convention(slots, cleanups.get(a, set()), argc.get(a))
    if conv is None or (conv == "reg" and slots != n):
        return []
    fw: list = []
    param_uses(cg, a, entries, slots, conv == "reg", fw, exact=True)
    out = []
    for k, pn in enumerate(params, 1):
        kind = type_of(pn)
        if not kind:
            continue
        j = starts[k - 1]
        slot = j if conv == "stack" else VC.REG_ARGS[j - 1]
        up = flow_verdict(kind, flow_values(sources, profiles, cleanups, argc, a, slot, a))
        down = down_verdict(kind, [(t, jj, site) for kk, t, jj, site in fw
                                   if kk == j and isinstance(jj, int) and t != a], profiles, code, base)
        out.append((k, pn, kind, up, down))
    return out


def _complete(p: dict | None, prm: dict | None) -> bool:
    """剖面的這個位置列出了全部相異值,且每次執行都有記明細(沒有被每份紀錄的上限截掉)。"""
    return bool(p and prm and prm["distinct"] <= len(prm["top"]) and p["calls"].get("logged") == p["calls"].get("total"))


def flow_live_consistency(sources: dict, profiles: dict[str, dict], cleanups: dict[int, set[int]],
                          argc: dict[int, int | None]) -> tuple[int, list[str]]:
    """呼叫點值流對實機紀錄的校準 -> (相符的引數數, 矛盾明細)。

    只取「函式的實機呼叫點全部在靜態呼叫點裡」的堆疊引數:各呼叫點的來源聯集後,常數直接是值、呼叫者參數 / 回傳值
    代入來源函式的實機值(來源的剖面必須完整 —— 每份紀錄記明細有上限,截掉的值會被誤判成矛盾)、'small' 允許
    < 0x10000 或小負數、'stack' 允許其餘;實機值(受測位置剖面完整)每一個都要被允許。有任何解不出的來源就不比。
    """
    ok, bad = 0, []
    for key, p in profiles.items():
        t = int(key, 16)
        sites = sources.get(t, {})
        live_sites = {int(c[1], 16) for c in p["callers"] if c[1]}
        if not live_sites or not live_sites <= set(sites):
            continue
        for j in range(1, 9):
            prm = p["params"].get(f"s{j}")
            if not _complete(p, prm):
                continue
            descs = set().union(*(sites[x][1].get(j, UNK) for x in live_sites))
            exact: set[int] = set()
            kinds: set[str] = set()
            for d in descs:
                if d is None or d == _TOP or d[0] == "load":
                    break
                if d[0] == "imm":
                    exact.add(d[1])
                elif d[0] in ("small", "stack"):
                    kinds.add(d[0])
                else:
                    src = d[1]
                    sp = profiles.get(f"{src:#x}")
                    if d[0] == "ret":
                        sprm = sp["ret"] if sp else None
                    else:
                        conv = call_conv(src, cleanups, argc)
                        sl = f"s{d[2]}" if conv == "stack" else VC.REG_ARGS[d[2] - 1] if conv == "reg" and d[2] <= 4 else None
                        sprm = sp["params"].get(sl) if sp and sl else None
                    if not _complete(sp, sprm):
                        break
                    exact |= {int(v, 16) for v, _ in sprm["top"]}
            else:
                lv = {int(v, 16) for v, _ in prm["top"]}
                odd = [v for v in lv if not (v in exact or ("small" in kinds and (v < 0x10000 or v >= 0xFFFF0000))
                                             or ("stack" in kinds and 0x10000 <= v < 0xFFFF0000))]
                if odd:
                    bad.append(f"{t:#x} s{j}:實機 {sorted(hex(v) for v in odd)} 不在靜態來源 {sorted(map(str, descs))}")
                else:
                    ok += 1
    return ok, bad


def flow_calibration(names: list[dict], cg, entries: list[int], sources: dict, profiles: dict[str, dict],
                     cleanups: dict[int, set[int]], argc: dict[int, int | None], code: bytes | None, base: int
                     ) -> tuple[dict[tuple[str, str | None, str | None], int], list[str]]:
    """param_flow 判決對實機型別判決的校準(有實機紀錄的參數,受測函式自己的實機值不用)。

    回傳 ({(方向 'up' / 'down', 靜態判決, 實機判決): 個數}, 誤報明細:靜態 'viol' 而實機 'ok')。實機判決與實機型別篩選
    同一條規則(該位置最常見值合計 ≥ MIN_COVERED、≥ 80% 違反)。
    """
    mat: dict[tuple[str, str | None, str | None], int] = {}
    fps: list[str] = []
    for x in names:
        a = int(x["addr"], 16)
        p = profiles.get(f"{a:#x}")
        params, n = parse_sig(x.get("summary") or "")
        if not p or not params or n is None:
            continue
        conv = role_convention(n_slots(params, n), cleanups.get(a, set()), argc.get(a))
        starts = slot_starts(params)
        for k, pn, kind, up, down in flow_param_verdicts(x, cg, entries, sources, profiles, cleanups, argc, code, base):
            j = starts[k - 1]
            prm = p["params"].get(f"s{j}" if conv == "stack" else VC.REG_ARGS[j - 1])
            lv = None
            if prm:
                top = [(int(v, 16), c) for v, c in prm["top"]]
                cov = sum(c for _, c in top)
                if cov >= MIN_COVERED:
                    lv = "viol" if sum(c for v, c in top if violates(kind, v)) >= VIOLATION_SHARE * cov else "ok"
            for way, v in (("up", up[0]), ("down", down[0])):
                mat[(way, v, lv)] = mat.get((way, v, lv), 0) + 1
                if v == "viol" and lv == "ok":
                    fps.append(f"{a:#x} {x['name']} 第 {k} 參數 {pn}({kind}):{way} 判違反,實機不違反")
    return mat, fps


def screen_flow(sc: Screen, names: list[dict], cg, entries: list[int], sources: dict, profiles: dict[str, dict],
                cleanups: dict[int, set[int]], argc: dict[int, int | None], code: bytes | None, base: int) -> None:
    """`param_flow`:實機型別篩選沒比到的參數(`sc.type_checked` 以外),以呼叫端值流與被呼叫端實機值判型別。"""
    for x in names:
        a = int(x["addr"], 16)
        rows = [r for r in flow_param_verdicts(x, cg, entries, sources, profiles, cleanups, argc, code, base)
                if (a, r[0]) not in sc.type_checked]
        if rows:
            _bump(sc, "param_flow 函式")
        for k, pn, kind, up, down in rows:
            if up[0] is None and down[0] is None:
                continue
            _bump(sc, "param_flow 可比")
            if up[0]:
                _bump(sc, "param_flow 可比(呼叫端)")
            if down[0]:
                _bump(sc, "param_flow 可比(被呼叫端)")
            if "viol" in (up[0], down[0]):
                sc.cands.append(Cand(a, x["name"], "param_flow", f"p{k}",
                                     f"第 {k} 參數 {pn}({kind}):呼叫點 {up[2]} / {up[1]} 個違反;"
                                     f"轉交的被呼叫端 {down[2]} / {down[1]} 個違反", [list(up), list(down)]))


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
    cleanups = call_cleanups(st.code, st.base, set(st.entries))
    screen_static_count(sc, names, cleanups, st.argc)
    cg = CG(CC.EXE)
    screen_roles(sc, names, cg, st.entries, st.argc, cleanups, st.code, st.base)
    sources = arg_sources(cg, st.entries, st.code, st.base, st.fixups, st.thunk_of, cleanups, st.argc)
    screen_flow(sc, names, cg, st.entries, sources, profiles, cleanups, st.argc, st.code, st.base)
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
    chk("「三個參數」讀不出個數(不可當 1 個)", parse_sig("(三個參數照轉) …"), (["三個參數照轉"], None))
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
    chk("實機比過個數的函式記入 count_checked(靜態版跳過它們)", sc.count_checked,
        {0x100, 0x200, 0x300, 0x400, 0x500, 0x700})
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
    screen_roles(rsc2, real_names, rcg, st.entries, st.argc, clean, st.code, st.base)
    n_cmp = rsc2.denom.get("param_role 可比", 0)
    chk("真實 param_role 可比 ≥ 90(續一百一十二含轉交)", n_cmp >= 90, True)
    chk("真實 param_role 可比(含轉交)≥ 40", rsc2.denom.get("param_role 可比(含轉交)", 0) >= 40, True)
    rsc2n = Screen()
    screen_roles(rsc2n, real_names, rcg, st.entries, st.argc, clean)
    chk("不給 code 就不追轉交(可比較少)", rsc2n.denom.get("param_role 可比", 0) < n_cmp, True)
    ru = role_uses(rcg, st.code, st.base, st.entries, 0x1E7F6, 4, False, {}) or {}
    chk("draw_unit_hp_bar 第 1 個:add eax, [esp+0x10] 衍生後轉給 draw_hp_bar 的目的(只經轉交寫入)",
        (ru.get(1, {}).get("w"), ru.get(1, {}).get("fw", 0) > 0), (0, True))
    bt = role_uses(rcg, st.code, st.base, st.entries, 0x4ED34, 3, False, {}) or {}
    chk("blit_image_transparent:edi / esi 經暫存器轉交給核心 -> 第 1 個寫、第 2 個讀",
        (bt.get(1, {}).get("fw", 0) > 0, bt.get(1, {}).get("fr", 0), bt.get(2, {}).get("fr", 0) > 0,
         bt.get(2, {}).get("fw", 0)), (True, 0, True, 0))

    def flip(x: dict) -> dict:
        ps, _ = parse_sig(x.get("summary") or "")
        if not ps:
            return x
        swap = {"dst": "src", "src": "dst"}
        new = [swap[role_of(p)] if role_of(p) else p for p in ps]
        rest = (x.get("summary") or "")[VC.PARAMS.match(x["summary"]).end():]
        return {**x, "summary": "(" + ", ".join(new) + ")" + rest}

    rsc3 = Screen()
    screen_roles(rsc3, [flip(x) for x in real_names], rcg, st.entries, st.argc, clean, st.code, st.base)
    hit = sum(c.screen == "param_role" for c in rsc3.cands)
    print(f"    (角色全部對調的對照:{hit} / {rsc3.denom.get('param_role 可比', 0)} 觸發;原本 {len(rsc2.cands)})")
    chk("對照:角色全部對調後 ≥ 90% 觸發(篩選分得出讀寫)", hit >= 0.9 * rsc3.denom.get("param_role 可比", 1), True)
    run_sc = run(REVIEW_JSON)[0]
    chk("run() 有接上角色篩選(分母與單獨跑相同)", run_sc.denom.get("param_role 可比"), n_cmp)
    chk("run() 有接上靜態個數篩選(兩種分母都非零)",
        (run_sc.denom.get("param_count 可比(靜態清堆疊)", 0) > 0, run_sc.denom.get("param_count 可比(靜態 argc)", 0) > 0),
        (True, True))
    chk("真實:靜態個數篩選不重比實機比過的函式", any(c.addr in real.count_checked and "靜態" in c.detail
                                            for c in run_sc.cands), False)

    print("[13] 續一百一十二:格數、靜態個數、轉交、指標衍生")
    chk("double 佔 2 格", slot_starts(["double", "輸出"]), [1, 3])
    chk("double* 是指標佔 1 格", slot_starts(["double*", "x"]), [1, 2])
    chk("格數:(double, n) = 3", n_slots(["double", "n"], 2), 3)
    chk("格數:(3 個參數) = 3", n_slots([], 3), 3)
    chk("格數:讀不出個數 -> None", n_slots(["a", "..."], None), None)
    dprof = {"0x100": prof([[None, "0x2020", "direct", 5]],
                           {"s1": {"top": small_top}, "s3": {"top": ptr_top}}, [["0x0", 9]])}
    dsc = screen([{"addr": "0x100", "name": "f", "summary": "(double, x):…"}], dprof, bytes(ccode), 0x2000)
    chk("實機:(double, x) 呼叫端清 3 個 -> 個數相符;x 取 s3", sorted((c.screen, c.key) for c in dsc.cands),
        [("param_type", "s3")])
    snames = [{"addr": f"{a:#x}", "name": f"f{a:x}", "summary": sm} for a, sm in (
        (0x10, "(a, b):…"), (0x20, "(a, b):…"), (0x30, "(double, x):…"), (0x40, "(a, b):…"), (0x50, "(a, b):…"),
        (0x60, "(a, b):…"), (0x70, "(a, b, c):…"), (0x80, "(三個參數):…"), (0x90, "(a, b):…"))]
    ssc = Screen(count_checked={0x70})
    screen_static_count(ssc, snames, {0x10: {3}, 0x20: {2}, 0x30: {3}, 0x60: {2, 3}, 0x70: {2}, 0x80: {3}},
                        {0x40: 3, 0x50: 1, 0x60: 3, 0x90: 0})
    chk("靜態個數:清 3 / 2 格、argc 3 > 2 -> 候選;double、argc 較少、多值、實機比過、讀不出個數、argc 0 不報",
        sorted(c.addr for c in ssc.cands), [0x10, 0x40])
    chk("靜態個數分母(清堆疊 3、argc 2)", (ssc.denom.get("param_count 可比(靜態清堆疊)"),
                                       ssc.denom.get("param_count 可比(靜態 argc)")), (3, 2))
    chk("靜態候選與實機版同鍵", {(c.screen, c.key) for c in ssc.cands}, {("param_count", "count")})

    def U2(body: list[tuple[str, str]], n: int = 2):
        return param_uses(_G({0: body}), 0, [], n, False)

    chk("add r, [堆疊參數]:r 原本沒裝參數 -> 衍生", U2([("mov", "eax, 0x10"), ("add", "eax, dword ptr [esp + 4]"),
                                                ("mov", "byte ptr [eax], 1"), RET], n=1), {1: W1})
    chk("add r1, r2:r2 裝參數 -> r1 衍生", U2([("mov", "edx, dword ptr [esp + 4]"), ("mov", "eax, 0x10"),
                                         ("add", "eax, edx"), ("mov", "byte ptr [eax], 1"), RET]), {1: W1})
    chk("add 已裝參數的 r 加另一個參數 -> 兩個都算(續一百一十三聯集)",
        U2([("mov", "eax, dword ptr [esp + 4]"), ("add", "eax, dword ptr [esp + 8]"), ("mov", "byte ptr [eax], 1"),
            RET]), {1: W1, 2: W1})
    chk("add 超過 n 的堆疊參數不對應", U2([("mov", "eax, 0"), ("add", "eax, dword ptr [esp + 8]"),
                                    ("mov", "byte ptr [eax], 1"), RET], n=1), {})
    chk("lea 唯一不帶倍率的暫存器 -> 衍生", U2([("mov", "edx, dword ptr [esp + 4]"), ("lea", "eax, [ecx + edx]"),
                                         ("mov", "byte ptr [eax], 1"), RET]), {1: W1})
    chk("lea 帶倍率不算", U2([("mov", "edx, dword ptr [esp + 4]"), ("lea", "eax, [ecx + edx*4]"),
                          ("mov", "byte ptr [eax], 1"), RET]), {})
    chk("lea 兩個參數 -> 兩個都算(續一百一十三聯集)", U2([("mov", "edx, dword ptr [esp + 4]"),
                                                 ("mov", "ecx, dword ptr [esp + 8]"), ("lea", "eax, [ecx + edx]"),
                                                 ("mov", "byte ptr [eax], 1"), RET]), {1: W1, 2: W1})
    fw: list = []
    param_uses(_G({0: [("push", "dword ptr [esp + 8]"), ("push", "dword ptr [esp + 8]"), ("call", "0x100"),
                       ("add", "esp, 8"), RET]}), 0, [], 2, False, fw)
    chk("轉交:兩個堆疊參數依序推入 -> (k, 目標, 第 j 個引數, 呼叫點)", fw, [(2, 0x100, 2, 2), (1, 0x100, 1, 2)])
    fw2: list = []
    param_uses(_G({0: [("push", "dword ptr [esp + 4]"), ("add", "esp, 4"), ("call", "0x100"), RET]}), 0, [], 1,
               False, fw2)
    chk("轉交:推入後被彈掉的不算", fw2, [])
    fw2b: list = []
    param_uses(_G({0: [("push", "dword ptr [esp + 4]"), ("add", "esp, 4"), ("push", "5"), ("call", "0x100"),
                       ("add", "esp, 4"), RET]}), 0, [], 1, False, fw2b)
    chk("轉交:彈掉後同一深度改推常數,不可沿用舊的參數", fw2b, [])
    fw2c: list = []
    param_uses(_G({0: [("push", "dword ptr [esp + 8]"), ("call", "0x100"), ("add", "esp, 4"), RET]}), 0, [], 1, False,
               fw2c)
    chk("轉交:超過 n 的堆疊參數不記", fw2c, [])
    fw3: list = []
    param_uses(_G({0: [("mov", "edi, dword ptr [esp + 4]"), ("call", "0x100"), RET]}), 0, [], 1, False, fw3)
    chk("轉交:call 當下暫存器裡的參數也記", fw3, [(1, 0x100, "edi", 1)])
    chk("init 指定入口暫存器", param_uses(_G({0: [("stosb", "byte ptr es:[edi], al"), RET]}), 0, [], 0, False,
                                       None, {"edi": 1}), {1: W1})

    # 合成:0x0 / 0x200 把兩個堆疊參數推給 0x100(第 1 個寫、第 2 個讀);0x300 只清 1 個;0x400 以 edi / esi 交給 0x500
    fbody = [("push", "dword ptr [esp + 8]"), ("push", "dword ptr [esp + 8]"), ("call", "0x100"),
             ("add", "esp, 8"), RET]
    freg = [("mov", "edi, dword ptr [esp + 4]"), ("mov", "esi, dword ptr [esp + 8]"), ("call", "0x500"), RET]
    core = [("lodsb", "al, byte ptr [esi]"), ("stosb", "byte ptr es:[edi], al"), RET]
    gf = _G({0x0: fbody, 0x100: body, 0x200: fbody, 0x300: fbody, 0x400: freg, 0x500: core, 0x600: freg})
    fcode = bytearray(b"\x90" * 0x700)
    for site, cl in ((0x2, 8), (0x202, 8), (0x302, 4)):
        fcode[site:site + 8] = b"\xe8\0\0\0\0\x83\xc4" + bytes((cl,))
    fnames = [{"addr": "0x0", "name": "f_ok", "summary": "(dst, src):…"},
              {"addr": "0x200", "name": "f_swap", "summary": "(src, dst):…"},
              {"addr": "0x300", "name": "f_short", "summary": "(dst, src):…"},
              {"addr": "0x400", "name": "f_reg_ok", "summary": "(dst, src):…"},
              {"addr": "0x600", "name": "f_reg_swap", "summary": "(src, dst):…"}]
    fents = [0x0, 0x100, 0x200, 0x300, 0x400, 0x500, 0x600]
    fcl = {0x0: {2}, 0x200: {2}, 0x300: {2}, 0x400: {2}, 0x600: {2}}
    fsc = Screen()
    screen_roles(fsc, fnames, gf, fents, {}, fcl, bytes(fcode), 0)
    chk("轉交:名稱對調的兩個函式(堆疊、暫存器)各 2 個候選;正確的不報", sorted((c.addr, c.key) for c in fsc.cands),
        [(0x200, "p1"), (0x200, "p2"), (0x600, "p1"), (0x600, "p2")])
    chk("轉交:呼叫點只清 1 個 -> 第 2 個不算(可比 = 4 函式 x 2 + 1)",
        (fsc.denom.get("param_role 可比"), fsc.denom.get("param_role 可比(含轉交)")), (9, 9))
    chk("候選明細的讀次數含轉交(f_swap 第 2 個只經轉交讀 1 次)",
        [c.detail for c in fsc.cands if (c.addr, c.key) == (0x200, "p2") and "讀 1 次" in c.detail] != [], True)
    dnames = [{"addr": "0x0", "name": "f_dbl", "summary": "(double, 輸出):…"},
              {"addr": "0x100", "name": "f_dblreg", "summary": "(double, 輸出):…"}]
    dg = _G({0x0: [("mov", "eax, dword ptr [esp + 0xc]"), ("mov", "byte ptr [eax], 1"), RET],
             0x100: [("mov", "byte ptr [ebx], 1"), RET]})
    dsc2 = Screen()
    screen_roles(dsc2, dnames, dg, [0x0, 0x100], {0x100: 0}, {0x0: {3}})
    chk("double 後的參數取第 3 格、清 3 個才算堆疊;double 走暫存器不比",
        (dsc2.denom.get("param_role 函式"), dsc2.denom.get("param_role 可比"), dsc2.cands), (1, 1, []))
    fsc0 = Screen()
    screen_roles(fsc0, fnames, gf, fents, {}, fcl)
    chk("不給 code 就沒有轉交:全部零存取、不可比", (fsc0.denom.get("param_role 可比"), fsc0.cands), (None, []))
    deep = _G({0x0: fbody, 0x100: fbody, 0x200: fbody, 0x300: fbody, 0x400: fbody, 0x500: body})
    dcode = bytearray(b"\x90" * 0x600)
    for site in (0x2, 0x102, 0x202, 0x302, 0x402):
        dcode[site:site + 8] = b"\xe8\0\0\0\0\x83\xc4\x08"
    for a, op in ((0x0, "0x100"), (0x100, "0x200"), (0x200, "0x300"), (0x300, "0x400"), (0x400, "0x500")):
        deep.m[a + 2] = _I(a + 2, "call", op)
    dents = [0x0, 0x100, 0x200, 0x300, 0x400, 0x500]
    chk(f"轉交深度上限 {FWD_DEPTH}:第 5 層才寫入的追不到", role_uses(deep, bytes(dcode), 0, dents, 0x0, 2, False, {}),
        {})
    chk("轉交深度上限:從第 1 層起算追得到", role_uses(deep, bytes(dcode), 0, dents, 0x100, 2, False, {}),
        {1: {"r": 0, "w": 0, "fr": 0, "fw": 1}, 2: {"r": 0, "w": 0, "fr": 1, "fw": 0}})
    chk("不是已知入口的呼叫目標不追", role_uses(deep, bytes(dcode), 0, [0x400], 0x400, 2, False, {}), {})
    shared: dict = {}
    role_uses(deep, bytes(dcode), 0, dents, 0x0, 2, False, shared)
    chk("共用 memo:先從第 0 層走過(較深處被截斷)再問第 1 層,結果與單獨問相同",
        role_uses(deep, bytes(dcode), 0, dents, 0x100, 2, False, shared),
        role_uses(deep, bytes(dcode), 0, dents, 0x100, 2, False, {}))

    print("[14] 續一百一十三:控制流引擎、堆疊 / 全域槽、零存取的五種原因")
    rsrc0 = arg_sources(rcg, st.entries, st.code, st.base, st.fixups, st.thunk_of, clean, st.argc)
    # 共用尾段:兩條路徑各推 0 / 5 再進同一個 call(依位址順序只看得到 5)
    tail = [("cmp", "eax, 1"), ("jne", "0x4"), ("push", "0"), ("jmp", "0x5"), ("push", "5"), ("call", "0x100"),
            ("add", "esp, 4"), RET]
    tcode = bytearray(b"\x90" * 0x200)
    tcode[5:13] = b"\xe8\0\0\0\0\x83\xc4\x04"
    tg = _G({0: tail, 0x100: [RET]})
    ts = arg_sources(tg, [0, 0x100], bytes(tcode), 0, {}, {}, {}, {})
    chk("合流:共用尾段的引數 = 兩條路徑的聯集 {0, 5}", ts[0x100][5][1][1], frozenset({("imm", 0), ("imm", 5)}))
    chk("呼叫點記呼叫者", ts[0x100][5][0], 0)
    ts2 = arg_sources(_G({0: [("push", "0x3a30"), ("call", "0x100"), ("add", "esp, 4"), RET], 0x100: [RET]}), [0, 0x100],
                      bytes(b"\x90" + b"\xe8\0\0\0\0\x83\xc4\x04" + b"\x90" * 0x200), 0, {1 - 4: 0x53A30}, {}, {}, {})
    chk("位址常數套 fixup -> 執行期值(obj2 + 0x19c000;合成指令長 1,立即值位置 = 位址 + 1 - 4)", ts2[0x100][1][1][1],
        frozenset({("imm", 0x53A30 + VC.DELTA)}))
    chk("fixup 不在立即值位置(只有位移有)-> 立即值不重定位",
        _value_step(_I(0x10, "mov", "dword ptr [0x3c57], 0"), (0, None), {}, 0, {0x10: 0x53C57}, set()),
        {("g", 0x53C57): frozenset({("imm", 0)})})
    chk("真實:0x28ee1 / 0x291f5 推的 esi 是 [0x53c57] 的內容(0),不是它的位址",
        all(("imm", 0x1EFC57) not in rsrc0[0x1B8E7][x][1][2] for x in (0x28EE1, 0x291F5)), True)
    chk("obj3(>= 0x60000)位移不同", _runtime(0x602AD), 0x602AD + VC.OBJ3_DELTA)
    stg = [("sub", "esp, 4"), ("mov", "dword ptr [esp], 7"), ("call", "0x100"), ("add", "esp, 4"), RET]
    scode = bytearray(b"\x90" * 0x200)
    scode[2:10] = b"\xe8\0\0\0\0\x83\xc4\x04"
    chk("mov [esp], 7 預先放的引數", arg_sources(_G({0: stg, 0x100: [RET]}), [0, 0x100], bytes(scode), 0, {}, {}, {},
                                              {})[0x100][2][1][1], frozenset({("imm", 7)}))
    nocl = arg_sources(_G({0: [("push", "9"), ("call", "0x100"), ("jmp", "0x300")], 0x100: [RET], 0x300: [RET]}),
                       [0, 0x100, 0x300], bytes(0x400), 0, {}, {}, {}, {0x100: 1})
    chk("呼叫點後面沒有 add esp -> 引數個數取被呼叫端 argc", nocl[0x100][1][1].get(1), frozenset({("imm", 9)}))
    chk("值流:byte 載入 -> small、lea [esp+X] -> stack、xor r, r -> 0",
        [_value_step(_I(0, m, o), (4, None), {}, 0, {}, set())[r] for m, o, r in
         (("movzx", "eax, byte ptr [ebx]", "eax"), ("lea", "eax, [esp + 8]", "eax"), ("xor", "ecx, ecx", "ecx"))],
        [_SMALL, frozenset({("stack",)}), frozenset({("imm", 0)})])
    chk("值流:寫子暫存器,原本不明 -> 不明;原本小 -> 小",
        (_value_step(_I(0, "mov", "al, 1"), (0, None), {}, 0, {}, set()).get("eax"),
         _value_step(_I(0, "mov", "al, 1"), (0, None), {"eax": frozenset({("imm", 3)})}, 0, {}, set()).get("eax")),
        (None, _SMALL))
    chk("值流:call 之後 eax = 回傳值、ecx / edx 失效",
        _value_step(_I(0, "call", "0x100"), (0, None), {"ecx": frozenset({("imm", 1)})}, 0, {}, {0x100}),
        {"eax": frozenset({("ret", 0x100)})})
    chk("值流:pop 取回堆疊頂", _value_step(_I(0, "pop", "edx"), (4, None), {4: frozenset({("imm", 2)})}, 0, {}, set()),
        {4: frozenset({("imm", 2)}), "edx": frozenset({("imm", 2)})})
    chk("合流:超過 CAP 個可能值 -> 不明,且之後一直不明(單調)",
        (_join({"eax": frozenset(("imm", v) for v in range(CAP))}, {"eax": frozenset({("imm", 99)})}, UNK),
         _join({"eax": frozenset({_TOP})}, {"eax": frozenset({("imm", 1)})}, UNK)),
        ({"eax": frozenset({_TOP})}, {"eax": frozenset({_TOP})}))
    chk("合流:參數追蹤一邊沒有 = 空集合(取聯集)", _join({"eax": frozenset({1})}, {}, frozenset()), {"eax": frozenset({1})})
    chk("合流:值流一邊沒有 = 不明(None 併入)", _join({"eax": frozenset({("imm", 1)})}, {}, UNK),
        {"eax": frozenset({("imm", 1), None})})
    loop = [("mov", "ecx, 0"), ("push", "ecx"), ("call", "0x100"), ("add", "esp, 4"), ("inc", "ecx"), ("cmp", "ecx, 3"),
            ("jl", "0x1"), RET]
    lcode = bytearray(b"\x90" * 0x200)
    lcode[2:10] = b"\xe8\0\0\0\0\x83\xc4\x04"
    chk("迴圈:定點會停(inc 使 ecx 不明,入口的 0 與回邊的不明合流)",
        arg_sources(_G({0: loop, 0x100: [RET]}), [0, 0x100], bytes(lcode), 0, {}, {}, {}, {})[0x100][2][1][1],
        frozenset({("imm", 0), None}))
    chk("[ebp - 8] 是區域變數(深度 = 框架基底 + 8)", _depth("dword ptr [ebp - 8]", 12, 4), 12)
    chk("[esp] 沒有位移也是堆疊", _depth("dword ptr [esp]", 8, None), 8)
    chk("[esp + eax*4] 不是單純堆疊參考", _depth("dword ptr [esp + eax*4]", 8, None), None)
    chk("參數暫存到區域變數再讀回", U2([("sub", "esp, 4"), ("mov", "eax, dword ptr [esp + 8]"),
                                 ("mov", "dword ptr [esp], eax"), ("mov", "ecx, dword ptr [esp]"),
                                 ("mov", "byte ptr [ecx], 1"), ("add", "esp, 4"), RET]), {1: W1})
    chk("ebp 框架:參數存到 [ebp - 4] 再讀回", U2([("push", "ebp"), ("mov", "ebp, esp"), ("sub", "esp, 4"),
                                          ("mov", "eax, dword ptr [ebp + 8]"), ("mov", "dword ptr [ebp - 4], eax"),
                                          ("mov", "ecx, dword ptr [ebp - 4]"), ("mov", "byte ptr [ecx], 1"),
                                          ("add", "esp, 4"), ("pop", "ebp"), RET]), {1: W1})
    chk("push / pop 搬運", U2([("mov", "eax, dword ptr [esp + 4]"), ("push", "eax"), ("pop", "edx"),
                            ("mov", "byte ptr [edx], 1"), RET]), {1: W1})
    chk("區域變數被其他值覆寫 -> 失效", U2([("sub", "esp, 4"), ("mov", "eax, dword ptr [esp + 8]"),
                                    ("mov", "dword ptr [esp], eax"), ("mov", "dword ptr [esp], 0"),
                                    ("mov", "ecx, dword ptr [esp]"), ("mov", "byte ptr [ecx], 1"), ("add", "esp, 4"),
                                    RET]), {})
    chk("全域槽:存進 [0x1000] 再讀回", U2([("mov", "eax, dword ptr [esp + 4]"), ("mov", "dword ptr [0x1000], eax"),
                                     ("mov", "edi, dword ptr [0x1000]"), ("stosb", "byte ptr es:[edi], al"), RET]),
        {1: W1})
    chk("全域槽只追 dword", U2([("mov", "eax, dword ptr [esp + 4]"), ("mov", "word ptr [0x1000], ax"),
                            ("mov", "edi, dword ptr [0x1000]"), ("stosb", "byte ptr es:[edi], al"), RET]), {})
    chk("全域槽的鍵:有 fixup 用目標、沒有用印出的位移",
        (_gslot("dword ptr [0x27ac]", 0x627AC), _gslot("dword ptr [0x27ac]"), _gslot("byte ptr [0x27ac]")),
        (("g", 0x627AC), ("g", 0x27AC), None))
    chk("指令的第一個 fixup(位移在立即值前)", _mem_fix(_I(0x10, "mov", "x"), {0x10: 5, 0x13: 9}), 5)
    chk("索引在前、指標在後的 [esi + ebx]", U2([("mov", "ebx, dword ptr [esp + 4]"), ("mov", "byte ptr [esi + ebx], 1"),
                                          RET]), {1: W1})
    chk("帶倍率的索引不算", U2([("mov", "ebx, dword ptr [esp + 4]"), ("mov", "byte ptr [esi + ebx*4], 1"), RET]), {})
    for ah, want in ((0x41, {1: R1}), (0x3F, {1: W1}), (0x30, {})):
        chk(f"int 21h AH={ah:#x}:DS:EDX {want}", U2([("mov", "edx, dword ptr [esp + 4]"), ("mov", f"ah, {ah:#x}"),
                                                    ("int", "0x21"), RET], n=1), want)
    chk("int 21h:AH 由 mov eax, imm 設定", U2([("mov", "edx, dword ptr [esp + 4]"), ("mov", "eax, 0x4100"),
                                           ("int", "0x21"), RET], n=1), {1: R1})
    chk("int 21h:中間有其他寫 eax 的指令 -> 不判", U2([("mov", "edx, dword ptr [esp + 4]"), ("mov", "ah, 0x41"),
                                                ("inc", "eax"), ("int", "0x21"), RET], n=1), {})
    chk("int 21h:不寫 eax 的指令跳過", _dos_ah([_I(0, "mov", "ah, 0x41")] + [_I(0, "nop", "")] * 6), 0x41)
    fx: list = []
    param_uses(_G({0: [("mov", "eax, dword ptr [esp + 4]"), ("add", "eax, dword ptr [esp + 8]"), ("push", "eax"),
                       ("call", "0x100"), ("add", "esp, 4"), RET]}), 0, [], 2, False, fx, exact=True)
    fn: list = []
    param_uses(_G({0: [("mov", "eax, dword ptr [esp + 4]"), ("add", "eax, dword ptr [esp + 8]"), ("push", "eax"),
                       ("call", "0x100"), ("add", "esp, 4"), RET]}), 0, [], 2, False, fn)
    chk("exact:base + x 不算原樣轉交;一般模式兩個都算", ([f for f in fx if isinstance(f[2], int)],
                                               sorted(f[0] for f in fn if isinstance(f[2], int))), ([], [1, 2]))
    fx2: list = []
    param_uses(_G({0: [("mov", "eax, dword ptr [esp + 4]"), ("add", "eax, 4"), ("inc", "eax"), ("push", "eax"),
                       ("call", "0x100"), ("add", "esp, 4"), RET]}), 0, [], 1, False, fx2, exact=True)
    chk("exact:加減常數 / inc 仍是同一個值的型別", [f[0] for f in fx2 if isinstance(f[2], int)], [1])
    chk("exact:lea [r + 常數] 是複製、lea [r1 + r2] 不是",
        (_param_step(_I(0, "lea", "eax, [ebx + 4]"), (0, None), {"ebx": frozenset({1})}, 1, False, True).get("eax"),
         _param_step(_I(0, "lea", "eax, [ebx + ecx]"), (0, None), {"ebx": frozenset({1})}, 1, False, True).get("eax")),
        (frozenset({1}), None))
    # jmp 到本體外的共用收尾段:callee_argc 判不出,但照走
    wrap = _G({0: [("push", "ebx"), ("mov", "eax, dword ptr [esp + 8]"), ("mov", "byte ptr [eax], 1"), ("jmp", "0x100")],
               0x100: [("pop", "ebx"), RET]})
    chk("(前提)jmp 出本體時位移不為 0 -> callee_argc 判不出", DNA.callee_argc(wrap, 0, [0, 0x100]),
        (None, "leaf without clean ret"))
    chk("jmp 到共用收尾段的本體照走(AIL API 包裝)", param_uses(wrap, 0, [0, 0x100], 1, False), {1: W1})
    chk("沒有 ret 也沒有跳出本體 -> 仍是 None", param_uses(_G({0: [("mov", "eax, dword ptr [esp + 4]"),
                                                           ("jmp", "eax")]}), 0, [0], 1, False), None)
    # 全域槽逃逸:0x0 把參數存進 [0x1000];0x100 讀它寫入;0x200 讀的是另一個物件的同一個位移
    esc = _G({0x0: [("mov", "eax, dword ptr [esp + 4]"), ("mov", "dword ptr [0x1000], eax"), RET],
              0x100: [("mov", "edi, dword ptr [0x1000]"), ("stosb", "byte ptr es:[edi], al"), RET],
              0x200: [("mov", "esi, dword ptr [0x1000]"), ("lodsb", "al, byte ptr [esi]"), RET]})
    esc._s113_fixups = {0x1: 0x51000, 0x100: 0x51000, 0x200: 0x61000}
    chk("全域槽逃逸:讀同一個槽的函式寫入 -> fw;另一個物件的同位移不算",
        role_uses(esc, b"", 0, [0x0, 0x100, 0x200], 0x0, 1, False, {}), {1: {"r": 0, "w": 0, "fr": 0, "fw": 1}})
    esc2 = _G({0x0: [("mov", "eax, dword ptr [esp + 4]"), ("mov", "dword ptr [0x1000], eax"), RET],
               0x100: [("mov", "dword ptr [0x1000], 0"), ("mov", "edi, dword ptr [0x1000]"),
                       ("stosb", "byte ptr es:[edi], al"), RET]})
    chk("全域槽逃逸:讀之前自己先寫過該槽的函式不算", role_uses(esc2, b"", 0, [0x0, 0x100], 0x0, 1, False, {}), {})
    # 呼叫點沒有 add esp:轉交的引數個數取被呼叫端讀到的個數
    nw = _G({0x0: [("push", "dword ptr [esp + 4]"), ("call", "0x100"), ("jmp", "0x200")],
             0x100: [("mov", "eax, dword ptr [esp + 4]"), ("mov", "byte ptr [eax], 1"), RET], 0x200: [RET]})
    ncode = bytearray(b"\x90" * 0x300)
    ncode[1:6] = b"\xe8\0\0\0\0"
    chk("呼叫點沒有清堆疊 -> 以被呼叫端 argc 追轉交", role_uses(nw, bytes(ncode), 0, [0x0, 0x100, 0x200], 0x0, 1, False,
                                                  {}), {1: {"r": 0, "w": 0, "fr": 0, "fw": 1}})

    print("[15] 續一百一十三:param_flow(合成)")
    chk("flow_verdict:全部違反 -> viol", flow_verdict("small", {1: {0x1F6C80}, 2: {0x1F6C90}}), ("viol", 2, 2))
    chk("flow_verdict:4 / 5 違反(80%)-> viol", flow_verdict("small", {i: {0x1F6C80} if i < 4 else {5}
                                                                        for i in range(5)}), ("viol", 5, 4))
    chk("flow_verdict:3 / 5 -> ok", flow_verdict("small", {i: {0x1F6C80} if i < 3 else {5} for i in range(5)}),
        ("ok", 5, 3))
    chk("flow_verdict:呼叫點的值有一個不違反就不算違反", flow_verdict("small", {1: {0x1F6C80, 7}}), ("ok", 1, 0))
    chk("flow_verdict:解不出的呼叫點不算分母;全部解不出 -> None",
        (flow_verdict("small", {1: {0x1F6C80}, 2: None}), flow_verdict("small", {1: None})), (("viol", 1, 1), (None, 0, 0)))
    chk("抽象值:small 違反 ptr / str、stack 違反 unit / small、stack 不違反 ptr",
        [_flow_violates(k, v) for k, v in (("ptr", "small"), ("str", "small"), ("unit", "stack"), ("small", "stack"),
                                            ("ptr", "stack"), ("unit", "small"))], [True, True, True, True, False, False])
    fprof = {"0x900": prof([], {"s1": {"top": [["0x1f6c80", 9]]}}, [["0x1f6c80", 9]], argc=1)}
    fsrc = {0x100: {0x10: (0x900, {1: frozenset({("param", 0x900, 1)})}), 0x20: (0x800, {1: frozenset({("ret", 0x900)})}),
                    0x30: (0x800, {1: frozenset({("load", 0x5000)})}), 0x40: (0x700, {1: frozenset({("param", 0x700, 1)})})},
            0x700: {0x50: (0x900, {1: frozenset({("imm", 3)})})}}
    fcl = {0x100: {1}, 0x700: {1}, 0x900: {1}}
    fv = flow_values(fsrc, fprof, fcl, {}, 0x100, 1, 0x100)
    chk("flow_values:呼叫者參數 -> 它的實機值;回傳值 -> 被呼叫者的實機回傳;全域載入解不出;沒紀錄的呼叫者往上追",
        fv, {0x10: {0x1F6C80}, 0x20: {0x1F6C80}, 0x30: None, 0x40: {3}})
    chk("flow_values:受測函式自己的實機值不用", flow_values(fsrc, fprof, fcl, {}, 0x100, 1, 0x900)[0x10], None)
    chk(f"flow_values:往上追最多 {FLOW_DEPTH} 層", flow_values(
        {0x100: {1: (0x200, {1: frozenset({("param", 0x200, 1)})})}, 0x200: {2: (0x300, {1: frozenset({("param", 0x300, 1)})})},
         0x300: {3: (0x400, {1: frozenset({("param", 0x400, 1)})})}, 0x400: {4: (0x500, {1: frozenset({("param", 0x500, 1)})})},
         0x500: {5: (0x600, {1: frozenset({("imm", 1)})})}},
        {}, {a: {1} for a in range(0x100, 0x700, 0x100)}, {}, 0x100, 1, 0)[1], None)
    dprof = {"0x500": prof([], {"s1": {"top": [["0x1f6c80", 9]]}, "s2": {"top": [["0x5", 2]]}}, [["0x0", 9]], argc=2)}
    dcode = bytearray(b"\x90" * 0x100)
    dcode[0x10:0x18] = b"\xe8\0\0\0\0\x83\xc4\x04"
    chk("down_verdict:被呼叫端該位置實機是指標 -> small 違反", down_verdict("small", [(0x500, 1, 0x10)], dprof, bytes(dcode), 0),
        ("viol", 1, 1))
    chk("down_verdict:呼叫點清不到第 j 個 / 次數 < MIN_COVERED / 沒紀錄都不算",
        [down_verdict("small", f, dprof, bytes(dcode), 0)[0] for f in ([(0x500, 2, 0x10)], [(0x600, 1, 0x10)])],
        [None, None])
    dcode2 = bytearray(dcode)
    dcode2[0x17] = 8
    chk("down_verdict:次數 2 < MIN_COVERED 不算", down_verdict("small", [(0x500, 2, 0x10)], dprof, bytes(dcode2), 0),
        (None, 0, 0))
    # screen_flow:實機比過型別的參數不再比;候選鍵 p<k>
    sg = _G({0x100: [("mov", "eax, dword ptr [esp + 4]"), ("mov", "eax, dword ptr [esp + 8]"), RET]})
    ssrc = {0x100: {0x10: (0x900, {1: frozenset({("imm", 0x1F6C80)}), 2: frozenset({("imm", 0x1F6C80)})})}}
    snm = [{"addr": "0x100", "name": "f", "summary": "(x, y):…"}]
    ssc = Screen()
    screen_flow(ssc, snm, sg, [0x100], ssrc, {}, {0x100: {2}}, {}, None, 0)
    chk("screen_flow:兩個 small 參數都收到指標 -> p1 / p2 候選", sorted((c.screen, c.key) for c in ssc.cands),
        [("param_flow", "p1"), ("param_flow", "p2")])
    ssc2 = Screen(type_checked={(0x100, 1)})
    screen_flow(ssc2, snm, sg, [0x100], ssrc, {}, {0x100: {2}}, {}, None, 0)
    chk("screen_flow:實機比過的 p1 不再比", [c.key for c in ssc2.cands], ["p2"])
    chk("screen_flow 分母", (ssc.denom.get("param_flow 函式"), ssc.denom.get("param_flow 可比"),
                           ssc.denom.get("param_flow 可比(呼叫端)")), (1, 2, 2))
    ssc3 = Screen()
    screen_flow(ssc3, snm, sg, [0x100], ssrc, {}, {0x100: {3}}, {}, None, 0)
    chk("screen_flow:清堆疊個數對不上參數列 -> 不比", (ssc3.cands, ssc3.denom), ([], {}))
    chk("實機篩選比過的參數記進 type_checked", sorted(dsc.type_checked), [(0x100, 2)])

    print("[16] 續一百一十三:真實 EXE 與實機紀錄校準")
    rsrc = rsrc0
    s0x1237c = rsrc[0x126F7][0x1237C][1][3]
    chk("真實:0x1237c 共用尾段(0x122f7 jmp 進來)的第 3 個引數含 0 / 1 / 5(依位址順序只有 5)",
        {("imm", 0), ("imm", 1), ("imm", 5)} <= s0x1237c, True)
    chk("真實:0x1eb1c 推的位址常數套 fixup = 實機值 0x1efa30", rsrc[0x1EC2A][0x1EB1C][1][1],
        frozenset({("imm", 0x1EFA30)}))
    n_ok, cbad = flow_live_consistency(rsrc, real_prof, clean, st.argc)
    print(f"    (呼叫點值流對實機:相符 {n_ok}、矛盾 {len(cbad)})")
    chk("校準:呼叫點值流對實機零矛盾", cbad, [])
    chk("校準:相符的引數 ≥ 250(不是空跑)", n_ok >= 250, True)
    mat, fps = flow_calibration(real_names, rcg, st.entries, rsrc, real_prof, clean, st.argc, st.code, st.base)
    print(f"    (有紀錄參數的靜態判決 vs 實機:{dict(sorted(mat.items(), key=str))})")
    chk("校準:有紀錄的參數上靜態判決零誤報(呼叫端 / 被呼叫端)", fps, [])
    chk("校準:呼叫端可比 ≥ 250、被呼叫端可比 ≥ 100",
        (sum(v for (w, sv, lv), v in mat.items() if w == "up" and sv and lv) >= 250,
         sum(v for (w, sv, lv), v in mat.items() if w == "down" and sv and lv) >= 100), (True, True))
    old = {0x1E7F6: ("(unit, dst, stride, pos):", {1, 2}), 0x18795: ("(x, dst, 列, 目前值, 最大值) …", {1, 2}),
           0x279BC: ("(店種) …", {1}), 0x1E529: ("(stat_ptr, growth_pair_ptr, msg, line):", {3}),
           0x27079: ("(mode, positions):", {1}), 0x2B4FB: ("(bg, limit, flags, cursor):", {1}),
           0x17D6F: ("(x, y, 長度, 色格) …", {1}), 0x344B4: ("(res, idx, x, stride, base, y):", {3}),
           0x22D1B: ("(caster, count, targets, field_off, anim):", {3, 5})}
    cur = {int(x["addr"], 16): x for x in real_names}

    def flagged(x: dict) -> set[int]:
        return {k for k, _, _, up, down in flow_param_verdicts(x, rcg, st.entries, rsrc, real_prof, clean, st.argc,
                                                               st.code, st.base) if "viol" in (up[0], down[0])}

    chk("召回:歷史上實機抓到的 9 筆型別錯誤(含本輪 blit_res_cell_xy),舊摘要以靜態值流全部重現在對的參數",
        {a: flagged({"addr": f"{a:#x}", "summary": sm}) for a, (sm, _) in old.items()},
        {a: want for a, (_, want) in old.items()})
    chk("對照:同 9 個函式的目前摘要一個都不報", {a: flagged(cur[a]) for a in old}, {a: set() for a in old})
    rsc4 = Screen()
    wav = {**cur[0x41DEB], "summary": "(取樣, 檔案影像) RIFF WAVE"}
    screen_roles(rsc4, [wav], rcg, st.entries, st.argc, clean, st.code, st.base)
    chk("召回:wav_parse_chunks 舊摘要 (取樣, 檔案影像) -> 角色篩選 p2(來源經 AIL 包裝轉到實作後被寫入)",
        [(c.screen, c.key) for c in rsc4.cands], [("param_role", "p2")])
    zero = []
    zmemo: dict = {}
    for x in real_names:
        ps, nn = parse_sig(x.get("summary") or "")
        rl = {k: role_of(p) for k, p in enumerate(ps or [], 1)}
        if not nn or not any(rl.values()):
            continue
        a = int(x["addr"], 16)
        sl = n_slots(ps, nn)
        cv = role_convention(sl, clean.get(a, set()), st.argc.get(a))
        if cv is None or (cv == "reg" and sl != nn):
            continue
        u = role_uses(rcg, st.code, st.base, st.entries, a, sl, cv == "reg", zmemo, 0, set(st.entries))
        if u is not None:
            zero += [(x["name"], k) for k, r in rl.items() if r and not any((u.get(slot_starts(ps)[k - 1]) or {}).values())]
    chk("真實:角色篩選零存取的參數 0 個(續一百一十二留 11 個;逐一查出 5 種原因並補機制)", zero, [])
    run_sc2 = run(REVIEW_JSON)[0]
    chk("run() 有接上 param_flow(分母非零)", (run_sc2.denom.get("param_flow 可比(呼叫端)", 0) > 0,
                                          run_sc2.denom.get("param_flow 可比(被呼叫端)", 0) > 0), (True, True))
    chk("真實 param_role 可比 ≥ 105(續一百一十三沿控制流 + 五種機制;續一百一十二 97)",
        run_sc2.denom.get("param_role 可比", 0) >= 105, True)

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
