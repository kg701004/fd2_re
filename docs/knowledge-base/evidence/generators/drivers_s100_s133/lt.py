# 存檔:原 scratchpad 驅動腳本(續一百 ~ 一百三十三),路徑保留當時的工作環境,不保證能直接執行(見 README.md)。
"""續一百:原版 FD2.EXE 從開機就錄的 LOGC 擷取驅動(只對原版 EXE,WSL -d Ubuntu)。

LOGC 連續錄,場景邊界不碰除錯器:只記下當下 LOGCPU.TXT 的位元組數(LOGC 每行即時寫入),
最後 finalize 依位元組區間切段去重。計數用完 dosbox-x 會自己進除錯器並關檔,此時改名 raw_K.TXT 再 LOGC 續錄。
(續一百實測:在已開檔時下 `LOGC 1` 想收檔,結果原檔只剩 1 行 —— 所以不用這種做法。)

用法(instance 名 lt2):
  python lt.py prep | boot | shot [tag] | state | pane
  python lt.py k <wait> <key...>    # 確認仍在錄 → 送鍵 → 等 → 截圖
  python lt.py mark <label>         # 從這裡開始算 <label> 段
  python lt.py finalize             # 停錄,依標記切段去重成 seg_NN_<label>_unique_cseip.txt
"""
from __future__ import annotations

import json
import subprocess
import sys
import time
from pathlib import Path

REPO = Path(r"C:/Users/kg701/Desktop/GAME/fd2_re")
sys.path.insert(0, str(REPO / "tools"))
import fd2_chapter_sweep as sw  # noqa: E402

NAME = "lt2"
OUT = Path(__file__).resolve().parent / "lt"
SHOTS = OUT / "shots"
STATE = OUT / "state.json"
WD = f"/home/kg701004/fd2-run-harness-{NAME}"
COUNT = "7FFFFFFF"


def wsl(cmd: str, timeout: int = 60) -> str:
    """-e:不經預設 shell,cmd 只被內層 bash 解析一次(續一百踩到外層先展開 $(...))。"""
    r = subprocess.run(["wsl", "-d", "Ubuntu", "-e", "bash", "-c", cmd], capture_output=True, text=True,
                       encoding="utf-8", errors="replace", timeout=timeout)
    return (r.stdout + r.stderr).strip()


def pane() -> str:
    return wsl(f"tmux -L fd2harness capture-pane -t harness-{NAME} -p")


def running() -> bool:
    lines = [x for x in pane().splitlines() if x.strip()]
    return bool(lines) and "Running" in lines[-1]


def dbg(text: str) -> None:
    sw.debugger_cmd(NAME, text)
    time.sleep(0.5)


def load() -> dict:
    if STATE.exists():
        return json.loads(STATE.read_text(encoding="utf-8"))
    return {"raw": 0, "marks": [], "shot": 0, "label": "boot"}


def save(st: dict) -> None:
    STATE.write_text(json.dumps(st, ensure_ascii=False, indent=1), encoding="utf-8")


def wait_halt(max_s: float = 60) -> bool:
    t0 = time.time()
    while time.time() - t0 < max_s:
        if not running():
            return True
        time.sleep(1)
    return False


def size() -> int:
    s = wsl(f"stat -c %s {WD}/LOGCPU.TXT")
    return int(s) if s.isdigit() else -1


def arm(st: dict) -> None:
    dbg(f"LOGC {COUNT}")
    time.sleep(2)
    print(f"armed LOGC {COUNT} -> raw_{st['raw']}, LOGCPU.TXT {size()} B, running={running()}")
    save(st)


def rotate(st: dict) -> None:
    """計數用完、已關檔:LOGCPU.TXT -> raw_K.TXT,再錄下一份。"""
    k = st["raw"]
    print(wsl(f"cd {WD} && mv LOGCPU.TXT raw_{k}.TXT && ls -la raw_{k}.TXT"))
    st["raw"] = k + 1
    st["marks"].append({"raw": k + 1, "off": 0, "label": st["label"]})
    arm(st)


def ensure(st: dict) -> None:
    if running():
        return
    print("debugger is active (LOGC count exhausted?) -> rotating")
    rotate(st)


def shot(st: dict, tag: str = "") -> Path:
    st["shot"] += 1
    p = SHOTS / f"{st['shot']:03d}_{st['label']}{('_' + tag) if tag else ''}.png"
    sw.screenshot(NAME, p)
    save(st)
    return p


