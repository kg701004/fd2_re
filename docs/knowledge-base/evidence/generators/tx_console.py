"""終端輸出(`.wsl_build/ctr/console/`)與 Claude Code 對話紀錄之間的匯出、比對與備份抽取。

續四十六~六十四的斷點讀值只印在終端,原始來源是 Claude Code 對話紀錄 jsonl 裡 Bash 呼叫的
`toolUseResult.stdout`。這支工具:

- `check`:對 console 目錄裡每一對 `<UTC>_<id>.txt` / `.meta.json`,在對話紀錄裡找同一個 tool_use_id,
  比對 stdout 逐字相同、meta 的指令 / 說明 / 時間 / stderr 也相同。結果 IDENTICAL / DIFFERENT(.txt 不同)/
  META_DIFFERENT / NOT_IN_TRANSCRIPT / CONFLICT(同一 id 有兩筆不同的非空 stdout)。全部 IDENTICAL 才 exit 0。
- `export`:把指定 id 寫成 console 檔(已存在且內容相同就略過;不同則失敗,不覆寫)。
- `extract`:把 console 檔用到的 id(再加上命令列給的 id)在對話紀錄裡的原始紀錄行原樣抽出,寫成 `.jsonl.xz`;
  對話紀錄被清掉之後,`check --transcript <抽出檔>` 仍能比對。抽出檔可能含原版程式的讀值,只放倉庫外備份夾。

同一個 tool_use_id 在對話紀錄裡可能有多筆結果紀錄(其中有 stdout 為空的),只取非空的;非空的必須彼此相同。

只讀對話紀錄,不啟動 DOSBox-X。

用法:python tx_console.py check --transcript <jsonl 或 .jsonl.xz> [--console-dir <目錄>]
      python tx_console.py export --transcript <...> <tool_use_id> [...]
      python tx_console.py extract --transcript <...> --out <檔名.jsonl.xz> [額外 tool_use_id ...]
      python tx_console.py --selftest     反向對照(.txt 差一個 byte、meta 指令不同、id 不在紀錄裡、
                                          同 id 兩筆不同輸出、export 遇到不同內容、抽出檔往返)
"""
from __future__ import annotations

import argparse
import hashlib
import json
import lzma
import shutil
import sys
import tempfile
from dataclasses import dataclass, field
from pathlib import Path
from typing import IO, Iterator

from _evpaths import ROOT

CONSOLE_DIR = ROOT / ".wsl_build/ctr/console"
SOURCE = "Claude Code session 064f5671-708e-478d-aa85-2e95400484d6 對話紀錄的 toolUseResult.stdout(原樣)"
META_KEYS = ("id", "ts", "cmd_ts", "cmd", "desc", "stderr")


@dataclass
class Record:
    """一個 tool_use_id 在對話紀錄裡的指令與輸出。

    Attributes:
        cmd_ts: tool_use 紀錄的時間。
        cmd: Bash / PowerShell 指令。
        desc: 呼叫時的說明。
        ts: 第一筆非空結果紀錄的時間。
        stdout: 非空的 stdout(多筆時必須相同)。
        stderr: 與 `ts` 同一筆結果紀錄的 stderr。
        conflicts: 不同於 `stdout` 的其他非空輸出筆數。
        raw_lines: 含這個 id 的原始紀錄行(extract 用)。
    """

    cmd_ts: str = ""
    cmd: str = ""
    desc: str = ""
    ts: str = ""
    stdout: str = ""
    stderr: str = ""
    conflicts: int = 0
    raw_lines: list[bytes] = field(default_factory=list)


def _open(path: Path) -> IO[bytes]:
    """以 binary 開啟對話紀錄;`.xz` 結尾的自動解壓。"""
    return lzma.open(path, "rb") if path.suffix == ".xz" else open(path, "rb")


def _lines(path: Path) -> Iterator[bytes]:
    with _open(path) as f:
        yield from f


