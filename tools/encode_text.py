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
    print(__doc__); return 1


if __name__ == "__main__":
    sys.exit(main(sys.argv))
