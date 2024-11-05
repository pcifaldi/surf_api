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

# Monkey patch the requests session in pysurfline to add headers
old_session = requests.Session

def new_session():
    session = old_session()
    # Match exactly what works locally
    session.headers.update({
        'User-Agent': 'python-requests/2.32.3',
        'Accept': '*/*',
        'Accept-Encoding': 'gzip, deflate',
        'Connection': 'keep-alive',
        'Content-Type': 'application/json',
        'Access-Control-Allow-Origin': '*',
        'access-control-allow-credentials': 'true',
        'x-auth-required': 'false'
    })
    # Remove problematic headers
    session.headers.pop('Origin', None)
    session.headers.pop('Referer', None)
    session.headers.pop('Host', None)  # Let requests set this automatically
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

@app.route('/test/headers')
def test_headers():
    """Test what headers and IP we're using"""
    url = 'https://services.surfline.com/kbyg/spots/details'
    params = {'spotId': '5842041f4e65fad6a7708a7d'}
    
    try:
        response = requests.get(url, params=params)
        ip_response = requests.get('https://api.ipify.org?format=json')
        ip_data = ip_response.json()

        debug_info = {
            'our_ip': ip_data.get('ip'),
            'request_headers': dict(response.request.headers),
            'response_status': response.status_code,
            'response_headers': dict(response.headers),
            'response_text': response.text[:500] + '...' if len(response.text) > 500 else response.text
        }
        
        return jsonify(debug_info)
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

if __name__ == "__main__":
    app.run(debug=True)
