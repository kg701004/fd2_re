"""續一百八十證據:evidence/sfx_ui_pool_table_s180_20261101.json(續一百七十九仍留:doc36 UI 池 index 表其餘列沒有重核)。

使用者 2026-11-01「依照你的建議自動繼續進行處理」。沒有新實機:FD2.EXE 反組譯、函式登錄表,與續一百零七的 cl1 .. cl14 呼叫紀錄
(每個入口前 200 次)。
(S) 全 EXE 直接呼叫 play_sfx_a / play_sfx_b 的每一處(同續一百七十九的列舉:相對呼叫端 + 跳進「推音效池那條」的無條件 jmp),
    取推 [0x53eec](UI 音效池)的那些,依推的 index 分組:靜態呼叫端數(A / B,在走不到的防拷函式裡的另計)與所屬函式(登錄名)。
(L) cl1 .. cl14 以 UI 池實際播放的每一次:index 與返回位址;每個返回位址都必須是同 index 的某個靜態呼叫端 + 5。
(D) doc36「`[0x53eec]`(UI 音效池)index 語意」表的前四欄(index、靜態呼叫端、呼叫端函式、cl1 .. cl14 次數)與上面逐格相同,
    「`play_sfx_a` **N 處**、`play_sfx_b` **M 處**」那句的 N / M 與列舉相同 —— 表格之後再和程式碼不一致,本產生器就失敗。
另記兩項舊紀錄的錯誤:doc36 舊表 0xb 列的 0x2cac3 不是呼叫端(是 cmp);ui_sfx_index_semantics.json 撤回的「0x32307 放 index 10」
其實成立(0x32280 push 0xa 那支,cl 紀錄看得到)。
任何判準不符就 assert 失敗。
"""
from __future__ import annotations

import bisect
import collections
import hashlib
import json
import re

from _evpaths import EVIDENCE, GEN_DIR, ROOT, out_path, rel, require_inputs  # noqa: E402
require_inputs(__file__)
from _exeops import _CBASE, _CODE, _EXE, _MD, insn  # noqa: E402  (_exeops 已把 tools/ 加進 sys.path)
import calllog_segments as cs  # noqa: E402
import disasm_le as dl  # noqa: E402

OUT = out_path("sfx_ui_pool_table_s180_20261101.json")
MD5 = "33464c81e6a364fd0660141139aa8e6e"
DELTA = 0x19C000
S178 = json.loads((EVIDENCE / "dig_word_order_sfx_s178_20261101.json").read_text(encoding="utf-8"))
S179 = json.loads((EVIDENCE / "sfx_triggers_irq_s179_20261101.json").read_text(encoding="utf-8"))
CL = {nm: (ROOT / v["path"], v["md5"]) for nm, v in S178["calllogs"].items()}
NAMES = ROOT / "docs/data/function_names.json"
DOC36 = ROOT / "docs/knowledge-base/36-sfx-audio-data.md"
OLD_CALLERS = ROOT / "docs/data/sfx_index_callers.json"
OLD_SEMANTICS = ROOT / "docs/data/ui_sfx_index_semantics.json"
LOAD, PLAY_A, PLAY_B = 0x111BA, 0x25A96, 0x25B45
POOL_PUSH = "push dword ptr [0x3eec]"   # [0x53eec]:obj2 的位移 0x3eec 經 fixup 指到 0x53eec
RET_POOL_LOAD = 0x25C75                 # game_main 0x25c70 load_res(FDOTHER #31) 的返回位址(續一百七十九)
STEP_CALL = 0x32307                     # play_step_sfx 三支共用的 push 池 / call 尾端
OLD_0B = 0x2CAC3                        # doc36 舊表 0xb 列的位址

assert hashlib.md5(_EXE).hexdigest() == MD5
assert S179["exe_md5"] == MD5 and set(CL) == set(S179["cl_logs"]), sorted(CL)

_NM = {int(r["addr"], 16): r["name"] for r in json.loads(NAMES.read_text(encoding="utf-8"))["names"]}
_ENT = sorted(_NM)


