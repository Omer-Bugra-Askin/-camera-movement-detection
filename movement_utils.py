import numpy as np
import cv2

def extract_features(image, algorithm="ORB", nfeatures=1000):
    """Extract keypoints and descriptors from an image using the specified algorithm."""
    gray = cv2.cvtColor(image, cv2.COLOR_BGR2GRAY)
    if algorithm == "SIFT":
        try:
            detector = cv2.SIFT_create()  # type: ignore
        except AttributeError:
            raise RuntimeError("SIFT is not available. Please install opencv-contrib-python.")
    else:
        detector = cv2.ORB_create(nfeatures)  # type: ignore
    keypoints, descriptors = detector.detectAndCompute(gray, None)
    return keypoints, descriptors

def match_features(des1, des2, algorithm="ORB"):
    """Match descriptors between two frames using the specified algorithm."""
    if des1 is None or des2 is None:
        return []
    norm = cv2.NORM_HAMMING if algorithm == "ORB" else cv2.NORM_L2
    bf = cv2.BFMatcher(norm, crossCheck=True)
    matches = bf.match(des1, des2)
    return sorted(matches, key=lambda x: x.distance)

def compute_homography(kp1, kp2, matches):
    """Compute homography and inlier mask from matched keypoints."""
    if len(matches) < 4:
        return None, None
    src_pts = np.array([kp1[m.queryIdx].pt for m in matches], dtype=np.float32).reshape(-1, 1, 2)
    dst_pts = np.array([kp2[m.trainIdx].pt for m in matches], dtype=np.float32).reshape(-1, 1, 2)
    M, mask = cv2.findHomography(src_pts, dst_pts, cv2.RANSAC, 5.0)
    return M, mask

def compute_translation_magnitude(M):
    """Compute translation magnitude from homography matrix."""
    if M is None:
        return None
    dx = M[0, 2]
    dy = M[1, 2]
    return np.sqrt(dx ** 2 + dy ** 2)

def compute_inlier_ratio(mask):
    """Compute inlier ratio from homography mask."""
    if mask is None:
        return None
    return float(mask.sum()) / len(mask)

def compute_optical_flow(img1, img2, warp_M=None):
    """Compute dense optical flow between two images. Optionally warp img2 to img1's perspective."""
    gray1 = cv2.cvtColor(img1, cv2.COLOR_BGR2GRAY)
    gray2 = cv2.cvtColor(img2, cv2.COLOR_BGR2GRAY)
    if warp_M is not None:
        h, w = gray1.shape
        gray2 = cv2.warpPerspective(gray2, warp_M, (w, h))
    flow = cv2.calcOpticalFlowFarneback(gray1, gray2, None, 0.5, 3, 15, 3, 5, 1.2, 0)  # type: ignore
    mag, ang = cv2.cartToPolar(flow[..., 0], flow[..., 1])
    return mag

def detect_movements(
    frames,
    movement_threshold,
    feature_threshold,
    min_feature_matches,
    feature_algorithm,
    object_flow_threshold
):
    """
    Detect camera and object movement in a sequence of frames.
    Returns: camera_movement_indices, object_movement_indices, match_counts, inlier_ratios, translation_magnitudes, optical_flow_object_indices
    """
    camera_movement_indices = []
    object_movement_indices = []
    match_counts = []
    inlier_ratios = []
    translation_magnitudes = []
    optical_flow_object_indices = []
    for i in range(len(frames) - 1):
        img1 = frames[i]
        img2 = frames[i + 1]
        kp1, des1 = extract_features(img1, feature_algorithm)
        kp2, des2 = extract_features(img2, feature_algorithm)
        if des1 is None or des2 is None or len(kp1) < feature_threshold or len(kp2) < feature_threshold:
            match_counts.append(0)
            inlier_ratios.append(None)
            translation_magnitudes.append(None)
            continue
        matches = match_features(des1, des2, feature_algorithm)
        match_counts.append(len(matches))
        if len(matches) < min_feature_matches:
            inlier_ratios.append(None)
            translation_magnitudes.append(None)
            continue
        M, mask = compute_homography(kp1, kp2, matches)
        translation_magnitude = compute_translation_magnitude(M)
        inlier_ratio = compute_inlier_ratio(mask)
        translation_magnitudes.append(translation_magnitude)
        inlier_ratios.append(inlier_ratio)
        camera_movement = False
        object_movement = False
        # Camera movement detection
        if translation_magnitude is not None and translation_magnitude > movement_threshold:
            if inlier_ratio is not None and inlier_ratio > 0.5:
                camera_movement_indices.append(i + 1)
                camera_movement = True
            else:
                object_movement_indices.append(i + 1)
                object_movement = True
        # Optical flow for object movement
        if camera_movement:
            mag = compute_optical_flow(img1, img2, warp_M=M)
        else:
            mag = compute_optical_flow(img1, img2)
        moving_pixels = np.sum(mag > 1.0)  # 1.0 px/frame threshold for movement
        total_pixels = mag.size
        moving_percent = 100.0 * moving_pixels / total_pixels
        if moving_percent > object_flow_threshold:
            optical_flow_object_indices.append(i + 1)
    # Merge object movement indices
    all_object_indices = sorted(set(object_movement_indices + optical_flow_object_indices))
    return camera_movement_indices, all_object_indices, match_counts, inlier_ratios, translation_magnitudes, optical_flow_object_indices 