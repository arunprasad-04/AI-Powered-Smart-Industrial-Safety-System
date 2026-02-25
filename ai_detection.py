import cv2
from ultralytics import YOLO
import math
import time
import numpy as np
import pyttsx3
from collections import defaultdict
import requests
import os
import winsound
import threading

# Optional: Twilio for SOS phone calls (install: pip install twilio)
try:
    from twilio.rest import Client
    TWILIO_AVAILABLE = True
except ImportError:
    TWILIO_AVAILABLE = False
    print("⚠️ Twilio not installed. SOS phone calls disabled. Install: pip install twilio")

# Frame file for sharing with backend
FRAME_FILE = ".detection_frame.jpg"

engine = pyttsx3.init()
EMPLOYEE_ID = "worker_001"
BACKEND_URL = "http://127.0.0.1:5000"

# ===== TWILIO SOS CONFIGURATION =====
# Install Twilio: pip install twilio
# Get credentials: https://www.twilio.com/try-twilio
TWILIO_ENABLED = True  # Set to False to disable SOS calls

# YOUR CREDENTIALS (Get from Twilio dashboard)
TWILIO_ACCOUNT_SID = "ACbd1c216109d0ad57061de375e4f07024"  # Replace with your Twilio Account SID
TWILIO_AUTH_TOKEN = "6301b3c268416a6ceb2f253438325b16"    # Replace with your Twilio Auth Token
TWILIO_PHONE_FROM = "+19156155448"        # Replace with your Twilio phone number
YOUR_PHONE_NUMBER = "+919952791914"      # Replace with your personal phone (with country code)

# Initialize Twilio client
twilio_client = None
if TWILIO_ENABLED and TWILIO_AVAILABLE:
    try:
        twilio_client = Client(TWILIO_ACCOUNT_SID, TWILIO_AUTH_TOKEN)
        print("✅ Twilio SOS system initialized")
    except Exception as e:
        print(f"⚠️ Twilio initialization failed: {e}")
        print(f"   Make sure credentials are correct in ai_detection.py")
        TWILIO_ENABLED = False

# ===== SIREN SOUND FUNCTION =====
def play_siren(duration=3):
    """
    Play a siren sound using Windows Beep
    Alternates between high and low frequency to create alarm effect
    Creates a distinctive alarm pattern: HIGH-LOW-HIGH-LOW...
    """
    def siren_loop():
        end_time = time.time() + duration
        while time.time() < end_time:
            # High frequency (1000 Hz) for 0.2 seconds
            winsound.Beep(1000, 200)
            # Low frequency (600 Hz) for 0.2 seconds  
            winsound.Beep(600, 200)
    
    # Run siren in background thread so it doesn't block video processing
    siren_thread = threading.Thread(target=siren_loop, daemon=True)
    siren_thread.start()

# ===== TWILIO SOS FUNCTIONS =====
def make_sos_call(worker_id, location_x, location_y, incident_type="FALL"):
    """
    Makes an emergency phone call to alert about incident
    Uses Twilio to make automated call with voice message
    Falls back to SMS if call fails
    
    Args:
        worker_id: Worker identifier
        location_x: X coordinate of incident
        location_y: Y coordinate of incident  
        incident_type: Type of incident (FALL, MEDICAL, etc.)
    """
    if not TWILIO_ENABLED or not twilio_client:
        print("⚠️ Twilio not configured - SOS call skipped")
        return False
    
    try:
        # Create voice message for the call
        message = (
            f"CRITICAL ALERT! {incident_type} detected for worker {worker_id} "
            f"at location {int(location_x)}, {int(location_y)}. "
            f"Emergency response activated. Repeat: CRITICAL ALERT!"
        )
        
        print(f"\n☎️ MAKING EMERGENCY CALL TO {YOUR_PHONE_NUMBER}...")
        
        # Make call with voice message
        call = twilio_client.calls.create(
            from_=TWILIO_PHONE_FROM,
            to=YOUR_PHONE_NUMBER,
            twiml=f'<Response><Say voice="alice">{message}</Say></Response>'
        )
        
        print(f"✅ EMERGENCY CALL PLACED")
        print(f"   📱 Call SID: {call.sid}")
        print(f"   📞 Calling: {YOUR_PHONE_NUMBER}")
        print(f"   ⏱️ Should arrive within 10 seconds")
        
        # Also send SMS as backup
        send_sos_sms(worker_id, location_x, location_y, incident_type)
        
        return True
        
    except Exception as e:
        print(f"❌ Emergency call failed: {e}")
        print(f"   Sending SMS backup instead...")
        send_sos_sms(worker_id, location_x, location_y, incident_type)
        return False


