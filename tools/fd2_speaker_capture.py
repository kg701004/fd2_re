#!/usr/bin/env python3
"""fd2_speaker_capture.py — 活體解出 273 個「執行期才能決定」的說話者。

背景
----
`docs/knowledge-base/40-speaker-portrait-mapping.md`(第 15 輪 RE)已經反組譯
證實:`0xFFED`/`0xFFEC` 開框碼的 operand 是**戰場單位陣列 index**,真正的
DATO.DAT 選擇器是該單位 `unit[idx].byte[+7]`——`tools/decode_story_text.py
--runtime-todo` 已經把全部 273 筆(哪個 FDTXT、第幾框、operand 是多少)結構化
成清單,但那份清單**回答不了「這個 idx 在這個場景裡是誰」**,因為場上單位
組成隨場景變動,這正是 273 筆靜態解不出來的原因。

這支工具做的事:對一個**已經在正確場景裡**的活體實例,讀整個單位陣列,把
每個需要的 idx 的 `byte[+7]` 拿去查 `decode_story_text.PORT`(0x00-0x1F 是
主角群,>0x1F 是 NPC,查不到就老實說查不到,不臆測)。

**這支工具不負責「怎麼到達正確場景」**——2026-09-05 活體探測(見
`docs/knowledge-base/SESSION-HANDOFF-2026-09-04.md` 對應小節)發現開場動畫
之後的第一段對話(疑似 ch00 王宮场景)當下,單位陣列讀出來的數值明顯是
**未初始化的殘留值**(HP/MP 大到不合理,且送出按鍵後完全沒有變化)——推測
'真正的' 說話者查表只有在**至少跑過一次章節/戰鬥初始化**(`FUN_00010010`/
`FUN_0001088d`)之後才有意義。這是本節誠實記錄的**未解問題**,不是這支工具
能力範圍內能修的,需要下一輪先定位「哪個活體操作點的陣列才是可信的」。

用法
----
    # 摸清楚目前這個活體場景裡,單位陣列每一格解出來是誰(探索用)
    python tools/fd2_speaker_capture.py --instance spk2 --dump-roster

    # 針對某個 FDTXT 的 --runtime-todo 清單,查目前活體場景能解出哪幾筆
    python tools/fd2_speaker_capture.py --instance spk2 \\
        --resolve-todo docs/data/runtime_speaker_todo.json --fdtxt FDTXT_032
"""

from __future__ import annotations

import argparse
import json
import sys
from pathlib import Path

sys.path.insert(0, str(Path(__file__).resolve().parent))
import fd2_dosbox_live_helper as H  # noqa: E402
from decode_story_text import PORT  # noqa: E402

DATO_OFFSET = 7
STRIDE = 0x50


def resolve_dato(dato: int) -> str:
    if dato in PORT:
        return PORT[dato]
    if dato > 0x1F:
        return f"NPC/敵(DATO={dato:#x},字模顯示,PORT 查無對應)"
    return f"未知(DATO={dato:#x},不在 0x00-0x1F 主角範圍,也不是已知 NPC 慣例)"


def read_roster_datos(instance: str, selector: str, num_records: int,
                      out_dir: Path) -> tuple[dict, list[int] | None]:
    """讀整個單位陣列一次,回傳 (完整 read-unit-array 結果, 每格 byte[+7] 列表)。

    重用 `mem_read_unit_array()` 已經驗證過的訊號校準+重試邏輯,不重寫一次
    定址——它已經把 array_dump 寫到磁碟,這裡直接重讀那個檔案切出 byte[+7],
    不需要再對活體多做一次記憶體存取。

    2026-09-06:原本沒有先呼叫 `enter_debugger()`——`mem_read_unit_array()`
    要求 debugger 已經停住才讀,不然為了不把「沒停住」跟「陣列真的是空的」
    混為一談,直接拒絕讀取(`fd2_battle_autoplay.py` 的 `snapshot()` 早就有
    這一步,這支工具當初漏寫)。補上跟 `snapshot()` 同款的
    `enter_debugger()`→讀→`resume()` bracket。
    """
    H.enter_debugger(instance)
    result = H.mem_read_unit_array(instance, selector, out_dir, num_records=num_records)
    H.resume(instance)
    if result.get("error"):
        return result, None
    array_dump = out_dir / "array_dump.bin"
    data = array_dump.read_bytes()
    datos = []
    for i in range(num_records):
        off = i * STRIDE + DATO_OFFSET
        if off >= len(data):
            break
        datos.append(data[off])
    return result, datos


def cmd_dump_roster(a) -> int:
    out_dir = Path(a.out_dir) if a.out_dir else (
        H.DEFAULT_SHOT_DIR / a.instance / "speaker_capture")
    result, datos = read_roster_datos(a.instance, a.selector, a.count, out_dir)
    if datos is None:
        print(f"讀取失敗:{result.get('error')}", file=sys.stderr)
        return 2
    print(f"array_base={result['array_base']}(delta={result['delta']})\n")
    for i, dato in enumerate(datos):
        print(f"  idx{i:2}  DATO={dato:#04x}  -> {resolve_dato(dato)}")
    return 0


