#!/usr/bin/env python3
"""calllog_segments.py —— 解析呼叫紀錄的 G / S / I 紀錄(FD2_CALLLOG_SEGS):非遊戲指令落在哪一段、中斷在哪一條收。

為什麼需要這支
--------------
續一百六十三 .. 一百七十的呼叫紀錄只在遊戲 selector 裡記錄,非遊戲指令只有 `n - i` 這個條數:
校準每次 int 21h 比 delay 多 4 .. 9 條、MDI 型重入在驅動 `iret` 還是 DOS/4GW 返回路徑收中斷、
離群 2 次(DIG 601、MDI 375)—— 三件都卡在「看不到非遊戲程式碼裡的位置」。
`tools/dosbox/fd2_calllog_patch.py` 續一百七十一加了 FD2_CALLLOG_SEGS:時間窗內每段同一 selector、同一模式的
連續指令一筆 G(或每條指令一筆 S),每次 `CPU_Interrupt` 一筆 I。這支把它們接回「哪一段、幾條、在哪收中斷」。

用語
----
run      一筆 G(或連續同 selector / 模式的 S):(模式, CS, 起 EIP, 訖 EIP, 條數)。
episode  兩段遊戲 selector 之間的非遊戲 run 與 I 紀錄;以「離開遊戲時最後的 EIP → 回來時第一個 EIP」分組。
         n 不連續(時間窗的邊界)時 episode 標成不完整,不進分組統計。

子命令
------
    python tools/calllog_segments.py summary  <CALLLOG>          # 各 (模式, CS) 的指令數、各中斷號 / 種類的次數、連續性檢查
    python tools/calllog_segments.py episodes <CALLLOG> [--min N] # episode 分組:條數分布與路徑(run 序列)種類
    python tools/calllog_segments.py diff     <CALLLOG> A B       # 兩個 episode(編號)逐 run / 逐指令對齊,列出多出 / 少掉的
    python tools/calllog_segments.py irq      <CALLLOG>           # 硬體中斷(I type 0)收在哪:(模式, CS, EIP) 與所在 episode
    python tools/calllog_segments.py disasm   <CALLLOG> [--cs CS] # 紀錄裡帶 c= 的每個位置的第一條指令(capstone;沒有就只印位元組)
    python tools/calllog_segments.py io       <CALLLOG> [--port P] # O / N(FD2_CALLLOG_IO)與 K(FD2_CALLLOG_KBD)依 n 排序
    python tools/calllog_segments.py trig     <CALLLOG> [--block SEQ] [--insns]
                                                       # 觸發區塊(FD2_CALLLOG_TRIG):統計、自核、run 路徑;--insns 逐條
    python tools/calllog_segments.py --selftest

模式字元:r 真實模式、v V86、p 16 位元保護模式、P 32 位元保護模式(r / v / p 以 16 位元反組譯)。
續一百七十三:O / N 是 I/O 寫 / 讀(埠、值、寬度、當時的模式 / CS / EIP),K 是進鍵盤控制器佇列的位元組;
它們在指令執行當中寫出,不切斷 S 的合併,與 G 的先後以 n 為準。O / N 的 eip:CPU 的 in / out 是那條指令本身
(lc173a 逐條窗內 144 / 144 與同 n 的 S 相同);DOSBox-X callback(C++ 的 BIOS 程式)自己做的 I/O 是 callback 指令之後
(lc173a 的 25 筆 N 0021 在 f000:d105,同 n 的 S 是 f000:d101)。
續一百七十四:Y .. YE 是 FD2_CALLLOG_TRIG 觸發寫出的區塊(一段非遊戲 selector 的連續指令,或一段開始執行時 IF = 0 的連續指令,
條數符合規則才寫;前文若干條 + 區間 + 結束那一條),YS 逐條、YI 中斷,另存在 `Log.trigs`,不進 runs(n 與 G / S 不相接)。
`trig_problems` 用這裡自己的定義重核每個區塊(與 C++ 端分開實作):n 連號、條數、第一條、區間內外的判斷。
YC / YN 是到那時為止的每條規則符合 / 寫出數與每種區間總數(每寫一個區塊、定期與結尾都寫,取最後一組;
沒寫出的不等於沒發生,看這兩個)。harness 收尾是砍掉模擬器,最後一行常寫到一半:`_read` 只在檔尾沒有換行時丟掉那一行(`tail_cut`)。
只讀紀錄檔,不寫任何檔案。
"""
from __future__ import annotations

import argparse
import contextlib
import difflib
import io as io_mod
import re
import statistics
import sys
from collections import Counter, defaultdict
from dataclasses import dataclass, field
from pathlib import Path
from typing import Iterable, Iterator

if hasattr(sys.stdout, "reconfigure"):
    sys.stdout.reconfigure(encoding="utf-8")
    sys.stderr.reconfigure(encoding="utf-8")

# FD2_CALLLOG_SLICES(續一百七十二)的選用欄位:累計時間片數 k、片起點多出的週期 b、片內多出的週期 w
_SL = r"(?: k=(\d+) b=(-?\d+) w=(-?\d+))?"
_G = re.compile(r"^G ([rvpP]) ([0-9a-f]{4}) ([0-9a-f]{8}) ([0-9a-f]{8}) (\d+) n=(\d+)" + _SL + r"(?: c=([0-9a-f?]{32}))?$")
_S = re.compile(r"^S ([rvpP]) ([0-9a-f]{4}) ([0-9a-f]{8}) n=(\d+)" + _SL + r"(?: c=([0-9a-f?]{32}))?$")
_I = re.compile(r"^I ([0-9a-f]{2}) ([0-9a-f]+) ([rvpP]) ([0-9a-f]{4}) ([0-9a-f]{8}) n=(\d+) t=([0-9.]+)" + _SL + "$")
_IO = re.compile(r"^([ON]) ([0-9a-f]{4}) ([0-9a-f]+) ([124]) ([rvpP]) ([0-9a-f]{4}) ([0-9a-f]{8}) n=(\d+) t=([0-9.]+)"
                 + _SL + "$")
_K = re.compile(r"^K ([0-9a-f]{3}) (\d+) n=(\d+) t=([0-9.]+)" + _SL + "$")
# 續一百七十四 FD2_CALLLOG_TRIG:觸發寫出的區塊 Y .. YE(內含 YS / YI)與結尾統計 YC / YN
_Y = re.compile(r"^Y (\d+) (ng|if) (\d+) (\d+) n0=(\d+) n1=(\d+) t0=([0-9.]+) t1=([0-9.]+) ([0-9a-f]{4}) ([0-9a-f]{8})"
                r"( trunc=1)?$")
_YS = re.compile(r"^YS ([rvpP]) ([0-9a-f]{4}) ([0-9a-f]{8}) n=(\d+) if=([01])" + _SL + r"(?: c=([0-9a-f?]{32}))?$")
_YI = re.compile(r"^YI ([0-9a-f]{2}) ([0-9a-f]+) ([rvpP]) ([0-9a-f]{4}) ([0-9a-f]{8}) n=(\d+) t=([0-9.]+)" + _SL + "$")
_YE = re.compile(r"^YE (\d+)$")
_YC = re.compile(r"^YC (\d+) (ng|if) (\d+) (\d+)$")
_YN = re.compile(r"^YN (ng|if) (\d+)$")
_H_CS = re.compile(r"\bcs=([0-9a-f]{4})\b")


