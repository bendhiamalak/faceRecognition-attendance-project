"""
API REST pour le Système de Gestion de Présence par Reconnaissance Faciale
Endpoints pour application mobile - FastAPI
"""

from fastapi import FastAPI, HTTPException, Request
from fastapi.middleware.cors import CORSMiddleware
from pydantic import BaseModel
from database import AttendanceDatabase
from face_detector import FaceDetector
import face_recognition
import numpy as np
import base64
import cv2
from datetime import datetime
import os
import sqlite3
from fastapi.staticfiles import StaticFiles

from fastapi.responses import FileResponse
import mimetypes

# ==================== INITIALISATION ====================
app = FastAPI(title="Attendance System API - FastAPI")
base_dir = os.path.dirname(__file__)
photos_dir = os.path.join(base_dir, "students_photos")
os.makedirs(photos_dir, exist_ok=True)

app.mount("/students_photos", StaticFiles(directory=photos_dir), name="students_photos")
# Autoriser CORS
app.add_middleware(
    CORSMiddleware,
    allow_origins=["*"],
    allow_origin_regex=".*",
    allow_credentials=True,
    allow_methods=["*"],
    allow_headers=["*"],
)

# Initialisation DB et FaceDetector
db = AttendanceDatabase()
detector = FaceDetector(tolerance=0.5)


# ==================== MODELS ====================

class ProfessorCreate(BaseModel):
    first_name: str
    last_name: str
    subject: str
    email: str

class StudentCreate(BaseModel):
    first_name: str
    last_name: str
    email: str
    gender: str = 'M'
    photo_base64: str = None

class SessionCreate(BaseModel):
    professor_id: int
    subject: str
    session_date: str = None

class MarkAttendance(BaseModel):
    session_id: int
    student_id: int

class DetectAttendance(BaseModel):
    session_id: int
    image_base64: str


# ==================== ENDPOINTS PROFESSEURS ====================

@app.post("/api/professors")
async def create_professor(prof: ProfessorCreate):
    if not all([prof.first_name, prof.last_name, prof.subject, prof.email]):
        raise HTTPException(status_code=400, detail="Tous les champs sont obligatoires")

    # Vérifier si l'email existe déjà
    existing = db.get_professor_by_email(prof.email)
    if existing:
        raise HTTPException(status_code=400, detail="Un professeur avec cet email existe déjà")

    professor_id = db.add_professor(prof.first_name, prof.last_name, prof.subject, prof.email)
    if not professor_id:
        raise HTTPException(status_code=500, detail="Erreur lors de la création du professeur")
    return {
        "success": True,
        "message": "Professeur créé avec succès",
        "data": {
            "professor_id": professor_id,
            "first_name": prof.first_name,
            "last_name": prof.last_name,
            "subject": prof.subject,
            "email": prof.email
        }
    }

@app.get("/api/professors")
async def get_professors():
    professors = db.get_all_professors()
    professors_list = [{
        "id": p[0],
        "first_name": p[1],
        "last_name": p[2],
        "subject": p[3],
        "email": p[4],
        "created_at": p[5]
    } for p in professors]
    return {"success": True, "data": professors_list, "count": len(professors_list)}

@app.get("/api/professors/{professor_id}")
async def get_professor(professor_id: int):
    professors = db.get_all_professors()
    professor = next((p for p in professors if p[0] == professor_id), None)
    if not professor:
        raise HTTPException(status_code=404, detail="Professeur introuvable")
    return {
        "success": True,
        "data": {
            "id": professor[0],
            "first_name": professor[1],
            "last_name": professor[2],
            "subject": professor[3],
            "email": professor[4],
            "created_at": professor[5]
        }
    }


# ==================== ENDPOINTS ÉTUDIANTS ====================

