"""續一百七十三證據:evidence/driver_io_keys_s173_20261030.json(I/O 與按鍵紀錄的機制、AIL 驅動檔靜態清單對實機、
SB16.DIG 初始化的單一樣本 DMA、START 放開鍵的 IRQ 1 晚 5.55 ms)。

使用者 2026-10-30「請新建工具」→「請把還沒做的 進行處理」。工具:tools/dosbox/fd2_calllog_patch.py 加 FD2_CALLLOG_IO(O 寫 / N 讀)
與 FD2_CALLLOG_KBD(K:進鍵盤控制器佇列的位元組);tools/ail_driver_disasm.py(.DIG / .MDI 整檔反組譯)。
實機 lc173a(原版 FD2.EXE、WSL -d Ubuntu、開機 → 標題 → START → 16 秒;drivers_s173/lc173.py;預測在跑之前寫在 drivers_s173/pred173.txt)。
(A) 紀錄本身:逐段相接、每筆都帶 k / b / w、k 不減;H 帶 io= 與 kbd=1。
(B) P1 O / N 的 eip:逐條窗內每筆 O / N 的 n 對到一筆 S。CPU 的 in / out:S 的 eip 相同、碼位元組是那條 in / out(方向、立即埠、寬度都對);
    DOSBox-X callback 自己做的 I/O:S 是 callback 指令(FE 38),O / N 的 eip 是它之後 4 個位元組。
(C) P2 工具 A:SB16.DIG(137c)與 SBPRO2.MDI(0f71)實機每個 I/O 位置都在 ail_driver_disasm.py 的靜態清單內,方向與立即埠相同;
    S 帶的碼位元組與檔案同位置相同;對照:換成另一個驅動檔就對不上。DMA 設定那一串的實際埠 = 檔案表格在同一個 bx 的值。
(D) P3 單一樣本 DMA:SB16.DIG 初始化送 DSP 0x41 22050 Hz、0xb0(16 位元單次)模式 0x30(立體聲)長度 1,DMA 通道 5 計數暫存器 1;
    DOSBox-X 以 basecnt < 一個樣本的 DMA 計數(16 位元立體聲 2)判單一樣本 → dma_dac_mode。P 紀錄的 DMA_DAC_Event 從那一刻排到
    真正放音(0xc6、通道 1 自動重載計數 0x0fff)為止,之後 IRQ7 每 2048 / 22050 秒一次。
(E) P4 鍵盤:K 都是 Return(01c / 09c)。START 放開鍵的 IRQ 1 晚 5.55 ms:START 按下之後 SB16.DIG 送 DSP 0xd4(暫停中的 DMA 繼續),
    下一次計時器中斷進 DIG 服務 0x404c0,它先 0x382d6 → 0x3f0a8 cli,填緩衝 9.33 ms 才在 0x3f0bc sti;IRQ 0 先收(重入保護只送 EOI),
    IRQ 1 在 DOS/4GW 返回段 0080:06ca 收 —— 續一百七十二「START 那一下總撞上 DIG 型重入」的原因。
任何判準不符就 assert 失敗。
"""
from __future__ import annotations

import bisect
import collections
import hashlib
import itertools
import json
import re
import statistics

from _evpaths import EVIDENCE, GAME, GEN_DIR, ROOT, out_path, rel, require_inputs  # noqa: E402
require_inputs(__file__)
from _exeops import _EXE, insn  # noqa: E402  (_exeops 已把 tools/ 加進 sys.path)
import ail_driver_disasm as ad  # noqa: E402
import calllog_segments as cs  # noqa: E402

OUT = out_path("driver_io_keys_s173_20261030.json")
MD5 = "33464c81e6a364fd0660141139aa8e6e"
DRV = GEN_DIR / "drivers_s173"
RAW = ROOT / ".wsl_build" / "lc173_live"
DELTA = 0x19C000
GAME_CS = 0x170
LOG_MD5 = "3a8bb8b852d99b3f6307a64306408efb"
SEGS = "3000-3150,3150-3250:x,3250-24000"
IO_PORTS = "0-f,20-21,40-43,60,64,81-8f,a0-a1,c0-df,220-22f,388-38b"
WIN = (3150.0, 3250.0)                    # SEGS 裡逐條(:x)的那一段
DIG_CS, MDI_CS = 0x137C, 0x0F71           # 續一百七十二 (E):137c 是 SB16.DIG;續一百六十五:0f71 是 SBPRO2.MDI
S172 = json.loads((EVIDENCE / "calllog_slices_s172_20261030.json").read_text(encoding="utf-8"))

assert hashlib.md5(_EXE).hexdigest() == MD5
_drv_src = (DRV / "lc173.py").read_text(encoding="utf-8")
assert f'SEGS = {{"lc173a": "{SEGS}"}}' in _drv_src and f'IO = {{"lc173a": "{IO_PORTS}"}}' in _drv_src
assert 'DOS_TIME = {"lc173a": "12:00:54"}' in _drv_src and 'os.environ["FD2_HARNESS_CALLLOG_KBD"] = "1"' in _drv_src
_b = (RAW / "lc173a_CALLLOG.TXT").read_bytes()
assert hashlib.md5(_b).hexdigest() == LOG_MD5
TEXT = _b.decode("ascii").splitlines()
LOG = cs.parse(TEXT)
assert LOG.game_cs == GAME_CS
_mh = re.fullmatch(r"H fd2calllog .* icount=1 segs=" + re.escape(SEGS) + r" slices=1 picev=([0-9a-f]+) io=" + re.escape(IO_PORTS)
                   + r" kbd=1", TEXT[0])
assert _mh, TEXT[0]
PICEV_REF = int(_mh.group(1), 16)
DIG = (GAME / "SB16.DIG").read_bytes()
MDI = (GAME / "SBPRO2.MDI").read_bytes()


def rt(a: int) -> int:
    return a + DELTA


