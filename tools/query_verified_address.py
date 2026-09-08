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


def selftest():
    """`normalize_addr` 是查詢的比對鍵——它一錯,查詢就會**靜默查不到**而不是報錯。

    這種函式的危險不是崩潰,是回傳一個看起來合理但配不上的字串。所以除了正向案例,
    這裡要求:(a) 所有寫法都收斂到同一個鍵;(b) 壞輸入回 None 而不是猜;
    (c) 與真實資料庫實際對得上(否則正規化得再漂亮也沒用)。
    """
    import sys as _sys
    if hasattr(_sys.stdout, "reconfigure"):
        _sys.stdout.reconfigure(encoding="utf-8")
        _sys.stderr.reconfigure(encoding="utf-8")
    fails = []

    print("(1) 同一個位址的各種寫法必須收斂到同一個鍵")
    variants = ["0x14818", "14818", "0X14818", "  0x14818  ", "0x014818", "0X0014818"]
    got = {normalize_addr(v) for v in variants}
    ok1 = got == {"0x14818"}
    print(f"    {'PASS' if ok1 else 'FAIL'}: {len(variants)} 種寫法 -> {got}")
    if not ok1:
        fails.append(f"寫法沒有收斂:{got}")

    print("\n(2) 壞輸入必須回 None,不能猜一個看起來合理的鍵出來")
    bad_in = ["", "  ", "zzz", "0x", "0xGG", "12g4", "0x12 34"]
    leaked = [b for b in bad_in if normalize_addr(b) is not None]
    ok2 = not leaked
    print(f"    {'PASS' if ok2 else 'FAIL'}: {len(bad_in)} 個壞輸入"
          + ("全部回 None" if ok2 else f",漏放 {[(b, normalize_addr(b)) for b in leaked]}"))
    if not ok2:
        fails.append(f"壞輸入沒有回 None:{leaked}")

    print("\n(3) 大小寫與前導零不得產生不同的鍵(這是最容易靜默查不到的來源)")
    pairs = [("0xABCDEF", "0xabcdef"), ("0x00FF", "0xff"), ("FF", "0xff")]
    diff = [(a, b) for a, b in pairs if normalize_addr(a) != normalize_addr(b)]
    ok3 = not diff
    print(f"    {'PASS' if ok3 else 'FAIL'}: 3 組"
          + ("全部一致" if ok3 else f",不一致 {diff}"))
    if not ok3:
        fails.append(f"大小寫/前導零產生不同鍵:{diff}")

    print("\n(4) 與真實資料庫對得上:正規化後必須真的命中已提交的 verified_addresses")
    import os as _os
    root = _os.path.dirname(_os.path.dirname(_os.path.abspath(__file__)))
    hit = total = 0
    for fn in ("verified_addresses.json", "known_address_errata.json"):
        p = _os.path.join(root, "docs", "data", fn)
        if not _os.path.isfile(p):
            continue
        try:
            data = json.load(open(p, encoding="utf-8"))
        except (OSError, ValueError):
            continue
        blob = json.dumps(data, ensure_ascii=False)
        import re as _re
        for a in set(_re.findall(r"0x[0-9a-fA-F]{4,6}", blob)):
            total += 1
            if normalize_addr(a) == normalize_addr(a.upper()) == normalize_addr(a[2:]):
                hit += 1
    ok4 = total > 0 and hit == total
    print(f"    {'PASS' if ok4 else 'FAIL'}: 資料庫中 {total} 個位址,"
          f"三種寫法都收斂的 {hit}")
    if total == 0:
        fails.append("找不到任何真實位址 —— 這題是空的,不算通過")
    elif hit != total:
        fails.append(f"{total - hit} 個真實位址的寫法不收斂")

    print("\n(5) 非恆真控制:不同的位址必須產生不同的鍵")
    ok5 = normalize_addr("0x1000") != normalize_addr("0x1001")
    print(f"    {'PASS' if ok5 else 'FAIL'}: 0x1000 vs 0x1001 -> "
          f"{normalize_addr('0x1000')} / {normalize_addr('0x1001')}")
    if not ok5:
        fails.append("不同位址被正規化成同一個鍵")

    if fails:
        print("\nSELFTEST FAILED:")
        for f in fails:
            print("  -", f)
        return 1
    print("\n--selftest passed(寫法收斂 + 壞輸入回 None + 大小寫/前導零 + "
          "真實資料庫命中 + 非恆真控制)。")
    return 0


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
    if len(argv) == 2 and argv[1] == '--selftest':
        return selftest()
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
