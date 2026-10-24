"""
Flask API Server for Watch Telemetry Ingestion
===============================================
Endpoints:
  - POST /api/upload_watch_csv: Ingests raw CSV multipart/form-data sent from 
    the Wear OS Galaxy Watch app over Wi-Fi, uploads the raw stream directly to 
    Google Drive, and returns the generated drive_file_id.
"""

import os
import sys
import io
import base64
from pathlib import Path
from flask import Flask, request, jsonify
from flask_cors import CORS

# Ensure root directory is in Python path for imports
ROOT_DIR = Path(__file__).resolve().parent.parent
if str(ROOT_DIR) not in sys.path:
    sys.path.insert(0, str(ROOT_DIR))

# Import the Google Drive uploader function from your Dash dashboard script
from visualization.data_collection_dash import upload_signal_to_google_drive

app = Flask(__name__)
CORS(app)  # Enable Cross-Origin Resource Sharing for watch / web requests

@app.route('/api/upload_watch_csv', methods=['POST'])
def upload_watch_csv():
    try:
        patient_id = request.form.get('patient_id', 'UNKNOWN').strip()
        
        if 'file' not in request.files:
            return jsonify({'status': 'error', 'message': 'No CSV file provided in request'}), 400
            
        file = request.files['file']
        filename = file.filename or f"{patient_id}_watch_raw.csv"
        content_bytes = file.read()
        
        if not content_bytes:
            return jsonify({'status': 'error', 'message': 'Uploaded file is empty'}), 400

        # 1. Format raw bytes into base64 Data URL expected by upload_signal_to_google_drive
        base64_encoded = base64.b64encode(content_bytes).decode('utf-8')
        data_url = f"data:text/csv;base64,{base64_encoded}"

        # 2. Upload file directly to study's Google Drive folder
        drive_file_id = upload_signal_to_google_drive(data_url, filename, patient_id)

        print(f"✅ [Flask Server] Received watch stream for {patient_id}. Saved to Drive (ID: {drive_file_id})")

        return jsonify({
            'status': 'success',
            'patient_id': patient_id,
            'drive_file_id': drive_file_id,
            'filename': filename
        }), 200

    except Exception as e:
        print(f"❌ [Flask Server] Error handling watch upload: {e}")
        return jsonify({'status': 'error', 'message': str(e)}), 500

if __name__ == '__main__':
    # Listen on all local interfaces on port 8050 (or port 5000)
    print("🚀 Starting Galaxy Watch Telemetry Ingestion API Server on port 8050...")
    app.run(host='0.0.0.0', port=5000, debug=True)
    