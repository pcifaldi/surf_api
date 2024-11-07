from flask import Flask, request, jsonify
import requests
import logging
import pysurfline
from datetime import datetime
import os

logging.basicConfig(level=logging.DEBUG)
logger = logging.getLogger(__name__)

app = Flask(__name__)

@app.route('/api/surf')
def get_surf_data():
    spot_id = request.args.get('spotId')
    if not spot_id:
        return jsonify({"error": "Missing spotId parameter"}), 400
    
    try:
        # Get the forecast data
        spotforecasts = pysurfline.get_spot_forecasts(
            spot_id,
            days=1,
            intervalHours=1
        )
        
        # Format the response
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
            
    except Exception as e:
        logger.error(f"Error getting surf data: {str(e)}")
        return jsonify({"error": str(e)}), 500

@app.route('/')
def home():
    return jsonify({
        "status": "ok",
        "message": "Surf API is running. Use /api/surf?spotId=<spot_id> to fetch surf data."
    })

if __name__ == "__main__":
    port = int(os.getenv('PORT', 5000))
    app.run(host='0.0.0.0', port=port, debug=True)