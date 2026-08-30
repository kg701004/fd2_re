#!/usr/bin/env python3
"""用 glyph_map.json 把 FDTXT 章節解成 UTF-8 文字(含說話者)。

對話結構:[控制碼 0xFFxx][說話者肖像ID][『=558][對白…(夾雜 0xFFFE 換行)…][』=561],
0xFFFF 結束。開框碼 0xFFEC..0xFFEF 開新對話框;0xFFFE 是框內原生換行(內容作者手動
打入的斷句點,不是任何寬度估算的產物——見 docs/knowledge-base/91-worklist.md
2026-08-30 DATO 輪的量測結論與 18-font-modernization-utf8-ttf-plan.md 方案 A)。
說話者肖像 ID → 角色名(memory.md);>0x1F 的 NPC/敵以字模顯示。

2026-08-30 修正:OPEN/CLOSE 常數原本是 557/560,但 docs/data/glyph_map.json 目前
校正後的『/』實際 glyph id 是 558/561(557/560 現在分別是「值」「下」)。舊常數會讓
下面 decode_string() 的開框偵測(`seg[1] == OPEN`)永遠不成立,說話者永遠回傳 None、
說話者 ID 數字字面滲進內文——已用 glyph_map.json 直接查表核對修正。這個常數同時也
被 tools/export_story_index_map.py 的 OPEN_GLYPH 使用,該檔未動(範圍外,見
91-worklist.md 對應段落)。

用法:
    python3 decode_story_text.py <FDTXT_NNN.bin>                       # 印單章
    python3 decode_story_text.py --all <FDTXT目錄> <out.md>             # 全章合一檔
    python3 decode_story_text.py --add-lines <story.json> <FDTXT目錄>   # 補 lines[](見下)
"""
import sys
import os
import json
import glob

OPEN, CLOSE, END = 558, 561, 0xFFFF
OPEN_BOX = {0xFFEC, 0xFFED, 0xFFEE, 0xFFEF}  # 開對話框控制碼;0xFFFE(換行)、0xFFFD(翻頁)不開新框
PORT = {0: "索爾", 1: "哈諾", 2: "鐵諾", 3: "哈瓦特", 4: "亞雷斯", 5: "洛娜",
        6: "萊汀", 7: "蘭斯洛特", 8: "希莉亞", 9: "悠妮", 0xA: "瑪琳", 0xB: "索菲亞",
        0xC: "凱麗", 0xD: "貝克威", 0xE: "珊", 0xF: "賽可邦勒", 0x10: "凱拉斯",
        0x11: "米亞斯多德", 0x12: "蜜蒂", 0x13: "羅德曼", 0x14: "莎拉", 0x15: "約拿",
        0x16: "卡里斯", 0x17: "羅蘭", 0x18: "希爾法", 0x19: "謝多", 0x1A: "聖寇拉斯",
        0x1B: "巴拿羅西亞", 0x1C: "達克賽", 0x1D: "亞奇梅吉", 0x1E: "蓋亞", 0x1F: "渥德"}

sys.path.insert(0, os.path.dirname(__file__))
from decode_text import parse_strings

_GM = None
def gm():
    global _GM
    if _GM is None:
        d = os.path.join(os.path.dirname(__file__), "..", "docs", "data", "glyph_map.json")
        m = json.load(open(d, encoding="utf-8"))
        _GM = {int(k): v for k, v in m.items() if k != "_comment"}
    return _GM


def g2s(codes):
    m = gm()
    return "".join(m.get(c, f"〈{c}〉") for c in codes)