@dataclass
class Run:
    """同一 selector、同一模式的一段連續指令。"""

    m: str
    cs: int
    e0: int
    e1: int
    count: int
    n_end: int
    eips: list[int] | None = None  # 只有由 S 組成的 run 才有逐條 EIP
    sl: tuple[int, int, int] | None = None  # 到 e1 為止的 (k, b, w);紀錄沒有 FD2_CALLLOG_SLICES 時 None
    sls: list[tuple[int, int, int] | None] | None = None  # S 組成的 run:逐條的 (k, b, w)

    @property
    def n_start(self) -> int:
        """這段第一條指令之前已執行的總指令數。"""
        return self.n_end - self.count


@dataclass
class Irq:
    """一筆 I 紀錄。"""

    num: int
    type: int
    m: str
    cs: int
    eip: int
    n: int
    t: float
    sl: tuple[int, int, int] | None = None  # (k, b, w);沒有 FD2_CALLLOG_SLICES 時 None


@dataclass
class Io:
    """一筆 O(寫)/ N(讀)紀錄。"""

    op: str
    port: int
    value: int
    width: int
    m: str
    cs: int
    eip: int
    n: int
    t: float
    sl: tuple[int, int, int] | None = None
    line: int = 0  # 檔案行號(同 n 時的先後)


@dataclass
class Key:
    """一筆 K 紀錄:進鍵盤控制器佇列的位元組(0x100 = AUX)與當時已排隊的個數。"""

    data: int
    used: int
    n: int
    t: float
    sl: tuple[int, int, int] | None = None
    line: int = 0


@dataclass
class Insn:
    """觸發區塊裡的一條指令(YS)。"""

    m: str
    cs: int
    eip: int
    n: int
    iff: int  # 這條指令開始執行前的 IF
    sl: tuple[int, int, int] | None = None


@dataclass
class Trig:
    """FD2_CALLLOG_TRIG 寫出的一個區塊(Y .. YE)。"""

    seq: int
    kind: str      # "ng" / "if"
    rule: int
    count: int     # 區間的指令數
    n0: int        # 區間第一條指令的 n
    n1: int        # 區間最後一條指令的 n
    t0: float
    t1: float
    cs: int        # 區間第一條指令
    eip: int
    trunc: bool    # 環形緩衝已經沒有區間開頭
    insns: list[Insn] = field(default_factory=list)
    irqs: list[Irq] = field(default_factory=list)
    order: list[tuple[str, int]] = field(default_factory=list)  # ("S", insns 索引) / ("I", irqs 索引)
    code: dict[tuple[str, int, int], bytes | None] = field(default_factory=dict)
    complete: bool = False  # 讀到相符的 YE

    def span(self) -> list[Insn]:
        """區間本身的指令(不含前文與結束那一條)。"""
        return [x for x in self.insns if self.n0 <= x.n <= self.n1]

    def runs(self) -> list[Run]:
        """區塊內連續同 selector / 模式的指令併成 run(帶逐條 EIP)。"""
        out: list[Run] = []
        for x in self.insns:
            last = out[-1] if out else None
            if last is not None and last.m == x.m and last.cs == x.cs and last.n_end + 1 == x.n:
                last.e1 = x.eip
                last.count += 1
                last.n_end = x.n
                assert last.eips is not None
                last.eips.append(x.eip)
            else:
                out.append(Run(x.m, x.cs, x.eip, x.eip, 1, x.n, [x.eip]))
        return out


@dataclass
class Episode:
    """兩段遊戲 selector 之間的非遊戲指令。"""

    index: int
    left_from: int | None  # 離開遊戲前最後一條遊戲指令的 EIP
    back_to: int | None    # 回到遊戲的第一條指令 EIP
    runs: list[Run] = field(default_factory=list)
    irqs: list[Irq] = field(default_factory=list)
    complete: bool = True

    @property
    def total(self) -> int:
        """非遊戲指令數。"""
        return sum(r.count for r in self.runs)

    def path(self) -> tuple[tuple[str, int, int, int], ...]:
        """路徑:run 序列(不含條數)。"""
        return tuple((r.m, r.cs, r.e0, r.e1) for r in self.runs)


@dataclass
class Log:
    """解析後的紀錄。"""

    game_cs: int
    runs: list[Run]                 # 依檔案次序(遊戲與非遊戲都有)
    irqs: list[Irq]
    order: list[tuple[str, int]]    # ("G", runs 索引) / ("I", irqs 索引),檔案次序
    code: dict[tuple[str, int, int], bytes | None]  # (模式, CS, EIP) -> 16 位元組(有 ?? 時 None)
    gaps: list[tuple[int, int]]     # (前一段 n_end, 這段 n_start) 不相接的地方
    ios: list[Io] = field(default_factory=list)    # O / N,檔案次序
    keys: list[Key] = field(default_factory=list)  # K,檔案次序
    trigs: list[Trig] = field(default_factory=list)                    # Y .. YE 區塊
    trig_counts: dict[int, tuple[str, int, int]] = field(default_factory=dict)  # YC:規則 -> (種類, 符合, 寫出)
    trig_spans: dict[str, int] = field(default_factory=dict)          # YN:種類 -> 區間數
    tail_cut: bool = False  # 檔尾最後一行沒有換行(寫的人被砍掉),`_read` 已丟掉那一行


def _slices(mt: re.Match[str], first: int) -> tuple[int, int, int] | None:
    """從第 `first` 個群組起取 (k, b, w);沒有這組欄位時 None。"""
    if mt.group(first) is None:
        return None
    return int(mt.group(first)), int(mt.group(first + 1)), int(mt.group(first + 2))


def _code(hexs: str | None) -> bytes | None:
    if hexs is None or "?" in hexs:
        return None
    return bytes.fromhex(hexs)


