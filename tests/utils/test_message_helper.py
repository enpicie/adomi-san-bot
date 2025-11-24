import pytest
import utils.message_helper as msg_helper

def test_get_user_ping():
    user_id = "123"
    expected = "<@123>"
    assert msg_helper.get_user_ping(user_id) == expected

def test_get_channel_mention():
    channel_id = "456"
    expected = "<#456>"
    assert msg_helper.get_channel_mention(channel_id) == expected
