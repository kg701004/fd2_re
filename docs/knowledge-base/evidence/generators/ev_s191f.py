"""續一百九十一證據:evidence/forest_beats_s191_20261104.json(91-worklist「handler 後半段 beats 解碼」—— ch1-forest.md 密林段)。

使用者 2026-11-04「open_static 7 項、open_live 2 項 請完整進行驗證及處理」。沒有新實機:續一百八十四的 lc184a(原版 FD2.EXE、
DOSBox-X,新遊戲開場逐鍵推進,含第 31 張圖森林段)呼叫紀錄,與 repo 的 tools/export_acting_resources.py(acting 0x5a..0x62)。
scene-decode/ch1-forest.md 依 doc50 規則推算的走位從未對原版執行期資料核對。本產生器(模型與紀錄抽取沿用子代理 s191_F 的
forest_core,判準重寫):
(1) 第 31 張圖段 handler(0x3253d .. 0x32822)發出的 26 個可觀察呼叫 == ch1-forest.md §1。
(2) 每個 acting 的 play_step_sfx 次數 = 6 × normal beats、參數 = 該 frame 第一個 slot(返回 0x13923)。
(3) 視窗內所有 m= 傾印恰從某單位記錄 +0 起者,(X, Y, +3, +4) 都落在 doc50 規則逐格模擬的可接受狀態裡,不一致 0。
(4) 對照(都必須出現不一致):索爾起點 X+1、蓋亞起點 Y+1、frame 內 slot0↔slot1、左右語意互換。
(5) ch1-forest.md §2 字面:唯一與模型不同的是 0x62 亞雷斯起點(文件 (9,44),模型與 0x61→0x62 之間的傾印都是 (8,45))。
任何判準不符就 assert 失敗。
"""
from __future__ import annotations

import collections
import copy
import hashlib
import json
from pathlib import Path
from typing import Any

from _evpaths import EVIDENCE, GAME, GEN_DIR, ROOT, out_path, rel, require_inputs  # noqa: E402
require_inputs(__file__)
from _exeops import _EXE, _META, insn  # noqa: E402,F401  (_exeops 已把 tools/ 加進 sys.path)
import calllog_segments as cs  # noqa: E402
import disasm_le as dl  # noqa: E402
import export_acting_resources as ear  # noqa: E402

OUT = out_path("forest_beats_s191_20261104.json")
EXE_MD5 = "33464c81e6a364fd0660141139aa8e6e"
DELTA = 0x19C000
STRIDE = 0x50
GLOBALS_LIN, PTR_UNITS, CNT_UNITS = 0x53A40, 0x53A45, 0x53BEB
RAW = ROOT / ".wsl_build/lc184_live"
S184 = json.loads((EVIDENCE / "live_checks_s184_20261102.json").read_text(encoding="utf-8"))
F_LOAD, F_SPAWN, F_PAN, F_ACT, F_TXT, F_HIDE, F_STEP, F_RES = 0x205DA, 0x10B4E, 0x135DD, 0x1366A, 0x15F84, 0x32975, 0x32230, 0x4EB48
STEP_RET_IN_ACT = 0x13923            # 0x1391e call 0x32230 的下一條
HANDLER_LO, HANDLER_HI = 0x3253D, 0x32822   # 第 31 張圖段:0x205da 回來(0x3253d)到下一次 call 0x205da(0x3281d)
RES_TABLE = 0x627D8                  # 0x4eb51: mov eax, dword ptr [eax + 0x27d8](fixup → 0x627d8)
DIRS = {0: (0, 1), 1: (-1, 0), 2: (0, -1), 3: (1, 0)}   # doc54:0 下 Y++、1 左 X--、2 上 Y--、3 右 X++

