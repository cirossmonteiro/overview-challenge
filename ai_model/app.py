import base64
from dataclasses import dataclass
import json
from typing import List

import cv2
from flask import Flask, request, jsonify
from flask_cors import CORS, cross_origin
import numpy as np
import onnxruntime as ort
from PIL import Image
import psycopg2
from smart_open import open

# base64 decode: https://stackoverflow.com/a/60270269


app = Flask(__name__)
cors = CORS(app)

app.config['CORS_HEADERS'] = 'Content-Type'

conn = psycopg2.connect(
    host="localhost",
    database="postgres",
    user="postgres",
    password="postgres"
)
cur = conn.cursor()

cur.execute('DROP TABLE IF EXISTS results;')
conn.commit()
print("Existing table 'results' may have been dropped.")

cur.execute("""
    CREATE TABLE results (
        id SERIAL PRIMARY KEY,
        confidence REAL NOT NULL,
        iou REAL NOT NULL,
        image_path VARCHAR(100) NOT NULL,
        predictions JSONB,
        instant DATE DEFAULT CURRENT_TIMESTAMP
    );
""")
conn.commit()

print("Table 'results' has been created.")

# cur.close()
# conn.close()

def save_to_db(image_path, confidence, iou, detections):
    print(f"Data to be inserted into database: >{json.dumps(detections)}<")
    cur.execute("""
        INSERT INTO results (
            confidence,
            iou,
            image_path,
            predictions
        ) VALUES (
            %s,
            %s,
            %s,
            %s
        );
    """, (confidence, iou, image_path, json.dumps(detections),))
    conn.commit()
    print("Saved.")


@dataclass
class BBOX:
    left: int
    top: int
    width: int
    height: int

@dataclass
class Prediction:
    class_name: int
    confidence: float
    box: BBOX
    
    def to_dict(self):
        return {
            "class_name": str(self.class_name),
            "confidence": float(self.confidence),
            "box": {
                "left": int(self.box.left),
                "top": int(self.box.top),
                "width": int(self.box.width),
                "height": int(self.box.height)
            }
        }

class Model:
    def __init__(self, model_name: str):
        self.model_name = model_name
        providers = ort.get_available_providers()
        print(f"Available providers: {providers}")
        self.model = ort.InferenceSession(f"models/{model_name}.onnx", providers=providers)
        self.input_name = self.model.get_inputs()[0].name
        self.output_name = self.model.get_outputs()[0].name
        self.input_width = self.model.get_inputs()[0].shape[2]
        self.input_height = self.model.get_inputs()[0].shape[3]
        self.idx2class = eval(self.model.get_modelmeta().custom_metadata_map['names'])
    
    def preprocess(
        self,
        img: Image.Image
    ) -> np.ndarray:
        img = img.resize((self.input_width, self.input_height))
        img = np.array(img).transpose(2, 0, 1)
        img = np.expand_dims(img, axis=0)
        img = img / 255.0
        img = img.astype(np.float32)
        return img
    
    def postprocess(
        self, 
        output: np.ndarray, 
        confidence_thresh: float, 
        iou_thresh: float,
        img_width: int,
        img_height: int
    ) -> List[Prediction]:
        
        outputs = np.transpose(np.squeeze(output[0]))
        rows = outputs.shape[0]
        boxes = []
        scores = []
        class_ids = []
        x_factor = img_width / self.input_width
        y_factor = img_height / self.input_height
        for i in range(rows):
            classes_scores = outputs[i][4:]
            max_score = np.amax(classes_scores)
            if max_score >= confidence_thresh:
                class_id = np.argmax(classes_scores)
                x, y, w, h = outputs[i][0], outputs[i][1], outputs[i][2], outputs[i][3]
                left = int((x - w / 2) * x_factor)
                top = int((y - h / 2) * y_factor)
                width = int(w * x_factor)
                height = int(h * y_factor)
                class_ids.append(class_id)
                scores.append(max_score)
                boxes.append([left, top, width, height])
        indices = cv2.dnn.NMSBoxes(boxes, scores, confidence_thresh, iou_thresh)
        detections = []
        if len(indices) > 0:
            for i in indices.flatten():
                left, top, width, height = boxes[i]
                class_id = class_ids[i]
                score = scores[i]
                detection = Prediction(
                    class_name=self.idx2class[class_id],
                    confidence=score,
                    box=BBOX(left, top, width, height)
                )
                detections.append(detection)
        return detections

    def __call__(
        self, 
        img: Image.Image,
        confidence_thresh: float, 
        iou_thresh: float
    ) -> List[Prediction]:
        img_input = self.preprocess(img)
        outputs = self.model.run(None, {self.input_name: img_input})
        predictions = self.postprocess(outputs, confidence_thresh, iou_thresh, img.width, img.height)
        return predictions

model = Model("yolov8s")

@app.route('/detect', methods=['POST'])
@cross_origin()
def detect():
    image_path = request.json['image_path']
    confidence = request.json['confidence']
    iou = request.json['iou']

# """
# This loop is a workaround for a issue that I haven't solved.
# I receive a base64 string from frontend request and I need to save it to binary file,
# but after that I couldn't be able to use Pillow's API.
# My workaround basically tests different "ranges" of the base64 string and
# it stops right after it works.
# I know it's weird, but it seems to work.
# """
    for i in range(50):
        try:
            # save the frame locally
            with open(image_path, 'wb') as f:
                f.write(base64.b64decode(request.json['base64'][i:]))
            
            # then load the local file to be processed
            # with open("test/bus.jpg", 'rb') as f: # this line works
            with open(image_path, 'rb') as f:
                original_img = Image.open(f).convert('RGB')
            print("worked: ", i)
            break
        except:
            pass
    else:
        raise Exception("The base64 string can't be loaded correctly.")

    predictions = model(original_img, confidence, iou)
    detections = [p.to_dict() for p in predictions]
    save_to_db(image_path, confidence, iou, detections)

    return jsonify(detections)

@app.route('/health_check', methods=['GET'])
def health_check():
    if model is None:
        return "Model is not loaded7"
    return f"Model {model.model_name} is loaded11"

@app.route('/load_model', methods=['POST'])
def load_model():
    model_name = request.json['model_name']
    global model
    model = Model(model_name)
    return f"Model {model_name} is loaded11"

if __name__ == "__main__":
    app.run(host='0.0.0.0', port=5000, debug=True)
print(226)