def parse(lines: Iterable[str]) -> Log:
    """解析呼叫紀錄的 H / G / S / I / O / N / K 紀錄;其他種類略過。

    Args:
        lines: 紀錄檔的各行。

    Returns:
        `Log`;連續的同 selector / 模式 S 紀錄併成一個帶逐條 EIP 的 run。

    Raises:
        ValueError: 沒有 H 紀錄,或 G / S / I / O / N / K 開頭的行格式不符。
    """
    game_cs: int | None = None
    runs: list[Run] = []
    irqs: list[Irq] = []
    order: list[tuple[str, int]] = []
    code: dict[tuple[str, int, int], bytes | None] = {}
    ios: list[Io] = []
    keys: list[Key] = []
    prev_kind = ""  # 上一筆 G / S / I 紀錄的種類;只有接在 S 後面的 S 才能併進同一段
    trigs: list[Trig] = []
    trig_counts: dict[int, tuple[str, int, int]] = {}
    trig_spans: dict[str, int] = {}
    for ln, raw in enumerate(lines, 1):
        line = raw.rstrip("\r\n")
        if not line:
            continue
        k = line[0]
        if k == "Y":
            # 觸發區塊與主紀錄分開存:區塊的 n 不與 G / S 相接,不能進 runs
            tag = line.partition(" ")[0]
            cur = trigs[-1] if trigs and not trigs[-1].complete else None
            if tag == "Y":
                my = _Y.match(line)
                if not my:
                    raise ValueError(f"line {ln}: bad Y record: {line[:80]}")
                trigs.append(Trig(int(my.group(1)), my.group(2), int(my.group(3)), int(my.group(4)), int(my.group(5)),
                                  int(my.group(6)), float(my.group(7)), float(my.group(8)), int(my.group(9), 16),
                                  int(my.group(10), 16), my.group(11) is not None))
            elif tag == "YS":
                ms = _YS.match(line)
                if not ms:
                    raise ValueError(f"line {ln}: bad YS record: {line[:80]}")
                if cur is None:
                    raise ValueError(f"line {ln}: YS outside a Y block")
                m, cs, e = ms.group(1), int(ms.group(2), 16), int(ms.group(3), 16)
                if ms.group(9) is not None:
                    cur.code[(m, cs, e)] = _code(ms.group(9))
                cur.insns.append(Insn(m, cs, e, int(ms.group(4)), int(ms.group(5)), _slices(ms, 6)))
                cur.order.append(("S", len(cur.insns) - 1))
            elif tag == "YI":
                mi = _YI.match(line)
                if not mi:
                    raise ValueError(f"line {ln}: bad YI record: {line[:80]}")
                if cur is None:
                    raise ValueError(f"line {ln}: YI outside a Y block")
                cur.irqs.append(Irq(int(mi.group(1), 16), int(mi.group(2), 16), mi.group(3), int(mi.group(4), 16),
                                    int(mi.group(5), 16), int(mi.group(6)), float(mi.group(7)), _slices(mi, 8)))
                cur.order.append(("I", len(cur.irqs) - 1))
            elif tag == "YE":
                me = _YE.match(line)
                if not me:
                    raise ValueError(f"line {ln}: bad YE record: {line[:80]}")
                if cur is None or cur.seq != int(me.group(1)):
                    raise ValueError(f"line {ln}: YE {me.group(1)} does not close the open Y block")
                cur.complete = True
            elif tag == "YC":
                mc = _YC.match(line)
                if not mc:
                    raise ValueError(f"line {ln}: bad YC record: {line[:80]}")
                trig_counts[int(mc.group(1))] = (mc.group(2), int(mc.group(3)), int(mc.group(4)))
            elif tag == "YN":
                mn = _YN.match(line)
                if not mn:
                    raise ValueError(f"line {ln}: bad YN record: {line[:80]}")
                trig_spans[mn.group(1)] = int(mn.group(2))
            else:
                raise ValueError(f"line {ln}: unknown Y record: {line[:80]}")
            continue
        if k == "H" and game_cs is None:
            mh = _H_CS.search(line)
            if not mh:
                raise ValueError(f"line {ln}: H record without cs=")
            game_cs = int(mh.group(1), 16)
            continue
        if k == "G":
            mg = _G.match(line)
            if not mg:
                raise ValueError(f"line {ln}: bad G record: {line[:80]}")
            m, cs, e0, e1 = mg.group(1), int(mg.group(2), 16), int(mg.group(3), 16), int(mg.group(4), 16)
            if mg.group(10) is not None:
                code[(m, cs, e0)] = _code(mg.group(10))
            runs.append(Run(m, cs, e0, e1, int(mg.group(5)), int(mg.group(6)), sl=_slices(mg, 7)))
            order.append(("G", len(runs) - 1))
            prev_kind = "G"
        elif k == "S":
            ms = _S.match(line)
            if not ms:
                raise ValueError(f"line {ln}: bad S record: {line[:80]}")
            m, cs, e, n = ms.group(1), int(ms.group(2), 16), int(ms.group(3), 16), int(ms.group(4))
            if ms.group(8) is not None:
                code[(m, cs, e)] = _code(ms.group(8))
            sl = _slices(ms, 5)
            last = runs[-1] if runs else None
            if prev_kind == "S" and last is not None and last.m == m and last.cs == cs and last.n_end + 1 == n:
                last.e1 = e
                last.count += 1
                last.n_end = n
                last.sl = sl
                assert last.eips is not None and last.sls is not None
                last.eips.append(e)
                last.sls.append(sl)
            else:
                runs.append(Run(m, cs, e, e, 1, n, [e], sl, [sl]))
                order.append(("G", len(runs) - 1))
            prev_kind = "S"
        elif k == "I":
            mi = _I.match(line)
            if not mi:
                raise ValueError(f"line {ln}: bad I record: {line[:80]}")
            irqs.append(Irq(int(mi.group(1), 16), int(mi.group(2), 16), mi.group(3), int(mi.group(4), 16),
                            int(mi.group(5), 16), int(mi.group(6)), float(mi.group(7)), _slices(mi, 8)))
            order.append(("I", len(irqs) - 1))
            prev_kind = "I"
        elif k in "ON":
            mo = _IO.match(line)
            if not mo:
                raise ValueError(f"line {ln}: bad {k} record: {line[:80]}")
            ios.append(Io(mo.group(1), int(mo.group(2), 16), int(mo.group(3), 16), int(mo.group(4)), mo.group(5),
                          int(mo.group(6), 16), int(mo.group(7), 16), int(mo.group(8)), float(mo.group(9)),
                          _slices(mo, 10), ln))
        elif k == "K":
            mk = _K.match(line)
            if not mk:
                raise ValueError(f"line {ln}: bad K record: {line[:80]}")
            keys.append(Key(int(mk.group(1), 16), int(mk.group(2)), int(mk.group(3)), float(mk.group(4)),
                            _slices(mk, 5), ln))
    if game_cs is None:
        raise ValueError("no H record")
    gaps = [(a.n_end, b.n_start) for a, b in zip(runs, runs[1:]) if b.n_start != a.n_end]
    return Log(game_cs, runs, irqs, order, code, gaps, ios, keys, trigs, trig_counts, trig_spans)


def episodes(log: Log) -> list[Episode]:
    """把非遊戲 run 依遊戲 selector 切成 episode。

    開頭還沒看過遊戲 run、或結尾沒回到遊戲的 episode,以及中間 n 不相接的,都標成不完整。

    Args:
        log: `parse` 的結果。

    Returns:
        依次序的 episode 清單。
    """
    out: list[Episode] = []
    cur: Episode | None = None
    last_game: Run | None = None
    prev: Run | None = None
    for kind, i in log.order:
        if kind == "I":
            if cur is None:
                cur = Episode(len(out), last_game.e1 if last_game else None, None, complete=last_game is not None)
            cur.irqs.append(log.irqs[i])
            continue
        r = log.runs[i]
        gap = prev is not None and r.n_start != prev.n_end
        prev = r
        if r.cs == log.game_cs and r.m in "pP":
            if cur is not None:
                cur.back_to = r.e0
                if gap or not cur.runs:
                    cur.complete = False  # 回來之前缺指令,或只有 I、沒有非遊戲指令
                out.append(cur)
                cur = None
            last_game = r
            continue
        if cur is None:
            cur = Episode(len(out), last_game.e1 if last_game else None, None,
                          complete=last_game is not None and not gap)
        elif gap:
            cur.complete = False
        cur.runs.append(r)
    if cur is not None:
        cur.complete = False
        out.append(cur)
    for k, e in enumerate(out):
        e.index = k
    return out


def group_episodes(eps: list[Episode]) -> dict[tuple[int | None, int | None], list[Episode]]:
    """完整的 episode 依 (離開 EIP, 回來 EIP) 分組。"""
    g: dict[tuple[int | None, int | None], list[Episode]] = defaultdict(list)
    for e in eps:
        if e.complete:
            g[(e.left_from, e.back_to)].append(e)
    return dict(g)


def diff_runs(a: Episode, b: Episode,
              code: dict[tuple[str, int, int], bytes | None] | None = None) -> list[str]:
    """兩個 episode 對齊後的差異(逐 run;兩邊都有逐條 EIP 時逐指令)。

    Args:
        a: 第一個 episode。
        b: 第二個 episode。
        code: `Log.code`;給了時逐指令差異附上反組譯。

    Returns:
        差異行;完全相同時是空清單。
    """
    out: list[str] = []
    # 以起點對齊:同一個進入點、條數或終點不同,是同一段程式走了不同的分支
    ka = [(r.m, r.cs, r.e0) for r in a.runs]
    kb = [(r.m, r.cs, r.e0) for r in b.runs]
    sm = difflib.SequenceMatcher(a=ka, b=kb, autojunk=False)
    for tag, i1, i2, j1, j2 in sm.get_opcodes():
        if tag == "equal":
            for ra, rb in zip(a.runs[i1:i2], b.runs[j1:j2]):
                if ra.count != rb.count or ra.e1 != rb.e1:
                    out.append(f"  run {ra.m} {ra.cs:04x} {ra.e0:08x}: {ra.count} vs {rb.count} "
                               f"({rb.count - ra.count:+d}); last {ra.e1:08x} vs {rb.e1:08x}")
                    if ra.eips is not None and rb.eips is not None:
                        out.extend(_diff_eips(ra, rb, code))
            continue
        for r in a.runs[i1:i2]:
            out.append(f"  only A: {r.m} {r.cs:04x} {r.e0:08x}-{r.e1:08x} x{r.count}")
        for r in b.runs[j1:j2]:
            out.append(f"  only B: {r.m} {r.cs:04x} {r.e0:08x}-{r.e1:08x} x{r.count}")
    return out


