data = open("core/models.py", "rb").read()
data = data.replace(b"\xe1", b"\xc3\xa1")  # á
data = data.replace(b"\xed", b"\xc3\xad")  # í
data = data.replace(b"\xf3", b"\xc3\xb3")  # ó
open("core/models.py", "wb").write(data)
print("done")