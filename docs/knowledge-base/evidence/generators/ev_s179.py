"""續一百七十九證據:evidence/sfx_triggers_irq_s179_20261101.json(續一百七十八仍留:31253 / 36793 型是哪個畫面事件、
6235 那段是哪一張表放的;續一百七十五 lc163a / lc167a 沒有 I 紀錄的兩項推論)。

使用者 2026-11-01「依照你的建議自動繼續進行處理」。沒有新實機:用 FD2.EXE 反組譯、FDOTHER.DAT,與既有的 DOSBox-X 呼叫紀錄 ——
續一百零七的 cl1 .. cl14(dump=32,每個入口前 200 次附指標處 32 位元組)、lc174a / lc174b / lc173a / lc163a / lc167a,
以及續一百六十七 lc167a 的截圖時刻與驅動腳本。
(T) 標題三段:title_seq 0x1f8de 載入 FDOTHER #77(存 [esp+0x54]),0x1fd24 以 play_digital_sample 放它的第 3 段,0x1fedb 放第 1 段(確認);
    0x1fd14 呼叫 ani_player,0x2044f 載入 #78、0x2054d 放其中一段。cl1 .. cl14 每份都是 load_res("FDOTHER.DAT", 0, 77) 之後
    play_digital_sample(指標, 3, 1),指標處 32 位元組 = #77 開頭(#49 / #53 開頭不同)→ 6235 那段由 #77 放。
    lc174a / lc174b / lc173a 的混音序列:#78 第 0 段 → #77 第 3 段 → #77 第 1 段;0x1fed3 之後第一次混音就是 #77 第 1 段。
(I) UI 音效池 [0x53eec] = game_main 0x25c70 載入的 FDOTHER #31。全 EXE 直接呼叫兩個播放函式的 122 處,以 [0x53eec] 放 index 9 的
    只有 play_step_sfx(0x322c7 push 9 → jmp 0x32301),放 index 2 的是 typewriter_tick 0x16546 與防拷問答 0x34126 / 0x34162
    (防拷函式唯一的呼叫點 0x118ac 前面是無條件 jmp,走不到)。cl1 .. cl14 實際呼叫:index 2 全部來自 0x1654b、index 9 全部來自 0x3230c。
(R) 中斷號:lc163a 那一次 ng 375 之後 0.1 ms 內的 DIG 服務是填緩衝(IRQ 7 的特徵,與 lc174a 直接看到 IRQ 7 的那次同型);
    302 / 303 型(重入沒有夾中斷)接著填緩衝的比例是對照。lc167a 532 那次落在 findempty 截圖之後、送 Up 鍵的窗內;
    558 那 3 次在最後一次送鍵(YES)之後 22 秒以上。
任何判準不符就 assert 失敗。
"""
from __future__ import annotations

import bisect
import collections
import hashlib
import itertools
import json
import re

from _evpaths import EVIDENCE, GAME, ROOT, out_path, rel, require_inputs  # noqa: E402
require_inputs(__file__)
from _exeops import _CBASE, _CODE, _EXE, _MD, insn, operand  # noqa: E402  (_exeops 已把 tools/ 加進 sys.path)
import calllog_segments as cs  # noqa: E402
import disasm_le as dl  # noqa: E402
import unpack_dat as ud  # noqa: E402

OUT = out_path("sfx_triggers_irq_s179_20261101.json")
MD5 = "33464c81e6a364fd0660141139aa8e6e"
DELTA = 0x19C000
S175 = json.loads((EVIDENCE / "audio_followups_s175_20261031.json").read_text(encoding="utf-8"))
S174 = json.loads((EVIDENCE / "trig_capture_s174_20261031.json").read_text(encoding="utf-8"))
S176 = json.loads((EVIDENCE / "dig_fill_lengths_s176_20261031.json").read_text(encoding="utf-8"))
S178 = json.loads((EVIDENCE / "dig_word_order_sfx_s178_20261101.json").read_text(encoding="utf-8"))
CL = {nm: (ROOT / v["path"], v["md5"]) for nm, v in S178["calllogs"].items()}
LC = {"lc174a": (ROOT / ".wsl_build/lc174_live/lc174a_CALLLOG.TXT", "0aaee51798ec85a779a95aa78ed85cac"),
      "lc174b": (ROOT / ".wsl_build/lc174_live/lc174b_CALLLOG.TXT", "9be49f776cc0ed2fbbc3d7e962503b14"),
      "lc173a": (ROOT / ".wsl_build/lc173_live/lc173a_CALLLOG.TXT", "3a8bb8b852d99b3f6307a64306408efb"),
      "lc163a": (ROOT / ".wsl_build/lc163_live/lc163a_CALLLOG.TXT", "3bebd4f463c821dfc137cd267c5c6112")}
