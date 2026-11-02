"""從 2026-08-28 那次 ch11chest 子代理的對話轉錄,抽出四支腳本印在 stdout 的讀值,寫成 .wsl_build 下的原始檔。

這四支(recover_state.py 兩次、continue_from_ring.py、confirm_open_chest.py)只印 stdout、沒有存檔;
當時的輸出只留在 Claude Code 的子代理轉錄裡(不在 repo、不提交)。本程式只抽「工具結果」裡含結束標記的那幾段,
原樣保存文字與時間戳,另記轉錄檔的 sha256;ev_s187.py 讀這個抽出檔(由 inputs_manifest 鎖定)。

用法:python extract_stdout.py <子代理轉錄 .jsonl>
"""
from __future__ import annotations

import hashlib
import json
import sys
from pathlib import Path

ROOT = Path(__file__).resolve().parents[5]
OUT = ROOT / ".wsl_build/chapter_sweep_ch11chest/stdout_s187.json"
# 結束標記 -> 印出它的腳本
MARKERS = {"RECOVER_DONE": "recover_state.py", "CONTINUE_DONE": "continue_from_ring.py",
           "CONFIRM_DONE": "confirm_open_chest.py"}


def tool_text(content: object) -> str:
    """工具結果的 content 可能是字串或 [{type: text, text}] 串列。"""
    if isinstance(content, str):
        return content
    return "".join(x.get("text", "") for x in content if isinstance(x, dict))


def main(src: Path) -> None:
    raw = src.read_bytes()
    runs = []
    for line in raw.decode("utf-8").splitlines():
        d = json.loads(line)
        content = d.get("message", {}).get("content")
        if not isinstance(content, list):
            continue
        for x in content:
            if not (isinstance(x, dict) and x.get("type") == "tool_result"):
                continue
            text = tool_text(x.get("content", ""))
            hit = [m for m in MARKERS if text.rstrip().endswith(m)]
            if hit:
                runs.append({"timestamp": d["timestamp"], "script": MARKERS[hit[0]], "stdout": text})
    assert runs, "轉錄裡沒有任何結束標記"
    OUT.write_text(json.dumps({"source_name": src.name, "source_sha256": hashlib.sha256(raw).hexdigest(),
                               "runs": runs}, ensure_ascii=False, indent=1) + "\n", encoding="utf-8", newline="\n")
    print(OUT, len(runs), [(r["timestamp"], r["script"]) for r in runs])


if __name__ == "__main__":
    main(Path(sys.argv[1]))