@app.post("/api/students")
async def create_student(student: StudentCreate):
    print("oyyyyyyyyyy")
    print(student)
    if not all([student.first_name, student.last_name, student.email]):
        raise HTTPException(status_code=400, detail="Le prénom, le nom et l'email sont obligatoires")

    # Vérifier unicité email
    existing = db.get_student_by_email(student.email)
    if existing:
        raise HTTPException(status_code=400, detail="Un étudiant avec cet email existe déjà")

    photo_path = None
    encoding = None
    print(student)

    if student.photo_base64:
        try:
            img_data = base64.b64decode(student.photo_base64.split(",")[-1])
            nparr = np.frombuffer(img_data, np.uint8)
            img = cv2.imdecode(nparr, cv2.IMREAD_COLOR)

            save_path = 'students_photos'
            os.makedirs(save_path, exist_ok=True)

            timestamp = datetime.now().strftime("%Y%m%d_%H%M%S")
            filename = f"{student.first_name}_{student.last_name}_{timestamp}.jpg"
            photo_path = os.path.join(save_path, filename)
            cv2.imwrite(photo_path, img)

            rgb_img = cv2.cvtColor(img, cv2.COLOR_BGR2RGB)
            face_locations = face_recognition.face_locations(rgb_img)
            if len(face_locations) == 1:
                encodings = face_recognition.face_encodings(rgb_img, face_locations)
                if encodings:
                    encoding = encodings[0]
            elif len(face_locations) == 0:
                raise HTTPException(status_code=400, detail="Aucun visage détecté")
            else:
                raise HTTPException(status_code=400, detail="Plusieurs visages détectés")
        except Exception as e:
            raise HTTPException(status_code=400, detail=f"Erreur traitement photo: {str(e)}")

    student_id = db.add_student(student.first_name, student.last_name, student.email, photo_path, encoding, student.gender)

    if student_id:
        # Assurer que le champ gender est mis (même si la DB a déjà la colonne)
        try:
            conn = sqlite3.connect(db.db_name)
            c = conn.cursor()
            c.execute('UPDATE students SET gender=? WHERE id=?', (student.gender, student_id))
            conn.commit()
            conn.close()
        except Exception:
            pass

        detector.load_encodings_from_database(db)

        return {
            "success": True,
            "message": "Étudiant créé avec succès",
            "data": {
                "student_id": student_id,
                "first_name": student.first_name,
                "last_name": student.last_name,
                "gender": student.gender,
                "photo_path": photo_path,
                "has_encoding": encoding is not None,
                "email": student.email
            }
        }
    raise HTTPException(status_code=500, detail="Erreur création étudiant")

@app.get("/api/students")
async def get_students():
    print("hehehheheh")
    conn = sqlite3.connect(db.db_name)
    c = conn.cursor()
    c.execute('SELECT id, first_name, last_name, photo_path, gender FROM students ORDER BY last_name')
    students = c.fetchall()
    conn.close()
    return {
        "success": True,
        "data": [{"id": s[0], "first_name": s[1], "last_name": s[2], "photo_path": s[3], "gender": s[4] if len(s) > 4 else 'M'} for s in students],
        "count": len(students)
    }

