from twitter_clone import routes


def test_get_greeting():
    assert routes.hello_world() == "Hello"
