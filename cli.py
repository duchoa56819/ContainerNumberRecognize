"""
CLI Tool for Shipping Container Number Recognition, Dataset Batch Evaluation, and Training.
"""
import argparse
import glob
import json
import os
import sys
import time
import cv2
import pandas as pd
from typing import Optional

from pipeline import ContainerRecognitionPipeline
from container_parser import (
    validate_container_number,
    calculate_check_digit,
    get_step_by_step_calculation,
    parse_container_info
)


def cmd_predict(args):
    """Predict container number from an image."""
    weights = args.weights or "weights/container_detector.pt"
    if not os.path.exists(weights):
        weights = "yolo11n.pt"

    print(f"Loading pipeline with model: {weights}...")
    pipeline = ContainerRecognitionPipeline(weights)

    if not os.path.exists(args.image):
        print(f"Error: Image file does not exist: {args.image}", file=sys.stderr)
        sys.exit(1)

    print(f"Processing image: {args.image}...")
    res = pipeline.process(
        args.image,
        conf_threshold=args.conf,
        use_detector=not args.no_detector,
        crop_padding=args.padding
    )

    print("\n" + "=" * 55)
    print("CONTAINER IDENTIFICATION RESULT")
    print("=" * 55)
    print(f"Container Number   : {res['container_number']}")
    print(f"Formatted Code     : {res['formatted_number']}")
    print(f"ISO 6346 Valid     : {res['is_valid']}")
    print(f"Auto-Repaired      : {res['repaired']}")
    print(f"Owner BIC Code     : {res['owner_code']}")
    print(f"Owner / Carrier    : {res['owner_name']}")
    print(f"Category           : {res['category_char']} ({res['category_description']})")
    print(f"Serial Number      : {res['serial_number']}")
    print(f"Check Digit        : {res['check_digit']} (Expected: {res['expected_check_digit']})")
    print(f"ISO Size/Type Code : {res['size_type_code'] or 'N/A'}")
    print(f"Container Type     : {res['size_type_desc'] or 'N/A'}")
    print(f"Detected Regions   : {len(res['detected_regions'])}")
    print(f"Inference Latency  : {res['elapsed_time_ms']} ms")
    print("=" * 55)

    if args.output:
        # Save JSON output (omit ndarray)
        out_dict = {k: v for k, v in res.items() if k != "annotated_image"}
        with open(args.output, "w") as f:
            json.dump(out_dict, f, indent=2)
        print(f"Structured result saved to: {args.output}")

    if args.save_image:
        cv2.imwrite(args.save_image, cv2.cvtColor(res["annotated_image"], cv2.COLOR_RGB2BGR))
        print(f"Annotated image saved to: {args.save_image}")


def cmd_batch(args):
    """Batch evaluation on a directory of images."""
    weights = args.weights or "weights/container_detector.pt"
    pipeline = ContainerRecognitionPipeline(weights)

    files = glob.glob(os.path.join(args.dir, "*.jpg")) + glob.glob(os.path.join(args.dir, "*.png"))
    if args.limit:
        files = files[:args.limit]

    print(f"Starting batch evaluation on {len(files)} images from: {args.dir}...")
    records = []
    valid_count = 0
    t0 = time.time()

    for idx, fpath in enumerate(files):
        res = pipeline.process(fpath, conf_threshold=args.conf)
        is_val = res["is_valid"]
        if is_val:
            valid_count += 1
        name = os.path.basename(fpath)
        print(f"[{idx+1}/{len(files)}] {name[:30]:30} -> {res['container_number']:11} | Valid: {str(is_val):5} | {res['elapsed_time_ms']}ms")
        records.append({
            "image": name,
            "container_number": res["container_number"],
            "is_valid": is_val,
            "repaired": res["repaired"],
            "regions": len(res["detected_regions"]),
            "owner": res["owner_name"],
            "size_type": res["size_type_code"],
            "latency_ms": res["elapsed_time_ms"]
        })

    total_time = time.time() - t0
    df = pd.DataFrame(records)
    accuracy = (valid_count / len(files) * 100) if files else 0

    print("\n" + "=" * 55)
    print("BATCH BENCHMARK SUMMARY")
    print("=" * 55)
    print(f"Total Evaluated    : {len(files)}")
    print(f"ISO Valid Found    : {valid_count} ({accuracy:.1f}%)")
    print(f"Total Elapsed Time : {total_time:.2f}s (Avg: {total_time/len(files)*1000:.1f} ms/img)")
    print("=" * 55)

    if args.output:
        df.to_csv(args.output, index=False)
        print(f"Saved results to: {args.output}")


