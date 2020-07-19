## why

almost always, http servers should be simple and easy.

## what

an http library wrapping [tornado](http://www.tornadoweb.org/en/latest/).

## install

```bash
git clone https://github.com/nathants/py-web
cd py-web
pip install -r requirements.txt .
```

## http example

```python
#!/usr/bin/env python3
import logging
import tornado.ioloop
import web

logging.basicConfig(level='INFO')

async def handler(request: web.Request) -> web.Response:
    size = int(request['query'].get('size', 0))
    token = request['kwargs']['token']
    return {'code': 200, 'body': f'{token} size: {size}'}

async def fallback_handler(request: web.Request) -> web.Response:
    route = request['args'][0]
    return {'code': 200, 'body': f'no such route: /{route}, try: /hello/xyz?size=123'}

routes = [('/hello/:token', {'get': handler}),
          ('/(.*)',         {'get': fallback_handler})]

app = web.app(routes)
server = tornado.httpserver.HTTPServer(app)
server.bind(8080)
server.start(0)
tornado.ioloop.IOLoop.current().start()
```

```bash
$ curl localhost:8080/hello/world?size=3
world size: 3
```

## https example

```python
#!/usr/bin/env python3
import logging
import tornado.ioloop
import web
import ssl
import subprocess

check_call = lambda *a: subprocess.check_call(' '.join(map(str, a)), shell=True, executable='/bin/bash', stderr=subprocess.STDOUT)

logging.basicConfig(level='INFO')

async def handler(request: web.Request) -> web.Response:
    size = int(request['query'].get('size', 0))
    token = request['kwargs']['token']
    return {'code': 200, 'body': f'{token} size: {size}'}

async def fallback_handler(request: web.Request) -> web.Response:
    route = request['args'][0]
    return {'code': 200, 'body': f'no such route: /{route}, try: /hello/XYZ'}

check_call('openssl req -x509 -nodes -newkey rsa:4096 -keyout ssl.key -out ssl.crt -days 9999 -subj "/CN=localhost/O=Fake Name/C=US"')
options = ssl.create_default_context(ssl.Purpose.CLIENT_AUTH)
options.load_cert_chain('ssl.crt', 'ssl.key')

routes = [('/hello/:token', {'get': handler}),
          ('/(.*)',         {'get': fallback_handler})]

app = web.app(routes)
server = tornado.httpserver.HTTPServer(app, ssl_options=options)
server.bind(8080)
server.start(0)
tornado.ioloop.IOLoop.current().start()
```

```bash
$ curl --cacert ssl.crt https://localhost:8080/hello/world?size=3
world size: 3
```
