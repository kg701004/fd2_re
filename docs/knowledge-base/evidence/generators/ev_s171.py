"""續一百七十一證據:evidence/calllog_segments_s171_20261030.json(非遊戲指令落在哪一段、int 21h 多出的指令、MDI 型重入收中斷的點)。

使用者 2026-10-30「先進行工具新建和優化改善」「請繼續」。工具:tools/dosbox/fd2_calllog_patch.py 加 FD2_CALLLOG_SEGS
(時間窗內每段同一 selector / 模式的連續指令一筆 G、逐條一筆 S、每次 CPU_Interrupt 一筆 I),解析在 tools/calllog_segments.py。
實機 lc171a / lc171b(原版 FD2.EXE、WSL -d Ubuntu、步驟同續一百六十三 lc163a:開機 → 標題 → START;drivers_s171/lc171.py)。
(A) 紀錄本身:時間窗內的指令數逐段相接(只在兩窗之間斷開);E / R / A 的 n 全落在遊戲段內;I 全在段的邊界上。
(B) 續一百六十五「校準每次 int 21h 比 delay 多 4 .. 9 條非遊戲指令」:兩者走同一條 9 段路徑,固定差 6 條在 DOS/4GW 的 int 21h
    轉送(selector 0088)裡一個看 CF 的分支;CF 是遊戲在 int 21h 之前留下的(DOSBox-X 的 AH=2Ch 不動 CF):校準兩個迴圈是 0,
    delay 迴圈是 cmp 0, dh 的結果(DH > 0 時 1),每次 delay 呼叫的第一次是 xor 之後的 0。
(C) 其餘起伏是同一條 rep movsw 被記了不只一次;把連續相同的 rep 指令併成一條後,同一組 int 21h 的指令序列全部相同。
(D) 續一百六十五「MDI 型收中斷的點在驅動 iret 還是 DOS/4GW 返回路徑」:MDI 驅動呼叫期間的硬體中斷全收在 DOS/4GW 真實模式
    模擬中斷那段 int 66h 的下一條(0c5c:1fad),前一段正是驅動 SBPRO2.MDI 的 iret(0f71:01b1)。
任何判準不符就 assert 失敗。
"""
from __future__ import annotations

import bisect
import collections
import hashlib
import json
import re

from _evpaths import EVIDENCE, GAME, GEN_DIR, ROOT, out_path, rel, require_inputs  # noqa: E402
require_inputs(__file__)
from _exeops import _EXE, insn  # noqa: E402  (_exeops 已把 tools/ 加進 sys.path)
import calllog_segments as cs  # noqa: E402

OUT = out_path("calllog_segments_s171_20261030.json")
MD5 = "33464c81e6a364fd0660141139aa8e6e"
DRV = GEN_DIR / "drivers_s171"
RAW = ROOT / ".wsl_build" / "lc171_live"
DELTA = 0x19C000
GAME_CS = 0x170
S165 = json.loads((EVIDENCE / "reentry_catchup_mdi_driver_s165_20261029.json").read_text(encoding="utf-8"))

assert hashlib.md5(_EXE).hexdigest() == MD5
LOGS = {"lc171a": "0323eeb1d98d77814b42148f6bd87a33", "lc171b": "2b18d320078a7fbbf8465c4366efdc6f"}
SEGS = {"lc171a": "1700-2000,2000-2010:x,2010-3400,3700-5000,5000-5010:x,5010-7900",
        "lc171b": "2000-2010:x,3800-3810:x,6300-6310:x"}
