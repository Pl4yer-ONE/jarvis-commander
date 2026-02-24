"""
Jarvis Skills — Vision & Perception

Phase 4 capabilities. Enables Max to look at the screen and through the 
camera. Integrates with YOLOv8 to locate specific coordinates of UI elements 
and passes them to the local LLaVA (multimodal) inference model.
"""

import logging
import subprocess
import json
import time

from skills import skill

logger = logging.getLogger("jarvis.skills.vision")


# ── Vision Skills ──────────────────────────────────────────

@skill(
    name="look_at_camera",
    description="Takes a live photo using the device webcam and returns a path to the image.",
)
def look_at_camera(**kwargs) -> str:
    """Captures a frame from the webcam."""
    try:
        import cv2
    except ImportError:
        return "Error: opencv-python is not installed. Run: pip install opencv-python"

    cap = cv2.VideoCapture(0)
    if not cap.isOpened():
        return "Error: Could not access the webcam."
        
    ret, frame = cap.read()
    cap.release()
    
    if not ret:
        return "Error: Could not read frame from webcam."

    out_path = "/tmp/max_camera_capture.jpg"
    cv2.imwrite(out_path, frame)
    return f"Image captured successfully and saved to {out_path}."


@skill(
    name="look_at_screen",
    description="Takes a full uncompressed screenshot of the current monitor display and returns the file path.",
)
def look_at_screen(**kwargs) -> str:
    """Takes a screenshot using mss."""
    try:
        import mss
    except ImportError:
        return "Error: mss is not installed. Run: pip install mss"

    out_path = "/tmp/max_screen_capture.png"
    with mss.mss() as sct:
        sct.shot(output=out_path)
    return f"Screenshot captured successfully and saved to {out_path}."


@skill(
    name="yolo_detect_screen",
    description="Uses a YOLOv8 nano model to find bounding box coordinates for objects on the screen.",
)
def yolo_detect_screen(**kwargs) -> str:
    """Runs YOLOv8 object detection on a screenshot."""
    try:
        import mss
        import numpy as np
        import cv2
        from ultralytics import YOLO
    except ImportError as e:
        return f"Error: Missing dependency: {e}. Run: pip install mss opencv-python ultralytics"

    try:
        model = YOLO('yolov8n.pt') 
    except Exception as e:
        return f"Error loading YOLO model: {e}"

    with mss.mss() as sct:
        monitor = sct.monitors[1] 
        sct_img = sct.grab(monitor)
        
        img = np.array(sct_img)
        img = cv2.cvtColor(img, cv2.COLOR_BGRA2BGR)

    results = model(img)
    
    detections = []
    for r in results:
        boxes = r.boxes
        for box in boxes:
            x1, y1, x2, y2 = box.xyxy[0]
            conf = box.conf[0]
            cls = int(box.cls[0])
            name = model.names[cls]
            
            if conf > 0.25:
                detections.append({
                    "object": name,
                    "confidence": float(conf),
                    "bbox": [int(x1), int(y1), int(x2), int(y2)],
                    "center": [int((x1+x2)/2), int((y1+y2)/2)]
                })

    if not detections:
        return "YOLO detected no objects on the screen."
        
    summary = f"YOLO detected {len(detections)} objects:\n"
    for d in detections:
        summary += f"- {d['object']} ({d['confidence']:.2f}) at center ({d['center'][0]}, {d['center'][1]})\n"
        
    return summary
