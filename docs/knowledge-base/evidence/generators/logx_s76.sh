#!/usr/bin/env bash
# 存檔:原 scratchpad 驅動腳本,路徑保留當時的工作環境,不保證能直接執行(見 README.md)。
# 續七十六:v33 的 DOSBox-X 記錄檔摘錄 —— 去掉 INT 6 迴圈每次一行的訊息,保留其餘最後 25 行與總數。
f="$HOME/fd2-run-harness-$1/dosbox-x.log"
echo "# total_lines $(wc -l < "$f")  int6_lines $(grep -c 'Unhandled Interrupt Called 6' "$f")"
grep -n -v 'Unhandled Interrupt Called 6' "$f" | tail -25
