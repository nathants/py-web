from __future__ import absolute_import, print_function
import contextlib
import datetime
import functools
import logging
import mock
import time
import traceback
import types

import six
import tornado.httpclient
import tornado.httputil
import tornado.web


import s.data
import s.exceptions
import s.func
import s.net
import pool.proc
import pool.thread
import schema

from tornado.web import RequestHandler
from tornado.httputil import HTTPServerRequest

# todo stop auto json parsing. magic considered harmful.

class schemas:
    req = {'verb': str,
           'url': str,
           'path': str,
           'query': {str: str},
           'body': str,
           'headers': {str: (':U', int)},
           'args': {str: str}}

    rep = {'code': (':O', int, 200),
           'reason': (':O', (':M', str), None),
           'headers': (':O', {str: str}, {}),
           'body': (':O', str, '')}


def _try_decode(text):
    try:
        return text.decode('utf-8')
    except:
        return text


def _handler_function_to_tornado_handler_method(fn):
    name = s.func.name(fn)
    @tornado.gen.coroutine
    def method(self, **args):
        req = _tornado_req_to_dict(self.request, args)
        try:
            rep = yield fn(req)
        except:
            logging.exception('uncaught exception in: %s', name)
            rep = {'code': 500}
        _update_handler_from_dict_rep(rep, self)
    method.fn = fn
    return method


def _verbs_dict_to_tornado_handler_class(**verbs: {str: callable}) -> type:
    class Handler(tornado.web.RequestHandler):
        for verb, fn in verbs.items():
            locals()[verb.lower()] = _handler_function_to_tornado_handler_method(fn)
        del verb, fn
    return Handler


def _update_handler_from_dict_rep(rep: schemas.rep, handler: RequestHandler) -> None:
    body = rep.get('body', '')
    handler.write(body)
    handler.set_status(rep.get('code', 200), rep.get('reason', ''))
    for header, value in rep.get('headers', {}).items():
        handler.set_header(header, value)


def _parse_query_string(query: str) -> schemas.req['query']:
    parsed = six.moves.urllib.parse.parse_qs(query, True)
    val = {k: v if len(v) > 1 else v.pop()
           for k, v in parsed.items()}
    return val


def _tornado_req_to_dict(obj: HTTPServerRequest, args: {str: str}) -> schemas.req:
    body = _try_decode(obj.body)
    return {'verb': obj.method.lower(),
            'url': obj.uri,
            'path': obj.path,
            'query': _parse_query_string(obj.query),
            'body': body,
            'headers': dict(obj.headers),
            'args': args}


def _parse_route_str(route: str) -> str:
    return '/'.join(['(?P<{}>.*)'.format(x[1:])
                     if x.startswith(':')
                     else x
                     for x in route.split('/')])


def app(routes: [(str, {str: callable})], debug: bool = False, **settings: dict) -> tornado.web.Application:
    """
    """
    routes = [(_parse_route_str(route),
               _verbs_dict_to_tornado_handler_class(**verbs))
              for route, verbs in routes]
    return tornado.web.Application(routes, debug=debug, **settings)


def wait_for_http(url, max_wait_seconds=5):
    start = time.time()
    while True:
        assert time.time() - start < max_wait_seconds, 'timed out'
        try:
            assert get_sync(url)['code'] != 599
            break
        except AssertionError:
            time.sleep(.001)


@contextlib.contextmanager
def test(app, poll='/', context=lambda: mock.patch.object(mock, '_fake_', create=True), use_thread=False):
    port = s.net.free_port()
    url = 'http://0.0.0.0:{}'.format(port)
    def run():
        with context():
            if isinstance(app, tornado.web.Application):
                app.listen(port)
            else:
                app().listen(port)
            if not use_thread:
                tornado.ioloop.IOLoop.current().start()
    proc = (pool.thread.new if use_thread else pool.proc.new)(run)
    if poll:
        wait_for_http(url + poll)
    try:
        yield url
    except:
        raise
    finally:
        if not use_thread:
            proc.terminate()


with s.exceptions.ignore(ImportError):
    tornado.httpclient.AsyncHTTPClient.configure("tornado.curl_httpclient.CurlAsyncHTTPClient")


class Blowup(Exception):
    def __init__(self, message, code, reason, body):
        super().__init__(message)
        self.code = code
        self.reason = reason
        self.body = _try_decode(body)

    def __str__(self):
        return '{}, code={}, reason="{}"\n{}'.format(self.args[0] if self.args else '', self.code, self.reason, self.body)


