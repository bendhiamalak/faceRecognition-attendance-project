import cv2
import face_recognition
import numpy as np
import os
from datetime import datetime

class FaceDetector:
    def __init__(self, tolerance=0.5):
        """
        Initialise le détecteur de visages
        tolerance: seuil de distance pour accepter une correspondance (0.6 par défaut)
        """
        self.tolerance = tolerance
        self.known_encodings = []
        self.known_students = []
        self.marked_students = set()  # Pour éviter les doublons dans une session
    
    def load_encodings_from_database(self, database):
        """Charge les encodages depuis la base de données"""
        self.known_encodings, self.known_students = database.get_student_encodings()
        print(f"✓ {len(self.known_encodings)} encodages chargés depuis la base de données")
    
    def capture_and_encode_face(self, student_name, save_path='students_photos'):
        """
        Capture une photo d'un étudiant via webcam et génère son encoding
        Retourne: (photo_path, encoding) ou (None, None) si échec
        """
        # Créer le dossier s'il n'existe pas
        if not os.path.exists(save_path):
            os.makedirs(save_path)
        
        cap = cv2.VideoCapture(0)
        
        if not cap.isOpened():
            print("✗ Impossible d'ouvrir la webcam")
            return None, None
        
        print("\n📸 Positionnez-vous devant la caméra")
        print("Appuyez sur ESPACE pour capturer ou ESC pour annuler")
        
        captured = False
        frame = None
        
        while True:
            success, frame = cap.read()
            if not success:
                break
            
            # Détecter les visages pour guider l'utilisateur
            rgb_frame = cv2.cvtColor(frame, cv2.COLOR_BGR2RGB)
            face_locations = face_recognition.face_locations(rgb_frame)
            
            # Dessiner un rectangle autour des visages détectés
            for (top, right, bottom, left) in face_locations:
                cv2.rectangle(frame, (left, top), (right, bottom), (0, 255, 0), 2)
                cv2.putText(frame, "Visage detecte", (left, top-10), 
                           cv2.FONT_HERSHEY_SIMPLEX, 0.5, (0, 255, 0), 2)
            
            # Afficher les instructions
            cv2.putText(frame, "ESPACE = Capturer | ESC = Annuler", (10, 30),
                       cv2.FONT_HERSHEY_SIMPLEX, 0.7, (255, 255, 255), 2)
            
            cv2.imshow('Capture Photo', frame)
            
            key = cv2.waitKey(1) & 0xFF
            
            if key == 32:  # ESPACE
                if len(face_locations) == 1:
                    captured = True
                    print("✓ Photo capturée!")
                    break
                elif len(face_locations) == 0:
                    print("✗ Aucun visage détecté. Réessayez.")
                else:
                    print("✗ Plusieurs visages détectés. Un seul visage autorisé.")
            
            elif key == 27:  # ESC
                print("✗ Capture annulée")
                break
        
        cap.release()
        cv2.destroyAllWindows()
        
        if not captured or frame is None:
            return None, None
        
        # Sauvegarder la photo
        timestamp = datetime.now().strftime('%Y%m%d_%H%M%S')
        filename = f"{student_name.replace(' ', '_')}_{timestamp}.jpg"
        photo_path = os.path.join(save_path, filename)
        cv2.imwrite(photo_path, frame)
        
        # Générer l'encoding
        rgb_frame = cv2.cvtColor(frame, cv2.COLOR_BGR2RGB)
        encodings = face_recognition.face_encodings(rgb_frame)
        
        if len(encodings) > 0:
            print(f"✓ Photo sauvegardée: {photo_path}")
            return photo_path, encodings[0]
        else:
            print("✗ Impossible de générer l'encoding")
            return None, None
    
    def detect_faces_in_frame(self, frame):
        """
        Détecte et identifie les visages dans une frame
        Retourne: liste de (student_info, face_location, distance)
        """
        # Réduire la taille pour accélérer le traitement
        small_frame = cv2.resize(frame, (0, 0), fx=0.25, fy=0.25)
        rgb_small_frame = cv2.cvtColor(small_frame, cv2.COLOR_BGR2RGB)
        
        # Détecter les visages
        face_locations = face_recognition.face_locations(rgb_small_frame)
        face_encodings = face_recognition.face_encodings(rgb_small_frame, face_locations)
        
        detected_faces = []
        
        for face_encoding, face_location in zip(face_encodings, face_locations):
            # Comparer avec les visages connus
            distances = face_recognition.face_distance(self.known_encodings, face_encoding)
            
            if len(distances) == 0:
                continue
            
            best_match_index = np.argmin(distances)
            best_distance = distances[best_match_index]
            
            if best_distance < self.tolerance:
                student_info = self.known_students[best_match_index]
                
                # Redimensionner les coordonnées du visage
                top, right, bottom, left = face_location
                top *= 4
                right *= 4
                bottom *= 4
                left *= 4
                
                detected_faces.append({
                    'student': student_info,
                    'location': (top, right, bottom, left),
                    'distance': best_distance,
                    'confidence': (1 - best_distance) * 100
                })
        
        return detected_faces
    
    def draw_faces_on_frame(self, frame, detected_faces):
        """Dessine les rectangles et noms sur la frame"""
        for face_data in detected_faces:
            student = face_data['student']
            top, right, bottom, left = face_data['location']
            confidence = face_data['confidence']
            
            # Couleur verte si déjà marqué, bleue sinon
            color = (0, 255, 0) if student['id'] in self.marked_students else (255, 165, 0)
            
            # Rectangle autour du visage
            cv2.rectangle(frame, (left, top), (right, bottom), color, 2)
            
            # Rectangle pour le texte
            cv2.rectangle(frame, (left, bottom - 35), (right, bottom), color, cv2.FILLED)
            
            # Nom de l'étudiant
            name = student['name']
            text = f"{name} ({confidence:.1f}%)"
            cv2.putText(frame, text, (left + 6, bottom - 6),
                       cv2.FONT_HERSHEY_SIMPLEX, 0.6, (255, 255, 255), 2)
        
        return frame
    
    def start_attendance_session(self, database, session_id):
        """
        Démarre une session de prise de présence
        """
        self.marked_students.clear()
        
        cap = cv2.VideoCapture(0)
        
        if not cap.isOpened():
            print("✗ Impossible d'ouvrir la webcam")
            return
        
        print("\n🎥 Session de présence démarrée")
        print("Appuyez sur 'q' pour terminer la session")
        
        frame_count = 0
        detection_interval = 30  # Détecter tous les 30 frames pour optimiser
        
        while True:
            success, frame = cap.read()
            if not success:
                print("✗ Erreur de lecture de la webcam")
                break
            
            frame_count += 1
            
            # Détecter les visages périodiquement
            if frame_count % detection_interval == 0:
                detected_faces = self.detect_faces_in_frame(frame)
                
                # Marquer la présence des étudiants détectés
                for face_data in detected_faces:
                    student = face_data['student']
                    student_id = student['id']
                    
                    if student_id not in self.marked_students:
                        success = database.mark_attendance(session_id, student_id)
                        if success:
                            self.marked_students.add(student_id)
                            print(f"✓ Présence marquée: {student['name']}")
            
            # Détecter et dessiner en temps réel (optimisé)
            if frame_count % 5 == 0:  # Rafraîchir l'affichage tous les 5 frames
                detected_faces = self.detect_faces_in_frame(frame)
                frame = self.draw_faces_on_frame(frame, detected_faces)
            
            # Afficher le compteur de présents
            cv2.putText(frame, f"Presents: {len(self.marked_students)}", (10, 30),
                       cv2.FONT_HERSHEY_SIMPLEX, 1, (0, 255, 0), 2)
            
            cv2.putText(frame, "Appuyez sur 'q' pour quitter", (10, 70),
                       cv2.FONT_HERSHEY_SIMPLEX, 0.7, (255, 255, 255), 2)
            
            cv2.imshow('Session de Presence', frame)
            
            # Quitter avec 'q'
            if cv2.waitKey(1) & 0xFF == ord('q'):
                break
        
        cap.release()
        cv2.destroyAllWindows()
        
        # Statistiques finales
        stats = database.get_session_stats(session_id)
        print(f"\n📊 Session terminée:")
        print(f"   - Présents: {stats['present']}/{stats['total']}")
        print(f"   - Absents: {stats['absent']}")
        print(f"   - Taux de présence: {stats['percentage']:.1f}%")
        
        # Terminer la session dans la base de données
        database.end_session(session_id)
        
        return stats