assert all(f'"{k}": "{v}"' in (DRV / "lc171.py").read_text(encoding="utf-8") for k, v in SEGS.items())
TEXT: dict[str, list[str]] = {}
LOG: dict[str, cs.Log] = {}
EPS: dict[str, list[cs.Episode]] = {}
for _k, _md5 in LOGS.items():
    _b = (RAW / f"{_k}_CALLLOG.TXT").read_bytes()
    assert hashlib.md5(_b).hexdigest() == _md5, _k
    TEXT[_k] = _b.decode("ascii").splitlines()
    # 最後一行是 teardown 砍掉 dosbox-x 時截斷的 E 紀錄(atexit 沒跑到),不是 G / S / I,解析器略過
    assert TEXT[_k][0].endswith(f" icount=1 segs={SEGS[_k]}"), TEXT[_k][0]
    LOG[_k] = cs.parse(TEXT[_k])
    EPS[_k] = cs.episodes(LOG[_k])
    assert LOG[_k].game_cs == GAME_CS

# ================= (A) 紀錄本身 =================
_rx_icount = re.compile(r" i=(\d+) n=(\d+) t=([0-9.]+)$")


def era_check(k: str) -> dict:
    """E / R / A 的 n 是否落在遊戲段內(時間窗內的才算)。"""
    lg = LOG[k]
    ends = [r.n_end for r in lg.runs]
    first, last = lg.runs[0].n_start, lg.runs[-1].n_end
    ok = bad = outside = trunc = 0
    for ln in TEXT[k]:
        if ln[:1] not in "ERA" or ln[1:2] != " ":
            continue
        m = _rx_icount.search(ln)
        if m is None:
            trunc += 1
            continue
        n = int(m.group(2))
        if n <= first or n > last or any(a < n <= b for a, b in lg.gaps):
            outside += 1
            continue
        r = lg.runs[bisect.bisect_left(ends, n)]
        if r.n_start < n <= r.n_end and r.cs == GAME_CS and r.m == "P":
            ok += 1
        else:
            bad += 1
    return {"inside_game_run": ok, "not_in_game_run": bad, "outside_windows": outside, "truncated_last_line": trunc}


def boundary_check(k: str) -> dict:
    """I 紀錄的 n 是否同時是一段的結尾與下一段的開頭。"""
    lg = LOG[k]
    ends, starts = {r.n_end for r in lg.runs}, {r.n_start for r in lg.runs}
    at = sum(1 for q in lg.irqs if q.n in ends and q.n in starts)
    return {"irq_records": len(lg.irqs), "at_run_boundary": at}


VALID = {k: {"runs": len(LOG[k].runs), "gaps": LOG[k].gaps, "era": era_check(k), "irq": boundary_check(k)} for k in LOGS}
for k in LOGS:
    assert VALID[k]["era"]["not_in_game_run"] == 0 and VALID[k]["era"]["truncated_last_line"] == 1, VALID[k]
    assert VALID[k]["irq"]["at_run_boundary"] == VALID[k]["irq"]["irq_records"] > 0, VALID[k]
# lc171a 只在 3400 .. 3700 那個空窗斷開一次;lc171b 三個逐條窗之間斷開兩次
assert len(VALID["lc171a"]["gaps"]) == 1 and len(VALID["lc171b"]["gaps"]) == 2, (VALID["lc171a"]["gaps"], VALID["lc171b"]["gaps"])
assert VALID["lc171a"]["era"]["inside_game_run"] == 4979 and VALID["lc171a"]["irq"]["irq_records"] == 22865
assert [VALID[k]["era"]["outside_windows"] for k in LOGS] == [17287, 17743], VALID

# ================= (B) 校準與 delay 的 int 21h =================
# 遊戲端(FD2.EXE 反組譯):三個 int 21h 與前面決定 CF 的指令
CAL1, CAL2, DLY = 0x3DFFD, 0x3E00D, 0x3E04D
STATIC = {a: insn(a) for a in (0x3DFF5, 0x3DFFB, CAL1, 0x3E003, 0x3E005, 0x3E00B, CAL2, 0x3E010, 0x3E012,
                                0x3E047, 0x3E049, 0x3E04B, DLY, 0x3E04F, 0x3E051, 0x3E052, 0x3F1A2)}
