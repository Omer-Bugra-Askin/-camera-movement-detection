import streamlit as st
import numpy as np
import cv2
from PIL import Image
import tempfile
import os
import time
import pandas as pd
from movement_utils import detect_movements


with open("style.css") as f:
    st.markdown(f"<style>{f.read()}</style>", unsafe_allow_html=True)


st.set_page_config(page_title="Camera Movement Detection", layout="wide")
st.markdown("""
<div class='custom-card' style='text-align:center;'>
    <div class='custom-header'>Camera Movement Detection App</div>
    <div class='custom-sub'>Upload a video or multiple images above. The app will automatically detect not only moving objects in the scene, but also significant movements of the camera itself.</div>
</div>
""", unsafe_allow_html=True)


st.sidebar.markdown("""
<div class='sidebar-card'>
    <div class='sidebar-label'>Detection Settings</div>
</div>
""", unsafe_allow_html=True)
with st.sidebar:
    with st.container():
        st.markdown("<div class='sidebar-card sidebar-slider'>", unsafe_allow_html=True)
        feature_algorithm = st.selectbox(
            "Feature Detection Algorithm",
            options=["ORB", "SIFT"],
            index=0,
            help="SIFT requires opencv-contrib-python."
        )
        feature_threshold = st.slider(
            "Minimum Keypoints per Frame", min_value=10, max_value=50, value=20, step=1, key="feature_slider",
            help="Minimum number of keypoints required in each frame for analysis. Lower values allow analysis of low-detail images, higher values require more features."
        )
        homography_threshold = st.slider(
            "Homography Translation Threshold (pixels)", min_value=10, max_value=40, value=20, step=1, key="homography_slider",
            help="Minimum pixel shift between frames to consider as significant camera movement. Lower values are more sensitive, higher values detect only large movements."
        )
        min_feature_matches = st.slider(
            "Minimum Feature Matches", min_value=10, max_value=40, value=20, step=1, key="match_slider",
            help="Minimum number of feature matches required between frames for movement analysis. Lower values are more tolerant, higher values require more similarity."
        )
        frame_interval = st.slider(
            "Frame Extraction Interval (video)", min_value=1, max_value=10, value=2, step=1, key="interval_slider",
            help="For videos: Analyze every Nth frame. 1 = every frame, 2 = every 2nd frame, etc."
        )
        object_flow_threshold = st.slider(
            "Object Movement Threshold (%)", min_value=1, max_value=20, value=2, step=1, key="object_flow_slider",
            help="If more than this percent of pixels are moving (when camera is still), object movement is detected."
        )
        st.markdown(f"<div style='color:#64748b; font-size:0.98em; margin-top:0.5em;'>Current interval: every <b>{frame_interval}</b> frame(s)</div>", unsafe_allow_html=True)
        st.markdown("</div>", unsafe_allow_html=True)


