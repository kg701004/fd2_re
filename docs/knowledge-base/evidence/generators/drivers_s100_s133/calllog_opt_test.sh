#!/usr/bin/env bash
# 存檔:原 scratchpad 驅動腳本(續一百 ~ 一百三十三),路徑保留當時的工作環境,不保證能直接執行(見 README.md)。
# 把 dosbox_harness.sh 的 FD2_HARNESS_CALLLOG 區塊單獨抽出來逐值測(die 換成 exit 1 的樁)。
H=/mnt/c/Users/kg701/Desktop/GAME/fd2_re/tools/dosbox_harness.sh
block=$(awk '/^    local calllog_env=""/{f=1} f{print} f&&/^    fi$/&&++n==3{exit}' "$H")
[[ -n "$block" ]] || { echo "BLOCK NOT FOUND"; exit 2; }
ent=$(mktemp); printf '001ac010\n' > "$ent"
empty=$(mktemp)
fake_unpatched=$(mktemp); printf 'nothing here' > "$fake_unpatched"
fake_patched=$(mktemp); printf 'xx FD2_CALLLOG_ENTRIES yy' > "$fake_patched"
run() {  # $1 = 期望 rc, 其餘 = env 指派
    local want=$1; shift
    out=$(env "$@" bash -c "die() { echo \"DIE: \$*\"; exit 1; }; name=t; workdir=/tmp/wd; f() {
$block
echo \"ENV=[\$calllog_env]\"
}; f" 2>&1); rc=$?
    if [[ $rc == "$want" ]]; then echo "PASS rc=$rc $* :: $out"; else echo "FAIL want=$want rc=$rc $* :: $out"; fi
}
run 0 DOSBOX_BIN="$fake_patched"
run 0 DOSBOX_BIN="$fake_patched" FD2_HARNESS_CALLLOG="$ent"
run 0 DOSBOX_BIN="$fake_patched" FD2_HARNESS_CALLLOG="$ent" FD2_HARNESS_CALLLOG_CAP=50 FD2_HARNESS_CALLLOG_DUMP=64
run 1 DOSBOX_BIN="$fake_unpatched" FD2_HARNESS_CALLLOG="$ent"
run 1 DOSBOX_BIN="$fake_patched" FD2_HARNESS_CALLLOG="$empty"
run 1 DOSBOX_BIN="$fake_patched" FD2_HARNESS_CALLLOG=/no/such/file
run 1 DOSBOX_BIN="$fake_patched" FD2_HARNESS_CALLLOG=relative.txt
run 1 DOSBOX_BIN="$fake_patched" FD2_HARNESS_CALLLOG="$ent" FD2_HARNESS_CALLLOG_CAP='5;id'
run 1 DOSBOX_BIN="$fake_patched" FD2_HARNESS_CALLLOG="$ent" FD2_HARNESS_CALLLOG_DUMP=abc
rm -f "$ent" "$empty" "$fake_unpatched" "$fake_patched"
