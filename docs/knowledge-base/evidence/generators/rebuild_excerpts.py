"""從 WSL 裡的完整 DOSBox-X 記錄重新切出摘錄,與 inputs_manifest.json 鎖定的摘錄逐 byte 比對。

續七十五~七十七有幾個輸入是從大型記錄(LOGCPU.TXT 每份約 5 GB、dosbox-x.log)切出的摘錄;完整記錄留在
WSL 的 `~/fd2-run-harness-<run>/`,不搬到 Windows、不進 git。這裡記下每個摘錄的切法(與存檔的驅動腳本相同),
重切到 stdout 比對,不寫任何檔案。只讀記錄檔,不啟動 DOSBox-X。

結果:IDENTICAL / DIFFERENT / SOURCE_MISSING(WSL 裡的完整記錄已不在)/ ERROR。全部 IDENTICAL 才 exit 0。

用法:python rebuild_excerpts.py [摘錄名稱 ...]     不給 = 全部(掃描約 30 GB,需數分鐘)
      python rebuild_excerpts.py --selftest      反向對照(切法差一行 → DIFFERENT、記錄不在 → SOURCE_MISSING)
"""
from __future__ import annotations

import hashlib
import json
import subprocess
import sys

from _evpaths import GEN_DIR, MANIFEST, resolve

# WSL 端看到的本目錄(存檔的驅動腳本可直接執行的那幾支用它)
_drive, _rest = str(GEN_DIR).split(":", 1)
GEN_WSL = "/mnt/" + _drive.lower() + _rest.replace("\\", "/")
H = "$HOME/fd2-run-harness-"

# 名稱 -> (清單裡的路徑, 需要存在的完整記錄, 重切指令(bash,輸出到 stdout))
EXCERPTS: dict[str, tuple[str, list[str], str]] = {
    # v21_exc.sh 前兩步:逃逸(第 7060958 行)前不在 blit 迴圈內的指令,再取每段出差的第一行
    "exc_entries": (".wsl_build/ctr/v21/ch25/exc_entries.txt", [H + "v21/LOGCPU.TXT"],
                    f"cd {H}v21 && awk 'NR<=7060957 && $2 !~ /^0170:001EAC(1F|24|25|66|68|6A|6C|6D|6E|70|72|74|75|77|7A|7B)$/ {{"
                    ' e = index($0, "EDI:"); c = index($0, "CR0:"); print NR, $2, substr($0, e, 12), substr($0, c, 12)'
                    "}' LOGCPU.TXT | awk 'NR==1 || $1 != prev+1 {print} {prev=$1}'"),
    # v21_c4000.sh 第一步:每次 stosb(0170:001EAC24)的 EDI 與 AL
    "stos_writes": (".wsl_build/ctr/v21/ch25/stos_writes.txt", [H + "v21/LOGCPU.TXT"],
                    f"cd {H}v21 && awk '$2 == \"0170:001EAC24\" {{"
                    ' e = index($0, "EDI:"); a = index($0, "EAX:"); print substr($0, e + 4, 8), substr($0, a + 10, 2)'
                    "}' LOGCPU.TXT"),
    # v21_excerpt.sh 的大括號區塊(原本寫到 OUT,這裡改到 stdout)
    "trace_excerpt": (".wsl_build/ctr/v21/ch25/trace_excerpt.txt", [H + "v21/LOGCPU.TXT"],
                      f"cd {H}v21 && "
                      "c3=$(grep -n -m1 ' C3FF:' LOGCPU.TXT | cut -d: -f1); "
                      "i6=$(grep -n -m1 ' F000:0000CA60' LOGCPU.TXT | cut -d: -f1); "
                      'echo "# lines $(wc -l < LOGCPU.TXT) bytes $(stat -c %s LOGCPU.TXT) sha256 $(sha256sum LOGCPU.TXT | cut -c1-64)"; '
                      'echo "# first_C3FF $c3 first_INT6_handler $i6"; '
                      "awk -v a=1 -v b=3 'NR>=a && NR<=b {print NR \"\\t\" $0}' LOGCPU.TXT; "
                      "awk -v a=7039299 -v b=7039340 'NR>=a && NR<=b {print NR \"\\t\" $0} NR>b {exit}' LOGCPU.TXT; "
                      "awk -v a=7060945 -v b=7060975 'NR>=a && NR<=b {print NR \"\\t\" $0} NR>b {exit}' LOGCPU.TXT; "
                      "awk -v a=$((c3 - 14)) -v b=$((c3 + 3)) 'NR>=a && NR<=b {print NR \"\\t\" $0} NR>b {exit}' LOGCPU.TXT; "
                      "awk -v a=$((i6 - 4)) -v b=$((i6 + 5)) 'NR>=a && NR<=b {print NR \"\\t\" $0} NR>b {exit}' LOGCPU.TXT; "
                      "tail -n 3 LOGCPU.TXT | awk -v n=$(wc -l < LOGCPU.TXT) '{print n - 3 + NR \"\\t\" $0}'"),
    # 2026-10-05 的指令:sed -n "7060950,7064630p;7064631q" LOGCPU.TXT > /tmp/v21_post.txt(之後原樣複製)
    "post_reset_trace": (".wsl_build/ctr/v21/ch25/post_reset_trace.txt", [H + "v21/LOGCPU.TXT"],
                         f"cd {H}v21 && sed -n '7060950,7064630p;7064631q' LOGCPU.TXT"),
    # msg_s76.sh:v21~v32 當時一次跑(取前 4 行),v33 另跑後附加
    "post_reset_messages": (".wsl_build/ctr/post_reset_messages.txt",
                            [H + v + "/LOGCPU.TXT" for v in ("v21", "v30", "v31", "v32", "v33")],
                            f"bash '{GEN_WSL}/msg_s76.sh' v21 v30 v31 v32 v33"),
    # reentry_s77.sh(背景任務輸出的前 5 行)
    "guard_reentry_lines": (".wsl_build/ctr/guard_reentry_lines.txt",
                            [H + v + "/LOGCPU.TXT" for v in ("v21", "v30", "v31", "v32", "v33")],
                            f"bash '{GEN_WSL}/reentry_s77.sh' v21 v30 v31 v32 v33 | head -5"),
    # logx_s76.sh v33
    "v33_dosbox_log_excerpt": (".wsl_build/ctr/v33/ch25/dosbox-x_log_excerpt.txt", [H + "v33/dosbox-x.log"],
                               f"bash '{GEN_WSL}/logx_s76.sh' v33"),
}


