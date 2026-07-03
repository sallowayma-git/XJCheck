from dwg_audit.utils.ids import IdFactory


def test_id_factory_increments() -> None:
    factory = IdFactory("X", width=3)
    assert factory.next() == "X001"
    assert factory.next() == "X002"
