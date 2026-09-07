#!/usr/bin/env python3
"""炎龍騎士團2 — Unicode → glyph 反向編碼(供中文化重打文本)。

讀 `docs/data/glyph_map.json`(glyph→字元),建反向表(字元→glyph 索引)。
- 重複字元(多個 glyph 對同一字)取**最小索引**為正則。
- 雙字元代號 / 數字字模(如 73/C2/11)以「整體符號」收錄(整串對一個 glyph)。

功能:
  1. 匯出反向表 `docs/data/unicode_to_glyph.json`。
  2. 把一段 UTF-8 中文編成 glyph 索引(uint16 LE)序列 → 可寫回 FDTXT。
  3. round-trip 驗證:FDTXT 字串 → 解碼文字 → 重新編碼 → 比對 glyph 序列。

控制碼(對話框 / 換行)沿用原值,不在本表內(見 14-text-control-codes)。

用法:
    python3 encode_text.py revtable                       # 產生反向表 JSON
    python3 encode_text.py encode "中文字串"               # 印 glyph 索引序列
    python3 encode_text.py roundtrip <FDTXT_NNN.bin>       # 驗證可逆性
    python3 encode_text.py runs <FDTXT_NNN.bin>            # 列出可回寫的文字段(見下)
    python3 encode_text.py writeback <in.bin> <edits.json> <out.bin>   # 實際回寫
    python3 encode_text.py selftest <FDTXT目錄>            # 驗證回寫(見下)

2026-09-07 新增 `runs` / `writeback`(worklist 431)。在此之前本檔的 docstring 只寫
「可寫回 FDTXT」,但**沒有任何真的寫檔的子命令**——`encode` 只把索引印在畫面上。

**回寫的定址單位是「文字段(run)」,不是整條字串。** 一條 FDTXT 字串是 glyph 與控制碼
交錯的序列;若讓使用者提供「整條字串的新文字」,控制碼(開框、換行、說話者 operand)
要嘛被抹掉、要嘛得靠猜的重新插回去。改成只替換**連續 glyph 的最長區段**,控制碼原封
不動逐一保留,是唯一不需要猜測的做法。`runs` 列出每個 run 的 `(string_index, run_index)`
座標與現有文字,`writeback` 吃這組座標:

    {"edits":[{"string_index":3,"run_index":1,"text":"新的台詞"}]}

**容器重建是逐字節精確的**:2026-09-07 實測把 35 個 FDTXT 全部「解析→不改任何東西→
重新序列化」,35/35 與原檔 byte-identical,代表次目錄與 0xFFFF 終結子的佈局已完全掌握,
沒有 padding 或空隙需要保留。這也讓 selftest 的「零編輯必須產生相同檔案」成為一個真的
在測序列化器的檢查,而不是把原始 bytes 抄一遍的空轉。

**定址陷阱(2026-09-07 實作時實地踩到,務必先跑 `runs` 看過再編輯)**:說話者 operand
和開/關引號『』的 glyph id 都 < 0xFF00,所以它們**跟對白正文在同一個 run 裡**。
一個框的第一個 run 長這樣:`0『累死了，`——開頭的 `0` 是說話者 ID、不是文字。
直接把整個 run 換掉會連說話者一起洗掉。安全做法是照 `runs` 印出來的原文,把要保留的
`『』` 和說話者字元一起打進新文字裡(實測 `　休息一下大家吧！』` 可正確回寫)。
本工具**不自動剝除**這些字元:哪個字是標點、哪個是說話者 ID,取決於這個 run 在框裡的
位置,自動判斷就是在猜——而猜錯會產生「看起來正常的壞檔」。

**兩個硬性拒絕條件**(寧可中止也不產生壞檔):
  1. 次目錄的位移是 **uint16**,重建後檔案超過 65535 byte 就無法定址 → 中止。
  2. 新文字含 glyph_map 沒有的字元 → 中止,不靜默丟字(`encode()` 的 unknown 清單)。

**本工具不驗證 glyph_map 是否對**(理由同下面 roundtrip 那段警語):回寫用的是同一份表,
表若錯,寫回去的字就錯,而所有 round-trip 檢查照樣會通過。

> **2026-09-03 全工具驗證:`roundtrip` 不能用來證明 glyph_map 是對的。**
> 它用同一份 glyph_map 同時建 g2c(解碼)與 c2g(編碼),所以「解碼→再編碼→再解碼」
> 這個恆等式在任何**自洽**的表上都成立,包含錯的表。實測:把 glyph 500-599 的
> 值整段輪轉一格後,decode_story_text 的劇情文字明顯壞掉(「很快就到了。」變成
> 「很快就到了極」、「帶著我」變成「帶著們」),但 35 個 FDTXT 資源的 roundtrip
> 仍然全數回報一致(35/35)。
>
> 它真正證明的是「這份表在 encode/decode 之間可逆」,不是「這份表對應到正確的字」。
> 要驗證正確性,只能回到字模點陣本身(見 commit a1851a76 的 pixel-IoU 方法)或
> 外部 ground truth。同理,`revtable` 產生的 unicode_to_glyph.json 也不被本檢查覆蓋
> ——它根本不讀那個檔;那份反向表要另外與 glyph_map 逐條比對(2026-09-03 已修:
> 該檔停留在 a1851a76 修正前的舊值,751 條索引錯位)。
"""
import sys
import os
import json
import struct

