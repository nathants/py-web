from __future__ import print_function, absolute_import
import s
import requests
import json


s.log.setup(debug=True)


def test_basic123():
    @s.async.coroutine
    def handler(request):
        yield s.async.moment
        raise s.async.Return({'body': 'ok',
                              'code': 200,
                              'headers': {'foo': 'bar'}})

    @s.async.coroutine
    def main(url):
        resp = yield s.web.get(url)
        assert resp['body'] == 'ok'
        assert resp['code'] == 200
        assert resp['headers']['foo'] == 'bar'

    app = s.web.server([('/', {'GET': handler})])
    with s.web.test(app) as url:
        s.async.run_sync(lambda: main(url))


def test_basic():
    @s.async.coroutine
    def handler(request):
        yield s.async.moment
        assert request['verb'] == 'get'
        raise s.async.Return({'headers': {'foo': 'bar'},
                              'code': 200,
                              'body': 'ok'})
    app = s.web.server([('/', {'GET': handler})])
    with s.web.test(app) as url:
        resp = requests.get(url)
        assert resp.text == 'ok'
        assert resp.headers['foo'] == 'bar'


def test_middleware():
    def middleware(old_handler):
        @s.async.coroutine
        def new_handler(request):
            request = s.dicts.merge(request, {'headers': {'asdf': ' [mod req]'}})
            response = yield old_handler(request)
            response = s.dicts.merge(response, {'body': response['body'] + ' [mod resp]'})
            raise s.async.Return(response)
        return new_handler
    @middleware
    @s.async.coroutine
    def handler(request):
        yield s.async.moment
        raise s.async.Return({'headers': {'foo': 'bar'},
                              'code': 200,
                              'body': 'ok' + request['headers']['asdf']})
    app = s.web.server([('/', {'GET': handler})])
    with s.web.test(app) as url:
        resp = requests.get(url)
        assert resp.text == 'ok [mod req] [mod resp]'


def test_url_params():
    @s.async.coroutine
    def handler(request):
        yield s.async.moment
        raise s.async.Return({'code': 200,
                              'body': json.dumps(request['query'])})
    app = s.web.server([('/', {'GET': handler})])
    with s.web.test(app) as url:
        resp = requests.get(url + '?asdf=123&foo=bar&foo=notbar&stuff')
        assert resp.json() == {'asdf': '123',
                               'foo': ['bar', 'notbar'],
                               'stuff': ''}


def test_url_args():
    @s.async.coroutine
    def handler(request):
        yield s.async.moment
        raise s.async.Return({'code': 200,
                              'body': json.dumps({'foo': request['arguments']['foo']})})
    app = s.web.server([('/:foo/stuff', {'GET': handler})])
    with s.web.test(app) as url:
        resp = requests.get(url + 'something/stuff')
        assert resp.json() == {'foo': 'something'}
