import re, pathlib
p = pathlib.Path("tools/infrabeat_erp/pyproject.toml")
t = p.read_text(encoding="utf-8")
if '"paramiko' in t or "'paramiko" in t:
    print("paramiko already in pyproject.toml (skip)")
    raise SystemExit(0)
m = re.search(r"^dependencies\s*=\s*\[([\s\S]*?)\]", t, re.MULTILINE)
if not m:
    print("FAIL: could not locate dependencies block")
    raise SystemExit(1)
list_body = m.group(1)
indent_m = re.search(r"\n(\s+)['\"]", list_body)
indent = indent_m.group(1) if indent_m else "    "
trimmed = list_body.rstrip()
if not trimmed.endswith(","):
    trimmed += ","
new_list = trimmed + f"\n{indent}\"paramiko>=3.0\",\n"
new_text = t[:m.start(1)] + new_list + t[m.end(1):]
p.write_text(new_text, encoding="utf-8", newline="\n")
print("OK: added paramiko>=3.0 to dependencies")