# ================= (A) 紀錄本身 =================
def validity() -> dict:
    """逐段相接、每筆 G / S / I / O / N / K 都帶 k / b / w、k 依檔案次序不減。"""
    seq = []
    for kind, i in LOG.order:
        if kind == "I":
            seq.append(LOG.irqs[i].sl)
        else:
            r = LOG.runs[i]
            seq.extend(r.sls if r.sls is not None else [r.sl])
    return {"runs": len(LOG.runs), "irqs": len(LOG.irqs), "ios": len(LOG.ios), "keys": len(LOG.keys), "gaps": LOG.gaps,
            "every_record_has_slices": all(s is not None for s in seq + [x.sl for x in LOG.ios] + [y.sl for y in LOG.keys]),
            "k_nondecreasing": all(a[0] <= b[0] for a, b in zip(seq, seq[1:])), "k_last": seq[-1][0]}


VALID = validity()
# k_last = G / S / I 紀錄(validity 的 seq)裡最大的 k(k 不減,最後一筆就是最大;E / R / A / O / N 在 SEGS 窗外還有,不算)
assert VALID["k_last"] == max(int(m.group(1)) for ln in TEXT if ln[:2] in ("G ", "S ", "I ")
                              for m in [re.search(r" k=(\d+) ", ln)] if m), VALID
assert VALID["gaps"] == [] and VALID["every_record_has_slices"] and VALID["k_nondecreasing"], VALID
_ports = [(int(p.split("-")[0], 16), int(p.split("-")[-1], 16)) for p in IO_PORTS.split(",")]
assert all(any(lo <= x.port <= hi for lo, hi in _ports) for x in LOG.ios)    # 只記設定的埠

# ================= (B) P1:O / N 的 eip 是哪一條 =================
_srun: dict[int, tuple[str, int, int]] = {}
for _r in LOG.runs:
    if _r.eips is not None:
        for _i, _e in enumerate(_r.eips):
            _srun[_r.n_start + 1 + _i] = (_r.m, _r.cs, _e)
_IN, _OUT = {0xE4, 0xE5, 0xEC, 0xED}, {0xE6, 0xE7, 0xEE, 0xEF}


def io_insn(code: bytes) -> tuple[str, int | None, int] | None:
    """碼位元組開頭若是 in / out(可有 0x66 前綴),回傳 (方向, 立即埠或 None, 寬度位元組數);其他 None。"""
    pre = code[0] == 0x66
    op = code[1] if pre else code[0]
    if op not in _IN | _OUT:
        return None
    imm = (code[2] if pre else code[1]) if op in (0xE4, 0xE5, 0xE6, 0xE7) else None
    width = 1 if op in (0xE4, 0xE6, 0xEC, 0xEE) else (2 if pre else 4)
    return ("N" if op in _IN else "O"), imm, width


def p1() -> dict:
    inwin = [x for x in LOG.ios if WIN[0] <= x.t < WIN[1]]
    cpu, cb, odd = collections.Counter(), collections.Counter(), []
    for x in inwin:
        s = _srun.get(x.n)
        assert s is not None, x                                  # 窗內每筆 O / N 的 n 都對到一筆 S
        code = LOG.code.get(s)
        if s == (x.m, x.cs, x.eip) and code is not None:
            dec = io_insn(code)
            if dec is not None and dec[0] == x.op and dec[1] in (None, x.port) and dec[2] == x.width:
                cpu[f"{x.m} {x.cs:04x}"] += 1
                continue
        elif s[:2] == (x.m, x.cs) and code is not None and code[:2] == b"\xfe\x38" and x.eip == s[2] + 4:
            cb[f"{x.op} {x.port:04x} {x.m} {x.cs:04x}:{x.eip:x} S {s[2]:x}"] += 1
            continue
        odd.append([x.op, x.port, x.m, x.cs, x.eip, list(s)])
    return {"in_window": len(inwin), "cpu_in_out_same_eip": sum(cpu.values()), "cpu_by_segment": dict(sorted(cpu.items())),
            "callback_after_fe38": dict(cb), "unexplained": odd}


P1 = p1()
assert P1["unexplained"] == [] and P1["cpu_in_out_same_eip"] > 100, P1
assert P1["cpu_in_out_same_eip"] + sum(P1["callback_after_fe38"].values()) == P1["in_window"]

# ================= (C) P2:工具 A 的靜態清單對實機 =================
DRIVERS = {"SB16.DIG": (DIG_CS, DIG), "SBPRO2.MDI": (MDI_CS, MDI)}
STATIC = {}
for _name, (_seg, _bytes) in DRIVERS.items():
    _prog, _tab, _st = ad.explore(_bytes)
    STATIC[_name] = {s.addr: s for s in ad.io_sites(_prog, _st)}


def p2_one(name: str, against: str) -> dict:
    """name 那個段的實機 O / N(eip、方向、立即埠)對 against 那份檔的靜態清單;另比 S 帶的碼位元組。"""
    seg = DRIVERS[name][0]
    static, fb = STATIC[against], DRIVERS[against][1]
    live = [x for x in LOG.ios if x.cs == seg and x.m == "r"]
    by = collections.Counter((x.eip, "out" if x.op == "O" else "in") for x in live)
    imm = sorted({(x.eip, x.port) for x in live if x.eip in static and isinstance(static[x.eip].port, int)})
    code = [(e, c) for (m, c_s, e), c in LOG.code.items() if m == "r" and c_s == seg and c is not None]
    return {"live": len(live), "eips": len(by), "in_static": sum(1 for e, _o in by if e in static),
            "same_direction": sum(1 for e, o in by if e in static and static[e].op == o),
            "imm_port_checked": len(imm), "imm_port_same": sum(1 for e, p in imm if static[e].port == p),
            "static_sites": len(static), "static_never_live": len([a for a in static if a not in {e for e, _o in by}]),
            "code_bytes": len(code),
            # 檔尾不足 16 位元組時只比檔內的部分;eip 超出檔案算不符
            "code_bytes_same": sum(1 for e, c in code if e < len(fb) and fb[e:e + 16] == c[:len(fb[e:e + 16])])}