LIVE167 = ROOT / ".wsl_build/lc167_live"
SWEEP = ROOT / "tools/fd2_chapter_sweep.py"
DRV167 = ROOT / "docs/knowledge-base/evidence/generators/drivers_s167"
NAMES = ROOT / "docs/data/function_names.json"
LOAD, PLAY_A, PLAY_B = 0x111BA, 0x25A96, 0x25B45
POOL_PUSH = "push dword ptr [0x3eec]"   # [0x53eec]:obj2 的位移 0x3eec 經 fixup 指到 0x53eec

assert hashlib.md5(_EXE).hexdigest() == MD5
assert len(CL) == 12, CL


def rt(a: int) -> int:
    return a + DELTA


def read_log(path, md5: str) -> cs.Log:
    assert hashlib.md5(path.read_bytes()).hexdigest() == md5, path
    return cs._read(str(path), calls=True)


FDO = (GAME / "FDOTHER.DAT").read_bytes()
TOP = ud.parse_directory(FDO)


def res(i: int) -> bytes:
    o, n = TOP[i]
    return FDO[o:o + n]


def seg(i: int, j: int) -> bytes:
    b = res(i)
    o, n = ud.parse_directory(b)[j]
    return b[o:o + n]


# ================= 靜態:title_seq / ani_player / UI 音效池 =================
STATIC = {0x1F8DE: f"call {LOAD:#x}", 0x1F8E6: "mov dword ptr [esp + 0x54], eax",
          0x1FD14: "call 0x20421", 0x1FD1C: "push 1", 0x1FD20: "push dword ptr [esp + 0x5c]", 0x1FD24: f"call {PLAY_B:#x}",
          0x1FED3: "push 1", 0x1FED7: "push dword ptr [esp + 0x5c]", 0x1FEDB: f"call {PLAY_A:#x}",
          0x2044F: f"call {LOAD:#x}", 0x20457: "mov dword ptr [esp + 0xc], eax",
          0x20546: "push 1", 0x20548: "push esi", 0x20549: "push dword ptr [esp + 0x14]", 0x2054D: f"call {PLAY_A:#x}",
          0x25C65: POOL_PUSH, 0x25C70: f"call {LOAD:#x}", 0x25C78: "mov dword ptr [0x3eec], eax",
          0x1653C: "push 1", 0x16540: POOL_PUSH, 0x16546: f"call {PLAY_A:#x}",
          0x322C5: "push 1", 0x322C9: "jmp 0x32301", 0x32301: POOL_PUSH, 0x32307: f"call {PLAY_A:#x}"}
for _a, _t in STATIC.items():
    assert insn(_a) == _t, (hex(_a), insn(_a), _t)
RES_TITLE = operand(0x1F8D6, "push ")          # 0x1f8d6 push 0x4d → #77
IDX_TITLE = operand(0x1FD1E, "push ")          # 第 3 段
IDX_CONFIRM = operand(0x1FED5, "push ")        # 第 1 段(續一百六十一的確認音效)
RES_ANI = operand(0x20446, "push ")            # 0x20446 push 0x4e → #78
RES_POOL = operand(0x25C63, "push ")           # 0x25c63 push 0x1f → #31
IDX_TYPE = operand(0x1653E, "push ")           # typewriter_tick
IDX_STEP = operand(0x322C7, "push ")           # play_step_sfx 地形 0 / 1 那一支
# 呼叫之後的返回位址(紀錄裡的 [esp])
RET_TITLE_LOAD, RET_TITLE_PLAY, RET_CONFIRM = 0x1F8E3, 0x1FD29, 0x1FEE0
RET_ANI_LOAD, RET_ANI_PLAY, RET_POOL_LOAD = 0x20454, 0x20552, 0x25C75
RET_TYPE, RET_STEP = 0x1654B, 0x3230C
for _call, _ret in ((0x1F8DE, RET_TITLE_LOAD), (0x1FD24, RET_TITLE_PLAY), (0x1FEDB, RET_CONFIRM), (0x2044F, RET_ANI_LOAD),
                    (0x2054D, RET_ANI_PLAY), (0x25C70, RET_POOL_LOAD), (0x16546, RET_TYPE), (0x32307, RET_STEP)):
    assert insn(_ret).startswith("add esp, ") and _ret == _call + 5, (hex(_call), hex(_ret))

