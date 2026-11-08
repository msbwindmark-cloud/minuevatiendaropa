import urllib.request, urllib.parse, http.cookiejar, re

cj = http.cookiejar.CookieJar()
opener = urllib.request.build_opener(urllib.request.HTTPCookieProcessor(cj))
resp = opener.open("http://127.0.0.1:8000/login/")
html = resp.read().decode()
m = re.search(r'name="csrfmiddlewaretoken" value="([^"]+)"', html)
token = m.group(1)
data = urllib.parse.urlencode({"username": "daw2", "password": "bosselli2024", "csrfmiddlewaretoken": token, "next": "/"}).encode()
req = urllib.request.Request("http://127.0.0.1:8000/login/", data=data, headers={"Referer": "http://127.0.0.1:8000/login/"})
opener.open(req)

r = opener.open("http://127.0.0.1:8000/clientes/")
h = r.read().decode()
rows = re.findall(r'<tr>', h)
print("Number of <tr> in clientes:", len(rows))
# Check if por_pagina selector is present
print("has selector:", "Mostrar:" in h)