#!/usr/bin/env bash
# 存檔:原 scratchpad 驅動腳本(續一百 ~ 一百三十三),路徑保留當時的工作環境,不保證能直接執行(見 README.md)。
# WSL:~ 底下所有 trace_unique_cseip.txt 的雜湊分布,與其他可能的軌跡輸出
cd ~ || exit 9
echo "== trace_unique_cseip.txt 雜湊分布(不跟隨連結)"
find . -xdev -name trace_unique_cseip.txt -type f 2>/dev/null | while read -r f; do sha256sum "$f"; done | cut -c1-16 | sort | uniq -c | sort -rn
echo "== 每個雜湊最早的檔(mtime)"
find . -xdev -name trace_unique_cseip.txt -type f -printf '%T+ %s %p\n' 2>/dev/null | sort | head -3
echo "== 其他軌跡相關檔名"
find . -xdev -maxdepth 3 \( -iname '*trace*' \) -type f -printf '%s %p\n' 2>/dev/null | grep -v trace_unique_cseip | sort -k2 | head -40
echo "== dosbox_exec_trace.sh 的輸出位置"
grep -n "trace_unique_cseip\|OUT\|out=" /mnt/c/Users/kg701/Desktop/GAME/fd2_re/tools/dosbox_exec_trace.sh | head -20