P2 = {n: p2_one(n, n) for n in DRIVERS}
for _n, _v in P2.items():
    assert _v["eips"] == _v["in_static"] == _v["same_direction"] and _v["imm_port_same"] == _v["imm_port_checked"], (_n, _v)
    assert _v["code_bytes"] > 0 and _v["code_bytes_same"] == _v["code_bytes"], (_n, _v)
assert (P2["SB16.DIG"]["eips"], P2["SBPRO2.MDI"]["eips"]) == (47, 9), P2
# 對照:另一個驅動檔的清單與位元組(同一套比法,分母相同)
P2_CONTROL = {"SBPRO2.MDI_vs_SB16.DIG": p2_one("SBPRO2.MDI", "SB16.DIG"), "SB16.DIG_vs_SBPRO2.MDI": p2_one("SB16.DIG", "SBPRO2.MDI")}
for _n, _v in P2_CONTROL.items():
    assert _v["same_direction"] < _v["eips"] // 2 and _v["code_bytes_same"] < _v["code_bytes"] // 2, (_n, _v)

# DMA 設定:每一串的實際埠 = 檔案表格[表 + bx],bx 唯一
_rx_tab = re.compile(r"byte\[bx\+0x([0-9a-f]+)\]")
DMA_EIPS = sorted(a for a, s in STATIC["SB16.DIG"].items() if isinstance(s.port, str) and _rx_tab.fullmatch(s.port))
_dw = [x for x in LOG.ios if x.cs == DIG_CS and x.m == "r" and x.op == "O" and x.eip in DMA_EIPS]
_groups: list[list[cs.Io]] = []
for x in _dw:
    if _groups and x.t - _groups[-1][-1].t < 1.0:
        _groups[-1].append(x)
    else:
        _groups.append([x])


def dma_bxs(g: list[cs.Io]) -> list[int]:
    """這一串每筆的實際埠都等於 表格[表 + bx] 的 bx(8 位元通道 0 .. 3、16 位元 5 .. 7;4 那格是 0xff)。"""
    tabs = [int(_rx_tab.fullmatch(STATIC["SB16.DIG"][x.eip].port).group(1), 16) for x in g]
    return [bx for bx in range(8) if all(DIG[t + bx] == x.port for t, x in zip(tabs, g))]


def dma_group(g: list[cs.Io]) -> dict:
    """完整的一串(有計數):bx 唯一,通道 = bx。"""
    bxs = dma_bxs(g)
    assert len(bxs) == 1, (bxs, [(hex(x.eip), hex(x.port)) for x in g])
    cnt = [x.value for x in g if x.eip in (0x285, 0x288)]
    mode = [x.value for x in g if x.eip == 0x29D]
    assert len(cnt) == 2 and len(mode) == 1, g
    return {"t_ms": round(min(x.t for x in g), ndigits=4), "bx": bxs[0], "channel": bxs[0], "writes": [[hex(x.eip), x.port, x.value] for x in g],
            "count_reg": cnt[0] | (cnt[1] << 8), "mode": mode[0]}


_prog_groups = [g for g in _groups if any(x.eip == 0x285 for x in g)]
DMA = [dma_group(g) for g in _prog_groups]
# 只有遮罩的串(停 / 開通道):埠也要是表格裡某個 bx 的值
DMA_MASK_ONLY = {"groups": len(_groups) - len(_prog_groups),
                 "all_match_table": all(dma_bxs(g) for g in _groups if g not in _prog_groups)}
assert len(DMA) == 2 and DMA_MASK_ONLY["all_match_table"], (DMA, DMA_MASK_ONLY)

# ================= (D) P3:單一樣本 DMA =================
SRC = (DRV / "dosbox_src_s173.txt").read_text(encoding="utf-8")
SRC172 = (GEN_DIR / "drivers_s172" / "dosbox_src_s172.txt").read_text(encoding="utf-8")
for _s in ("dma.chan->basecnt < ((new_mode==DSP_DMA_16_ALIASED?2:1)*((stereo || mixer.sbpro_stereo)?2:1))/*size of one sample in DMA counts*/)",
           "if (dsp.force_goldplay || (goldplay && freq > 0 && single_sample_dma))",
           "DSP_PrepareDMA_New((dsp.cmd & 0x10) ? DSP_DMA_16 : DSP_DMA_8,", "1u+(unsigned int)dsp.in.data[1]+((unsigned int)dsp.in.data[2] << 8u),",
           "(dsp.in.data[0] & 0x20) > 0", "chan->basecnt=(uint16_t)((chan->basecnt&0xff00)|val);",
           "PIC_AddEvent(DMA_DAC_Event,1000.0 / sb[ci].dma_dac_srcrate,(ci << CARD_INDEX_BIT));",
           "case 0xd4:  /* Continue DMA 8-bit*/", "PIC_RemoveEvents(DMA_DAC_Event);"):
    assert _s in SRC, _s
assert "Pbool = secprop->Add_bool(\"goldplay\",Property::Changeable::WhenIdle,true);" in SRC172
_NARGS = {0x41: 2, 0x42: 2, 0xE1: 0, 0xD0: 0, 0xD4: 0, 0xD1: 0, 0xD3: 0, 0xD5: 0, 0xD6: 0, 0xDA: 0, 0xD9: 0}