# TODO this should probably be an argument to something
faux_app = None


@tornado.gen.coroutine
def _fetch(verb, url, **kw):
    fetcher = _faux_fetch if faux_app else _real_fetch
    return (yield fetcher(verb, url, **kw))


@tornado.gen.coroutine
def _real_fetch(verb, url, **kw):
    url, timeout, blowup, kw = _process_fetch_kwargs(url, kw)
    req = tornado.httpclient.HTTPRequest(url, method=verb, **kw)
    future = tornado.concurrent.Future()
    rep = tornado.httpclient.AsyncHTTPClient().fetch(req, callback=lambda x: future.set_result(x))
    if timeout:
        tornado.ioloop.IOLoop.current().add_timeout(
            datetime.timedelta(seconds=timeout),
            lambda: not future.done() and future.set_exception(Timeout())
        )
    rep = yield future
    if blowup and rep.code != 200:
        raise Blowup('{verb} {url} did not return 200, returned {code}'.format(code=rep.code, **locals()),
                     rep.code,
                     rep.reason,
                     rep.body)
    return {'code': rep.code,
            'reason': rep.reason,
            'headers': {k.lower(): v for k, v in rep.headers.items()},
            'body': _try_decode(rep.body or b'')}


@tornado.gen.coroutine
def _faux_fetch(verb, url, **kw):
    assert isinstance(faux_app, tornado.web.Application)
    query = kw.get('query', {})
    url, _, blowup, kw = _process_fetch_kwargs(url, kw)
    dispatcher = tornado.web._RequestDispatcher(faux_app, None)
    dispatcher.set_request(tornado.httputil.HTTPServerRequest(method=verb, uri=url, **kw))
    args = dispatcher.path_kwargs
    try:
        handler = getattr(dispatcher.handler_class, verb.lower()).fn
    except AttributeError:
        raise Exception('no route matched: {verb} {url}'.format(**locals()))
    req = {'verb': verb,
               'url': url,
               'path': '/' + url.split('://')[-1].split('/', 1)[-2],
               'query': query,
               'body': _try_decode(kw.get('body', b'')),
               'headers': kw.get('headers', {}),
               'args': {k: _try_decode(v) for k, v in args.items()}}
    rep = (yield handler(req))
    if blowup and rep.get('code', 200) != 200:
        raise Blowup('{verb} {url} did not return 200, returned {code}'.format(code=rep['code'], **locals()),
                     rep['code'],
                     rep.get('reason', ''),
                     rep.get('body', ''))
    return rep


def _process_fetch_kwargs(url, kw):
    timeout = kw.pop('timeout', 10)
    blowup = kw.pop('blowup', False)
    if 'query' in kw:
        assert '?' not in url, 'you cannot user keyword arg query and have ? already in the url: {url}'.format(**locals())
        url += '?' + '&'.join('{}={}'.format(k, tornado.escape.url_escape(v))
                              for k, v in kw.pop('query').items())
    return url, timeout, blowup, kw


def get(url: str, **kw):
    return _fetch('GET', url, **kw)


# TODO support schema.check for pos/keyword args with default like body
def post(url, body='', **kw):
    return _fetch('POST', url, body=body, **kw)


def get_sync(url, **kw):
    @tornado.gen.coroutine
    def fn():
        return (yield get(url, **kw))
    return tornado.ioloop.IOLoop.instance().run_sync(fn)


def post_sync(url, data='', **kw):
    @tornado.gen.coroutine
    def fn():
        return (yield post(url, data, **kw))
    return tornado.ioloop.IOLoop.instance().run_sync(fn)


class Timeout(Exception):
    pass


@s.func.optionally_parameterized_decorator
def validate(*args, **kwargs):
    def decorator(decoratee):
        name = s.func.name(decoratee)
        request_schema = schema._get_schemas(decoratee, args, kwargs)['arg'][0]
        decoratee = schema.check(*args, **kwargs)(decoratee)
        @functools.wraps(decoratee)
        @tornado.gen.coroutine
        def decorated(req):
            try:
                schema._validate(request_schema, req)
            except schema.Error:
                return {'code': 403, 'reason': 'your req is not valid', 'body': traceback.format_exc() + '\nvalidation failed for: {}'.format(name)}
            else:
                return (yield decoratee(req))
        return decorated
    return decorator