def scan(path: Path, ids: set[str]) -> dict[str, Record]:
    """掃描對話紀錄,收集指定 id 的指令與輸出。

    Args:
        path: 對話紀錄 jsonl(可為 .xz)。
        ids: 要找的 tool_use_id。

    Returns:
        id -> Record;對話紀錄裡完全沒有的 id 不在結果裡。
    """
    keys = [i.encode() for i in ids]
    out: dict[str, Record] = {}
    for line in _lines(path):
        # 先以 bytes 子字串過濾,避免對 1.7 GB 的紀錄逐行 json 解析
        if not any(k in line for k in keys):
            continue
        d = json.loads(line)
        content = (d.get("message") or {}).get("content")
        if not isinstance(content, list):
            continue
        hit: set[str] = set()
        for c in content:
            if not isinstance(c, dict):
                continue
            if c.get("type") == "tool_use" and c.get("id") in ids:
                hit.add(c["id"])
                r = out.setdefault(c["id"], Record())
                inp = c.get("input") or {}
                if not r.cmd_ts:
                    r.cmd_ts, r.cmd, r.desc = d.get("timestamp", ""), inp.get("command", ""), inp.get("description", "")
            elif c.get("type") == "tool_result" and c.get("tool_use_id") in ids:
                hit.add(c["tool_use_id"])
                r = out.setdefault(c["tool_use_id"], Record())
                tur = d.get("toolUseResult")
                so = tur.get("stdout") if isinstance(tur, dict) else None
                if not so:
                    continue
                if not r.stdout:
                    r.ts, r.stdout, r.stderr = d.get("timestamp", ""), so, tur.get("stderr") or ""
                elif so != r.stdout:
                    r.conflicts += 1
        # 只記結構上真的屬於該 id 的行(tool_use / tool_result),不靠子字串
        for i in hit:
            out[i].raw_lines.append(line if line.endswith(b"\n") else line + b"\n")
    return out


def console_pairs(console_dir: Path) -> dict[str, Path]:
    """console 目錄裡的 id -> .txt 路徑(由 .meta.json 的 id 欄位決定)。"""
    pairs: dict[str, Path] = {}
    for m in sorted(console_dir.glob("*.meta.json")):
        i = json.loads(m.read_text(encoding="utf-8"))["id"]
        pairs[i] = m.with_name(m.name[: -len(".meta.json")] + ".txt")
    return pairs


def _meta(i: str, r: Record) -> dict[str, str]:
    return {"id": i, "ts": r.ts, "cmd_ts": r.cmd_ts, "cmd": r.cmd, "desc": r.desc, "stderr": r.stderr, "source": SOURCE}


def _stem(i: str, r: Record) -> str:
    return r.ts[:19].replace("-", "").replace(":", "") + "_" + i


def check(transcript: Path, console_dir: Path) -> dict[str, str]:
    """比對每份 console 匯出與對話紀錄,回傳 id -> 判定。"""
    pairs = console_pairs(console_dir)
    recs = scan(transcript, set(pairs))
    res: dict[str, str] = {}
    for i, txt in pairs.items():
        r = recs.get(i)
        if r is None or not r.stdout:
            res[i] = "NOT_IN_TRANSCRIPT"
        elif r.conflicts:
            res[i] = "CONFLICT"
        elif txt.read_bytes() != r.stdout.encode("utf-8"):
            res[i] = "DIFFERENT"
        else:
            meta = json.loads(txt.with_name(txt.name[:-4] + ".meta.json").read_text(encoding="utf-8"))
            want = _meta(i, r)
            same = all(meta.get(k) == want[k] for k in META_KEYS) and txt.name[:-4] == _stem(i, r)
            res[i] = "IDENTICAL" if same else "META_DIFFERENT"
    return res


def _write_once(p: Path, data: bytes) -> None:
    # 已存在就只比對,絕不覆寫既有原始紀錄
    if p.exists():
        if p.read_bytes() != data:
            raise SystemExit(f"{p} 已存在且內容不同,不覆寫")
        return
    p.write_bytes(data)


def export(transcript: Path, console_dir: Path, ids: list[str]) -> list[Path]:
    """把指定 id 的輸出寫成 console 檔,回傳 .txt 路徑。"""
    recs = scan(transcript, set(ids))
    bad = [i for i in ids if i not in recs or not recs[i].stdout or recs[i].conflicts]
    if bad:
        raise SystemExit(f"對話紀錄裡沒有、輸出為空或有兩筆不同輸出:{bad}")
    console_dir.mkdir(parents=True, exist_ok=True)
    out = []
    for i in ids:
        r = recs[i]
        stem = _stem(i, r)
        _write_once(console_dir / f"{stem}.txt", r.stdout.encode("utf-8"))
        meta = json.dumps(_meta(i, r), ensure_ascii=False, indent=1) + "\n"
        _write_once(console_dir / f"{stem}.meta.json", meta.encode("utf-8"))
        out.append(console_dir / f"{stem}.txt")
    return out


