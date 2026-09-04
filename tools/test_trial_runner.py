"""`fd2_trial_runner` 的正反向驗證。

為什麼要用替身而不是實體實例:一次真實試驗要 10 分鐘,而這裡要驗的是**工具的判讀邏輯**
——「遊戲死了會不會被記成 exited」「活著會不會被記成 survived」「什麼都沒量到會不會
硬報 0/0」。那三件事與 DOSBox 無關,用替身測既快又能刻意製造真實環境裡難重現的情況。

**兩個方向都要測**,這是本檔存在的理由:
只測「死了要記成 exited」的話,一個永遠回傳 exited 的實作也會通過。
2026-09-04 的整段調查就是毀在單向驗證上(交接檔 C.12)。
"""

import io
import json
import sys
import unittest
from contextlib import redirect_stdout
from pathlib import Path

sys.path.insert(0, str(Path(__file__).resolve().parent))

import fd2_dosbox_live_helper as H
import fd2_trial_runner as R


class _Stub:
    """把 runner 對外界的四個接觸點換成可控的替身。"""

    def __init__(self, drive_ok=True, alive_seq=(True, True)):
        self.drive_ok = drive_ok
        self.alive_seq = list(alive_seq)
        self.torn_down = []
        self.conditions_run = []

    def install(self):
        self._orig = (R.launch, R.drive, R.run_condition, H.game_alive)
        R.launch = lambda inst, keepalive=3600: None
        R.drive = lambda inst, log: (log.write_text("READY\n" if self.drive_ok else "",
                                                    encoding="utf-8"), self.drive_ok)[1]
        R.run_condition = lambda inst, args, log: (
            self.conditions_run.append((inst, tuple(args))),
            log.write_text("ran\n", encoding="utf-8"))[0]
        H.game_alive = lambda inst, **kw: (
            (self.alive_seq.pop(0) if self.alive_seq else True),
            {"frames": [{"distinct_colors": 100}], "distinct_colors": 100})
        R.teardown = lambda inst: self.torn_down.append(inst)

    def restore(self):
        R.launch, R.drive, R.run_condition, H.game_alive = self._orig


class TrialOutcomeTest(unittest.TestCase):
    def setUp(self):
        import tempfile
        self.td = tempfile.TemporaryDirectory()
        self.d = Path(self.td.name)

    def tearDown(self):
        self.td.cleanup()

    def _one(self, stub):
        stub.install()
        try:
            import threading
            res = []
            R.one_trial("c", ["--x"], self.d, res, threading.Lock())
            return res[0]
        finally:
            stub.restore()

    # ---- 正向:真的死了要記成 exited ---------------------------------
    def test_exit_is_recorded_as_exited(self):
        rec = self._one(_Stub(alive_seq=(True, False)))   # 起點活、跑完死
        self.assertEqual(rec["outcome"], "exited")

    # ---- 反向:活著要記成 survived。缺這條的話,一個永遠回傳 exited 的
    #      實作也會通過上一條 -------------------------------------------
    def test_survival_is_recorded_as_survived(self):
        rec = self._one(_Stub(alive_seq=(True, True)))
        self.assertEqual(rec["outcome"], "survived")

    def test_drive_failure_is_not_counted_as_survival(self):
        """驅動失敗代表**沒測到條件**,不可混進分母當成存活。"""
        stub = _Stub(drive_ok=False)
        rec = self._one(stub)
        self.assertEqual(rec["outcome"], "drive_failed")
        self.assertEqual(stub.conditions_run, [], "驅動失敗時不該還去跑條件")

    def test_dead_before_condition_is_distinguished(self):
        rec = self._one(_Stub(alive_seq=(False,)))
        self.assertEqual(rec["outcome"], "dead_before_condition")

    def test_instance_is_torn_down_even_on_failure(self):
        stub = _Stub(drive_ok=False)
        self._one(stub)
        self.assertEqual(len(stub.torn_down), 1, "失敗路徑也必須拆掉實例,否則會累積殘留")


class SummaryTest(unittest.TestCase):
    def setUp(self):
        import tempfile
        self.td = tempfile.TemporaryDirectory()
        self.d = Path(self.td.name)

    def tearDown(self):
        self.td.cleanup()

    def _run_main(self, stub, trials=2):
        stub.install()
        argv = sys.argv
        sys.argv = ["x", "--trials", str(trials), "--workers", "1",
                    "--out", str(self.d), "--cond", "a:--x"]
        try:
            buf = io.StringIO()
            with redirect_stdout(buf):
                rc = R.main()
            return rc, buf.getvalue()
        finally:
            sys.argv = argv
            stub.restore()

    def test_refuses_to_report_when_nothing_was_measured(self):
        """全部驅動失敗時**不可**印出 0/0 當結果。

        第一版就是這樣:6 次 drive_failed 之後照樣印「0/0」與判讀提醒,
        看起來像跑完了一輪。檢查跑不起來 ≠ 檢查通過。
        """
        rc, out = self._run_main(_Stub(drive_ok=False))
        self.assertEqual(rc, 2, "什麼都沒量到時離開碼應為 2")
        self.assertIn("一次有效試驗都沒有", out)
        data = json.loads((self.d / "results.json").read_text(encoding="utf-8"))
        self.assertFalse(data["valid"])

    def test_reports_normally_when_trials_are_valid(self):
        """對照組:有有效試驗時要正常報告,否則上一條可能只是它永遠拒絕。"""
        rc, out = self._run_main(_Stub(alive_seq=(True, False, True, False)))
        self.assertEqual(rc, 0)
        self.assertIn("退回 DOS 2/2", out)
        self.assertNotIn("一次有效試驗都沒有", out)


if __name__ == "__main__":
    unittest.main()
