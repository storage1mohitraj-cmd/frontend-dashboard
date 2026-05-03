"""
Auto Screenshot Cropper for Whiteout Survival OCR Training
Extracts individual player cards from full alliance screenshots.
"""

import cv2
import numpy as np
import os
from pathlib import Path


def detect_player_cards(image):
    """
    Detect all player cards using edge detection.
    The background is blue too, so we use edges to find card boundaries.
    Returns list of (x, y, w, h) bounding boxes.
    """
    gray = cv2.cvtColor(image, cv2.COLOR_BGR2GRAY)
    
    # Edge detection
    edges = cv2.Canny(gray, 50, 150)
    
    # Dilate edges to connect nearby lines
    kernel = np.ones((3, 3), np.uint8)
    edges_dilated = cv2.dilate(edges, kernel, iterations=2)
    
    # Find contours
    contours, _ = cv2.findContours(edges_dilated, cv2.RETR_EXTERNAL, cv2.CHAIN_APPROX_SIMPLE)
    
    # Filter by size and aspect ratio
    cards = []
    for contour in contours:
        x, y, w, h = cv2.boundingRect(contour)
        
        # Cards are roughly 200-230px wide, 80-120px tall
        if 100 < w < 300 and 50 < h < 150:
            aspect = w / h if h > 0 else 0
            # Cards are wider than tall (aspect 1.5-3.0)
            if 1.3 < aspect < 3.5:
                # Skip if too close to top (header area) or bottom (navigation)
                if y > 100 and y + h < image.shape[0] - 50:
                    cards.append((x, y, w, h))
    
    # Remove overlapping/duplicate detections
    cards = remove_overlapping(cards)
    
    # Sort top-to-bottom, left-to-right
    cards.sort(key=lambda c: (c[1] // 40, c[0]))
    return cards


def remove_overlapping(boxes, overlap_threshold=0.5):
    """Remove boxes that overlap significantly with larger boxes."""
    if not boxes:
        return []
    
    # Sort by area (largest first)
    boxes = sorted(boxes, key=lambda b: b[2] * b[3], reverse=True)
    keep = []
    
    for box in boxes:
        x1, y1, w1, h1 = box
        is_duplicate = False
        
        for kept in keep:
            x2, y2, w2, h2 = kept
            
            # Calculate intersection
            xi1 = max(x1, x2)
            yi1 = max(y1, y2)
            xi2 = min(x1 + w1, x2 + w2)
            yi2 = min(y1 + h1, y2 + h2)
            
            if xi1 < xi2 and yi1 < yi2:
                intersection = (xi2 - xi1) * (yi2 - yi1)
                area1 = w1 * h1
                if intersection / area1 > overlap_threshold:
                    is_duplicate = True
                    break
        
        if not is_duplicate:
            keep.append(box)
    
    return keep


def extract_name_region(card_img):
    """
    Extract just the name region from a player card.
    Improved padding for better OCR.
    """
    h, w = card_img.shape[:2]
    # Name is typically in right 65% of card, top 50%
    # Giving more space around the name helps PaddleOCR
    y1 = int(h * 0.05)
    y2 = int(h * 0.45)
    x1 = int(w * 0.32)
    x2 = int(w * 0.95)
    
    name_region = card_img[y1:y2, x1:x2]
    return name_region


def extract_status_region(card_img):
    """
    Extract the status region (below the avatar).
    This contains 'Online' or 'X min ago'.
    """
    h, w = card_img.shape[:2]
    # Status is below avatar (left side)
    # Avatar is roughly left 30%
    y1 = int(h * 0.65)
    y2 = int(h * 0.95)
    x1 = int(w * 0.02)
    x2 = int(w * 0.30)
    
    status_region = card_img[y1:y2, x1:x2]
    return status_region


def crop_cards_from_image(image_path, output_dir, start_idx=0):
    """
    Crop all player cards from a screenshot.
    """
    # Ignore debug files
    if image_path.name.startswith("debug_"):
        return 0
        
    img = cv2.imread(str(image_path))
    if img is None:
        return 0
    
    cards = detect_player_cards(img)
    print(f"  🔍 {image_path.name}: Found {len(cards)} cards")
    
    count = 0
    for i, (x, y, w, h) in enumerate(cards):
        card_img = img[y:y+h, x:x+w]
        name_region = extract_name_region(card_img)
        status_region = extract_status_region(card_img)
        
        if name_region.size > 0:
            card_path = output_dir / f"card_{start_idx + count:04d}.png"
            name_path = output_dir / f"name_{start_idx + count:04d}.png"
            status_path = output_dir / f"status_{start_idx + count:04d}.png"
            
            cv2.imwrite(str(card_path), card_img)
            cv2.imwrite(str(name_path), name_region)
            cv2.imwrite(str(status_path), status_region)
            count += 1
    
    return count


def process_all_screenshots(raw_dir, output_dir):
    """
    Process all screenshots in raw_dir and extract cards to output_dir.
    """
    raw_path = Path(raw_dir)
    output_path = Path(output_dir)
    output_path.mkdir(parents=True, exist_ok=True)
    
    total_cards = 0
    for img_file in sorted(raw_path.glob("*.png")):
        count = crop_cards_from_image(img_file, output_path, total_cards)
        total_cards += count
    
    print(f"\n✅ Total cards extracted: {total_cards}")
    print(f"   Output directory: {output_path}")
    return total_cards


if __name__ == "__main__":
    import sys
    
    # Default paths
    script_dir = Path(__file__).parent.parent
    raw_dir = script_dir / "data" / "raw"
    output_dir = script_dir / "data" / "cropped"
    
    print("=" * 50)
    print("Whiteout Survival Card Cropper")
    print("=" * 50)
    
    if not raw_dir.exists():
        print(f"Raw directory not found: {raw_dir}")
        sys.exit(1)
    
    process_all_screenshots(raw_dir, output_dir)
