"""重新記錄每個產生器實際讀到的、不在 git 裡的輸入,寫成 `inputs_manifest.json`。

做法:以 `_trace/sitecustomize.py` 的 audit hook 執行每個產生器(子行程一併記錄),
輸出導到暫存目錄(不碰已提交的證據檔)。保留的輸入 = 以讀取模式開啟的檔案,扣掉
Python 本身、本目錄的程式、git 追蹤中的檔案(由 git 版本控管)與同一次執行自己寫出的檔案。
倉庫外的輸入除遊戲目錄(記為 `{GAME}/...`)以外一律視為錯誤。

只有原始紀錄確實換過(例如重新跑了某次 DOSBox-X)時才需要重建;重建後要用
`run_all.py` 確認全部 IDENTICAL,並在提交訊息說明換了哪些輸入。

用法:python build_manifest.py [ev_s76 ...]   # 不給名稱 = 全部
"""
from __future__ import annotations

import json
import os
import subprocess
import sys
import sysconfig
import tempfile
from pathlib import Path

from _evpaths import GAME, GEN_DIR, MANIFEST, ROOT, _sha256

GENERATORS = ["ev_s65", "ev_s65b", "ev_s66", "ev_s67", "ev_s68", "ev_s69", "ev_s70", "ev_s71",
              "ev_s72", "ev_s73", "ev_s74", "ev_s75", "ev_s76",
              # 2026-09-29~10-01(續四十六~六十四)
              "ev_ai_action_choice", "ev_ai_heal_score", "ev_ai_item_score", "ev_ai_move_nearest",
              "ev_ai_physical_candidate", "ev_ai_physical_untested_branches", "ev_ai_spell_path", "ev_ai_spell_score",
              "ev_attack_exp", "ev_attack_path_selection", "ev_collect_targets_in_range", "ev_heal_spell_targets",
              "ev_level_up", "ev_move_landing_select", "ev_real_kill_corpse", "ev_rest_recover", "ev_spell9_path",
              "ev_terrain_modifier", "ev_terrain_types_3_5"]


def _norm(p: str) -> str:
    """絕對、正規化、Windows 不分大小寫的比較鍵。"""
    return os.path.normcase(os.path.normpath(os.path.join(GEN_DIR, p)))


def _under(absp: str, base: Path) -> str | None:
    """absp(未改大小寫的絕對路徑)在 base 底下時回傳相對路徑(posix,保留原大小寫),否則 None。"""
    b = os.path.normpath(str(base))
    if not os.path.normcase(absp).startswith(os.path.normcase(b) + os.sep):
        return None
    return Path(absp[len(b) + 1:]).as_posix()


def tracked() -> set[str]:
    out = subprocess.run(["git", "ls-files", "-z"], cwd=ROOT, capture_output=True, check=True).stdout
    return {os.path.normcase(os.path.normpath(str(ROOT / f))) for f in out.decode("utf-8").split("\0") if f}


def trace(gen: str, td: Path) -> tuple[list[tuple[str, str]], list[str], int, str]:
    """執行一個產生器並回傳(開啟紀錄、輸出檔名、exit code、stderr 尾端)。"""
    log = td / f"{gen}.log"
    out = td / f"{gen}_out"
    out.mkdir()
    env = dict(os.environ, EVTRACE_LOG=str(log), PYTHONPATH=str(GEN_DIR / "_trace"),
               FD2_EVIDENCE_OUT_DIR=str(out), FD2_EVIDENCE_MANIFEST_BUILD="1")
    r = subprocess.run([sys.executable, "-X", "utf8", "-W", "ignore", str(GEN_DIR / f"{gen}.py")],
                       cwd=GEN_DIR, env=env, capture_output=True, text=True, encoding="utf-8", errors="replace")
    rows = []
    if log.exists():
        for line in log.read_text(encoding="utf-8").splitlines():
            kind, mode, path = line.split("\t", 2)
            if kind == "open":
                rows.append((mode, path))
    return rows, sorted(p.name for p in out.iterdir()), r.returncode, r.stderr[-400:]


def main(argv: list[str]) -> int:
    names = argv or GENERATORS
    man = json.loads(MANIFEST.read_text(encoding="utf-8")) if MANIFEST.exists() else {"generators": {}}
    man["_note"] = ("每個證據產生器讀到的、不在 git 裡的輸入:{相對路徑: [大小, sha256]}。"
                    "`{GAME}/` = 原版遊戲目錄(FD2_GAME_DIR)。由 build_manifest.py 產生,不要手改。")
    py_roots = {os.path.normcase(os.path.normpath(p)) for p in
                (sys.base_prefix, sys.prefix, sysconfig.get_paths()["purelib"], sysconfig.get_paths()["platlib"])}
    git = tracked()
    gen_key = _norm(str(GEN_DIR))
    bad = 0
    with tempfile.TemporaryDirectory(prefix="evman_") as tdn:
        td = Path(tdn)
        for gen in names:
            rows, outputs, rc, err = trace(gen, td)
            if rc != 0:
                print(f"FAIL {gen}: rc={rc}\n{err}")
                bad += 1
                continue
            written = {_norm(p) for m, p in rows if any(c in m for c in "wax+")}
            inputs: dict[str, list] = {}
            external = []
            for mode, p in rows:
                if any(c in mode for c in "wax+"):
                    continue
                absp = os.path.normpath(os.path.join(GEN_DIR, p))
                k = os.path.normcase(absp)
                if (k in written or k.endswith(".pyc") or k.startswith(gen_key + os.sep)
                        or any(k.startswith(r + os.sep) for r in py_roots) or "site-packages" in k
                        or k in git or not os.path.isfile(k)):
                    continue
                rel = _under(absp, GAME)
                if rel is not None:
                    key = "{GAME}/" + rel
                else:
                    rel = _under(absp, ROOT)
                    if rel is None:
                        external.append(p)
                        continue
                    key = rel
                inputs[key] = [os.path.getsize(k), _sha256(Path(k))]
            if external:
                print(f"FAIL {gen}: 讀了倉庫與遊戲目錄以外的檔案:{sorted(set(external))[:5]}")
                bad += 1
                continue
            man["generators"][gen] = {"outputs": outputs, "inputs": dict(sorted(inputs.items()))}
            print(f"ok   {gen}: {len(inputs)} 筆輸入,{sum(v[0] for v in inputs.values()) / 1e6:.2f} MB;輸出 {outputs}")
    if bad:
        print(f"{bad} 個產生器失敗,清單未寫入")
        return 1
    man["generators"] = dict(sorted(man["generators"].items()))
    MANIFEST.write_bytes((json.dumps(man, ensure_ascii=False, indent=1) + "\n").encode("utf-8"))
    return 0


if __name__ == "__main__":
    sys.exit(main(sys.argv[1:]))