def dsp_cmds() -> list[dict]:
    """SB16.DIG 寫 DSP(22c)的位元組依命令切開;0xb0 .. 0xcf 帶 3 個參數。"""
    w = [x for x in LOG.ios if x.op == "O" and x.port == 0x22C and x.cs == DIG_CS and x.m == "r"]
    out, i = [], 0
    while i < len(w):
        c = w[i].value
        n = 3 if 0xB0 <= c <= 0xCF else _NARGS.get(c)
        assert n is not None, hex(c)
        args = [x.value for x in w[i + 1:i + 1 + n]]
        assert len(args) == n and all(x.t - w[i].t < 1 for x in w[i + 1:i + 1 + n]), (hex(c), i)
        out.append({"t_ms": round(w[i].t, 4), "cmd": c, "args": args})
        i += 1 + n
    assert sum(1 + len(d["args"]) for d in out) == len(w), (len(w), out)
    return out


DSP = dsp_cmds()
_rate = [d for d in DSP if d["cmd"] == 0x41]
_blk = [d for d in DSP if 0xB0 <= d["cmd"] <= 0xCF]
assert len(_blk) == 2 and len(DMA) >= 2, (_blk, DMA)
INIT, PLAY = _blk


def blk(d: dict) -> dict:
    mode, lo, hi = d["args"]
    return {"t_ms": d["t_ms"], "cmd": hex(d["cmd"]), "bits": 16 if d["cmd"] & 0x10 else 8, "autoinit": bool(d["cmd"] & 4),
            "stereo": bool(mode & 0x20), "signed": bool(mode & 0x10), "length": 1 + lo + (hi << 8)}


BLK = {"init": blk(INIT), "play": blk(PLAY)}
_dma_init = max((g for g in DMA if g["t_ms"] <= INIT["t_ms"]), key=lambda g: g["t_ms"])
_dma_play = max((g for g in DMA if g["t_ms"] <= PLAY["t_ms"]), key=lambda g: g["t_ms"])
RATE = {d["t_ms"]: (d["args"][0] << 8) | d["args"][1] for d in _rate}
assert set(RATE.values()) == {22050}, RATE


def one_sample(b: dict, channel: int) -> int:
    """DOSBox-X:一個樣本的 DMA 計數 = (16 位元走 8 位元通道 aliased ? 2 : 1) × (立體聲 ? 2 : 1)。"""
    aliased = b["bits"] == 16 and channel < 4
    return (2 if aliased else 1) * (2 if b["stereo"] else 1)


SINGLE = {"init": {"channel": _dma_init["channel"], "basecnt": _dma_init["count_reg"], "one_sample": one_sample(BLK["init"], _dma_init["channel"])},
          "play": {"channel": _dma_play["channel"], "basecnt": _dma_play["count_reg"], "one_sample": one_sample(BLK["play"], _dma_play["channel"])}}
for _k, _v in SINGLE.items():
    _v["single_sample_dma"] = _v["basecnt"] < _v["one_sample"]
assert BLK["play"]["autoinit"] and SINGLE["play"]["basecnt"] + 1 == 2 * BLK["play"]["length"] * SINGLE["play"]["one_sample"], (BLK, SINGLE)
assert SINGLE["init"]["single_sample_dma"] and not SINGLE["play"]["single_sample_dma"], SINGLE
assert (BLK["init"]["bits"], BLK["init"]["stereo"], BLK["init"]["length"], BLK["init"]["autoinit"]) == (16, True, 1, False), BLK
assert (BLK["play"]["bits"], BLK["play"]["stereo"], BLK["play"]["autoinit"]) == (8, False, True), BLK
assert SINGLE["play"]["basecnt"] + 1 == 2 * BLK["play"]["length"], (SINGLE, BLK)     # 自動重載:緩衝 = 兩個半塊
# 預測 P3 的句子寫「(計數 + 1)小於一個樣本」:實際計數 + 1 = 2 恰好等於一個 16 位元立體聲樣本;DOSBox-X 比的是 basecnt(暫存器值)
P3_PRED_WORDING = {"count_plus_1": SINGLE["init"]["basecnt"] + 1, "one_sample": SINGLE["init"]["one_sample"],
                   "wording_holds": SINGLE["init"]["basecnt"] + 1 < SINGLE["init"]["one_sample"],
                   "code_condition_holds": SINGLE["init"]["single_sample_dma"]}
assert P3_PRED_WORDING["wording_holds"] is False and P3_PRED_WORDING["code_condition_holds"] is True

# P 紀錄:DMA_DAC_Event 從 0xb0 那一刻到 0xc6 那一刻
NM_LINES = (DRV / "nm_handlers_s173.txt").read_text(encoding="utf-8").splitlines()
assert NM_LINES[0].startswith("# nm ~/fd2-dosbox-calllog3/dosbox-x/src/dosbox-x sha256 12294f935c52")
NM = {int(a, 16): s for a, _t, s in (ln.split() for ln in NM_LINES[1:])}
BIAS = PICEV_REF - next(a for a, s in NM.items() if s == "_Z19fd2calllog_piceventPv")
PREC: dict[int, dict[str, int]] = {}
for ln in TEXT:
    if ln.startswith("P "):
        f = ln.split()
        d = {}
        for kv in f[2:]:
            a, c = kv.split("=")
            sym = NM.get(int(a, 16) - BIAS)
            assert sym is not None, (f[1], a)
            d[re.fullmatch(r"_Z(?:L)?\d+(\w+?)(?:m|Pv)", sym).group(1)] = int(c)
        PREC[int(f[1])] = d
_dac = sorted(b for b, d in PREC.items() if d.get("DMA_DAC_Event"))
DAC = {"first_bucket": _dac[0], "first_count": PREC[_dac[0]]["DMA_DAC_Event"], "last_bucket": _dac[-1],
       "last_count": PREC[_dac[-1]]["DMA_DAC_Event"], "contiguous": _dac == list(range(_dac[0], _dac[-1] + 100, 100)),
       "middle_counts": sorted({PREC[b]["DMA_DAC_Event"] for b in _dac[1:-1]})}