def _wsl(cmd: str, timeout: int) -> subprocess.CompletedProcess:
    # 明確呼叫 wsl.exe(Windows 上單打 "bash" 也會落到 WSL,但不保證是哪個發行版)。
    # 指令從 stdin 給 bash -s:wsl.exe 會把命令列參數再交給一層 shell 展開,awk 的 $0 / $1 會被吃掉。
    return subprocess.run(["wsl", "-d", "Ubuntu", "--", "bash", "-s"], input=cmd.encode("utf-8"),
                          capture_output=True, timeout=timeout)


def check(name: str, pinned: dict[str, list]) -> tuple[str, str]:
    """重切一個摘錄並比對;回傳 (結果, 說明)。"""
    rel, sources, cmd = EXCERPTS[name]
    missing = _wsl(" ; ".join(f'test -f "{s}" || echo "{s}"' for s in sources), 60).stdout.decode().split()
    if missing:
        return "SOURCE_MISSING", " ".join(missing)
    r = _wsl("set -o pipefail; " + cmd, 3600)
    if r.returncode != 0:
        return "ERROR", f"rc={r.returncode} {r.stderr.decode(errors='replace')[-200:]}"
    size, sha = pinned[rel]
    got = hashlib.sha256(r.stdout).hexdigest()
    if (len(r.stdout), got) == (size, sha):
        return "IDENTICAL", f"{size} bytes"
    return "DIFFERENT", f"重切 {len(r.stdout)} bytes {got[:12]} != 清單 {size} bytes {sha[:12]}"


def selftest(pinned: dict[str, list]) -> int:
    """反向對照(用最快的 post_reset_trace):切法差一行 → DIFFERENT;完整記錄不在 → SOURCE_MISSING;原樣 → IDENTICAL。"""
    rel, sources, cmd = EXCERPTS["post_reset_trace"]
    cases = [
        ("原樣", (rel, sources, cmd), "IDENTICAL"),
        ("起始行 +1", (rel, sources, cmd.replace("7060950,", "7060951,")), "DIFFERENT"),
        ("完整記錄不在", (rel, [H + "v99_missing/LOGCPU.TXT"], cmd), "SOURCE_MISSING"),
    ]
    fails = 0
    for label, spec, want in cases:
        EXCERPTS["_selftest"] = spec
        got, detail = check("_selftest", pinned)
        fails += got != want
        print(f"{'ok  ' if got == want else 'FAIL'} {label}: {got}(應為 {want}) {detail}")
    del EXCERPTS["_selftest"]
    print("selftest", "PASS" if not fails else f"FAIL ({fails})")
    return 1 if fails else 0


def main(argv: list[str]) -> int:
    man = json.loads(MANIFEST.read_text(encoding="utf-8"))["generators"]
    pinned = {k: v for g in man.values() for k, v in g["inputs"].items()}
    if argv[:1] == ["--selftest"]:
        return selftest(pinned)
    names = argv or list(EXCERPTS)
    unknown = [n for n in names if n not in EXCERPTS]
    if unknown:
        raise SystemExit(f"沒有這個摘錄:{unknown}")
    # 鎖定的摘錄本身也要與清單相符,否則比對沒有意義
    bad = 0
    for n in names:
        rel = EXCERPTS[n][0]
        assert rel in pinned, f"{rel} 不在 inputs_manifest.json"
        local = resolve(rel).read_bytes()
        assert hashlib.sha256(local).hexdigest() == pinned[rel][1], f"{rel} 與清單不符"
        verdict, detail = check(n, pinned)
        bad += verdict != "IDENTICAL"
        print(f"{verdict:15s} {n}  {detail}", flush=True)
    print(f"{len(names) - bad}/{len(names)} IDENTICAL")
    return 1 if bad else 0


if __name__ == "__main__":
    sys.exit(main(sys.argv[1:]))
