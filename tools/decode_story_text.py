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
    python3 decode_story_text.py --runtime-todo <FDTXT目錄> <out.json>  # 273 筆待解清單(見下)
"""
import sys
import os
import json
import glob
import re

OPEN, CLOSE, END = 558, 561, 0xFFFF
OPEN_BOX = {0xFFEC, 0xFFED, 0xFFEE, 0xFFEF}  # 開對話框控制碼;0xFFFE(換行)、0xFFFD(翻頁)不開新框
PORT = {0: "索爾", 1: "哈諾", 2: "鐵諾", 3: "哈瓦特", 4: "亞雷斯", 5: "洛娜",
        6: "萊汀", 7: "蘭斯洛特", 8: "希莉亞", 9: "悠妮", 0xA: "瑪琳", 0xB: "索菲亞",
        0xC: "凱麗", 0xD: "貝克威", 0xE: "珊", 0xF: "賽可邦勒", 0x10: "凱拉斯",
        0x11: "米亞斯多德", 0x12: "蜜蒂", 0x13: "羅德曼", 0x14: "莎拉", 0x15: "約拿",
        0x16: "卡里斯", 0x17: "羅蘭", 0x18: "希爾法", 0x19: "謝多", 0x1A: "聖寇拉斯",
        0x1B: "巴拿羅西亞", 0x1C: "達克賽", 0x1D: "亞奇梅吉", 0x1E: "蓋亞", 0x1F: "渥德"}

# 開框碼分兩類,operand 的語意**完全不同**(doc09「控制碼語意」節):
#   0xFFEF/0xFFEE — 開上/下框 + 載入 DATO;operand 走 0x12C60 身分查找 → 靜態可解。
#   0xFFED/0xFFEC — 開上/下框 + runtime unit lookup;operand 是**執行期 unit index**,
#                   最後讀該 record +7 當 DATO selector → 靜態**不可解**。
# 2026-09-04 之前這裡不看開框碼,四種一律查 PORT。doc09 用原版截圖抓到 ch01 王宮
# 兩句被標成索爾、實際是國王;全 FDTXT 量測顯示這種框有 273/1450(18.8%)。
IDENTITY_BOX = {0xFFEE, 0xFFEF}
RUNTIME_BOX = {0xFFEC, 0xFFED}


def resolve_speaker(leading, operand):
    """依開框碼解說話者。**靜態不可知時回報不可知,不猜名字。**

    這是本工具最容易產生「看起來正常的錯值」的地方:runtime-unit 框的 operand
    是小整數,拿去查 PORT 一定查得到某個角色名,結果毫無徵兆地錯。
    """
    if leading in RUNTIME_BOX:
        return f"unit#{operand}(執行期決定)"
    if leading in IDENTITY_BOX:
        return PORT.get(operand, g2s([operand]))
    # 前導控制碼不是開框碼(實測全 35 個 FDTXT 沒有這種框,但不假設它不會出現)
    return f"?#{operand}(開框碼 {'None' if leading is None else hex(leading)})"


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
            name = resolve_speaker(leading, spk)
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


_RUNTIME_SPK_RE = re.compile(r"^unit#(\d+)\(執行期決定\)$")


def find_runtime_todo(path):
    """列出這個 FDTXT 裡**說話者靜態不可解**的框(即 §doc09/B.6 記錄的 273/1450)。

    2026-09-05:為了讓 273 筆「靜態不可解」變成一份可以交給活體工具逐一解的清單,
    不重寫 `decode_string()`/`resolve_speaker()` 的判斷邏輯(核心解碼路徑不動,
    降低改壞既有 273/1450 統計的風險),只對 `render_chapter()` 已經產生的
    `unit#N(執行期決定)` 字串做後處理——這個字串格式本身就是 `resolve_speaker()`
    唯一的「不可解」輸出,拿它當比對目標不會漏判也不會多判。

    `box_index` 是這個 FDTXT 檔內、非空白框的 0-based 順序位置(跟 `render_chapter()`
    輸出的行序一致)——活體工具要靠這個序號在播放時數到第幾個對話框才是這一筆。
    """
    todo = []
    for idx, ln in enumerate(render_chapter(path)):
        # 每一行輸出剛好對應一個非空框(見 render_chapter 的 `if not text.strip(): continue`),
        # 所以用列舉序號當 box_index 不會因為跳過非說話者行而錯位——**不能**只對
        # 「- **」開頭的行計數,那樣會把純續行/無說話者框漏掉,box_index 就對不齊了。
        if not ln.startswith("- **"):
            continue
        m = _RUNTIME_SPK_RE.match(ln[4:].split("**：", 1)[0])
        if m:
            snippet = ln.split("：", 1)[1] if "：" in ln else ln
            todo.append({"box_index": idx, "operand": int(m.group(1)),
                        "text_snippet": snippet[:60]})
    return todo


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
    if argv[1] == "--runtime-todo":
        src, out = argv[2], argv[3]
        todo = []
        for p in sorted(glob.glob(os.path.join(src, "*.bin"))):
            base = os.path.splitext(os.path.basename(p))[0]
            for entry in find_runtime_todo(p):
                todo.append({"fdtxt": base, **entry})
        with open(out, "w", encoding="utf-8") as f:
            json.dump({"_meta": {"total": len(todo),
                                 "note": "operand 是執行期 unit roster slot,不是角色 id;"
                                         "box_index 是該 FDTXT 內第幾個非空對話框(0-based),"
                                         "須配合實際遊玩對到第幾框才能解出真正說話者"},
                      "todo": todo}, f, ensure_ascii=False, indent=1)
        print(f"{len(todo)} 筆執行期說話者待解 -> {out}")
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
