import yaomem


def test_imports_with_version():
    assert isinstance(yaomem.__version__, str)