@app.get("/api/students/{student_id}")
async def get_student(student_id: int, request: Request):
    conn = sqlite3.connect(db.db_name)
    c = conn.cursor()
    c.execute('SELECT id, first_name, last_name, photo_path, gender FROM students WHERE id=?', (student_id,))
    student = c.fetchone()
    if not student:
        raise HTTPException(status_code=404, detail="Étudiant introuvable")
    c.execute('''
        SELECT COUNT(*) as total_sessions,
               SUM(CASE WHEN a.student_id IS NOT NULL THEN 1 ELSE 0 END) as attended
        FROM sessions s
        LEFT JOIN attendance a ON s.id = a.session_id AND a.student_id = ?
    ''', (student_id,))
    stats = c.fetchone()
    conn.close()
    total_sessions = stats[0] if stats[0] else 0
    attended = stats[1] if stats[1] else 0
    absence_rate = ((total_sessions - attended) / total_sessions * 100) if total_sessions > 0 else 0

    # Construire les URLs utiles pour le front
    photo_path = student[4]
    photo_url = None
    photo_endpoint = f"{str(request.base_url).rstrip('/')}/api/students/{student_id}/photo"

    # Si le chemin stocké est dans le dossier public 'students_photos', construire l'URL publique
    if photo_path:
        # normaliser les séparateurs
        normalized = photo_path.replace('\\', '/')
        if normalized.startswith('students_photos/'):
            filename = normalized.split('/', 1)[1]
            photo_url = f"{str(request.base_url).rstrip('/')}/students_photos/{filename}"
        elif normalized.startswith('./students_photos/'):
            filename = normalized.split('/', 2)[2]
            photo_url = f"{str(request.base_url).rstrip('/')}/students_photos/{filename}"

    return {
        "success": True,
        "data": {
            "id": student[0],
            "first_name": student[1],
            "last_name": student[2],
            "email": student[3],
            "photo_path": photo_path,
            "photo_endpoint": photo_endpoint,
            "gender": student[5] if len(student) > 4 else 'M',
            "statistics": {
                "total_sessions": total_sessions,
                "attended": attended,
                "absent": total_sessions - attended,
                "attendance_rate": round(100 - absence_rate, 2),
                "absence_rate": round(absence_rate, 2)
            }
        }
    }

@app.get("/api/students/{student_id}/photo")
async def get_student_photo(student_id: int):
    """Retourne la photo d'un étudiant (FileResponse)"""
    conn = sqlite3.connect(db.db_name)
    c = conn.cursor()
    c.execute('SELECT photo_path FROM students WHERE id=?', (student_id,))
    row = c.fetchone()
    conn.close()
    if not row or not row[0]:
        raise HTTPException(status_code=404, detail="Photo introuvable pour cet étudiant")
    photo_path = row[0]

    # Support des chemins relatifs stockés comme 'students_photos/xxx.jpg'
    if not os.path.isabs(photo_path):
        abs_path = os.path.join(base_dir, photo_path)
    else:
        abs_path = photo_path

    if not os.path.exists(abs_path):
        raise HTTPException(status_code=404, detail="Fichier photo introuvable sur le serveur")

    # Détecter le content-type
    mime_type, _ = mimetypes.guess_type(abs_path)
    return FileResponse(abs_path, media_type=mime_type or 'image/jpeg')
@app.get("/api/students/email/{email}")
async def get_student_by_email(email: str, request: Request):
    conn = sqlite3.connect(db.db_name)
    c = conn.cursor()
    # Recherche insensible à la casse
    c.execute('SELECT id, first_name, last_name,email, photo_path, gender FROM students WHERE LOWER(email)=LOWER(?)', (email,))
    student = c.fetchone()
    print(student)
    if not student:
        conn.close()
        raise HTTPException(status_code=404, detail="Étudiant introuvable")

    c.execute('''
        SELECT COUNT(*) as total_sessions,
               SUM(CASE WHEN a.student_id IS NOT NULL THEN 1 ELSE 0 END) as attended
        FROM sessions s
        LEFT JOIN attendance a ON s.id = a.session_id AND a.student_id = ?
    ''', (student[0],))
    stats = c.fetchone()
    conn.close()

    total_sessions = stats[0] if stats and stats[0] else 0
    attended = stats[1] if stats and stats[1] else 0
    absence_rate = ((total_sessions - attended) / total_sessions * 100) if total_sessions > 0 else 0

    photo_path = student[4]
    photo_url = None
    photo_endpoint = f"{str(request.base_url).rstrip('/')}/api/students/{student[0]}/photo"

    if photo_path:
        normalized = photo_path.replace('\\', '/')
        if normalized.startswith('students_photos/'):
            filename = normalized.split('/', 1)[1]
            photo_url = f"{str(request.base_url).rstrip('/')}/students_photos/{filename}"
        elif normalized.startswith('./students_photos/'):
            filename = normalized.split('/', 2)[2]
            photo_url = f"{str(request.base_url).rstrip('/')}/students_photos/{filename}"

    return {
        "success": True,
        "data": {
            "id": student[0],
            "first_name": student[1],
            "last_name": student[2],
            "email": student[3],
            "photo_path": photo_path,
            "photo_endpoint": photo_endpoint,
            "gender": student[5] if len(student) > 4 else 'M',
            "statistics": {
                "total_sessions": total_sessions,
                "attended": attended,
                "absent": total_sessions - attended,
                "attendance_rate": round(100 - absence_rate, 2),
                "absence_rate": round(absence_rate, 2)
            }
        }
    }