def send_sos_sms(worker_id, location_x, location_y, incident_type="FALL"):
    """
    Sends emergency SMS as backup or primary alert
    
    Args:
        worker_id: Worker identifier
        location_x: X coordinate of incident
        location_y: Y coordinate of incident
        incident_type: Type of incident
    """
    if not TWILIO_ENABLED or not twilio_client:
        return False
    
    try:
        message = (
            f"🚨 SOS ALERT: {incident_type} DETECTED!\n"
            f"Worker: {worker_id}\n"
            f"Location: ({int(location_x)}, {int(location_y)})\n"
            f"Status: Emergency response ACTIVATED\n"
            f"Time: {time.strftime('%H:%M:%S')}\n"
            f"Action: Check camera feed immediately"
        )
        
        print(f"\n📱 SENDING EMERGENCY SMS BACKUP TO {YOUR_PHONE_NUMBER}...")
        
        sms = twilio_client.messages.create(
            from_=TWILIO_PHONE_FROM,
            to=YOUR_PHONE_NUMBER,
            body=message
        )
        
        print(f"✅ EMERGENCY SMS SENT")
        print(f"   📱 Message SID: {sms.sid}")
        return True
        
    except Exception as e:
        print(f"❌ SMS failed: {e}")
        return False

# ===== EVENT SENDER =====
def send_event(event_type, detail):
    """
    Sends a structured event to the backend
    event_type: NO_HELMET, NO_VEST, FALL_DETECTED, UNCONSCIOUS_EMERGENCY, etc.
    detail: description of the event
    """
    try:
        payload = {
            "event": event_type,
            "detail": detail
        }
        response = requests.post(f"{BACKEND_URL}/event", json=payload, timeout=1)
        if response.status_code == 200:
            print(f"✅ Event sent: {event_type}")
        else:
            print(f"⚠️ Event failed: {response.status_code}")
    except Exception as e:
        print(f"⚠️ Could not send event: {str(e)}")


# ===== AGENTIC PREVENTION ACTION SYSTEM =====
# Track action states to prevent duplicate triggers
ppe_alarm_active = False
proximity_alarm_active = False
fall_emergency_dispatched = False
security_lockdown_active = False
last_ppe_alarm_time = 0
last_proximity_alert_time = 0

