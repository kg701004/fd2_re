"""以 audit hook 記下這個行程(與繼承環境變數的子行程)開啟、列目錄、匯入的每一個路徑,附加到 $EVTRACE_LOG。"""
import os
import sys

_LOG = os.environ.get("EVTRACE_LOG")
if _LOG:
    _f = open(_LOG, "a", encoding="utf-8")

    def _hook(event, args):
        try:
            if event == "open" and args and isinstance(args[0], (str, bytes, os.PathLike)):
                mode = args[1] if len(args) > 1 and isinstance(args[1], str) else "r"
                _f.write(f"open\t{mode}\t{os.fsdecode(args[0])}\n")
            elif event in ("os.listdir", "os.scandir") and args:
                _f.write(f"list\t-\t{os.fsdecode(args[0]) if args[0] is not None else '.'}\n")
            elif event == "subprocess.Popen":
                _f.write(f"proc\t-\t{args[1]!r}\n")
            elif event == "import" and args and args[1]:
                _f.write(f"import\t-\t{os.fsdecode(args[1])}\n")
            _f.flush()
        except Exception:
            pass

    sys.addaudithook(_hook)
