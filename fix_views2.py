data = open("negocio/views.py", "rb").read()
needle = b"\n'''\n\n# ---------------------------------------------------------------------------\n# Backup diario"
replacement = b"\n\n# ---------------------------------------------------------------------------\n# Backup diario"
assert needle in data, "needle not found"
data = data.replace(needle, replacement, 1)
open("negocio/views.py", "wb").write(data)
print("done")