if hasattr(sys.stdout, "reconfigure"):
    sys.stdout.reconfigure(encoding="utf-8")
    sys.stderr.reconfigure(encoding="utf-8")   # 中止訊息也要看得懂,不能只顧 stdout

HERE = os.path.dirname(__file__)
MAP = os.path.join(HERE, "..", "docs", "data", "glyph_map.json")


def load_maps():
    m = json.load(open(MAP, encoding="utf-8"))
    g2c = {int(k): v for k, v in m.items() if k != "_comment"}
    c2g = {}
    for idx in sorted(g2c):          # 由小到大 → 取最小索引為正則
        ch = g2c[idx]
        if ch in ("□",) or ch == " ":
            continue
        c2g.setdefault(ch, idx)
    return g2c, c2g


def encode(text, c2g):
    """回傳 (glyph_indices, unknown_chars)。多字元 token(代號)需整體匹配。"""
    # 收集多字元 token(長度>1 的對映,如 '73''C2')
    multi = sorted((k for k in c2g if len(k) > 1), key=len, reverse=True)
    out = []
    unknown = []
    i = 0
    while i < len(text):
        matched = False
        for tok in multi:                       # 先試多字元代號
            if text.startswith(tok, i):
                out.append(c2g[tok]); i += len(tok); matched = True; break
        if matched:
            continue
        ch = text[i]; i += 1
        if ch in c2g:
            out.append(c2g[ch])
        elif ch in ("\n", "\r", "　"):
            continue
        else:
            unknown.append(ch)
    return out, unknown


CTRL_MIN = 0xFF00
STR_END = 0xFFFF
MAX_FILE = 0x10000       # 次目錄位移是 uint16


def split_runs(codes):
    """回傳這條字串裡連續 glyph 的最長區段 [(start, end_exclusive), …]。"""
    runs = []
    i = 0
    while i < len(codes):
        if codes[i] >= CTRL_MIN:
            i += 1
            continue
        j = i
        while j < len(codes) and codes[j] < CTRL_MIN:
            j += 1
        runs.append((i, j))
        i = j
    return runs


def serialize(strings):
    """次目錄 + 各字串(每條以 0xFFFF 結尾)。與 decode_text.parse_strings 互為逆運算。"""
    out = bytearray(struct.pack("<H", 0) * len(strings))
    for i, s in enumerate(strings):
        # 上限**必須在寫次目錄之前逐條檢查**,不能等全部組完再看總長度:第一版就是那樣寫的,
        # 結果 selftest(5) 抓到 pack_into 會先丟出裸 struct.error('H' format requires…),
        # 使用者看到的是 traceback 而不是「請縮短新文字」。
        if len(out) > MAX_FILE - 2:
            raise SystemExit(f"重建到第 {i} 條字串時已達 {len(out)} byte,超過 uint16 次目錄"
                             f"可定址的 {MAX_FILE} byte,中止不寫檔——請縮短新文字")
        struct.pack_into("<H", out, 2 * i, len(out))
        for c in s:
            out += struct.pack("<H", c)
        out += struct.pack("<H", STR_END)
    if len(out) > MAX_FILE:
        raise SystemExit(f"重建後 {len(out)} byte 超過 uint16 次目錄可定址的 {MAX_FILE} byte,"
                         "中止不寫檔——請縮短新文字")
    return bytes(out)


