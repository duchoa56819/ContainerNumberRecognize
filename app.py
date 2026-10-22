"""
Container Number Identification Web Application.
Built with Streamlit, YOLO, RapidOCR, and ISO 6346 Validator.
"""
import os
import glob
import time
import pandas as pd
import numpy as np
from PIL import Image
import streamlit as st

from pipeline import ContainerRecognitionPipeline
from container_parser import (
    validate_container_number,
    calculate_check_digit,
    get_step_by_step_calculation,
    OWNER_CODES,
    SIZE_TYPE_CODES
)

# Page Configuration
st.set_page_config(
    page_title="ContainerLens - Container Number Recognition",
    page_icon="🚢",
    layout="wide",
    initial_sidebar_state="expanded"
)

# Custom Styling
st.markdown("""
<style>
    .main-header {
        font-size: 2.2rem;
        font-weight: 700;
        color: #1E88E5;
        margin-bottom: 0px;
    }
    .sub-header {
        font-size: 1.05rem;
        color: #90A4AE;
        margin-bottom: 1.5rem;
    }
    .metric-card {
        background-color: #1e222d;
        border-radius: 10px;
        padding: 1.2rem;
        border-left: 5px solid #1E88E5;
        box-shadow: 0 4px 6px rgba(0,0,0,0.3);
    }
    .metric-val {
        font-size: 1.8rem;
        font-weight: bold;
        color: #FFFFFF;
        font-family: monospace;
    }
    .metric-lbl {
        font-size: 0.85rem;
        color: #90A4AE;
        text-transform: uppercase;
        letter-spacing: 0.5px;
    }
    .badge-valid {
        display: inline-block;
        padding: 4px 12px;
        background-color: #2E7D32;
        color: white;
        border-radius: 6px;
        font-weight: bold;
        font-size: 0.85rem;
    }
    .badge-repaired {
        display: inline-block;
        padding: 4px 12px;
        background-color: #F57C00;
        color: white;
        border-radius: 6px;
        font-weight: bold;
        font-size: 0.85rem;
    }
    .badge-invalid {
        display: inline-block;
        padding: 4px 12px;
        background-color: #C62828;
        color: white;
        border-radius: 6px;
        font-weight: bold;
        font-size: 0.85rem;
    }
</style>
""", unsafe_allow_html=True)


@st.cache_resource
def load_pipeline(weights_path: str):
    """Caches pipeline instance to prevent reloading on each interaction."""
    return ContainerRecognitionPipeline(weights_path)


# Sidebar Configuration
st.sidebar.image("https://img.icons8.com/fluency/96/cargo-ship.png", width=64)
st.sidebar.title("ContainerLens")
st.sidebar.caption("ISO 6346 Container Number Recognition")
st.sidebar.divider()

# Model Weights Selection
weights_options = {}
if os.path.exists("weights/container_detector.pt"):
    weights_options["Custom Fine-Tuned (YOLO11n-Container)"] = "weights/container_detector.pt"
if os.path.exists("runs/detect/models/container_detector/weights/best.pt"):
    weights_options["Run Best Checkpoint"] = "runs/detect/models/container_detector/weights/best.pt"
if os.path.exists("yolo11n.pt"):
    weights_options["Base YOLO11n"] = "yolo11n.pt"

selected_model_name = st.sidebar.selectbox("YOLO Detector Model", list(weights_options.keys()))
selected_weights = weights_options[selected_model_name]

# Detection Parameters
conf_threshold = st.sidebar.slider("Detection Confidence Threshold", 0.05, 0.90, 0.20, 0.05)
crop_padding = st.sidebar.slider("Region Crop Padding (%)", 0.0, 0.25, 0.08, 0.01)
use_detector = st.sidebar.checkbox("Enable YOLO Region Detector", value=True)

pipeline = load_pipeline(selected_weights)

# Main Application Header
st.markdown('<p class="main-header">🚢 ContainerLens Identification System</p>', unsafe_allow_html=True)
st.markdown('<p class="sub-header">Automated ISO 6346 shipping container code detection, OCR extraction, and Modulo-11 verification.</p>', unsafe_allow_html=True)

# Tabs
tab1, tab2, tab3, tab4 = st.tabs([
    "🔍 Container Identifier",
    "📊 Batch Dataset Benchmark",
    "🧠 Model Studio & Training",
    "📐 ISO 6346 Calculator"
])

