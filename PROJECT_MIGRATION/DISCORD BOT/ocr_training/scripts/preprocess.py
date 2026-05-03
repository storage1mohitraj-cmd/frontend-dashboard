"""
Preprocessing Script for Whiteout Survival OCR Training
Prepares labeled data for PaddleOCR training.
"""

import cv2
import numpy as np
import random
import shutil
from pathlib import Path


def preprocess_image(img, target_height=48, target_width=320):
    """
    Preprocess image for OCR training:
    - Resize to fixed height while maintaining aspect ratio
    - Pad to fixed width
    - Normalize colors
    """
    h, w = img.shape[:2]
    
    # Calculate new width maintaining aspect ratio
    new_w = int(w * target_height / h)
    
    # Resize
    if new_w > target_width:
        new_w = target_width
    
    resized = cv2.resize(img, (new_w, target_height))
    
    # Create padded image (white background)
    padded = np.ones((target_height, target_width, 3), dtype=np.uint8) * 255
    padded[:, :new_w] = resized
    
    return padded


def augment_image(img):
    """
    Apply random augmentations:
    - Slight rotation
    - Brightness variation
    - Optional blur
    """
    h, w = img.shape[:2]
    
    # Random rotation (-3 to 3 degrees)
    if random.random() < 0.5:
        angle = random.uniform(-3, 3)
        M = cv2.getRotationMatrix2D((w/2, h/2), angle, 1.0)
        img = cv2.warpAffine(img, M, (w, h), borderValue=(255, 255, 255))
    
    # Random brightness
    if random.random() < 0.5:
        factor = random.uniform(0.8, 1.2)
        img = np.clip(img * factor, 0, 255).astype(np.uint8)
    
    # Random blur
    if random.random() < 0.1:
        img = cv2.GaussianBlur(img, (3, 3), 0)
    
    return img


def prepare_training_data(labels_file, output_dir, val_split=0.2, augment=True):
    """
    Prepare training and validation datasets from labels file.
    
    Args:
        labels_file: Path to labels.txt (image_path\tlabel format)
        output_dir: Base output directory (will create train/ and val/ subdirs)
        val_split: Fraction of data for validation
        augment: Whether to apply augmentation to training data
    """
    labels_path = Path(labels_file)
    output_path = Path(output_dir)
    
    train_dir = output_path / "train"
    val_dir = output_path / "val"
    train_dir.mkdir(parents=True, exist_ok=True)
    val_dir.mkdir(parents=True, exist_ok=True)
    
    # Read labels
    with open(labels_path, 'r', encoding='utf-8') as f:
        lines = [line.strip().split('\t') for line in f if '\t' in line]
    
    if not lines:
        print("No labels found!")
        return
    
    # Shuffle and split
    random.shuffle(lines)
    split_idx = int(len(lines) * (1 - val_split))
    train_data = lines[:split_idx]
    val_data = lines[split_idx:]
    
    print(f"Training samples: {len(train_data)}")
    print(f"Validation samples: {len(val_data)}")
    
    # Process training data
    train_labels = []
    for i, (img_path, label) in enumerate(train_data):
        img = cv2.imread(img_path)
        if img is None:
            continue
        
        # Preprocess
        processed = preprocess_image(img)
        
        # Save original
        out_name = f"train_{i:04d}.png"
        cv2.imwrite(str(train_dir / out_name), processed)
        train_labels.append(f"{out_name}\t{label}")
        
        # Create augmented versions
        if augment:
            for aug_idx in range(2):  # 2 augmented versions per image
                aug_img = augment_image(processed.copy())
                aug_name = f"train_{i:04d}_aug{aug_idx}.png"
                cv2.imwrite(str(train_dir / aug_name), aug_img)
                train_labels.append(f"{aug_name}\t{label}")
    
    # Process validation data (no augmentation)
    val_labels = []
    for i, (img_path, label) in enumerate(val_data):
        img = cv2.imread(img_path)
        if img is None:
            continue
        
        processed = preprocess_image(img)
        out_name = f"val_{i:04d}.png"
        cv2.imwrite(str(val_dir / out_name), processed)
        val_labels.append(f"{out_name}\t{label}")
    
    # Write label files
    with open(train_dir / "labels.txt", 'w', encoding='utf-8') as f:
        f.write('\n'.join(train_labels))
    
    with open(val_dir / "labels.txt", 'w', encoding='utf-8') as f:
        f.write('\n'.join(val_labels))
    
    print(f"\n✅ Prepared {len(train_labels)} training images (with augmentation)")
    print(f"✅ Prepared {len(val_labels)} validation images")
    print(f"   Output: {output_path}")


if __name__ == "__main__":
    script_dir = Path(__file__).parent.parent
    labels_file = script_dir / "data" / "labels.txt"
    output_dir = script_dir / "data"
    
    if not labels_file.exists():
        print(f"Labels file not found: {labels_file}")
        print("Run label_tool.py first to create labels.")
    else:
        prepare_training_data(labels_file, output_dir)