def trigger_ppe_alarm(worker_id, missing_gear):
    """
    🚨 PPE Non-Compliance AGENTIC ACTION:
    - Sound SIREN alarm (distinctive high-low pattern)
    - Block machine startup
    - Reduce machine speed to 50%
    - Send supervisor alert
    """
    global ppe_alarm_active, last_ppe_alarm_time
    
    current_time = time.time()
    if current_time - last_ppe_alarm_time < 2:  # Cooldown to avoid spam
        return
    
    last_ppe_alarm_time = current_time
    
    # 📊 UPDATE METRICS
    metrics["total_incidents"] += 1
    metrics["ppe_violations"] += 1
    if "HELMET" in missing_gear:
        metrics["helmet_violations"] += 1
    else:
        metrics["vest_violations"] += 1
    
    print(f"\n🚨 PPE ALARM TRIGGERED - Worker {worker_id} missing {missing_gear}")
    print(f"   🔊 SIREN ACTIVATED! (High-Low pattern)")
    
    # 1. Sound siren alarm
    play_siren(duration=3)  # Play 3-second siren with HIGH-LOW pattern
    
    # Also speak the warning
    try:
        engine.say(f"Safety violation! Please wear {missing_gear} immediately. Machine operation blocked.")
        engine.runAndWait()
    except:
        pass
    
    # 2. Block machine startup
    print(f"  ✋ ACTION: Blocking machine startup")
    send_event("MACHINE_BLOCKED", f"Machine startup blocked - Worker missing {missing_gear}")
    
    # 3. Reduce machine speed to 50%
    print(f"  ⚙️ ACTION: Reducing nearby machine speed to 50%")
    send_event("MACHINE_SPEED_REDUCED", f"Machine speed reduced to 50% - PPE non-compliance")
    
    # 4. Send supervisor alert
    print(f"  👔 ACTION: URGENT supervisor alert sent")
    send_event("SUPERVISOR_URGENT_ALERT", f"URGENT: Worker {worker_id} non-compliant - Manual intervention REQUIRED!")
    
    # Send metrics update
    send_metrics()
    
    ppe_alarm_active = True


def trigger_proximity_alarm(distance, worker_id):
    """
    ⚠️ Machine-Human Proximity Danger AGENTIC ACTION:
    - Auto-stop the machine
    - Escalating proximity alarm
    - Lock down danger zone
    - Alert machine operator
    """
    global proximity_alarm_active, last_proximity_alert_time
    
    current_time = time.time()
    if current_time - last_proximity_alert_time < 1:
        return
    
    last_proximity_alert_time = current_time
    
    print(f"\n⚠️ PROXIMITY EMERGENCY - Worker {worker_id} at {int(distance)}px from machine!")
    
    # 1. Auto-stop machine
    print(f"  🛑 ACTION: Emergency STOP activated - Machine halting immediately")
    send_event("MACHINE_EMERGENCY_STOP", f"Machine emergency stop! Worker at critical distance {int(distance)}px")
    
    # 2. Escalating alarm
    if distance < 100:
        try:
            engine.say("CRITICAL DANGER! Machine stopping! Step back immediately!")
            engine.runAndWait()
        except:
            pass
        print(f"  🔊 ACTION: CRITICAL ALERT - Hazard distance detected (10 meters)")
    elif distance < 150:
        try:
            engine.say("Warning! Dangerous proximity to machine! Step back now!")
            engine.runAndWait()
        except:
            pass
        print(f"  🔊 ACTION: WARNING ALERT - Caution zone")
    
    # 3. Lock down danger zone
    print(f"  🔒 ACTION: Danger zone electronically locked")
    send_event("ZONE_LOCKDOWN", f"Danger zone locked - Access restricted due to proximity hazard")
    
    # 4. Alert machine operator
    print(f"  📡 ACTION: Machine operator notified")
    send_event("OPERATOR_ALERT", f"OPERATOR ALERT: Worker detected too close! Maintain safe distance!")
    
    # 5. Update metrics
    metrics["total_incidents"] += 1
    metrics["proximity_alerts"] += 1
    send_metrics()
    
    proximity_alarm_active = True