DAC["start_ms_est"] = round(DAC["first_bucket"] + 100 - DAC["first_count"] / 22.05, ndigits=2)
DAC["stop_ms_est"] = round(DAC["last_bucket"] + DAC["last_count"] / 22.05, ndigits=2)
assert DAC["contiguous"] and DAC["middle_counts"] == [2205], DAC
# 開始 = 0xb0 那串送完(長度高位元組),結束 = 0xc6 那串;差在一個樣本週期(1 / 22.05 ms)內
_b0_end = max(x.t for x in LOG.ios if x.op == "O" and x.port == 0x22C and x.t <= INIT["t_ms"] + 0.1)
_c6_end = max(x.t for x in LOG.ios if x.op == "O" and x.port == 0x22C and x.t <= PLAY["t_ms"] + 0.1)
DAC["b0_end_ms"], DAC["c6_end_ms"] = round(_b0_end, 4), round(_c6_end, 4)
assert abs(DAC["start_ms_est"] - _b0_end) < 1 / 22.05 + 0.01 and abs(DAC["stop_ms_est"] - _c6_end) < 1 / 22.05 + 0.01, DAC
_irq7 = [q for q in LOG.irqs if q.num == 0x0F and q.type == 0]
IRQ7 = {"first": [_irq7[0].t, f"{_irq7[0].m} {_irq7[0].cs:04x}:{_irq7[0].eip:x}"], "second_ms": _irq7[1].t,
        "period_ms_median": round(statistics.median(b.t - a.t for a, b in zip(_irq7[1:], _irq7[2:])), 3), "count": len(_irq7)}
assert IRQ7["first"][0] < IRQ7["second_ms"] and not any(IRQ7["first"][0] < q.t < IRQ7["second_ms"] for q in _irq7), IRQ7
# 一個樣本的 DMA 傳完就 IRQ7(初始化測 IRQ);真正放音之後每 2048 / 22050 秒一次
assert IRQ7["first"][1] == "r 137c:31a" and 0 < IRQ7["first"][0] - _b0_end < 0.1, IRQ7
assert IRQ7["second_ms"] > _c6_end and abs(IRQ7["period_ms_median"] - BLK["play"]["length"] / 22.05) < 0.3, IRQ7
# 續一百七十二 lc172b 的同一現象(時刻不同,型相同)
assert S172["slices"]["dma_dac"]["middle_counts"] == [2205] and S172["slices"]["irq7"]["first"][1] == "r 137c:31a"

# ================= (E) P4:鍵盤 =================
KEYS = [{"data": hex(y.data), "used": y.used, "t_ms": round(y.t, 4)} for y in LOG.keys]
assert [y.data for y in LOG.keys] == [0x1C, 0x9C] * 7 and all(y.used == 0 for y in LOG.keys), KEYS
assert "KEYDELAY=0.300f;" in SRC and "PIC_AddEvent(KEYBOARD_TransferBuffer,KEYDELAY);" in SRC and "PIC_ActivateIRQ(1);" in SRC
HW = [q for q in LOG.irqs if q.type == 0]
HW_N = [q.n for q in HW]
LOG_T0 = float(SEGS.split("-")[0])


def key_rows() -> list[dict]:
    rows = []
    for y in LOG.keys:
        if y.t < LOG_T0:
            continue                                             # 紀錄窗之前:沒有 I 紀錄
        j = bisect.bisect_left(HW_N, y.n)
        q9 = next(q for q in HW[j:] if q.num == 0x09)
        between = [q for q in HW[j:] if q.n < q9.n]
        rows.append({"key": hex(y.data), "t_ms": round(y.t, 4), "irq1_ms": q9.t, "delay_ms": round(q9.t - y.t, 4),
                     "at": f"{q9.m} {q9.cs:04x}:{q9.eip:x}", "irqs_before": [[hex(q.num), q.t, f"{q.m} {q.cs:04x}:{q.eip:x}"] for q in between]})
    return rows