def extract(transcript: Path, console_dir: Path, out: Path, extra: list[str]) -> tuple[int, int, str]:
    """抽出 console 檔用到的 id 與額外 id 的原始紀錄行,寫成 .jsonl.xz。

    Returns:
        (id 數, 紀錄行數, 抽出檔 sha256)。
    """
    ids = set(console_pairs(console_dir)) | set(extra)
    recs = scan(transcript, ids)
    missing = sorted(ids - set(recs))
    if missing:
        raise SystemExit(f"對話紀錄裡沒有:{missing}")
    if out.exists():
        raise SystemExit(f"{out} 已存在,不覆寫")
    # 依原本在對話紀錄裡的順序保留每一行(同一行可能同時含多個 id,只寫一次)
    keep = {ln for r in recs.values() for ln in r.raw_lines}
    n = 0
    with lzma.open(out, "wb", preset=9) as f:
        for line in _lines(transcript):
            ln = line if line.endswith(b"\n") else line + b"\n"
            if ln in keep:
                f.write(ln)
                keep.discard(ln)
                n += 1
    return len(ids), n, hashlib.sha256(out.read_bytes()).hexdigest()


def _summary(res: dict[str, str]) -> int:
    counts: dict[str, int] = {}
    for i, v in sorted(res.items()):
        counts[v] = counts.get(v, 0) + 1
        if v != "IDENTICAL":
            print(v, i)
    print(" ".join(f"{k}={v}" for k, v in sorted(counts.items())), f"total={len(res)}")
    return 0 if res and all(v == "IDENTICAL" for v in res.values()) else 1


