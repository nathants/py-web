from typing import List, Tuple, Union, Dict, Type, Callable
try:
    from typing import TypedDict
except ImportError:
    from typing_extensions import TypedDict
import contextlib
import itertools
import logging
import pool.proc
import pool.thread
import time
import tornado.httpclient
import tornado.web
import urllib
import util.exceptions
import util.func
import util.log
import util.net
from tornado.ioloop import IOLoop
from tornado.web import RequestHandler, Application
from tornado.httputil import HTTPServerRequest, HTTPFile
from tornado.simple_httpclient import HTTPTimeoutError

class Request(TypedDict):
    verb: str
    url: str
    path: str
    query: Dict[str, List[str]]
    body: Union[str, bytes]
    headers: Dict[str, Union[str, int]]
    args: List[str]
    files: Dict[str, List[HTTPFile]]
    kwargs: Dict[str, str]
    remote: str

class Response(TypedDict, total=False):
    code: int
    reason: str
    headers: Dict[str, str]
    body: Union[str, bytes]

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

def _verbs_dict_to_tornado_handler_class(verbs_or_handler: Union[Dict[str, Callable], Type[RequestHandler]]) -> Type[RequestHandler]:
    if isinstance(verbs_or_handler, type(RequestHandler)):
        return verbs_or_handler
    else:
        class Handler(RequestHandler):
            for verb, fn in verbs_or_handler.items(): # type: ignore
                locals()[verb.lower()] = _handler_function_to_tornado_handler_method(fn)
            del verb, fn
        return Handler

def _update_handler_from_dict_resp(resp: Response, handler: RequestHandler) -> None:
    body = resp.get('body')
    if body:
        handler.write(body)
    handler.set_status(resp.get('code') or 200, resp.get('reason') or '')
    for header, value in (resp.get('headers') or {}).items():
        handler.set_header(header, value)

def _parse_query_string(query: str) -> Dict[str, List[str]]:
    return {k: list(v) for k, v in urllib.parse.parse_qs(query, True).items()}

def _tornado_req_to_dict(obj: HTTPServerRequest, a: List[str], kw: Dict[str, str]) -> Request:
    return {
        'verb': (obj.method or '').lower(),
        'url': obj.uri or '',
        'path': obj.path,
        'query': _parse_query_string(obj.query),
        'body': _try_decode(obj.body),
        'headers': {k.lower(): v for k, v in dict(obj.headers).items()},
        'args': a,
        'kwargs': kw,
        'files': obj.files,
        'remote': obj.remote_ip,
    }

def _parse_route_str(route: str) -> str:
    return '/'.join([f'(?P<{x[1:]}>.*)' if x.startswith(':') else x for x in route.split('/')])

def app(routes: List[Tuple[str, Union[Type[RequestHandler], Dict[str, Callable]]]], debug: bool = False, **settings) -> Application:
    routes = [(_parse_route_str(route),
               _verbs_dict_to_tornado_handler_class(verbs))
              for route, verbs in routes]
    return Application(routes, debug=debug, **settings) # type: ignore

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
def test(app, poll='/', context=None, use_thread=False):
    from unittest import mock
    context = context or (lambda: mock.patch.object(mock, '_fake_', create=True))
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
tornado.httpclient.AsyncHTTPClient.configure(None, max_clients=256)

class Blowup(Exception):
    def __init__(self, message, code, reason, body):
        super().__init__(message)
        self.code = code
        self.reason = reason
        self.body = _try_decode(body)

    def __str__(self):
        return f'{self.args[0] if self.args else ""}, code={self.code}, reason="{self.reason}"\n{self.body}'

async def _fetch(verb: str, url: str, **kw: dict) -> Response:
    url, timeout, blowup, kw = _process_fetch_kwargs(url, kw)
    kw['user_agent'] = kw.get('user_agent') or "Mozilla/5.0 (compatible; pycurl)" # type: ignore
    future = tornado.httpclient.AsyncHTTPClient().fetch(url, method=verb, raise_error=False, connect_timeout=timeout, request_timeout=timeout, **kw)
    resp = await future
    if blowup and resp.code != 200:
        raise Blowup(f'{verb} {url} did not return 200, returned {resp.code}',
                     resp.code,
                     resp.reason,
                     resp.body)
    return {'code': resp.code,
            'reason': resp.reason or '',
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

def post(url, body='', **kw):
    return _fetch('POST', url, body=body, **kw)

Timeout = HTTPTimeoutError