# 函式名(登錄表)與入口
_NM = {int(r["addr"], 16): r["name"] for r in json.loads(NAMES.read_text(encoding="utf-8"))["names"]}
_ENT = sorted(_NM)


def func_of(a: int) -> int:
    return _ENT[bisect.bisect_right(_ENT, a) - 1]


assert _NM[func_of(0x1FD24)] == "title_seq" and _NM[func_of(0x2054D)] == "ani_player"
assert _NM[func_of(RET_TYPE)] == "typewriter_tick" and _NM[func_of(RET_STEP)] == "play_step_sfx"
assert _NM[func_of(RET_POOL_LOAD)] == "game_main"

# ================= 全 EXE:直接呼叫兩個播放函式的每一處,推的音效池與 index =================
INSNS, _stops = dl.resync_sweep(_MD, _CODE, _CBASE)
_IX = {i.address: k for k, i in enumerate(INSNS)}
BRANCH: dict[int, list[tuple[int, str]]] = collections.defaultdict(list)   # 目標 → [(來源, 助記符)]
for _i in INSNS:
    if (_i.mnemonic == "call" or _i.mnemonic.startswith("j")) and re.fullmatch(r"0x[0-9a-f]+", _i.op_str):
        BRANCH[int(_i.op_str, 16)].append((_i.address, _i.mnemonic))


def text(i) -> str:
    return f"{i.mnemonic} {i.op_str}"


SITES = []
for tgt in (PLAY_A, PLAY_B):
    hits, _ = dl.find_rel_callers(_MD, _CODE, _CBASE, tgt)
    assert all(al for _a, _m, _o, al in hits) and all(m == "call" for _a, m, _o, _al in hits), hits
    for a, _m, _o, _al in hits:
        k = _IX[a]
        buf, idx = INSNS[k - 1], INSNS[k - 2]
        assert buf.mnemonic == "push" and a not in BRANCH, hex(a)
        # 推 index 的那條:順著往下的一條,加上每一個跳到「推音效池那條」的 jmp 前一條
        paths = [(None, idx)]
        for src, mn in BRANCH.get(buf.address, []):
            assert mn == "jmp", (hex(a), hex(src), mn)        # 只處理無條件跳入;條件跳入的話這裡要重寫
            paths.append((src, INSNS[_IX[src] - 1]))
        assert idx.address not in BRANCH, hex(a)
        for via, ins in paths:
            assert ins.mnemonic == "push", (hex(a), text(ins))
            SITES.append({"call": a, "target": tgt, "buf": buf.op_str, "via": via, "idx_at": ins.address, "idx": ins.op_str})
POOL_SITES = [s for s in SITES if "push " + s["buf"] == POOL_PUSH]
assert all(re.fullmatch(r"-?(0x[0-9a-f]+|\d+)", s["idx"]) for s in POOL_SITES), [s for s in POOL_SITES if not s["idx"][-1].isdigit()]
BY_IDX = collections.defaultdict(list)
for s in POOL_SITES:
    BY_IDX[int(s["idx"], 0)].append(s)
STEP_SITES = [(s["idx_at"], s["via"], s["call"]) for s in BY_IDX[IDX_STEP]]
TYPE_SITES = [(s["idx_at"], s["via"], s["call"]) for s in BY_IDX[IDX_TYPE]]
assert STEP_SITES == [(0x322C7, 0x322C9, 0x32307)], STEP_SITES
assert [c for _i, _v, c in TYPE_SITES] == [0x16546, 0x34126, 0x34162] and all(v is None for _i, v, _c in TYPE_SITES), TYPE_SITES
# 0x34126 / 0x34162 在防拷問答裡;它唯一的呼叫點 0x118ac 前一條是無條件 jmp(跳過它),也沒有任何分支或 fixup 指到 0x118ac / 入口
CP = func_of(0x34126)
assert func_of(0x34162) == CP and _NM[CP] == "copy_protection_password_check"
_cp_callers, _ = dl.find_rel_callers(_MD, _CODE, _CBASE, CP)
assert [(a, m) for a, m, _o, _al in _cp_callers] == [(0x118AC, "call")], _cp_callers
_pre = INSNS[_IX[0x118AC] - 1]
_skip = int(_pre.op_str, 16)
assert _pre.mnemonic == "jmp" and _pre.address + _pre.size == 0x118AC and _skip > 0x118AC + INSNS[_IX[0x118AC]].size, text(_pre)
assert 0x118AC not in BRANCH
_FX = set(dl.build_fixups(_EXE, dl.parse_le(_EXE)).values())
assert 0x35854 in _FX                                     # 對照:跳表裡已知的函式指標(disasm_le selftest (3))查得到
assert CP not in _FX and 0x118AC not in _FX
CP_DEAD = {"entry": hex(CP), "only_call": "0x118ac", "jmp_before": f"{_pre.address:#x} {text(_pre)}"}