FINALIZE_SH = r'''
set -eu
cd "$1"
# 每行: raw_index start_off end_off(-1=到檔尾) out_name
while read -r k a b name; do
  f=raw_$k.TXT
  if [ "$b" = "-1" ]; then b=$(stat -c %s "$f"); fi
  n=$((b - a))
  tail -c +$((a + 1)) "$f" | head -c "$n" | awk '!seen[$0]++' >> "$name.tmp"
  echo "$name: raw_$k [$a,$b) $n bytes"
done < segplan.txt
for t in *_unique_cseip.txt.tmp; do
  awk '!seen[$0]++' "$t" > "${t%.tmp}"; rm "$t"; echo "${t%.tmp} $(wc -l < "${t%.tmp}") unique"
done
'''


def finalize(st: dict) -> None:
    if running():
        sw.enter_debugger(NAME)
        wait_halt(20)
    # 停在除錯器時檔案仍開著但每行都已寫入;同一檔案系統內改名,開著的 handle 跟著走(之後不再 RUN)
    print(wsl(f"cd {WD} && mv LOGCPU.TXT raw_{st['raw']}.TXT && ls -la raw_*.TXT"))
    marks = st["marks"]
    plan = []
    for i, m in enumerate(marks):
        nxt = marks[i + 1] if i + 1 < len(marks) else None
        name = f"seg_{[x['label'] for x in marks].index(m['label']):02d}_{m['label']}_unique_cseip.txt"
        if nxt is not None and nxt["raw"] == m["raw"]:
            plan.append(f"{m['raw']} {m['off']} {nxt['off']} {name}")
        else:
            plan.append(f"{m['raw']} {m['off']} -1 {name}")
    print("\n".join(plan))
    (OUT / "segplan.txt").write_text("\n".join(plan) + "\n", encoding="utf-8", newline="\n")
    (OUT / "finalize.sh").write_text(FINALIZE_SH, encoding="utf-8", newline="\n")
    wp = "/mnt/c/" + str(OUT).replace("\\", "/").split(":", 1)[1].lstrip("/")
    print(wsl(f"cp {wp}/segplan.txt {WD}/segplan.txt && bash {wp}/finalize.sh {WD}", timeout=7200))


def main(argv: list[str]) -> int:
    OUT.mkdir(parents=True, exist_ok=True)
    SHOTS.mkdir(parents=True, exist_ok=True)
    cmd = argv[0]
    st = load()
    if cmd == "prep":
        log: list[str] = []
        n = 23
        cap = sw.guard_selection_threshold(n) + 1
        sw.prepare_chapter_save(REPO / ".wsl_build/chapter_sweep/FD2_source.SAV", n, OUT / "patched.SAV", 0, log,
                                pad_roster=True, roster_mode="complete", roster_cap=cap)
        print("\n".join(log[-6:]))
    elif cmd == "boot":
        sw.overwrite_save(NAME, OUT / "patched.SAV")
        print(wsl(f"md5sum {WD}/FD2.EXE {WD}/FD2.SAV"))
        dbg("BPINT 21 4B")
        dbg("RUN")
        ok = wait_halt(120)
        print("halted:", ok)
        print("\n".join(pane().splitlines()[:6]))
        if not ok:
            return 1
        dbg("BPDEL *")
        st = {"raw": 0, "marks": [{"raw": 0, "off": 0, "label": "boot"}], "shot": 0, "label": "boot"}
        arm(st)
    elif cmd == "k":
        wait = float(argv[1])
        ensure(st)
        sw.send_keys(NAME, *argv[2:])
        time.sleep(wait)
        print(shot(st, "_".join(k.replace("+", "") for k in argv[2:])[:40]))
    elif cmd == "shot":
        print(shot(st, argv[1] if len(argv) > 1 else ""))
    elif cmd == "mark":
        ensure(st)
        off = size()
        st["label"] = argv[1]
        st["marks"].append({"raw": st["raw"], "off": off, "label": argv[1]})
        save(st)
        print(f"mark {argv[1]} at raw_{st['raw']} off {off}")
    elif cmd == "finalize":
        finalize(st)
    elif cmd == "state":
        print(json.dumps(st, ensure_ascii=False), "running", running())
        print(wsl(f"ls -la {WD}/LOGCPU.TXT {WD}/raw_* 2>&1"))
    elif cmd == "pane":
        print(pane())
    else:
        print(__doc__)
        return 2
    return 0


if __name__ == "__main__":
    sys.exit(main(sys.argv[1:]))