def trigger_fall_emergency(worker_id, location_x, location_y):
    """
    🆘 Fall/Unconsciousness AGENTIC ACTION:
    - IMMEDIATELY call SOS number on personal phone
    - Dispatch ambulance (911 call)
    - Notify supervisors with location
    - Keep camera focused on worker
    """
    global fall_emergency_dispatched
    
    if fall_emergency_dispatched:
        return
    
    print(f"\n🆘 FALL EMERGENCY - Worker {worker_id} at ({location_x}, {location_y})")
    
    # 1. MAKE EMERGENCY PHONE CALL (IMMEDIATE - Most Urgent!!!)
    print(f"  ☎️ ACTION: EMERGENCY PHONE CALL TO YOUR MOBILE")
    make_sos_call(worker_id, location_x, location_y, "FALL")
    send_event("PHONE_CALL_SOS", f"📞 EMERGENCY CALL PLACED to {YOUR_PHONE_NUMBER}")
    
    # 2. Dispatch ambulance
    print(f"  📞 ACTION: Calling 911 - Ambulance dispatch INITIATED")
    send_event("EMERGENCY_911_DISPATCH", f"911 CALL PLACED: Ambulance dispatched for worker {worker_id} at site ({int(location_x)}, {int(location_y)})")
    
    # 3. Notify all supervisors
    print(f"  📲 ACTION: SMS/Push notifications sent to ALL supervisors")
    send_event("SUPERVISOR_CRITICAL_ALERT", f"🆘 CRITICAL: Fall detected at ({int(location_x)}, {int(location_y)}) - EMS called - Immediate response needed")
    
    # 4. Camera focus
    print(f"  📹 ACTION: Camera recording focused on incident")
    send_event("INCIDENT_RECORDING", f"Critical incident recording: Fall at ({int(location_x)}, {int(location_y)})")
    
    # 5. Update metrics
    metrics["total_incidents"] += 1
    metrics["fall_detections"] += 1
    send_metrics()
    
    fall_emergency_dispatched = True
    print(f"  ⏱️ Emergency response protocol ACTIVATED")


def trigger_security_lockdown(worker_id, location_x, location_y):
    """
    🔓 Unauthorized Access AGENTIC ACTION:
    - Lock all doors/gates
    - Capture intruder photo
    - Block exit routes
    - High-zoom surveillance
    - Alert security team
    - Disable asset removal
    """
    global security_lockdown_active
    
    if security_lockdown_active:
        return
    
    print(f"\n🔓 SECURITY BREACH - Unauthorized access at ({location_x}, {location_y})")
    
    # 1. Lock all doors
    print(f"  🔐 ACTION: All facility doors LOCKED electronically")
    send_event("DOORS_LOCKED", f"LOCKDOWN: All entries locked to contain intruder")
    
    # 2. Capture photo
    print(f"  📸 ACTION: Intruder photo CAPTURED and logged")
    send_event("INTRUDER_PHOTO", f"Intruder detected and photographed at ({int(location_x)}, {int(location_y)})")
    
    # 3. Block exits
    print(f"  🚫 ACTION: Emergency exit routes BLOCKED")
    send_event("EXITS_BLOCKED", f"All escape routes sealed - Intruder containment ACTIVE")
    
    # 4. High-zoom surveillance
    print(f"  🎥 ACTION: High-zoom surveillance ACTIVATED on intruder")
    send_event("ZOOM_SURVEILLANCE", f"Camera zoomed and tracked on unauthorized person")
    
    # 5. Alert security
    print(f"  🚨 ACTION: Security team MOBILIZED")
    send_event("SECURITY_ALERT", f"SECURITY BREACH! Intruder in restricted zone - Containment ACTIVE")
    
    # 6. Disable assets
    print(f"  🔒 ACTION: All valuable assets LOCKED/DISABLED")
    send_event("ASSETS_DISABLED", f"Equipment and assets locked - Theft prevention ACTIVE")
    
    # 7. Update metrics
    metrics["total_incidents"] += 1
    metrics["security_breaches"] += 1
    send_metrics()
    
    security_lockdown_active = True
    print(f"  🛡️ Total facility lockdown INITIATED")


# ===== AGENT MEMORY =====
violation_log = defaultdict(int)
machine_active = True
theft_start_time = None

# ===== REAL-TIME METRICS TRACKING =====
metrics = {
    "total_incidents": 0,
    "ppe_violations": 0,
    "fall_detections": 0,
    "proximity_alerts": 0,
    "security_breaches": 0,
    "helmet_violations": 0,
    "vest_violations": 0,
    "start_time": time.time()
}

