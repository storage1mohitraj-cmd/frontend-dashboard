"""
Debug script to analyze HSV values in Whiteout Survival screenshots.
Helps calibrate the card detection for crop_cards.py
"""

import cv2
import numpy as np
from pathlib import Path


def analyze_hsv(image_path):
    """Analyze HSV values in an image and find card-like regions."""
    img = cv2.imread(str(image_path))
    if img is None:
        print(f"Could not read: {image_path}")
        return
    
    hsv = cv2.cvtColor(img, cv2.COLOR_BGR2HSV)
    height, width = img.shape[:2]
    
    print(f"\nAnalyzing: {image_path.name}")
    print(f"Image size: {width}x{height}")
    
    # Sample some regions known to contain cards (based on screenshot layout)
    # Cards appear in 2 columns, let's sample some specific areas
    sample_points = [
        # Left column cards (roughly x=10-220, y varies)
        (100, 200),
        (100, 300),
        (100, 400),
        # Right column cards (roughly x=260-470)
        (350, 200),
        (350, 300),
        (350, 400),
    ]
    
    print("\nHSV values at sample points:")
    for x, y in sample_points:
        if x < width and y < height:
            h, s, v = hsv[y, x]
            b, g, r = img[y, x]
            print(f"  ({x}, {y}): HSV=({h}, {s}, {v}), BGR=({b}, {g}, {r})")
    
    # Try different HSV ranges and count white pixels
    ranges_to_test = [
        ("Cyan/Light Blue", [80, 30, 120], [140, 255, 255]),
        ("Deep Blue", [100, 100, 100], [130, 255, 255]),
        ("Sky Blue", [85, 50, 150], [110, 200, 255]),
        ("White-ish Blue", [85, 20, 200], [120, 100, 255]),
        ("Very Light Blue", [90, 10, 200], [130, 80, 255]),
    ]
    
    print("\nMask coverage for different HSV ranges:")
    for name, lower, upper in ranges_to_test:
        mask = cv2.inRange(hsv, np.array(lower), np.array(upper))
        coverage = np.sum(mask > 0) / (width * height) * 100
        print(f"  {name}: {coverage:.1f}% white pixels")
        
        # Save debug mask
        debug_path = image_path.parent / f"debug_mask_{name.replace(' ', '_').replace('/', '_')}.png"
        cv2.imwrite(str(debug_path), mask)
    
    # Also try edge detection to find card boundaries
    gray = cv2.cvtColor(img, cv2.COLOR_BGR2GRAY)
    edges = cv2.Canny(gray, 50, 150)
    
    # Dilate edges to connect nearby lines
    kernel = np.ones((3, 3), np.uint8)
    edges_dilated = cv2.dilate(edges, kernel, iterations=2)
    
    # Find contours from edges
    contours, _ = cv2.findContours(edges_dilated, cv2.RETR_EXTERNAL, cv2.CHAIN_APPROX_SIMPLE)
    
    print(f"\nEdge-based detection found {len(contours)} contours")
    
    # Filter by size
    good_contours = []
    for cnt in contours:
        x, y, w, h = cv2.boundingRect(cnt)
        if 100 < w < 300 and 50 < h < 150:
            aspect = w / h if h > 0 else 0
            if 1.3 < aspect < 3.5:
                good_contours.append((x, y, w, h))
    
    print(f"After filtering: {len(good_contours)} card-like contours")
    
    # Draw debug visualization
    debug_img = img.copy()
    for x, y, w, h in good_contours:
        cv2.rectangle(debug_img, (x, y), (x+w, y+h), (0, 255, 0), 2)
    
    debug_path = image_path.parent / "debug_cards_detected.png"
    cv2.imwrite(str(debug_path), debug_img)
    print(f"Saved debug image: {debug_path}")


if __name__ == "__main__":
    script_dir = Path(__file__).parent.parent
    raw_dir = script_dir / "data" / "raw"
    
    # Analyze first image found
    for img_file in sorted(raw_dir.glob("*.png"))[:3]:
        analyze_hsv(img_file)
