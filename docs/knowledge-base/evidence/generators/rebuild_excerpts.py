"""從 WSL 裡的完整 DOSBox-X 記錄重新切出摘錄,與 inputs_manifest.json 鎖定的摘錄逐 byte 比對。

續七十五~七十七有幾個輸入是從大型記錄(LOGCPU.TXT 每份約 5 GB、dosbox-x.log)切出的摘錄;完整記錄原本留在
WSL 的 `~/fd2-run-harness-<run>/`,不搬到 Windows、不進 git。2026-10-08 起 WSL 裡的完整記錄已刪除,
預設模式會回報 7 個 SOURCE_MISSING,要用下面的 `--from-backup`。這裡記下每個摘錄的切法(與存檔的驅動腳本相同),
重切到 stdout 比對,不寫任何檔案。只讀記錄檔,不啟動 DOSBox-X。

結果:IDENTICAL / DIFFERENT / SOURCE_MISSING(WSL 裡的完整記錄已不在)/ SOURCE_CHANGED(記錄大小與
SOURCE_LOGS 不符,例如被新的執行覆寫)/ ERROR。全部 IDENTICAL 才 exit 0。

完整記錄另有壓縮備份(倉庫外的本機備份夾,`full_logs_manifest.tsv` + 每份一個 `.xz`)。WSL 裡的記錄不在時用
`--from-backup <備份夾>`:把需要的記錄解壓到 WSL 的暫存目錄,逐份以 SOURCE_LOGS 的大小與 sha256 驗證,
再以同一組切法重切(切法裡的路徑都是 `$HOME/fd2-run-harness-…`,所以只把 HOME 指到暫存目錄),最後刪除暫存目錄。

用法:python rebuild_excerpts.py [摘錄名稱 ...]     不給 = 全部(掃描約 30 GB,需數分鐘)
      python rebuild_excerpts.py --from-backup <備份夾> [摘錄名稱 ...]
      python rebuild_excerpts.py --selftest [--from-backup <備份夾>]
                                                 反向對照(切法差一行 → DIFFERENT、記錄不在 → SOURCE_MISSING、
                                                  大小不符 → SOURCE_CHANGED、備份內容不符 → 還原失敗);
                                                  WSL 沒有 v21 記錄又沒給備份夾時回報 BLOCKED(rc 2)
"""
from __future__ import annotations

import hashlib
import json
import lzma
import subprocess
import sys
import tempfile
from pathlib import Path

from _evpaths import GEN_DIR, MANIFEST, ROOT, resolve

# WSL 端看到的本目錄(存檔的驅動腳本可直接執行的那幾支用它)
_drive, _rest = str(GEN_DIR).split(":", 1)
GEN_WSL = "/mnt/" + _drive.lower() + _rest.replace("\\", "/")
H = "$HOME/fd2-run-harness-"
# 完整記錄的身分(相對 $HOME/fd2-run-harness- 的路徑 -> (bytes, sha256)),2026-10-05 備份時量得
# (v21 的值另與 trace_excerpt.txt 切出當時印下的 bytes / sha256 相同)
SOURCE_LOGS: dict[str, tuple[int, str]] = {
    "v21/LOGCPU.TXT": (5402271701, "10d20cbdae4634c4f97d2b6993105ff6a24699fb541bac0be3095bf32999fdbb"),
    "v30/LOGCPU.TXT": (5402271426, "c7da3eae26899450d38cbdc66c9825693c32989bc03aabb21d995b5357a0fcaa"),
    "v31/LOGCPU.TXT": (5402271624, "73cbad19941e16e476f2811dedadc4daec2d0166e646408ec23beac8f704ee23"),
    "v32/LOGCPU.TXT": (5419048933, "5cd1173a86564dd058e64cdb5d7efc99781531e7b58f098a8b58ae8937e256d1"),
    "v33/LOGCPU.TXT": (5402270869, "386299bb885e3c8a306a73a82978ecb8c447e70a5c876de79b83b44724bde32f"),
    "v33/dosbox-x.log": (193381323, "6c20a033cf32c8dfa2afc1eda2d729c0d69680ba39b0db01abd4923a6c7372de"),
}
# --from-backup 的暫存目錄(WSL 端);只會刪除本程式自己建立的這個目錄
RESTORE_ROOT = "/tmp/fd2-excerpt-restore"

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


def _to_wsl(path: Path) -> str:
    """Windows 路徑 -> WSL 的 /mnt/<磁碟>/… 路徑。"""
    drive, rest = str(path.resolve()).split(":", 1)
    return "/mnt/" + drive.lower() + rest.replace("\\", "/")


def _home(home: str | None) -> str:
    """指令前綴:把 HOME 指到還原目錄(None = 不改,用 WSL 裡原本的記錄)。"""
    return f"export HOME='{home}'; " if home else ""


class RestoreError(Exception):
    """備份不完整,或還原出的記錄與 SOURCE_LOGS 不符。"""


