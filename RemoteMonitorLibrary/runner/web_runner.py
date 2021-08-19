
from enum import Enum, IntEnum
from typing import Optional

import requests
import requests.packages.urllib3
import json
import logging

from RemoteMonitorLibrary.utils import logger


class HTTPMethod(Enum):
    GET = 'get'
    POST = 'post'
    OPTION = 'option'

    def session_callback(self, session: requests.session):
        if self.name in (self.GET.name, self.GET.value):
            return session.get
        if self.name in (self.POST.name, self.POST.value):
            return session.post
        if self.name in (self.OPTION.name, self.OPTION.value):
            return session.options
        raise requests.exceptions.InvalidURL(f"Unknown issue occurred")


class ProtocolPorts(IntEnum):
    http = 80
    https = 443


def _get_parent_class(type_, deep=1, **kwargs):
    return type_.__class__.__mro__[deep](**kwargs)


def _filter_results(data: dict, **kwargs):
    matches = {}
    try:
        for _name, value in kwargs.items():
            assert _name in data.keys(), {_name: f'Not listed - <font color="red">FAIL</font>'}
            assert value == data[_name], {_name: f'Expected: {value} vs. Real: {data[_name]} - <font color="red">FAIL</font>'}
            matches.update(**{_name: f'{value} - <font color="green">PASS</font>'})
    except AssertionError as e:
        if len(matches) > 0:
            matches.update(**e.args[0])
            raise AssertionError("Some of arguments not matched:\n\t{}".format(
                '\n\t'.join(f"{k}: {v}" for k, v in matches.items()))
            )
        return False
    else:
        return True


class ResponseTextSerializer:
    def __init__(self, resp_code=200):
        super().__init__()
        self.resp_code = resp_code
        self._result = ''

    @property
    def result(self):
        return self._result

    def serialize(self, response):
        assert response.status_code == self.resp_code, \
            f"Server error [Expected: {self.resp_code}]: {response.status_code} {response.text}"
        self._result = response.text

    def __call__(self, response):
        self.serialize(response)


class JSONSerializer(ResponseTextSerializer):
    def __init__(self, resp_code=200):
        super().__init__(resp_code)

    @property
    def result(self):
        return self._result

    def serialize(self, response):
        super().serialize(response)
        self._result = json.loads(self.result)


class JSONAccumulativeSerializer(JSONSerializer, list):
    def __init__(self, resp_code=200, **filter_items):
        JSONSerializer.__init__(self, resp_code)
        list.__init__(self)
        self.filters = filter_items

    @property
    def eof_reached(self):
        return len(self.result) == 0

    def serialize(self, response):
        self._result = response
        if not self.eof_reached:
            self.extend([item for item in response if _filter_results(item, **self.filters)])
        return True


class WebBaseSession:
    def __init__(self, **kwargs):
        self.url = kwargs.get('url', None)
        self.user = kwargs.get('user')
        self.password = kwargs.get('password')
        self.protocol = kwargs.get('protocol', ProtocolPorts.HTTP)
        self.port = kwargs.get('port', None) or self.protocol.value
        self.keep_alive = kwargs.get('keep_alive')
        self.level = kwargs.get('level')

        requests_log = logging.getLogger("requests")
        requests_log.setLevel('DEBUG' if self.level == 'TRACE' else self.level)
        requests_log.propagate = True
        if self.level == 'INFO':
            requests.packages.urllib3.disable_warnings()

        self._session = None
        self._auth_token = ''

    @property
    def session(self):
        if self._session is None:
            self._session = requests.Session()
        return self._session

    def login(self, path):
        try:
            auth = (self.user, self.password)
            resp = HTTPMethod.POST.session_callback(self.session)(self.base_url + path, auth=auth, verify=False)
            assert resp.status_code == 200, f"Server respond with error: {resp.status_code}\n{resp.text}"
            assert 'Authorization' in resp.headers, f"Response doesn't contain header 'Authorization'"
            self._auth_token = resp.headers['Authorization']
        except Exception as e:
            logger.error(f"Connect To Server Error: {e}")
            raise
        else:
            logger.debug(f"Login successful (Bearer token: {self._auth_token})")

    @property
    def base_url(self):
        return f"{self.protocol}://{self.url}:{self.port}"

    @property
    def headers(self):
        headers_ = {'Authorization': self._auth_token}
        if self.keep_alive:
            headers_.update(Connection='keep-alive')
        return headers_

    def get_paged_request(self, method, path: str, pager, **kwargs) -> JSONAccumulativeSerializer:
        page = 0
        serializer: JSONAccumulativeSerializer = kwargs.pop('serializer', None)
        assert serializer is not None, "Serializer must be provided"
        assert isinstance(serializer, JSONAccumulativeSerializer), "Serializer must be {} (Provided: {})".format(
            JSONAccumulativeSerializer.__name__,
            type(serializer).__name__)
        parent_serializer = _get_parent_class(serializer)
        # TODO: Implement multithreading solution; When lot of data arrive works too slow
        while True:
            resp = self(method, path.format(**{pager: page}), serializer=parent_serializer, **kwargs)
            serializer(resp)
            page += 1
            if serializer.eof_reached:
                logger.debug(f"End of data in the response.")
                break

        return serializer

    def single_request(self, method: HTTPMethod, path: str, **kwargs) -> ResponseTextSerializer:
        serializer: ResponseTextSerializer = kwargs.get('serializer', ResponseTextSerializer())
        logger.debug(f'Request: {method.__name__.upper()} {self.base_url}{path}; Headers: {self.headers}')
        result = method.session_callback(self._session)(
            self.base_url + path, headers=self.headers, verify=kwargs.pop('verify', False))
        serializer(result)
        return serializer

    def __call__(self, method: HTTPMethod, path: str, **kwargs):
        pager = kwargs.pop('pager', None)
        if pager:
            logger.debug(f"Paging request: {self.base_url + path}; Headers: {self.headers}")
            return self.get_paged_request(method, path, pager, **kwargs)
        return self.single_request(method, path, headers=self.headers, **kwargs).result

    def close(self):
        self._auth_token = None
        self._session = None
