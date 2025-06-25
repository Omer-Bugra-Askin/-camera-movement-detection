import cv2
import numpy as np
from typing import List

"""
Detects significant camera movement between consecutive frames using ORB feature matching and homography estimation.
"""

def detect_camera_movement(frames: List[np.ndarray], movement_threshold: float = 30.0) -> List[int]:
    """
    Detects significant camera movement between consecutive frames.
    Args:
        frames: List of np.ndarray images (BGR)
        movement_threshold: Threshold for significant movement (pixels)
    Returns:
        List of frame indices where significant movement is detected
    """
    try:
        orb = getattr(cv2, "ORB_create")(1000)
    except AttributeError:
        raise ImportError("cv2.ORB_create not found. Please install opencv-contrib-python.")
    bf = cv2.BFMatcher(cv2.NORM_HAMMING, crossCheck=True)
    significant_movement_indices = []

    for i in range(len(frames) - 1):
        img1 = frames[i]
        img2 = frames[i + 1]
        gray1 = cv2.cvtColor(img1, cv2.COLOR_BGR2GRAY)
        gray2 = cv2.cvtColor(img2, cv2.COLOR_BGR2GRAY)
        kp1, des1 = orb.detectAndCompute(gray1, None)
        kp2, des2 = orb.detectAndCompute(gray2, None)
        if des1 is None or des2 is None or len(kp1) < 10 or len(kp2) < 10:
            continue
        matches = bf.match(des1, des2)
        matches = sorted(matches, key=lambda x: x.distance)
        if len(matches) < 10:
            continue
        src_pts = np.array([kp1[m.queryIdx].pt for m in matches], dtype=np.float32).reshape(-1, 1, 2)
        dst_pts = np.array([kp2[m.trainIdx].pt for m in matches], dtype=np.float32).reshape(-1, 1, 2)
        if src_pts.shape[0] < 4 or dst_pts.shape[0] < 4:
            continue
        M, mask = cv2.findHomography(src_pts, dst_pts, cv2.RANSAC, 5.0)
        if M is None:
            continue
        dx = M[0, 2]
        dy = M[1, 2]
        translation_magnitude = np.sqrt(dx ** 2 + dy ** 2)
        if translation_magnitude > movement_threshold:
            significant_movement_indices.append(i + 1)
    return significant_movement_indices 