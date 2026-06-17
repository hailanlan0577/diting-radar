from diting.models import SignalItem, Interests
from diting.signal.distill import distill_interests


class _FakeClient:
    def __init__(self, payload):
        self.payload = payload
        self.seen = None

    def complete_json(self, messages, **kw):
        self.seen = messages
        return self.payload


def test_distill_maps_to_interests():
    client = _FakeClient({"topics": ["LoRA 微调"], "entities": ["MLX", "ytst"],
                          "open_loops": ["阈值还没定"], "decisions": ["阈值改 0.3"]})
    out = distill_interests(client, [SignalItem("obsidian_session", "今天搞 LoRA", 1.0)])
    assert isinstance(out, Interests)
    assert out.topics == ("LoRA 微调",)
    assert "MLX" in out.entities
    # 确认把原文喂进了 prompt
    assert "今天搞 LoRA" in client.seen[-1]["content"]


def test_distill_tolerates_missing_keys():
    client = _FakeClient({"topics": ["x"]})
    out = distill_interests(client, [SignalItem("s", "t", 1.0)])
    assert out.entities == () and out.open_loops == ()