def _diff_eips(ra: Run, rb: Run, code: dict[tuple[str, int, int], bytes | None] | None) -> list[str]:
    assert ra.eips is not None and rb.eips is not None
    out: list[str] = []

    def line(sign: str, e: int) -> str:
        c = None if code is None else code.get((ra.m, ra.cs, e))
        return f"    {sign} {e:08x}" + ("" if c is None else "  " + disasm_one(ra.m, e, c))

    sm = difflib.SequenceMatcher(a=ra.eips, b=rb.eips, autojunk=False)
    for tag, i1, i2, j1, j2 in sm.get_opcodes():
        if tag == "equal":
            continue
        for e in ra.eips[i1:i2]:
            out.append(line("-", e))
        for e in rb.eips[j1:j2]:
            out.append(line("+", e))
    return out


def disasm_one(m: str, eip: int, code: bytes) -> str:
    """反組譯 `code` 開頭的一條指令(r / v / p 用 16 位元,P 用 32 位元)。

    Args:
        m: 模式字元。
        eip: 位址(只用於顯示相對跳躍的目標)。
        code: 至少一條指令的位元組。

    Returns:
        "mnemonic op_str";沒有 capstone 時回傳 "(no capstone) <hex>",解不出時 "(bad) <hex>"。
    """
    try:
        import capstone  # 選用:Windows 端的 Python 有,WSL 端沒有
    except ImportError:
        return "(no capstone) " + code.hex()
    md = capstone.Cs(capstone.CS_ARCH_X86, capstone.CS_MODE_32 if m == "P" else capstone.CS_MODE_16)
    for ins in md.disasm(code, eip):
        return f"{ins.mnemonic} {ins.op_str}".strip()
    return "(bad) " + code.hex()


def _read(path: str) -> Log:
    """讀紀錄檔;檔尾沒有換行的最後一行(harness 砍掉模擬器時寫到一半)丟掉並標 `tail_cut`,其餘格式錯誤照樣報。"""
    with open(path, encoding="ascii", errors="replace", newline="") as f:
        lines = f.readlines()
    cut = bool(lines) and not lines[-1].endswith("\n")
    log = parse(lines[:-1] if cut else lines)
    log.tail_cut = cut
    return log


def cmd_summary(log: Log) -> int:
    """印各 (模式, CS) 指令數、I 次數與連續性。"""
    per: Counter[tuple[str, int]] = Counter()
    for r in log.runs:
        per[(r.m, r.cs)] += r.count
    print(f"game cs {log.game_cs:04x}; runs {len(log.runs)}; I {len(log.irqs)}; n gaps {len(log.gaps)}")
    for (m, cs), n in sorted(per.items(), key=lambda kv: -kv[1]):
        tag = " (game)" if cs == log.game_cs and m in "pP" else ""
        print(f"  {m} {cs:04x} {n}{tag}")
    ic: Counter[tuple[int, int]] = Counter((q.num, q.type) for q in log.irqs)
    for (num, typ), n in sorted(ic.items()):
        print(f"  I {num:02x} type {typ:x}: {n}")
    for a, b in log.gaps[:10]:
        print(f"  gap: n {a} -> {b} ({b - a:+d})")
    return 0


def cmd_episodes(log: Log, min_count: int) -> int:
    """印 episode 分組。"""
    eps = episodes(log)
    g = group_episodes(eps)
    print(f"episodes {len(eps)} (complete {sum(e.complete for e in eps)})")
    for key, lst in sorted(g.items(), key=lambda kv: -len(kv[1])):
        if len(lst) < min_count:
            continue
        tot = [e.total for e in lst]
        lf = "-" if key[0] is None else f"{key[0]:08x}"
        bt = "-" if key[1] is None else f"{key[1]:08x}"
        print(f"{lf} -> {bt}: {len(lst)} episodes, non-game {min(tot)} .. {max(tot)} "
              f"(median {statistics.median(tot)}); first #{lst[0].index}")
        paths = Counter(e.path() for e in lst)
        for p, n in paths.most_common(5):
            sample = next(e for e in lst if e.path() == p)
            cnts = Counter(e.total for e in lst if e.path() == p)
            segs = " ".join(f"{m}{cs:04x}:{e0:x}-{e1:x}" for m, cs, e0, e1 in p[:8])
            more = f" ... +{len(p) - 8}" if len(p) > 8 else ""
            print(f"    path x{n} ({len(p)} runs; totals {dict(sorted(cnts.items()))}; e.g. #{sample.index}): {segs}{more}")
    return 0


def cmd_diff(log: Log, a: int, b: int) -> int:
    """印兩個 episode 的差異。"""
    eps = episodes(log)
    for k in (a, b):
        if not 0 <= k < len(eps):
            print(f"FAIL: episode {k} out of range 0..{len(eps) - 1}")
            return 2
    ea, eb = eps[a], eps[b]
    print(f"A #{a}: {ea.total} non-game, {len(ea.runs)} runs; B #{b}: {eb.total} non-game, {len(eb.runs)} runs "
          f"({eb.total - ea.total:+d})")
    lines = diff_runs(ea, eb, log.code)
    for line in lines:
        print(line)
    if not lines:
        print("  identical")
    return 0


def cmd_irq(log: Log) -> int:
    """印硬體中斷收在哪裡。"""
    eps = episodes(log)
    where: dict[int, Episode] = {}
    for e in eps:
        for q in e.irqs:
            where[id(q)] = e
    hw = [q for q in log.irqs if q.type == 0]
    c: Counter[tuple[int, str, int, int]] = Counter((q.num, q.m, q.cs, q.eip) for q in hw)
    print(f"hardware interrupts {len(hw)}")
    for (num, m, cs, eip), n in c.most_common(40):
        ctx = Counter()
        for q in hw:
            if (q.num, q.m, q.cs, q.eip) == (num, m, cs, eip):
                e = where.get(id(q))
                ctx["in game" if e is None else f"episode from {e.left_from:08x}" if e.left_from is not None else "?"] += 1
        tag = " (game)" if cs == log.game_cs and m in "pP" else ""
        print(f"  int {num:02x} at {m} {cs:04x}:{eip:08x}{tag} x{n}  {dict(ctx.most_common(3))}")
    return 0


def cmd_disasm(log: Log, cs_filter: int | None) -> int:
    """印紀錄裡帶碼位元組的每個位置的第一條指令。"""
    for (m, cs, eip), code in sorted(log.code.items(), key=lambda kv: (kv[0][1], kv[0][2], kv[0][0])):
        if cs_filter is not None and cs != cs_filter:
            continue
        text = "(unreadable)" if code is None else disasm_one(m, eip, code)
        print(f"{m} {cs:04x}:{eip:08x}  {text}")
    return 0


