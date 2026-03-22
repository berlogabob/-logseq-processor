from unittest.mock import Mock, patch

import requests

from src.html_parser import fetch_html


def _cfg(retry_count=2, backoff=1.5):
    cfg = Mock()
    cfg.http_retry_429_count = retry_count
    cfg.http_retry_429_backoff_seconds = backoff
    return cfg


def test_fetch_html_retries_429_with_exponential_backoff_then_succeeds():
    r1 = Mock(status_code=429)
    r2 = Mock(status_code=429)
    r3 = Mock(status_code=200, text="ok")
    r1.raise_for_status.side_effect = requests.HTTPError("429")
    r2.raise_for_status.side_effect = requests.HTTPError("429")
    r3.raise_for_status.return_value = None

    with patch("src.html_parser.validate_url", return_value=True), patch(
        "src.html_parser.get_rate_limiter"
    ) as mock_rl, patch("src.html_parser.trafilatura.fetch_url", return_value=None), patch(
        "src.html_parser.Config.get", return_value=_cfg(retry_count=2, backoff=1.5)
    ), patch(
        "src.html_parser._session.get", side_effect=[r1, r2, r3]
    ) as mock_get, patch(
        "src.html_parser.time.sleep"
    ) as mock_sleep:
        mock_rl.return_value.wait.return_value = False
        result = fetch_html("https://example.com/a")

    assert result == "ok"
    assert mock_get.call_count == 3
    mock_sleep.assert_any_call(1.5)
    mock_sleep.assert_any_call(3.0)


def test_fetch_html_stops_after_configured_429_retries():
    r1 = Mock(status_code=429)
    r2 = Mock(status_code=429)
    r3 = Mock(status_code=429)
    err = requests.HTTPError("429 too many requests")
    r1.raise_for_status.side_effect = err
    r2.raise_for_status.side_effect = err
    r3.raise_for_status.side_effect = err

    with patch("src.html_parser.validate_url", return_value=True), patch(
        "src.html_parser.get_rate_limiter"
    ) as mock_rl, patch("src.html_parser.trafilatura.fetch_url", return_value=None), patch(
        "src.html_parser.Config.get", return_value=_cfg(retry_count=2, backoff=0.5)
    ), patch(
        "src.html_parser._session.get", side_effect=[r1, r2, r3]
    ) as mock_get, patch(
        "src.html_parser.time.sleep"
    ) as mock_sleep:
        mock_rl.return_value.wait.return_value = False
        result = fetch_html("https://example.com/b")

    assert result is None
    assert mock_get.call_count == 3
    assert mock_sleep.call_count == 2