assert [STATIC[a] for a in (CAL1, CAL2, DLY)] == ["int 0x21"] * 3
assert STATIC[0x3DFF5] == "xor eax, eax" and STATIC[0x3E003] == "cmp ebx, eax" and STATIC[0x3E005] == "je 0x3dffb"
assert STATIC[0x3E010] == "cmp bl, dh" and STATIC[0x3E012] == "je 0x3e00b"
assert (STATIC[0x3E047], STATIC[0x3E049], STATIC[0x3E04F], STATIC[0x3E051], STATIC[0x3E052]) == (
    "xor eax, eax", "mov bl, al", "cmp bl, dh", "dec esi", "jne 0x3e04b")
assert STATIC[0x3F1A2] == "int 0x31"
# int 21h 前一條都是 mov ah, 0x2c(不動旗標),所以 CF 由再前面那條決定
assert [STATIC[a] for a in (0x3DFFB, 0x3E00B, 0x3E04B)] == ["mov ah, 0x2c"] * 3
# DOSBox-X:case 0x2c 不設 CF(沒有 CALLBACK_SCF),結尾的 overhead() 只動 IP
DOS2C = (DRV / "dosbox_dos_int21_2c.txt").read_text(encoding="utf-8").splitlines()
assert DOS2C[0].startswith("source ~/fd2-dosbox-calllog2/dosbox-x/src/dos/dos.cpp ") and DOS2C[1].strip().startswith("case 0x2c:")
_ov = DOS2C.index("--- same file lines 583-585 (overhead, called at the end of case 0x2c)")
assert not any("SCF" in ln or "reg_flags" in ln or "SETFLAGBIT" in ln for ln in DOS2C[1:_ov])
assert DOS2C[_ov - 3].strip() == "overhead();" and [ln.strip() for ln in DOS2C[_ov + 1:]] == [
    "static inline void overhead() {", "reg_ip += 2;", "}"]


def rt(a: int) -> int:
    return a + DELTA


E3B = ("p", 0x88, 0xE3B)                # DOS/4GW int 21h 轉送裡看 CF 的那一段(進入點)


def seg(ep: cs.Episode, key: tuple[str, int, int]) -> list[cs.Run]:
    return [r for r in ep.runs if (r.m, r.cs, r.e0) == key]


G_A = cs.group_episodes(EPS["lc171a"])
GROUPS = {name: G_A[(rt(a), rt(a) + 2)] for name, a in (("cal_3dffd", CAL1), ("cal_3e00d", CAL2), ("delay_3e04d", DLY))}
# 三組的主要路徑(進入點序列)相同:9 段
MAIN = {}
for name, lst in GROUPS.items():
    c = collections.Counter(tuple((r.m, r.cs, r.e0) for r in e.runs) for e in lst)
    MAIN[name] = c.most_common(1)[0]
assert len({p for p, _n in MAIN.values()}) == 1 and len(MAIN["cal_3dffd"][0]) == 9, MAIN
MAIN_PATH = MAIN["cal_3dffd"][0]
assert E3B in MAIN_PATH


def path_class(c: int) -> str:
    """E3B 那段的條數:33 .. 35 短路、39 .. 41 長路(差 0 .. 2 是 rep movsw 多記);其他是那段被中斷切開。"""
    return "short" if 33 <= c <= 35 else "long" if 39 <= c <= 41 else "split"


def preceding_game_runs(k: str) -> dict[int, cs.Run]:
    """episode 編號 -> 它前面那段遊戲 run(緊接、n 相接)。"""
    out: dict[int, cs.Run] = {}
    lg, eps = LOG[k], EPS[k]
    first_run = {id(e.runs[0]): e.index for e in eps if e.runs}
    prev = None
    for kind, i in lg.order:
        if kind != "G":
            continue
        r = lg.runs[i]
        if id(r) in first_run and prev is not None and prev.cs == GAME_CS and prev.m == "P" and prev.n_end == r.n_start:
            out[first_run[id(r)]] = prev
        prev = r
    return out


