from diting.dig import generate_dig_queries


class _Client:
    def __init__(self, payload):
        self._p = payload
        self.seen = None
    def complete_json(self, messages, **kw):
        self.seen = messages
        return self._p


def test_generate_dig_queries_returns_and_caps():
    c = _Client({"queries": ["q1", "q2", "q3", "q4", "q5", "q6", "q7"]})
    out = generate_dig_queries(c, "RAG 新做法", max_queries=6)
    assert out == ["q1", "q2", "q3", "q4", "q5", "q6"]
    # 话题被传给了模型
    assert "RAG 新做法" in c.seen[1]["content"]

def test_generate_dig_queries_empty_payload():
    assert generate_dig_queries(_Client({}), "X") == []