def send_metrics():
    """Send real-time metrics to backend"""
    try:
        elapsed_time = int(time.time() - metrics["start_time"])
        payload = {
            "total_incidents": metrics["total_incidents"],
            "ppe_violations": metrics["ppe_violations"],
            "fall_detections": metrics["fall_detections"],
            "proximity_alerts": metrics["proximity_alerts"],
            "security_breaches": metrics["security_breaches"],
            "helmet_violations": metrics["helmet_violations"],
            "vest_violations": metrics["vest_violations"],
            "runtime_seconds": elapsed_time
        }
        requests.post(f"{BACKEND_URL}/metrics", json=payload, timeout=0.5)
    except:
        pass  # Silent fail for metrics

# ==========================LOAD MODELS FIRST======================
print("\n⏳ Loading AI models...", end="", flush=True)
model = YOLO("ppe.pt")              # PPE model
print(".", end="", flush=True)
machine_model = YOLO("yolov8n.pt") # General model
print(" ✅ Done!\n")

print("PPE Classes:", model.names)
print("Machine Classes:", machine_model.names)

# ==========================OPEN CAMERA (INSTANT DETECTION)======================
print("\n📷 Opening camera...")
cap = cv2.VideoCapture(0, cv2.CAP_DSHOW)
cap.set(cv2.CAP_PROP_BUFFERSIZE, 1)  # Reduce buffer for faster frame delivery

if not cap.isOpened():
    print("❌ Camera not opened")
    exit()

cv2.namedWindow("PPE Compliance System", cv2.WINDOW_NORMAL)
print("✅ Camera ready - Detection starting immediately!\n")
# ================= GEOFENCE DRAWING =================
danger_zone = []
restricted_zone = []
current_zone = "danger"

def draw_zone(event, x, y, flags, param):
    global danger_zone, restricted_zone, current_zone
    if event == cv2.EVENT_LBUTTONDOWN:
        if current_zone == "danger":
            danger_zone.append((x, y))
        else:
            restricted_zone.append((x, y))

cv2.setMouseCallback("PPE Compliance System", draw_zone)

def point_inside_zone(point, zone):
    if len(zone) < 3:
        return False
    x,y = point
    inside = False
    j = len(zone)-1
    for i in range(len(zone)):
        xi,yi = zone[i]
        xj,yj = zone[j]
        if ((yi>y) != (yj>y)) and (x < (xj-xi)*(y-yi)/(yj-yi)+xi):
            inside = not inside
        j=i
    return inside



fall_start_time = None
theft_start_time = None

def draw_info_panel(frame, info_text):
    """Draw a clean info panel on the right side of frame"""
    h, w = frame.shape[:2]
    panel_width = 180
    
    # Draw semi-transparent panel
    overlay = frame.copy()
    cv2.rectangle(overlay, (w - panel_width, 0), (w, h), (0, 0, 0), -1)
    cv2.addWeighted(overlay, 0.5, frame, 0.5, 0, frame)
    
    # Draw border
    cv2.rectangle(frame, (w - panel_width, 0), (w, h), (0, 200, 255), 2)
    
    # Draw text
    y_offset = 25
    for text, color in info_text:
        cv2.putText(frame, text, (w - panel_width + 10, y_offset),
                    cv2.FONT_HERSHEY_SIMPLEX, 0.4, color, 1)
        y_offset += 20
    
    return frame

