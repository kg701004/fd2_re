"""續一百三十九證據:evidence/rle4_roundtrip_s139_20261020.json。

四模式 sprite RLE 的來回驗證:解碼後再編回去,逐 byte 與原檔相同才算把格式看完整。
(A) 範圍:FDICON.B24 全部 1680 個圖示、FDSHAP 圖塊庫(偶數號,去掉一份重複後 32 份)全部圖塊、FIGANI 與 FDOTHER 裡
    所有「幀容器」的每一幀。每個串流用線性解碼剛好吃完、剛好填滿 w×h,而且沒有任何一個控制位元組的跨距跨過列尾
    —— 原編碼器是逐列編的。
(B) 一個逐列編碼器加上 6 條規則,把上面每一個串流逐 byte 編回原樣(0 個不同)。每條規則單獨改掉,都會有串流編不回去,
    所以 6 條都是資料逼出來的,不是多餘的。
(C) 對照:模式 1 若照 decode_sprite.py 當時(續一百四十改成 dither 以前)的預設當成 literal(讀 count 個像素),含模式 1 的串流沒有一個能剛好吃完;
    用錯一欄的寬度解碼,跨列的控制位元組就出現 —— 「0 個跨列」只在真正的寬度成立。
容器:FDICON 的位移表有 count + 1 筆(最後一筆 = 檔長);FDSHAP 只有 count 筆;FIGANI / FDOTHER 的幀數是第 0 個 byte,
第 1 個 byte 是 0 或 1(FIGANI 有 15 份是 1),位移表從 +8 起。
全部從原版 FDICON.B24 與 extracted/raw 重算;任何判準或預測不符就 assert 失敗。
"""
from __future__ import annotations

import collections
import json
import struct

from _evpaths import GAME, ROOT, out_path, rel, require_inputs  # noqa: E402
require_inputs(__file__)

FDICON = GAME / "FDICON.B24"
RAW = ROOT / "extracted/raw"
OUT = out_path("rle4_roundtrip_s139_20261020.json")
T = -1        # 沒寫入(透明)
CAP = 64      # 控制位元組低 6 bit + 1


# ================= 解碼 =================
def walk(body: bytes, w: int, total: int, mode1_literal: bool = False) -> tuple[list[int], int, int, int, int]:
    """線性解碼。回傳 (像素, 吃掉的 bytes, 最後位置, 跨列的控制位元組數, 模式 1 個數);T = 沒寫入。

    mode1_literal=True 是對照:把模式 1 當成 literal(decode_sprite.py 續一百四十以前的預設 mode01="literal")。
    """
    out = [T] * total
    i = pos = cross = m1 = 0
    while pos < total and i < len(body):
        c = body[i]
        i += 1
        m, n = c >> 6, (c & 63) + 1
        if m == 1 and mode1_literal:
            m = 2
        span = 2 * n if m == 1 else n
        if pos // w != (pos + span - 1) // w:
            cross += 1
        if m == 0:
            out[pos:pos + n] = [body[i]] * n
            i += 1
        elif m == 1:
            m1 += 1
            out[pos + 1:pos + 2 * n:2] = [body[i]] * len(range(pos + 1, min(pos + 2 * n, total), 2))
            i += 1
        elif m == 2:
            out[pos:pos + n] = list(body[i:i + n])
            i += n
        pos += span
    return out[:total], i, pos, cross, m1


