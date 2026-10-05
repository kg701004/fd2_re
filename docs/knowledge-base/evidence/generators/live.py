"""續六十六:DOSBox-X 即時操作的小工具(包 fd2_dosbox_live_helper.py)。只對原版 FD2.EXE 使用。"""
from __future__ import annotations

import re
import struct
import subprocess
import time
from pathlib import Path

from _evpaths import ROOT  # noqa: E402,F401
HELPER = [r"python", "-X", "utf8", str(ROOT / "tools" / "fd2_dosbox_live_helper.py")]
DELTA = 0x19C000


def run(args: list[str], timeout: int = 120) -> str:
    """執行 helper 子命令並回傳 stdout。"""
    r = subprocess.run(HELPER + args, cwd=ROOT, capture_output=True, text=True, encoding="utf-8",
                       errors="replace", timeout=timeout)
    return r.stdout + r.stderr


class Live:
    """單一 instance 的操作。"""

    def __init__(self, inst: str, out: Path, ubase: int | None = None) -> None:
        self.i = inst
        self.out = out
        out.mkdir(parents=True, exist_ok=True)
        self.ubase = ubase

    def pane(self) -> str:
        r = subprocess.run(["wsl", "-d", "Ubuntu", "tmux", "-L", "fd2harness", "capture-pane", "-t",
                            f"harness-{self.i}", "-p"], capture_output=True, text=True, encoding="utf-8",
                           errors="replace")
        return r.stdout

    def running(self) -> bool:
        lines = [x for x in self.pane().splitlines() if x.strip()]
        return bool(lines) and "Running" in lines[-1]

    def regs(self) -> dict[str, int]:
        p = self.pane()
        out = {}
        for k in ("EAX", "EBX", "ECX", "EDX", "ESI", "EDI", "EBP", "ESP", "EIP"):
            m = re.search(k + r"=([0-9A-F]{8})", p)
            if m:
                out[k] = int(m.group(1), 16)
        return out

    def dump(self, lin: int, n: int, name: str = "tmp") -> bytes:
        f = self.out / f"{name}.bin"
        run(["mem", "dump", "--instance", self.i, "--selector", "0170", "--linear", f"{lin:x}",
             "--bytecount", f"{n:x}", "--out", str(f)])
        return f.read_bytes()

    def d32(self, lin: int) -> int:
        return struct.unpack("<I", self.dump(lin, 4, "d32"))[0]

    def halt(self, tries: int = 8) -> bool:
        """進除錯器並確認 [0x53a45] 是預期的單位表指標(避開即時模式停在 DOS 呼叫內)。"""
        for _ in range(tries):
            run(["enter-debugger", "--instance", self.i])
            time.sleep(3)
            p = self.d32(0x53A45 + DELTA)
            if self.ubase is None and 0x200000 < p < 0x300000:
                self.ubase = p
            if p == self.ubase:
                return True
            run(["resume", "--instance", self.i])
            time.sleep(2)
        return False

    def cmd(self, c: str) -> str:
        r = run(["debugger-cmd", "--instance", self.i, c])
        time.sleep(0.3)
        return r

    def sm(self, lin: int, data: bytes) -> None:
        self.cmd(f"SM 0170:{lin:x} " + " ".join(f"{b:02x}" for b in data))

    def ua(self, idx: int, off: int = 0) -> int:
        assert self.ubase is not None
        return self.ubase + idx * 80 + off

    def units(self, name: str, count: int | None = None) -> bytes:
        if count is None:
            count = self.d32(0x53BEB + DELTA) & 0xFF
        return self.dump(self.ubase, count * 80, name)

    def resume(self) -> None:
        run(["resume", "--instance", self.i])
        time.sleep(1)

    def key(self, k: str, wait: float = 1.0) -> None:
        run(["key", "--instance", self.i, "--wait", str(wait), k])

    def shot(self, name: str) -> Path:
        f = self.out / f"{name}.png"
        run(["screenshot", "--instance", self.i, "--out", str(f)])
        return f

    def cursor(self) -> tuple[int, int]:
        b = self.dump(0x53AB1 + DELTA, 8, "cursor")
        return struct.unpack("<ii", b)

    def wait_stop(self, max_s: float = 30, poll: float = 1.5) -> dict[str, int] | None:
        """等斷點停下(pane 最後一行不再是 Running);逾時回 None。"""
        t0 = time.time()
        while time.time() - t0 < max_s:
            time.sleep(poll)
            if not self.running():
                return self.regs()
        return None