# ==========================================
# TAB 1: CONTAINER IDENTIFIER
# ==========================================
with tab1:
    col_input, col_meta = st.columns([1, 1], gap="medium")

    with col_input:
        st.subheader("1. Input Container Image")
        source_mode = st.radio("Select Image Source:", ["Sample Gallery", "Upload File", "Camera Capture"], horizontal=True)

        selected_image = None
        img_name = ""

        if source_mode == "Sample Gallery":
            sample_files = glob.glob("test/images/*.jpg")[:40]
            if sample_files:
                sample_names = [os.path.basename(f) for f in sample_files]
                selected_sample = st.selectbox("Choose a sample from test dataset:", sample_names, index=2)
                sample_path = os.path.join("test/images", selected_sample)
                selected_image = Image.open(sample_path)
                img_name = selected_sample
            else:
                st.warning("No sample images found in test/images.")

        elif source_mode == "Upload File":
            uploaded_file = st.file_uploader("Upload container photo (JPG, PNG, WEBP)", type=["jpg", "jpeg", "png", "webp"])
            if uploaded_file is not None:
                selected_image = Image.open(uploaded_file)
                img_name = uploaded_file.name

        elif source_mode == "Camera Capture":
            camera_file = st.camera_input("Take a photo of a container code")
            if camera_file is not None:
                selected_image = Image.open(camera_file)
                img_name = "camera_snapshot.jpg"

        if selected_image is not None:
            st.image(selected_image, caption=f"Input: {img_name}", use_container_width=True)

    with col_meta:
        st.subheader("2. Recognition Result")
        if selected_image is not None:
            with st.spinner("Processing image through YOLO + OCR + ISO Validator..."):
                result = pipeline.process(
                    selected_image,
                    conf_threshold=conf_threshold,
                    use_detector=use_detector,
                    crop_padding=crop_padding
                )

            code = result["container_number"]
            formatted = result["formatted_number"]
            is_valid = result["is_valid"]
            repaired = result["repaired"]
            owner = result["owner_name"]
            size_code = result["size_type_code"]
            size_desc = result["size_type_desc"]
            elapsed = result["elapsed_time_ms"]
            regions_count = len(result["detected_regions"])

            # Container Result Card
            st.markdown(f"""
            <div class="metric-card">
                <div class="metric-lbl">Identified Container Number</div>
                <div class="metric-val">{formatted}</div>
                <div style="margin-top: 10px;">
                    {'<span class="badge-valid">✓ ISO 6346 VALID</span>' if is_valid and not repaired else ''}
                    {'<span class="badge-repaired">⚡ AUTO-CORRECTED (VALID)</span>' if is_valid and repaired else ''}
                    {'<span class="badge-invalid">✕ INVALID CHECK DIGIT</span>' if not is_valid and code != 'Not Found' else ''}
                    {'<span class="badge-invalid">✕ NO NUMBER DETECTED</span>' if code == 'Not Found' else ''}
                    <span style="color: #90A4AE; margin-left: 15px; font-size: 0.9rem;">⏱ {elapsed} ms</span>
                    <span style="color: #90A4AE; margin-left: 15px; font-size: 0.9rem;">📍 {regions_count} region(s) detected</span>
                </div>
            </div>
            """, unsafe_allow_html=True)

            st.write("")

            # Structured Metadata Table
            meta_data = {
                "Field": [
                    "Owner Code (BIC)",
                    "Shipping Line / Operator",
                    "Category Identifier",
                    "Category Type",
                    "Serial Number",
                    "Check Digit (Provided)",
                    "Check Digit (Calculated)",
                    "ISO Size & Type Code",
                    "Container Description"
                ],
                "Value": [
                    result["owner_code"],
                    owner,
                    result["category_char"],
                    result["category_description"],
                    result["serial_number"],
                    result["check_digit"],
                    result["expected_check_digit"],
                    size_code or "Not Detected",
                    size_desc or "N/A"
                ]
            }
            st.dataframe(pd.DataFrame(meta_data), use_container_width=True, hide_index=True)

            # Copy helper
            if code != "Not Found":
                st.code(code, language="text")

    # Full Visual Inspection Section
    if selected_image is not None:
        st.divider()
        st.subheader("3. Visual Pipeline Inspection")
        tab_v1, tab_v2, tab_v3, tab_v4 = st.tabs([
            "🖼 Annotated Image",
            "🔍 Detected Region Crop",
            "📝 All Extracted OCR Candidates",
            "📐 Modulo-11 Verification Proof"
        ])

        with tab_v1:
            st.image(result["annotated_image"], caption="Detections (Cyan: Code Panel, Yellow: OCR bounding boxes)", use_container_width=True)

        with tab_v2:
            crop_box = result.get("selected_crop_box")
            if crop_box:
                x1, y1, x2, y2 = crop_box
                img_np = np.array(selected_image)
                crop_np = img_np[y1:y2, x1:x2]
                st.image(crop_np, caption=f"Cropped Container Panel [{x1}:{x2}, {y1}:{y2}]", width=400)
            else:
                st.info("Full image scan was used (no localized crop or fallback activated).")

        with tab_v3:
            cands = result.get("all_candidates", [])
            if cands:
                st.dataframe(pd.DataFrame(cands), use_container_width=True)
            else:
                st.info("No candidates extracted.")
            st.caption("Raw OCR text tokens: " + " | ".join(result.get("raw_ocr_texts", [])))

        with tab_v4:
            if len(code) >= 10:
                proof = get_step_by_step_calculation(code[:10])
                if proof:
                    st.write(f"**Prefix:** `{code[:10]}` | **Total Weighted Sum:** `{proof['total_sum']}`")
                    st.write(f"**Sum % 11:** `{proof['modulo_11']}` → **Expected Check Digit:** `{proof['check_digit']}`")
                    st.dataframe(pd.DataFrame(proof["steps"]), use_container_width=True, hide_index=True)
            else:
                st.info("Select or recognize a valid 10+ character container code to see calculation steps.")


