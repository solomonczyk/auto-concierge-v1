import urllib.request, urllib.parse, urllib.error, json

BASE = 'http://localhost:8000/api/v1'
candidates = ['admin123', 'admin', 'Admin123', 'password', 'qwerty', 'admin1234']

for pwd in candidates:
    data = urllib.parse.urlencode({'username': 'admin', 'password': pwd}).encode()
    req = urllib.request.Request(BASE + '/login/access-token', data=data)
    try:
        resp = urllib.request.urlopen(req)
        body = json.loads(resp.read().decode())
        print('FOUND! password=' + pwd + ' token=' + body['access_token'][:30] + '...')
        break
    except urllib.error.HTTPError as e:
        print('wrong: ' + pwd + ' → ' + str(e.code))
