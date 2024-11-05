import json
import pysurfline
from pathlib import Path
from datetime import datetime, timedelta
from flask import Flask, request, jsonify
import os
import logging
import requests
import socket
import socks

# Configure logging
logging.basicConfig(level=logging.DEBUG)
logger = logging.getLogger(__name__)

# Set up SOCKS support for the socket library
socks.set_default_proxy(
    socks.SOCKS5, 
    "gate.smartproxy.com",
    7000,
    username="user-spj1z9isp9-session-1-state-us_south_carolina",
    password="ys~j6rwfY95HikP3jZ"
)
socket.socket = socks.socksocket

# Smartproxy configuration - using residential rotating endpoint
SMARTPROXY_USERNAME = "user-spj1z9isp9-session-1-state-us_south_carolina"
SMARTPROXY_PASSWORD = "ys~j6rwfY95HikP3jZ"
SMARTPROXY_URL = f"http://{SMARTPROXY_USERNAME}:{SMARTPROXY_PASSWORD}@us.smartproxy.com:10001"

# Monkey patch the requests session
old_session = requests.Session

def new_session():
    session = old_session()
    # More complete browser-like headers
    session.headers.update({
        'User-Agent': 'Mozilla/5.0 (Macintosh; Intel Mac OS X 10_15_7) AppleWebKit/537.36 (KHTML, like Gecko) Chrome/119.0.0.0 Safari/537.36',
        'Accept': 'text/html,application/xhtml+xml,application/xml;q=0.9,image/avif,image/webp,image/apng,*/*;q=0.8,application/signed-exchange;v=b3;q=0.7',
        'Accept-Language': 'en-US,en;q=0.9',
        'Accept-Encoding': 'gzip, deflate, br',
        'Cache-Control': 'max-age=0',
        'Sec-Ch-Ua': '"Google Chrome";v="119", "Chromium";v="119", "Not?A_Brand";v="24"',
        'Sec-Ch-Ua-Mobile': '?0',
        'Sec-Ch-Ua-Platform': '"macOS"',
        'Sec-Fetch-Dest': 'document',
        'Sec-Fetch-Mode': 'navigate',
        'Sec-Fetch-Site': 'none',
        'Sec-Fetch-User': '?1',
        'Upgrade-Insecure-Requests': '1',
        'Connection': 'keep-alive',
        'Referer': 'https://www.surfline.com/',
        'Host': 'services.surfline.com'
    })

    # Configure proxy
    session.proxies = {
        'http': SMARTPROXY_URL,
        'https': SMARTPROXY_URL
    }
    logger.debug("Smartproxy configured for session")

    return session

# Apply the monkey patch
requests.Session = new_session

app = Flask(__name__)

@app.route('/test/proxy')
def test_proxy():
    """Test the proxy configuration"""
    try:
        # Test with multiple IP check services
        responses = {
            'smartproxy': requests.get('https://ip.smartproxy.com/json').json(),
            'ipify': requests.get('https://api.ipify.org?format=json').json(),
            'httpbin': requests.get('https://httpbin.org/ip').json()
        }
        
        # Test Surfline
        surfline_url = 'https://services.surfline.com/kbyg/spots/details'
        surfline_response = requests.get(
            surfline_url, 
            params={'spotId': '5842041f4e65fad6a7708a7d'},
            allow_redirects=False
        )

        return jsonify({
            'ip_checks': responses,
            'headers_being_sent': dict(requests.Session().headers),
            'proxy_settings': {
                'configured_url': SMARTPROXY_URL.replace(SMARTPROXY_PASSWORD, '****'),
                'active_proxies': requests.Session().proxies,
                'using_socks': True
            },
            'surfline_status': surfline_response.status_code,
            'surfline_headers': dict(surfline_response.headers),
            'surfline_response': surfline_response.text[:500] if surfline_response.text else None
        })
    except Exception as e:
        logger.error(f"Proxy test error: {str(e)}")
        return jsonify({
            'error': str(e),
            'type': type(e).__name__,
            'error_detail': str(e)
        })

if __name__ == "__main__":
    port = int(os.getenv('PORT', 5000))
    app.run(host='0.0.0.0', port=port)
