from unittest.mock import Mock, patch

import requests

from src.utils import expand_url


def test_expand_url_head_redirect_returns_final_url():
    session = Mock()
    session.max_redirects = None
    session.head.return_value = Mock(url="https://example.com/final")

    with patch("src.utils.requests.Session", return_value=session):
        result = expand_url("https://short.example/abc", timeout=3, max_redirects=7)

    assert result == "https://example.com/final"
    session.head.assert_called_once_with(
        "https://short.example/abc", allow_redirects=True, timeout=3
    )
    assert session.max_redirects == 7
    session.get.assert_not_called()


def test_expand_url_head_failure_then_get_success():
    session = Mock()
    session.max_redirects = None
    session.head.side_effect = requests.RequestException("head failed")
    get_response = Mock(url="https://example.com/from-get")
    session.get.return_value = get_response

    with patch("src.utils.requests.Session", return_value=session):
        result = expand_url("https://short.example/fallback")

    assert result == "https://example.com/from-get"
    session.head.assert_called_once()
    session.get.assert_called_once_with(
        "https://short.example/fallback",
        allow_redirects=True,
        timeout=10,
        stream=True,
    )
    get_response.close.assert_called_once()


def test_expand_url_head_and_get_fail_returns_none():
    session = Mock()
    session.max_redirects = None
    session.head.side_effect = requests.RequestException("head failed")
    session.get.side_effect = requests.RequestException("get failed")

    with patch("src.utils.requests.Session", return_value=session):
        result = expand_url("https://short.example/fail")

    assert result is None


def test_expand_url_non_http_final_url_returns_none():
    session = Mock()
    session.max_redirects = None
    session.head.return_value = Mock(url="ftp://example.com/file")

    with patch("src.utils.requests.Session", return_value=session):
        result = expand_url("https://short.example/ftp")

    assert result is None