# ---------------- ch1-forest.md 的預測(逐字轉成資料) ----------------
# §3 roster:slot → (portrait, X, Y, spawn group)
DOC_ROSTER = {0: (0, 19, 46, 1), 1: (4, 19, 47, 1), 2: (75, 5, 44, 3), 3: (30, 5, 43, 3), 4: (9, 5, 44, 5)}
# §1 beat 表(只列可在紀錄觀察的呼叫;9b 的 bgm 停 / [0x53afb]=1 另以 O2 的 0x11d40 旁證)
DOC_BEATS = [("load", None), ("pan", (5, 0x2A)), ("spawn", 1), ("act", 0x5A), ("txt", 0), ("act", 0x5B), ("txt", 1),
             ("act", 0x5C), ("txt", 2), ("spawn", 3), ("pan", (4, 0x29)), ("txt", 3), ("act", 0x5D), ("txt", 4),
             ("hide", 2), ("spawn", 5), ("txt", 5), ("act", 0x5E), ("txt", 6), ("act", 0x5F), ("txt", 7),
             ("act", 0x60), ("txt", 8), ("act", 0x61), ("txt", 9), ("act", 0x62)]
# §2 表「推算走位/姿態結果」欄的字面:slot → (起點, 終點, 終了朝向或 None);None 起點 = 文字沒寫
DOC_ACT: dict[int, dict[int, tuple[tuple[int, int] | None, tuple[int, int], int | None]]] = {
    0x5A: {0: ((19, 46), (13, 46), 3), 1: ((19, 47), (15, 46), 1)},          # 末段 s:slot0 面右 / slot1 面左
    0x5B: {0: ((13, 46), (14, 47), 3), 1: ((15, 46), (15, 46), 1)},          # s:slot0 面右;s:slot1 面左(0 拍)
    0x5C: {0: ((14, 47), (13, 47), None)},
    0x5D: {0: ((13, 47), (8, 44), None), 1: ((15, 46), (9, 44), None), 3: ((5, 43), (7, 44), 3)},
    0x5E: {0: ((8, 44), (7, 44), None), 3: ((7, 44), (7, 43), 0), 4: (None, (5, 44), 3)},
    0x5F: {0: ((7, 44), (8, 44), 1), 3: ((7, 43), (7, 44), 1)},
    0x60: {3: ((7, 44), (7, 44), 2)},                                         # 面右→下→上,原地
    0x61: {1: ((9, 44), (8, 45), 2), 0: ((8, 44), (8, 44), 0)},
    0x62: {0: ((8, 44), (15, 46), None), 1: ((9, 44), (14, 46), None), 3: ((7, 44), (13, 46), None),
           4: ((5, 44), (12, 46), None)},
}
ACT_IDS = list(range(0x5A, 0x63))


def md5(p: Path) -> str:
    """檔案 md5。"""
    return hashlib.md5(p.read_bytes()).hexdigest()


def frames_from_exporter() -> dict[int, list[dict[str, Any]]]:
    """repo 的 tools/export_acting_resources.py 解出的 0x5a..0x62(與 ch1-forest.md §2 同一工具)。"""
    res = ear.export_resources(GAME / "FD2.EXE")
    return {i: res[str(i)] for i in ACT_IDS}


# ---------------- 模擬(doc50 規則 + 0x1366a 的呼叫時序) ----------------
State = dict[int, list[int]]          # slot → [X, Y, +3, +4]


def sim_acting(state: State, frames: list[dict[str, Any]]) -> dict[str, Any]:
    """一個 acting 的逐次 play_step_sfx 預測。

    回傳 entry[i](第 i 次 step 呼叫入口時的狀態)、between[i](第 i 次與第 i+1 次之間可接受的狀態集;
    between[-1] = 進 acting 到第一次 step 之間;between[len] 不存在,最後一段算在 between[last])、
    args[i](push 的 slot)與 final。時序依 0x1366a:normal frame 每格 sub=1..6 先 call 0x32230 再寫 +3/+4=sub,
    第 7 次不再 call,直接搬格並寫 +4=0;跨 frame 時搬格到下一次 call 之間沒有任何 call。
    """
    st = copy.deepcopy(state)
    entry: list[State] = []
    args: list[int] = []
    between: dict[int, list[State]] = {}
    cur: list[State] = [copy.deepcopy(st)]
    i = 0
    for fi, fr in enumerate(frames):
        units = [(u["slot"], u["pose"]) for u in fr["units"]]
        if fr.get("special"):
            for s, p in units:
                st[s][2] = p
            cur.append(copy.deepcopy(st))
            continue
        nxt_normal = fi + 1 < len(frames) and not frames[fi + 1].get("special")
        for b in range(fr["beats"]):
            for j in range(1, 7):
                between[i - 1] = cur
                entry.append(copy.deepcopy(st))
                args.append(units[0][0])
                for s, p in units:
                    st[s][2], st[s][3] = p, j
                cur = [copy.deepcopy(st)]
                i += 1
            for s, p in units:
                dx, dy = DIRS[p]
                st[s][0] += dx
                st[s][1] += dy
                st[s][3] = 0
            if b == fr["beats"] - 1 and not nxt_normal:
                cur.append(copy.deepcopy(st))
    between[i - 1] = cur
    return {"entry": entry, "between": between, "args": args, "final": st}


