import sqlite3
from datetime import datetime
import pickle

class AttendanceDatabase:
    def __init__(self, db_name='attendance_system.db'):
        self.db_name = db_name
        self.init_database()
    
    def init_database(self):
        """Initialise la base de données avec les tables nécessaires"""
        conn = sqlite3.connect(self.db_name)
        c = conn.cursor()
        
        # Table des professeurs
        c.execute('''CREATE TABLE IF NOT EXISTS professors (
            id INTEGER PRIMARY KEY AUTOINCREMENT,
            first_name TEXT NOT NULL,
            last_name TEXT NOT NULL,
            subject TEXT NOT NULL,
            email TEXT NOT NULL UNIQUE,
            gender TEXT,
            created_at TIMESTAMP DEFAULT CURRENT_TIMESTAMP
        )''')
        
        # Table des étudiants
        c.execute('''CREATE TABLE IF NOT EXISTS students (
            id INTEGER PRIMARY KEY AUTOINCREMENT,
            first_name TEXT NOT NULL,
            last_name TEXT NOT NULL,
            email TEXT NOT NULL UNIQUE,
            photo_path TEXT,
            gender TEXT,
            encoding BLOB,
            created_at TIMESTAMP DEFAULT CURRENT_TIMESTAMP
        )''')
        
        # Table des séances
        c.execute('''CREATE TABLE IF NOT EXISTS sessions (
            id INTEGER PRIMARY KEY AUTOINCREMENT,
            professor_id INTEGER,
            subject TEXT,
            session_date DATE,
            start_time TIME,
            end_time TIME,
            FOREIGN KEY (professor_id) REFERENCES professors(id)
        )''')
        
        # Table des présences
        c.execute('''CREATE TABLE IF NOT EXISTS attendance (
            id INTEGER PRIMARY KEY AUTOINCREMENT,
            session_id INTEGER,
            student_id INTEGER,
            check_in_time TIMESTAMP,
            status TEXT DEFAULT 'present',
            FOREIGN KEY (session_id) REFERENCES sessions(id),
            FOREIGN KEY (student_id) REFERENCES students(id),
            UNIQUE(session_id, student_id)
        )''')
        
        # Assurer l'existence de la colonne email et d'un index UNIQUE (migration pour bases existantes)
        c.execute("PRAGMA table_info('professors')")
        cols = [row[1] for row in c.fetchall()]
        if 'email' not in cols:
            try:
                c.execute("ALTER TABLE professors ADD COLUMN email TEXT")
                conn.commit()
                print("→ Colonne 'email' ajoutée à la table professors (migration)")
            except Exception as e:
                print(f"⚠ Impossible d'ajouter la colonne 'email': {e}")
        # Créer un index UNIQUE si non présent (permet d'imposer l'unicité sur les valeurs non-null)
        try:
            c.execute("CREATE UNIQUE INDEX IF NOT EXISTS idx_professors_email ON professors(email)")
            conn.commit()
        except Exception as e:
            print(f"⚠ Impossible de créer l'index unique sur email: {e}")

        # --- Migration: assurer que students a bien une colonne email et un index unique ---
        c.execute("PRAGMA table_info('students')")
        student_cols = [row[1] for row in c.fetchall()]
        if 'email' not in student_cols:
            try:
                c.execute("ALTER TABLE students ADD COLUMN email TEXT")
                conn.commit()
                print("→ Colonne 'email' ajoutée à la table students (migration)")
            except Exception as e:
                print(f"⚠ Impossible d'ajouter la colonne 'email' à students: {e}")
        try:
            c.execute("CREATE UNIQUE INDEX IF NOT EXISTS idx_students_email ON students(email)")
            conn.commit()
        except Exception as e:
            print(f"⚠ Impossible de créer l'index unique sur students.email: {e}")

        conn.close()
        print("✓ Base de données initialisée avec succès")
    
    # === GESTION PROFESSEURS ===
    def add_professor(self, first_name, last_name, subject, email):
        """Ajoute un professeur"""
        conn = sqlite3.connect(self.db_name)
        c = conn.cursor()
        try:
            c.execute('''INSERT INTO professors (first_name, last_name, subject, email)
                        VALUES (?, ?, ?, ?)''', (first_name, last_name, subject, email))
            conn.commit()
            professor_id = c.lastrowid
            print(f"✓ Professeur {first_name} {last_name} ajouté avec ID: {professor_id}")
            return professor_id
        except sqlite3.IntegrityError as ie:
            # Erreur d'unicité (email déjà existant)
            print(f"✗ Intégrité DB lors de l'ajout du professeur (possible email dupliqué): {ie}")
            return None
        except Exception as e:
            print(f"✗ Erreur lors de l'ajout du professeur: {e}")
            return None
        finally:
            conn.close()
    
    def get_all_professors(self):
        """Récupère tous les professeurs"""
        conn = sqlite3.connect(self.db_name)
        c = conn.cursor()
        c.execute('SELECT * FROM professors ORDER BY last_name')
        professors = c.fetchall()
        conn.close()
        return professors

    def get_professor_by_email(self, email):
        """Récupère un professeur par email (ou None)"""
        conn = sqlite3.connect(self.db_name)
        c = conn.cursor()
        c.execute('SELECT * FROM professors WHERE email = ? LIMIT 1', (email,))
        prof = c.fetchone()
        conn.close()
        return prof

    # === GESTION ÉTUDIANTS ===
    def add_student(self, first_name, last_name, email, photo_path=None, encoding=None, gender=None):
        """Ajoute un étudiant. Email est requis et doit être unique."""
        conn = sqlite3.connect(self.db_name)
        c = conn.cursor()
        try:
            # Convertir l'encoding en bytes si fourni
            encoding_blob = pickle.dumps(encoding) if encoding is not None else None

            # Spécifier explicitement les colonnes pour être compatible avec les migrations
            c.execute('''INSERT INTO students (first_name, last_name, email, photo_path, gender, encoding)
                        VALUES (?, ?, ?, ?, ?, ?)''',
                     (first_name, last_name, email, photo_path, gender, encoding_blob))
            conn.commit()
            student_id = c.lastrowid
            print(f"✓ Étudiant {first_name} {last_name} ajouté avec ID: {student_id}")
            return student_id
        except sqlite3.IntegrityError as ie:
            # Erreur d'unicité (email déjà existant)
            print(f"✗ Intégrité DB lors de l'ajout de l'étudiant (possible email dupliqué): {ie}")
            return None
        except Exception as e:
            print(f"✗ Erreur lors de l'ajout de l'étudiant: {e}")
            return None
        finally:
            conn.close()

    def get_student_by_email(self, email):
        """Récupère un étudiant par email (ou None)"""
        conn = sqlite3.connect(self.db_name)
        c = conn.cursor()
        c.execute('SELECT * FROM students WHERE email = ? LIMIT 1', (email,))
        student = c.fetchone()
        conn.close()
        return student

    def get_student_by_id(self, student_id):
        """Récupère un étudiant par id (ou None)"""
        conn = sqlite3.connect(self.db_name)
        c = conn.cursor()
        c.execute('SELECT * FROM students WHERE id = ? LIMIT 1', (student_id,))
        student = c.fetchone()
        conn.close()
        return student

    def remove_student(self, student_id):
        """Supprime un étudiant par id.
        Retourne (True, photo_path) si supprimé, (False, None) si inexistant.
        La suppression ne touche que la base; la suppression du fichier photo peut être faite par l'API.
        """
        conn = sqlite3.connect(self.db_name)
        c = conn.cursor()
        c.execute('SELECT photo_path FROM students WHERE id = ?', (student_id,))
        row = c.fetchone()
        if not row:
            conn.close()
            return False, None
        photo_path = row[0]
        try:
            # Supprimer d'abord les présences liées pour éviter les références orphelines
            try:
                c.execute('DELETE FROM attendance WHERE student_id = ?', (student_id,))
            except Exception:
                pass
            c.execute('DELETE FROM students WHERE id = ?', (student_id,))
            conn.commit()
            return True, photo_path
        except Exception as e:
            print(f"✗ Erreur lors de la suppression de l'étudiant: {e}")
            return False, photo_path
        finally:
            conn.close()

    def get_all_students(self):
        """Récupère tous les étudiants"""
        conn = sqlite3.connect(self.db_name)
        c = conn.cursor()
        c.execute('SELECT id, first_name, last_name, photo_path FROM students ORDER BY last_name')
        students = c.fetchall()
        conn.close()
        return students
    
    def get_student_encodings(self):
        """Récupère tous les encodages des étudiants"""
        conn = sqlite3.connect(self.db_name)
        c = conn.cursor()
        c.execute('SELECT id, first_name, last_name, encoding FROM students WHERE encoding IS NOT NULL')
        results = c.fetchall()
        conn.close()
        
        encodings = []
        students_info = []
        
        for student_id, first_name, last_name, encoding_blob in results:
            if encoding_blob:
                encoding = pickle.loads(encoding_blob)
                encodings.append(encoding)
                students_info.append({
                    'id': student_id,
                    'name': f"{first_name} {last_name}",
                    'first_name': first_name,
                    'last_name': last_name
                })
        
        return encodings, students_info
    
    # === GESTION SÉANCES ===
    def create_session(self, professor_id, subject, session_date=None):
        """Crée une nouvelle séance"""
        if session_date is None:
            session_date = datetime.now().strftime('%Y-%m-%d')
        
        start_time = datetime.now().strftime('%H:%M:%S')
        
        conn = sqlite3.connect(self.db_name)
        c = conn.cursor()
        try:
            c.execute('''INSERT INTO sessions (professor_id, subject, session_date, start_time)
                        VALUES (?, ?, ?, ?)''', 
                     (professor_id, subject, session_date, start_time))
            conn.commit()
            session_id = c.lastrowid
            print(f"✓ Séance créée avec ID: {session_id}")
            return session_id
        except Exception as e:
            print(f"✗ Erreur lors de la création de la séance: {e}")
            return None
        finally:
            conn.close()
    
    def end_session(self, session_id):
        """Termine une séance"""
        end_time = datetime.now().strftime('%H:%M:%S')
        
        conn = sqlite3.connect(self.db_name)
        c = conn.cursor()
        try:
            c.execute('UPDATE sessions SET end_time = ? WHERE id = ?', 
                     (end_time, session_id))
            conn.commit()
            print(f"✓ Séance {session_id} terminée à {end_time}")
        except Exception as e:
            print(f"✗ Erreur lors de la fin de la séance: {e}")
        finally:
            conn.close()
    
    # === GESTION PRÉSENCES ===
    def mark_attendance(self, session_id, student_id):
        """Marque la présence d'un étudiant"""
        check_in_time = datetime.now().strftime('%Y-%m-%d %H:%M:%S')
        
        conn = sqlite3.connect(self.db_name)
        c = conn.cursor()
        try:
            c.execute('''INSERT OR IGNORE INTO attendance (session_id, student_id, check_in_time)
                        VALUES (?, ?, ?)''', 
                     (session_id, student_id, check_in_time))
            conn.commit()
            
            if c.rowcount > 0:
                print(f"✓ Présence marquée pour l'étudiant ID: {student_id}")
                return True
            else:
                print(f"⚠ Présence déjà marquée pour l'étudiant ID: {student_id}")
                return False
        except Exception as e:
            print(f"✗ Erreur lors du marquage de présence: {e}")
            return False
        finally:
            conn.close()

    def mark_attendance_socketIO(self, session_id, student_id, null=None):
        """Marque la présence d'un étudiant"""
        check_in_time = datetime.now().strftime('%Y-%m-%d %H:%M:%S')

        conn = sqlite3.connect(self.db_name)
        c = conn.cursor()
        try:
            c.execute('''INSERT OR IGNORE INTO attendance (session_id, student_id, check_in_time)
                        VALUES (?, ?, ?)''',
                      (session_id, student_id, check_in_time))
            conn.commit()

            if c.rowcount > 0:
                return (True, "Présence marquée pour l'étudiant ID: " + str(student_id))
            else:
                return (False, "Présence déjà marquée pour l'étudiant ID : " + str(student_id))
        except Exception as e:
            print(f"✗ Erreur lors du marquage de présence: {e}")
            return (False, null)
        finally:
            conn.close()

    def export_attendance_to_csv(self, session_id, filename='attendance_report.csv'):
        """Export les présences d'une séance en CSV"""
        conn = sqlite3.connect(self.db_name)
        c = conn.cursor()
        
        c.execute('''
            SELECT 
                s.first_name || ' ' || s.last_name as student_name,
                a.check_in_time,
                a.status
            FROM attendance a
            JOIN students s ON a.student_id = s.id
            WHERE a.session_id = ?
            ORDER BY a.check_in_time
        ''', (session_id,))
        
        results = c.fetchall()
        conn.close()
        
        with open(filename, 'w', encoding='utf-8') as f:
            f.write('Nom Complet,Heure d\'arrivée,Statut\n')
            for row in results:
                f.write(f'{row[0]},{row[1]},{row[2]}\n')
        
        print(f"✓ Rapport exporté vers {filename}")
        return filename
    
    def get_session_stats(self, session_id):
        """Obtient les statistiques d'une séance"""
        conn = sqlite3.connect(self.db_name)
        c = conn.cursor()
        
        # Total étudiants
        c.execute('SELECT COUNT(*) FROM students')
        total_students = c.fetchone()[0]
        
        # Présents
        c.execute('SELECT COUNT(*) FROM attendance WHERE session_id = ?', (session_id,))
        present_count = c.fetchone()[0]
        
        conn.close()
        
        return {
            'total': total_students,
            'present': present_count,
            'absent': total_students - present_count,
            'percentage': (present_count / total_students * 100) if total_students > 0 else 0
        }