# ================= (T) / (I) cl1 .. cl14:實際的載入與播放 =================
_hd = {int(re.search(r" dump=(\d+) ", p.open(encoding="ascii").readline()).group(1)) for p, _m in CL.values()}
assert len(_hd) == 1, _hd
HEAD = _hd.pop()                                          # 紀錄的傾印大小(指標處幾個位元組)
H77, H78, H31 = res(RES_TITLE)[:HEAD], res(RES_ANI)[:HEAD], res(RES_POOL)[:HEAD]
# 6235 那段的另外兩處(續一百七十八)開頭跟 #77 不同,只看指標處的 32 位元組就分得出
_ALT = [w for w in S178["sounds"] if ["FDOTHER.DAT", RES_TITLE, IDX_TITLE] in w["where"]]
assert len(_ALT) == 1 and len(_ALT[0]["where"]) == 3, _ALT
SND_TITLE = _ALT[0]
assert len(seg(RES_TITLE, IDX_TITLE)) == SND_TITLE["length"] and hashlib.md5(seg(RES_TITLE, IDX_TITLE)).hexdigest() == SND_TITLE["md5"]
OTHER_HEADS = {f"#{r}": res(r)[:HEAD] for _f, r, _j in SND_TITLE["where"] if r != RES_TITLE}
assert len(OTHER_HEADS) == 2 and all(h != H77 for h in OTHER_HEADS.values()), OTHER_HEADS
CL_ROWS = {}
POOL_CALLERS: dict[int, collections.Counter] = {IDX_TYPE: collections.Counter(), IDX_STEP: collections.Counter()}
for nm, (p, m5) in CL.items():
    lg = read_log(p, m5)
    by_ret = collections.defaultdict(list)
    for c in lg.calls:
        if c.eip in (rt(LOAD), rt(PLAY_A), rt(PLAY_B)):
            by_ret[(c.eip - DELTA, c.ret - DELTA)].append(c)
    (ld,) = by_ret[(LOAD, RET_TITLE_LOAD)]
    (pl,) = by_ret[(PLAY_B, RET_TITLE_PLAY)]
    assert ld.mem_prefix["s1"].split(b"\0")[0] == b"FDOTHER.DAT" and ld.stack[1:3] == [0, RES_TITLE], (nm, ld.stack[:3])
    assert pl.stack[1:3] == [IDX_TITLE, 1] and pl.line > ld.line, (nm, pl.stack[:3])
    assert pl.mem_prefix["s1"] == H77, nm                       # 指標處就是 #77 的開頭
    r = lg.rets.get(ld.seq)
    direct = r is not None and r.kind == "R"
    if direct:
        assert r.eax == pl.stack[0], (nm, hex(r.eax))
    # 載入之後、播放之前沒有別的載入回同一個指標(緩衝之後會被別的資源重用)
    assert not any(c.line > ld.line and c.line < pl.line and lg.rets.get(c.seq) is not None and lg.rets[c.seq].eax == pl.stack[0]
                   for c in lg.calls if c.eip == rt(LOAD)), nm
    conf = by_ret[(PLAY_A, RET_CONFIRM)]
    assert all(c.stack[0] == pl.stack[0] and c.stack[1] == IDX_CONFIRM for c in conf), nm
    ani = by_ret[(PLAY_A, RET_ANI_PLAY)]
    assert ani and all(c.mem_prefix["s1"] == H78 and c.stack[1] == 0 for c in ani), (nm, len(ani))
    assert all(c.stack[2] == RES_ANI for c in by_ret[(LOAD, RET_ANI_LOAD)]) and by_ret[(LOAD, RET_ANI_LOAD)], nm
    (pool_ld,) = by_ret[(LOAD, RET_POOL_LOAD)]
    pr = lg.rets[pool_ld.seq]
    assert pool_ld.stack[2] == RES_POOL and pr.kind == "R", nm
    pool = pr.eax
    pool_plays = [c for k, v in by_ret.items() if k[0] in (PLAY_A, PLAY_B) for c in v if c.stack[0] == pool]
    assert pool_plays and all(c.mem_prefix["s1"] == H31 for c in pool_plays), nm
    for c in pool_plays:
        if c.stack[1] in POOL_CALLERS:
            POOL_CALLERS[c.stack[1]].update([c.ret - DELTA])
    title_ptr, *_rest = pl.stack
    n_a = sum(len(v) for k, v in by_ret.items() if k[0] == PLAY_A)
    assert n_a == sum(c.eip == rt(PLAY_A) for c in lg.calls), nm
    CL_ROWS[nm] = {"title_ptr": hex(title_ptr), "load_ret_seen": direct, "confirm_plays": len(conf), "ani_plays": len(ani),
                   "pool": hex(pool), "pool_plays": len(pool_plays), "play_a_calls": n_a}
