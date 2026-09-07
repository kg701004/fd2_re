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
    python3 decode_story_text.py --script-json <FDTXT目錄|檔> <out.json> # 機器可讀劇本(見下)
    python3 decode_story_text.py --selftest <FDTXT目錄>                 # 驗證上一項

2026-09-07 新增 `--script-json`(worklist 272/348)。`--all` 產出的是給人讀的 Markdown,
字串裡的 `- **名字**：` 前綴和換行都得靠正則再剖一次才能程式化使用;`--script-json`
輸出同一份解碼結果的結構化形式,每個對話框一筆:

    {"chapters":[{"fdtxt":"FDTXT_001","boxes":[
       {"box_index":0,"string_index":0,"speaker":"索爾","speaker_kind":"identity",
        "operand":0,"lines":["…","…"]}, …]}]}

`speaker_kind` 把 `resolve_speaker()` 的三種輸出明確分開,**不讓呼叫端拿字串猜**:
`identity`(靜態可解)/`runtime`(執行期 unit,operand 不是角色 id,見 doc09 B.6)/
`unmatched`(前導碼不是開框碼)/`none`(續行框,無說話者)。`string_index` 是這個框
所屬字串在 FDTXT 容器內的序號,可直接餵給 `tools/encode_text.py writeback` 定位回寫。

**驗證設計(`--selftest`)**:核心解碼路徑一行未動,新路徑與舊路徑共用 `decode_string()`,
所以自我比對會是廢的。真正有鑑別力的檢查是 (1) 把 script-json 依 `render_chapter()`
的格式重組回文字,必須與 `render_chapter()` 的輸出**逐行完全相同**——新舊兩條輸出路徑
的交叉核對;(2) `speaker_kind=="runtime"` 的框數必須等於 `--runtime-todo` 在同一檔
數出的筆數(兩個獨立實作的判定,一個看開框碼、一個比對字串格式);(3) 故障注入:
把說話者分類改壞後,(1) 必須失敗——證明檢查真的在測分類而不是恆真。

