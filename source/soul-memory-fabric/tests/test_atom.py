"""MemoryAtom 字段测试。"""

from soul_fabric.atom import MemoryAtom, MemoryState


def test_session_type_default():
    atom = MemoryAtom(user_id="alice")
    assert atom.session_type == "unknown"


def test_session_type_custom():
    atom = MemoryAtom(user_id="alice", session_type="websocket")
    assert atom.session_type == "websocket"


def test_session_type_in_dump():
    atom = MemoryAtom(user_id="alice", session_type="telegram")
    data = atom.model_dump()
    assert data["session_type"] == "telegram"


def test_atom_defaults():
    atom = MemoryAtom(user_id="bob")
    assert atom.user_id == "bob"
    assert atom.tenant_id == "default"
    assert atom.state == MemoryState.RAW
    assert atom.memory_id.startswith("mem_")
