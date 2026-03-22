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


def test_expand_url_extracts_wrapped_query_url():
    session = Mock()
    session.max_redirects = None
    session.head.return_value = Mock(
        url="https://news.example/redirect?url=https%3A%2F%2Ftarget.example%2Farticle"
    )

    with patch("src.utils.requests.Session", return_value=session):
        result = expand_url("https://short.example/wrapped")

    assert result == "https://target.example/article"
    session.get.assert_not_called()


def test_expand_url_closes_get_response_on_wrapped_early_return():
    session = Mock()
    session.max_redirects = None
    session.head.side_effect = requests.RequestException("head failed")
    get_resp = Mock(
        url="https://wrapper.example/redirect?url=https%3A%2F%2Ftarget.example%2Ffinal"
    )
    session.get.return_value = get_resp

    with patch("src.utils.requests.Session", return_value=session):
        result = expand_url("https://short.example/wrapped-get")

    assert result == "https://target.example/final"
    get_resp.close.assert_called_once()


def test_expand_url_meta_fallback_from_wrapper_page():
    session = Mock()
    session.max_redirects = None
    session.head.return_value = Mock(url="https://news.example/redirect?id=1")
    html_resp = Mock(
        url="https://news.example/redirect?id=1",
        text="""
            <html><head>
              <meta property="og:url" content="https://target.example/from-og" />
            </head></html>
        """,
    )
    session.get.return_value = html_resp

    with patch("src.utils.requests.Session", return_value=session):
        result = expand_url("https://short.example/meta")

    assert result == "https://target.example/from-og"
    session.get.assert_called_once()
    html_resp.close.assert_called_once()


def test_expand_url_search_app_shortlink_resolves_to_canonical_target():
    session = Mock()
    session.max_redirects = None
    session.head.return_value = Mock(url="https://klausai.com/")

    with patch("src.utils.requests.Session", return_value=session):
        result = expand_url("https://search.app/2Xn5o")

    assert result == "https://klausai.com/"
    session.get.assert_not_called()


def test_expand_url_rejects_private_network_target():
    session = Mock()
    session.max_redirects = None
    session.head.return_value = Mock(url="http://127.0.0.1/admin")

    with patch("src.utils.requests.Session", return_value=session):
        result = expand_url("https://short.example/private")

    assert result is None


def test_expand_url_handles_non_request_exception_in_html_fallback():
    session = Mock()
    session.max_redirects = None
    session.head.return_value = Mock(url="https://news.example/redirect?id=1")
    html_resp = Mock(url="https://news.example/redirect?id=1")
    type(html_resp).text = property(lambda _self: (_ for _ in ()).throw(UnicodeDecodeError("utf-8", b"x", 0, 1, "boom")))
    session.get.return_value = html_resp

    with patch("src.utils.requests.Session", return_value=session):
        result = expand_url("https://short.example/meta-bad")

    assert result == "https://news.example/redirect?id=1"
    html_resp.close.assert_called_once()