def decode_string(codes):
    """回傳 list of (speaker_or_None, lines)。

    lines 是同一個對話框內、依 0xFFFE 原生換行切開的字串陣列(至少 1 個元素);
    呼叫端要單句可自行 "".join(lines)。與舊版(逐控制碼切、回傳單一字串)的差異只在
    「同一框內的續行不再各自變成獨立的頂層項目」——框的邊界看的是「這段是不是接在開框
    控制碼(0xFFEC..0xFFEF)之後、且 seg[1]==OPEN(『)」,不是任何控制碼都算開框;
    0xFFFE(換行,含 0xFFFD 翻頁,目前不特別區分頁邊界)一律併進當前框的 lines。
    """
    if END in codes:
        codes = codes[:codes.index(END)]
    segs = []  # list of (leading_ctrl_or_None, code_list)
    cur = []
    leading = None
    for c in codes:
        if 0xFF00 <= c <= 0xFFFE:
            segs.append((leading, cur))
            cur = []
            leading = c
        else:
            cur.append(c)
    segs.append((leading, cur))

    out = []
    cur_speaker = None
    cur_lines = None
    for leading, seg in segs:
        if not seg:
            continue
        is_box_open = leading is None or leading in OPEN_BOX
        if is_box_open and len(seg) >= 2 and seg[1] == OPEN:
            spk = seg[0]
            name = PORT.get(spk, g2s([spk]))
            body = [c for c in seg[2:] if c not in (OPEN, CLOSE)]
            if cur_lines is not None:
                out.append((cur_speaker, cur_lines))
            cur_speaker, cur_lines = name, [g2s(body)]
        else:
            body = [c for c in seg if c not in (OPEN, CLOSE)]
            text = g2s(body)
            if cur_lines is None:
                # 防禦性 fallback(理論上不該發生,見不到開框段就先出現續行):
                # 沿用舊行為,獨立輸出一個 speaker=None 項目,不強行掛在不存在的框上。
                out.append((None, [text]))
            else:
                cur_lines.append(text)
    if cur_lines is not None:
        out.append((cur_speaker, cur_lines))
    return out


def render_chapter(path):
    lines = []
    for codes in parse_strings(path):
        for spk, box_lines in decode_string(codes):
            text = "".join(box_lines)
            if not text.strip():
                continue
            if spk:
                lines.append(f"- **{spk}**：{text}")
            else:
                lines.append(f"  {text}")
    return lines


def add_lines_to_story(story_path, raw_dir):
    """在 story JSON 每個 line 物件補上 "lines"(0xFFFE 原生斷行陣列),保留既有
    "text" 欄位不動(見 docs/knowledge-base/18-font-modernization-utf8-ttf-plan.md 方案 A)。

    對齊策略沿用 tools/export_story_index_map.py 的保守哲學:只有在 FDTXT 解出的
    對話框「總數」與 story JSON 的行「總數」完全相等時才逐一配對寫入,兩邊都是
    「一個框=一句對白」的順序流,不做任何內容比對猜測;數量對不上就整個中止、不寫檔。
    """
    with open(story_path, encoding="utf-8") as f:
        data = json.load(f)
    source_dat = data["source_dat"]
    raw_path = os.path.join(raw_dir, f"{source_dat}.bin")
    boxes = []
    for codes in parse_strings(raw_path):
        for _spk, box_lines in decode_string(codes):
            boxes.append(box_lines)

    json_lines = [ln for scene in data["scenes"] for ln in scene["lines"]]
    if len(boxes) != len(json_lines):
        raise SystemExit(
            f"count mismatch: {raw_path} decodes to {len(boxes)} dialogue box(es), "
            f"but {story_path} has {len(json_lines)} line(s) — count-aligned only, aborting without writing"
        )
    for box_lines, ln in zip(boxes, json_lines):
        ln["lines"] = box_lines

    with open(story_path, "w", encoding="utf-8") as f:
        json.dump(data, f, ensure_ascii=False, indent=1)
        f.write("\n")
    print(f"{story_path}: 補上 lines[] 至 {len(json_lines)} 句對白(source={source_dat})")


def main(argv):
    if len(argv) < 2:
        print(__doc__); return 1
    if argv[1] == "--add-lines":
        story_path, raw_dir = argv[2], argv[3]
        add_lines_to_story(story_path, raw_dir)
        return 0
    if argv[1] == "--all":
        src, out = argv[2], argv[3]
        with open(out, "w", encoding="utf-8") as f:
            f.write("# 炎龍騎士團2 — 全劇情自動解碼\n\n")
            f.write("> 由 FDTXT.DAT + glyph_map.json 自動解碼。遊戲著作權內容,僅本機對照用,不散布。\n\n")
            for p in sorted(glob.glob(os.path.join(src, "*.bin"))):
                base = os.path.splitext(os.path.basename(p))[0]
                ls = render_chapter(p)
                if not ls:
                    continue
                f.write(f"\n## {base}\n\n")
                f.write("\n".join(ls) + "\n")
        print(f"全章 -> {out}")
        return 0
    for ln in render_chapter(argv[1]):
        print(ln)
    return 0


if __name__ == "__main__":
    sys.exit(main(sys.argv))
