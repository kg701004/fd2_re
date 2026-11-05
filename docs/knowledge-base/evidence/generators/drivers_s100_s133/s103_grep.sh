#!/bin/bash
# 存檔:原 scratchpad 驅動腳本(續一百 ~ 一百三十三),路徑保留當時的工作環境,不保證能直接執行(見 README.md)。
# 續一百零三:在 LOGCPU.TXT 找 28 個法術 handler 入口第一次出現的行號(背景跑,完成時寫 grep.done)。
cd ~/fd2-run-harness-s103 || exit 1
LC_ALL=C grep -n -F -x -f chk/pat.txt LOGCPU.TXT | awk -F: '!seen[$2":"$3]++' > chk/first_hits.txt
echo "rc=${PIPESTATUS[0]}" > chk/grep.done