def apply_edits(strings, edits, c2g, _offset_bug=0):
    """把 edits 套進 strings(不就地修改)。`_offset_bug` 僅供故障注入。"""
    out = [list(s) for s in strings]
    for e in edits:
        si, ri, text = e["string_index"], e["run_index"], e["text"]
        if not 0 <= si < len(out):
            raise SystemExit(f"string_index {si} 超出範圍(共 {len(out)} 條字串)")
        runs = split_runs(out[si])
        if not 0 <= ri < len(runs):
            raise SystemExit(f"string[{si}] 只有 {len(runs)} 個文字段,run_index {ri} 超出範圍")
        idxs, unk = encode(text, c2g)
        if unk:
            raise SystemExit(f"string[{si}].run[{ri}] 有 {len(unk)} 個字元在 glyph_map 內"
                             f"找不到對應字模:{''.join(sorted(set(unk)))} — 中止不寫檔"
                             "(需先擴字型,不會靜默丟字)")
        s, t = runs[ri]
        out[si][s + _offset_bug:t] = idxs
    return out


def list_runs(path, g2c):
    sys.path.insert(0, HERE)
    from decode_text import parse_strings
    rows = []
    for si, codes in enumerate(parse_strings(path)):
        for ri, (s, t) in enumerate(split_runs(codes)):
            rows.append({"string_index": si, "run_index": ri,
                         "text": "".join(g2c.get(c, f"〈{c}〉") for c in codes[s:t])})
    return rows


def main(argv):
    if len(argv) < 2:
        print(__doc__); return 1
    g2c, c2g = load_maps()
    if argv[1] == "revtable":
        out = os.path.join(HERE, "..", "docs", "data", "unicode_to_glyph.json")
        # 以 codepoint 排序輸出
        obj = {"_comment": "炎龍騎士團2 Unicode→glyph 反向表(中文化重打用)。重複字取最小 glyph 索引;多字元 key 為代號/數字字模(整體符號)。",
               **{k: c2g[k] for k in sorted(c2g)}}
        json.dump(obj, open(out, "w", encoding="utf-8"), ensure_ascii=False, indent=0)
        print(f"反向表 {len(c2g)} 條 -> {out}")
        return 0
    if argv[1] == "encode":
        idxs, unk = encode(argv[2], c2g)
        print("glyph 索引:", idxs)
        print("uint16 LE bytes:", b"".join(struct.pack("<H", x) for x in idxs).hex())
        if unk:
            print("⚠ 無對應字元(需先擴字型):", "".join(sorted(set(unk))))
        return 0
    if argv[1] == "roundtrip":
        sys.path.insert(0, HERE)
        from decode_text import parse_strings
        ok = tot = 0
        for codes in parse_strings(argv[2]):
            # 取出純 glyph(去控制碼)
            glyphs = [c for c in codes if c < 0xFF00]
            text = "".join(g2c.get(c, "") for c in glyphs)
            re_idx, unk = encode(text, c2g)
            tot += 1
            # 比對:重新編碼的字元串 == 原字元串(允許重複字落到不同 index)
            re_text = "".join(g2c.get(c, "") for c in re_idx)
            if re_text == text and not unk:
                ok += 1
            else:
                if tot <= 3:
                    print(f"  差異: 原[{text[:30]}] vs 重編[{re_text[:30]}] unk={unk}")
        print(f"round-trip 文字一致: {ok}/{tot} 字串")
        return 0
    if argv[1] == "runs":
        rows = list_runs(argv[2], g2c)
        for r in rows:
            print(f"  [{r['string_index']:>4}.{r['run_index']}] {r['text']}")
        print(f"{len(rows)} 個可回寫文字段")
        return 0
    if argv[1] == "writeback":
        sys.path.insert(0, HERE)
        from decode_text import parse_strings
        src, edits_path, out = argv[2], argv[3], argv[4]
        with open(edits_path, encoding="utf-8") as f:
            edits = json.load(f)["edits"]
        data = serialize(apply_edits(parse_strings(src), edits, c2g))
        with open(out, "wb") as f:
            f.write(data)
        print(f"套用 {len(edits)} 筆編輯 -> {out}({len(data)} byte)")
        return 0
    if argv[1] == "selftest":
        return selftest(argv[2], g2c, c2g)
    print(__doc__); return 1