def func_of(a: int) -> int:
    return _ENT[bisect.bisect_right(_ENT, a) - 1]


# ================= (S) 靜態列舉 =================
INSNS, _stops = dl.resync_sweep(_MD, _CODE, _CBASE)
_IX = {i.address: k for k, i in enumerate(INSNS)}
BRANCH: dict[int, list[tuple[int, str]]] = collections.defaultdict(list)   # 目標 → [(來源, 助記符)]
for _i in INSNS:
    if (_i.mnemonic == "call" or _i.mnemonic.startswith("j")) and re.fullmatch(r"0x[0-9a-f]+", _i.op_str):
        BRANCH[int(_i.op_str, 16)].append((_i.address, _i.mnemonic))

SITES = []
N_CALLS = {}
for tgt in (PLAY_A, PLAY_B):
    hits, _ = dl.find_rel_callers(_MD, _CODE, _CBASE, tgt)
    assert all(al for _a, _m, _o, al in hits) and all(m == "call" for _a, m, _o, _al in hits), hits
    N_CALLS[tgt] = len(hits)
    for a, _m, _o, _al in hits:
        k = _IX[a]
        buf, idx = INSNS[k - 1], INSNS[k - 2]
        assert buf.mnemonic == "push" and a not in BRANCH and idx.address not in BRANCH, hex(a)
        paths = [(None, idx)]
        for src, mn in BRANCH.get(buf.address, []):
            assert mn == "jmp", (hex(a), hex(src), mn)        # 只處理無條件跳入
            paths.append((src, INSNS[_IX[src] - 1]))
        for via, ins in paths:
            assert ins.mnemonic == "push", (hex(a), ins.mnemonic, ins.op_str)
            SITES.append({"call": a, "target": tgt, "buf": buf.op_str, "via": via, "idx_at": ins.address, "idx": ins.op_str})
assert N_CALLS[PLAY_A] + N_CALLS[PLAY_B] == S179["static"]["play_call_sites"], N_CALLS
POOL = [s for s in SITES if "push " + s["buf"] == POOL_PUSH]
assert all(re.fullmatch(r"0x[0-9a-f]+|\d+", s["idx"]) for s in POOL), [s["idx"] for s in POOL]
BY_IDX: dict[int, list[dict]] = collections.defaultdict(list)
for s in sorted(POOL, key=lambda s: (s["call"], s["idx_at"])):
    BY_IDX[int(s["idx"], 0)].append(s)

# 防拷問答函式走不到(續一百七十九已證:唯一呼叫點前一條是無條件 jmp、沒有分支或 fixup 指到它)
CP = int(S179["static"]["copy_protection_unreachable"]["entry"], 16)
assert _NM[CP] == "copy_protection_password_check"

# play_step_sfx 的共用尾端服務三個 index(0x32280 push 0xa / 0x322c7 push 9 經 jmp,0x322ff push 0xb 直落)
STEP = sorted((int(s["idx"], 0), s["idx_at"], s["via"]) for s in POOL if s["call"] == STEP_CALL)
assert [(i, a) for i, a, _v in STEP] == [(9, 0x322C7), (0xA, 0x32280), (0xB, 0x322FF)], STEP
assert all(_NM[func_of(a)] == "play_step_sfx" for _i, a, _v in STEP)
# doc36 舊表 0xb 列的 0x2cac3:那裡是 cmp,不是推 index 也不是呼叫
assert insn(OLD_0B) == "cmp dword ptr [ebx*4 + 0x40b0], 0" and OLD_0B in _IX and all(OLD_0B not in (s["call"], s["idx_at"]) for s in SITES), insn(OLD_0B)

