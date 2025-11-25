"""
Flask + Socket.IO server for real-time image streaming and face detection.

- Generates a session_id on client connect and emits 'session_created'.
- Manages session state (active/inactive, detection on/off).
- Events supported: start_detection, stop_detection, frame
- When detection is ON for the session, received frames (base64) are decoded
  to OpenCV BGR frames and passed to `run_detection(frame)` from `main.py`.
- Emits 'detection_result' back to the client containing session_id + results.

Run: python server.py

Notes:
- For real WebSocket transport with Flask-SocketIO ensure 'eventlet' is installed.
- CORS is allowed for all origins (adjust in production).
"""

from flask import Flask, request
from flask_cors import CORS
from flask_socketio import SocketIO, emit
import base64
import numpy as np
import cv2
import uuid
import time
import logging

# Import the detection entrypoint implemented in main.py
from main import run_detection
from database import AttendanceDatabase

# Instantiate shared DB
db = AttendanceDatabase()

# --- Configuration ---
HOST = '0.0.0.0'
PORT = 5000

# Create Flask app
app = Flask(__name__)
app.config["SECRET_KEY"] = "super-secret-key"
CORS(app, resources={r"/*": {"origins": "*"}})

# Use eventlet if available for proper websocket transport support
# If eventlet isn't installed the server will still run but websocket may fall back to polling
try:
    import eventlet  # noqa: F401
    async_mode = 'eventlet'
except Exception:
    async_mode = None

socketio = SocketIO(app, cors_allowed_origins='*', async_mode=async_mode)

logger = logging.getLogger('socketio_server')
logger.setLevel(logging.INFO)
handler = logging.StreamHandler()
handler.setFormatter(logging.Formatter('%(asctime)s %(levelname)s %(message)s'))
logger.addHandler(handler)


class SessionManager:
    """Gestion simple des sessions clients.

    sessions: dict mapping session_id -> session_info
    sid_to_session: dict mapping socket sid -> session_id
    """

    def __init__(self):
        self.sessions = {}
        self.sid_to_session = {}

    def create_session_for_sid(self, sid):
        session_id = str(uuid.uuid4())
        now = time.time()
        info = {
            'session_id': session_id,
            'sid': sid,
            'created_at': now,
            'last_seen': now,
            'active': True,
            'detection': False,  # detection mode off by default
            'db_session_id': None,  # link to attendance.sessions.id in DB
        }
        self.sessions[session_id] = info
        self.sid_to_session[sid] = session_id
        return session_id

    def get_by_sid(self, sid):
        session_id = self.sid_to_session.get(sid)
        if not session_id:
            return None
        return self.sessions.get(session_id)

    def set_detection(self, sid, enabled: bool):
        session = self.get_by_sid(sid)
        if not session:
            return False
        session['detection'] = bool(enabled)
        session['last_seen'] = time.time()
        return True

    def mark_inactive(self, sid):
        session = self.get_by_sid(sid)
        if session:
            session['active'] = False
            session['last_seen'] = time.time()
            # remove mapping
            self.sid_to_session.pop(sid, None)


sessions = SessionManager()


# --- Socket.IO events ---
@socketio.on('connect')
def handle_connect():
    sid = getattr(request, 'sid', None)
    if sid is None:
        # Fallback: generate a temporary sid-like identifier (rare)
        sid = str(uuid.uuid4())
    session_id = sessions.create_session_for_sid(sid)
    logger.info(f"Client connected (sid={sid}) -> session {session_id}")

    # Emit session_created only to the connecting client
    emit('session_created', {'session_id': session_id})


@socketio.on('disconnect')
def handle_disconnect():
    sid = getattr(request, 'sid', None)
    if sid is None:
        logger.info("Client disconnected (unknown sid)")
        return
    sessions.mark_inactive(sid)
    logger.info(f"Client disconnected (sid={sid})")


@socketio.on('start_detection')
def handle_start_detection(data=None):
    """Activate detection mode for this session.

    Client can optionally send {'session_id': '...', 'professor_id': int, 'subject': str},
    but usually the server tracks session by socket sid. If professor_id/subject are provided
    we create a DB session (or recreate it once) and store `db_session_id` in session info.
    """
    sid = getattr(request, 'sid', None)
    if sid is None:
        emit('error', {'detail': 'Session non trouvée (sid manquant)'})
        return
    session = sessions.get_by_sid(sid)
    if session is None:
        emit('error', {'detail': 'Session non trouvée'})
        return

    # optionally create a DB session (only if not already created for this socket-session)
    professor_id = None
    subject = 'mobile_stream'
    if isinstance(data, dict):
        professor_id = data.get('professor_id', None)
        subject = data.get('subject', subject)

    if session.get('db_session_id') is None:
        try:
            db_session_id = db.create_session(professor_id, subject)
            session['db_session_id'] = db_session_id
            logger.info(f"DB session created id={db_session_id} for socket session {session['session_id']}")
        except Exception:
            logger.exception('Failed to create DB session')

    sessions.set_detection(sid, True)
    logger.info(f"Detection started for session {session['session_id']}")
    emit('detection_started', {'session_id': session['session_id'], 'db_session_id': session.get('db_session_id')})


