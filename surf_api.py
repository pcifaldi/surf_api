import pysurfline
from flask import Flask, jsonify
from datetime import datetime, timedelta
import os
from dotenv import load_dotenv
import requests

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

def get_surf_forecast(spot_id):
    """Get surf forecast directly from the API"""
    # Build the URL for the Surfline API
    base_url = "https://services.surfline.com/kbyg/spots/forecasts"
    endpoints = {
        'wave': f'{base_url}/wave',
        'wind': f'{base_url}/wind',
        'tides': f'{base_url}/tides',
        'weather': f'{base_url}/weather'
    }
    
    params = {
        'spotId': spot_id,
        'days': 1,
        'intervalHours': 1
    }
    
    # Make API requests
    forecasts = {}
    for name, url in endpoints.items():
        response = requests.get(url, params=params)
        if response.status_code == 200:
            forecasts[name] = response.json()
        else:
            return None, f"Error fetching {name} data: {response.status_code}"
    
    return forecasts, None

def create_surf_data(spot_id):
    """Generate surf data for a given spot ID"""
    try:
        # Validate spot_id format
        if not spot_id.strip() or not all(c in '0123456789abcdefABCDEF' for c in spot_id):
            return None, "Invalid spot ID format"
        
        # Get forecasts directly
        forecasts, error = get_surf_forecast(spot_id)
        if error:
            return None, error

        # Create data structure
        current_wave = forecasts['wave']['data'][0]
        current_weather = forecasts['weather']['data'][0]
        current_wind = forecasts['wind']['data'][0]
        tides = forecasts['tides']['data']
        
        # Filter extreme tides
        extreme_tides = [tide for tide in tides if tide['type'] in ['HIGH', 'LOW']][:4]
        
        # Prepare tide data
        tide_data = {}
        for i, tide in enumerate(extreme_tides, 1):
            time = datetime.fromtimestamp(tide['timestamp'])
            adjusted_time = adjust_time(time, -4)  # Assuming UTC-4 for now
            tide_data.update({
                f'tide{i}_time': adjusted_time,
                f'tide{i}_height': round(tide['height'], 1),
                f'tide{i}_type': tide['type']
            })
        
        # Fill in missing tide slots
        for i in range(len(extreme_tides) + 1, 5):
            tide_data.update({
                f'tide{i}_time': '',
                f'tide{i}_height': '',
                f'tide{i}_type': ''
            })

        # Create data structure
        data = {
            "surf_height": f"{current_wave['surf']['min']}-{current_wave['surf']['max']}",
            "surf_condition": current_wave['surf']['humanRelation'],
            "swell_height": round(current_wave['swells'][0]['height'], 1),
            "swell_period": current_wave['swells'][0]['period'],
            "swell_direction": round(current_wave['swells'][0]['direction']),
            "wind_speed": round(current_wind['speed']),
            "wind_direction": round(current_wind['direction']),
            "wind_type": current_wind.get('directionType', 'Unknown'),
            "temperature": round(current_weather['temperature']),
            "location": forecasts['wave']['associated']['name'],
            "sunrise": datetime.fromtimestamp(current_weather['sunrise']).strftime("%I:%M %p"),
            "sunset": datetime.fromtimestamp(current_weather['sunset']).strftime("%I:%M %p"),
            **tide_data
        }
        return data, None
    except Exception as e:
        print(f"Unexpected error: {str(e)}")  # Add logging
        return None, f"Unexpected error: {str(e)}"

@app.route('/')
def home():
    """Health check endpoint"""
    return jsonify({
        'status': 'ok',
        'message': 'Surf API is running'
    })

@app.route('/api/surf/<spot_id>')
def get_surf_data(spot_id):
    """API endpoint that returns JSON data for a given spot ID"""
    data, error = create_surf_data(spot_id)
    
    if error:
        error_response = {
            'error': error,
            'status': 'error'
        }
        if "not found" in error.lower():
            return jsonify(error_response), 404
        elif "invalid spot id format" in error.lower():
            return jsonify(error_response), 400
        else:
            return jsonify(error_response), 500
    
    return jsonify({
        'status': 'success',
        'data': data
    })

if __name__ == '__main__':
    port = int(os.getenv('PORT', 5000))
    app.run(host='0.0.0.0', port=port)