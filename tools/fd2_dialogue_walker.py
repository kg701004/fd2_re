#!/usr/bin/env python3
"""fd2_dialogue_walker.py — 自動化「連續送出按鍵、只保留畫面真的改變那幾格」的
劇情推進工具，加速 speaker-resolution 這類需要人眼逐格核對文字的活體作業。

背景
----
`fd2_speaker_capture.py --resolve-todo` 需要呼叫端先用螢幕截圖親眼確認目前
畫面文字對到目標 FDTXT 的哪一個 box_index，再用 `--confirm-text` 核對。過去
做法是每按一次確認鍵就呼叫一次 `screenshot`，人工逐張看——這支工具把「連續
按 N 次確認鍵、只留下畫面真的變了的那幾張」自動化成一次呼叫，回傳一份依
出現順序排列的 manifest，讓呼叫端一次看完所有「新畫面」而不必每按一次都
截圖一次。

**這支工具不做的事**：不做 OCR、不自動判斷文字對到哪個 box_index、不自動
呼叫 `fd2_speaker_capture.py`——這些仍需要呼叫端(Claude)用眼睛看 manifest
裡的截圖決定。這是刻意的：本專案沒有可信的原版點陣字型 OCR，用猜的文字比對
比不截圖直接看還危險(見 `fd2_speaker_capture.py` 自己文件裡記載的
FDTXT_032/033 誤判教訓)。這支工具只解決「機械式減少來回呼叫次數」，不解決
「這是哪一格」的判斷本身。

方法
----
每按一次鍵，就截一次圖、算 SHA1；只有雜湊跟「上一張留下來的」不同時才真的
存檔、寫進 manifest。這樣一次 200 次按鍵的推進，畫面可能只變了 20-30 次
(打字機效果逐字顯示的過程中間幾偵會被跳過，因為那些偵彼此不同——**這是本
工具的一個已知限制，見下方"多重驗證"第③點**，manifest 保留的是最終定格的
畫面，不保證漏掉打字機動畫中間偵)。

多重驗證(使用者要求「新工具必須多向多重驗證過」，見下)
----
本檔案的 `--selftest` 模式做三個獨立方向的驗證，缺一都算失敗:
① **退化樣本檢查**(對應本專案 `feedback_degenerate_verification_sample`
   教訓)：manifest 裡任兩張存檔的 hash 必須兩兩不同——如果同一個 hash 出現
   兩次，代表去重邏輯本身有 bug(該去重的沒去重，或不該去重的被錯誤去重)。
② **零假陽性控制**：對一個已知**完全靜止**的畫面(例如剛截圖後、不送任何
   按鍵、只重複截圖 N 次)跑同一套「hash 變了才存檔」邏輯，manifest 必須
   剛好只有 1 筆——如果 >1 筆，代表截圖管線本身有雜訊(例如壓縮/時間戳記
   造成同一畫面每次截圖 hash 都不同)，那樣「畫面真的改變」這個判準就不
   可信，整支工具的核心假設就是錯的。
③ **已知場景重播比對**：對 2026-09-06 已經人工核對過的 ch01 海盜遭遇戰
   (`docs/data/runtime_speaker_resolved.json` 的 `FDTXT_001`)重新跑一次
   本工具，manifest 裡至少要有一張畫面的檔案內容經人工目視能看到
   "乖乖的把身上的錢財和" 這段已知文字(這一步驟仍需人眼看一次截圖，
   `--selftest` 只自動檢查①②，③需要呼叫端在 selftest 之後自行核對，
   本工具誠實地不宣稱能自動化這一步)。

用法
----
    # 連續按確認鍵最多 150 次，只保留畫面有變的截圖，settle 偵測到每次按鍵後的定格
    python tools/fd2_dialogue_walker.py --instance spk2 --key confirm \\
        --max-presses 150 --out-dir .wsl_build/walk_spk2

    # 自我測試(①②兩個方向的驗證，不需要活體遊戲畫面內容有意義，只需要
    # instance 存在且能截圖——用一個已啟動的 instance 皆可)
    python tools/fd2_dialogue_walker.py --instance spk2 --selftest
"""

