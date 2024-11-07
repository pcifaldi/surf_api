import json
import pysurfline
from pathlib import Path
from datetime import datetime, timedelta
from flask import Flask, request, jsonify
import os
import logging
import requests
from requests.auth import HTTPProxyAuth

# Configure logging
logging.basicConfig(level=logging.DEBUG)
logger = logging.getLogger(__name__)

# SmartProxy configuration for Birmingham, UK
SMARTPROXY_USERNAME = "user-spj1z9isp9-country-gb-city-birmingham"
SMARTPROXY_PASSWORD = "ys~j6rwfY95HikP3jZ"
SMARTPROXY_URL = f"https://{SMARTPROXY_USERNAME}:{SMARTPROXY_PASSWORD}@gate.smartproxy.com:10001"

# Monkey patch the requests session
old_session = requests.Session

def new_session():
    session = old_session()
    # Browser-like headers
    session.headers.update({
        'User-Agent': 'Mozilla/5.0 (Macintosh; Intel Mac OS X 10_15_7) AppleWebKit/537.36 (KHTML, like Gecko) Chrome/119.0.0.0 Safari/537.36',
        'Accept': 'application/json',
        'Accept-Language': 'en-GB,en;q=0.9',
        'Accept-Encoding': 'gzip, deflate',
        'Origin': 'https://www.surfline.com',
        'Referer': 'https://www.surfline.com/'
    })

    # Configure proxy with authentication
    session.proxies = {
        'http': SMARTPROXY_URL,
        'https': SMARTPROXY_URL
    }

    # Add proxy authentication
    auth = HTTPProxyAuth(SMARTPROXY_USERNAME, SMARTPROXY_PASSWORD)
    session.auth = auth

    logger.debug("Configured SmartProxy session (Birmingham, UK)")
    return session

# Apply the monkey patch
requests.Session = new_session

# Patch pysurfline's session creation to use our proxy
original_init = pysurfline.SpotForecast.__init__
def new_init(self, *args, **kwargs):
    original_init(self, *args, **kwargs)
    self._session = new_session()
pysurfline.SpotForecast.__init__ = new_init

app = Flask(__name__)

@app.route('/test/proxy')
def test_proxy():
    """Test the proxy configuration"""
    try:
        # Create a new session for testing
        session = new_session()
        
        # Test sequence
        tests = {
            'smartproxy': 'https://ip.smartproxy.com/json',
            'ipify': 'https://api.ipify.org?format=json',
            'surfline_test': 'https://services.surfline.com/kbyg/spots/details?spotId=5842041f4e65fad6a7708a7d'
        }
        
        results = {}
        for name, url in tests.items():
            try:
                response = session.get(url, timeout=10)
                results[name] = {
                    'status': response.status_code,
                    'data': response.json() if name != 'surfline_test' else 'Response too long to display',
                    'headers': dict(response.headers)
                }
            except Exception as e:
                results[name] = {'error': str(e)}

        return jsonify({
            'proxy_settings': {
                'url': 'gate.smartproxy.com:10001',
                'location': 'Birmingham, UK',
                'headers': dict(session.headers)
            },
            'test_results': results
        })
    except Exception as e:
        logger.error(f"Test error: {str(e)}")
        return jsonify({'error': str(e)}), 500

@app.route('/api/surf')
def get_surf_data():
    spot_id = request.args.get('spotId')
    if not spot_id:
        return jsonify({"error": "Missing spotId parameter"}), 400
    
    try:
        spotforecasts = pysurfline.get_spot_forecasts(
            spot_id,
            days=1,
            intervalHours=1
        )
        
        data = {
            "current_conditions": {
                "surf": {
                    "min": spotforecasts.waves[0].surf.min,
                    "max": spotforecasts.waves[0].surf.max,
                    "human_relation": spotforecasts.waves[0].surf.humanRelation
                },
                "wind": {
                    "speed": round(spotforecasts.wind[0].speed),
                    "direction": round(spotforecasts.wind[0].direction),
                    "type": spotforecasts.wind[0].directionType
                },
                "tide": next((tide.height for tide in spotforecasts.tides if tide.type in ['HIGH', 'LOW']), None)
            }
        }
        return jsonify(data)
    except Exception as e:
        logger.error(f"Error getting surf data: {str(e)}")
        return jsonify({"error": str(e)}), 500

if __name__ == "__main__":
    port = int(os.getenv('PORT', 5000))
    app.run(host='0.0.0.0', port=port)