def cmd_validate(args):
    """Validates an ISO 6346 container code."""
    code = args.code.strip().upper()
    print(f"Validating Container Code: '{code}'...")
    if len(code) == 10:
        chk = calculate_check_digit(code)
        print(f"Calculated Check Digit: {chk}")
        print(f"Full 11-char code: {code}{chk}")
    elif len(code) == 11:
        is_valid, exp = validate_container_number(code)
        info = parse_container_info(code)
        print(f"Valid ISO 6346: {is_valid}")
        print(f"Expected Check Digit: {exp}")
        print(f"Owner: {info['owner_name']}")
        print(f"Category: {info['category_description']}")
    else:
        print("Code must be 10 or 11 characters.")

    step_info = get_step_by_step_calculation(code[:10])
    if step_info:
        print("\nStep-by-step Modulo 11 Breakdown:")
        for s in step_info["steps"]:
            print(f"  Pos {s['position']}: '{s['char']}' (val {s['value']:2}) x {s['weight']:11} = {s['product']}")
        print(f"Total Sum: {step_info['total_sum']} -> Modulo 11: {step_info['modulo_11']} -> Check Digit: {step_info['check_digit']}")


def cmd_train(args):
    """Fine-tunes the YOLO container detector."""
    from ultralytics import YOLO

    base_model = args.model or "yolo11n.pt"
    print(f"Starting training from: {base_model}")
    print(f"Epochs: {args.epochs}, Batch: {args.batch}, Fraction: {args.fraction}, Imgsz: {args.imgsz}")

    model = YOLO(base_model)
    results = model.train(
        data="data.yaml",
        epochs=args.epochs,
        batch=args.batch,
        fraction=args.fraction,
        imgsz=args.imgsz,
        device="cpu",
        name="container_detector",
        project="models",
        exist_ok=True
    )

    print("Training finished successfully!")
    weights_path = "models/container_detector/weights/best.pt"
    if os.path.exists(weights_path):
        os.makedirs("weights", exist_ok=True)
        import shutil
        shutil.copy(weights_path, "weights/container_detector.pt")
        print("Updated weights/container_detector.pt!")


def main():
    parser = argparse.ArgumentParser(description="ContainerLens: ISO 6346 Container Number Recognition Tool")
    subparsers = parser.add_subparsers(dest="command", help="Available subcommands")

    # Predict
    p_pred = subparsers.add_parser("predict", help="Predict container number from an image")
    p_pred.add_argument("--image", required=True, help="Path to container image file")
    p_pred.add_argument("--weights", default="weights/container_detector.pt", help="Path to YOLO weights")
    p_pred.add_argument("--conf", type=float, default=0.20, help="Detection confidence threshold")
    p_pred.add_argument("--padding", type=float, default=0.08, help="Region crop padding fraction")
    p_pred.add_argument("--no-detector", action="store_true", help="Disable YOLO detector (direct OCR)")
    p_pred.add_argument("--output", help="Path to save JSON result")
    p_pred.add_argument("--save-image", help="Path to save annotated image")

    # Batch
    p_batch = subparsers.add_parser("batch", help="Batch evaluation on image directory")
    p_batch.add_argument("--dir", default="test/images", help="Directory of images")
    p_batch.add_argument("--weights", default="weights/container_detector.pt", help="Path to YOLO weights")
    p_batch.add_argument("--limit", type=int, default=20, help="Maximum number of images to test")
    p_batch.add_argument("--conf", type=float, default=0.20, help="Detection confidence threshold")
    p_batch.add_argument("--output", default="batch_results.csv", help="Output CSV path")

    # Validate
    p_val = subparsers.add_parser("validate", help="Validate container number using ISO 6346 formula")
    p_val.add_argument("--code", required=True, help="10 or 11 character container code")

    # Train
    p_train = subparsers.add_parser("train", help="Train / fine-tune YOLO model")
    p_train.add_argument("--model", default="yolo11n.pt", help="Base model weights")
    p_train.add_argument("--epochs", type=int, default=5, help="Number of training epochs")
    p_train.add_argument("--batch", type=int, default=16, help="Batch size")
    p_train.add_argument("--fraction", type=float, default=0.08, help="Dataset fraction (0.01 to 1.0)")
    p_train.add_argument("--imgsz", type=int, default=416, help="Image size")

    args = parser.parse_args()
    if args.command == "predict":
        cmd_predict(args)
    elif args.command == "batch":
        cmd_batch(args)
    elif args.command == "validate":
        cmd_validate(args)
    elif args.command == "train":
        cmd_train(args)
    else:
        parser.print_help()


if __name__ == "__main__":
    main()