def restore(backup: Path, keys: list[str]) -> None:
    """把 keys 指定的完整記錄從備份夾解壓到 RESTORE_ROOT,逐份驗證大小與 sha256。

    Args:
        backup: 備份夾(Windows 路徑,含 full_logs_manifest.tsv 與 .xz)。
        keys: SOURCE_LOGS 的鍵(例如 "v21/LOGCPU.TXT")。

    Raises:
        RestoreError: 備份清單缺項、與 SOURCE_LOGS 不一致,或還原內容不符。
    """
    rows = {}
    for line in (backup / "full_logs_manifest.tsv").read_text(encoding="utf-8").splitlines()[1:]:
        path, size, sha, xzname, _ = line.split("\t")
        rows[path.removeprefix("fd2-run-harness-")] = (int(size), sha, xzname)
    for k in keys:
        if k not in rows:
            raise RestoreError(f"備份清單沒有 {k}")
        # 備份清單只是備份的一部分;身分以本程式的 SOURCE_LOGS 為準,兩者不一致就不還原
        if rows[k][:2] != SOURCE_LOGS[k]:
            raise RestoreError(f"備份清單的 {k} 與 SOURCE_LOGS 不一致")
        size, sha, xzname = rows[k]
        dst = f"{RESTORE_ROOT}/fd2-run-harness-{k}"
        r = _wsl(f"set -euo pipefail; mkdir -p \"$(dirname '{dst}')\"; xz -dc '{_to_wsl(backup / xzname)}' > '{dst}'; "
                 f"stat -c %s '{dst}'; sha256sum '{dst}' | cut -c1-64", 3600)
        out = r.stdout.decode().split()
        if r.returncode != 0 or out != [str(size), sha]:
            raise RestoreError(f"還原的 {k} 不符:rc={r.returncode} {out} {r.stderr.decode(errors='replace')[-200:]}")


def cleanup_restore() -> None:
    """刪除 RESTORE_ROOT(只有本程式建立的暫存目錄)。"""
    _wsl(f"rm -rf '{RESTORE_ROOT}'", 600)


def check(name: str, pinned: dict[str, list], home: str | None = None) -> tuple[str, str]:
    """重切一個摘錄並比對;回傳 (結果, 說明)。home 不為 None 時從那個目錄下的記錄重切。"""
    rel, sources, cmd = EXCERPTS[name]
    pre = _home(home)
    missing = _wsl(pre + " ; ".join(f'test -f "{s}" || echo "{s}"' for s in sources), 60).stdout.decode().split()
    if missing:
        return "SOURCE_MISSING", " ".join(missing)
    # 記錄大小必須等於 SOURCE_LOGS(便宜的身分檢查;完整的 sha256 在還原時驗)
    sizes = _wsl(pre + " ; ".join(f'stat -c %s "{s}"' for s in sources), 60).stdout.decode().split()
    want = [str(SOURCE_LOGS[s.removeprefix(H)][0]) for s in sources]
    if sizes != want:
        return "SOURCE_CHANGED", f"大小 {sizes} != {want}"
    r = _wsl(pre + "set -o pipefail; " + cmd, 3600)
    if r.returncode != 0:
        return "ERROR", f"rc={r.returncode} {r.stderr.decode(errors='replace')[-200:]}"
    size, sha = pinned[rel]
    got = hashlib.sha256(r.stdout).hexdigest()
    if (len(r.stdout), got) == (size, sha):
        return "IDENTICAL", f"{size} bytes"
    return "DIFFERENT", f"重切 {len(r.stdout)} bytes {got[:12]} != 清單 {size} bytes {sha[:12]}"


