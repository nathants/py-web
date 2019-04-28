import json
import pytest
import tornado.ioloop
import util.net
import pool.proc
import web

def test_non_2XX_codes():
    async def handler(req):
        1 / 0
    app = web.app([('/', {'get': handler})])
    with web.test(app) as url:
        rep = web.get_sync(url)
        assert '1 / 0' not in rep['body']
        assert rep['code'] == 500

def test_normal_app():
    async def handler(req):
        return {'body': 'asdf'}
    port = util.net.free_port()
    web.app([('/', {'get': handler})]).listen(port)
    proc = pool.proc.new(tornado.ioloop.IOLoop.current().start)
    url = f'http://0.0.0.0:{port}'
    assert web.get_sync(url)['body'] == 'asdf'
    proc.terminate()

def test_get_timeout():
    async def handler(req):
        if 'sleep' in req['query']:
            await tornado.gen.sleep(1)
        handler._sleep = True
        return {}
    async def main(url):
        await web.get(url + '?sleep', timeout=.001)
    app = web.app([('/', {'get': handler})])
    with web.test(app) as url:
        with pytest.raises(web.Timeout):
            tornado.ioloop.IOLoop.instance().run_sync(lambda: main(url))

def test_get():
    async def handler(req):
        return {'body': 'ok',
                'code': 200,
                'headers': {'foo': 'bar'}}
    async def main(url):
        rep = await web.get(url)
        assert rep['body'] == 'ok'
        assert rep['code'] == 200
        assert rep['headers']['foo'] == 'bar'
    app = web.app([('/', {'get': handler})])
    with web.test(app) as url:
        tornado.ioloop.IOLoop.instance().run_sync(lambda: main(url))

def test_get_params():
    async def handler(req):
        return {'body': json.dumps(req['query'])}
    async def main(url):
        rep = await web.get(url, query={'foo': 'bar'})
        assert json.loads(rep['body']) == {'foo': 'bar'}
    app = web.app([('/', {'get': handler})])
    with web.test(app) as url:
        tornado.ioloop.IOLoop.instance().run_sync(lambda: main(url))

def test_post():
    async def handler(req):
        body = json.loads(req['body'])
        return {'code': body['num'] + 1}
    async def main(url):
        rep = await web.post(url, json.dumps({'num': 200}))
        assert rep['code'] == 201
    app = web.app([('/', {'post': handler})])
    with web.test(app) as url:
        tornado.ioloop.IOLoop.instance().run_sync(lambda: main(url))

def test_post_timeout():
    async def handler(req):
        await tornado.gen.sleep(1)
        return {'code': 200}
    async def main(url):
        rep = await web.post(url, '', timeout=.001)
        assert rep['code'] == 201
    app = web.app([('/', {'post': handler})])
    with web.test(app) as url:
        with pytest.raises(web.Timeout):
            tornado.ioloop.IOLoop.instance().run_sync(lambda: main(url))

def test_basic():
    async def handler(req):
        assert req['verb'] == 'get'
        return {'headers': {'foo': 'bar'},
                'code': 200,
                'body': 'ok'}
    app = web.app([('/', {'get': handler})])
    with web.test(app) as url:
        rep = web.get_sync(url)
        assert rep['body'] == 'ok'
        assert rep['headers']['foo'] == 'bar'

def test_middleware():
    def middleware(old_handler):
        async def new_handler(req):
            req = util.dicts.merge(req, {'headers': {'asdf': ' [mod req]'}})
            rep = await old_handler(req)
            rep = util.dicts.merge(rep, {'body': rep['body'] + ' [mod rep]'})
            return rep
        return new_handler
    @middleware
    async def handler(req):
        return {'headers': {'foo': 'bar'},
                'code': 200,
                'body': 'ok' + req['headers']['asdf']}
    app = web.app([('/', {'get': handler})])
    with web.test(app) as url:
        rep = web.get_sync(url)
        assert rep['body'] == 'ok [mod req] [mod rep]'

def test_url_params():
    async def handler(req):
        return {'code': 200,
                'body': json.dumps(req['query'])}
    app = web.app([('/', {'get': handler})])
    with web.test(app) as url:
        rep = web.get_sync(url + '/?asdf=123&foo=bar&foo=notbar&stuff')
        assert json.loads(rep['body']) == {'asdf': '123',
                                           'foo': ['bar', 'notbar'],
                                           'stuff': ''}

def test_url_kwargs():
    async def handler(req):
        return {'code': 200,
                'body': json.dumps(req['kwargs']['foo'])}
    app = web.app([('/:foo/stuff', {'get': handler})])
    with web.test(app) as url:
        rep = web.get_sync(url + '/something/stuff')
        assert json.loads(rep['body']) == 'something', rep

def test_url_args():
    async def handler(req):
        return {'code': 200,
                'body': json.dumps(req['args'])}
    app = web.app([('/(.*)/(.*)', {'get': handler})])
    with web.test(app) as url:
        rep = web.get_sync(url + '/something/stuff')
        assert json.loads(rep['body']) == ['something', 'stuff'], rep

def test_validate():
    async def handler(req):
        return {'code': 200,
                'body': json.dumps(req['query'])}
    app = web.app([('/', {'get': handler})])
    with web.test(app) as url:
        rep = web.get_sync(url + '/?asdf=123&foo=bar&foo=notbar&stuff')
        assert json.loads(rep['body']) == {'asdf': '123',
                                           'foo': ['bar', 'notbar'],
                                           'stuff': ''}