KROWS = key_rows()
assert all(r["delay_ms"] >= 0.3 for r in KROWS), KROWS                       # 不早於 KEYDELAY
NORMAL = [r for r in KROWS if r["delay_ms"] < 0.35]                      # KEYDELAY 0.3 ms 加到下一條指令
LATE = [r for r in KROWS if r not in NORMAL]
# PICEV:每個 K 的 KEYBOARD_TransferBuffer 都在 K + 0.3 ms 那一格(放開鍵也是;晚的是 CPU 收 IRQ 1)
_tb = collections.Counter(int((y.t + 0.3) // 100) * 100 for y in LOG.keys if y.t >= LOG_T0)
TB = {b: (PREC.get(b, {}).get("KEYBOARD_TransferBuffer", 0), n) for b, n in sorted(_tb.items())}
assert all(a == n for a, n in TB.values()), TB
START = KROWS[-1]
assert START["key"] == "0x9c" and START["delay_ms"] > 5, START

# START 放開鍵:這一串依檔案次序逐筆核對
REENTRY, ISR, SERVE = rt(0x3EBAD), rt(0x3EA8E), rt(0x404C0)
q9i = next(i for i, q in enumerate(HW) if q.t == START["irq1_ms"])
qa, qb = HW[q9i - 1], HW[q9i - 2]                                  # qa:sti 後收的 IRQ 0;qb:進 DIG 服務的那一次
k_start = LOG.keys[-1]
assert (qa.num, qa.m, qa.cs, qa.eip) == (0x08, "P", GAME_CS, rt(0x3F0BE)) and qb.num == 0x08 and qb.t < k_start.t < qa.t, (qa, qb)
assert qa.t - qb.t > 5.0                                          # 5 ms 基底的計時器中斷到期了卻沒收
_long = [r for r in LOG.runs if qb.n < r.n_end <= qa.n]
_lr = max(_long, key=lambda r: r.count)
assert (_lr.m, _lr.cs, _lr.e0, _lr.e1, _lr.n_end) == ("P", GAME_CS, ISR, rt(0x3F0BD), qa.n) and _lr.n_start < k_start.n, _lr
_rx_e = re.compile(r"^E (\d+) ([0-9a-f]{8}) ([0-9a-f]{8}) ")
_li = next(i for i, ln in enumerate(TEXT) if ln.startswith("I 08 ") and f" n={qb.n} " in ln)
_lj = next(i for i in range(_li, len(TEXT)) if TEXT[i].startswith("I 08 ") and f" n={qa.n} " in TEXT[i])
_lk = next(i for i in range(_lj, len(TEXT)) if TEXT[i].startswith("I 09 "))
SEQ_A = [" ".join(ln.split()[:4]) for ln in TEXT[_li + 1:_lj] if ln[:2] in ("E ", "O ", "N ", "I ", "K ")]
SEQ_B = [" ".join(ln.split()[:4]) for ln in TEXT[_lj + 1:_lk] if ln[:2] in ("E ", "O ", "N ", "I ", "K ")]
for _sq, _ra in ((SEQ_A, range(_li, _lj)), (SEQ_B, range(_lj, _lk))):
    _want = [ln for ln in TEXT[_ra.start:_ra.stop][1:] if re.match(r"[EONIK] ", ln)]
    assert _sq and len(_sq) == len(_want) and all(x.split() == ln.split()[:len(x.split())] and len(x.split()) == len(ln.split()[:4])
                                                  for x, ln in zip(_sq, _want)), (_sq, _want[:3])
_ea = [_rx_e.match(ln) for ln in TEXT[_li + 1:_lj] if ln.startswith("E ")]
_eb = [_rx_e.match(ln) for ln in TEXT[_lj + 1:_lk] if ln.startswith("E ")]
assert [(int(m.group(2), 16), int(m.group(3), 16)) for m in _ea][:2] == [(ISR, 0xED6), (SERVE, rt(0x3EB42))], SEQ_A
assert [int(m.group(2), 16) for m in _eb] == [ISR, REENTRY], SEQ_B
_eoi_a = [x for x in LOG.ios if qb.n < x.n < qa.n and x.op == "O" and x.port == 0x20]
_eoi_b = [x for x in LOG.ios if qa.n < x.n < HW[q9i].n and x.op == "O" and x.port == 0x20]
assert [(x.m, x.cs, x.eip, x.value) for x in _eoi_a if x.cs == GAME_CS] == [("P", GAME_CS, rt(0x3EB13), 0x20)], _eoi_a
assert [(x.m, x.cs, x.eip, x.value) for x in _eoi_b if x.cs == GAME_CS] == [("P", GAME_CS, rt(0x3EBB0), 0x20)], _eoi_b
assert not [y for y in LOG.keys if qb.n < y.n < qa.n and y is not k_start]
assert START["at"] == "p 0080:6ca" and [q[0] for q in START["irqs_before"]] == ["0x8"], START
# 靜態:ISR 先 EOI 再 sti 才叫服務;服務 0x404c0 先 0x382d6 → 0x3f0a8 cli,結尾 0x382db → 0x3f0ac 依存下的 IF 決定 sti
STATIC_CHAIN = {
    0x3EA8E: "cmp dword ptr cs:[0x2be6], 0", 0x3EA96: "ja 0x3ebad", 0x3EB13: "out 0x20, al", 0x3EB15: "sti ",
    0x3EB3C: "call dword ptr [edi + 0x2a54]", 0x404EA: "call 0x382d6", 0x382D6: "jmp 0x3f0a8", 0x3F0A8: "pushfd ",
    0x3F0A9: "pop eax", 0x3F0AA: "cli ", 0x3F0AB: "ret ", 0x40534: "call 0x382db", 0x382E0: "call 0x3f0ac",
    0x3F0B5: "test byte ptr [ebp + 5], 2", 0x3F0B9: "cli ", 0x3F0BA: "je 0x3f0bd", 0x3F0BC: "sti ", 0x3F0BD: "pop ebp",
    0x3F0BE: "popfd ", 0x3EBB0: "out 0x20, al", 0x3EBB3: "iretd ",
}
for _a, _t in STATIC_CHAIN.items():
    assert insn(_a) == _t, (hex(_a), insn(_a), _t)
assert "// FORCE another instruction decode before allowing interrupt processing" in SRC    # sti 之後多做一條(pop ebp)才收
# 觸發:START 按下的 IRQ 1 之後、進服務之前,SB16.DIG 送 DSP 0xd4(暫停中的 8 位元 DMA 繼續);前一個 DSP 命令是 0xd0(暫停)
_make_irq = max((r for r in KROWS if r["key"] == "0x1c" and r["t_ms"] < START["t_ms"]), key=lambda r: r["t_ms"])["irq1_ms"]
_d4 = [d for d in DSP if d["cmd"] == 0xD4 and _make_irq < d["t_ms"] < qb.t]
assert len(_d4) == 1, _d4
_prev = DSP[DSP.index(_d4[0]) - 1]
assert _prev["cmd"] == 0xD0, _prev
TRIGGER = {"make_irq1_ms": _make_irq, "dsp_d4_ms": _d4[0]["t_ms"], "previous_dsp": [hex(_prev["cmd"]), _prev["t_ms"]],
           "serve_irq0_ms": qb.t, "serve_from": f"{qb.m} {qb.cs:04x}:{qb.eip:x}", "sti_irq0_ms": qa.t,
           "if_off_ms": round(qa.t - qb.t, ndigits=3), "game_insns": _lr.count, "break_k_ms": round(k_start.t, 4), "irq1_ms": START["irq1_ms"],
           "seq_serve": SEQ_A, "seq_after_sti": SEQ_B}
# 一般化:收在 0x3f0be 的 I 紀錄都是 IRQ 0(服務關中斷超過一個計時器週期);每次 DSP 0xd4 之後都接一個
AT_STI = [q for q in HW if (q.m, q.cs, q.eip) == ("P", GAME_CS, rt(0x3F0BE))]
_win = [(HW[HW.index(q) - 1].t, q.t) for q in AT_STI]
STI_WIN = {"count": len(AT_STI), "nums": sorted({q.num for q in AT_STI}), "ms_min": round(min(b - a for a, b in _win), 3),
           "ms_max": round(max(b - a for a, b in _win), ndigits=3)}
_d4all = [d["t_ms"] for d in DSP if d["cmd"] == 0xD4]
STI_WIN["d4_followed"] = [any(0 < a - t < 5.5 for a, _b in _win) for t in _d4all]
assert STI_WIN["nums"] == [0x08] and all(STI_WIN["d4_followed"]) and len(_d4all) == 2, STI_WIN
# 其他晚收的按鍵:收的位置也是長空窗結束的地方(關中斷的段落結束)
_gap_end = collections.Counter(f"{b.m} {b.cs:04x}:{b.eip:x}" for a, b in itertools.pairwise(HW) if b.t - a.t > 5.5 and a.t > LOG_T0)
OTHER_LATE = [{**r, "site_ends_long_gaps": _gap_end[r["at"]] + sum(_gap_end[q[2]] for q in r["irqs_before"])}
              for r in LATE if r is not START]
assert all(o["site_ends_long_gaps"] > 0 for o in OTHER_LATE), OTHER_LATE


def late_run(r: dict) -> dict:
    """K 到它的 I 09 之間最長的那段 run:哪一段、多少條、是不是在 K 之前就開始(那段關著中斷)。"""
    y = next(k for k in LOG.keys if round(k.t, 4) == r["t_ms"])
    q9 = next(q for q in HW if q.t == r["irq1_ms"])
    lr = max((x for x in LOG.runs if y.n < x.n_end <= q9.n), key=lambda x: x.count)
    return {"m": lr.m, "cs": lr.cs, "e0": lr.e0, "e1": lr.e1, "count": lr.count, "n_end": lr.n_end,
            "started_before_key": lr.n_start < y.n, "irq1_eip": q9.eip}


LATE_RUNS = {o["t_ms"]: late_run(o) for o in OTHER_LATE}
_l1, _l2 = (LATE_RUNS[o["t_ms"]] for o in OTHER_LATE)
# 3849:K 之前已進 SBPRO2.MDI 分派段(檔頭 +0x34),一段 7000 多條沒收中斷,回來才收 IRQ 1(續一百六十五「MDI 期間擋 IRQ 的是驅動」)
assert (_l1["m"], _l1["cs"], _l1["e0"]) == ("r", MDI_CS, ad.parse_header(MDI)[1]) and _l1["started_before_key"] and _l1["count"] > 5000, _l1
assert not OTHER_LATE[0]["irqs_before"]
# 9262:DOS/4GW 0070 一段 1000 多條沒收中斷,結束在 IRQ 0;遊戲 ISR 0x3eb15 sti 再多做一條(0x3eb16)才收 IRQ 1(0x3eb1d)
assert (_l2["m"], _l2["cs"]) == ("p", 0x70) and _l2["started_before_key"] and _l2["count"] > 1000, _l2
assert [q[0] for q in OTHER_LATE[1]["irqs_before"]] == ["0x8"] and _l2["n_end"] == next(q.n for q in HW if q.t == OTHER_LATE[1]["irqs_before"][0][1])
assert _l2["irq1_eip"] == rt(0x3EB1D) and insn(0x3EB15) == "sti " and insn(0x3EB16) == "cmp dword ptr [0x2bea], 0" and insn(0x3EB1D) == "jg 0x3eb4e"

# 重入之後的非遊戲指令數(同 ev_s172 (F)):602 = DIG 型 69 + 鍵盤 533,就是這一次;MDI 375 仍沒出現
_rx_era = re.compile(r"^([ERA]) (\d+) ([0-9a-f]{8}) .*? i=(\d+) n=(\d+) t=([0-9.]+)")
_recs = [(m.group(1), int(m.group(3), 16), int(m.group(4)), int(m.group(5)), float(m.group(6)))
         for m in (_rx_era.match(ln) for ln in TEXT if ln[:2] in ("E ", "R ", "A ")) if m]
POST = collections.Counter()
POST_ODD = []
for _p, _q in zip(_recs, _recs[1:]):
    if _p[0] == "E" and _p[1] == REENTRY:
        _v = (_q[3] - _p[3]) - (_q[2] - _p[2])
        POST.update([_v])
        if _v not in (69, 70, 302, 303):
            POST_ODD.append({"t": _p[4], "post": _v})
assert [o["post"] for o in POST_ODD] == [602] and abs(POST_ODD[0]["t"] - qa.t) < 0.1, POST_ODD
assert 375 not in POST

CONC = {
    "p1_eip": f"窗內 {P1['in_window']} 筆 O / N 的 n 都對到一筆 S:{P1['cpu_in_out_same_eip']} 筆是 CPU 的 in / out,eip 是那條指令本身"
              f"(碼位元組的方向、立即埠、寬度都對);{sum(P1['callback_after_fe38'].values())} 筆是 DOSBox-X callback(FE 38)自己做的 I/O,eip 在 callback 指令之後 4 個位元組。",
    "p2_static": f"SB16.DIG 實機 {P2['SB16.DIG']['eips']} 個、SBPRO2.MDI {P2['SBPRO2.MDI']['eips']} 個 I/O 位置全在工具 A 的靜態清單內,方向與立即埠相同,"
                 f"S 帶的碼位元組與檔案同位置相同;對照(換成另一個驅動檔)方向對上 {P2_CONTROL['SBPRO2.MDI_vs_SB16.DIG']['same_direction']} / {P2_CONTROL['SBPRO2.MDI_vs_SB16.DIG']['eips']}。"
                 f"DMA 設定兩串的埠 = 檔案表格在 bx {DMA[0]['bx']} / {DMA[-1]['bx']} 的值。",
    "p3_single": f"SB16.DIG 初始化({BLK['init']['t_ms']} ms)送 0x41 22050 Hz、{BLK['init']['cmd']} 16 位元立體聲長度 {BLK['init']['length']},"
                 f"DMA 通道 {SINGLE['init']['channel']} 計數暫存器 {SINGLE['init']['basecnt']} < 一個樣本 {SINGLE['init']['one_sample']} → 單一樣本 DMA;"
                 f"DMA_DAC_Event 推回 {DAC['start_ms_est']} .. {DAC['stop_ms_est']} ms,對上 0xb0 送完 {DAC['b0_end_ms']}、0xc6 送完 {DAC['c6_end_ms']}。"
                 f"真正放音 {BLK['play']['cmd']} 8 位元自動重載長度 {BLK['play']['length']}、通道 {SINGLE['play']['channel']} 計數 {SINGLE['play']['basecnt']},"
                 f"IRQ7 每 {IRQ7['period_ms_median']} ms。預測句的「計數 + 1 小於一個樣本」差一({P3_PRED_WORDING['count_plus_1']} = {P3_PRED_WORDING['one_sample']}),"
                 f"DOSBox-X 比的是暫存器值。",
    "p4_start": f"START 放開鍵 {TRIGGER['break_k_ms']} ms 進佇列、IRQ 1 {TRIGGER['irq1_ms']} ms 才收(晚 {START['delay_ms']} ms)。"
                f"按下的 IRQ 1 之後 SB16.DIG 送 DSP 0xd4({TRIGGER['dsp_d4_ms']} ms,前一個是 0xd0),{TRIGGER['serve_irq0_ms']} ms 的計時器中斷進 DIG 服務 0x404c0,"
                f"ISR 在 0x3eb15 sti、服務一開頭 0x3f0aa cli;從進 ISR 到 0x3f0bc sti 共 {TRIGGER['if_off_ms']} ms({TRIGGER['game_insns']} 條遊戲指令)"
                f"沒收任何中斷,sti 之後 IRQ 0 先收(重入只送 EOI)、"
                f"IRQ 1 在 0080:06ca 收;續一百七十二的 602 就是這一次。收在 0x3f0be 的 {STI_WIN['count']} 筆全是 IRQ 0,兩次 0xd4 之後都有。MDI 375 仍沒出現。"
                f"另兩次晚收:{OTHER_LATE[0]['t_ms']} ms 按下時正在 SBPRO2.MDI 分派段(一段 {_l1['count']} 條)、{OTHER_LATE[1]['t_ms']} ms 按下時正在 DOS/4GW 0070(一段 {_l2['count']} 條,"
                f"之後 IRQ 0 先收、ISR 0x3eb15 sti 再一條才收 IRQ 1)。",
}
for _part, _key in (("144 筆", "p1_eip"), ("25 筆", "p1_eip"), ("47 個", "p2_static"), ("9 個", "p2_static"), ("bx 5 / 1", "p2_static"),
                    ("計數暫存器 1 < 一個樣本 2", "p3_single"), ("差一(2 = 2)", "p3_single"), ("晚 5.5522 ms", "p4_start"),
                    ("前一個是 0xd0", "p4_start"), ("0xd4(10790.9074 ms", "p4_start"), ("0080:06ca", "p4_start"),
                    ("SBPRO2.MDI 分派段(一段 7617 條)", "p4_start"), ("另兩次晚收:3849.0002 ms", "p4_start"), ("DOS/4GW 0070(一段 1070 條", "p4_start")):
    assert _part in CONC[_key], (_part, CONC[_key])

OUTD = {
    "generator": rel(GEN_DIR / "ev_s173.py"),
    "exe_md5": MD5,
    "calllog": {"path": rel(RAW / "lc173a_CALLLOG.TXT"), "md5": LOG_MD5, "segs": SEGS, "io": IO_PORTS},
    "dosbox_src": rel(DRV / "dosbox_src_s173.txt"), "nm": rel(DRV / "nm_handlers_s173.txt"), "prediction": rel(DRV / "pred173.txt"),
    "validity": VALID,
    "p1_io_eip": P1,
    "p2_static_vs_live": {"drivers": P2, "control": P2_CONTROL, "dma_eips": [hex(a) for a in DMA_EIPS], "dma_groups": DMA, "dma_mask_only": DMA_MASK_ONLY},
    "p3_single_sample": {"dsp": [{**d, "cmd": hex(d["cmd"])} for d in DSP], "blocks": BLK, "rate": sorted(set(RATE.values())),
                         "single_sample": SINGLE, "prediction_wording": P3_PRED_WORDING, "dma_dac": DAC, "irq7": IRQ7},
    "p4_keys": {"keys": KEYS, "rows": KROWS, "normal": len(NORMAL), "transfer_buffer_per_bucket": {str(b): list(v) for b, v in TB.items()},
                "start_break": TRIGGER, "sti_windows": STI_WIN, "other_late": OTHER_LATE,
                "other_late_runs": {str(t): {**v, "cs": f"{v['cs']:04x}", "e0": hex(v["e0"]), "e1": hex(v["e1"]), "irq1_eip": hex(v["irq1_eip"])}
                                    for t, v in LATE_RUNS.items()},
                "reentry_post": dict(sorted(POST.items())), "reentry_odd": POST_ODD},
    "conclusion": CONC,
}
OUT.write_text(json.dumps(OUTD, ensure_ascii=False, indent=1) + "\n", encoding="utf-8", newline="\n")
print("wrote", OUT.name, P1["in_window"], {k: v["eips"] for k, v in P2.items()}, SINGLE, START["delay_ms"])