@app.delete("/api/students/{student_id}")
async def delete_student(student_id: int):
    """Supprime un étudiant de la base et le fichier photo associé si présent."""
    # Supprimer de la DB (retourne photo_path si existait)
    deleted, photo_path = db.remove_student(student_id)
    if not deleted:
        raise HTTPException(status_code=404, detail="Étudiant introuvable")

    photo_deleted = False
    if photo_path:
        # Construire le chemin absolu
        if not os.path.isabs(photo_path):
            abs_path = os.path.join(base_dir, photo_path)
        else:
            abs_path = photo_path
        try:
            if os.path.exists(abs_path):
                os.remove(abs_path)
                photo_deleted = True
        except Exception as e:
            # Ne pas échouer la suppression DB si la suppression fichier plante; loguer
            print(f"⚠ Impossible de supprimer le fichier photo '{abs_path}': {e}")

    # Recharger les encodages connus
    try:
        detector.load_encodings_from_database(db)
    except Exception:
        pass

    return {
        "success": True,
        "message": "Étudiant supprimé avec succès",
        "data": {
            "student_id": student_id,
            "photo_path": photo_path,
            "photo_deleted": photo_deleted
        }
    }


# ==================== ENDPOINTS SÉANCES ====================

@app.post("/api/sessions")
async def create_session(session: SessionCreate):
    if not all([session.professor_id, session.subject]):
        raise HTTPException(status_code=400, detail="professor_id et subject obligatoires")
    session_id = db.create_session(session.professor_id, session.subject, session.session_date)
    if not session_id:
        raise HTTPException(status_code=500, detail="Erreur création séance")
    detector.load_encodings_from_database(db)
    return {
        "success": True,
        "message": "Séance créée avec succès",
        "data": {
            "session_id": session_id,
            "professor_id": session.professor_id,
            "subject": session.subject,
            "session_date": session.session_date or datetime.now().strftime("%Y-%m-%d"),
            "students_registered": len(detector.known_encodings)
        }
    }

@app.put("/api/sessions/{session_id}/end")
async def end_session(session_id: int):
    db.end_session(session_id)
    stats = db.get_session_stats(session_id)
    return {
        "success": True,
        "message": "Séance terminée avec succès",
        "data": {
            "session_id": session_id,
            "end_time": datetime.now().strftime("%H:%M:%S"),
            "statistics": {
                "total_students": stats['total'],
                "present": stats['present'],
                "absent": stats['absent'],
                "attendance_rate": round(stats['percentage'], 2)
            }
        }
    }

@app.get("/api/sessions")
async def get_all_sessions():
    conn = sqlite3.connect(db.db_name)
    c = conn.cursor()
    c.execute('''
        SELECT s.id, s.professor_id, p.first_name, p.last_name, 
               s.subject, s.session_date, s.start_time, s.end_time
        FROM sessions s
        LEFT JOIN professors p ON s.professor_id = p.id
        ORDER BY s.session_date DESC, s.start_time DESC
    ''')
    sessions = c.fetchall()
    conn.close()
    return {
        "success": True,
        "data": [
            {
                "session_id": s[0],
                "professor_id": s[1],
                "professor_name": f"{s[2]} {s[3]}" if s[2] else "N/A",
                "subject": s[4],
                "date": s[5],
                "start_time": s[6],
                "end_time": s[7],
                "status": "terminée" if s[7] else "en cours"
            } for s in sessions
        ],
        "count": len(sessions)
    }