def selftest(pinned: dict[str, list], backup: Path | None = None) -> int:
    """反向對照(用最快的 post_reset_trace):切法差一行 → DIFFERENT;完整記錄不在 → SOURCE_MISSING;原樣 → IDENTICAL。

    Args:
        pinned: inputs_manifest.json 鎖定的 (bytes, sha256)。
        backup: 備份夾;給了就先把 v21 記錄還原到 RESTORE_ROOT 再對照(WSL 裡的記錄 2026-10-08 已刪除)。

    Returns:
        0 = 全部通過;1 = 有對照失敗;2 = 沒有 v21 記錄可用(BLOCKED,正向對照無法執行)。
    """
    rel, sources, cmd = EXCERPTS["post_reset_trace"]
    k = "v21/LOGCPU.TXT"
    home = None
    fails = 0
    try:
        if backup is not None:
            try:
                restore(backup, [k])
            except RestoreError as e:
                print(f"FAIL 還原 v21 記錄: {e}")
                return 1
            home = RESTORE_ROOT
        elif _wsl(f'test -f "{H}{k}"', 60).returncode != 0:
            # 正向對照(原樣 → IDENTICAL)必須用真的記錄;沒有記錄時不能把其他項目的 ok 當成通過
            print(f"BLOCKED WSL 裡沒有 {H}{k}(2026-10-08 已刪除);改用 --selftest --from-backup <備份夾>")
            return 2
        cases = [
            ("原樣", (rel, sources, cmd), "IDENTICAL"),
            ("起始行 +1", (rel, sources, cmd.replace("7060950,", "7060951,")), "DIFFERENT"),
            ("完整記錄不在", (rel, [H + "v99_missing/LOGCPU.TXT"], cmd), "SOURCE_MISSING"),
        ]
        for label, spec, want in cases:
            EXCERPTS["_selftest"] = spec
            got, detail = check("_selftest", pinned, home)
            fails += got != want
            print(f"{'ok  ' if got == want else 'FAIL'} {label}: {got}(應為 {want}) {detail}")
        # 記錄大小與 SOURCE_LOGS 不符(模擬被新的執行覆寫)→ SOURCE_CHANGED
        orig = SOURCE_LOGS[k]
        SOURCE_LOGS[k] = (orig[0] + 1, orig[1])
        EXCERPTS["_selftest"] = (rel, sources, cmd)
        try:
            got, detail = check("_selftest", pinned, home)
        finally:
            SOURCE_LOGS[k] = orig
            del EXCERPTS["_selftest"]
        fails += got != "SOURCE_CHANGED"
        print(f"{'ok  ' if got == 'SOURCE_CHANGED' else 'FAIL'} 記錄大小不符: {got}(應為 SOURCE_CHANGED) {detail}")
    finally:
        if backup is not None:
            cleanup_restore()
    # 備份還原:.xz 內容不是那份記錄、備份清單與 SOURCE_LOGS 不一致 → 都必須 RestoreError(不能還原成功)。
    # 暫存備份夾放在 .wsl_build(gitignore、WSL 看得到)
    (ROOT / ".wsl_build").mkdir(exist_ok=True)
    with tempfile.TemporaryDirectory(dir=ROOT / ".wsl_build") as td:
        b = Path(td)
        (b / "x.xz").write_bytes(lzma.compress(b"not the log\n"))
        for label, (size, sha) in (("備份內容不符", orig), ("備份清單與 SOURCE_LOGS 不一致", (orig[0], "0" * 64))):
            (b / "full_logs_manifest.tsv").write_text(
                f"path\tsize\tsha256\txz\txz_size\nfd2-run-harness-{k}\t{size}\t{sha}\tx.xz\t0\n", encoding="utf-8")
            try:
                restore(b, [k])
                got, detail = "RESTORED", ""
            except RestoreError as e:
                got, detail = "RestoreError", str(e)[:120]
            finally:
                cleanup_restore()
            fails += got != "RestoreError"
            print(f"{'ok  ' if got == 'RestoreError' else 'FAIL'} {label}: {got}(應為 RestoreError) {detail}")
    print("selftest", "PASS" if not fails else f"FAIL ({fails})")
    return 1 if fails else 0


def main(argv: list[str]) -> int:
    man = json.loads(MANIFEST.read_text(encoding="utf-8"))["generators"]
    pinned = {k: v for g in man.values() for k, v in g["inputs"].items()}
    if argv[:1] == ["--selftest"]:
        if argv[1:2] == ["--from-backup"]:
            if len(argv) < 3:
                raise SystemExit("--from-backup 需要備份夾路徑")
            return selftest(pinned, Path(argv[2]))
        return selftest(pinned)
    backup = None
    if argv[:1] == ["--from-backup"]:
        if len(argv) < 2:
            raise SystemExit("--from-backup 需要備份夾路徑")
        backup, argv = Path(argv[1]), argv[2:]
    names = argv or list(EXCERPTS)
    unknown = [n for n in names if n not in EXCERPTS]
    if unknown:
        raise SystemExit(f"沒有這個摘錄:{unknown}")
    # 鎖定的摘錄本身也要與清單相符,否則比對沒有意義
    for n in names:
        rel = EXCERPTS[n][0]
        assert rel in pinned, f"{rel} 不在 inputs_manifest.json"
        local = resolve(rel).read_bytes()
        assert hashlib.sha256(local).hexdigest() == pinned[rel][1], f"{rel} 與清單不符"
    home = None
    bad = 0
    try:
        if backup is not None:
            keys = sorted({s.removeprefix(H) for n in names for s in EXCERPTS[n][1]})
            print(f"從備份還原 {len(keys)} 份完整記錄到 WSL {RESTORE_ROOT}(逐份驗 sha256)…", flush=True)
            try:
                restore(backup, keys)
            except RestoreError as e:
                print(f"RESTORE_FAILED  {e}")
                return 1
            home = RESTORE_ROOT
        for n in names:
            verdict, detail = check(n, pinned, home)
            bad += verdict != "IDENTICAL"
            print(f"{verdict:15s} {n}  {detail}", flush=True)
    finally:
        if backup is not None:
            cleanup_restore()
    print(f"{len(names) - bad}/{len(names)} IDENTICAL")
    return 1 if bad else 0


if __name__ == "__main__":
    sys.exit(main(sys.argv[1:]))
