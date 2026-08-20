#!/usr/bin/env python3
"""查詢 docs/data/verified_addresses.json / known_address_errata.json。

用法:
    python tools/query_verified_address.py 0x14818
        精確位址查詢:同時檢查 verified_addresses.json(命中則列出完整條目)
        與 known_address_errata.json(該位址若是已知的錯誤舊位址,或是某筆
        勘誤的正確新位址,都會被提示)。

    python tools/query_verified_address.py --search "AoE"
        對 verified_addresses.json 的 semantic/notes/source_section 欄位做
        不分大小寫關鍵字模糊搜尋,列出所有命中條目的摘要。

不依賴第三方套件。給未來 agent/開發者快速確認「這個位址是不是已經有人查過」用,
避免重工;引用任何位址前,建議先查一次。
"""
import json
import os
import sys

if hasattr(sys.stdout, "reconfigure"):
    sys.stdout.reconfigure(encoding="utf-8")
    sys.stderr.reconfigure(encoding="utf-8")

HERE = os.path.dirname(os.path.abspath(__file__))
DATA_DIR = os.path.join(HERE, "..", "docs", "data")
VERIFIED_PATH = os.path.join(DATA_DIR, "verified_addresses.json")
ERRATA_PATH = os.path.join(DATA_DIR, "known_address_errata.json")


def load_json(path):
    with open(path, encoding="utf-8") as f:
        return json.load(f)


def normalize_addr(s):
    """把 '0x14818' / '14818' / '0X14818' 都正規化成小寫 '0x14818' 形式做比對。"""
    s = s.strip()
    if s.lower().startswith("0x"):
        s = s[2:]
    try:
        return "0x" + format(int(s, 16), "x")
    except ValueError:
        return None


def print_entry(e, indent="  "):
    print(f"{indent}地址: {e['address']}  [{e.get('linear_or_file_offset', '?')}]  confidence={e.get('confidence', '?')}")
    print(f"{indent}語意: {e.get('semantic', '')}")
    src = e.get("source_doc", "?")
    sec = e.get("source_section")
    date = e.get("verified_date", "?")
    if sec:
        print(f"{indent}來源: {src} {sec} (verified_date={date})")
    else:
        print(f"{indent}來源: {src} (verified_date={date})")
    notes = e.get("notes")
    if notes:
        print(f"{indent}備註: {notes}")


def print_erratum(err, indent="  "):
    print(f"{indent}[錯誤] {err['wrong_address']}  ->  [正確] {err['correct_address']}")
    print(f"{indent}原誤植語意: {err.get('wrong_semantic_claimed', '')}")
    print(f"{indent}發現日期: {err.get('discovered_date', '?')}  發現方式: {err.get('discovery_method', '')}")
    if err.get("root_cause"):
        print(f"{indent}根因: {err['root_cause']}")
    if err.get("still_pending"):
        print(f"{indent}後續: {err['still_pending']}")
    corr = err.get("correction_doc")
    if corr:
        sec = err.get("correction_section", "")
        print(f"{indent}訂正出處: {corr} {sec}")


def exact_lookup(addr_arg):
    norm = normalize_addr(addr_arg)
    if norm is None:
        print(f"無法解析位址: {addr_arg!r}(請用如 0x14818 或 14818 的十六進位格式)")
        return 1

    found_any = False

    verified = load_json(VERIFIED_PATH)
    hits = [e for e in verified["entries"] if normalize_addr(e["address"]) == norm]
    if hits:
        found_any = True
        print(f"== verified_addresses.json 命中 {len(hits)} 筆 (查詢: {norm}) ==")
        for e in hits:
            print_entry(e)
            print()

    errata = load_json(ERRATA_PATH)
    as_wrong = [er for er in errata["errata"] if normalize_addr_field(er["wrong_address"]) == norm]
    as_correct = [er for er in errata["errata"] if normalize_addr_field(er["correct_address"]) == norm]

    if as_wrong:
        found_any = True
        print(f"!! 警告:{norm} 是已知的錯誤位址(known_address_errata.json) !!")
        for er in as_wrong:
            print_erratum(er)
            print()

    if as_correct:
        found_any = True
        print(f"== {norm} 是下列勘誤條目的「已訂正正確位址」==")
        for er in as_correct:
            print_erratum(er)
            print()

    if not found_any:
        print(f"{norm}：資料庫裡沒有記錄(不代表位址無效,只代表尚未被本資料庫收錄；"
              f"可用 --search 試試相關關鍵字，或直接去 knowledge-base 全文搜尋)。")
        return 1
    return 0


def normalize_addr_field(s):
    """errata 檔案裡的 wrong_address/correct_address 有時帶額外說明文字
    (例如 '0x55445 (硬編碼於 dump_native_movement_cost_rows...)')，
    只取開頭的十六進位位址部分再正規化。"""
    token = s.strip().split()[0] if s.strip() else s
    return normalize_addr(token)


def search(keyword):
    verified = load_json(VERIFIED_PATH)
    kw = keyword.lower()
    hits = []
    for e in verified["entries"]:
        haystack = " ".join(str(e.get(k, "")) for k in ("semantic", "notes", "source_section", "source_doc"))
        if kw in haystack.lower():
            hits.append(e)

    errata = load_json(ERRATA_PATH)
    erratum_hits = []
    for er in errata["errata"]:
        haystack = " ".join(str(er.get(k, "")) for k in
                             ("wrong_semantic_claimed", "root_cause", "still_pending", "discovery_method"))
        if kw in haystack.lower():
            erratum_hits.append(er)

    if not hits and not erratum_hits:
        print(f"關鍵字 {keyword!r} 沒有命中任何條目。")
        return 1

    if hits:
        print(f"== verified_addresses.json 命中 {len(hits)} 筆 (關鍵字: {keyword!r}) ==")
        for e in hits:
            print(f"  {e['address']:10} [{e.get('confidence','?')}]  {e.get('semantic','')[:80]}")
        print()

    if erratum_hits:
        print(f"== known_address_errata.json 命中 {len(erratum_hits)} 筆 (關鍵字: {keyword!r}) ==")
        for er in erratum_hits:
            print(f"  {er['wrong_address']} -> {er['correct_address']}  {er.get('wrong_semantic_claimed','')[:80]}")
    return 0


def main(argv):
    if len(argv) < 2:
        print(__doc__)
        return 1

    if argv[1] == "--search":
        if len(argv) < 3:
            print("用法: python tools/query_verified_address.py --search <關鍵字>")
            return 1
        return search(" ".join(argv[2:]))

    return exact_lookup(argv[1])


if __name__ == "__main__":
    sys.exit(main(sys.argv))
