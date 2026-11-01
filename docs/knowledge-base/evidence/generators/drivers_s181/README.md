# 驅動腳本(續一百八十一)

開機 → 標題 → START → 120 秒的實機三次(instance `lc181a`、`lc181b`、`lc181c`,使用者 2026-11-01「全部依照你的建議自動進行處理」;
計畫三次、失敗即停,三次都正常結束)(DOSBox-X)。用觸發式擷取收 ng 375 / ng 302-303 的 Y 區塊,驗「375 = MDI 型重入夾一次 IRQ 7」。
只對原版 FD2.EXE(md5 33464c81e6a364fd0660141139aa8e6e)、WSL `-d Ubuntu`;不改記憶體、不下斷點。
dosbox-x 同 lc174b(`~/fd2-dosbox-calllog4`,sha256 882925130480c1eaf2e5e366c867bd880ad50a6f801202e1fcb6cea073a4f592);入口檔 `~/fd2-calllog-s163/entries_3b.txt`。

| 檔 | 用途 | 產生的原始紀錄 |
|---|---|---|
| `lc181.py` | `run NAME` / `down NAME`(由 `drivers_s174/lc174.py` 改:不設 SEGS / IO,START 後等 120 秒) | `.wsl_build/lc181_live/<NAME>_CALLLOG.TXT`、`cl/<NAME>_run.json` |
| `pred181.txt` | 實機前寫的預測 P1 .. P4(跑完不改) | — |

設定:`FD2_CALLLOG_TRIG=ng:375,ng:302-303`、`_TRIGCAP=40`、`_CAP=100000000`、`_DUMP=0`、`_ICOUNT=1`、`_SLICES=1`、`_PICEV=1`、`_KBD=1`、
DOS 時間 12:00:54。

指紋(teardown 之後):lc181a md5 0dcee91e57df141a188fb805b407d469、lc181b c676d94a047c56b78e275d1e6732f17d、
lc181c b429596b086c214778fd95e39c6fe6b5(三份的最後一行都寫到一半,`calllog_segments._read` 丟掉)。

結果與判準在 `../ev_s181b.py`(`../mut_s181b.py`):三次 ng 375 都 0 次(P1 NOT TESTED),302 / 303 寫出的各 40 個全是 MDI 型、區塊內沒有 YI(P2 PASS)。
