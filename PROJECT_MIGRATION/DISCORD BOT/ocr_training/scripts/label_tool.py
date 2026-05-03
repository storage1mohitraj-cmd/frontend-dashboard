"""
Interactive Labeling Tool for Whiteout Survival OCR Training
Displays cropped name regions and lets user type the correct text.
"""

import cv2
import os
import numpy as np
from pathlib import Path


def label_images(cropped_dir, output_file):
    """
    Interactive labeling: show each name image, user types the label.
    Saves labels in PaddleOCR format: image_path\tlabel
    """
    cropped_path = Path(cropped_dir)
    output_path = Path(output_file)
    
    # Find all name images (not full cards)
    name_images = sorted(cropped_path.glob("name_*.png"))
    
    if not name_images:
        print("No name images found! Run crop_cards.py first.")
        return
    
    print("=" * 50)
    print("Whiteout Survival OCR Labeling Tool")
    print("=" * 50)
    print(f"Found {len(name_images)} images to label")
    print("\nInstructions:")
    print("  - Type the player name exactly as shown")
    print("  - Press ENTER to submit")
    print("  - Type 'SKIP' to skip an image")
    print("  - Type 'QUIT' to save and exit")
    print("  - Type 'BACK' to go back one image")
    print("=" * 50)
    
    labels = []
    i = 0
    
    while i < len(name_images):
        img_path = name_images[i]
        img = cv2.imread(str(img_path))
        
        if img is None:
            print(f"Could not read: {img_path}")
            i += 1
            continue
        
        # Display the image
        cv2.imshow("Name Region - Type the name", img)
        cv2.waitKey(100)  # Brief pause to ensure window updates
        
        # Get user input
        print(f"\n[{i+1}/{len(name_images)}] {img_path.name}")
        label = input("  Player name: ").strip()
        
        if label.upper() == "QUIT":
            print("Saving and exiting...")
            break
        elif label.upper() == "SKIP":
            print("  Skipped.")
            i += 1
            continue
        elif label.upper() == "BACK":
            if i > 0:
                i -= 1
                if labels:
                    labels.pop()
            continue
        elif label:
            # Save label
            labels.append((str(img_path.absolute()), label))
            print(f"  ✓ Saved: {label}")
            i += 1
        else:
            print("  Empty label, try again.")
    
    cv2.destroyAllWindows()
    
    # Write labels file
    with open(output_path, 'w', encoding='utf-8') as f:
        for img_path, label in labels:
            f.write(f"{img_path}\t{label}\n")
    
    print(f"\n✅ Saved {len(labels)} labels to {output_path}")
    return labels


