import pathlib
p = pathlib.Path("tools/infrabeat_erp/tests/test_doctor.py")
t = p.read_text(encoding="utf-8")
if "test_run_all_returns_5_checks" not in t:
    print("anchor not found (already patched?)")
    raise SystemExit(0)
n = t.replace("test_run_all_returns_5_checks", "test_run_all_returns_8_checks").replace("assert len(results) == 5", "assert len(results) == 8")
p.write_text(n, encoding="utf-8", newline="\n")
print("Patched: 5_checks -> 8_checks, assertion 5 -> 8")