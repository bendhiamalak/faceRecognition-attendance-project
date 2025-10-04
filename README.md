# 🎓 Face Recognition Attendance System  

This project is an **AI-powered attendance system** that uses **face recognition** to automatically mark student attendance.  
It leverages **OpenCV, DLIB, and the `face_recognition` library** to detect and identify faces in real-time, logging the arrival time of each student into a CSV file.  

<p align="center">
  <img src="githubmedia/demo.gif" alt="Demo" width="600"/>
</p>

---

## 🚀 Features
- Detects and recognizes faces from a live camera feed.  
- Uses **HOG (Histogram of Oriented Gradients)** for face detection.  
- Aligns and standardizes faces using **DLIB facial landmarks**.  
- Encodes faces into **128-dimension numerical embeddings** using a pre-trained neural network.  
- Compares faces using **SVM-based similarity metrics** (`compare_faces`, `face_distance`).  
- Marks attendance with a **timestamp** into `attendance.csv`.  

---


## ⚙️ Installation  

### 1️⃣ Clone the repository  
```bash
git clone https://github.com/bendhiamalak/faceRecognition-attendance-project.git
cd faceRecognition-attendance-project
```

### 2️⃣ Create a virtual environment
```bash
python -m venv venv
source venv/bin/activate   # Linux / Mac
venv\Scripts\activate      # Windows
```

### 3️⃣ Install dependencies
```bash
pip install -r requirements.txt
```

### 4️⃣ Run the project
```bash
python attendanceProject.py
```

## 📂 Project Structure
.
├── imagesBasic/           
├── githubmedia/           
├── attendance.csv 
├── attendanceProject.py  
├── basic.py               
├── requirements.txt      
└── README.md             

## 📊 Example Output

Attendance file (attendance.csv):
Name,Time
Malek,09:12:45
Sarah,09:15:10


### 👨‍💻 Author

Developed by Malek Ben Dhia