_GAME_RUNS = {k: [r for r in LOG[k].runs if r.cs == GAME_CS and r.m == "P"] for k in LOGS}
_GAME_IDX = {k: {id(r): i for i, r in enumerate(v)} for k, v in _GAME_RUNS.items()}


def cf_of(r: cs.Run) -> str | None:
    """依遊戲 run 的起點與條數判斷 int 21h 前的 CF;看不出來回傳 None。

    迴圈是 0x3e04f cmp bl, dh / 051 dec / 052 jne / 04b mov / 04d int(5 條);第一次是 047 xor / 049 mov / 04b / 04d。
    int 21h 一定離開遊戲 selector,所以一段 run 裡最多一次經過 int:從 04f 起、不超過 5 條是迴圈;超過 5 條是離開 delay
    又從 0x3e01d 進來(經過 xor)。起點 051 / 052 是 cmp 之後被中斷;起點 04b / 04d 兩條路都會經過,要往前看。
    """
    e0 = r.e0 - DELTA
    if e0 == 0x3E04F:
        return "cf1_loop" if r.count <= 5 else "cf0_first"
    if e0 in (0x3E051, 0x3E052):
        return "cf1_loop"
    if e0 in (0x3E04B, 0x3E04D):
        return None
    return "cf0_first"


_STOP = {rt(a) for a in (0x3E047, 0x3E049, 0x3E04B, 0x3E04F, 0x3E051, 0x3E052)}   # 被中斷時的最後一條


def cf_source(k: str, g: cs.Run) -> str:
    """int 21h 前的 CF 從哪裡來;g 被中斷切開時往前找被切的那段(中斷處理的遊戲 run 跳過;iret 還原旗標,CF 不變)。"""
    i = _GAME_IDX[k][id(g)]
    cf = cf_of(g)
    while cf is None:
        i -= 1
        while i >= 0 and _GAME_RUNS[k][i].e1 not in _STOP:
            i -= 1
        if i < 0:
            return "unknown"
        cf = cf_of(_GAME_RUNS[k][i])
    return cf


def cf_table(k: str) -> dict:
    """delay 的 int 21h:前面遊戲指令決定的 CF 與 E3B 段走的路。"""
    pre = preceding_game_runs(k)
    tab: collections.Counter = collections.Counter()
    for e in EPS[k]:
        if not (e.complete and e.left_from == rt(DLY) and e.back_to == rt(DLY) + 2):
            continue
        g = pre.get(e.index)
        if g is None:
            tab[("no_game_run", "-")] += 1
            continue
        cf = cf_source(k, g)
        assert cf in ("cf0_first", "cf1_loop"), cf
        s = seg(e, E3B)
        tab[(cf, path_class(s[0].count) if len(s) == 1 else "no_e3b")] += 1
    return {f"{a}|{b}": n for (a, b), n in sorted(tab.items())}


CF = {k: cf_table(k) for k in LOGS}
for k in LOGS:
    # 判準:CF = 0 -> 長路、CF = 1 -> 短路,反例 0(DH = 0 的那一秒兩份紀錄都沒遇到)
    assert CF[k].get("cf0_first|short", 0) == 0 and CF[k].get("cf1_loop|long", 0) == 0, CF[k]
assert CF["lc171a"].get("cf0_first|long") == 259 and CF["lc171a"].get("cf1_loop|short") == 8431, CF["lc171a"]
assert CF["lc171b"].get("cf0_first|long") == 1 and CF["lc171b"].get("cf1_loop|short") == 97, CF["lc171b"]
# 校準兩組全是 CF = 0:沒有短路
CAL_CLASS = {name: dict(collections.Counter(path_class(seg(e, E3B)[0].count) for e in GROUPS[name]
                                            if len(seg(e, E3B)) == 1)) for name in ("cal_3dffd", "cal_3e00d")}
