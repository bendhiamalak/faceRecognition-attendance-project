"""
Système de Gestion de Présence par Reconnaissance Faciale
Projet PFA - Computer Vision
"""

from database import AttendanceDatabase
from face_detector import FaceDetector
import sys

class AttendanceSystem:
    def __init__(self):
        self.db = AttendanceDatabase()
        self.detector = FaceDetector(tolerance=0.5)
        self.current_professor_id = None
        self.current_session_id = None
    
    def display_menu(self):
        """Affiche le menu principal"""
        print("\n" + "="*60)
        print("   SYSTÈME DE GESTION DE PRÉSENCE - RECONNAISSANCE FACIALE")
        print("="*60)
        print("\n📋 MENU PRINCIPAL:")
        print("  1. Inscription Professeur")
        print("  2. Inscription Étudiant")
        print("  3. Démarrer une Séance")
        print("  4. Consulter les Professeurs")
        print("  5. Consulter les Étudiants")
        print("  6. Exporter Rapport de Présence")
        print("  0. Quitter")
        print("-"*60)
    
    def register_professor(self):
        """Module d'inscription des professeurs"""
        print("\n📝 INSCRIPTION PROFESSEUR")
        print("-"*60)
        
        first_name = input("Prénom: ").strip()
        last_name = input("Nom: ").strip()
        subject = input("Matière enseignée: ").strip()
        
        if not first_name or not last_name or not subject:
            print("✗ Tous les champs sont obligatoires!")
            return
        
        professor_id = self.db.add_professor(first_name, last_name, subject)
        
        if professor_id:
            print(f"\n✓ Professeur {first_name} {last_name} inscrit avec succès!")
            print(f"   ID: {professor_id}")
    
    def register_student(self):
        """Module d'inscription des étudiants avec capture photo"""
        print("\n📝 INSCRIPTION ÉTUDIANT")
        print("-"*60)
        
        first_name = input("Prénom: ").strip()
        last_name = input("Nom: ").strip()
        
        if not first_name or not last_name:
            print("✗ Le prénom et le nom sont obligatoires!")
            return
        
        full_name = f"{first_name}_{last_name}"
        
        print(f"\n📸 Capture de la photo de {first_name} {last_name}...")
        photo_path, encoding = self.detector.capture_and_encode_face(full_name)
        
        if photo_path is None or encoding is None:
            print("✗ Échec de la capture de la photo. Inscription annulée.")
            return
        
        student_id = self.db.add_student(first_name, last_name, photo_path, encoding)
        
        if student_id:
            print(f"\n✓ Étudiant {first_name} {last_name} inscrit avec succès!")
            print(f"   ID: {student_id}")
            print(f"   Photo: {photo_path}")
            
            # Recharger les encodages
            self.detector.load_encodings_from_database(self.db)
    
    def start_session(self):
        """Démarre une séance de présence"""
        print("\n🎓 DÉMARRER UNE SÉANCE")
        print("-"*60)
        
        # Afficher les professeurs
        professors = self.db.get_all_professors()
        
        if not professors:
            print("✗ Aucun professeur enregistré. Veuillez d'abord inscrire un professeur.")
            return
        
        print("\nProfesseurs disponibles:")
        for prof in professors:
            print(f"  [{prof[0]}] {prof[1]} {prof[2]} - {prof[3]}")
        
        try:
            prof_id = int(input("\nID du professeur: "))
            
            # Vérifier que le professeur existe
            professor = next((p for p in professors if p[0] == prof_id), None)
            if not professor:
                print("✗ Professeur introuvable!")
                return
            
            subject = professor[3]  # Matière du professeur
            
        except ValueError:
            print("✗ ID invalide!")
            return
        
        # Vérifier qu'il y a des étudiants
        students = self.db.get_all_students()
        if not students:
            print("✗ Aucun étudiant enregistré. Veuillez d'abord inscrire des étudiants.")
            return
        
        # Charger les encodages
        print("\n⏳ Chargement des encodages des étudiants...")
        self.detector.load_encodings_from_database(self.db)
        
        if len(self.detector.known_encodings) == 0:
            print("✗ Aucun encodage disponible!")
            return
        
        # Créer la séance
        session_id = self.db.create_session(prof_id, subject)
        
        if not session_id:
            print("✗ Erreur lors de la création de la séance!")
            return
        
        print(f"\n✓ Séance créée (ID: {session_id})")
        print(f"   Professeur: {professor[1]} {professor[2]}")
        print(f"   Matière: {subject}")
        print(f"   Étudiants inscrits: {len(students)}")
        
        input("\nAppuyez sur ENTRÉE pour lancer la détection de présence...")
        
        # Démarrer la détection
        stats = self.detector.start_attendance_session(self.db, session_id)
        
        # Proposer l'export
        export = input("\nVoulez-vous exporter le rapport en CSV? (o/n): ")
        if export.lower() == 'o':
            filename = f"attendance_session_{session_id}.csv"
            self.db.export_attendance_to_csv(session_id, filename)
    
    def view_professors(self):
        """Affiche la liste des professeurs"""
        print("\n👨‍🏫 LISTE DES PROFESSEURS")
        print("-"*60)
        
        professors = self.db.get_all_professors()
        
        if not professors:
            print("Aucun professeur enregistré.")
            return
        
        for prof in professors:
            print(f"\nID: {prof[0]}")
            print(f"  Nom: {prof[1]} {prof[2]}")
            print(f"  Matière: {prof[3]}")
            print(f"  Inscrit le: {prof[4]}")
    
    def view_students(self):
        """Affiche la liste des étudiants"""
        print("\n👨‍🎓 LISTE DES ÉTUDIANTS")
        print("-"*60)
        
        students = self.db.get_all_students()
        
        if not students:
            print("Aucun étudiant enregistré.")
            return
        
        for student in students:
            print(f"\nID: {student[0]}")
            print(f"  Nom: {student[1]} {student[2]}")
            if student[3]:
                print(f"  Photo: {student[3]}")
    
    def export_report(self):
        """Export un rapport de présence"""
        print("\n📄 EXPORT RAPPORT DE PRÉSENCE")
        print("-"*60)
        
        try:
            session_id = int(input("ID de la séance: "))
            filename = input("Nom du fichier (ex: rapport.csv): ").strip()
            
            if not filename:
                filename = f"attendance_session_{session_id}.csv"
            
            self.db.export_attendance_to_csv(session_id, filename)
            
            # Afficher les stats
            stats = self.db.get_session_stats(session_id)
            print(f"\n📊 Statistiques:")
            print(f"   - Présents: {stats['present']}/{stats['total']}")
            print(f"   - Taux de présence: {stats['percentage']:.1f}%")
            
        except ValueError:
            print("✗ ID de séance invalide!")
        except Exception as e:
            print(f"✗ Erreur: {e}")
    
    def run(self):
        """Boucle principale de l'application"""
        print("\n🚀 Démarrage du système...")
        print("✓ Base de données initialisée")
        
        while True:
            self.display_menu()
            
            try:
                choice = input("\nVotre choix: ").strip()
                
                if choice == '1':
                    self.register_professor()
                
                elif choice == '2':
                    self.register_student()
                
                elif choice == '3':
                    self.start_session()
                
                elif choice == '4':
                    self.view_professors()
                
                elif choice == '5':
                    self.view_students()
                
                elif choice == '6':
                    self.export_report()
                
                elif choice == '0':
                    print("\n👋 Au revoir!")
                    sys.exit(0)
                
                else:
                    print("✗ Choix invalide!")
                
            except KeyboardInterrupt:
                print("\n\n👋 Au revoir!")
                sys.exit(0)
            
            except Exception as e:
                print(f"\n✗ Erreur: {e}")
                import traceback
                traceback.print_exc()

def main():
    """Point d'entrée de l'application"""
    try:
        system = AttendanceSystem()
        system.run()
    except Exception as e:
        print(f"Erreur fatale: {e}")
        import traceback
        traceback.print_exc()

if __name__ == "__main__":
    main()