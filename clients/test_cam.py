# run with "python clients/test_cam.py --url http://127.0.0.1:5000 --camera 0 --fps 1 --professor-id 1"
import argparse
import base64
import time
import signal
import sys

import cv2
import socketio


def parse_args():
    p = argparse.ArgumentParser(description='Test camera -> send frames to Socket.IO server')
    p.add_argument('--url', default='http://127.0.0.1:5000', help='Server URL (http://host:port)')
    p.add_argument('--camera', type=int, default=0, help='Camera index for OpenCV')
    p.add_argument('--fps', type=float, default=1.0, help='Frames per second to send')
    p.add_argument('--professor-id', type=int, default=None, help='Optional professor_id to create the DB session on server')
    return p.parse_args()


class TestCamSender:
    def __init__(self, url, camera_index=0, fps=1.0, professor_id=None):
        self.url = url
        self.camera_index = camera_index
        self.fps = fps
        self.professor_id = professor_id
        # enable reconnection attempts to be robust
        self.sio = socketio.Client(reconnection=True, reconnection_attempts=5)
        self.cap = None
        self.running = False
        self.connected = False
        self.session_id = None

        @self.sio.event
        def connect():
            print('[socket] connected')
            self.connected = True

        @self.sio.on('session_created')
        def on_session_created(data):
            print('[socket] session_created', data)
            try:
                self.session_id = data.get('session_id') if isinstance(data, dict) else None
            except Exception:
                self.session_id = None

        @self.sio.on('detection_result')
        def on_detection_result(payload):
            print('')
            #print('[socket] detection_result', payload)

        @self.sio.on('attendance_marked')
        def on_attendance_marked(payload):
            # Payload: { session_id, db_session_id, student_id, student_name, marked, message }
            try:
                msg = payload.get('message') if isinstance(payload, dict) else str(payload)
            except Exception:
                msg = str(payload)
            print('[socket] attendance_marked:', msg)

        @self.sio.event
        def disconnect():
            print('[socket] disconnected')
            self.connected = False

        @self.sio.on('error')
        def on_error(err):
            print('[socket] error', err)

    def start(self):
        print(f'[client] connecting to {self.url} ...')
        try:
            # prefer websocket transport
            self.sio.connect(self.url, transports=['websocket'])
        except Exception as e:
            print('[client] websocket connection failed:', e)
            print("[client] Attempting fallback (polling transport). To enable websocket install: pip install websocket-client")
            try:
                self.sio.connect(self.url)
            except Exception as e2:
                print('[client] fallback connection failed:', e2)
                return

        # wait for connection/session to be established
        wait_until = time.time() + 5.0
        while not self.connected and time.time() < wait_until:
            time.sleep(0.05)

        if not self.connected:
            print('[client] connection not established after timeout')
            try:
                self.sio.disconnect()
            except Exception:
                pass
            return

        # open camera
        self.cap = cv2.VideoCapture(self.camera_index)
        if not self.cap.isOpened():
            print('[camera] Impossible d\'ouvrir la caméra index', self.camera_index)
            self.sio.disconnect()
            return

        # start detection on server (send session_id if known)
        try:
            payload = {}
            if self.session_id:
                payload['session_id'] = self.session_id
            if self.professor_id is not None:
                payload['professor_id'] = self.professor_id

            if payload:
                self.sio.emit('start_detection', payload)
            else:
                self.sio.emit('start_detection')
        except Exception as e:
            print('[client] start_detection emit failed:', e)

        self.running = True
        interval = 1.0 / max(0.0001, self.fps)
        print(f'[camera] Envoi des frames ~{self.fps} FPS (intervalle {interval:.3f}s)')

        try:
            while self.running:
                t0 = time.time()
                ret, frame = self.cap.read()
                if not ret:
                    print('[camera] lecture frame echouee')
                    time.sleep(0.5)
                    continue

                # encode JPEG
                ok, jpeg = cv2.imencode('.jpg', frame, [int(cv2.IMWRITE_JPEG_QUALITY), 70])
                if not ok:
                    print('[camera] jpeg encode failed')
                    continue

                b64 = base64.b64encode(jpeg.tobytes()).decode('ascii')
                data_url = f'data:image/jpeg;base64,{b64}'

                # emit frame only if connected
                if not self.sio.connected:
                    print('[socket] not connected, skipping emit')
                else:
                    try:
                        self.sio.emit('frame', {'image': data_url})
                    except Exception as e:
                        print('[socket] emit frame failed', e)

                # throttle
                elapsed = time.time() - t0
                to_sleep = interval - elapsed
                if to_sleep > 0:
                    time.sleep(to_sleep)
        except KeyboardInterrupt:
            print('\n[client] KeyboardInterrupt')
            self.stop()
        finally:
            self.stop()

    def stop(self):
        # attempt to stop gracefully
        if self.running:
            self.running = False
            try:
                if self.sio.connected:
                    self.sio.emit('stop_detection')
            except Exception:
                pass

        # ensure resources released
        try:
            if self.cap and self.cap.isOpened():
                self.cap.release()
        except Exception:
            pass
        try:
            if self.sio.connected:
                self.sio.disconnect()
        except Exception:
            pass
        print('[client] stopped')


if __name__ == '__main__':
    args = parse_args()
    sender = TestCamSender(url=args.url, camera_index=args.camera, fps=args.fps, professor_id=args.professor_id)

    # handle SIGINT gracefully
    def _sigint_handler(sig, frame):
        print('\n[client] SIGINT received, stopping...')
        sender.stop()
        sys.exit(0)

    signal.signal(signal.SIGINT, _sigint_handler)

    sender.start()
