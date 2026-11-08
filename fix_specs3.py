s = open("ESPECIFICACIONES.md", encoding="utf-8").read()
# Find my appended section and renumber it
old = "## 14. Estandares de UI para listados (obligatorio)"
new = "## 22. Estandares de UI para listados (obligatorio)"
assert old in s
s = s.replace(old, new)
# Also add pagination selector details
old2 = "3. **Paginacion**: minimo 5 registros por pagina. Se incluye\n   partials/paginacion.html en todos los listados. La paginacion muestra\n   navegacion anterior/siguiente y numero de pagina."
new2 = "3. **Paginacion**: minimo 5 registros por pagina (default 5). Se incluye\n   partials/paginacion.html en todos los listados. La paginacion muestra\n   navegacion anterior/siguiente, numero de pagina y un selector para\n   cambiar la cantidad (5, 10, 15, 25, 50)."
assert old2 in s
s = s.replace(old2, new2)
open("ESPECIFICACIONES.md", "w", encoding="utf-8").write(s)
print("updated")