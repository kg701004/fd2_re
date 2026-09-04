"""`fd2_dosbox_live_helper` 的路徑解析回歸測試。

為什麼要有這一份
----------------
2026-09-04:`fd2_trial_runner.py` 連續兩輪、10 次試驗**全滅**,錯誤看起來是
`_eip()` 裡的 `IndexError`。修好 `_eip` 之後錯誤原封不動——**真正的根因**是
`subprocess.run(["bash", ...])` 從 Windows python.exe 呼叫時,在這台機器上解析到
`C:\\Windows\\System32\\bash.exe`(WSL 轉接器),不是 Git Bash。互動式 shell 的
`where bash` 顯示 Git Bash 排第一,是因為互動式 shell 的 PATH 被 Git Bash 的 profile
改過;`subprocess.run` 用的是未經修改的原始環境 PATH,順序不同。於是整條驅動流程跑進
**WSL 自己的 python3**,`Path(__file__).resolve()` 給出沒有磁碟機代號冒號的 POSIX 路徑,
而 `SH_SCRIPT_WSL`/`to_wsl_path` 舊版寫死假設一定有冒號可切——這才是 IndexError/
ValueError 真正的來源,且**每次都會發生**,不是機率性的,只是手動用互動式 Bash 工具
重現時,那條路徑天生解析到 Git Bash,測不出來。

這個檔案測兩件事,兩者都不需要真的驅動任何 DOSBox 實例:
1. `GIT_BASH` 明確指到 Git Bash,不是 System32 裡的 WSL 轉接器。
2. `_to_wsl_path`/`to_wsl_path` 對兩種輸入(Windows 路徑、已經是 POSIX 的路徑)
   都要給出一樣的結果——這正是當初漏掉的那個分支。
"""

import sys
import unittest
from pathlib import Path

sys.path.insert(0, str(Path(__file__).resolve().parent))

import fd2_dosbox_live_helper as H


class GitBashResolutionTest(unittest.TestCase):
    def test_git_bash_is_not_the_wsl_stub(self):
        """2026-09-04 的實際事故:裸 "bash" 解析到 System32 的 WSL 轉接器。"""
        self.assertNotIn("system32", H.GIT_BASH.lower(),
                        "GIT_BASH 解析到了 WSL 轉接器,不是 Git Bash——"
                        "這正是造成 10 次試驗全滅的那個 bug")

    def test_git_bash_path_exists(self):
        self.assertTrue(Path(H.GIT_BASH).is_file(), f"{H.GIT_BASH} 不存在")

    def test_git_bash_is_actually_mingw(self):
        """不只檢查路徑字面上不含 system32,還要證明執行起來真的是 Git Bash/MSYS,
        不是路徑碰巧沒寫 system32 但其實還是別的東西。"""
        import subprocess
        r = subprocess.run([H.GIT_BASH, "-c", "uname -s"],
                           capture_output=True, text=True, timeout=15)
        self.assertIn("MINGW", r.stdout.upper(),
                      f"GIT_BASH({H.GIT_BASH}) 執行後 uname 沒有回報 MINGW:{r.stdout!r}")


class ToWslPathBothInputShapesTest(unittest.TestCase):
    """**兩個方向都要測**,這是本目錄一貫的規則。只測 Windows 路徑那一半的話,
    2026-09-04 的 bug(輸入已經是 POSIX 路徑時整支函式崩潰)不會被抓到。"""

    def test_windows_style_path(self):
        p = Path(r"C:\Users\kg701\Desktop\GAME\fd2_re\tools\x.sh")
        self.assertEqual(H._to_wsl_path(p), "/mnt/c/Users/kg701/Desktop/GAME/fd2_re/tools/x.sh")

    def test_posix_style_path_does_not_raise(self):
        """這正是 2026-09-04 崩潰的那個輸入形狀:已經是 POSIX 路徑,沒有冒號可切。"""
        p = Path("/mnt/c/Users/kg701/Desktop/GAME/fd2_re/tools/x.sh")
        self.assertEqual(H._to_wsl_path(p), "/mnt/c/Users/kg701/Desktop/GAME/fd2_re/tools/x.sh")

    def test_both_shapes_converge_to_the_same_result(self):
        w = Path(r"C:\a\b\c.sh")
        p = Path("/mnt/c/a/b/c.sh")
        self.assertEqual(H._to_wsl_path(w), H._to_wsl_path(p))

    def test_public_to_wsl_path_delegates_correctly(self):
        # to_wsl_path 呼叫 .resolve(),所以用一個真實存在的路徑(這個檔案自己)。
        got = H.to_wsl_path(Path(__file__))
        self.assertTrue(got.startswith("/mnt/"), got)
        self.assertNotIn("\\", got)
        self.assertNotIn(":", got)

    def test_public_to_wsl_path_survives_a_posix_shaped_resolve(self):
        """**這一條才是真正有鑑別力的**:上一條在 Windows python 下測不出舊 bug,
        因為 `Path.resolve()` 在這個環境永遠補回磁碟機代號,天生造不出會讓舊版
        `to_wsl_path`(`p.split(":", 1)` 直接拆兩個變數)崩潰的輸入。

        2026-09-04 的真實崩潰場景是**在 WSL 自己的 python3 底下執行**,那裡
        `.resolve()` 給的就是沒有冒號的 POSIX 路徑。用 monkeypatch 模擬那個結果,
        不用文字比對原始碼、也不用真的啟動 WSL python——直接驗證行為。
        """
        class _FakePosixResolved:
            def __str__(self):
                return "/mnt/c/Users/kg701/Desktop/GAME/fd2_re/tools/x.sh"

        class _FakePath:
            def resolve(self):
                return _FakePosixResolved()

        got = H.to_wsl_path(_FakePath())          # 舊版在這裡會 ValueError
        self.assertEqual(got, "/mnt/c/Users/kg701/Desktop/GAME/fd2_re/tools/x.sh")


if __name__ == "__main__":
    unittest.main()
