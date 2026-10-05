"""證據產生器共用的路徑與輸入檢查。

產生器(`ev_s*.py`)由這裡取得倉庫根目錄、原版遊戲目錄與輸出目錄,啟動時呼叫
`require_inputs(__file__)`:依 `inputs_manifest.json` 逐一比對它要讀的、不在 git 裡的
輸入(`.wsl_build/` 的 DOSBox-X 原始紀錄、`extracted/`、原版遊戲檔)的大小與 sha256。
缺檔或內容不同時以 exit code 3 結束並列出每一筆 —— 不讓產生器拿錯的輸入算出
「看起來正常」的結果。

環境變數:
    FD2_GAME_DIR            原版遊戲目錄(預設 `<repo>/org_game/炎龍騎士團/FLAME2`)。
    FD2_EVIDENCE_OUT_DIR    證據 JSON 的輸出目錄(預設 `docs/knowledge-base/evidence`);
                            `run_all.py` 與變異測試把它指到暫存目錄,不覆寫已提交的檔案。
    FD2_EVIDENCE_MANIFEST    輸入清單的位置(預設本目錄的 inputs_manifest.json;run_all 的自我測試用)。
    FD2_EVIDENCE_MANIFEST_BUILD=1
                            只給 `build_manifest.py` 用:略過輸入檢查以便重新記錄輸入
                            (會在 stderr 印出警告)。
"""
from __future__ import annotations

import hashlib
import json
import os
import sys
from pathlib import Path

GEN_DIR = Path(__file__).resolve().parent
ROOT = GEN_DIR.parents[3]
ROOT_S = ROOT.as_posix()
TOOLS = ROOT / "tools"
GAME = Path(os.environ.get("FD2_GAME_DIR") or ROOT / "org_game/炎龍騎士團/FLAME2")
GAME_S = GAME.as_posix()
EVIDENCE = ROOT / "docs/knowledge-base/evidence"
MANIFEST = Path(os.environ.get("FD2_EVIDENCE_MANIFEST") or GEN_DIR / "inputs_manifest.json")
MISSING_INPUT_RC = 3


def out_path(name: str) -> Path:
    """證據檔的輸出位置;平常是 `docs/knowledge-base/evidence/<name>`。"""
    return Path(os.environ.get("FD2_EVIDENCE_OUT_DIR") or EVIDENCE) / name


def resolve(entry: str) -> Path:
    """把清單裡的路徑轉成實際路徑:`{GAME}/x` 對到遊戲目錄,其餘相對於倉庫根目錄。"""
    if entry.startswith("{GAME}/"):
        return GAME / entry[len("{GAME}/"):]
    return ROOT / entry


def _sha256(p: Path) -> str:
    h = hashlib.sha256()
    with open(p, "rb") as f:
        for chunk in iter(lambda: f.read(1 << 20), b""):
            h.update(chunk)
    return h.hexdigest()


def check_inputs(gen: str) -> list[str]:
    """回傳產生器 `gen` 的輸入問題清單(空清單 = 全部相符)。"""
    if not MANIFEST.exists():
        return [f"找不到 {MANIFEST.name}"]
    man = json.loads(MANIFEST.read_text(encoding="utf-8"))
    if gen not in man["generators"]:
        return [f"{MANIFEST.name} 沒有 {gen} 的輸入登錄"]
    problems = []
    for rel, (size, sha) in man["generators"][gen]["inputs"].items():
        p = resolve(rel)
        if not p.is_file():
            problems.append(f"缺檔 {rel}")
        elif p.stat().st_size != size:
            problems.append(f"大小不符 {rel}:{p.stat().st_size} != {size}")
        elif _sha256(p) != sha:
            problems.append(f"內容不符 {rel}")
    return problems


def require_inputs(script: str) -> None:
    """產生器啟動時呼叫;輸入不符就印出每一筆並以 exit code 3 結束。"""
    gen = Path(script).stem
    if os.environ.get("FD2_EVIDENCE_MANIFEST_BUILD") == "1":
        print(f"警告:{gen} 略過輸入檢查(FD2_EVIDENCE_MANIFEST_BUILD=1)", file=sys.stderr)
        return
    problems = check_inputs(gen)
    if problems:
        print(f"MISSING_INPUT {gen}:{len(problems)} 筆輸入與清單不符", file=sys.stderr)
        for line in problems[:40]:
            print("  " + line, file=sys.stderr)
        sys.exit(MISSING_INPUT_RC)