def run_model(frames: dict[int, list[dict[str, Any]]], roster: dict[int, tuple[int, int, int, int]],
              override_start: dict[int, State] | None = None) -> dict[int, dict[str, Any]]:
    """依 handler 次序(spawn → acting)串接;override_start[id] 可把某 acting 的起始狀態換成文件字面(對照用)。"""
    state: State = {}
    out: dict[int, dict[str, Any]] = {}
    spawned_before = {0x5A: (1,), 0x5D: (3,), 0x5E: (5,)}
    for aid in ACT_IDS:
        for g in spawned_before.get(aid, ()):
            for s, (_por, x, y, grp) in roster.items():
                if grp == g:
                    state[s] = [x, y, 0, 0]          # 0x10ec5..0x10eed:spawn 寫 +3=0、+4=0(doc54 §1)
        st = copy.deepcopy(state)
        if override_start and aid in override_start:
            for s, v in override_start[aid].items():
                st[s] = list(v)
        r = sim_acting(st, frames[aid])
        r["start"] = st
        out[aid] = r
        state = copy.deepcopy(r["final"])
    return out


# ---------------- 紀錄 ----------------
def load_log() -> dict[str, Any]:
    """讀 lc184a(md5 先驗),抽出第 31 張圖視窗。"""
    run = S184["runs"]["lc184a"]
    p = ROOT / run["calllog"]
    assert md5(p) == run["md5"] == "dcbf7cf1a6f579616cb5a709493019f6", "calllog md5"
    lg = cs._read(str(p), calls=True)
    loads = [c for c in lg.calls if c.eip - DELTA == F_LOAD]
    ins = [c for c in loads if c.ret - DELTA == HANDLER_LO]             # 載入第 31 張圖那次
    outs = [c for c in loads if c.ret - DELTA == 0x32822]               # 第 31 張圖段結束
    assert len(ins) == 1 and len(outs) == 1, (len(ins), len(outs))
    c_in, c_out = ins[0], outs[0]
    s0, s1 = c_in.seq, c_out.seq
    win = [c for c in lg.calls if s0 <= c.seq <= s1]
    return {"lg": lg, "win": win, "s0": s0, "s1": s1, "path": run["calllog"], "md5": run["md5"]}


def n_of(c: Any) -> int:
    """E 紀錄的指令計數 n。"""
    assert c.ic is not None
    return c.ic[1]


def handler_seq(L: dict[str, Any]) -> list[tuple[str, Any, int]]:
    """O1:handler(返回位址在第 31 張圖段)發出的呼叫。"""
    kind = {F_LOAD: "load", F_PAN: "pan", F_SPAWN: "spawn", F_ACT: "act", F_TXT: "txt", F_HIDE: "hide"}
    out = []
    for c in L["win"]:
        e = c.eip - DELTA
        if e in kind and (HANDLER_LO <= c.ret - DELTA <= 0x32822 or c.seq == L["s0"]):
            k = kind[e]
            a = {"load": None, "pan": (c.stack[0], c.stack[1]), "spawn": c.stack[0], "act": c.stack[0],
                 "txt": c.stack[1], "hide": c.stack[0]}[k]
            out.append((k, a, c.seq))
    return out[:-1] if out and out[-1][0] == "load" and out[-1][2] == L["s1"] else out


