import cv2
import numpy as np
import face_recognition

imgMalek=face_recognition.load_image_file('imagesBasic/malek.jpeg')
imgMalek=cv2.cvtColor(imgMalek,cv2.COLOR_BGR2RGB)

imgTest=face_recognition.load_image_file('imagesBasic/hamza.jpeg')
imgTest=cv2.cvtColor(imgTest,cv2.COLOR_BGR2RGB)

faceLoc=face_recognition.face_locations(imgMalek)[0]
encodeMalek=face_recognition.face_encodings(imgMalek)[0]
print(faceLoc)
cv2.rectangle(imgMalek,(faceLoc[3],faceLoc[0]),(faceLoc[1],faceLoc[2]),(255,0,255),2)

faceLocTest=face_recognition.face_locations(imgTest)[0]
encodeTest=face_recognition.face_encodings(imgTest)[0]
print(faceLocTest)
cv2.rectangle(imgTest,(faceLocTest[3],faceLocTest[0]),(faceLocTest[1],faceLocTest[2]),(255,0,255),2)


results=face_recognition.compare_faces([encodeMalek],encodeTest)
faceDis=face_recognition.face_distance([encodeMalek],encodeTest)
print(results,faceDis)



cv2.imshow("malek ben dhia", imgMalek)
cv2.imshow("test", imgTest)
cv2.waitKey(0)