**`--selftest` 覆蓋不到的東西(2026-09-08 以資料側故障注入實測)**:把 FDTXT 副本裡
每個 glyph 值整體 +1 之後,本檔的 selftest **仍然全數通過**(對照組 `encode_text.py`
的 roundtrip 則會失敗)。原因是三項檢查全都是**兩條程式碼路徑之間的內部一致性**——
資料壞掉時兩邊等量地壞,於是仍然一致。所以它證明的是「新舊輸出路徑等價」,
**不是「解出來的字是對的」**。要驗證後者只能回到字模點陣本身或外部 ground truth
(與 `encode_text.py` 那段 2026-09-03 的 roundtrip 警語同一個道理)。
"""
import sys
import os
import json
import glob
import re

if hasattr(sys.stdout, "reconfigure"):
    sys.stdout.reconfigure(encoding="utf-8")
    sys.stderr.reconfigure(encoding="utf-8")   # 中止訊息也要看得懂,不能只顧 stdout

DEFAULT_FDTXT_DIR = os.path.join(os.path.dirname(__file__), "..", "extracted", "raw", "FDTXT")

OPEN, CLOSE, END = 558, 561, 0xFFFF
OPEN_BOX = {0xFFEC, 0xFFED, 0xFFEE, 0xFFEF}  # 開對話框控制碼;0xFFFE(換行)、0xFFFD(翻頁)不開新框
PORT = {0: "索爾", 1: "哈諾", 2: "鐵諾", 3: "哈瓦特", 4: "亞雷斯", 5: "洛娜",
        6: "萊汀", 7: "蘭斯洛特", 8: "希莉亞", 9: "悠妮", 0xA: "瑪琳", 0xB: "索菲亞",
        0xC: "凱麗", 0xD: "貝克威", 0xE: "珊", 0xF: "塞可邦勒", 0x10: "凱拉斯",
        0x11: "米亞斯多德", 0x12: "蜜蒂", 0x13: "羅德曼", 0x14: "莎拉", 0x15: "約拿",
        0x16: "卡里斯", 0x17: "羅蘭", 0x18: "希爾法", 0x19: "謝多", 0x1A: "聖寇拉斯",
        0x1B: "巴拿羅西亞", 0x1C: "達克塞", 0x1D: "亞齊梅吉", 0x1E: "蓋亞", 0x1F: "渥德"}

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


def decode_string(codes, with_meta=False):
    """回傳 list of (speaker_or_None, lines);`with_meta=True` 時每筆多帶 (leading, operand)。

    `with_meta` 是 2026-09-07 為 `--script-json` 加的,預設關閉、既有呼叫端行為完全不變。
    它存在的理由是**驗證獨立性**:如果 script-json 也像 `find_runtime_todo()` 那樣拿
    `resolve_speaker()` 產生的字串去比對正則來判斷「這框是不是執行期不可解」,那兩者就是
    同一個機制的兩次執行,互相比對證明不了任何事(見 memory「degenerate verification
    sample」)。改成直接回報**開框控制碼原值**,script-json 依控制碼分類、`--runtime-todo`
    依字串分類,兩個獨立判定的數量一致才是有鑑別力的交叉核對。

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
    cur_meta = (None, None)
    for leading, seg in segs:
        if not seg:
            continue
        is_box_open = leading is None or leading in OPEN_BOX
        if is_box_open and len(seg) >= 2 and seg[1] == OPEN:
            spk = seg[0]
            name = resolve_speaker(leading, spk)
            body = [c for c in seg[2:] if c not in (OPEN, CLOSE)]
            if cur_lines is not None:
                out.append((cur_speaker, cur_lines, cur_meta))
            cur_speaker, cur_lines, cur_meta = name, [g2s(body)], (leading, spk)
        else:
            body = [c for c in seg if c not in (OPEN, CLOSE)]
            text = g2s(body)
            if cur_lines is None:
                # 防禦性 fallback(理論上不該發生,見不到開框段就先出現續行):
                # 沿用舊行為,獨立輸出一個 speaker=None 項目,不強行掛在不存在的框上。
                out.append((None, [text], (None, None)))
            else:
                cur_lines.append(text)
    if cur_lines is not None:
        out.append((cur_speaker, cur_lines, cur_meta))
    if with_meta:
        return out
    return [(spk, lines) for spk, lines, _meta in out]


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


def speaker_kind(leading):
    """由**開框控制碼原值**分類說話者可解性(不看 resolve_speaker() 產生的字串)。"""
    if leading is None:
        return "none"
    if leading in RUNTIME_BOX:
        return "runtime"
    if leading in IDENTITY_BOX:
        return "identity"
    return "unmatched"


def script_boxes(path):
    """這個 FDTXT 的所有非空對話框,結構化形式。

    `box_index` 與 `render_chapter()` 的輸出行序、以及 `find_runtime_todo()` 的
    `box_index` 對齊——三者用同一條「跳過純空白框」的規則,不能各自為政。
    """
    boxes = []
    for si, codes in enumerate(parse_strings(path)):
        for spk, lines, (leading, operand) in decode_string(codes, with_meta=True):
            if not "".join(lines).strip():
                continue
            boxes.append({"box_index": len(boxes), "string_index": si,
                          "speaker": spk, "speaker_kind": speaker_kind(leading),
                          "operand": operand, "lines": lines})
    return boxes


def _fdtxt_paths(src):
    if os.path.isdir(src):
        return sorted(glob.glob(os.path.join(src, "*.bin")))
    return [src]


def write_script_json(src, out):
    chapters = []
    total = 0
    for p in _fdtxt_paths(src):
        boxes = script_boxes(p)
        if not boxes:
            continue
        total += len(boxes)
        chapters.append({"fdtxt": os.path.splitext(os.path.basename(p))[0], "boxes": boxes})
    obj = {"_meta": {
        "generator": "tools/decode_story_text.py --script-json",
        "total_boxes": total,
        "speaker_kind": {
            "identity": "開框碼 0xFFEE/0xFFEF,operand 走 0x12C60 身分查找,靜態可解",
            "runtime": "開框碼 0xFFEC/0xFFED,operand 是執行期 unit roster slot,"
                       "**不是角色 id**,靜態不可解(見 doc09 B.6)",
            "unmatched": "前導碼不是開框碼(實測 35 個 FDTXT 未出現,但不假設不會出現)",
            "none": "續行框,無說話者"},
        "note": "lines[] 是 0xFFFE 原生換行切開的框內斷行,非任何寬度估算的產物;"
                "string_index 可餵給 tools/encode_text.py writeback 定位回寫"},
        "chapters": chapters}
    with open(out, "w", encoding="utf-8") as f:
        json.dump(obj, f, ensure_ascii=False, indent=1)
        f.write("\n")
    print(f"{total} 個對話框 / {len(chapters)} 章 -> {out}")


