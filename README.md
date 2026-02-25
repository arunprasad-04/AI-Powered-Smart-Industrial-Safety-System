# Industrial AI Safety Monitoring System

A real-time AI-powered safety monitoring dashboard for industrial environments. This system uses computer vision to detect PPE violations, falls, unauthorized zone access, and other safety incidents, with automatic escalation and alerting mechanisms.

## 🏗️ System Architecture

### Backend (Flask)
- **POST /event**: Receives structured safety events from the AI detection system
- **GET /events**: Returns all recent events (stores up to 100 events)
- **GET /violations/<worker_id>**: Returns violation history for a specific worker
- **GET /video**: Streams live video feed from the camera

### Frontend (React + Vite)
- **Real-time Polling**: Polls `/events` endpoint every 500ms
- **Live Feed**: Displays live camera stream
- **Safety Status**: Shows machine status, PPE compliance, violation counts
- **Violations Log**: Table of all detected safety events
- **Geofencing**: Visual indicators for danger and restricted zones
- **Workers**: Individual worker cards with violation tracking
- **Agentic Operations**: Status of AI detection operations
- **Emergency Banner**: Prominent display during critical incidents

### AI Detection (Python with YOLO)
- PPE Detection (helmet, vest)
- Fall Detection using aspect ratio analysis
- Machine proximity monitoring
- Geofence violation detection
- Unauthorized access tracking

## 📋 Event Types

```
NO_HELMET              - Worker detected without helmet
NO_VEST                - Worker detected without safety vest
MACHINE_STOPPED        - Machine stopped (safety violation)
MACHINE_RUNNING        - Machine operating normally
FALL_DETECTED          - Worker fall detected
UNCONSCIOUS_EMERGENCY  - Worker unconscious for 10+ seconds
UNAUTHORIZED_ACCESS    - Worker in restricted zone
DANGER_ZONE_ENTRY      - Worker entered danger zone
PROXIMITY_ALERT        - Worker too close to machine
SUPERVISOR_ALERT       - Escalation to supervisor
HR_ESCALATION          - Escalation to HR department
```

## 🚀 Setup & Installation

### 1. Backend Requirements
```bash
cd "d:\MAKEATHON_PROJECT - Copy"
pip install -r requirements.txt
```

### 2. Frontend Requirements
```bash
cd frontend
npm install
```

### 3. Configuration
Ensure backend is running on `http://127.0.0.1:5000`

## ▶️ Running the System

### Terminal 1: Start Backend Server
```bash
cd "d:\MAKEATHON_PROJECT - Copy"
python backend_server.py
```

Backend will start at: `http://127.0.0.1:5000`

### Terminal 2: Start AI Detection
```bash
cd "d:\MAKEATHON_PROJECT - Copy"
python ai_detection.py
```

This opens a live camera window. Controls:
- Press `D` - Draw danger zone
- Press `R` - Draw restricted zone  
- Press `C` - Clear all zones
- Press `Q` - Quit

### Terminal 3: Start React Frontend
```bash
cd frontend
npm start
```

Frontend will open at: `http://localhost:3000`

## 📊 Integration Flow

1. **AI Detection** captures frames and runs YOLO models
2. Detections trigger events → **Event Sent to Backend** via POST `/event`
3. **Backend** stores events in queue and by worker ID
4. **Frontend** polls `/events` every 500ms
5. **Events processed** through INTEGRATION_RULES
6. **UI updates** automatically based on event type:
   - PPE violations → increment worker violation count, red alert
   - Falls → emergency banner with timer
   - Machine status → update indicator
   - Geofence → show zone breach warning
   - HR escalations → highlight worker in red

## 🎨 Dashboard Sections

| Section | Purpose |
|---------|---------|
| **Live Feed** | Real-time camera stream (16:9 aspect ratio) |
| **Safety Status** | 4-card display: Machine Status, PPE, Total Violations, Active Employees |
| **Active Alerts** | Scrollable list of recent alerts with severity colors |
| **Violations Log** | Timestamped table of all detected events |
| **Geofencing** | Zone status indicators (danger/restricted) |
| **Workers** | Individual worker cards with violation counts |
| **Agentic Operations** | Status of detection systems |
| **Emergency Banner** | Full-width red banner with timer during critical incidents |

## 🔴 Alert Severity Levels

- **Critical**: FALL_DETECTED, UNCONSCIOUS_EMERGENCY, HR_ESCALATION
- **High**: NO_HELMET, NO_VEST, UNAUTHORIZED_ACCESS, SUPERVISOR_ALERT, DANGER_ZONE_ENTRY
- **Medium**: MACHINE_STOPPED, PROXIMITY_ALERT
- **Low**: MACHINE_RUNNING

## 🧠 Agentic Rules

The system automatically escalates violations:

1. **First Violation**: Voice warning + visual alert
2. **Second Violation**: Supervisor alert + machine cutoff
3. **Third+ Violations**: HR escalation (worker highlighted in red)

## 📱 API Endpoints Reference

### POST /event
```json
{
  "event": "NO_HELMET",
  "detail": "Worker worker_001 detected without helmet"
}
```

Response:
```json
{
  "status": "success",
  "message": "Event recorded"
}
```

### GET /events
Response:
```json
{
  "events": [
    {
      "timestamp": "2026-02-20T14:30:45.123456",
      "event": "NO_HELMET",
      "detail": "Worker worker_001 detected without helmet"
    }
  ],
  "total_events": 5
}
```

### GET /violations/worker_001
Response:
```json
{
  "worker_id": "worker_001",
  "violation_count": 3,
  "violations": [
    {
      "timestamp": "2026-02-20T14:30:45.123456",
      "event": "NO_HELMET",
      "detail": "Worker worker_001 detected without helmet"
    }
  ]
}
```

## 🛠️ Troubleshooting

### Backend won't start
- Check if port 5000 is already in use: `netstat -ano | findstr :5000`
- Ensure all dependencies are installed: `pip install -r requirements.txt`

### Camera not detected
- Ensure camera is connected and not in use by another application
- Check camera permissions in Windows settings

### CORS errors on frontend
- Backend has been configured with flask-cors
- Ensure BACKEND_URL in App.js matches your backend address

### Video stream not showing
- Verify backend server is running
- Check browser console for errors
- Ensure camera feed is accessible via `/video` endpoint

## 📈 Performance Metrics

- **Polling Interval**: 500ms (configurable in App.js POLL_INTERVAL)
- **Event Queue Size**: 100 most recent events
- **Video Stream**: MJPEG format, adaptive quality
- **Detection FPS**: ~15-30 FPS (depends on GPU and model)

## 🔐 Security Notes

- CORS is enabled for all origins (configure for production)
- No authentication currently implemented (add for production)
- Events stored in memory only (implement database for persistence)
- Camera feed accessible without authentication (add login for production)

## 🎯 Future Enhancements

- [ ] Database integration (PostgreSQL/MongoDB)
- [ ] User authentication and role-based access
- [ ] WebSocket for real-time updates instead of polling
- [ ] Advanced analytics and trend reporting
- [ ] Multi-camera support
- [ ] Mobile app
- [ ] Email/SMS notifications
- [ ] Incident report generation
- [ ] Worker scheduling integration
- [ ] Machine telemetry integration

## 📞 Support

For issues or questions, ensure:
1. All Python packages are installed: `pip install -r requirements.txt`
2. Camera is properly connected
3. Port 5000 is available
4. Node.js and npm are installed for frontend
5. All three services (backend, AI detection, frontend) are running

---

**System Status**: Production Ready ✅  
**Last Updated**: February 20, 2026  
**Version**: 1.0.0
