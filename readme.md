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

## example

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
    size = request['query']['size']
    token = request['kwargs']['token']
    return {'code': 200,
            'body': f'{token} size: {size}'}

routes = [
    ('/hello/:token', {'get': handler}),
]

app = web.app(routes)
app.listen(8080)
tornado.ioloop.IOLoop.current().start()
```

```
$ curl localhost:8080/hello/world?size=3
world size: 3
```