from __future__ import annotations

import argparse
import hashlib
import json
import sys
import time
from pathlib import Path

sys.path.insert(0, str(Path(__file__).resolve().parent))
import fd2_dosbox_live_helper as H  # noqa: E402


def _hash_file(path: Path) -> str:
    return hashlib.sha1(path.read_bytes()).hexdigest()


def _stable_hash(instance: str, tmp: Path, confirms: int = 2, gap: float = 0.25,
                 retries: int = 4) -> str:
    """截圖+算hash,重複讀到連續 `confirms` 次拿到同一個 hash 才回傳——單次讀值
    不可信(見本檔案 selftest ②抓到的真實發現:同一個完全靜止畫面偶爾連續
    截圖也會拿到不同 hash,推測是截圖管線本身的間歇性雜訊,不是畫面真的變了)。
    最多重試 `retries` 輪去湊齊 `confirms` 次相同讀值,湊不齊就回傳最後一次讀到
    的 hash 並印警告——不無限重試卡死,但誠實標記這次讀值沒有達到穩定門檻。"""
    seen: list[str] = []
    for _ in range(retries + confirms):
        H.screenshot(instance, tmp)
        h = _hash_file(tmp)
        seen.append(h)
        if len(seen) >= confirms and len(set(seen[-confirms:])) == 1:
            return h
        time.sleep(gap)
    print(f"警告:讀值 {retries + confirms} 輪仍未連續 {confirms} 次一致"
          f"(最近幾次:{seen[-confirms:]})——回傳最後一次讀值,但這次的『畫面是否"
          "真的穩定』不確定。", file=sys.stderr)
    return seen[-1]


def walk(instance: str, key: str, max_presses: int, out_dir: Path,
         wait: float = 0.6, settle: bool = True, settle_timeout: float = 6.0) -> list[dict]:
    """送出最多 `max_presses` 次 `key`，每次都用 `_stable_hash()` 讀取畫面雜湊，
    只有畫面真的變了(且新畫面本身也讀到穩定)才存檔+登記進回傳的 manifest
    (list of dict)。press_count=0 那筆是起始畫面(完全沒送鍵前),必定存在。

    2026-09-06:原本直接單次截圖算hash,被自己的`--selftest`②項抓到一個真實
    問題——同一個完全靜止的畫面，短間隔連續截圖偶爾會拿到不同hash(截圖管線
    本身間歇性雜訊，不是畫面真的變了)。改用`_stable_hash()`要求連續讀值一致
    才採信，見該函式docstring。"""
    out_dir.mkdir(parents=True, exist_ok=True)
    tmp = out_dir / "_scratch.png"
    manifest: list[dict] = []

    h = _stable_hash(instance, tmp)
    dest = out_dir / "state_0000.png"
    tmp.replace(dest)
    manifest.append({"index": 0, "press_count": 0, "file": dest.name, "hash": h})
    last_hash = h

    resolved_key = H.resolve_key(key)
    for i in range(1, max_presses + 1):
        H.send_keys(instance, [resolved_key])
        if settle:
            H.wait_for_settle(instance, timeout=settle_timeout)
        else:
            time.sleep(wait)
        h = _stable_hash(instance, tmp)
        if h != last_hash:
            idx = len(manifest)
            dest = out_dir / f"state_{idx:04d}.png"
            tmp.replace(dest)
            manifest.append({"index": idx, "press_count": i, "file": dest.name, "hash": h})
            last_hash = h
    if tmp.exists():
        tmp.unlink()
    return manifest