def auto_label_with_paddleocr(cropped_dir, output_file):
    """
    Auto-label using PaddleOCR as initial guess, then allow corrections.
    """
    import os
    import subprocess
    from paddleocr import PaddleOCR
    
    cropped_path = Path(cropped_dir)
    output_path = Path(output_file)
    
    # Load existing labels if any
    existing_labels = {}
    if output_path.exists():
        with open(output_path, 'r', encoding='utf-8') as f:
            for line in f:
                if '\t' in line:
                    path, lbl = line.strip().split('\t')
                    existing_labels[path] = lbl
    
    name_images = sorted(cropped_path.glob("name_*.png"))
    if not name_images:
        print("No name images found!")
        return
    
    print(f"Loaded {len(existing_labels)} existing labels.")
    
    print("Initializing PaddleOCR for auto-labeling...")
    # Using basic initialization to avoid argument errors with this version
    ocr = PaddleOCR(lang='ch')
    
    labels = list(existing_labels.items())
    
    print(f"\nAuto-labeling {len(name_images)} images...")
    # ... (instructions)
    
    for i, img_path in enumerate(name_images):
        full_path = str(img_path.absolute())
        if full_path in existing_labels:
            continue  # Already labeled
            
        img = cv2.imread(str(img_path))
        if img is None:
            continue
        
        # Upscale for better OCR
        h, w = img.shape[:2]
        img_large = cv2.resize(img, (w*3, h*3), interpolation=cv2.INTER_CUBIC)
        
        # Get OCR prediction
        try:
            result = ocr.ocr(img_large)
            
            # Robust extraction logic for different PaddleOCR/PaddleX versions
            predicted = ""
            
            def find_text(obj):
                """Recursively find and join all text strings."""
                texts = []
                if isinstance(obj, str):
                    t = obj.strip()
                    if len(t) > 1 and t.lower() not in ['lv', 'lv.', 'lv:']:
                        return [t]
                    return []
                
                if isinstance(obj, (list, tuple)):
                    for item in obj:
                        texts.extend(find_text(item))
                elif isinstance(obj, dict):
                    # Check common keys
                    for key in ['rec_texts', 'text', 'str_res']:
                        if key in obj:
                            texts.extend(find_text(obj[key]))
                    if not texts:
                        for v in obj.values():
                            texts.extend(find_text(v))
                elif hasattr(obj, 'rec_texts'):
                    texts.extend(find_text(obj.rec_texts))
                
                return texts

            all_words = find_text(result)
            if all_words:
                # Remove duplicates while preserving order
                seen = set()
                unique_words = [x for x in all_words if not (x in seen or seen.add(x))]
                predicted = " ".join(unique_words)
        except Exception as e:
            print(f"  ⚠️ OCR Error: {e}")
            predicted = ""
        
        # Clean up obvious junk
        if predicted.lower() in ['n', 'v', '(', ')', '11', 'l', '|', 'lv']:
            predicted = ""
        
        # Also get the corresponding card and status images
        card_path = img_path.parent / img_path.name.replace("name_", "card_")
        status_path = img_path.parent / img_path.name.replace("name_", "status_")
        display_path = card_path if card_path.exists() else img_path
        
        # Detect Online Status (Green color check)
        status_str = "Offline"
        if status_path.exists():
            status_img = cv2.imread(str(status_path))
            if status_img is not None:
                # Green color mask (same as bot's live scanner)
                hsv_status = cv2.cvtColor(status_img, cv2.COLOR_BGR2HSV)
                lower_green = np.array([35, 80, 80])
                upper_green = np.array([85, 255, 255])
                mask_green = cv2.inRange(hsv_status, lower_green, upper_green)
                if np.sum(mask_green > 0) > 10:  # If enough green pixels found
                    status_str = "Online"

        # Open image in default viewer (Windows)
        print(f"\n[{i+1}/{len(name_images)}]")
        print(f"  📁 File: {img_path.name}")
        print(f"  🔮 Predicted Name: '{predicted}'")
        print(f"  🔋 Status: {status_str}")
        
        # Open in default viewer
        try:
            os.startfile(str(display_path))
        except:
            # Fallback to cv2
            cv2.imshow("Card Image", cv2.imread(str(display_path)))
            cv2.waitKey(100)
        
        correction = input("  ✏️  Accept (ENTER) or type correction: ").strip()
        
        if correction.upper() == "QUIT":
            break
        elif correction.upper() == "SKIP":
            print("  ⏭️  Skipped")
            continue
        
        final_label = correction if correction else predicted
        if final_label and len(final_label) >= 1:
            labels.append((full_path, final_label))
            print(f"  ✅ Saved: '{final_label}'")
            
            # Save incrementally to prevent data loss
            with open(output_path, 'a', encoding='utf-8') as f:
                f.write(f"{full_path}\t{final_label}\n")
    
    cv2.destroyAllWindows()
    
    print(f"\n{'='*60}")
    print(f"✅ Finished! Labels saved to {output_path}")
    print(f"{'='*60}")


if __name__ == "__main__":
    script_dir = Path(__file__).parent.parent
    cropped_dir = script_dir / "data" / "cropped"
    labels_file = script_dir / "data" / "labels.txt"
    
    print("Choose labeling mode:")
    print("  1. Manual labeling (type each name)")
    print("  2. Auto-label with PaddleOCR (review/correct)")
    
    choice = input("\nEnter 1 or 2: ").strip()
    
    if choice == "1":
        label_images(cropped_dir, labels_file)
    elif choice == "2":
        auto_label_with_paddleocr(cropped_dir, labels_file)
    else:
        print("Invalid choice. Running manual labeling...")
        label_images(cropped_dir, labels_file)