def split_rows(body: bytes, w: int, h: int) -> list[bytes]:
    """原串流依控制位元組的起點切成每列的 bytes(已確認沒有跨列)。"""
    rows = [bytearray() for _ in range(h)]
    i = pos = 0
    while pos < w * h and i < len(body):
        s = i
        c = body[i]
        i += 1
        m, n = c >> 6, (c & 63) + 1
        i += 1 if m in (0, 1) else n if m == 2 else 0
        rows[pos // w] += body[s:i]
        pos += 2 * n if m == 1 else n
    return [bytes(r) for r in rows]


# ================= 編碼 =================
POLICY = {
    "run_min": 3,                 # R1 同色連續 >= 3 個 → 模式 0;較短的併入 literal
    "pair_as_run": True,          # R2 整段 literal 只有兩個同色像素 → 模式 0(n = 2)
    "mode1": True,                # R3 單一透明 + 單像素 literal → 模式 1(先跳過再寫)
    "mode1_at_row_end": False,    # R4 那個像素是列尾最後一個時不用模式 1
    "after_mode1_same": "merge",  # R5a 緊接在模式 1 後、同一個值 → 併進前一個(n 加 1)
    "after_mode1_full": "new",    # R5b 前一個模式 1 已滿 64 → 開新的模式 1
    "after_mode1_diff": "no",     # R5c 緊接在模式 1 後、不同值 → 不用模式 1
    "run_leftover_to_literal": True,             # R6 同色 run 切掉 64 的整段後,剩下不到 3 個 → 併入 literal
}
RULES = {
    "R1_run_min_3": "同色連續 3 個以上用模式 0,1 ~ 2 個併入 literal",
    "R2_pair_as_run": "flush 時整段 literal 剛好是兩個同色像素 → 模式 0(n = 2)",
    "R3_mode1": "單一透明像素後接單像素 literal → 模式 1(n = 1)",
    "R4_not_at_row_end": "那個像素是列尾最後一個像素時不用模式 1",
    "R5a_after_mode1_same": "緊接在模式 1 之後、同一個值 → 併進前一個模式 1(n 加 1)",
    "R5b_after_mode1_full": "前一個模式 1 已滿 64 → 開新的模式 1",
    "R5c_after_mode1_diff": "緊接在模式 1 之後、不同值 → 不用模式 1(透明與像素各自輸出)",
    "R6_run_leftover": "同色 run 長過 64:先輸出 64 的整段,剩下 3 個以上仍是模式 0,不到 3 個併入下一段 literal",
}


def enc_row(r: tuple[int, ...], pol: dict) -> bytes:
    """一列像素 → 四模式 RLE bytes(依 pol 的規則)。"""
    w = len(r)
    ops: list[tuple[int, int, list[int]]] = []
    lit: list[int] = []

    def flush() -> None:
        if not lit:
            return
        if pol["pair_as_run"] and len(lit) == 2 and lit[0] == lit[1]:
            ops.append((0, 2, [lit[0]]))
        else:
            for s in range(0, len(lit), CAP):
                ops.append((2, len(lit[s:s + CAP]), lit[s:s + CAP]))
        lit.clear()

    x = 0
    while x < w:
        v = r[x]
        e = x
        while e < w and r[e] == v:
            e += 1
        n = e - x
        if v == T:
            flush()
            while n:
                k = min(n, CAP)
                ops.append((3, k, []))
                n -= k
        elif n >= pol["run_min"]:
            flush()
            while n >= CAP:
                ops.append((0, CAP, [v]))
                n -= CAP
            if n >= pol["run_min"] or (n and not pol["run_leftover_to_literal"]):
                ops.append((0, n, [v]))
            else:
                lit.extend([v] * n)
        else:
            lit.extend([v] * n)
        x = e
    flush()
    out: list[tuple[int, int, list[int]]] = []
    x = 0
    for op in ops:
        span = 2 * op[1] if op[0] == 1 else op[1]
        cand = (pol["mode1"] and out and out[-1] == (3, 1, []) and op[0] == 2 and op[1] == 1
                and (pol["mode1_at_row_end"] or x + 1 < w))
        prev1 = len(out) >= 2 and out[-2][0] == 1
        if cand and prev1:
            if out[-2][2] != op[2]:
                choice = pol["after_mode1_diff"]
            elif out[-2][1] < CAP:
                choice = pol["after_mode1_same"]
            else:
                choice = pol["after_mode1_full"]
            if choice == "merge":
                out.pop()
                out[-1] = (1, out[-1][1] + 1, op[2])
            elif choice == "new":
                out[-1] = (1, 1, op[2])
            else:
                out.append(op)
        elif cand:
            out[-1] = (1, 1, op[2])
        else:
            out.append(op)
        x += span
    b = bytearray()
    for m, n, pay in out:
        assert 1 <= n <= CAP, (m, n)
        b.append((m << 6) | (n - 1))
        b.extend(pay)
    return bytes(b)


# ================= (A) 語料 =================
def frame_container(d: bytes) -> tuple[int, list[tuple[int, int, bytes]]] | None:
    """FIGANI / FDOTHER 的幀容器:+0 u8 幀數、+1 u8 旗標、+8 u32[幀數] 位移;每幀 13-byte 標頭(+9 u16 w、+11 u16 h)。"""
    if len(d) < 12:
        return None
    o0 = struct.unpack_from("<I", d, 8)[0]
    if o0 < 12 or (o0 - 8) % 4 or o0 > len(d) or d[0] != (o0 - 8) // 4:
        return None
    nf = d[0]
    offs = [struct.unpack_from("<I", d, 8 + 4 * k)[0] for k in range(nf)] + [len(d)]
    if any(a + 13 > b for a, b in zip(offs, offs[1:])):
        return None
    return d[1], [struct.unpack_from("<HH", d, offs[k] + 9) + (d[offs[k] + 13:offs[k + 1]],) for k in range(nf)]


CORPUS: dict[str, list[tuple[str, int, int, bytes]]] = {}
CONTAINER: dict[str, dict] = {}

# FDICON:位移表 count + 1 筆,最後一筆是檔長
_d = FDICON.read_bytes()
_w, _h, _n = struct.unpack_from("<HHH", _d, 0)
_off = [struct.unpack_from("<I", _d, 6 + 4 * k)[0] for k in range(_n + 1)]
assert (_w, _h, _n) == (24, 24, 1680) and _off[0] == 6 + 4 * (_n + 1) and _off[_n] == len(_d), (_w, _h, _n, _off[0], _off[-1])
CORPUS["FDICON"] = [(f"FDICON.B24#{k}", 24, 24, _d[_off[k]:_off[k + 1]]) for k in range(_n)]
FDICON_FIRST = _off[0]
assert FDICON_FIRST == 6730 == 6 + 4 * 1681, FDICON_FIRST
CONTAINER["FDICON"] = {"file": rel(FDICON), "offset_entries": "count + 1(最後一筆 = 檔長)", "first_offset": FDICON_FIRST}

# FDSHAP:偶數號是 24×24 圖塊庫(奇數號是地形控制表);位移表 count 筆
_shp, _dup, _seen = [], {}, {}
for p in sorted((RAW / "FDSHAP").glob("FDSHAP_*.bin")):
    d = p.read_bytes()
    if len(d) < 6 or struct.unpack_from("<HH", d, 0) != (24, 24):
        continue
    _shp.append(p.name)
    if d in _seen:
        _dup[p.name] = _seen[d]
        continue
    _seen[d] = p.name
    n = struct.unpack_from("<H", d, 4)[0]
    off = [struct.unpack_from("<I", d, 6 + 4 * k)[0] for k in range(n)] + [len(d)]
    assert off[0] == 6 + 4 * n, (p.name, off[0], n)
    CORPUS.setdefault("FDSHAP", []).extend((f"{p.name}#{k}", 24, 24, d[off[k]:off[k + 1]]) for k in range(n))
assert _shp == [f"FDSHAP_{2 * m:03d}.bin" for m in range(33)], _shp
assert _dup == {"FDSHAP_060.bin": "FDSHAP_020.bin"}, _dup
CONTAINER["FDSHAP"] = {"files": f"FDSHAP_000 ~ FDSHAP_064 偶數號 {len(_shp)} 份", "duplicate_files": _dup,
                       "offset_entries": "count(第一筆 = 6 + 4 × count)"}

# FIGANI / FDOTHER:幀容器;不是幀容器的檔案逐類計數
for kind in ("FIGANI", "FDOTHER"):
    files = sorted((RAW / kind).glob(f"{kind}_*.bin"))
    flags, other = collections.Counter(), collections.Counter()
    for p in files:
        d = p.read_bytes()
        fc = frame_container(d)
        if fc is None:
            other["empty" if not d else "3_bytes_00000a" if d == b"\x00\x00\x0a" else "other_format"] += 1
            continue
        flags[fc[0]] += 1
        CORPUS.setdefault(kind, []).extend((f"{p.name}#{k}", w, h, b) for k, (w, h, b) in enumerate(fc[1]))
    CONTAINER[kind] = {"files": len(files), "frame_containers_by_flag_byte": dict(sorted(flags.items())),
                       "not_frame_container": dict(sorted(other.items()))}
assert CONTAINER["FIGANI"]["files"] == 409 and CONTAINER["FIGANI"]["frame_containers_by_flag_byte"] == {0: 249, 1: 15}, CONTAINER
assert CONTAINER["FIGANI"]["not_frame_container"] == {"3_bytes_00000a": 144, "empty": 1}, CONTAINER["FIGANI"]
assert CONTAINER["FDOTHER"]["files"] == 104 and CONTAINER["FDOTHER"]["frame_containers_by_flag_byte"] == {0: 28}, CONTAINER
assert CONTAINER["FDOTHER"]["not_frame_container"] == {"empty": 1, "other_format": 75}, CONTAINER["FDOTHER"]
assert all(w > 0 and h > 0 for lst in CORPUS.values() for _, w, h, _ in lst)

# 解一次,留下每列像素與原串流每列的 bytes
DEC: dict[str, list[tuple[list[tuple[int, ...]], list[bytes]]]] = {}
A: dict[str, dict] = {}
for name, lst in CORPUS.items():
    rows_all, st = [], collections.Counter()
    for label, w, h, body in lst:
        px, used, pos, cross, m1 = walk(body, w, w * h)
        st["exact_consume"] += used == len(body) and pos == w * h
        st["cross_row_ops"] += cross
        st["mode1_ops"] += m1
        st["items_with_mode1"] += m1 > 0
        st["pixels"] += w * h
        rows_all.append(([tuple(px[y * w:(y + 1) * w]) for y in range(h)], split_rows(body, w, h)))
    DEC[name] = rows_all
    A[name] = {"items": len(lst), "unique_streams": len({b for *_, b in lst}), **dict(st)}
for name, v in A.items():
    assert v["exact_consume"] == v["items"] and v["cross_row_ops"] == 0, (name, v)
ITEMS = {k: v["items"] for k, v in A.items()}
assert ITEMS == {"FDICON": 1680, "FDSHAP": 8064, "FIGANI": 2118, "FDOTHER": 701}, ITEMS
STATS = {k: (v["unique_streams"], v["mode1_ops"], v["items_with_mode1"], v["pixels"]) for k, v in A.items()}
assert STATS == {"FDICON": (1332, 818, 450, 967680), "FDSHAP": (2985, 330, 107, 4644864),
                 "FIGANI": (1752, 89948, 1882, 47928212), "FDOTHER": (476, 3064, 255, 6138370)}, STATS


# ================= (B) 編回去 =================
def misses(pol: dict) -> dict[str, int]:
    """每個語料有幾個串流編不回原樣(逐列比對;同一列像素只編一次)。"""
    cache: dict[tuple[int, ...], bytes] = {}
    res = {}
    for name, rows_all in DEC.items():
        bad = 0
        for rows, orig in rows_all:
            for r, o in zip(rows, orig):
                e = cache.get(r)
                if e is None:
                    e = cache[r] = enc_row(r, pol)
                if e != o:
                    bad += 1
                    break
        res[name] = bad
    return res


FULL = misses(POLICY)
assert FULL == {"FDICON": 0, "FDSHAP": 0, "FIGANI": 0, "FDOTHER": 0}, FULL
# 整串再接起來比一次(不只逐列):每個串流 = 各列編碼直接相接
_joined_ok = sum(b"".join(enc_row(r, POLICY) for r in rows) == b"".join(orig)
                 for rows_all in DEC.values() for rows, orig in rows_all)
_joined_src = sum(b"".join(orig) == body for name, lst in CORPUS.items() for (rows, orig), (*_, body) in zip(DEC[name], lst))
assert _joined_ok == _joined_src == sum(ITEMS.values()), (_joined_ok, _joined_src)

VARIANTS = {
    "R1_run_min_2": {"run_min": 2},
    "R1_run_min_4": {"run_min": 4},
    "R2_off": {"pair_as_run": False},
    "R3_off": {"mode1": False},
    "R4_allow_at_row_end": {"mode1_at_row_end": True},
    "R5a_same_as_new": {"after_mode1_same": "new"},
    "R5a_same_as_no": {"after_mode1_same": "no"},
    "R5b_full_as_no": {"after_mode1_full": "no"},
    "R5c_diff_as_new": {"after_mode1_diff": "new"},
    "R6_leftover_as_run": {"run_leftover_to_literal": False},
}
ABL = {k: misses({**POLICY, **v}) for k, v in VARIANTS.items()}
assert all(sum(v.values()) > 0 for v in ABL.values()), ABL
assert ABL == {
    "R1_run_min_2": {"FDICON": 1455, "FDSHAP": 6634, "FIGANI": 2077, "FDOTHER": 654},
    "R1_run_min_4": {"FDICON": 1455, "FDSHAP": 6465, "FIGANI": 2077, "FDOTHER": 578},
    "R2_off": {"FDICON": 1014, "FDSHAP": 2272, "FIGANI": 2049, "FDOTHER": 490},
    "R3_off": {"FDICON": 450, "FDSHAP": 107, "FIGANI": 1882, "FDOTHER": 255},
    "R4_allow_at_row_end": {"FDICON": 32, "FDSHAP": 1, "FIGANI": 603, "FDOTHER": 71},
    "R5a_same_as_new": {"FDICON": 0, "FDSHAP": 5, "FIGANI": 1639, "FDOTHER": 29},
    "R5a_same_as_no": {"FDICON": 0, "FDSHAP": 5, "FIGANI": 1639, "FDOTHER": 29},
    "R5b_full_as_no": {"FDICON": 0, "FDSHAP": 0, "FIGANI": 70, "FDOTHER": 0},
    "R5c_diff_as_new": {"FDICON": 0, "FDSHAP": 31, "FIGANI": 677, "FDOTHER": 37},
    "R6_leftover_as_run": {"FDICON": 0, "FDSHAP": 0, "FIGANI": 137, "FDOTHER": 18}}, ABL
# R3 關掉時編不回去的,剛好是含模式 1 的串流
assert ABL["R3_off"] == {k: v["items_with_mode1"] for k, v in A.items()}, ABL["R3_off"]


# ================= (C) 對照 =================
def m1_payload_control() -> dict[str, dict[str, list[int]]]:
    """含 / 不含模式 1 的串流各:[個數, 正確解法剛好吃完的個數, 模式 1 當 literal 解剛好吃完的個數]。

    兩種解法走同一段計數,所以「當 literal 吃不完」的 0 與「正確解法全部吃完」一起成立才算數。
    """
    res = {}
    for name, lst in CORPUS.items():
        cnt = {"with_mode1": [0, 0, 0], "without_mode1": [0, 0, 0]}
        for _, w, h, body in lst:
            for k, lit in enumerate((False, True), 1):
                _, used, pos, _, m1 = walk(body, w, w * h, mode1_literal=lit)
                if k == 1:
                    row = cnt["with_mode1" if m1 else "without_mode1"]
                    row[0] += 1
                row[k] += used == len(body) and pos == w * h
        res[name] = cnt
    return res


M1LIT = m1_payload_control()
assert all(M1LIT[k] == {"with_mode1": [A[k]["items_with_mode1"]] * 2 + [0],
                        "without_mode1": [ITEMS[k] - A[k]["items_with_mode1"]] * 3} for k in ITEMS), M1LIT
assert {k: v["without_mode1"][0] for k, v in M1LIT.items()} == {"FDICON": 1230, "FDSHAP": 7957, "FIGANI": 236, "FDOTHER": 446}, M1LIT


def cross_at(dw: int) -> dict[str, int]:
    """寬度錯 dw 欄(高度照總像素數不變的前提下只看跨列)時,有跨列控制位元組的串流數。"""
    res = {}
    for name, lst in CORPUS.items():
        res[name] = sum(walk(body, w + dw, w * h)[3] > 0 for _, w, h, body in lst if w + dw > 0)
    return res


XW = {str(dw): cross_at(dw) for dw in (-1, 1)}
assert all(v > 0 for d in XW.values() for v in d.values()), XW
assert XW == {"-1": {"FDICON": 1680, "FDSHAP": 8062, "FIGANI": 2118, "FDOTHER": 683},
              "1": {"FDICON": 1680, "FDSHAP": 8062, "FIGANI": 2118, "FDOTHER": 683}}, XW

ev = {"note": "FD2.EXE md5 33464c81e6a364fd0660141139aa8e6e 的資產:FDICON.B24(原版遊戲目錄)與 extracted/raw 的 FDSHAP / FIGANI / FDOTHER。"
              "STATIC ANALYSIS(資產解析):解碼後用逐列編碼器編回,逐 byte 比對。",
      "A_streams": {"containers": CONTAINER, "per_corpus": A,
                    "finding": "每個串流線性解碼都剛好吃完、剛好填滿 w×h,沒有一個控制位元組跨過列尾。"},
      "B_encoder": {"rules": RULES, "policy": POLICY, "misses_full_policy": FULL,
                    "misses_with_one_rule_changed": ABL,
                    "finding": "6 條規則(R5 分三個子規則)的逐列編碼器把 4 種資源的全部串流逐 byte 編回原樣;任一條規則改掉都會有串流編不回去。"
                               "列寬不超過 64 的 FDICON / FDSHAP 碰不到 64 上限,R5b 與 R6 只由 FIGANI / FDOTHER 驗到。"},
      "C_controls": {"mode1_payload_[items,exact_correct,exact_as_literal]": M1LIT,
                     "streams_with_cross_row_ops_at_wrong_width": XW,
                     "finding": "模式 1 只帶 1 個值 byte:當成 literal 解,含模式 1 的串流沒有一個能剛好吃完(不含的全部不受影響)。"
                                "寬度錯一欄,每個語料都出現跨列的控制位元組。"},
      "conclusion": "STATIC ANALYSIS:四模式 RLE 的文法(含模式 1 的 1-byte 負載)與原編碼器的選擇規則都已完整 —— "
                    "FDICON 1680、FDSHAP 8064、FIGANI 2118 幀、FDOTHER 701 幀全部逐 byte 重現。"
                    "模式 1 的「先跳過再寫」次序不由本檢查決定(只看 bytes 分不出來),仍以續一百三十四 / 一百三十五的 EXE 與 VGA 證據為準。"}
OUT.write_bytes((json.dumps(ev, ensure_ascii=False, indent=1) + "\n").encode("utf-8"))
print("ok", ITEMS, FULL)
