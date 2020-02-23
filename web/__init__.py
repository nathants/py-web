import collections
import contextlib
import datetime
import functools
import itertools
import logging
import pool.proc
import pool.thread
import schema
import time
import tornado.httpclient
import tornado.web
import traceback
import urllib
import util.data
import util.exceptions
import util.func
import util.log
import util.net
from unittest import mock
from tornado.ioloop import IOLoop
from tornado.web import RequestHandler, Application
from tornado.httputil import HTTPServerRequest

class schemas:
    # :or is union, :optional is optional
    req = {'verb': str,
           'url': str,
           'path': str,
           'query': {str: (':or', str, [str])},
           'body': (':or', str, bytes),
           'headers': {str: (':or', str, int)},
           'args': [str],
           'files': {str: [{'body': bytes, 'content_type': str, 'filename': str}]},
           'kwargs': {str: str},
           'remote': str}

    resp = {'code': (':optional', int, 200),
            'reason': (':optional', (':or', str, None), None),
            'headers': (':optional', {str: str}, {}),
            'body': (':optional', (':or', str, bytes), '')}

def _try_decode(text):
    try:
        return text.decode('utf-8')
    except:
        return text

def _handler_function_to_tornado_handler_method(fn):
    name = util.func.name(fn)
    async def method(self, *a, **kw):
        req = _tornado_req_to_dict(self.request, a, kw)
        try:
            resp = await fn(req)
        except:
            logging.exception('uncaught exception in: %s', name)
            resp = {'code': 500}
        _update_handler_from_dict_resp(resp, self)
    method.fn = fn
    return method

@schema.check
def _verbs_dict_to_tornado_handler_class(verbs_or_handler: (':or', {str: callable}, type(RequestHandler))) -> type:
    if type(verbs_or_handler) is type(RequestHandler):
        return verbs_or_handler
    else:
        class Handler(RequestHandler):
            for verb, fn in verbs_or_handler.items():
                locals()[verb.lower()] = _handler_function_to_tornado_handler_method(fn)
            del verb, fn
        return Handler

@schema.check
def _update_handler_from_dict_resp(resp: schemas.resp, handler: RequestHandler) -> None:
    body = resp.get('body', None)
    if body:
        handler.write(body)
    handler.set_status(resp.get('code', 200), resp.get('reason', ''))
    for header, value in resp.get('headers', {}).items():
        handler.set_header(header, value)

@schema.check
def _parse_query_string(query: str) -> schemas.req['query']:
    parsed = urllib.parse.parse_qs(query, True)
    val = {k: v if len(v) > 1 else v.pop()
           for k, v in parsed.items()}
    return val

def _tree():
    return collections.defaultdict(_tree)

@schema.check
def _tornado_req_to_dict(obj: HTTPServerRequest, a: [str], kw: {str: str}) -> schemas.req:
    body = _try_decode(obj.body)
    return collections.defaultdict(_tree, {
        'verb': obj.method.lower(),
        'url': obj.uri,
        'path': obj.path,
        'query': _parse_query_string(obj.query),
        'body': body,
        'headers': {k.lower(): v for k, v in dict(obj.headers).items()},
        'args': a,
        'kwargs': kw,
        'files': obj.files,
        'remote': obj.remote_ip,
    })

@schema.check
def _parse_route_str(route: str) -> str:
    return '/'.join([f'(?P<{x[1:]}>.*)'
                     if x.startswith(':')
                     else x
                     for x in route.split('/')])

@schema.check
def app(routes: [(str, (':or', type(RequestHandler), {str: callable}))], debug: bool = False, **settings) -> Application:
    routes = [(_parse_route_str(route),
               _verbs_dict_to_tornado_handler_class(verbs))
              for route, verbs in routes]
    return Application(routes, debug=debug, **settings)

def wait_for_http(url, max_wait_seconds=5):
    import requests
    import requests.exceptions
    start = time.time()
    for i in itertools.count(1):
        assert time.time() - start < max_wait_seconds, 'timed out'
        try:
            assert requests.get(url).status_code != 599
            break
        except requests.exceptions.ConnectionError:
            time.sleep(.01 * 1)

@contextlib.contextmanager
def test(app, poll='/', context=lambda: mock.patch.object(mock, '_fake_', create=True), use_thread=False):
    port = util.net.free_port()
    url = f'http://0.0.0.0:{port}'
    def run():
        with context():
            util.log.setup()
            if isinstance(app, Application):
                app.listen(port)
            else:
                app().listen(port)
            if not use_thread:
                IOLoop.current().start()
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

with util.exceptions.ignore(ImportError):
    tornado.httpclient.AsyncHTTPClient.configure("tornado.curl_httpclient.CurlAsyncHTTPClient")

class Blowup(Exception):
    def __init__(self, message, code, reason, body):
        super().__init__(message)
        self.code = code
        self.reason = reason
        self.body = _try_decode(body)

    def __str__(self):
        return f'{self.args[0] if self.args else ""}, code={self.code}, reason="{self.reason}"\n{self.body}'

@schema.check
async def _fetch(verb: str, url: str, **kw: dict) -> schemas.resp:
    url, timeout, blowup, kw = _process_fetch_kwargs(url, kw)
    kw['user_agent'] = kw.get('user_agent', "Mozilla/5.0 (compatible; pycurl)")
    future = tornado.httpclient.AsyncHTTPClient().fetch(url, method=verb, raise_error=False, **kw)
    if timeout:
        IOLoop.current().add_timeout(
            datetime.timedelta(seconds=timeout),
            lambda: not future.done() and future.set_exception(Timeout())
        )
    resp = await future
    if blowup and resp.code != 200:
        raise Blowup(f'{verb} {url} did not return 200, returned {resp.code}',
                     resp.code,
                     resp.reason,
                     resp.body)
    return {'code': resp.code,
            'reason': resp.reason,
            'headers': {k.lower(): v for k, v in resp.headers.items()},
            'body': _try_decode(resp.body or b'')}

def _process_fetch_kwargs(url, kw):
    timeout = kw.pop('timeout', 10)
    blowup = kw.pop('blowup', False)
    if 'query' in kw:
        assert '?' not in url, f'you cannot user keyword arg query and have ? already in the url: {url}'
        url += '?' + '&'.join(f'{k}={tornado.escape.url_escape(v)}'
                              for k, v in kw.pop('query').items())
    return url, timeout, blowup, kw

def get(url, **kw):
    return _fetch('GET', url, **kw)

# TODO support schema.check for pos/keyword args with default like body
def post(url, body='', **kw):
    return _fetch('POST', url, body=body, **kw)

class Timeout(Exception):
    pass

@util.func.optionally_parameterized_decorator
def validate(*args, **kwargs):
    def decorator(decoratee):
        name = util.func.name(decoratee)
        request_schema = schema._get_schemas(decoratee, args, kwargs)['arg'][0]
        decoratee = schema.check(*args, **kwargs)(decoratee)
        @functools.wraps(decoratee)
        async def decorated(req):
            try:
                schema._validate(request_schema, req)
            except schema.Error:
                return {'code': 403, 'reason': 'your req is not valid', 'body': traceback.format_exc() + f'\nvalidation failed for: {name}'}
            else:
                return (await decoratee(req))
        return decorated
    return decorator