def io_events(log: Log, ports: set[int] | None = None) -> list[str]:
    """O / N(只取 ports 裡的埠;None = 全部)與 K 依 n 排序(同 n 依檔案次序),每筆一行。"""
    ev = [(x.n, x.line, f"{x.t:.6f} {x.op} {x.port:04x} {x.value:x} w{x.width} {x.m} {x.cs:04x}:{x.eip:08x} n={x.n}")
          for x in log.ios if ports is None or x.port in ports]
    ev += [(y.n, y.line, f"{y.t:.6f} K {y.data:03x} used={y.used} n={y.n}") for y in log.keys]
    return [text for _n, _ln, text in sorted(ev)]


def cmd_io(log: Log, ports: list[int]) -> int:
    """印 O / N / K。"""
    for line in io_events(log, set(ports) if ports else None):
        print(line)
    return 0


def trig_problems(t: Trig, game_cs: int) -> list[str]:
    """用解析端自己的定義重核一個觸發區塊(與 C++ 端判斷分開實作),回傳不符的地方。

    Args:
        t: 一個 Y 區塊。
        game_cs: H 的遊戲 selector。

    Returns:
        問題清單;空清單 = 區塊與它的標頭一致。
    """
    bad: list[str] = []
    if not t.complete:
        bad.append("no YE")
    ns = [x.n for x in t.insns]
    if any(b != a + 1 for a, b in zip(ns, ns[1:])):
        bad.append("YS n not consecutive")
    if t.n1 - t.n0 + 1 != t.count:
        bad.append(f"n1 - n0 + 1 = {t.n1 - t.n0 + 1} != count {t.count}")
    sp = t.span()
    if not t.trunc:
        if len(sp) != t.count:
            bad.append(f"span holds {len(sp)} instructions, header says {t.count}")
        elif (sp[0].cs, sp[0].eip) != (t.cs, t.eip):
            bad.append("first span instruction differs from the header")
    inside = (lambda x: x.cs != game_cs) if t.kind == "ng" else (lambda x: x.iff == 0)
    if not all(inside(x) for x in sp):
        bad.append(f"a span instruction is outside the {t.kind} span")
    after = [x for x in t.insns if x.n == t.n1 + 1]
    if len(after) != 1 or inside(after[0]):
        bad.append("the instruction after the span is missing or still inside it")
    before = [x for x in t.insns if x.n == t.n0 - 1]
    if before and inside(before[0]) and not t.trunc:
        bad.append("the instruction before the span is inside it")
    return bad


def cmd_trig(log: Log, block: int | None, insns: bool) -> int:
    """印觸發區塊:結尾統計、每個區塊的標頭、自核結果、run 路徑、中斷;--insns 逐條反組譯。"""
    for r, (kind, matched, written) in sorted(log.trig_counts.items()):
        print(f"rule {r} {kind}: matched {matched}, written {written}")
    for kind, n in sorted(log.trig_spans.items()):
        print(f"{kind} spans {n}")
    rc = 0
    for t in log.trigs:
        if block is not None and t.seq != block:
            continue
        bad = trig_problems(t, log.game_cs)
        rc |= 1 if bad else 0
        print(f"#{t.seq} {t.kind} rule {t.rule}: {t.count} instructions n {t.n0}..{t.n1}, {t.t0:.6f} .. {t.t1:.6f} ms "
              f"({t.t1 - t.t0:.4f}), first {t.cs:04x}:{t.eip:08x}{' TRUNC' if t.trunc else ''}"
              f"{'' if not bad else ' PROBLEMS: ' + '; '.join(bad)}")
        if insns:
            irq_at: defaultdict[int, list[Irq]] = defaultdict(list)
            for q in t.irqs:
                irq_at[q.n].append(q)
            for x in t.insns:
                for q in irq_at.pop(x.n - 1, []):
                    print(f"    I {q.num:02x} type {q.type:x} at {q.m} {q.cs:04x}:{q.eip:08x} {q.t:.6f}")
                c = t.code.get((x.m, x.cs, x.eip))
                text = "" if c is None else disasm_one(x.m, x.eip, c)
                mark = "*" if t.n0 <= x.n <= t.n1 else " "
                print(f"  {mark}{x.m} {x.cs:04x}:{x.eip:08x} if={x.iff} n={x.n}  {text}")
            for lst in irq_at.values():
                for q in lst:
                    print(f"    I {q.num:02x} type {q.type:x} at {q.m} {q.cs:04x}:{q.eip:08x} {q.t:.6f} (n={q.n})")
        else:
            rs = t.runs()
            for r in rs[:40]:
                print(f"    {r.m} {r.cs:04x}:{r.e0:08x}-{r.e1:08x} x{r.count}")
            if len(rs) > 40:
                print(f"    ... +{len(rs) - 40} runs")
            for q in t.irqs:
                print(f"    I {q.num:02x} type {q.type:x} at {q.m} {q.cs:04x}:{q.eip:08x} n={q.n} {q.t:.6f}")
    return rc