def selftest(instance: str, out_dir: Path) -> int:
    """①退化樣本檢查(hash兩兩不同) + ②零假陽性控制(靜止畫面只留1筆)。
    回傳 0 表示兩項都通過,非0表示至少一項失敗(印出哪一項、為什麼)。"""
    fails: list[str] = []

    # ① 用一段真的會推進畫面的按鍵序列(confirm)產生 manifest,檢查 hash 唯一
    m1 = walk(instance, "confirm", max_presses=5, out_dir=out_dir / "selftest_moving",
             settle=False, wait=0.3)
    hashes1 = [e["hash"] for e in m1]
    if len(hashes1) != len(set(hashes1)):
        fails.append(f"①退化樣本檢查失敗:manifest 裡有重複 hash(共 {len(hashes1)} 筆,"
                     f"唯一 {len(set(hashes1))} 筆)——去重邏輯本身有 bug。")
    else:
        print(f"①退化樣本檢查通過:{len(hashes1)} 筆 manifest,hash 兩兩不同。")

    # ② 完全不送鍵,用實際會用到的 `_stable_hash()` 重複讀 8 次,檢查是否被
    # 誤判成「畫面一直在變」——這一項刻意呼叫跟 walk() 同一個函式,不是另外
    # 寫一次簡化版判準,否則測的是「理想情況」而不是「工具實際會用的邏輯」。
    static_dir = out_dir / "selftest_static"
    static_dir.mkdir(parents=True, exist_ok=True)
    tmp = static_dir / "_scratch.png"
    hashes2 = [_stable_hash(instance, tmp) for _ in range(8)]
    if tmp.exists():
        tmp.unlink()
    unique2 = set(hashes2)
    if len(unique2) != 1:
        fails.append(f"②零假陽性控制失敗:同一個畫面用 `_stable_hash()` 重複讀 8 次,"
                     f"卻拿到 {len(unique2)} 種不同結果——連穩定化讀值都擋不住這個"
                     "環境的雜訊,本工具在這個環境下不可信,需要更強的穩定化策略"
                     "才能用,不能直接上場。")
    else:
        print("②零假陽性控制通過:靜止畫面用 `_stable_hash()` 重複讀 8 次,結果完全一致。")

    if fails:
        print("\n".join(fails), file=sys.stderr)
        return 1
    print("\n--selftest 通過(①②兩項)。③(已知場景重播的文字內容核對)仍需人眼看"
          "一次 manifest 截圖,--selftest 不自動化這一步——見本檔案docstring。")
    return 0


def main() -> int:
    ap = argparse.ArgumentParser(description=__doc__,
                                 formatter_class=argparse.RawDescriptionHelpFormatter)
    ap.add_argument("--instance", required=True)
    ap.add_argument("--key", default="confirm", help="要連續送出的按鍵(alias 或 xdotool 鍵名)")
    ap.add_argument("--max-presses", type=int, default=150)
    ap.add_argument("--wait", type=float, default=0.6, help="--no-settle 時每次按鍵後的固定等待秒數")
    ap.add_argument("--settle", action="store_true", default=True)
    ap.add_argument("--no-settle", dest="settle", action="store_false")
    ap.add_argument("--settle-timeout", type=float, default=6.0)
    ap.add_argument("--out-dir", type=Path, required=True)
    ap.add_argument("--selftest", action="store_true",
                    help="只做①②兩項自我驗證,不執行真正的劇情推進")
    a = ap.parse_args()

    if a.selftest:
        return selftest(a.instance, a.out_dir)

    manifest = walk(a.instance, a.key, a.max_presses, a.out_dir,
                    wait=a.wait, settle=a.settle, settle_timeout=a.settle_timeout)
    manifest_path = a.out_dir / "manifest.json"
    manifest_path.write_text(json.dumps(manifest, ensure_ascii=False, indent=1), encoding="utf-8")
    print(f"送出最多 {a.max_presses} 次「{a.key}」,畫面共出現 {len(manifest)} 個相異狀態"
          f"(含起始畫面)。manifest -> {manifest_path}")
    for e in manifest:
        print(f"  [{e['index']:3}] press_count={e['press_count']:4}  {e['file']}")
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