assert all("short" not in v for v in CAL_CLASS.values()), CAL_CLASS
assert CAL_CLASS == {"cal_3dffd": {"long": 3127}, "cal_3e00d": {"long": 9053, "split": 2}}, CAL_CLASS

# lc171b 逐條窗:校準 #1 與 delay #94 逐指令對齊
EB = EPS["lc171b"]
CAL_EP, DLY_EP = EB[1], EB[94]
assert (CAL_EP.left_from, DLY_EP.left_from) == (rt(CAL2), rt(DLY)) and (CAL_EP.total, DLY_EP.total) == (481, 475)
DIFF = cs.diff_runs(CAL_EP, DLY_EP, LOG["lc171b"].code)
assert DIFF[0] == "  run p 0088 00000e3b: 39 vs 33 (-6); last 000021c2 vs 000021c2" and len(DIFF) == 1 + 10 + 4, DIFF
CAL_ONLY = [ln[6:14] for ln in DIFF[1:] if ln.startswith("    - ")]
DLY_ONLY = [ln[6:14] for ln in DIFF[1:] if ln.startswith("    + ")]
assert len(CAL_ONLY) - len(DLY_ONLY) == 6 == CAL_EP.total - DLY_EP.total
CODE_B = LOG["lc171b"].code


def dis(m: str, c: int, e: int) -> str:
    return cs.disasm_one(m, e, CODE_B[(m, c, e)])


BRANCH = {"test": dis("p", 0x88, 0x2149), "jcc": dis("p", 0x88, 0x214D), "cf0_next": dis("p", 0x88, 0x214F),
          "cf1_next": dis("p", 0x88, 0x2152)}
assert BRANCH == {"test": "test byte ptr [bp - 0x22], 1", "jcc": "jne 0x2152", "cf0_next": "jmp 0x2160",
                  "cf1_next": "mov ax, word ptr [bp - 0x34]"}, BRANCH
assert CAL_ONLY[0] == "0000214f" and DLY_ONLY[0] == "00002152"

# ================= (C) rep movsw 多記 =================


def is_rep(m: str, c: int, e: int) -> bool:
    """那個位置的指令有 rep / repe / repne 前綴(以反組譯判斷;0x66 等前綴可能排在 F3 前面)。"""
    code = CODE_B.get((m, c, e))
    return code is not None and cs.disasm_one(m, e, code).split(" ", 1)[0] in ("rep", "repe", "repne")


def collapse(ep: cs.Episode) -> tuple:
    """逐條紀錄併掉連續相同的 rep 前綴指令(同一條 rep 被記不只一次)。"""
    out: list[tuple[str, int, int]] = []
    for r in ep.runs:
        assert r.eips is not None
        for e in r.eips:
            item = (r.m, r.cs, e)
            if out and out[-1] == item and is_rep(*item):
                continue
            out.append(item)
    return tuple(out)


S_GROUPS = collections.defaultdict(list)
_pre_b = preceding_game_runs("lc171b")
for e in EB:
    if e.complete and e.runs and all(r.eips is not None for r in e.runs):
        if e.left_from == rt(CAL2):
            S_GROUPS["cal_3e00d"].append(e)
        elif e.left_from == rt(DLY) and e.back_to == rt(DLY) + 2:
            g = _pre_b.get(e.index)
            if g is not None and g.e0 == rt(0x3E04F) and g.count == 5:
                S_GROUPS["delay_loop"].append(e)
REP = {}
for name, lst in S_GROUPS.items():
    seqs = collections.Counter(collapse(e) for e in lst)
    tot = collections.Counter(e.total for e in lst)
    REP[name] = {"episodes": len(lst), "distinct_after_collapse": len(seqs), "collapsed_len": len(next(iter(seqs))),
                 "totals": {str(t): n for t, n in sorted(tot.items())}}