def selftest() -> int:
    """合成紀錄的自我檢查(含成對對照)。

    Returns:
        0 = 通過,1 = 失敗。
    """
    fails: list[str] = []

    def check(cond: bool, what: str) -> None:
        if not cond:
            fails.append(what)

    def g(m: str, cs: int, e0: int, e1: int, cnt: int, n: int, c: str | None = None) -> str:
        return f"G {m} {cs:04x} {e0:08x} {e1:08x} {cnt} n={n}" + (f" c={c}" if c else "")

    pad = "00" * 14
    # 遊戲 delay 迴圈兩次 int 21h:第一次 DOS/4GW 6 條 + 真實模式 3 條,第二次真實模式多 2 條(9 vs 11)
    lines = [
        "H fd2calllog 1 cs=0170 entries=1 cap=200 dump=32 lo=00000000 hi=00000001 icount=1 segs=0-10",
        g("P", 0x170, 0x3e01d, 0x3e025, 5, 5, "cd21" + pad),
        g("P", 0x0f00, 0x100, 0x120, 6, 11, "cd21" + pad),
        g("r", 0xf000, 0x10, 0x18, 3, 14, "b80100" + "00" * 13),
        g("P", 0x170, 0x3e027, 0x3e02f, 5, 19),
        g("P", 0x0f00, 0x100, 0x120, 6, 25),
        g("r", 0xf000, 0x10, 0x1c, 5, 30),
        g("P", 0x170, 0x3e027, 0x3e02f, 5, 35),
        "I 08 0 r f000 0000001a n=35 t=1.5",
        g("r", 0xf000, 0x10, 0x1c, 5, 40),
        g("P", 0x170, 0x3e027, 0x3e02f, 5, 45),
    ]
    log = parse(lines)
    check(log.game_cs == 0x170, "game cs from H")
    check(len(log.runs) == 9 and len(log.irqs) == 1, "record counts")
    check(log.gaps == [], "contiguous log has no gaps")
    eps = episodes(log)
    check([e.total for e in eps] == [9, 11, 5], "episode totals 9 / 11 / 5")
    check(all(e.complete for e in eps), "all three complete")
    check(eps[0].left_from == 0x3e025 and eps[0].back_to == 0x3e027, "episode endpoints")
    check(len(eps[2].irqs) == 1 and eps[2].irqs[0].eip == 0x1a, "I record attached to its episode")
    check(log.irqs[0] == Irq(0x08, 0, "r", 0xF000, 0x1A, 35, 1.5), "I record fields parsed")
    check(log.order[:3] == [("G", 0), ("G", 1), ("G", 2)] and log.order[7] == ("I", 0), "order indexes")
    grp = group_episodes(eps)
    check(len(grp[(0x3e025, 0x3e027)]) == 1 and len(grp[(0x3e02f, 0x3e027)]) == 2, "grouping by endpoints")
    d = diff_runs(eps[0], eps[1])
    check(any("00000010: 3 vs 5 (+2); last 00000018 vs 0000001c" in x for x in d), "diff reports the +2 run")
    check(len(d) == 1, "diff reports only the changed run")
    check(diff_runs(eps[1], eps[1]) == [], "control: an episode vs itself has no diff")
    # 對照:拿掉一筆非遊戲 G(n=25 那 6 條)時要看到不相接,所在 episode 不完整
    log2 = parse(lines[:5] + lines[6:])
    check(log2.gaps == [(19, 25)], "removed run shows up as a gap")
    eps2 = episodes(log2)
    check([e.complete for e in eps2] == [True, False, True], "gapped episode (first run after the gap) incomplete")
    # 不相接落在 episode 中間也要標
    log3 = parse(lines[:2] + lines[3:])
    check([e.complete for e in episodes(log3)] == [False, True, True], "gap before returning to the game marks it")
    # S 紀錄:逐條併成 run,逐指令對齊找出多出來的那一條
    s_lines = [
        "H fd2calllog 1 cs=0170 segs=0-1:x",
        "S P 0170 00001000 n=1",
        "S r f000 00000010 n=2 c=90" + "00" * 15,
        "S r f000 00000011 n=3",
        "S r f000 00000012 n=4",
        "S P 0170 00001002 n=5",
        "S r f000 00000010 n=6",
        "S r f000 00000011 n=7",
        "S r f000 00000020 n=8",
        "S r f000 00000012 n=9",
        "S P 0170 00001002 n=10",
    ]
    slog = parse(s_lines)
    check(len(slog.runs) == 5 and slog.runs[1].eips == [0x10, 0x11, 0x12], "S records merged into runs")
    check([(r.e0, r.count, r.n_end) for r in slog.runs] == [(0x1000, 1, 1), (0x10, 3, 4), (0x1002, 1, 5), (0x10, 4, 9),
                                                           (0x1002, 1, 10)], "S runs: start, count, n_end")
    check(slog.order == [("G", k) for k in range(5)], "S runs in order")
    seps = episodes(slog)
    check([(e.left_from, e.back_to, e.total) for e in seps] == [(0x1000, 0x1002, 3), (0x1002, 0x1002, 4)],
          "S episodes endpoints and totals")
    # G 或 I 之後,即使 n 相接、selector / 模式相同,S 也要另起一段(對照:兩筆 S 相接時要併)
    gs = parse(["H x cs=0170", "G r f000 00000010 00000012 3 n=3", "S r f000 00000013 n=4",
                "I 08 0 r f000 00000013 n=4 t=1.0", "S r f000 00000013 n=5", "S r f000 00000014 n=6"])
    check([(r.e0, r.count, r.eips) for r in gs.runs] == [(0x10, 3, None), (0x13, 1, [0x13]), (0x13, 2, [0x13, 0x14])],
          "S after G / I starts a new run; S after S merges")
    check(gs.order == [("G", 0), ("G", 1), ("I", 0), ("G", 2)], "order across G / S / I")
    two_i = parse(["H x cs=0170", "I 08 0 r f000 00000001 n=1 t=1.0", "I 21 1 P 0170 00000002 n=1 t=2.0"])
    check(two_i.order == [("I", 0), ("I", 1)] and two_i.irqs[1].num == 0x21 and two_i.irqs[1].type == 1,
          "second I record indexed and parsed")
    try:
        parse(["H x cs=0170", "S r f000 zz"])
        check(False, "bad S must raise")
    except ValueError as e:
        check(str(e).startswith("line 2:"), "error names the 1-based line")
    sd = diff_runs(seps[0], seps[1])
    check("    + 00000020" in sd and not any(x.startswith("    -") for x in sd), "per-instruction diff finds the extra one")
    sdc = diff_runs(seps[0], seps[1], {("r", 0xF000, 0x20): bytes.fromhex("cd21")})
    if not disasm_one("r", 0, bytes.fromhex("90")).startswith("(no capstone)"):
        check("    + 00000020  int 0x21" in sdc, "diff annotates the extra instruction with its decode")
    # 長序列(>= 200)裡重複很多次的元素不能被 difflib 當成雜訊(autojunk 開著時,
    # 150 個相同 + 1 個不同 + 150 個相同,會被判成後面 151 個整段換掉)
    def rr(e0: int) -> Run:
        return Run("r", 0xF000, e0, e0, 1, 1)

    ea = Episode(0, 1, 2, [rr(0x10)] * 150 + [rr(0x11)] + [rr(0x10)] * 150)
    eb = Episode(1, 1, 2, [rr(0x10)] * 150 + [rr(0x12)] + [rr(0x10)] * 150)
    check(diff_runs(ea, eb) == ["  only A: r f000 00000011-00000011 x1", "  only B: r f000 00000012-00000012 x1"],
          "long run sequence: only the one differing run")
    ra = Run("r", 0xF000, 0x10, 0x10, 301, 301, [0x10] * 150 + [0x11] + [0x10] * 150)
    rb = Run("r", 0xF000, 0x10, 0x10, 301, 301, [0x10] * 150 + [0x12] + [0x10] * 150)
    check(_diff_eips(ra, rb, None) == ["    - 00000011", "    + 00000012"], "long eip sequence: only the one differing eip")
    # type 是任意位數的十六進位(單一位數在 16 / 17 進位下相同,要兩位數才分得出來)
    check(parse(["H x cs=0170", "I 0d 1e p 0088 00000001 n=1 t=1.0"]).irqs[0].type == 0x1E, "I type parsed as hex")
    # FD2_CALLLOG_SLICES 的 k / b / w(三個值各不相同,w 可以是負的;對照:沒有這組欄位時是 None)
    sl = parse(["H x cs=0170 slices=1", "G r f000 00000010 00000012 3 n=3 k=12 b=34 w=-5 c=90" + "00" * 15,
                "S r f000 00000013 n=4 k=13 b=36 w=-5", "S r f000 00000014 n=5 k=13 b=36 w=7",
                "I 08 0 r f000 00000014 n=5 t=1.0 k=14 b=38 w=9"])
    check(sl.runs[0].sl == (12, 34, -5) and sl.code[("r", 0xF000, 0x10)] == bytes.fromhex("90" + "00" * 15),
          "G slices and code bytes both parsed")
    check(sl.runs[1].sls == [(13, 36, -5), (13, 36, 7)] and sl.runs[1].sl == (13, 36, 7), "S slices per instruction")
    check(sl.irqs[0].sl == (14, 38, 9), "I slices parsed")
    check(gs.runs[0].sl is None and gs.runs[1].sls == [None] and gs.irqs[0].sl is None, "control: no slices -> None")
    # 不相接的 S 不能併進前一段(對照:n 跳號)
    slog2 = parse(s_lines[:3] + ["S r f000 00000011 n=9"])
    check(len(slog2.runs) == 3 and slog2.gaps == [(2, 8)], "non-consecutive S starts a new run")
    # 格式錯誤要報出來,不能默默略過
    try:
        parse(["H x cs=0170", "G P 0170 zz"])
        check(False, "bad G must raise")
    except ValueError:
        pass
    try:
        parse(["G P 0170 00000000 00000000 1 n=1"])
        check(False, "missing H must raise")
    except ValueError:
        pass
    # 續一百七十三:O / N / K(值與埠各不相同;夾在兩筆 S 中間不切斷合併)
    io = parse(["H x cs=0170 io=0-f,220-22f kbd=1",
                "S r 0f71 00000285 n=10",
                "O 0003 1 1 r 0f71 00000286 n=10 t=12.5",
                "K 01c 0 n=10 t=12.75",
                "S r 0f71 00000286 n=11",
                "N 022e ab 2 v 0088 00001234 n=11 t=13.0 k=7 b=8 w=-9",
                "O 0060 9c 4 P 0170 0003e01d n=9 t=14.0",
                "K 19c 3 n=12 t=15.0 k=1 b=2 w=3"])
    check(io.ios[0] == Io("O", 3, 1, 1, "r", 0xF71, 0x286, 10, 12.5, None, 3), "O fields")
    check(io.ios[1] == Io("N", 0x22E, 0xAB, 2, "v", 0x88, 0x1234, 11, 13.0, (7, 8, -9), 6), "N fields + slices")
    check(io.keys == [Key(0x1C, 0, 10, 12.75, None, 4), Key(0x19C, 3, 12, 15.0, (1, 2, 3), 8)], "K fields")
    check(len(io.runs) == 1 and io.runs[0].eips == [0x285, 0x286], "O / K between two S do not split the run")
    check(io_events(io) == ["14.000000 O 0060 9c w4 P 0170:0003e01d n=9",
                            "12.500000 O 0003 1 w1 r 0f71:00000286 n=10",
                            "12.750000 K 01c used=0 n=10",
                            "13.000000 N 022e ab w2 v 0088:00001234 n=11",
                            "15.000000 K 19c used=3 n=12"], "io events by n, then file line")
    check(io_events(io, {3}) == ["12.500000 O 0003 1 w1 r 0f71:00000286 n=10", "12.750000 K 01c used=0 n=10",
                                 "15.000000 K 19c used=3 n=12"], "port filter keeps K")
    check(gs.ios == [] and gs.keys == [], "control: no O / N / K -> empty")
    for bad in ("O 0003 1 3 r 0f71 00000286 n=10 t=1.0", "N 03 1 1 r 0f71 00000286 n=10 t=1.0", "K 1c 0 n=1 t=1.0"):
        try:
            parse(["H x cs=0170", bad])
            check(False, f"bad record must raise: {bad}")
        except ValueError as e:
            check(str(e).startswith(f"line 2: bad {bad[0]} record"), f"error names the kind: {bad}")
    # 續一百七十四:觸發區塊(ng 區間 3 條,前文 2 條,結束那一條回到遊戲;中間一筆 YI 不切斷)
    c90 = "90" * 16
    yl = ["H fd2calllog 1 cs=0170 trig=ng:3 trigring=1024 trigpre=2 trigcap=20",
          "Y 1 ng 0 3 n0=12 n1=14 t0=1.5 t1=1.75 0080 00000ed6",
          "YS P 0170 0003eb10 n=10 if=1 c=" + c90,
          "YS P 0170 0003eb11 n=11 if=1",
          "YS p 0080 00000ed6 n=12 if=0 c=cf" + "00" * 15,
          "YI 1c 1e p 0080 00000ed7 n=12 t=1.6 k=7 b=8 w=-9",
          "YS p 0088 00000ed7 n=13 if=1 k=4 b=5 w=-6",
          "YS p 0080 00000ed8 n=14 if=1",
          "YS P 0170 0003eb12 n=15 if=1",
          "YE 1",
          "YC 0 ng 3 2", "YN ng 5", "YN if 2"]
    ty = parse(yl)
    check(len(ty.trigs) == 1 and ty.runs == [] and ty.irqs == [] and ty.code == {},
          "trigger block kept apart from the main runs / irqs / code")
    t1 = ty.trigs[0]
    check((t1.seq, t1.kind, t1.rule, t1.count, t1.n0, t1.n1, t1.t0, t1.t1, t1.cs, t1.eip, t1.trunc, t1.complete) ==
          (1, "ng", 0, 3, 12, 14, 1.5, 1.75, 0x80, 0xED6, False, True), "Y header fields")
    check([x.n for x in t1.span()] == [12, 13, 14] and len(t1.insns) == 6, "span vs pre-context and closing instruction")
    check(t1.insns[3] == Insn("p", 0x88, 0xED7, 13, 1, (4, 5, -6)) and t1.insns[2].iff == 0, "YS fields")
    check(t1.irqs == [Irq(0x1C, 0x1E, "p", 0x80, 0xED7, 12, 1.6, (7, 8, -9))]
          and t1.order == [("S", 0), ("S", 1), ("S", 2), ("I", 0), ("S", 3), ("S", 4), ("S", 5)],
          "YI fields (hex num / type, slices) and order")
    check([(r.m, r.cs, r.e0, r.e1, r.count) for r in t1.runs()] ==
          [("P", 0x170, 0x3EB10, 0x3EB11, 2), ("p", 0x80, 0xED6, 0xED6, 1), ("p", 0x88, 0xED7, 0xED7, 1),
           ("p", 0x80, 0xED8, 0xED8, 1), ("P", 0x170, 0x3EB12, 0x3EB12, 1)], "block runs split by selector, not by YI")
    check(Trig(1, "ng", 0, 2, 1, 2, 0.0, 0.0, 0x80, 1, False,
               [Insn("p", 0x80, 1, 1, 1), Insn("p", 0x80, 2, 3, 1)]).runs()[1].e0 == 2, "n gap splits a block run")
    check(t1.code == {("P", 0x170, 0x3EB10): bytes.fromhex(c90), ("p", 0x80, 0xED6): bytes.fromhex("cf" + "00" * 15)},
          "block code bytes")
    check(ty.trig_counts == {0: ("ng", 3, 2)} and ty.trig_spans == {"ng": 5, "if": 2}, "YC / YN")
    check(trig_problems(t1, 0x170) == [], "consistent block has no problems")
    # 對照:每種不一致各注入一次,都要被抓到
    def tp(repl: tuple[int, str]) -> list[str]:
        ls = list(yl)
        ls[repl[0]] = repl[1]
        return trig_problems(parse(ls).trigs[0], 0x170)

    check("n1 - n0 + 1 = 3 != count 4" in tp((1, "Y 1 ng 0 4 n0=12 n1=14 t0=1.5 t1=1.75 0080 00000ed6")),
          "fault: header count off by one")
    check(any("consecutive" in p for p in tp((6, "YS p 0080 00000ed7 n=12 if=1"))), "fault: repeated n")
    check(any("after the span" in p for p in tp((8, "YS p 0080 0003eb12 n=15 if=1"))), "fault: span did not end")
    check(any("before the span" in p for p in tp((3, "YS p 0080 0003eb11 n=11 if=1"))), "fault: span started earlier")
    check(any("outside the ng span" in p for p in tp((6, "YS P 0170 00000ed7 n=13 if=1"))), "fault: game insn in span")
    check(any("differs from the header" in p for p in tp((1, "Y 1 ng 0 3 n0=12 n1=14 t0=1.5 t1=1.75 0088 00000ed6"))),
          "fault: header first selector")
    check(any("differs from the header" in p for p in tp((1, "Y 1 ng 0 3 n0=12 n1=14 t0=1.5 t1=1.75 0080 00000ed7"))),
          "fault: header first instruction")
    open_blk = parse(yl[:9]).trigs[0]
    check(not open_blk.complete and "no YE" in trig_problems(open_blk, 0x170), "fault: missing YE")
    # if 區間用 IF 判斷(對照:同一份資料當 ng 看就不符)
    il = ["H x cs=0170", "Y 2 if 1 2 n0=6 n1=7 t0=1.0 t1=2.0 0170 00000010",
          "YS P 0170 0000000f n=5 if=1", "YS P 0170 00000010 n=6 if=0", "YS P 0170 00000011 n=7 if=0",
          "YS P 0170 00000012 n=8 if=1", "YE 2"]
    ti = parse(il).trigs[0]
    check(trig_problems(ti, 0x170) == [], "if block consistent")
    ti.kind = "ng"
    check(trig_problems(ti, 0x170) != [], "control: same block judged as ng fails")
    # trunc:區間比留下的短時只在 trunc=1 下可以
    tl = ["H x cs=0170", "Y 3 ng 0 4 n0=10 n1=13 t0=1.0 t1=2.0 0080 00000001 trunc=1",
          "YS p 0080 00000003 n=12 if=1", "YS p 0080 00000004 n=13 if=1", "YS P 0170 00000005 n=14 if=1", "YE 3"]
    check(trig_problems(parse(tl).trigs[0], 0x170) == [], "truncated block accepted with trunc=1")
    check(any("span holds 2" in p for p in trig_problems(parse([tl[0], tl[1].replace(" trunc=1", "")] + tl[2:]).trigs[0],
                                                          0x170)), "control: same block without trunc=1 fails")
    for bad, msg in ((["YS P 0170 00000001 n=1 if=1"], "outside a Y block"),
                     (yl[1:3] + ["YE 9"], "does not close"),
                     (["YZ 1"], "unknown Y record"),
                     (["Y 1 ng 0 3 n0=1 n1=3 t0=1 t1=2 80 00000001"], "bad Y record"),
                     (yl[1:2] + ["YS P 0170 00000001 n=1 if=2"], "bad YS record")):
        try:
            parse(["H x cs=0170"] + bad)
            check(False, f"must raise: {msg}")
        except ValueError as e:
            check(msg in str(e), f"error text: {msg}")
    buf = io_mod.StringIO()
    with contextlib.redirect_stdout(buf):
        rc_ok = cmd_trig(ty, None, True)
    out_lines = buf.getvalue().splitlines()
    check(rc_ok == 0 and out_lines[0] == "rule 0 ng: matched 3, written 2", "cmd_trig summary and rc 0")
    i_line = next((k for k, s in enumerate(out_lines) if s.startswith("    I 1c type 1e at p 0080:00000ed7")), -1)
    check(i_line > 0 and "n=13" in out_lines[i_line + 1] and "n=12" in out_lines[i_line - 1],
          "YI printed between the instructions it fell between")
    check(sum(1 for s in out_lines if s.startswith("  *")) == 3, "span instructions marked")
    with contextlib.redirect_stdout(io_mod.StringIO()):
        rc_bad = cmd_trig(parse(yl[:9]), None, False)
    check(rc_bad == 1, "cmd_trig rc 1 on a block with problems")
    # --block 篩選(對照:不存在的 seq 一個區塊也不印)
    for seq, want in ((1, 1), (2, 0)):
        buf = io_mod.StringIO()
        with contextlib.redirect_stdout(buf):
            cmd_trig(ty, seq, False)
        check(sum(1 for s in buf.getvalue().splitlines() if s.startswith("#")) == want, f"--block {seq} prints {want}")
    # run 超過 40 個只印前 40 個:42 條交替 selector + 結束那條(0170,接在 0171 後另起)= 43 個 run;
    # 41 條時最後一條是 0170,結束那條併進去 = 41 個 run(對照:剛好超過 1 個也要截)
    for nr, more in ((42, 3), (41, 1)):
        ml = ["H x cs=0170", f"Y 5 if 0 {nr} n0=1 n1={nr} t0=1.0 t1=2.0 0170 00000000"]
        ml += [f"YS P {0x170 if k % 2 == 0 else 0x171:04x} {k:08x} n={k + 1} if=0" for k in range(nr)]
        ml += [f"YS P 0170 {nr:08x} n={nr + 1} if=1", "YE 5"]
        buf = io_mod.StringIO()
        with contextlib.redirect_stdout(buf):
            cmd_trig(parse(ml), None, False)
        lines_m = buf.getvalue().splitlines()
        check(sum(1 for s in lines_m if s.startswith("    P ")) == 40 and f"    ... +{more} runs" in lines_m,
              f"run listing capped at 40 ({40 + more} runs)")
    # 檔尾寫到一半(沒有換行)的那一行丟掉並標 tail_cut;對照:有換行的壞行照樣報錯、完整檔不標
    import tempfile
    with tempfile.TemporaryDirectory() as td:
        good = "H x cs=0170\nS r f000 00000010 n=1\n"
        pth = Path(td) / "c.txt"
        pth.write_bytes((good + "S r f000 0000").encode("ascii"))
        lc = _read(str(pth))
        check(lc.tail_cut and len(lc.runs) == 1, "cut tail dropped and flagged")
        pth.write_bytes(good.encode("ascii"))
        check(not _read(str(pth)).tail_cut and len(_read(str(pth)).runs) == 1, "control: complete file not flagged")
        pth.write_bytes((good + "S r f000 0000\n").encode("ascii"))
        try:
            _read(str(pth))
            check(False, "a bad line with its newline must still raise")
        except ValueError:
            pass
        pth.write_bytes((good + "S r f000 0000\r\n").encode("ascii"))
        try:
            _read(str(pth))
            check(False, "a bad CRLF line must still raise")
        except ValueError:
            pass
    # 反組譯:同一組位元組 16 / 32 位元解法不同(模式要真的影響結果)
    b = bytes.fromhex("b801000000")
    d16, d32 = disasm_one("r", 0, b), disasm_one("P", 0, b)
    if d16.startswith("(no capstone)"):
        print("note: capstone missing, disasm checks skipped")
    else:
        check(d16 == "mov ax, 1", f"16-bit decode ({d16})")
        check(d32 == "mov eax, 1", f"32-bit decode ({d32})")
        check(disasm_one("p", 0, bytes.fromhex("cd21")) == "int 0x21", "int 21h decode")
    for f in fails:
        print("FAIL:", f)
    print("selftest:", "PASS" if not fails else f"FAIL ({len(fails)})")
    return 0 if not fails else 1


