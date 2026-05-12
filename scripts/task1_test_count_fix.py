import pathlib
p = pathlib.Path("tools/infrabeat_erp/tests/test_backup.py")
t = p.read_text(encoding="utf-8")
if "exec_calls) == 1" not in t:
    print("anchor not found (already patched?)")
else:
    n = t.replace("assert len(adapter.exec_calls) == 1", "assert len(adapter.exec_calls) == 2  # bench + ls")
    p.write_text(n, encoding="utf-8", newline="\n")
    print("Patched: exec_calls count 1 -> 2 (bench + ls)")