def selftest(src, g2c, c2g):
    """見模組 docstring。5 項:1 個恆等、1 個真實回寫、3 個反向控制。"""
    import glob
    sys.path.insert(0, HERE)
    from decode_text import parse_strings
    paths = sorted(glob.glob(os.path.join(src, "*.bin"))) if os.path.isdir(src) else [src]
    fails = []

    print(f"(1) 零編輯:完整重新序列化必須與原檔 byte-identical({len(paths)} 檔)")
    bad = [os.path.basename(p) for p in paths
           if serialize(apply_edits(parse_strings(p), [], c2g)) != open(p, "rb").read()]
    print(f"    {'PASS' if not bad else 'FAIL'}: {len(paths) - len(bad)}/{len(paths)}"
          + (f" 不符={bad[:5]}" if bad else ""))
    if bad:
        fails.append(f"零編輯重建與原檔不同:{bad[:5]}")

    print("\n(2) 真實回寫:把某段文字寫進另一段,重讀後該段等於新文字、其餘各段逐碼不變")
    # 用檔案內既有的文字當新內容,保證一定編得出來(不會被未知字元擋掉,那是另一項檢查)。
    victim = next((p for p in paths if len(list_runs(p, g2c)) >= 2), None)
    if victim is None:
        fails.append("找不到含 2 個以上文字段的 FDTXT,無法測回寫")
        print("    FAIL: 無可用檔案")
    else:
        orig = parse_strings(victim)
        rows = list_runs(victim, g2c)
        src_row = next(r for r in rows if r["text"].strip())
        dst_row = next(r for r in rows if r is not src_row and r["text"].strip())
        new = apply_edits(orig, [{"string_index": dst_row["string_index"],
                                  "run_index": dst_row["run_index"],
                                  "text": src_row["text"]}], c2g)
        tmp = os.path.join(HERE, "..", ".wsl_build", "_encode_selftest.bin")
        os.makedirs(os.path.dirname(tmp), exist_ok=True)
        open(tmp, "wb").write(serialize(new))
        back = list_runs(tmp, g2c)
        got = next(r for r in back if r["string_index"] == dst_row["string_index"]
                   and r["run_index"] == dst_row["run_index"])
        # 重編碼會把重複字落到最小 glyph 索引,所以比對**文字**而非 glyph 碼。
        edited_ok = got["text"] == src_row["text"]
        # 其餘各段則是原碼逐一搬過去,可以、也應該用最嚴的逐碼比對。
        others_ok = all(
            n == o for i, (n, o) in enumerate(zip(new, orig))
            if i != dst_row["string_index"])
        print(f"    {'PASS' if edited_ok and others_ok else 'FAIL'}: "
              f"目標段={'改成新文字' if edited_ok else '沒改對'} / "
              f"其餘字串={'逐碼不變' if others_ok else '被動到了'}")
        if not edited_ok:
            fails.append(f"回寫後目標段是[{got['text'][:20]}],期望[{src_row['text'][:20]}]")
        if not others_ok:
            fails.append("回寫動到了不該動的字串")
        os.remove(tmp)

    print("\n(3) 故障注入:把 run 起點位移 1 個 code,檢查(1)必須失敗")
    p = paths[0]
    r0 = list_runs(p, g2c)[0]
    hurt = apply_edits(parse_strings(p), [{"string_index": r0["string_index"],
                                           "run_index": r0["run_index"],
                                           "text": r0["text"]}], c2g, _offset_bug=1)
    if serialize(hurt) == open(p, "rb").read():
        fails.append("位移注入後檔案仍與原檔相同——回寫根本沒作用在指定位置")
        print("    FAIL: 注入無效果")
    else:
        print("    PASS: 注入後如預期不同")

    print("\n(4) 未知字元必須中止,不靜默丟字")
    try:
        apply_edits(parse_strings(paths[0]), [{"string_index": 0, "run_index": 0,
                                               "text": "\U0001F600"}], c2g)
        fails.append("含未知字元的編輯沒有被拒絕")
        print("    FAIL: 沒擋下來")
    except SystemExit as ex:
        print(f"    PASS: 已拒絕({str(ex)[:40]}…)")

    print("\n(5) uint16 位移上限必須中止")
    try:
        serialize([[1] * 40000, [1] * 40000])
        fails.append("超過 uint16 可定址範圍的檔案沒有被拒絕")
        print("    FAIL: 沒擋下來")
    except SystemExit as ex:
        print(f"    PASS: 已拒絕({str(ex)[:40]}…)")

    if fails:
        print("\nSELFTEST FAILED:")
        for f in fails:
            print("  -", f)
        return 1
    print("\n--selftest passed(2 正向 + 3 反向)。")
    return 0


if __name__ == "__main__":
    sys.exit(main(sys.argv))