# ================= (L) cl1 .. cl14 以 UI 池實際播放的每一次 =================
CL_N: collections.Counter = collections.Counter()
CL_BY_FUNC: dict[int, collections.Counter] = collections.defaultdict(collections.Counter)
for nm, (p, m5) in CL.items():
    assert hashlib.md5(p.read_bytes()).hexdigest() == m5, p
    lg = cs._read(str(p), calls=True)
    (ld,) = [c for c in lg.calls if c.eip == LOAD + DELTA and c.ret - DELTA == RET_POOL_LOAD]
    pool = lg.rets[ld.seq].eax
    assert hex(pool) == S179["cl_logs"][nm]["pool"], nm
    plays = [c for c in lg.calls if c.eip in (PLAY_A + DELTA, PLAY_B + DELTA) and c.stack[0] == pool]
    assert len(plays) == S179["cl_logs"][nm]["pool_plays"], (nm, len(plays))
    for c in plays:
        k, call = c.stack[1], c.ret - DELTA - 5
        tgt = c.eip - DELTA
        assert any(s["call"] == call and s["target"] == tgt for s in BY_IDX[k]), (nm, k, hex(call))
        CL_N[k] += 1
        CL_BY_FUNC[k][_NM[func_of(call)]] += 1
assert set(CL_N) <= set(BY_IDX), set(CL_N) - set(BY_IDX)
assert all(sum(CL_BY_FUNC[k].values()) == n for k, n in CL_N.items()), CL_BY_FUNC
# ui_sfx_index_semantics.json 撤回的 index 10 其實成立
N10 = CL_BY_FUNC[0xA]["play_step_sfx"]
assert N10 > 0 and N10 == CL_N[0xA], CL_BY_FUNC[0xA]


def idx_s(k: int) -> str:
    return str(k) if k < 10 else hex(k)


def static_s(v: list[dict]) -> str:
    a = sum(s["target"] == PLAY_A for s in v)
    b = sum(s["target"] == PLAY_B for s in v)
    dead = sum(func_of(s["call"]) == CP for s in v)
    return f"A {a} / B {b}" + (f"(防拷 {dead} 處走不到)" if dead else "")


def funcs_s(v: list[dict]) -> str:
    return "、".join(f"`{n}`" for n in dict.fromkeys(_NM[func_of(s["idx_at"])] for s in v))


ROWS = {idx_s(k): [static_s(v), funcs_s(v), str(CL_N[k])] for k, v in sorted(BY_IDX.items())}

# ================= (D) doc36 表格與那句總數 =================
_doc = DOC36.read_text(encoding="utf-8").splitlines()
_h = [n for n, ln in enumerate(_doc) if ln.startswith("### `[0x53eec]`")]
assert len(_h) == 1, _h
_tbl = []
for ln in _doc[_h[0] + 1:]:
    if ln.startswith("|"):
        _tbl.append([c.strip() for c in ln.strip().strip("|").split("|")])
    elif _tbl:
        break
_head, _sep, *_body = _tbl
assert _head[:4] == ["index", "靜態呼叫端", "呼叫端函式(登錄名)", "cl1 .. cl14 次數"], _head
DOC_ROWS = {r[0]: r[1:4] for r in _body}
_diff = {k: (DOC_ROWS.get(k), ROWS.get(k)) for k in sorted(set(DOC_ROWS) | set(ROWS)) if DOC_ROWS.get(k) != ROWS.get(k)}
assert not _diff, json.dumps(_diff, ensure_ascii=False, indent=1)
_tot = [m.groups() for ln in _doc for m in [re.search(r"`play_sfx_a` \*\*(\d+) 處\*\*、`play_sfx_b` \*\*(\d+) 處\*\*", ln)] if m]
assert _tot == [(str(N_CALLS[PLAY_A]), str(N_CALLS[PLAY_B]))], _tot

POOLS = collections.Counter(s["buf"] for s in SITES)
assert POOLS["dword ptr [0x3eec]"] == len(POOL)

# ================= (O) 兩份舊 docs/data 表:逐筆比對並要求標明已被本檔取代 =================
# sfx_index_callers.json(2026-09-04 從 call 往回貪婪解析 push)仍是 fd2_sfx_static_reachability 稽核的對象,不改內容;
# 差異逐筆歸類:舊表多出的呼叫點要嘛推的是別的表(不是 UI 池),要嘛根本不是 play_sfx 的呼叫;舊表少的就是貪婪解析沒解到的。
_OLD = json.loads(OLD_CALLERS.read_text(encoding="utf-8"))
_old = {int(k): {int(x, 16) for x in v} for k, v in _OLD["index_to_callers"].items()}
_new = {k: {s["call"] for s in v} for k, v in BY_IDX.items()}
_by_call = collections.defaultdict(set)
for s in SITES:
    _by_call[s["call"]].add(s["buf"])
