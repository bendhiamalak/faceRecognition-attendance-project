import cv2
import numpy as np
import face_recognition

imgElon=face_recognition.load_image_file('imagesBasic/elon1.jpg')
imgElon=cv2.cvtColor(imgElon,cv2.COLOR_BGR2RGB)

imgTest=face_recognition.load_image_file('imagesBasic/elo2.jpg')
imgTest=cv2.cvtColor(imgTest,cv2.COLOR_BGR2RGB)

faceLoc=face_recognition.face_locations(imgElon)[0]
encodeElon=face_recognition.face_encodings(imgElon)[0]
print(faceLoc)
cv2.rectangle(imgElon,(faceLoc[3],faceLoc[0]),(faceLoc[1],faceLoc[2]),(255,0,255),2)


cv2.imshow("elonMusk", imgElon)
cv2.imshow("elonMuskTest", imgTest)
cv2.waitKey(0)