def acting_calls(L: dict[str, Any]) -> dict[int, dict[str, Any]]:
    """每個 acting:入口 / 返回的 n、其中的 step 呼叫(seq、n、參數、ebx 與 ebx 傾印)。"""
    lg = L["lg"]
    acts = {}
    for c in L["win"]:
        if c.eip - DELTA == F_ACT and HANDLER_LO <= c.ret - DELTA <= 0x32822:
            r = lg.rets[c.seq]
            assert r.kind == "R" and r.ic is not None
            acts[c.stack[0]] = {"seq": c.seq, "n0": n_of(c), "n1": r.ic[1], "steps": []}
    for c in L["win"]:
        if c.eip - DELTA == F_STEP:
            hit = [a for a, v in acts.items() if v["n0"] < n_of(c) < v["n1"]]
            assert len(hit) == 1, (c.seq, hit)
            aid = hit[0]
            assert c.ret - DELTA == STEP_RET_IN_ACT, c.seq
            acts[aid]["steps"].append(c)
            r = lg.rets[c.seq]
            assert r.kind == "R" and r.ic is not None, c.seq
            acts[aid].setdefault("step_ret_n", []).append(r.ic[1])
    for v in acts.values():
        v.setdefault("step_ret_n", [])
    return acts


def unit_dumps(L: dict[str, Any], base: int, nslots: int = 5) -> list[dict[str, Any]]:
    """O3:視窗內 m= 傾印從某單位記錄 +0 起、且至少讀到 5 個位元組者(同一 E 紀錄同 slot 去重)。"""
    out = []
    for c in L["win"]:
        seen = set()
        for nm in cs.PTR_ORDER:
            p = c.ptr(nm)
            if base <= p < base + nslots * STRIDE and (p - base) % STRIDE == 0:
                s = (p - base) // STRIDE
                b = c.mem_prefix[nm]
                if s in seen or len(b) < 5:
                    continue
                seen.add(s)
                out.append({"seq": c.seq, "n": n_of(c), "func": c.eip - DELTA, "reg": nm, "slot": s,
                            "obs": [b[0], b[1], b[3], b[4]], "plus5": b[5] if len(b) > 5 else None})
    return out


def spawn_rets(L: dict[str, Any]) -> dict[int, tuple[int, int]]:
    """handler 的 0x10b4e(group):group → (入口 n, 返回 n)。"""
    out = {}
    for c in L["win"]:
        if c.eip - DELTA == F_SPAWN and HANDLER_LO <= c.ret - DELTA <= 0x32822:
            out[c.stack[0]] = (n_of(c), L["lg"].rets[c.seq].ic[1])
    return out


def admissible(dump: dict[str, Any], model: dict[int, dict[str, Any]], acts: dict[int, dict[str, Any]],
               spawns: dict[int, tuple[int, int]], roster: dict[int, tuple[int, int, int, int]]) -> tuple[str, list[list[int]]]:
    """某次傾印時刻,該 slot 的可接受狀態集。回傳 (情境, 狀態列);情境 'unspawned' 時不比對。"""
    s, n = dump["slot"], dump["n"]
    grp = roster[s][3]
    sp0, sp1 = spawns[grp]
    if n <= sp1:
        return ("unspawned" if n < sp0 else "spawning"), []
    for aid in ACT_IDS:
        a = acts[aid]
        m = model[aid]
        if a["n0"] < n < a["n1"]:
            ns = [n_of(c) for c in a["steps"]]
            # play_step_sfx 本身與它裡面巢狀的呼叫(play_sfx_a 等):狀態 = 該次 step 入口(寫 +3/+4 在它返回之後)
            for i, c in enumerate(a["steps"]):
                if n_of(c) <= n <= a["step_ret_n"][i]:
                    st = m["entry"][i]
                    return f"act{aid:#x}:in_step{i}", ([st[s]] if s in st else [])
            i = sum(x < n for x in ns)
            sts = m["between"][i - 1]
            return f"act{aid:#x}:after{i}", [x[s] for x in sts if s in x]
        if n == a["n0"]:
            return f"act{aid:#x}:entry", ([m["start"][s]] if s in m["start"] else [])
    prev = [aid for aid in ACT_IDS if acts[aid]["n1"] <= n]
    if not prev:
        _por, x, y, _g = roster[s]
        return "rest:before5a", [[x, y, 0, 0]]
    st = model[prev[-1]]["final"]
    if s not in st:                                   # 已出場但還沒進過任何 acting(例:group 5 出場後、0x5e 之前)
        _por, x, y, _g = roster[s]
        return f"rest:after{prev[-1]:#x}", [[x, y, 0, 0]]
    return f"rest:after{prev[-1]:#x}", [st[s]]


