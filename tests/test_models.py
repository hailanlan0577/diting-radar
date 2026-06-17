from diting.models import Interests, RankedItem, Report

def test_interests_is_frozen():
    i = Interests(topics=("LoRA",), entities=("MLX",), open_loops=(), decisions=())
    import dataclasses, pytest
    with pytest.raises(dataclasses.FrozenInstanceError):
        i.topics = ()

def test_empty_report_is_honest():
    r = Report(lens="research", date="2026-06-18", items=(), notes=("今天这块没值得看的",))
    assert r.is_empty() is True
    assert "没值得看" in r.notes[0]
