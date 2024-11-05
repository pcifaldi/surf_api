import json
import pysurfline
from pathlib import Path
from datetime import datetime, timedelta
from flask import Flask, request, jsonify
import os
import logging
import requests

# Configure logging
logging.basicConfig(level=logging.DEBUG)
logger = logging.getLogger(__name__)

# Smartproxy residential configuration
SMARTPROXY_USERNAME = 'spj1z9isp9'
SMARTPROXY_PASSWORD = 'ys~j6rwfY95HikP3jZ'
SMARTPROXY_URL = f"http://{SMARTPROXY_USERNAME}:{SMARTPROXY_PASSWORD}@residential.smartproxy.com:10000"

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

    # Configure Smartproxy
    session.proxies = {
        'http': SMARTPROXY_URL,
        'https': SMARTPROXY_URL
    }
    logger.debug("Smartproxy residential configured for session")

    return session

# Apply the monkey patch
requests.Session = new_session

app = Flask(__name__)

@app.route('/test/proxy')
def test_proxy():
    """Test the proxy configuration"""
    try:
        # Test with different services
        ip_response = requests.get('https://ip.smartproxy.com/json')
        ipify_response = requests.get('https://api.ipify.org?format=json')
        
        # Test Surfline with specific endpoint
        surfline_url = 'https://services.surfline.com/kbyg/spots/details'
        surfline_response = requests.get(
            surfline_url, 
            params={'spotId': '5842041f4e65fad6a7708a7d'},
            allow_redirects=False  # Don't follow redirects to see exact response
        )

        return jsonify({
            'smartproxy_ip': ip_response.json(),
            'ipify_check': ipify_response.json(),
            'headers_being_sent': dict(requests.Session().headers),
            'proxy_settings': {
                'configured_url': SMARTPROXY_URL.replace(SMARTPROXY_PASSWORD, '****'),
                'active_proxies': requests.Session().proxies
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
