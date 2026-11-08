import re
s = open("negocio/views.py").read()
s = s.replace("\n'''\n\n# ---------------------------------------------------------------------------\n# Backup diario", "\n\n# ---------------------------------------------------------------------------\n# Backup diario")
open("negocio/views.py", "w").write(s)
print("done")
"