def selftest(src, _break_kind=False):
    """見模組 docstring「驗證設計」。`_break_kind` 是故障注入用,正常呼叫不要傳。"""
    fails = []
    paths = _fdtxt_paths(src)
    print(f"(1) script-json 重組回文字,必須與 render_chapter() 逐行相同({len(paths)} 檔)")
    bad = []
    for p in paths:
        rebuilt = []
        for b in script_boxes(p):
            text = "".join(b["lines"])
            spk = b["speaker"]
            if _break_kind:
                spk = None          # 故障注入:抹掉說話者
            rebuilt.append(f"- **{spk}**：{text}" if spk else f"  {text}")
        if rebuilt != render_chapter(p):
            bad.append(os.path.basename(p))
    print(f"    {'PASS' if not bad else 'FAIL'}: {len(paths) - len(bad)}/{len(paths)} 相同"
          + (f" 不符={bad[:5]}" if bad else ""))
    if bad:
        fails.append(f"script-json 與 render_chapter 輸出不一致:{bad[:5]}")

    print("\n(2) runtime 框數 == --runtime-todo 的筆數(兩個獨立判定:控制碼 vs 字串正則)")
    bad = []
    for p in paths:
        a = sum(1 for b in script_boxes(p) if b["speaker_kind"] == "runtime")
        b_ = len(find_runtime_todo(p))
        if a != b_:
            bad.append((os.path.basename(p), a, b_))
    print(f"    {'PASS' if not bad else 'FAIL'}: {len(paths) - len(bad)}/{len(paths)} 一致"
          + (f" 不符={bad[:5]}" if bad else ""))
    if bad:
        fails.append(f"runtime 框數兩法不一致:{bad[:5]}")

    if not _break_kind:
        print("\n(3) 故障注入:抹掉說話者後,檢查(1)必須失敗")
        # 注入標的**必須**是真的有說話者的檔案。第一版直接拿 paths[0],而 FDTXT_000 是
        # 名稱表、整份沒有任何帶說話者的框,注入等於空操作、檢查(1)照樣通過——當場被這
        # 個注入檢查自己抓到。這正是「退化樣本」:抹掉不存在的東西當然改不了輸出。
        victim = next((p for p in paths if any(b["speaker"] for b in script_boxes(p))), None)
        if victim is None:
            fails.append("找不到任何含說話者的 FDTXT,故障注入無從執行")
            print("    FAIL: 無可注入的檔案")
            victim = paths[0]
        import io
        import contextlib
        buf = io.StringIO()
        with contextlib.redirect_stdout(buf):
            hurt = selftest(victim, _break_kind=True)
        if hurt == 0:
            fails.append("故障注入後檢查(1)仍然通過——該檢查沒有在測說話者")
            print("    FAIL: 注入後仍通過")
        else:
            print("    PASS: 注入後如預期失敗")

    if fails:
        print("\nSELFTEST FAILED:")
        for f in fails:
            print("  -", f)
        return 1
    print("\n--selftest passed。")
    return 0


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
    if argv[1] == "--script-json":
        write_script_json(argv[2], argv[3])
        return 0
    if argv[1] == "--selftest":
        # 目錄可省略。全 repo 的稽核工具 (tools/verify_all_tools.py) 以不帶參數的
        # `--selftest` 呼叫每一支工具,原本這裡直接取 argv[2] 會 IndexError,於是
        # 這個 selftest 在全工具稽核裡一直是 FAIL 而不是被執行。
        return selftest(argv[2] if len(argv) > 2 else DEFAULT_FDTXT_DIR)
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