assert sum(r["load_ret_seen"] for r in CL_ROWS.values()) >= 1
assert set(POOL_CALLERS[IDX_TYPE]) == {RET_TYPE} and set(POOL_CALLERS[IDX_STEP]) == {RET_STEP}, POOL_CALLERS
assert all(POOL_CALLERS[k][r] > 0 for k, r in ((IDX_TYPE, RET_TYPE), (IDX_STEP, RET_STEP)))

# ================= (T) / (I) lc174a / lc174b / lc173a:混音序列與時刻 =================
BASE0 = S176["prediction"]["base0"]
PER_MIX = S176["static"]["per_sample"]["mix"]
END = S176["static"]["mix_end"] + S176["static"]["src_done"]


def m_of(t: int) -> int | None:
    q, r = divmod(t - BASE0 - END, PER_MIX)
    return q if r == 0 else None


TRUE_T = {}
for _gp in S176["observed"]["partial_groups"]:
    if _gp["mode_n"] >= 3:
        TRUE_T.update({int(v): _gp["mode"] for v in _gp["values"]})
for _w in S178["weak_groups"]:
    TRUE_T.update({v: _w["true"] for v in _w["values"]})
WHERE = {(w["k"], w["m"]): [tuple(x) for x in w["where"]] for w in S178["sounds"]}
K_TITLE = ("FDOTHER.DAT", RES_TITLE, IDX_TITLE)
K_CONF = ("FDOTHER.DAT", RES_TITLE, IDX_CONFIRM)
K_ANI = ("FDOTHER.DAT", RES_ANI, 0)
K_TYPE = ("FDOTHER.DAT", RES_POOL, IDX_TYPE)
K_STEP = ("FDOTHER.DAT", RES_POOL, IDX_STEP)
assert [K_TYPE] in WHERE.values() and [K_STEP] in WHERE.values() and [K_CONF] in WHERE.values() and [K_ANI] in WHERE.values()
LCLOG = {nm: read_log(*LC[nm]) for nm in LC}


def entry_t(nm: str, a: int) -> list[float]:
    return [c.ic[2] for c in LCLOG[nm].calls if c.eip == rt(a)]


