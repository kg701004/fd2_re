"""讀取當時 DOSBox-X 驅動腳本的終端輸出(原始紀錄)。

續四十六~六十四的驅動腳本把斷點停點的暫存器讀值印到終端,沒有另存檔案;產生器原本把這些值抄寫在
程式裡。這些輸出後來從 Claude Code 的對話紀錄(toolUseResult.stdout)原樣匯出到
`.wsl_build/ctr/console/<UTC 時間>_<tool_use_id>.txt`,旁邊的 `.meta.json` 記錄當時執行的指令、
說明與時間。它們和其他原始紀錄一樣不進 git、由 `inputs_manifest.json` 以 sha256 鎖定。
"""
from __future__ import annotations

import json
import re
import shlex

from _evpaths import ROOT

CONSOLE_DIR = ROOT / ".wsl_build/ctr/console"
_STOP = re.compile(r"^stop (\d+): (.*)$")
_REG = re.compile(r"\b([A-Z]{2,3})=([0-9A-F]+)\b")


def load(stem: str) -> tuple[dict, str]:
    """回傳 (meta, stdout 全文)。

    Args:
        stem: `<UTC 時間>_<tool_use_id>`。
    """
    meta = json.loads((CONSOLE_DIR / f"{stem}.meta.json").read_text(encoding="utf-8"))
    text = (CONSOLE_DIR / f"{stem}.txt").read_text(encoding="utf-8")
    assert stem.endswith("_" + meta["id"]), (stem, meta["id"])
    return meta, text


def invocations(cmd: str, script: str) -> list[list[str]]:
    """指令裡每一次呼叫 `script` 的參數(依出現順序;以換行、`;`、`&&`、`|` 分隔的各段)。"""
    out = []
    for part in re.split(r"\n|;|&&|\|", cmd):
        if script in part:
            argv = shlex.split(part)
            i = next(k for k, a in enumerate(argv) if a.endswith(script))
            out.append(argv[i + 1:])
    return out


def segments(stem: str, script: str, sep: str = "----") -> list[tuple[list[str], str]]:
    """一次工具呼叫裡依序執行多次 `script`、輸出以 `sep` 一行分隔時,回傳 [(參數, 該次輸出)]。

    段數必須等於呼叫次數,否則失敗(不猜對應)。
    """
    meta, text = load(stem)
    calls = invocations(meta["cmd"], script)
    segs = re.split(rf"(?m)^{re.escape(sep)}\n", text) if len(calls) > 1 else [text]
    assert len(segs) == len(calls), (stem, script, len(segs), len(calls))
    return list(zip(calls, segs))


def stops(text: str) -> list[dict[str, int]]:
    """解析 `stop N: EIP=... EAX=...` 行;每個停點回傳 {"n": N, 暫存器: 值}。"""
    out = []
    for line in text.splitlines():
        m = _STOP.match(line.strip())
        if m:
            out.append({"n": int(m.group(1))} | {k: int(v, 16) for k, v in _REG.findall(m.group(2))})
    return out
