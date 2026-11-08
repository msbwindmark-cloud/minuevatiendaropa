data = open("core/models.py", "rb").read()
old = b"backup_automatico = models.BooleanField(default=False, help_text='Enviar backup autom"
# Find the full line
idx = data.find(old)
end = data.find(b"\r\n", idx)
line = data[idx:end]
print(repr(line))
new_line = b"backup_automatico = models.BooleanField(default=False, help_text='Enviar backup automaticamente al cerrar el dia')"
data = data[:idx] + new_line + data[end:]
open("core/models.py", "wb").write(data)
print("fixed")