ORDER = {}
for nm, fl in S176["observed"]["fills"].items():
    snd, run = [], None
    for i, (t, kind, span) in enumerate(fl):
        if kind == "full":
            run = run if run is not None else (i, t)
            continue
        if kind == "partial":
            st = run if run is not None else (i, t)
            snd.append({"start": st[1], "end": t, "where": WHERE[(i - st[0], m_of(TRUE_T[span]))]})
        run = None
    (t_fd7c,), (t_fed3,), (t_new,) = entry_t(nm, 0x1FD7C), entry_t(nm, 0x1FED3), entry_t(nm, 0x32326)
    s_ani, s_title, s_conf, *_later = snd
    first3 = [s["where"] for s in (s_ani, s_title, s_conf)]
    assert first3 == [[K_ANI], [tuple(x) for x in SND_TITLE["where"]], [K_CONF]], (nm, first3)
    assert s_title["end"] < t_fd7c < t_fed3, nm                                     # 標題那段在選單之前放完
    mix = [f for f in fl if f[1] in ("full", "partial")]
    nxt = next(f for f in mix if f[0] > t_fed3)
    gap = min(b[0] - a[0] for a, b in itertools.pairwise(fl))
    assert nxt[0] == s_conf["start"] and nxt[0] - t_fed3 < gap, (nm, nxt, t_fed3, gap)   # 按確認之後第一次混音就是確認音效
    pool_snd = [s for s in snd if s["where"] in ([K_TYPE], [K_STEP])]
    assert pool_snd and all(s["start"] > t_new for s in pool_snd), nm             # 都在「開始」之後(開場劇情)
    ORDER[nm] = {"sounds_first3": [[list(w) for w in s["where"]] for s in (s_ani, s_title, s_conf)],
                 "starts_ms": [round(s["start"], ndigits=1) for s in (s_ani, s_title, s_conf)], "t_1fd7c": round(t_fd7c, ndigits=1),
                 "t_1fed3": round(t_fed3, ndigits=1), "confirm_first_fill_dt_ms": round(nxt[0] - t_fed3, ndigits=3),
                 "min_fill_gap_ms": round(gap, ndigits=2), "t_new_game": round(t_new, ndigits=1),
                 "pool_sounds": dict(collections.Counter(f"#{s['where'][0][1]}/{s['where'][0][2]}" for s in pool_snd))}
for w in S178["sounds"]:
    if [tuple(x) for x in w["where"]] in ([K_TYPE], [K_STEP]):
        assert all(ORDER[nm]["pool_sounds"][f"#{RES_POOL}/{w['where'][0][2]}"] == n for nm, n in w["per_log"].items()), w

# ================= (R) 沒有 I 紀錄的兩份:中斷號 =================
ISR_REENTER, DIG_SERVE = 0x3EBAD, 0x404C0


def ordered(lg: cs.Log) -> list:
    """E / R / A 依檔案行號排。"""
    return sorted(list(lg.calls) + list(lg.rets.values()), key=lambda x: x.line)


def dig_services(lg: cs.Log) -> list[tuple[int, float, int | None]]:
    """每次 DIG 服務:(E 的 n, t, 遊戲指令數;被重入蓋掉沒有 R 時 None)。"""
    out = []
    for c in lg.calls:
        if c.eip == rt(DIG_SERVE):
            r = lg.rets.get(c.seq)
            out.append((c.ic[1], c.ic[2], r.ic[0] - c.ic[0] if r is not None and r.kind == "R" else None))
    return out


def fill_floor(svc: list) -> int:
    """遊戲指令數的兩群(不填 / 填緩衝)之間最大的倍數落差;回傳上群的最小值。"""
    gs = sorted({g for _n, _t, g in svc if g})
    k = max(range(1, len(gs)), key=lambda i: gs[i] / gs[i - 1])
    assert gs[k] / gs[k - 1] > 10, gs[k - 1:k + 1]
    return gs[k]


REENTRY = {}
for nm in ("lc163a", "lc174a", "lc174b", "lc173a"):
    lg = LCLOG[nm]
    seq = ordered(lg)
    svc = dig_services(lg)
    floor = fill_floor(svc)
    sn = [s[0] for s in svc]
    rows = collections.defaultdict(list)
    for k, x in enumerate(seq):
        if isinstance(x, cs.Call) and x.eip == rt(ISR_REENTER):
            y = seq[k + 1]
            ng = (y.ic[1] - x.ic[1]) - (y.ic[0] - x.ic[0])
            d = svc[bisect.bisect_left(sn, x.ic[1])]
            rows[ng].append({"t": round(x.ic[2], ndigits=1), "next_dig_dt_ms": round(d[1] - x.ic[2], ndigits=3),
                             "next_dig_fill": d[2] is None or d[2] >= floor})
    REENTRY[nm] = rows