MAX_FRAMES = 60
frames = []
uploaded_files = st.file_uploader(
    "Upload multiple images or a video (at least 10 frames recommended)",
    type=["jpg", "jpeg", "png", "mp4", "avi"],
    accept_multiple_files=True
)
if uploaded_files:
    video_files = [f for f in uploaded_files if f.name.lower().endswith((".mp4", ".avi"))]
    image_files = [f for f in uploaded_files if f.name.lower().endswith((".jpg", ".jpeg", ".png"))]

    if len(video_files) > 1:
        st.error("Lütfen aynı anda sadece bir video yükleyin. Birden fazla video yüklemek uygulamanın çökmesine neden olur.")
    elif len(video_files) == 1:
        last_video = video_files[0]
        tfile = tempfile.NamedTemporaryFile(delete=False)
        tfile.write(last_video.read())
        cap = cv2.VideoCapture(tfile.name)
        total_frames = int(cap.get(cv2.CAP_PROP_FRAME_COUNT))
        if total_frames < 2:
            st.error("Video çok kısa veya bozuk.")
        else:
            indices = np.linspace(0, total_frames - 1, min(MAX_FRAMES, total_frames), dtype=int)
            idx_set = set(indices)
            idx = 0
            selected = 0
            while True:
                ret, frame = cap.read()
                if not ret or selected >= len(indices):
                    break
                if idx in idx_set:
                    frames.append(frame)
                    selected += 1
                idx += 1
            cap.release()
            time.sleep(0.1)
            try:
                os.unlink(tfile.name)
            except PermissionError:
                pass
            if total_frames > MAX_FRAMES:
                st.warning(f"Video {total_frames} kare içeriyor. Eşit aralıklı {MAX_FRAMES} kare analiz edilecek.")
    elif len(image_files) > 0:
        if len(image_files) > MAX_FRAMES:
            st.warning(f"Çok fazla resim yüklendi ({len(image_files)}). Sadece ilk {MAX_FRAMES} resim işlenecek.")
        for file in image_files[:MAX_FRAMES]:
            try:
                img = Image.open(file).convert("RGB")
                frame = np.array(img)
                frame = cv2.cvtColor(frame, cv2.COLOR_RGB2BGR)
                frames.append(frame)
            except Exception:
                st.markdown("<div class='custom-error'>Yüklediğiniz dosyalardan biri resim olarak açılamadı. Lütfen geçerli bir resim yükleyin.</div>", unsafe_allow_html=True)
    else:
        st.markdown("<div class='custom-error'>Lütfen en az bir video veya resim yükleyin.</div>", unsafe_allow_html=True)

    if len(frames) < 2 and len(video_files) <= 1:
        st.markdown("<div class='custom-error'>At least 2 frames are required.</div>", unsafe_allow_html=True)
    elif len(frames) >= 2:
        st.markdown(f"<div class='custom-success'>{len(frames)} frames loaded. Running analysis...</div>", unsafe_allow_html=True)

        # Frame sayısını 300 ile sınırla
        if len(frames) > MAX_FRAMES:
            st.warning(f"Çok fazla frame tespit edildi ({len(frames)}). Sadece ilk {MAX_FRAMES} frame işlenecek.")
            frames = frames[:MAX_FRAMES]

        camera_movement_indices, object_movement_indices, match_counts, inlier_ratios, translation_magnitudes, optical_flow_object_indices = detect_movements(
            frames, homography_threshold, feature_threshold, min_feature_matches, feature_algorithm, object_flow_threshold
        )

       
        st.markdown("<div class='custom-card' style='margin-top:2em;'>"
                    "<h2 style='color:#2563eb;'>Results</h2>", unsafe_allow_html=True)
        if camera_movement_indices:
            st.markdown(f"<div style='color:#ef4444; font-weight:600; font-size:1.15em; margin-bottom:1em;'><b>Camera movement</b> detected in {len(camera_movement_indices)} frames!<br>Frame indices: {camera_movement_indices}</div>", unsafe_allow_html=True)
        else:
            st.markdown("<div style='color:#22c55e; font-weight:600; font-size:1.15em; margin-bottom:1em;'>No significant camera movement detected.</div>", unsafe_allow_html=True)
        if object_movement_indices:
            st.markdown(f"<div style='color:#facc15; font-weight:600; font-size:1.15em; margin-bottom:1em;'><b>Object movement</b> detected in {len(object_movement_indices)} frames!<br>Frame indices: {object_movement_indices}</div>", unsafe_allow_html=True)
        st.markdown("</div>", unsafe_allow_html=True)

       
        st.markdown("<div class='custom-card'><h3 style='color:#2563eb;'>Frame Summary</h3>", unsafe_allow_html=True)
        df = pd.DataFrame({
            "Frame": list(range(len(frames))),
            "Feature Matches": match_counts + [None],
            "Inlier Ratio": inlier_ratios + [None],
            "Translation Magnitude": translation_magnitudes + [None],
            "Camera Movement": [idx in camera_movement_indices for idx in range(len(frames))],
            "Object Movement": [idx in object_movement_indices for idx in range(len(frames))],
            "Object Movement (Optical Flow)": [idx in optical_flow_object_indices for idx in range(len(frames))]
        })
        st.dataframe(df, use_container_width=True, hide_index=True)
        st.markdown("</div>", unsafe_allow_html=True)

       
        st.markdown("<div class='custom-card'><h3 style='color:#2563eb;'>Frame Gallery</h3>", unsafe_allow_html=True)
        gallery_frames = []
        for idx, frame in enumerate(frames):
            cam = idx in camera_movement_indices
            obj = idx in object_movement_indices
            if not (cam or obj):
                continue
            if cam and obj:
                movement_text = "Camera and object movement detected"
            elif cam:
                movement_text = "Camera movement detected"
            elif obj:
                movement_text = "Object movement detected"
            caption = f"Frame {idx}: {movement_text}"
            img_rgb = cv2.cvtColor(frame, cv2.COLOR_BGR2RGB)
            pil_img = Image.fromarray(img_rgb)
            gallery_frames.append((pil_img, caption))
        for i in range(0, len(gallery_frames), 4):
            cols = st.columns(4)
            for j, (img, caption) in enumerate(gallery_frames[i:i+4]):
                cols[j].image(img, caption=caption, use_container_width=True, output_format="PNG")
        st.markdown("</div>", unsafe_allow_html=True)
else:
    st.markdown("<div class='custom-info'>Upload images or a video to get started.</div>", unsafe_allow_html=True) 