## why

http servers should be easier and simpler.

## what

a port of [ring](https://github.com/ring-clojure/ring/wiki) to [tornado](http://www.tornadoweb.org/en/latest/) for python3.

## install

note: tested only on ubuntu

```
git clone https://github.com/nathants/py-web
cd py-aws
pip3 install -r requirements.txt
pip3 install .
```

## http example

```
#!/usr/bin/env python3.6
import logging
import tornado.gen
import tornado.ioloop
import web

logging.basicConfig(level='INFO')

@tornado.gen.coroutine
def handler(request):
    yield None # must yield at least once
    size = request['query'].get('size', 0)
    token = request['kwargs']['token']
    return {'code': 200, 'body': f'{token} size: {size}'}

@tornado.gen.coroutine
def fallback_handler(request):
    yield None # must yield at least once
    route = request['args'][0]
    return {'code': 200, 'body': f'no such route: /{route}, try: /hello/xyz?size=123'}

routes = [('/hello/:token', {'get': handler}),
          ('/(.*)',         {'get': fallback_handler})]

app = web.app(routes)
app.listen(8080)
tornado.ioloop.IOLoop.current().start()
```

```
$ curl localhost:8080/hello/world?size=3
world size: 3
```

## https example

```
#!/usr/bin/env python3.6
import logging
import tornado.gen
import tornado.ioloop
import web
import ssl
import subprocess

check_call = lambda *a: subprocess.check_call(' '.join(map(str, a)), shell=True, executable='/bin/bash', stderr=subprocess.STDOUT)

logging.basicConfig(level='INFO')

@tornado.gen.coroutine
def handler(request):
    yield None # must yield at least once
    size = request['query'].get('size', 0)
    token = request['kwargs']['token']
    return {'code': 200, 'body': f'{token} size: {size}'}

@tornado.gen.coroutine
def fallback_handler(request):
    yield None # must yield at least once
    route = request['args'][0]
    return {'code': 200, 'body': f'no such route: /{route}, try: /hello/XYZ'}

check_call('openssl req -x509 -nodes -newkey rsa:4096 -keyout ssl.key -out ssl.crt -days 9999 -subj "/CN=localhost/O=Fake Name/C=US"')
options = ssl.create_default_context(ssl.Purpose.CLIENT_AUTH)
options.load_cert_chain('ssl.crt', 'ssl.key')

routes = [('/hello/:token', {'get': handler}),
          ('/(.*)',         {'get': fallback_handler})]

app = web.app(routes)
app.listen(8080, ssl_options=options)
tornado.ioloop.IOLoop.current().start()
```

```
$ curl --cacert ssl.crt https://localhost:8080/hello/world?size=3
world size: 3
```
