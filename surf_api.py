import json
import pysurfline
from pathlib import Path
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

if __name__ == "__main__":
    app.run(debug=True)
