from __future__ import print_function, absolute_import
import pytest
import tornado.gen
import tornado.ioloop

import s.net
import pool.proc
import web


def test_non_2XX_codes():
    @tornado.gen.coroutine
    def handler(request):
        yield tornado.gen.moment
        1 / 0

    app = web.app([('/', {'get': handler})])
    with web.test(app) as url:
        rep = web.get_sync(url)
        assert '1 / 0' not in rep['body']
        assert rep['code'] == 500


def test_normal_app():
    @tornado.gen.coroutine
    def handler(request):
        yield tornado.gen.moment
        raise tornado.gen.Return({'body': 'asdf'})
    port = s.net.free_port()
    web.app([('/', {'get': handler})]).listen(port)
    proc = pool.proc.new(tornado.ioloop.IOLoop.current().start)
    url = 'http://0.0.0.0:{port}'.format(**locals())
    assert web.get_sync(url)['body'] == 'asdf'
    proc.terminate()


def test_get_timeout():
    @tornado.gen.coroutine
    def handler(request):
        if 'sleep' in request['query']:
            yield tornado.gen.sleep(1)
        handler._sleep = True
        raise tornado.gen.Return({})

    @tornado.gen.coroutine
    def main(url):
        yield web.get(url + '?sleep', timeout=.001)

    app = web.app([('/', {'get': handler})])
    with web.test(app) as url:
        with pytest.raises(web.Timeout):
            tornado.ioloop.IOLoop.instance().run_sync(lambda: main(url))


def test_get():
    @tornado.gen.coroutine
    def handler(request):
        yield tornado.gen.moment
        raise tornado.gen.Return({'body': 'ok',
                                  'code': 200,
                                  'headers': {'foo': 'bar'}})

    @tornado.gen.coroutine
    def main(url):
        resp = yield web.get(url)
        assert resp['body'] == 'ok'
        assert resp['code'] == 200
        assert resp['headers']['foo'] == 'bar'

    app = web.app([('/', {'get': handler})])
    with web.test(app) as url:
        tornado.ioloop.IOLoop.instance().run_sync(lambda: main(url))


def test_get_params_json():
    @tornado.gen.coroutine
    def handler(request):
        yield tornado.gen.moment
        raise tornado.gen.Return({'body': request['query']})

    @tornado.gen.coroutine
    def main(url):
        resp = yield web.get(url, query={'data': [1, 2, 3]})
        assert resp['body'] == {'data': [1, 2, 3]}

    app = web.app([('/', {'get': handler})])
    with web.test(app) as url:
        tornado.ioloop.IOLoop.instance().run_sync(lambda: main(url))


def test_get_params():
    @tornado.gen.coroutine
    def handler(request):
        yield tornado.gen.moment
        raise tornado.gen.Return({'body': request['query']})

    @tornado.gen.coroutine
    def main(url):
        resp = yield web.get(url, query={'foo': 'bar'})
        assert resp['body'] == {'foo': 'bar'}

    app = web.app([('/', {'get': handler})])
    with web.test(app) as url:
        tornado.ioloop.IOLoop.instance().run_sync(lambda: main(url))


def test_post():
    @tornado.gen.coroutine
    def handler(request):
        yield tornado.gen.moment
        raise tornado.gen.Return({'code': request['body']['num'] + 1})

    @tornado.gen.coroutine
    def main(url):
        resp = yield web.post(url, {'num': 200})
        assert resp['code'] == 201

    app = web.app([('/', {'post': handler})])
    with web.test(app) as url:
        tornado.ioloop.IOLoop.instance().run_sync(lambda: main(url))


def test_post_timeout():
    @tornado.gen.coroutine
    def handler(request):
        yield tornado.gen.sleep(1)
        raise tornado.gen.Return({'code': 200})

    @tornado.gen.coroutine
    def main(url):
        resp = yield web.post(url, '', timeout=.001)
        assert resp['code'] == 201

    app = web.app([('/', {'post': handler})])
    with web.test(app) as url:
        with pytest.raises(web.Timeout):
            tornado.ioloop.IOLoop.instance().run_sync(lambda: main(url))


def test_basic():
    @tornado.gen.coroutine
    def handler(request):
        yield tornado.gen.moment
        assert request['verb'] == 'get'
        raise tornado.gen.Return({'headers': {'foo': 'bar'},
                                  'code': 200,
                                  'body': 'ok'})
    app = web.app([('/', {'get': handler})])
    with web.test(app) as url:
        resp = web.get_sync(url)
        assert resp['body'] == 'ok'
        assert resp['headers']['foo'] == 'bar'


def test_middleware():
    def middleware(old_handler):
        @tornado.gen.coroutine
        def new_handler(request):
            request = s.dicts.merge(request, {'headers': {'asdf': ' [mod req]'}})
            response = yield old_handler(request)
            response = s.dicts.merge(response, {'body': response['body'] + ' [mod resp]'})
            raise tornado.gen.Return(response)
        return new_handler
    @middleware
    @tornado.gen.coroutine
    def handler(request):
        yield tornado.gen.moment
        raise tornado.gen.Return({'headers': {'foo': 'bar'},
                                  'code': 200,
                                  'body': 'ok' + request['headers']['asdf']})
    app = web.app([('/', {'get': handler})])
    with web.test(app) as url:
        resp = web.get_sync(url)
        assert resp['body'] == 'ok [mod req] [mod resp]'


def test_url_params():
    @tornado.gen.coroutine
    def handler(request):
        yield tornado.gen.moment
        raise tornado.gen.Return({'code': 200,
                                  'body': request['query']})
    app = web.app([('/', {'get': handler})])
    with web.test(app) as url:
        resp = web.get_sync(url + '/?asdf=123&foo=bar&foo=notbar&stuff')
        assert resp['body'] == {'asdf': 123,
                                'foo': ['bar', 'notbar'],
                                'stuff': ''}


def test_url_args():
    @tornado.gen.coroutine
    def handler(request):
        yield tornado.gen.moment
        raise tornado.gen.Return({'code': 200,
                                  'body': {'foo': request['args']['foo']}})
    app = web.app([('/:foo/stuff', {'get': handler})])
    with web.test(app) as url:
        resp = web.get_sync(url + '/something/stuff')
        assert resp['body'] == {'foo': 'something'}, resp