def compare_dumps(dumps: list[dict[str, Any]], model: dict[int, dict[str, Any]], acts: dict[int, dict[str, Any]],
                  spawns: dict[int, tuple[int, int]], roster: dict[int, tuple[int, int, int, int]]) -> list[dict[str, Any]]:
    """逐筆傾印判一致 / 不一致 / 不比對。"""
    rows = []
    for d in dumps:
        ctx, adm = admissible(d, model, acts, spawns, roster)
        if ctx in ("unspawned", "spawning"):
            verdict = "skip_" + ctx
        elif not adm:
            verdict = "no_prediction"
        else:
            verdict = "match" if d["obs"] in adm else "MISMATCH"
        rows.append({**d, "ctx": ctx, "admissible": adm, "verdict": verdict})
    return rows


def resource_link(L: dict[str, Any], frames: dict[int, list[dict[str, Any]]]) -> dict[str, Any]:
    """O5:執行期 0x4eb48(id) 的回傳 − 靜態 0x627d8[id] 的 fixup 目標 為常數;靜態該處位元組 parse 後 == exporter。"""
    fx = dl.build_fixups(_EXE, _META)
    rows = {}
    for c in L["win"]:
        if c.eip - DELTA == F_RES and c.stack[0] in frames:
            rt = L["lg"].rets[c.seq].eax
            st = fx[RES_TABLE + 4 * c.stack[0]]
            raw = bytes(dl.object_bytes(_EXE, _META, st, 128))
            parsed = ear.parse_resource(raw, 0, c.stack[0])
            rows[c.stack[0]] = {"runtime": rt, "static": st, "delta": rt - st, "parse_equals_exporter": parsed == frames[c.stack[0]]}
    return rows


# ================= 判準 =================
def swap_slots(frames: dict[int, list[dict[str, Any]]], a: int, b: int) -> dict[int, list[dict[str, Any]]]:
    """對照:frame 內 slot a / b 互換(= slot 對照表錯)。"""
    out = copy.deepcopy(frames)
    for fl in out.values():
        for f in fl:
            for u in f["units"]:
                u["slot"] = {a: b, b: a}.get(u["slot"], u["slot"])
    return out


def mirror_lr(frames: dict[int, list[dict[str, Any]]]) -> dict[int, list[dict[str, Any]]]:
    """對照:pose 1(左)與 3(右)互換(= 左右語意弄反)。"""
    out = copy.deepcopy(frames)
    for fl in out.values():
        for f in fl:
            for u in f["units"]:
                u["pose"] = {1: 3, 3: 1}.get(u["pose"], u["pose"])
    return out


def mismatches(frames: dict[int, list[dict[str, Any]]], roster: dict[int, tuple[int, int, int, int]]) -> int:
    """以 frames / roster 重跑模型,傾印不一致的筆數。"""
    rows = compare_dumps(DUMPS, run_model(frames, roster), ACTS, SPAWNS, roster)
    return sum(r["verdict"] == "MISMATCH" for r in rows)


assert hashlib.md5(_EXE).hexdigest() == EXE_MD5
FRAMES = frames_from_exporter()
L = load_log()
BASE = int(S184["live_tables"]["lc184a/map31"]["unit_base"], 16)
# (1) handler 呼叫序列
HSEQ = handler_seq(L)
assert [(k, a) for k, a, _s in HSEQ] == DOC_BEATS, [(k, a) for k, a, _s in HSEQ]
# (2) play_step_sfx 次數與參數
ACTS = acting_calls(L)
SPAWNS = spawn_rets(L)
MODEL = run_model(FRAMES, DOC_ROSTER)
STEP_COUNTS = {hex(a): len(ACTS[a]["steps"]) for a in ACT_IDS}
NORMAL_BEATS = {hex(a): sum(f["beats"] for f in FRAMES[a] if not f.get("special")) for a in ACT_IDS}
assert all(STEP_COUNTS[k] == 6 * NORMAL_BEATS[k] for k in STEP_COUNTS), (STEP_COUNTS, NORMAL_BEATS)
assert list(STEP_COUNTS.values()) == [36, 12, 6, 48, 6, 6, 0, 12, 54], STEP_COUNTS
for a in ACT_IDS:
    assert [c.stack[0] for c in ACTS[a]["steps"]] == MODEL[a]["args"], hex(a)
