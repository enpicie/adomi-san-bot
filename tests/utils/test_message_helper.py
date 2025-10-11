import pytest
from utils.message_helper import get_user_ping

def test_get_user_ping():
    user_id = "123"
    expected = "<@123>"
    assert get_user_ping(user_id) == expected