# ==========================================
# TAB 2: BATCH DATASET BENCHMARK
# ==========================================
with tab2:
    st.subheader("Batch Dataset Evaluation")
    st.write("Run the full recognition pipeline against samples from the test/valid dataset and compute precision metrics.")

    b_col1, b_col2, b_col3 = st.columns([1, 1, 1])
    with b_col1:
        split_choice = st.selectbox("Dataset Split", ["test/images", "valid/images", "train/images"])
    with b_col2:
        num_eval = st.slider("Number of Images to Test", 5, 100, 20, 5)
    with b_col3:
        st.write("")
        st.write("")
        run_batch_btn = st.button("🚀 Run Evaluation Benchmark", use_container_width=True, type="primary")

    if run_batch_btn:
        img_paths = glob.glob(f"{split_choice}/*.jpg")[:num_eval]
        if not img_paths:
            st.error(f"No images found in {split_choice}")
        else:
            progress_bar = st.progress(0)
            status_text = st.empty()

            records = []
            valid_count = 0
            detected_regions_count = 0
            total_time = 0.0

            for i, p in enumerate(img_paths):
                status_text.text(f"Evaluating ({i+1}/{len(img_paths)}): {os.path.basename(p)}")
                res = pipeline.process(p, conf_threshold=conf_threshold, use_detector=use_detector, crop_padding=crop_padding)
                
                is_val = res["is_valid"]
                has_reg = len(res["detected_regions"]) > 0
                if is_val:
                    valid_count += 1
                if has_reg:
                    detected_regions_count += 1
                total_time += res["elapsed_time_ms"]

                records.append({
                    "Image File": os.path.basename(p),
                    "Container Number": res["container_number"],
                    "Valid ISO": "✓ Yes" if is_val else "✕ No",
                    "Auto-Repaired": "Yes" if res["repaired"] else "No",
                    "Regions": len(res["detected_regions"]),
                    "Owner": res["owner_name"],
                    "Size/Type": res["size_type_code"] or "-",
                    "Latency (ms)": res["elapsed_time_ms"]
                })
                progress_bar.progress((i + 1) / len(img_paths))

            status_text.text(f"Benchmark Complete! Evaluated {len(img_paths)} images.")

            # Summary Metric Cards
            m1, m2, m3, m4 = st.columns(4)
            recog_rate = (valid_count / len(img_paths)) * 100
            region_rate = (detected_regions_count / len(img_paths)) * 100
            avg_lat = total_time / len(img_paths)

            with m1:
                st.markdown(f"""
                <div class="metric-card">
                    <div class="metric-lbl">Total Tested</div>
                    <div class="metric-val">{len(img_paths)}</div>
                </div>
                """, unsafe_allow_html=True)
            with m2:
                st.markdown(f"""
                <div class="metric-card">
                    <div class="metric-lbl">ISO Valid Rate</div>
                    <div class="metric-val" style="color: #4CAF50;">{recog_rate:.1f}%</div>
                </div>
                """, unsafe_allow_html=True)
            with m3:
                st.markdown(f"""
                <div class="metric-card">
                    <div class="metric-lbl">Region Detection</div>
                    <div class="metric-val" style="color: #2196F3;">{region_rate:.1f}%</div>
                </div>
                """, unsafe_allow_html=True)
            with m4:
                st.markdown(f"""
                <div class="metric-card">
                    <div class="metric-lbl">Avg Latency</div>
                    <div class="metric-val">{avg_lat:.1f} ms</div>
                </div>
                """, unsafe_allow_html=True)

            st.write("")
            df_results = pd.DataFrame(records)
            st.dataframe(df_results, use_container_width=True)

            # Export CSV
            csv_data = df_results.to_csv(index=False).encode('utf-8')
            st.download_button(
                label="📥 Download Benchmark Results (CSV)",
                data=csv_data,
                file_name=f"container_benchmark_{split_choice.replace('/', '_')}.csv",
                mime="text/csv"
            )


