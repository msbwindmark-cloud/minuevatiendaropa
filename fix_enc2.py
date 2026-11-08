data = open("negocio/views.py", "rb").read()
data = data.replace(b"\xf3", b"\xc3\xb3")  # ó
data = data.replace(b"\xf1", b"\xc3\xb1")  # ñ
open("negocio/views.py", "wb").write(data)
print("done")