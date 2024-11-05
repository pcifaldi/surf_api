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
SMARTPROXY_USERNAME = "user-spj1z9isp9-session-1-state-us_south_carolina"
SMARTPROXY_PASSWORD = "ys~j6rwfY95HikP3jZ"
# Using residential proxy endpoint
SMARTPROXY_URL = f"http://{SMARTPROXY_USERNAME}:{SMARTPROXY_PASSWORD}@us-sc.smartproxy.com:10001"

# Monkey patch the requests session
old_session = requests.Session

def new_session():
    session = old_session()
    # Browser-like headers
    session.headers.update({
        'User-Agent': 'Mozilla/5.0 (Windows NT 10.0; Win64; x64) AppleWebKit/537.36 (KHTML, like Gecko) Chrome/119.0.0.0 Safari/537.36',
        'Accept': 'text/html,application/xhtml+xml,application/xml;q=0.9,image/avif,image/webp,image/apng,*/*;q=0.8',
        'Accept-Language': 'en-US,en;q=0.9',
        'Accept-Encoding': 'gzip, deflate',
        'Cache-Control': 'no-cache',
        'Pragma': 'no-cache',
        'Connection': 'keep-alive'
    })

    # Configure Smartproxy
    session.proxies = {
        'http': SMARTPROXY_URL,
        'https': SMARTPROXY_URL
    }
    logger.debug(f"Configured proxy: {SMARTPROXY_URL.split('@')[1]}")
    
    return session

# Apply the monkey patch
requests.Session = new_session

app = Flask(__name__)

@app.route('/test/proxy')
def test_proxy():
    """Test the proxy configuration"""
    try:
        # First test with a simple IP check
        ip_test = requests.get('http://ip.smartproxy.com/json', timeout=10)
        logger.debug(f"IP Test Response: {ip_test.text}")

        # If successful, try Surfline
        surfline_url = 'https://services.surfline.com/kbyg/spots/details'
        surfline_response = requests.get(
            surfline_url, 
            params={'spotId': '5842041f4e65fad6a7708a7d'},
            timeout=10,
            allow_redirects=False
        )

        return jsonify({
            'proxy_test': {
                'ip_data': ip_test.json(),
                'status': ip_test.status_code
            },
            'headers_sent': dict(requests.Session().headers),
            'proxy_config': {
                'endpoint': SMARTPROXY_URL.split('@')[1],
                'active': bool(requests.Session().proxies)
            },
            'surfline_test': {
                'status': surfline_response.status_code,
                'headers': dict(surfline_response.headers),
                'response': surfline_response.text[:500]
            }
        })
    except requests.exceptions.RequestException as e:
        logger.error(f"Request error: {str(e)}")
        return jsonify({
            'error': str(e),
            'type': 'RequestException',
            'details': {
                'proxy_configured': bool(requests.Session().proxies),
                'headers': dict(requests.Session().headers)
            }
        }), 500
    except Exception as e:
        logger.error(f"Unexpected error: {str(e)}")
        return jsonify({
            'error': str(e),
            'type': type(e).__name__
        }), 500

if __name__ == "__main__":
    port = int(os.getenv('PORT', 5000))
    app.run(host='0.0.0.0', port=port)