def cmd_resolve_todo(a) -> int:
    todo_all = json.loads(Path(a.resolve_todo).read_text(encoding="utf-8"))["todo"]
    todo = [e for e in todo_all if e["fdtxt"] == a.fdtxt]
    if not todo:
        print(f"{a.fdtxt} 在 {a.resolve_todo} 裡沒有待解項目(可能已經全部解出,"
              "或這個 FDTXT 名稱不對)", file=sys.stderr)
        return 2
    # 2026-09-05 血淋淋的教訓:第一版沒有這道檢查,同一次活體觀察在沒有送出任何
    # 按鍵、畫面完全沒變的情況下,對 FDTXT_033(當下真的在播放)跟 FDTXT_032
    # (根本不是當下畫面)各跑一次 --resolve-todo,兩次都「成功」印出結果——
    # 因為這支工具原本對「目前活體畫面到底是不是這個 FDTXT」**完全沒有查核**,
    # 純粹相信呼叫端沒有搞錯。032 那次的結果是把 033 的王室场景陣列套到
    # 032 的童年練劍場景上,DATO 值剛好都能查到某個 NPC——**看起來正常,實際上
    # 全錯**,跟 `decode_story_text.py` 自己文件裡警告的「runtime 框 operand
    # 拿去查表一定查得到某個角色名,結果毫無徵兆地錯」是同一種失敗形狀,這次
    # 是本工具自己親手示範了一次。
    #
    # 修法:呼叫端必須用 `--confirm-text` 提供**當下畫面上看得到的一段原文**
    # (从螢幕截圖目視確認,不是猜的),而且這段文字必須能在這個 FDTXT 的某一筆
    # `text_snippet` 裡找到完全對應——找不到就拒絕往下跑。這不是萬無一失
    # (呼叫端還是可以謊稱看到不存在的文字),但至少把「有沒有真的看過螢幕」
    # 變成一個會被檢查的步驟,而不是文件裡一句沒人會回頭看的警語。
    if not a.confirm_text:
        print("拒絕執行:必須用 --confirm-text 提供目前螢幕上實際看到的一段原文"
              "(先截圖親眼確認,不要用猜的)——2026-09-05 已經在這支工具自己身上"
              "示範過一次『沒有這道檢查,結果看起來正常但套錯場景』的真實錯誤。",
              file=sys.stderr)
        return 2
    matched = [e for e in todo if a.confirm_text in e["text_snippet"]]
    if not matched:
        print(f"拒絕執行:--confirm-text {a.confirm_text!r} 在 {a.fdtxt} 的任何一筆"
              f"text_snippet 裡都找不到——目前活體畫面很可能不是這個 FDTXT 的內容,"
              "不能套用目前讀到的單位陣列。", file=sys.stderr)
        return 2
    print(f"--confirm-text 核對通過(對到 box_index={matched[0]['box_index']}),"
          "繼續解析。\n")
    needed_idx = sorted({e["operand"] for e in todo})
    out_dir = Path(a.out_dir) if a.out_dir else (
        H.DEFAULT_SHOT_DIR / a.instance / "speaker_capture")
    result, datos = read_roster_datos(a.instance, a.selector,
                                      max(needed_idx) + 1, out_dir)
    if datos is None:
        print(f"讀取失敗:{result.get('error')}", file=sys.stderr)
        return 2
    print(f"{a.fdtxt}:{len(todo)} 筆待解,涉及 idx {needed_idx}\n")
    resolved = []
    for e in todo:
        idx = e["operand"]
        dato = datos[idx] if idx < len(datos) else None
        name = resolve_dato(dato) if dato is not None else "idx 超出陣列範圍,讀不到"
        resolved.append({**e, "dato": dato, "resolved_name": name})
        print(f"  box_index={e['box_index']:3}  operand(idx)={idx:2}  "
              f"-> {name}\n      {e['text_snippet']}")
    if a.out_json:
        Path(a.out_json).write_text(
            json.dumps(resolved, ensure_ascii=False, indent=1), encoding="utf-8")
        print(f"\n-> {a.out_json}")
    print("\n⚠ 這個結果只在『目前這個活體場景的單位陣列就是這個 FDTXT 播放當下的"
          "真實場景』這個前提下才可信——本工具不驗證這個前提,呼叫端要自己確認"
          "(例如靠螢幕截圖看到的畫面內容,或已知的章節/戰鬥流程)。")
    return 0


def main() -> int:
    ap = argparse.ArgumentParser(description=__doc__,
                                 formatter_class=argparse.RawDescriptionHelpFormatter)
    ap.add_argument("--instance", required=True)
    ap.add_argument("--selector", default="0170")
    ap.add_argument("--count", type=int, default=24,
                    help="--dump-roster 模式讀幾格(預設 24,覆蓋常見 operand 範圍)")
    ap.add_argument("--out-dir")
    ap.add_argument("--dump-roster", action="store_true")
    ap.add_argument("--resolve-todo", metavar="JSON",
                    help="decode_story_text.py --runtime-todo 產生的清單檔")
    ap.add_argument("--fdtxt", help="只解這個 FDTXT 的項目,例如 FDTXT_032")
    ap.add_argument("--confirm-text",
                    help="--resolve-todo 必填:目前螢幕上實際看到的一段原文"
                         "(先截圖親眼確認),必須能在這個 FDTXT 的某筆 text_snippet "
                         "裡找到,否則拒絕執行——防止套錯場景(見本檔 2026-09-05 的教訓)")
    ap.add_argument("--out-json", help="配合 --resolve-todo,把解出的結果存成 JSON")
    a = ap.parse_args()

    if a.dump_roster:
        return cmd_dump_roster(a)
    if a.resolve_todo:
        if not a.fdtxt:
            print("--resolve-todo 需要搭配 --fdtxt 指定要解哪個檔", file=sys.stderr)
            return 2
        return cmd_resolve_todo(a)
    print(__doc__)
    return 1


if __name__ == "__main__":
    sys.exit(main())