# 併掉 rep 多記之後,同一組只剩一種指令序列;兩組相差 6 條
assert REP["cal_3e00d"]["episodes"] == 86 and REP["delay_loop"]["episodes"] == 97, REP
assert REP["cal_3e00d"]["distinct_after_collapse"] == 1 and REP["delay_loop"]["distinct_after_collapse"] == 1, REP
assert REP["cal_3e00d"]["collapsed_len"] - REP["delay_loop"]["collapsed_len"] == 6, REP
# 對照:不併 rep 時同一組不只一種
assert len({tuple((r.m, r.cs, e) for r in x.runs for e in r.eips) for x in S_GROUPS["cal_3e00d"]}) > 1
# 與續一百六十五(lc163a)的平均:兩者都不低於本輪的最小值 481 / 475,差的是 rep 多記的次數
S165_CAL = S165["calibration"]["calibration_per_int21"]
S165_DLY = S165["calibration"]["per_int21_range"]
MIN_CAL = min(int(t) for t in REP["cal_3e00d"]["totals"])
MIN_DLY = min(int(t) for t in REP["delay_loop"]["totals"])
assert (MIN_CAL, MIN_DLY) == (481, 475) and S165_CAL[0] >= MIN_CAL and S165_DLY[0] >= MIN_DLY, (S165_CAL, S165_DLY)

# ================= (D) MDI 型重入收中斷的點 =================
LA = LOG["lc171a"]
_ep_of_irq = {id(q): e for e in EPS["lc171a"] for q in e.irqs}
MDI_IRQ = [q for q in LA.irqs if q.type == 0 and _ep_of_irq.get(id(q)) is not None
           and _ep_of_irq[id(q)].left_from == rt(0x3F1A2)]
assert len(MDI_IRQ) == 3 and {(q.num, q.m, q.cs, q.eip) for q in MDI_IRQ} == {(0x08, "r", 0x0C5C, 0x1FAD)}, MDI_IRQ
# 每一次:前一段是驅動 SBPRO2.MDI 那段、結尾在 iret(0f71:01b1)
_pos = {id(LA.irqs[i]): k for k, (kind, i) in enumerate(LA.order) if kind == "I"}
BEFORE = []
for q in MDI_IRQ:
    k = _pos[id(q)]
    kind, i = LA.order[k - 1]
    assert kind == "G"
    r = LA.runs[i]
    BEFORE.append((r.m, r.cs, r.e0, r.e1))
assert {(m, c, e1) for m, c, _e0, e1 in BEFORE} == {("r", 0x0F71, 0x1B1)}, BEFORE
CODE_A = LA.code
MDI_FILE = (GAME / "SBPRO2.MDI").read_bytes()
# 0f71 就是 SBPRO2.MDI 從位移 0 載入:紀錄裡每個 0f71 位置的 16 個碼位元組與檔案同一位移相同
_drv = [(e, b) for (m, c, e), b in CODE_A.items() if c == 0x0F71 and b is not None]
assert len(_drv) > 200 and all(MDI_FILE[e:e + 16] == b for e, b in _drv), len(_drv)
CHAIN = {"stub_popf": cs.disasm_one("r", 0x1FAA, CODE_A[("r", 0x0C5C, 0x1FAA)]),
         "stub_int": cs.disasm_one("r", 0x1FAB, CODE_A[("r", 0x0C5C, 0x1FAB)]),
         "stub_after": cs.disasm_one("r", 0x1FAD, CODE_A[("r", 0x0C5C, 0x1FAD)]),
         "stub_cli": cs.disasm_one("r", 0x1FAE, CODE_A[("r", 0x0C5C, 0x1FAE)]),
         "hook_137c": cs.disasm_one("r", 0x16A, CODE_A[("r", 0x137C, 0x16A)]),
         "hook_137c_chain": cs.disasm_one("r", 0x1FA, CODE_A[("r", 0x137C, 0x1FA)]),
         "driver_entry": cs.disasm_one("r", 0x132, MDI_FILE[0x132:0x142]),
         "driver_iret": cs.disasm_one("r", 0x1B1, MDI_FILE[0x1B1:0x1C1])}
