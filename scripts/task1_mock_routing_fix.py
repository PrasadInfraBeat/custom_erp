import pathlib
p = pathlib.Path("tools/infrabeat_erp/tests/test_backup.py")
t = p.read_text(encoding="utf-8")
old_block = """        if "bench" in command and "backup" in command:
            return self.exit_code, self.bench_output, ""
        if "ls -t" in command:
            return 0, self.ls_output, ""
"""
new_block = """        if "ls -t" in command:
            return 0, self.ls_output, ""
        if "bench --site" in command:
            return self.exit_code, self.bench_output, ""
"""
if "bench --site" in t:
    print("already patched")
elif old_block in t:
    p.write_text(t.replace(old_block, new_block, 1), encoding="utf-8", newline="\n")
    print("Patched: ls check first, bench --site precise (no more false-positive routing)")
else:
    print("anchor not found - paste me the current exec() method body for manual fix")