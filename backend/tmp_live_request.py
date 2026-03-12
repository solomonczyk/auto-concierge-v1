import urllib.request
try:
    r = urllib.request.urlopen("http://127.0.0.1:8000/live", timeout=5)
    print("status:", r.status)
    print("body:", r.read().decode())
except Exception as e:
    print(type(e).__name__ + ":", e)