# 續一百六十五數的 lc163a(重入之後到下一筆的非遊戲指令)
S165_POST = {"69": 60, "70": 2, "601": 1, "302": 14, "375": 1}
assert {str(k): len(v) for k, v in REENTRY["lc163a"].items()} == S165_POST, REENTRY["lc163a"].keys()
(R375,) = REENTRY["lc163a"][375]
(P375,) = REENTRY["lc174a"][375]                       # 正向對照:I 紀錄直接看到 IRQ 7(續一百七十四)
assert S174["b_mdi375"]["lc174a"]["irq"].split()[0] == "0f" and round(S174["b_mdi375"]["lc174a"]["t0"], 1) == P375["t"]
assert R375["next_dig_fill"] and P375["next_dig_fill"] and R375["next_dig_dt_ms"] == P375["next_dig_dt_ms"], (R375, P375)
CTRL_NG = (302, 303)                                    # MDI 型重入沒夾中斷(續一百七十四 (B));兩型在 lc174a / lc173a 都要出現
assert all(REENTRY[nm].get(ng) for ng in CTRL_NG for nm in ("lc174a", "lc173a")), CTRL_NG
CTRL = [r for nm in REENTRY for ng in CTRL_NG for r in REENTRY[nm].get(ng, [])]
CTRL_FILL = sum(r["next_dig_fill"] for r in CTRL)
assert len(CTRL) > 50 and CTRL_FILL / len(CTRL) < 0.05, (len(CTRL), CTRL_FILL)
assert not any(r["next_dig_fill"] for nm in REENTRY for ng in (601, 602) for r in REENTRY[nm].get(ng, []))

# lc167a:4 次短呼叫(續一百七十五)vs 送鍵時刻
SHORT = S175["b_short_calls"]["lc167a_short"]
assert [r["nongame"] for r in SHORT] == [532, 558, 558, 558], SHORT
FR = json.loads((LIVE167 / "frames_mtime.json").read_text(encoding="utf-8"))["mtime"]
MK = json.loads((LIVE167 / "lc167a_finish.json").read_text(encoding="utf-8"))["marks"]
(H0, L0), (H1, L1) = MK["yes"], MK["P2_c"]
RATE = (L1 - L0) / ((H1 - H0) * 1000)
assert abs(RATE - 1) < 1e-3, RATE                         # 模擬器時間與主機時間 1:1


def host2log(h: float) -> float:
    return L0 + (h - H0) * 1000 * RATE


_src = SWEEP.read_text(encoding="utf-8")
_fe = _src[_src.index("def find_empty_adjacent_tile"):]
_fe = _fe[:_fe.index("\ndef ")]
_pos = [_fe.index(s) for s in ('"findempty_000_start.png"', "send_keys(name, direction)", 'f"findempty_{step:03d}_{direction}.png"')]
assert _pos == sorted(_pos), _pos
SLEEP_DIR = float(re.search(r"send_keys\(name, direction\)\n\s*time\.sleep\(([0-9.]+)\)", _fe).group(1))
assert not any(k.startswith("findempty_clear") for k in FR)        # 起點判讀不是 None:沒有清對話,直接送方向鍵
W0, W1 = host2log(FR["findempty_000_start.png"]), host2log(FR["findempty_001_Up.png"] - SLEEP_DIR)
(KB,) = [r for r in SHORT if r["nongame"] == min(x["nongame"] for x in SHORT)]   # 532 = IRQ 1 的條數(續一百七十五)
I7 = [r for r in SHORT if r is not KB]
assert W0 <= KB["t"] <= W1, (W0, KB["t"], W1)
_fin = (DRV167 / "finish.py").read_text(encoding="utf-8")
_readme = (DRV167 / "README.md").read_text(encoding="utf-8")
assert _fin.count("send_keys(") == 1 and "`finish.py lc167a` → `lc167.py down lc167a`" in _readme
_steps = [json.loads(x) for x in (LIVE167 / "lc167a_steps.jsonl").read_text(encoding="utf-8").splitlines()]
LAST_KEY = max([L0] + [s["t"] for s in _steps])          # step.py 的 t 在送鍵之後;finish 的 YES 在 marks.yes 之後立刻送
assert LAST_KEY == L0
GAP558 = min(r["t"] for r in I7) - LAST_KEY
assert GAP558 > 20000, GAP558

# ================= 輸出 =================
SITE_ROWS = {str(k): [{"idx_push": hex(i), "via_jmp": None if v is None else hex(v), "call": hex(c), "function": _NM[func_of(c)]}
                      for i, v, c in ((s["idx_at"], s["via"], s["call"]) for s in BY_IDX[k])] for k in (IDX_TYPE, IDX_STEP)}