def _selftest() -> int:
    """以合成的對話紀錄驗證每一種判定都會出現,且每個錯誤都會被擋下。"""
    ok = True

    def expect(name: str, got: object, want: object) -> None:
        nonlocal ok
        good = got == want
        ok &= good
        print("PASS" if good else "FAIL", name, got if not good else "")

    def rec(obj: dict) -> str:
        return json.dumps(obj, ensure_ascii=False) + "\n"

    def use(i: str, ts: str, cmd: str) -> str:
        return rec({"timestamp": ts, "message": {"content": [{"type": "tool_use", "id": i, "name": "Bash",
                                                               "input": {"command": cmd, "description": "d" + i}}]}})

    def res(i: str, ts: str, so: str) -> str:
        return rec({"timestamp": ts, "toolUseResult": {"stdout": so, "stderr": ""},
                    "message": {"content": [{"type": "tool_result", "tool_use_id": i}]}})

    with tempfile.TemporaryDirectory() as td:
        t = Path(td)
        tx = t / "tx.jsonl"
        # A:先有一筆空輸出(實際紀錄就有這種),再有真正輸出;B:一般;C:兩筆不同輸出
        tx.write_text(use("A", "2026-01-01T00:00:00.000Z", "cmdA") + res("A", "2026-01-01T00:00:01.000Z", "")
                      + res("A", "2026-01-01T00:00:02.000Z", "EAX=1\n") + rec({"timestamp": "x", "message": {}})
                      # 內文提到 A、B 但不屬於它們的紀錄:抽出時不能收
                      + rec({"timestamp": "y", "message": {"content": [{"type": "text", "text": "A B"}]}})
                      + use("B", "2026-01-01T00:01:00.000Z", "cmdB") + res("B", "2026-01-01T00:01:01.000Z", "EBX=2\n中")
                      + use("C", "2026-01-01T00:02:00.000Z", "cmdC") + res("C", "2026-01-01T00:02:01.000Z", "x\n")
                      + res("C", "2026-01-01T00:02:02.000Z", "y\n"), encoding="utf-8", newline="\n")
        con = t / "console"
        export(tx, con, ["A", "B"])
        expect("export 後 check 全 IDENTICAL", check(tx, con), {"A": "IDENTICAL", "B": "IDENTICAL"})
        expect("A 取非空那筆的時間", sorted(p.name for p in con.glob("*A.txt")), ["20260101T000002_A.txt"])
        export(tx, con, ["A"])  # 已存在且相同:略過
        try:
            export(tx, con, ["C"])
            expect("同 id 兩筆不同輸出 → export 失敗", "no error", "SystemExit")
        except SystemExit:
            expect("同 id 兩筆不同輸出 → export 失敗", "SystemExit", "SystemExit")

        b = next(con.glob("*_B.txt"))
        orig = b.read_bytes()
        b.write_bytes(orig[:-1] + bytes([orig[-1] ^ 1]))
        expect(".txt 差一個 byte → DIFFERENT", check(tx, con)["B"], "DIFFERENT")
        try:
            export(tx, con, ["B"])
            expect("export 遇到不同內容 → 失敗且不覆寫", "no error", "SystemExit")
        except SystemExit:
            expect("export 遇到不同內容 → 失敗且不覆寫", b.read_bytes() != orig, True)
        b.write_bytes(orig)

        m = next(con.glob("*_A.meta.json"))
        mo = m.read_text(encoding="utf-8")
        m.write_text(mo.replace("cmdA", "cmdX"), encoding="utf-8", newline="\n")
        expect("meta 指令不同 → META_DIFFERENT", check(tx, con)["A"], "META_DIFFERENT")
        m.write_text(mo, encoding="utf-8", newline="\n")

        # C 的 console 檔(手工放入)→ CONFLICT;不在紀錄裡的 Z → NOT_IN_TRANSCRIPT
        (con / "20260101T000201_C.txt").write_bytes(b"x\n")
        (con / "20260101T000201_C.meta.json").write_text(json.dumps({"id": "C"}), encoding="utf-8")
        (con / "20260101T000000_Z.txt").write_bytes(b"z")
        (con / "20260101T000000_Z.meta.json").write_text(json.dumps({"id": "Z"}), encoding="utf-8")
        r = check(tx, con)
        expect("同 id 兩筆不同輸出 → CONFLICT", r["C"], "CONFLICT")
        expect("id 不在紀錄裡 → NOT_IN_TRANSCRIPT", r["Z"], "NOT_IN_TRANSCRIPT")
        expect("有任一非 IDENTICAL → exit 1", _summary(r), 1)
        for p in list(con.glob("*_C.*")) + list(con.glob("*_Z.*")):
            p.unlink()

        xz = t / "sub.jsonl.xz"
        nid, nl, _ = extract(tx, con, xz, [])
        expect("抽出 2 個 id、5 行(A 的 3 行 + B 的 2 行,不含無關行)", (nid, nl), (2, 5))
        expect("抽出檔往返 check 全 IDENTICAL", check(xz, con), {"A": "IDENTICAL", "B": "IDENTICAL"})
        try:
            extract(tx, con, xz, [])
            expect("抽出檔已存在 → 不覆寫", "no error", "SystemExit")
        except SystemExit:
            expect("抽出檔已存在 → 不覆寫", True, True)
        shutil.rmtree(con)
    print("SELFTEST", "PASS" if ok else "FAIL")
    return 0 if ok else 1


def main(argv: list[str]) -> int:
    """命令列入口。"""
    if argv == ["--selftest"]:
        return _selftest()
    ap = argparse.ArgumentParser(description=__doc__.splitlines()[0])
    ap.add_argument("action", choices=["check", "export", "extract"])
    ap.add_argument("ids", nargs="*")
    ap.add_argument("--transcript", type=Path, required=True)
    ap.add_argument("--console-dir", type=Path, default=CONSOLE_DIR)
    ap.add_argument("--out", type=Path)
    a = ap.parse_args(argv)
    if a.action == "check":
        return _summary(check(a.transcript, a.console_dir))
    if a.action == "export":
        for p in export(a.transcript, a.console_dir, a.ids):
            print(p.relative_to(ROOT).as_posix() if p.is_relative_to(ROOT) else p)
        return 0
    if a.out is None:
        ap.error("extract 需要 --out")
    nid, nl, sha = extract(a.transcript, a.console_dir, a.out, a.ids)
    print(f"ids={nid} lines={nl} sha256={sha} -> {a.out}")
    return 0


if __name__ == "__main__":
    sys.exit(main(sys.argv[1:]))
