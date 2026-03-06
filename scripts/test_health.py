import urllib.request, json
r = urllib.request.urlopen('http://localhost:8000/health')
print('HTTP STATUS:', r.status)
body = json.loads(r.read().decode())
print(json.dumps(body, indent=2, ensure_ascii=False))