assert CHAIN == {"stub_popf": "popf", "stub_int": "int 0x66", "stub_after": "pushf", "stub_cli": "cli",
                 "hook_137c": "cmp ax, 0x300", "hook_137c_chain": "ljmp cs:[0x36]",
                 "driver_entry": "cmp ax, 0x300", "driver_iret": "iret"}, CHAIN
# 路徑:模擬中斷 int 66h -> 137c 的掛勾 -> 驅動分派 -> iret -> 0c5c:1fad(收中斷)-> cli
HOOK = ("r", 0x137C, 0x16A)
DRV_IN = ("r", 0x0F71, 0x132)


def via_hook(e: cs.Episode) -> bool:
    """驅動入口前面是 137c 的掛勾(True)或直接是 stub 的 int 66h(False);兩者都不是就 assert。"""
    keys = [(r.m, r.cs, r.e0) for r in e.runs]
    i = keys.index(DRV_IN)
    if keys[i - 1] == HOOK:
        assert e.runs[i - 2].e1 == 0x1FAB, keys
        return True
    assert (e.runs[i - 1].m, e.runs[i - 1].cs, e.runs[i - 1].e1) == ("r", 0x0C5C, 0x1FAB), keys
    return False


MDI_ALL = [e for e in G_A[(rt(0x3F1A2), rt(0x3F1A2) + 2)] if DRV_IN in [(r.m, r.cs, r.e0) for r in e.runs]]
_hook = [via_hook(e) for e in MDI_ALL]
HOOKED = {"calls": len(_hook), "via_137c": sum(_hook),
          # 沒經過 137c 的全排在經過的前面(續一百七十二:137c 是 DIG 驅動,在 3400 .. 3700 ms 空窗裡掛上)
          "without_first": max(e.index for e, h in zip(MDI_ALL, _hook) if not h) < min(e.index for e, h in zip(MDI_ALL, _hook) if h)}
assert HOOKED == {"calls": 131, "via_137c": 111, "without_first": True}, HOOKED
MDI_EPS = [_ep_of_irq[id(q)] for q in MDI_IRQ]
assert [via_hook(e) for e in MDI_EPS] == [False, True, True]
# 對照:沒有被中斷的 MDI 驅動呼叫,iret 之後同一段接著 1fad 往下走(收中斷的地方就是這條)
_plain = [e for e in G_A[(rt(0x3F1A2), rt(0x3F1A2) + 2)] if not any(q.type == 0 for q in e.irqs)]
assert len(_plain) == 131 and all(any((r.m, r.cs, r.e0) == ("r", 0x0C5C, 0x1FAD) for r in e.runs) for e in _plain), len(_plain)

