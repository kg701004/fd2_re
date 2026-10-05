"""證據產生器共用的路徑與輸入檢查。

產生器(`ev_*.py`)由這裡取得倉庫根目錄、原版遊戲目錄與輸出目錄,啟動時呼叫
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
import subprocess
import sys
from pathlib import Path

GEN_DIR = Path(__file__).resolve().parent
ROOT = GEN_DIR.parents[3]
ROOT_S = ROOT.as_posix()
TOOLS = ROOT / "tools"
GAME_DEFAULT_REL = "org_game/炎龍騎士團/FLAME2"
GAME = Path(os.environ.get("FD2_GAME_DIR") or ROOT / GAME_DEFAULT_REL)
GAME_S = GAME.as_posix()
EVIDENCE = ROOT / "docs/knowledge-base/evidence"
MANIFEST = Path(os.environ.get("FD2_EVIDENCE_MANIFEST") or GEN_DIR / "inputs_manifest.json")
MISSING_INPUT_RC = 3


def out_path(name: str) -> Path:
    """證據檔的輸出位置;平常是 `docs/knowledge-base/evidence/<name>`。"""
    return Path(os.environ.get("FD2_EVIDENCE_OUT_DIR") or EVIDENCE) / name


def rel(p: Path) -> str:
    """證據裡記錄檔案位置用的字串:一律 `/` 分隔,不隨作業系統或 `FD2_GAME_DIR` 改變。

    遊戲目錄裡的檔案記成預設位置 `org_game/炎龍騎士團/FLAME2/<檔名>`(遊戲目錄放在倉庫外時
    也一樣,檔案身分由證據裡同時記錄的 md5 鎖定);其餘記成相對倉庫根目錄的路徑。

    Args:
        p: 遊戲目錄或倉庫內的檔案 / 目錄路徑。

    Returns:
        `/` 分隔的相對路徑。

    Raises:
        ValueError: 路徑既不在遊戲目錄也不在倉庫內。
    """
    rp = Path(p).resolve()
    try:
        return GAME_DEFAULT_REL + "/" + rp.relative_to(GAME.resolve()).as_posix()
    except ValueError:
        return rp.relative_to(ROOT).as_posix()


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


def git_blob(blob: str, path: str) -> bytes:
    """讀倉庫歷史裡某個已追蹤檔案當時的內容(以 blob sha 鎖定)。

    證據記錄的是「當時那份已追蹤檔案」的狀態、而該檔之後已修改時使用(例如證據就是在記錄
    那份檔案當時的錯誤)。讀不到(沒有 git、淺層 clone 缺物件)或內容與 sha 不符時,
    與缺輸入同樣以 exit code 3 結束。

    Args:
        blob: git blob 的完整 sha1。
        path: 該 blob 對應的倉庫相對路徑,只用於錯誤訊息。

    Returns:
        blob 的原始 bytes。
    """
    try:
        r = subprocess.run(["git", "-C", str(ROOT), "cat-file", "blob", blob], capture_output=True, timeout=60)
        data, ok = r.stdout, r.returncode == 0
    except (OSError, subprocess.TimeoutExpired):
        data, ok = b"", False
    # git 的 blob sha1 = sha1("blob <長度>\0" + 內容);再算一次,確認拿到的就是這個版本
    if not ok or hashlib.sha1(b"blob %d\0" % len(data) + data).hexdigest() != blob:
        print(f"MISSING_INPUT 讀不到 git blob {blob}({path} 的舊版本)", file=sys.stderr)
        sys.exit(MISSING_INPUT_RC)
    return data