# ==========================================
# TAB 3: MODEL STUDIO & TRAINING
# ==========================================
with tab3:
    st.subheader("Model Studio & Dataset Training")
    st.write("Fine-tune the YOLO detector model on the local Roboflow dataset.")

    # Dataset Summary
    train_c = len(glob.glob("train/images/*.jpg"))
    val_c = len(glob.glob("valid/images/*.jpg"))
    test_c = len(glob.glob("test/images/*.jpg"))

    c1, c2, c3, c4 = st.columns(4)
    with c1:
        st.metric("Train Split", f"{train_c} images")
    with c2:
        st.metric("Validation Split", f"{val_c} images")
    with c3:
        st.metric("Test Split", f"{test_c} images")
    with c4:
        st.metric("Classes", "1 (con-region)")

    st.divider()

    st.write("#### Train New / Additional Epochs")
    tr_col1, tr_col2, tr_col3, tr_col4 = st.columns(4)
    with tr_col1:
        tr_epochs = st.number_input("Epochs", min_value=1, max_value=50, value=5)
    with tr_col2:
        tr_batch = st.selectbox("Batch Size", [8, 16, 32], index=1)
    with tr_col3:
        tr_fraction = st.slider("Dataset Fraction", 0.02, 1.0, 0.08, 0.02, help="Fraction of 4501 train images to use per epoch")
    with tr_col4:
        tr_imgsz = st.selectbox("Image Size", [416, 512, 640], index=0)

    if st.button("🏋️ Start Training Job in Background", type="secondary"):
        st.info("You can run training directly via CLI for continuous terminal monitoring:")
        st.code(f"python cli.py train --epochs {tr_epochs} --batch {tr_batch} --fraction {tr_fraction} --imgsz {tr_imgsz}")

    # Display existing training curves if available
    train_runs = glob.glob("runs/detect/**/results.png", recursive=True)
    if train_runs:
        st.write("#### Training Metrics & Evaluation Plots")
        st.image(train_runs[-1], caption=f"Latest Run: {os.path.dirname(train_runs[-1])}", use_container_width=True)


# ==========================================
# TAB 4: ISO 6346 CALCULATOR
# ==========================================
with tab4:
    st.subheader("ISO 6346 Container Number Math & Modulo-11 Calculator")
    st.write("Inspect how the international shipping container check digit is calculated step-by-step.")

    calc_input = st.text_input("Enter 10 or 11 Character Container Code:", value="TCLU4897918", max_chars=11).upper()
    
    if calc_input:
        prefix_10 = calc_input[:10]
        step_info = get_step_by_step_calculation(prefix_10)

        if step_info:
            calc_chk = step_info["check_digit"]
            provided_chk = calc_input[10] if len(calc_input) == 11 else None
            is_match = (provided_chk == str(calc_chk)) if provided_chk else None

            res_c1, res_c2, res_c3 = st.columns(3)
            with res_c1:
                st.metric("Calculated Check Digit", str(calc_chk))
            with res_c2:
                st.metric("Total Weighted Sum", str(step_info["total_sum"]))
            with res_c3:
                status_str = "✓ MATCH (VALID)" if is_match else ("✕ MISMATCH" if is_match is False else "READY")
                st.metric("Status", status_str)

            st.write("#### Calculation Step Breakdown:")
            st.dataframe(pd.DataFrame(step_info["steps"]), use_container_width=True, hide_index=True)
            st.latex(r"\text{Check Digit} = \left( \sum_{i=0}^{9} \text{val}_i \times 2^i \right) \pmod{11}")
        else:
            st.warning("Please enter valid alphanumeric characters (first 4 must be letters, next 6 digits).")