# ==================== ENDPOINTS PRÉSENCES ====================

@app.post("/api/attendance/mark")
async def mark_attendance(data: MarkAttendance):
    if not all([data.session_id, data.student_id]):
        raise HTTPException(status_code=400, detail="session_id et student_id obligatoires")
    success = db.mark_attendance(data.session_id, data.student_id)
    if not success:
        raise HTTPException(status_code=400, detail="Présence déjà marquée")
    return {
        "success": True,
        "message": "Présence marquée avec succès",
        "data": {
            "session_id": data.session_id,
            "student_id": data.student_id,
            "timestamp": datetime.now().strftime("%Y-%m-%d %H:%M:%S")
        }
    }

@app.post("/api/attendance/detect")
async def detect_and_mark_attendance(data: DetectAttendance):
    if not all([data.session_id, data.image_base64]):
        raise HTTPException(status_code=400, detail="session_id et image_base64 obligatoires")
    
    detector.load_encodings_from_database(db)
    if len(detector.known_encodings) == 0:
        raise HTTPException(status_code=400, detail="Aucun encodage étudiant disponible")
    
    try:
        img_data = base64.b64decode(data.image_base64.split(",")[-1])
        nparr = np.frombuffer(img_data, np.uint8)
        frame = cv2.imdecode(nparr, cv2.IMREAD_COLOR)
    except Exception as e:
        raise HTTPException(status_code=400, detail=f"Erreur décodage image: {str(e)}")

    detected_faces = detector.detect_faces_in_frame(frame)
    marked_students = []
    for face_data in detected_faces:
        student = face_data['student']
        student_id = student['id']
        confidence = face_data['confidence']
        success = db.mark_attendance(data.session_id, student_id)
        marked_students.append({
            "student_id": student_id,
            "name": student['name'],
            "confidence": round(confidence, 2),
            "marked": success,
            "already_present": not success
        })
    stats = db.get_session_stats(data.session_id)
    return {
        "success": True,
        "message": f"{len(marked_students)} visage(s) détecté(s)",
        "data": {
            "session_id": data.session_id,
            "detected_count": len(detected_faces),
            "students": marked_students,
            "session_stats": {
                "present": stats['present'],
                "total": stats['total'],
                "attendance_rate": round(stats['percentage'], 2)
            }
        }
    }


# ==================== STATISTIQUES AVANCÉES ====================

@app.get("/api/statistics/semester")
async def get_semester_statistics(start_date: str = None, end_date: str = None, absence_threshold: float = 20.0):
    conn = sqlite3.connect(db.db_name)
    c = conn.cursor()

    date_filter = ""
    params = []
    if start_date and end_date:
        date_filter = "WHERE s.session_date BETWEEN ? AND ?"
        params = [start_date, end_date]

    c.execute(f"SELECT COUNT(*) FROM sessions s {date_filter}", params)
    total_sessions = c.fetchone()[0]

    c.execute(f'''
        SELECT st.id, st.first_name, st.last_name,
            COUNT(a.session_id) as attended,
            (SELECT COUNT(*) FROM sessions) as total_sessions
        FROM students st
        LEFT JOIN attendance a ON st.id = a.student_id
        GROUP BY st.id
    ''')
    students_stats = []
    for row in c.fetchall():
        student_id, first_name, last_name, attended, total = row
        attendance_rate = (attended / total * 100) if total else 0
        if 100 - attendance_rate > absence_threshold:
            students_stats.append({
                "student_id": student_id,
                "name": f"{first_name} {last_name}",
                "attended": attended,
                "total_sessions": total,
                "attendance_rate": round(attendance_rate, 2),
                "absent_rate": round(100 - attendance_rate, 2)
            })

    conn.close()
    return {
        "success": True,
        "data": {
            "total_sessions": total_sessions,
            "students_with_high_absence": students_stats,
            "absence_threshold": absence_threshold
        }
    }
