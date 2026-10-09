from slugify import slugify


def test_basic():
    assert slugify("Hello World") == "hello-world"


def test_collapses_separators():
    assert slugify("Hello,   World!!") == "hello-world"


def test_accents():
    assert slugify("Café Crème") == "cafe-creme"


def test_empty():
    assert slugify("") == ""