CONC = {
    "title": f"6235 位元組那段由 FDOTHER #{RES_TITLE} 放:title_seq 0x1f8de 載入 #{RES_TITLE}、0x1fd24 play_digital_sample(指標, {IDX_TITLE}, 1);"
             f"12 份 DOSBox-X 呼叫紀錄 cl1 .. cl14 的指標處 32 位元組都是 #{RES_TITLE} 的開頭(#49 / #53 開頭不同)。"
             f"lc174a / lc174b / lc173a 的混音序列 #{RES_ANI} 第 0 段 → #{RES_TITLE} 第 {IDX_TITLE} 段 → #{RES_TITLE} 第 {IDX_CONFIRM} 段,"
             f"與 title_seq 的順序(0x1fd14 ani_player → 0x1fd24 → 0x1fedb)相同。",
    "pool": f"index {IDX_STEP}(sfx_09)是 play_step_sfx 的走路聲:全 EXE 以 UI 音效池 [0x53eec](#{RES_POOL})放 index {IDX_STEP} 的只有 0x322c7;"
            f"index {IDX_TYPE}(sfx_02)是 typewriter_tick 的打字聲(另兩處在防拷問答,唯一呼叫點 0x118ac 前面是無條件 jmp,走不到)。"
            f"cl1 .. cl14 實際:index {IDX_TYPE} {POOL_CALLERS[IDX_TYPE][RET_TYPE]} 次全來自 0x1654b、index {IDX_STEP} {POOL_CALLERS[IDX_STEP][RET_STEP]} 次全來自 0x3230c。",
    "irq": f"lc163a 的 ng 375({R375['t']} ms)之後 {R375['next_dig_dt_ms']} ms 的 DIG 服務是填緩衝,與 lc174a 直接看到 IRQ 7 的那次"
           f"({P375['t']} ms,{P375['next_dig_dt_ms']} ms)同型;沒夾中斷的 302 / 303 型 {len(CTRL)} 次只有 {CTRL_FILL} 次接著填。"
           f"lc167a 532 那次在送 Up 鍵的窗內({round(W0, ndigits=1)} .. {round(W1, ndigits=1)} ms),558 那 3 次在最後一次送鍵之後 "
           f"{round(GAP558 / 1000, ndigits=1)} 秒以上 —— 兩份都仍沒有 I 紀錄,這是獨立佐證,不是直接看到。",
}
for _part, _key in ((f"#{RES_TITLE} 第 {IDX_TITLE} 段", "title"), ("play_step_sfx 的走路聲", "pool"), ("typewriter_tick 的打字聲", "pool"),
                    ("不是直接看到", "irq")):
    assert _part in CONC[_key], (_part, _key)
out = {
    "generator": "docs/knowledge-base/evidence/generators/ev_s179.py",
    "exe_md5": MD5,
    "calllogs": {**{nm: {"path": rel(p), "md5": m} for nm, (p, m) in CL.items()},
                 **{nm: {"path": rel(p), "md5": m} for nm, (p, m) in LC.items()}},
    "upstream": [rel(EVIDENCE / f) for f in ("audio_followups_s175_20261031.json", "trig_capture_s174_20261031.json",
                                             "dig_fill_lengths_s176_20261031.json", "dig_word_order_sfx_s178_20261101.json")],
    "static": {"res_title": RES_TITLE, "idx_title": IDX_TITLE, "idx_confirm": IDX_CONFIRM, "res_ani": RES_ANI, "res_pool": RES_POOL,
               "idx_type": IDX_TYPE, "idx_step": IDX_STEP, "play_call_sites": len({s["call"] for s in SITES}),
               "pool_sites_by_idx": SITE_ROWS, "copy_protection_unreachable": CP_DEAD},
    "cl_logs": CL_ROWS,
    "pool_callers": {str(k): {hex(r): n for r, n in v.items()} for k, v in POOL_CALLERS.items()},
    "lc_order": ORDER,
    "reentry_nongame": {nm: {str(k): len(v) for k, v in sorted(rows.items())} for nm, rows in REENTRY.items()},
    "ng375": {"lc163a": R375, "lc174a_irq7": P375},
    "control_302_303": {"n": len(CTRL), "next_dig_fill": CTRL_FILL},
    "lc167a": {"short": SHORT, "clock_rate": round(RATE, ndigits=7), "up_window_ms": [round(W0, ndigits=1), round(W1, ndigits=1)],
               "last_key_ms": LAST_KEY, "gap_558_ms": round(GAP558, ndigits=1)},
    "conclusion": CONC,
}
OUT.write_text(json.dumps(out, ensure_ascii=False, indent=1) + "\n", encoding="utf-8", newline="\n")
print("wrote", OUT)