def main(argv: list[str] | None = None) -> int:
    """命令列入口。"""
    ap = argparse.ArgumentParser(description="解析呼叫紀錄的 G / S / I / O / N / K / Y 紀錄")
    ap.add_argument("--selftest", action="store_true")
    sub = ap.add_subparsers(dest="cmd")
    for name in ("summary", "episodes", "diff", "irq", "disasm", "io", "trig"):
        sp = sub.add_parser(name)
        sp.add_argument("log")
        if name == "episodes":
            sp.add_argument("--min", type=int, default=1, help="只印至少這麼多個 episode 的分組")
        if name == "diff":
            sp.add_argument("a", type=int)
            sp.add_argument("b", type=int)
        if name == "disasm":
            sp.add_argument("--cs", type=lambda s: int(s, 16), default=None)
        if name == "io":
            sp.add_argument("--port", action="append", type=lambda s: int(s, 16), default=[])
        if name == "trig":
            sp.add_argument("--block", type=int, default=None, help="只印這個區塊(Y 的 seq)")
            sp.add_argument("--insns", action="store_true", help="逐條指令(含反組譯與中斷位置)")
    args = ap.parse_args(argv)
    if args.selftest:
        return selftest()
    if not args.cmd:
        ap.print_help()
        return 2
    try:
        log = _read(args.log)
    except (OSError, ValueError) as e:
        print(f"FAIL: {args.log}: {e}")
        return 1
    if log.tail_cut:
        print("note: last line had no newline (writer killed); dropped", file=sys.stderr)
    if args.cmd == "summary":
        return cmd_summary(log)
    if args.cmd == "episodes":
        return cmd_episodes(log, args.min)
    if args.cmd == "diff":
        return cmd_diff(log, args.a, args.b)
    if args.cmd == "irq":
        return cmd_irq(log)
    if args.cmd == "io":
        return cmd_io(log, args.port)
    if args.cmd == "trig":
        return cmd_trig(log, args.block, args.insns)
    return cmd_disasm(log, args.cs)


if __name__ == "__main__":
    sys.exit(main())