CONC = {
    "tool": f"lc171a 時間窗內 {VALID['lc171a']['runs']} 段指令逐段相接(只在 3400 .. 3700 ms 空窗斷開一次);"
            f"{VALID['lc171a']['era']['inside_game_run']} 筆 E / R / A 全落在遊戲段內;{VALID['lc171a']['irq']['irq_records']} 筆 I 全在段的邊界上。",
    "cf_branch": f"校準與 delay 的 int 21h 走同一條 9 段路徑,固定差的 6 條在 DOS/4GW int 21h 轉送(selector 0088)的 "
                 f"{BRANCH['test']} / {BRANCH['jcc']}:CF = 0 走 {len(CAL_ONLY)} 條、CF = 1 走 {len(DLY_ONLY)} 條。DOSBox-X 的 AH=2Ch 不動 CF,"
                 f"所以 CF 是遊戲留下的:校準兩個迴圈是 0(xor / 相等的 cmp),delay 迴圈是 cmp 0, dh(DH > 0 時 1),"
                 f"每次 delay 呼叫的第一次是 xor 之後的 0。lc171a:delay 第一次 {CF['lc171a']['cf0_first|long']} 次全走長路、"
                 f"迴圈內 {CF['lc171a']['cf1_loop|short']} 次全走短路,反例 0。",
    "rep": f"其餘起伏是同一條 rep movsw 被記了不只一次:lc171b 逐條窗校準 {REP['cal_3e00d']['episodes']} 次、delay 迴圈 "
           f"{REP['delay_loop']['episodes']} 次,併掉連續相同的 rep 指令後各只剩一種序列,長度差 6。"
           f"續一百六十五的 {S165_CAL[0]} .. {S165_CAL[1]} 與 {S165_DLY[0]} .. {S165_DLY[1]} = 481 / 475 加上 rep 多記。",
    "mdi_irq": f"MDI 驅動呼叫期間的硬體中斷 {len(MDI_IRQ)} 次全收在 0c5c:1fad(DOS/4GW 真實模式模擬中斷那段 int 66h 的下一條 pushf,"
               f"再下一條才 cli);前一段都是 SBPRO2.MDI(0f71,從位移 0 載入)結尾在 01b1 的 iret。所以是驅動 iret 把 IF 打開之後、"
               f"DOS/4GW 返回路徑的第一條指令收的。完整的 {HOOKED['calls']} 次驅動呼叫裡 {HOOKED['via_137c']} 次 int 66h 先進 137c:016a 的掛勾"
               f"(AX 不在自己的 0x300 .. 0x4ff 時經 ljmp cs:[0x36] 轉給驅動),其餘直接進驅動、而且都在前面。"
               f"(續一百七十二更正:原寫成「0x300 .. 0x4ff 時轉給驅動」是反的;137c 是 DIG 驅動 SB16.DIG,在 3400 .. 3700 ms 空窗裡掛上。)",
}
for _part, _key in (("6 條", "cf_branch"), ("259 次全走長路", "cf_branch"), ("8431 次全走短路", "cf_branch"),
                    ("481.49 .. 484.51", "rep"), ("475.44 .. 476.5", "rep"), ("長度差 6", "rep"), ("3 次全收在 0c5c:1fad", "mdi_irq"), ("01b1 的 iret", "mdi_irq")):
    assert _part in CONC[_key], (_part, CONC[_key])

OUTD = {
    "generator": rel(GEN_DIR / "ev_s171.py"),
    "exe_md5": MD5,
    "calllogs": {k: {"path": rel(RAW / f"{k}_CALLLOG.TXT"), "md5": v, "segs": SEGS[k]} for k, v in LOGS.items()},
    "validity": VALID,
    "static": {hex(a): t for a, t in STATIC.items()},
    "dosbox_2c": rel(DRV / "dosbox_dos_int21_2c.txt"),
    "int21": {"main_path": [f"{m} {c:04x}:{e:x}" for m, c, e in MAIN_PATH],
              "groups": {n: {"episodes": len(v), "main_path_share": MAIN[n][1]} for n, v in GROUPS.items()},
              "calibration_e3b_class": CAL_CLASS, "cf_table": CF, "branch": BRANCH,
              "cal_only": CAL_ONLY, "delay_only": DLY_ONLY},
    "rep": REP, "s165": {"calibration_per_int21": S165_CAL, "delay_per_int21": S165_DLY},
    "mdi_irq": {"count": len(MDI_IRQ), "where": "r 0c5c:1fad", "before": [f"{m} {c:04x}:{a:x}-{b:x}" for m, c, a, b in BEFORE],
                "chain": CHAIN, "hook_137c": HOOKED, "driver_bytes_checked": len(_drv), "uninterrupted_checked": len(_plain)},
    "conclusion": CONC,
}
OUT.write_text(json.dumps(OUTD, ensure_ascii=False, indent=1) + "\n", encoding="utf-8", newline="\n")
print("wrote", OUT.name, CF["lc171a"], REP)