# (3) 傾印比對
DUMPS = unit_dumps(L, BASE)
ROWS = compare_dumps(DUMPS, MODEL, ACTS, SPAWNS, DOC_ROSTER)
VERDICTS = collections.Counter(r["verdict"] for r in ROWS)
assert VERDICTS["MISMATCH"] == 0 and VERDICTS["match"] > 6000, VERDICTS
BY_SLOT = collections.Counter(r["slot"] for r in ROWS if r["verdict"] == "match")
assert all(BY_SLOT[s] > 0 for s in (0, 1, 3, 4)), BY_SLOT
# (4) 對照
_r = copy.deepcopy(DOC_ROSTER)
_r[0] = (_r[0][0], _r[0][1] + 1, _r[0][2], _r[0][3])
_g = copy.deepcopy(DOC_ROSTER)
_g[3] = (_g[3][0], _g[3][1], _g[3][2] + 1, _g[3][3])
NULLS = {"sol_start_x_plus1": mismatches(FRAMES, _r), "gaia_start_y_plus1": mismatches(FRAMES, _g),
         "slot0_slot1_swapped": mismatches(swap_slots(FRAMES, 0, 1), DOC_ROSTER),
         "left_right_mirrored": mismatches(mirror_lr(FRAMES), DOC_ROSTER)}
assert all(v > 0 for v in NULLS.values()), NULLS
# (5) 文件字面 vs 模型:起點(有寫的)與終點
DIFFS = []
for aid, slots in DOC_ACT.items():
    for s, (start, end, _face) in slots.items():
        m0, m1 = MODEL[aid]["start"].get(s), MODEL[aid]["final"].get(s)
        if start is not None and m0 is not None and tuple(m0[:2]) != start:
            DIFFS.append({"act": hex(aid), "slot": s, "field": "start", "doc": list(start), "model": m0[:2]})
        if m1 is not None and tuple(m1[:2]) != end:
            DIFFS.append({"act": hex(aid), "slot": s, "field": "end", "doc": list(end), "model": m1[:2]})
assert DIFFS == [{"act": "0x62", "slot": 1, "field": "start", "doc": [9, 44], "model": [8, 45]}], DIFFS
# 0x61 結束到 0x62 開始之間 slot 1 的傾印全是 (8,45)
GAP = [r["obs"][:2] for r in ROWS if r["slot"] == 1 and ACTS[0x61]["n1"] <= r["n"] <= ACTS[0x62]["n0"]]
assert GAP and all(p == [8, 45] for p in GAP), GAP[:4]
RES = resource_link(L, FRAMES)
assert len({v["delta"] for v in RES.values()}) == 1 and all(v["parse_equals_exporter"] for v in RES.values()), RES

OUT.write_text(json.dumps({
    "generator": rel(GEN_DIR / "ev_s191f.py"), "exe_md5": EXE_MD5, "calllog": L["path"], "calllog_md5": L["md5"],
    "window_seq": [L["s0"], L["s1"]], "handler_calls": len(HSEQ), "step_counts": STEP_COUNTS, "normal_beats": NORMAL_BEATS,
    "dump_verdicts": dict(VERDICTS), "matches_by_slot": {str(k): v for k, v in sorted(BY_SLOT.items())},
    "nulls_mismatches": NULLS, "doc_vs_model": DIFFS, "slot1_dumps_between_0x61_0x62": len(GAP),
    "resource_delta": hex(next(iter(RES.values()))["delta"]),
    "conclusion": "ch1-forest.md 的 §1 呼叫序列、doc50 走位規則與 slot 對照都與 lc184a 一致(傾印 0 不一致,四個對照都不一致);"
                  "§2 唯一的字面錯是 0x62 亞雷斯起點,應為 (8,45)(文件寫 (9,44))。",
}, ensure_ascii=False, indent=1) + "\n", encoding="utf-8", newline="\n")
print(OUT, STEP_COUNTS, dict(VERDICTS), NULLS, DIFFS)
