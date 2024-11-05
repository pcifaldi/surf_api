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

# Brightdata proxy configuration
BRIGHTDATA_USERNAME = "brd-customer-hl_05e0f25a-zone-residential_proxy1-country-us"
BRIGHTDATA_PASSWORD = "go7qdsqremvt"
BRIGHTDATA_HOST = "brd.superproxy.io:22225"
BRIGHTDATA_URL = f"http://{BRIGHTDATA_USERNAME}:{BRIGHTDATA_PASSWORD}@{BRIGHTDATA_HOST}"

# Monkey patch the requests session
old_session = requests.Session

def new_session():
    session = old_session()
    # Browser-like headers
    session.headers.update({
        'User-Agent': 'Mozilla/5.0 (Windows NT 10.0; Win64; x64) AppleWebKit/537.36 (KHTML, like Gecko) Chrome/119.0.0.0 Safari/537.36',
        'Accept': 'application/json, text/plain, */*',
        'Accept-Language': 'en-US,en;q=0.9',
        'Accept-Encoding': 'gzip, deflate',
        'Origin': 'https://www.surfline.com',
        'Referer': 'https://www.surfline.com/',
        'DNT': '1',
        'Connection': 'keep-alive',
        'Sec-Fetch-Dest': 'empty',
        'Sec-Fetch-Mode': 'cors',
        'Sec-Fetch-Site': 'same-site'
    })

    # Configure Brightdata proxy
    session.proxies = {
        'http': BRIGHTDATA_URL,
        'https': BRIGHTDATA_URL
    }
    logger.debug(f"Configured Brightdata proxy: {BRIGHTDATA_HOST}")
    
    return session

# Apply the monkey patch
requests.Session = new_session

app = Flask(__name__)

@app.route('/test/proxy')
def test_proxy():
    """Test the proxy configuration"""
    try:
        logger.debug("Starting proxy test")
        
        # Test with multiple IP services
        test_urls = [
            'http://ip.brightdata.com/json',
            'https://api.ipify.org?format=json',
            'http://ip-api.com/json'
        ]
        
        ip_results = {}
        for url in test_urls:
            try:
                response = requests.get(url, timeout=10)
                ip_results[url] = response.json()
            except Exception as e:
                ip_results[url] = {'error': str(e)}

        # Test Surfline
        surfline_url = 'https://services.surfline.com/kbyg/spots/details'
        surfline_response = requests.get(
            surfline_url, 
            params={'spotId': '5842041f4e65fad6a7708a7d'},
            timeout=10
        )

        return jsonify({
            'ip_tests': ip_results,
            'headers_sent': dict(requests.Session().headers),
            'proxy_config': {
                'endpoint': BRIGHTDATA_HOST,
                'active': bool(requests.Session().proxies)
            },
            'surfline_test': {
                'status': surfline_response.status_code,
                'headers': dict(surfline_response.headers),
                'response': surfline_response.text[:500]
            }
        })
    except Exception as e:
        logger.error(f"Test error: {str(e)}")
        return jsonify({
            'error': str(e),
            'type': type(e).__name__,
            'details': {
                'proxy_configured': bool(requests.Session().proxies),
                'headers': dict(requests.Session().headers)
            }
        }), 500

@app.route('/api/surf')
def get_surf_data():
    spot_id = request.args.get('spotId')
    if not spot_id:
        return jsonify({"error": "Missing spotId parameter"}), 400
    
    try:
        spotforecasts = pysurfline.get_spot_forecasts(
            spot_id,
            days=1,
            intervalHours=1,
        )
        return jsonify({"data": spotforecasts})
    except Exception as e:
        return jsonify({"error": str(e)}), 500

if __name__ == "__main__":
    port = int(os.getenv('PORT', 5000))
    app.run(host='0.0.0.0', port=port)