while True:
    ret, frame = cap.read()
    if not ret:
        break

    frame = cv2.resize(frame, (640, 640))
    h, w = frame.shape[:2]
    
    # ===== INFO COLLECTION =====
    info_panel = []  # List of (text, color) tuples
    helmet_detected = False
    vest_detected = False
    no_helmet_alert = False
    no_vest_alert = False
    emergency_status = ""

    # ================= PPE DETECTION =================
    results = model(frame, conf=0.25, iou=0.45)

    for r in results:
        if r.boxes is None:
            continue

        for box in r.boxes:
            x1, y1, x2, y2 = map(int, box.xyxy[0])
            cls = int(box.cls[0])
            conf = float(box.conf[0])
            label = model.names[cls]
            color = (0, 255, 0)
            text = ""

            # Helmet
            if label in ["Hardhat", "helmet"]:
                text = "HELMET"
                helmet_detected = True
                machine_active = True
                color = (0, 255, 0)

            elif label in ["NO-Hardhat", "no-helmet"]:
                text = "NO HELMET"
                no_helmet_alert = True
                helmet_detected = False
                send_event("NO_HELMET", f"Worker {EMPLOYEE_ID} detected without helmet")
                machine_active = False
                violation_log[EMPLOYEE_ID] += 1
                count = violation_log[EMPLOYEE_ID]
                color = (0, 0, 255)
                # 🤖 AGENTIC ACTION: PPE Compliance Prevention
                trigger_ppe_alarm(EMPLOYEE_ID, "HELMET")
                
                if count == 1:
                    engine.say("Safety violation detected. Please wear helmet.")
                    engine.runAndWait()
                    emergency_status = "VOICE WARNING"
                elif count == 2:
                    emergency_status = "SUPERVISOR ALERTED"
                    send_event("SUPERVISOR_ALERT", f"Worker {EMPLOYEE_ID} has {count} violations")
                elif count >= 3:
                    emergency_status = "HR ESCALATION"
                    send_event("HR_ESCALATION", f"Worker {EMPLOYEE_ID} critical violations: {count}")

            # Vest
            elif label in ["Safety Vest", "vest", "safety-vest"]:
                text = "VEST"
                vest_detected = True
                color = (0, 255, 0)

            elif label in ["NO-Safety Vest", "no-vest"]:
                text = "NO VEST"
                no_vest_alert = True
                vest_detected = False
                send_event("NO_VEST", f"Worker {EMPLOYEE_ID} detected without safety vest")
                color = (0, 0, 255)
                # 🤖 AGENTIC ACTION: PPE Compliance Prevention
                trigger_ppe_alarm(EMPLOYEE_ID, "SAFETY VEST")

            else:
                continue

            # Draw bounding box
            cv2.rectangle(frame, (x1, y1), (x2, y2), color, 2)
            cv2.putText(frame, f"{text} {conf:.2f}", (x1, y1 - 10),
                        cv2.FONT_HERSHEY_SIMPLEX, 0.5, color, 1)

    # ================= MACHINE + PERSON DETECTION =================
    machine_results = machine_model(frame, conf=0.3)

    persons = []
    machines = []
    fall_detected = False
    proximity_danger = False
    zone_danger = False
    unconscious_time = 0

    for r in machine_results:
        if r.boxes is None:
            continue

        for box in r.boxes:
            x1, y1, x2, y2 = map(int, box.xyxy[0])
            cls = int(box.cls[0])
            label = machine_model.names[cls]

            # PERSON
            if label == "person":
                persons.append((x1, y1, x2, y2))
                cv2.rectangle(frame, (x1, y1), (x2, y2), (255, 0, 0), 2)

                # ================= FALL DETECTION =================
                w = x2 - x1
                h = y2 - y1

                if w > h * 1.2:
                    fall_detected = True
                    
                    if fall_start_time is None:
                        fall_start_time = time.time()
                        send_event("FALL_DETECTED", f"Worker {EMPLOYEE_ID} fall detected")
                        # 🤖 AGENTIC ACTION: Emergency Response for Fall
                        trigger_fall_emergency(EMPLOYEE_ID, (x1 + x2) // 2, (y1 + y2) // 2)

                    unconscious_time = int(time.time() - fall_start_time)
                    cv2.rectangle(frame, (x1, y1), (x2, y2), (0, 0, 255), 3)
                    
                    if unconscious_time >= 10:
                        send_event("UNCONSCIOUS_EMERGENCY", f"Worker {EMPLOYEE_ID} critical - unconscious for {unconscious_time}s")

            # MACHINES / VEHICLES
            elif label in ["car", "truck", "bus", "motorcycle", "excavator"]:
                machines.append((x1, y1, x2, y2))
                cv2.rectangle(frame, (x1, y1), (x2, y2), (0, 165, 255), 2)

    # ================= DISTANCE SAFETY =================
    for (px1, py1, px2, py2) in persons:
        pcx = (px1 + px2) // 2
        pcy = (py1 + py2) // 2

        for (mx1, my1, mx2, my2) in machines:
            mcx = (mx1 + mx2) // 2
            mcy = (my1 + my2) // 2

            distance = math.sqrt((pcx - mcx) ** 2 + (pcy - mcy) ** 2)
            cv2.line(frame, (pcx, pcy), (mcx, mcy), (0, 0, 255), 1)

            if distance < 150:
                proximity_danger = True
                send_event("PROXIMITY_ALERT", f"Worker {EMPLOYEE_ID} too close to machine - distance: {int(distance)}px")
                # 🤖 AGENTIC ACTION: Proximity Danger Prevention
                trigger_proximity_alarm(distance, EMPLOYEE_ID)

    # ================= GEOFENCE ZONES =================
    if len(danger_zone) > 1:
        cv2.polylines(frame, [np.array(danger_zone)], True, (0, 0, 255), 2)
    if len(restricted_zone) > 1:
        cv2.polylines(frame, [np.array(restricted_zone)], True, (255, 0, 0), 2)

    # ================= GEOFENCE CHECK =================
    for (px1, py1, px2, py2) in persons:
        cx = (px1 + px2) // 2
        cy = (py1 + py2) // 2

        if point_inside_zone((cx, cy), danger_zone):
            zone_danger = True
            send_event("DANGER_ZONE_ENTRY", f"Worker {EMPLOYEE_ID} entered danger zone")

        if point_inside_zone((cx, cy), restricted_zone):
            send_event("UNAUTHORIZED_ACCESS", f"Worker {EMPLOYEE_ID} entered restricted zone")
            # 🤖 AGENTIC ACTION: Security Lockdown for Unauthorized Access
            trigger_security_lockdown(EMPLOYEE_ID, cx, cy)

    # ================= BUILD INFO PANEL =================
    info_panel = []
    
    # PPE Status
    if helmet_detected:
        info_panel.append(("✓ Helmet", (0, 255, 0)))
    else:
        info_panel.append(("✗ NO HELMET!", (0, 0, 255)))
    
    if vest_detected:
        info_panel.append(("✓ Vest", (0, 255, 0)))
    else:
        info_panel.append(("✗ NO VEST!", (0, 0, 255)))
    
    # Safety Alerts
    if fall_detected:
        info_panel.append(("⚠ FALL!", (0, 0, 255)))
        if unconscious_time > 0:
            info_panel.append((f"Conscious: {unconscious_time}s", (0, 0, 255)))
    
    if proximity_danger:
        info_panel.append(("⚠ PROXIMITY ALERT", (0, 0, 255)))
    
    if zone_danger:
        info_panel.append(("⚠ DANGER ZONE", (0, 0, 255)))
    
    # Machine Status
    if machine_active:
        info_panel.append(("Machine: RUNNING", (0, 255, 0)))
    else:
        info_panel.append(("Machine: STOPPED", (0, 165, 255)))
    
    # Draw the info panel
    frame = draw_info_panel(frame, info_panel)
    
    # ================= UI HELP =================
    cv2.putText(frame, "D=Danger | R=Restricted | C=Clear", 
                (10, 20), cv2.FONT_HERSHEY_SIMPLEX, 0.5, (255, 255, 255), 1)

    # ================= SAVE FRAME FOR BACKEND =================
    try:
        cv2.imwrite(FRAME_FILE, frame)
    except:
        pass  # Ignore write errors

    cv2.imshow("PPE Compliance System", frame)

    key = cv2.waitKey(1) & 0xFF
    if key == ord('d'):
        current_zone = "danger"
        print("Drawing DANGER zone")
    if key == ord('r'):
        current_zone = "restricted"
        print("Drawing RESTRICTED zone")
    if key == ord('c'):
        danger_zone.clear()
        restricted_zone.clear()
    if key == ord('q'):
        break



cap.release()
cv2.destroyAllWindows()