OLD_DIFF = {}
for k in sorted(set(_old) | set(_new)):
    extra, miss = _old.get(k, set()) - _new.get(k, set()), _new.get(k, set()) - _old.get(k, set())
    if not (extra or miss):
        continue
    why = {}
    for a in sorted(extra):
        bufs = _by_call.get(a, set())
        # 舊表多出的每一筆都是 play_sfx 的呼叫、推的是別的表(貪婪解析把別的表的 index 當成 UI 池)
        assert bufs and POOL_PUSH[len("push "):] not in bufs, (k, hex(a), bufs)
        why[hex(a)] = "、".join(sorted(bufs))
    OLD_DIFF[idx_s(k)] = {"only_old": why, "only_new": [hex(a) for a in sorted(miss)]}
assert OLD_DIFF and all(set(v["only_new"]).isdisjoint(v["only_old"]) for v in OLD_DIFF.values()), OLD_DIFF
# 由舊表套用差異必須恰好還原新表(差異沒有漏記或多記)
for k in set(_old) | set(_new):
    _d = OLD_DIFF.get(idx_s(k), {"only_old": {}, "only_new": []})
    assert (_old.get(k, set()) - {int(a, 16) for a in _d["only_old"]}) | {int(a, 16) for a in _d["only_new"]} == _new.get(k, set()), k
for _p in (OLD_CALLERS, OLD_SEMANTICS):
    _j = json.loads(_p.read_text(encoding="utf-8"))
    _sup = _j.get("_meta", _j).get("_superseded_by")
    assert _sup == rel(EVIDENCE / OUT.name), (_p.name, _sup)
OUT.write_text(json.dumps({
    "generator": rel(GEN_DIR / "ev_s180.py"), "exe_md5": MD5,
    "upstream": {"calllogs": rel(EVIDENCE / "dig_word_order_sfx_s178_20261101.json"),
                 "copy_protection": rel(EVIDENCE / "sfx_triggers_irq_s179_20261101.json"), "names": rel(NAMES), "doc": rel(DOC36)},
    "static": {"play_sfx_a_calls": N_CALLS[PLAY_A], "play_sfx_b_calls": N_CALLS[PLAY_B], "paths": len(SITES),
               "pool_paths_by_table": dict(POOLS.most_common()), "ui_pool_paths": len(POOL),
               "play_step_sfx_tail": [[idx_s(i), hex(a), v and hex(v)] for i, a, v in STEP],
               "old_doc36_0xb_site": {"addr": hex(OLD_0B), "insn": insn(OLD_0B)}},
    "ui_pool": {idx_s(k): {"sites": [{"call": hex(s["call"]), "handle": "A" if s["target"] == PLAY_A else "B", "idx_at": hex(s["idx_at"]),
                                      "via": s["via"] and hex(s["via"]), "func": _NM[func_of(s["idx_at"])],
                                      "unreachable": func_of(s["call"]) == CP} for s in v],
                           "cl_plays": CL_N[k], "cl_plays_by_func": dict(CL_BY_FUNC[k].most_common())}
                for k, v in sorted(BY_IDX.items())},
    "doc36_rows": ROWS,
    "old_callers_table_diff": {"file": rel(OLD_CALLERS), "by_index": OLD_DIFF},
    "conclusion": f"UI 池 [0x53eec] 共 {len(POOL)} 條推 index 的路徑、{len(BY_IDX)} 個 index;doc36 表前四欄與此逐格相同。"
                  f"0xb 只由 play_step_sfx 的 0x322ff 推(舊表 0x2cac3 是 cmp);0x32307 共用尾端放 9 / 0xa / 0xb,"
                  f"cl1 .. cl14 實際看到 index 10 {N10} 次。",
}, ensure_ascii=False, indent=1) + "\n", encoding="utf-8", newline="\n")
print(OUT)
