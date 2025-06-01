import json
from urllib import request, parse


class FeedlyClient:
    """Minimal Feedly client mimicking feedly/python-api-client."""

    BASE_URL = "https://cloud.feedly.com/v3"

    def __init__(self, access_token: str):
        self.access_token = access_token

    def _request(self, path: str, params: dict | None = None) -> dict:
        query = parse.urlencode(params or {})
        url = f"{self.BASE_URL}{path}"
        if query:
            url += "?" + query
        req = request.Request(url)
        req.add_header("Authorization", f"OAuth {self.access_token}")
        with request.urlopen(req, timeout=10) as resp:
            data = resp.read()
        return json.loads(data)

    def get_stream_contents(self, stream_id: str, count: int = 10) -> dict:
        return self._request("/streams/contents", {"streamId": stream_id, "count": count})
