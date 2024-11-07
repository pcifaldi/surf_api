import json
import pysurfline
from pathlib import Path
from datetime import datetime, timedelta
from flask import Flask, request, jsonify
import os
import logging
import requests
from requests.auth import HTTPProxyAuth

logging.basicConfig(level=logging.DEBUG)
logger = logging.getLogger(__name__)

# SmartProxy configuration
SMARTPROXY_USERNAME = 'user-spj1z9isp9-country-gb-city-birmingham'
SMARTPROXY_PASSWORD = 'ys~j6rwfY95HikP3jZ'
SMARTPROXY_HOST = 'gate.smartproxy.com:10001'

def configure_session():
    session = requests.Session()
    
    # Set up proxy authentication
    auth = HTTPProxyAuth(SMARTPROXY_USERNAME, SMARTPROXY_PASSWORD)
    session.auth = auth
    
    # Configure proxy URL without credentials
    proxy_url = f"http://{SMARTPROXY_HOST}"
    session.proxies = {
        'http': proxy_url,
        'https': proxy_url
    }
    
    # Add headers
    session.headers.update({
        'User-Agent': 'Mozilla/5.0 (Macintosh; Intel Mac OS X 10_15_7) AppleWebKit/537.36 (KHTML, like Gecko) Chrome/119.0.0.0 Safari/537.36',
        'Accept': 'application/json',
        'Accept-Language': 'en-US,en;q=0.9',
        'Accept-Encoding': 'gzip, deflate',
        'Origin': 'https://www.surfline.com',
        'Referer': 'https://www.surfline.com/'
    })
    
    logger.debug("SmartProxy session configured with auth")
    return session

app = Flask(__name__)

@app.route('/test/proxy')
def test_proxy():
    """Test the proxy configuration"""
    try:
        session = configure_session()
        
        # Test sequence
        ip_response = session.get('http://ip.smartproxy.com/json')
        logger.debug(f"IP Response: {ip_response.text}")
        
        surfline_response = session.get(
            'https://services.surfline.com/kbyg/spots/details',
            params={'spotId': '5842041f4e65fad6a7708a7d'}
        )
        logger.debug(f"Surfline Status: {surfline_response.status_code}")

        return jsonify({
            'proxy_test': {
                'ip_data': ip_response.json(),
                'surfline_status': surfline_response.status_code
            },
            'config': {
                'proxy_host': SMARTPROXY_HOST,
                'username': SMARTPROXY_USERNAME,
                'headers': dict(session.headers)
            }
        })
    except requests.exceptions.RequestException as e:
        logger.error(f"Request error: {str(e)}")
        return jsonify({
            'error': str(e),
            'type': 'RequestException',
            'details': {
                'proxy_configured': bool(session.proxies),
                'auth_configured': bool(session.auth),
                'headers': dict(session.headers)
            }
        }), 500
    except Exception as e:
        logger.error(f"Test error: {str(e)}")
        return jsonify({'error': str(e)}), 500

@app.route('/api/surf')
def get_surf_data():
    """Get surf data using configured proxy"""
    spot_id = request.args.get('spotId')
    if not spot_id:
        return jsonify({"error": "Missing spotId parameter"}), 400
    
    try:
        old_session = requests.Session
        requests.Session = configure_session
        
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
                    "temperature": round(spotforecasts.weather[0].temperature)
                },
                "tides": [
                    {
                        "time": str(tide.timestamp),
                        "height": round(tide.height, 1),
                        "type": tide.type
                    }
                    for tide in spotforecasts.tides if tide.type in ['HIGH', 'LOW']
                ][:4],
                "location": spotforecasts.name
            }
            return jsonify(data)
        finally:
            requests.Session = old_session
            
    except Exception as e:
        logger.error(f"Error getting surf data: {str(e)}")
        return jsonify({"error": str(e)}), 500

if __name__ == "__main__":
    port = int(os.getenv('PORT', 5000))
    app.run(host='0.0.0.0', port=port)
