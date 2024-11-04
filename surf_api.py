import json
import requests
from datetime import datetime, timedelta
from flask import Flask, request, jsonify

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
        # Set up a session with custom headers to mimic a browser request
        session = requests.Session()
        session.headers.update({
            'User-Agent': 'Mozilla/5.0 (Windows NT 10.0; Win64; x64) AppleWebKit/537.36 (KHTML, like Gecko) Chrome/119.0.0.0 Safari/537.36',
            'Accept': 'application/json, text/plain, */*',
            'Accept-Language': 'en-US,en;q=0.9',
            'Origin': 'https://www.surfline.com',
            'Referer': 'https://www.surfline.com/'
        })
        
        # Make the request to Surfline API with the custom session
        response = session.get(
            f"https://services.surfline.com/kbyg/spots/details?spotId={spot_id}"
        )
        
        # Check if the response was successful; raise exception if not
        response.raise_for_status()
        
        # Parse the JSON response
        spotforecasts = response.json()
    except requests.exceptions.HTTPError as e:
        return None, f"Error fetching surf data: {e}"
    except Exception as e:
        return None, f"Unexpected error: {e}"

    # Assuming spotforecasts contains the necessary wave, weather, sunlightTimes, and tides data
    current_wave = spotforecasts['waves'][0]
    current_weather = spotforecasts['weather'][0]
    sunlight = spotforecasts['sunlightTimes'][0]
    
    # Filter only HIGH and LOW tides
    extreme_tides = [tide for tide in spotforecasts['tides'] if tide['type'] in ['HIGH', 'LOW']][:4]
    
    # Prepare tide data with explicit numbering and timezone adjustment
    tide_data = {}
    for i, tide in enumerate(extreme_tides, 1):
        adjusted_time = adjust_time(tide['timestamp'], tide['utcOffset'])
        tide_data.update({
            f'tide{i}_time': adjusted_time,
            f'tide{i}_height': round(tide['height'], 1),
            f'tide{i}_type': tide['type']
        })
    
    # Fill in any missing tide slots
    for i in range(len(extreme_tides) + 1, 5):
        tide_data.update({
            f'tide{i}_time': '',
            f'tide{i}_height': '',
            f'tide{i}_type': ''
        })

    # Create data structure with flat keys
    data = {
        "surf_height": f"{current_wave['surf']['min']}-{current_wave['surf']['max']}",
        "surf_condition": current_wave['surf']['humanRelation'],
        "swell_height": round(current_wave['swells'][0]['height'], 1),
        "swell_period": current_wave['swells'][0]['period'],
        "swell_direction": round(current_wave['swells'][0]['direction']),
        "wind_speed": round(spotforecasts['wind'][0]['speed']),
        "wind_direction": round(spotforecasts['wind'][0]['direction']),
        "wind_type": spotforecasts['wind'][0]['directionType'],
        "temperature": round(current_weather['temperature']),
        "location": spotforecasts['name'],
        # Adjust sunrise/sunset times using their UTC offsets
        "sunrise": adjust_time(sunlight['sunrise'], sunlight['sunriseUTCOffset']),
        "sunset": adjust_time(sunlight['sunset'], sunlight['sunsetUTCOffset']),
        **tide_data  # Add all tide data
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

if __name__ == "__main__":
    app.run(debug=True)