@socketio.on('stop_detection')
def handle_stop_detection(data=None):
    sid = getattr(request, 'sid', None)
    if sid is None:
        emit('error', {'detail': 'Session non trouvée (sid manquant)'})
        return
    session = sessions.get_by_sid(sid)
    if session is None:
        emit('error', {'detail': 'Session non trouvée'})
        return

    sessions.set_detection(sid, False)
    logger.info(f"Detection stopped for session {session['session_id']}")
    # Optionally end the DB session (if you want to mark end_time when stopping):
    db_session_id = session.get('db_session_id')
    if db_session_id:
        try:
            db.end_session(db_session_id)
            logger.info(f"DB session {db_session_id} ended")
        except Exception:
            logger.exception('Failed to end DB session')

    emit('detection_stopped', {'session_id': session['session_id']})


@socketio.on('frame')
def handle_frame(data):
    """Receive a base64-encoded frame and run detection if enabled for session.

    Expected payload: { 'image': '<base64 or dataURL>' }
    """
    sid = getattr(request, 'sid', None)
    if sid is None:
        emit('error', {'detail': 'Session non trouvée (sid manquant)'})
        return
    session = sessions.get_by_sid(sid)
    if session is None:
        emit('error', {'detail': 'Session non trouvée'})
        return

    session_id = session['session_id']

    image_b64 = None
    if isinstance(data, dict):
        # Accept either 'image' or 'image_base64' keys
        image_b64 = data.get('image') or data.get('image_base64')
    else:
        emit('error', {'detail': 'Payload attendu en objet JSON'})
        return

    if not image_b64:
        emit('error', {'detail': 'image (base64) manquante'})
        return

    # If detection is not enabled for this session, ignore the frame
    if not session.get('detection'):
        # Optional acknowledgement
        emit('detection_skipped', {'session_id': session_id})
        return

    # Decode base64 (handle data URLs)
    try:
        b64data = image_b64.split(',')[-1]
        img_bytes = base64.b64decode(b64data)
        nparr = np.frombuffer(img_bytes, dtype=np.uint8)
        frame = cv2.imdecode(nparr, cv2.IMREAD_COLOR)
    except Exception as e:
        logger.exception('Failed to decode image')
        emit('error', {'detail': 'Impossible de décoder l\'image', 'exception': str(e)})
        return

    if frame is None:
        emit('error', {'detail': 'Image decodee est None'})
        return

    # Call the detection function from main.py
    try:
        result = run_detection(frame)
    except Exception as e:
        logger.exception('run_detection raised an exception')
        emit('error', {'detail': 'Erreur lors de la détection', 'exception': str(e)})
        return

    # If detection returned faces with student_id and we have a DB session id, mark attendance
    attendance_records = []
    db_session_id = session.get('db_session_id')
    try:
        faces = result.get('faces') if isinstance(result, dict) else []
        if db_session_id and isinstance(faces, list):
            for f in faces:
                student_name = f.get('name', 'unknown')
                student_id = f.get('student_id')
                if student_id:
                    try:
                        status, message = db.mark_attendance_socketIO(db_session_id, student_id)
                        # Build the combined message as requested: message + " student name is : " + student_name
                        combined_message = f"{message} student name is : {student_name}"
                        # Log it on the server
                        logger.info(combined_message)
                        # Construct a notification payload and emit it to the client that sent the frame
                        attendance_payload = {
                            'session_id': session_id,
                            'db_session_id': db_session_id,
                            'student_id': student_id,
                            'student_name': student_name,
                            'marked': bool(status),
                            'message': combined_message,
                        }
                        # Emit immediate notification about attendance marking
                        emit('attendance_marked', attendance_payload)
                        # Also record for the final detection_result
                        attendance_records.append({
                            'student_id': student_id,
                            'student_name': student_name,
                            'marked': bool(status),
                            'message': combined_message,
                        })
                    except Exception:
                        logger.exception(f'Failed to mark attendance for student {student_id}')
                        attendance_records.append({'student_id': student_id, 'marked': False, 'error': 'db_error'})
    except Exception:
        logger.exception('Error while handling attendance marking')

    # Ensure result is serializable; attach session_id and attendance info
    payload = {
        'session_id': session_id,
        'db_session_id': db_session_id,
        'result': result,
        'attendance': attendance_records,
    }

    # Emit only to the sender
    emit('detection_result', payload)


# --- Health endpoint ---
@app.route('/health')
def health_check():
    return {'status': 'ok'}


if __name__ == '__main__':
    logger.info(f"Starting Socket.IO server on {HOST}:{PORT} (async_mode={async_mode})")
    # If eventlet is available, SocketIO will use it and provide websocket transport
    socketio.run(app, host=HOST, port=PORT)
