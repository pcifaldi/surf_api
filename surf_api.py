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

# Get the Fixie URL from environment
FIXIE_URL = os.getenv('FIXIE_URL')

# Configure the proxy globally for requests
if FIXIE_URL:
    os.environ['HTTP_PROXY'] = FIXIE_URL
    os.environ['HTTPS_PROXY'] = FIXIE_URL

# Monkey patch the requests session
old_session = requests.Session

def new_session():
    session = old_session()
    # More browser-like headers
    session.headers.update({
        'User-Agent': 'Mozilla/5.0 (Macintosh; Intel Mac OS X 10_15_7) AppleWebKit/537.36 (KHTML, like Gecko) Chrome/119.0.0.0 Safari/537.36',
        'Accept': 'application/json,text/html,application/xhtml+xml,application/xml;q=0.9,image/avif,image/webp,image/apng,*/*;q=0.8',
        'Accept-Language': 'en-US,en;q=0.9',
        'Accept-Encoding': 'gzip, deflate, br',
        'sec-ch-ua': '"Google Chrome";v="119", "Chromium";v="119", "Not?A_Brand";v="24"',
        'sec-ch-ua-mobile': '?0',
        'sec-ch-ua-platform': '"macOS"',
        'sec-fetch-dest': 'document',
        'sec-fetch-mode': 'navigate',
        'sec-fetch-site': 'none',
        'sec-fetch-user': '?1',
        'upgrade-insecure-requests': '1',
        'Referer': 'https://www.surfline.com/',
        'Origin': 'https://www.surfline.com'
    })

    # Explicitly set proxies for each session
    if FIXIE_URL:
        session.proxies = {
            'http': FIXIE_URL,
            'https': FIXIE_URL
        }
        logger.debug("Fixie proxy configured for session")

    return session

# Apply the monkey patch
requests.Session = new_session

app = Flask(__name__)

def adjust_time(timestamp, utc_offset):
    """Adjust time using UTC offset and format as HH:MM"""
    if hasattr(timestamp, 'timestamp'):
        time_str = str(timestamp)
        base_time = datetime.strptime(time_str, "Time(%Y-%m-%d %H:%M:%S)")
    else:
        base_time = timestamp
    
    adjusted_time = base_time + timedelta(hours=utc_offset)
    return adjusted_time.strftime("%I:%M %p").lstrip('0')

def create_surf_data(spot_id):
    try:
        # Fetch forecast data for the given spot ID
        spotforecasts = pysurfline.get_spot_forecasts(
            spot_id,
            days=1,
            intervalHours=1,
        )
    except Exception as e:
        return None, f"Error fetching surf data: {e}"
    
    # Process the forecast data
    current_wave = spotforecasts.waves[0]
    current_weather = spotforecasts.weather[0]
    sunlight = spotforecasts.sunlightTimes[0]
    
    extreme_tides = [tide for tide in spotforecasts.tides if tide.type in ['HIGH', 'LOW']][:4]
    
    tide_data = {}
    for i, tide in enumerate(extreme_tides, 1):
        adjusted_time = adjust_time(tide.timestamp, tide.utcOffset)
        tide_data.update({
            f'tide{i}_time': adjusted_time,
            f'tide{i}_height': round(tide.height, 1),
            f'tide{i}_type': tide.type
        })
    
    for i in range(len(extreme_tides) + 1, 5):
        tide_data.update({
            f'tide{i}_time': '',
            f'tide{i}_height': '',
            f'tide{i}_type': ''
        })

    data = {
        "surf_height": f"{current_wave.surf.min}-{current_wave.surf.max}",
        "surf_condition": current_wave.surf.humanRelation,
        "swell_height": round(current_wave.swells[0].height, 1),
        "swell_period": current_wave.swells[0].period,
        "swell_direction": round(current_wave.swells[0].direction),
        "wind_speed": round(spotforecasts.wind[0].speed),
        "wind_direction": round(spotforecasts.wind[0].direction),
        "wind_type": spotforecasts.wind[0].directionType,
        "temperature": round(current_weather.temperature),
        "location": spotforecasts.name,
        "sunrise": adjust_time(sunlight.sunrise, sunlight.sunriseUTCOffset),
        "sunset": adjust_time(sunlight.sunset, sunlight.sunsetUTCOffset),
        **tide_data
    }
    
    return data, None

@app.route('/api/surf')
def get_surf_data():
    spot_id = request.args.get('spotId')
    if not spot_id:
        return jsonify({"error": "Missing spotId parameter"}), 400
    
    data, error = create_surf_data(spot_id)
    if error:
        return jsonify({"error": error}), 500
    
    return jsonify(data)

@app.route('/')
def home():
    return jsonify({
        "status": "ok",
        "message": "Surf API is running. Use /api/surf?spotId=<spot_id> to fetch surf data."
    })

@app.route('/test/ip')
def test_ip():
    """Test what IP we're using"""
    try:
        response = requests.get('https://api.ipify.org?format=json')
        return jsonify({
            'ip': response.json().get('ip'),
            'using_proxy': bool(os.getenv('FIXIE_URL')),
            'status': 'success'
        })
    except Exception as e:
        return jsonify({
            'error': str(e),
            'type': type(e).__name__
        })

@app.route('/test/local')
def test_local():
    """Test pysurfline's direct implementation"""
    try:
        result = pysurfline.get_spot_forecasts(
            "5842041f4e65fad6a7708a7d",
            days=1,
            intervalHours=1
        )
        return jsonify({
            'success': True,
            'has_waves': hasattr(result, 'waves'),
            'has_wind': hasattr(result, 'wind'),
            'has_tides': hasattr(result, 'tides'),
        })
    except Exception as e:
        return jsonify({
            'error': str(e),
            'type': type(e).__name__
        })

@app.route('/test/proxy')
def test_proxy():
    """Detailed proxy test"""
    try:
        # Make test requests
        headers = dict(requests.Session().headers)
        r1 = requests.get('https://api.ipify.org?format=json')
        r2 = requests.get('http://ifconfig.me/ip')
        
        # Test surfline with direct request first
        test_url = 'https://services.surfline.com/kbyg/spots/details'
        r3 = requests.get(test_url, params={'spotId': '5842041f4e65fad6a7708a7d'})
        
        return jsonify({
            'fixie_url_configured': bool(FIXIE_URL),
            'environment_proxies': {
                'http_proxy': os.getenv('HTTP_PROXY'),
                'https_proxy': os.getenv('HTTPS_PROXY')
            },
            'session_proxies': requests.Session().proxies,
            'headers_being_sent': headers,
            'ip_check_1': r1.json()['ip'],
            'ip_check_2': r2.text.strip(),
            'surfline_status': r3.status_code,
            'surfline_response': r3.text[:500] if r3.text else None,
            'surfline_headers': dict(r3.headers)
        })
    except Exception as e:
        logger.error(f"Proxy test error: {str(e)}")
        return jsonify({
            'error': str(e),
            'type': type(e).__name__
        })

if __name__ == "__main__":
    app.run(debug=True)
