from diting.models import Interests
from diting.signal.profile import seed_profile, fatten_profile

class _FakeClient:
    def complete_json(self, messages, **kw):
        return {"stack": ["MLX", "llama.cpp"], "tools": ["graphify"], "topics": ["细粒度检索"]}

def test_seed_profile_from_texts():
    p = seed_profile(_FakeClient(), ["我常用 MLX 和 graphify"])
    assert "MLX" in p["stack"] and "graphify" in p["tools"]

def test_fatten_is_pure_and_dedup():
    base = {"stack": ["MLX"], "tools": ["graphify"], "topics": ["LoRA"]}
    interests = Interests(topics=("LoRA", "RRF 融合"), entities=("MLX", "Qdrant"),
                          open_loops=(), decisions=())
    out = fatten_profile(base, interests)
    assert out["topics"] == ["LoRA", "RRF 融合"]      # 去重 + 新增
    assert "Qdrant" in out["tools"]                    # 新实体并入 tools
    assert base["topics"] == ["LoRA"]                  # 原对象未被改（不可变）
