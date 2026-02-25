from flask import Flask, Response, request, jsonify
from flask_cors import CORS
import os
from datetime import datetime
from collections import deque

app = Flask(__name__)
CORS(app)

# Frame file location (shared with ai_detection.py)
FRAME_FILE = ".detection_frame.jpg"

# -------- Event Queue (stores last 100 events) ----------
event_queue = deque(maxlen=100)
violation_log = {}

# -------- Metrics (real-time dashboard) ----------
metrics = {
    "total_incidents": 0,
    "ppe_violations": 0,
    "fall_detections": 0,
    "proximity_alerts": 0,
    "security_breaches": 0,
    "helmet_violations": 0,
    "vest_violations": 0,
    "runtime_seconds": 0
}

def generate():
    """Generate video stream by reading frame file"""
    while True:
        try:
            if os.path.exists(FRAME_FILE):
                with open(FRAME_FILE, 'rb') as f:
                    frame = f.read()
                
                yield (b'--frame\r\n'
                       b'Content-Type: image/jpeg\r\n\r\n' + frame + b'\r\n')
            else:
                # No frame yet, send placeholder
                yield (b'--frame\r\n'
                       b'Content-Type: image/jpeg\r\n\r\n' + b'\r\n')
        except:
            pass
        
        # Small delay to avoid rapid reads
        __import__('time').sleep(0.03)

@app.route('/video')
def video():
    return Response(generate(),
        mimetype='multipart/x-mixed-replace; boundary=frame')

# -------- POST event endpoint ----------
@app.route('/event', methods=['POST'])
def receive_event():
    """
    Receives safety events from AI detection system
    Expected payload: {"event": "EVENT_TYPE", "detail": "description"}
    """
    try:
        data = request.get_json()
        
        if not data or 'event' not in data or 'detail' not in data:
            return jsonify({"error": "Missing event or detail"}), 400
        
        event_type = data['event']
        detail = data['detail']
        
        # Create event record with timestamp
        event_record = {
            "timestamp": datetime.now().isoformat(),
            "event": event_type,
            "detail": detail
        }
        
        # Store in queue
        event_queue.append(event_record)
        
        # Track violations for workers
        if "worker_" in detail.lower():
            worker_id = detail.split("worker_")[1].split()[0] if "worker_" in detail else "unknown"
            if worker_id not in violation_log:
                violation_log[worker_id] = []
            violation_log[worker_id].append(event_record)
        
        print(f"✅ Event received: {event_type} - {detail}")
        return jsonify({"status": "success", "message": "Event recorded"}), 200
        
    except Exception as e:
        print(f"❌ Error processing event: {str(e)}")
        return jsonify({"error": str(e)}), 500

# -------- GET all events endpoint ----------
@app.route('/events', methods=['GET'])
def get_events():
    """Returns all recent events from the queue"""
    return jsonify({
        "events": list(event_queue),
        "total_events": len(event_queue)
    }), 200

# -------- GET violations by worker ----------
@app.route('/violations/<worker_id>', methods=['GET'])
def get_violations(worker_id):
    """Returns violation history for a specific worker"""
    if worker_id in violation_log:
        return jsonify({
            "worker_id": worker_id,
            "violation_count": len(violation_log[worker_id]),
            "violations": violation_log[worker_id]
        }), 200
    else:
        return jsonify({
            "worker_id": worker_id,
            "violation_count": 0,
            "violations": []
        }), 200

# -------- POST/GET metrics endpoint ----------
@app.route('/metrics', methods=['POST'])
def receive_metrics():
    """Receives real-time metrics from AI detection system"""
    try:
        data = request.get_json()
        
        if not data:
            return jsonify({"error": "Missing metrics data"}), 400
        
        # Update metrics dictionary with received data
        metrics["total_incidents"] = data.get("total_incidents", metrics["total_incidents"])
        metrics["ppe_violations"] = data.get("ppe_violations", metrics["ppe_violations"])
        metrics["fall_detections"] = data.get("fall_detections", metrics["fall_detections"])
        metrics["proximity_alerts"] = data.get("proximity_alerts", metrics["proximity_alerts"])
        metrics["security_breaches"] = data.get("security_breaches", metrics["security_breaches"])
        metrics["helmet_violations"] = data.get("helmet_violations", metrics["helmet_violations"])
        metrics["vest_violations"] = data.get("vest_violations", metrics["vest_violations"])
        metrics["runtime_seconds"] = data.get("runtime_seconds", metrics["runtime_seconds"])
        
        return jsonify({"status": "success", "message": "Metrics updated"}), 200
        
    except Exception as e:
        print(f"❌ Error updating metrics: {str(e)}")
        return jsonify({"error": str(e)}), 500

@app.route('/metrics', methods=['GET'])
def get_metrics():
    """Returns current real-time metrics"""
    return jsonify(metrics), 200

# -------- alert sender (for backwards compatibility) ----------
def send_alert(msg):
    """Sends alert message (used by ai_detection.py)"""
    pass

if __name__ == "__main__":
    app.run(host='127.0.0.1', port=5000, debug=False)
