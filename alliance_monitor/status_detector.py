"""
Online Status Detector for Whiteout Survival

Detects online status by reading green "Online" text using OCR
instead of looking for green dots.
"""

import cv2
import numpy as np
import pytesseract
from typing import List, Tuple, Optional
from PIL import Image
from .monitor_config import MonitorConfig


class OnlineStatusDetector:
    """Detects online status using OCR and green text detection"""
    
    def __init__(self):
        # Set Tesseract path
        if MonitorConfig.TESSERACT_PATH:
            pytesseract.pytesseract.tesseract_cmd = MonitorConfig.TESSERACT_PATH
        
        # HSV color range for green text
        self.lower_green = np.array(MonitorConfig.GREEN_HSV_LOWER)
        self.upper_green = np.array(MonitorConfig.GREEN_HSV_UPPER)
    
    def has_green_text(self, image: np.ndarray, x: int, y: int, width: int, height: int) -> bool:
        """
        Check if region contains green text (indicating "Online" status)
        
        Args:
            image: Full screenshot (BGR format)
            x, y: Top-left corner of region
            width, height: Size of region
            
        Returns:
            True if green text detected, False otherwise
        """
        # Extract region of interest
        roi = image[y:y+height, x:x+width]
        
        if roi.size == 0:
            return False
        
        # Convert to HSV
        hsv = cv2.cvtColor(roi, cv2.COLOR_BGR2HSV)
        
        # Create mask for green color
        mask = cv2.inRange(hsv, self.lower_green, self.upper_green)
        
        # Count green pixels
        green_pixels = cv2.countNonZero(mask)
        total_pixels = width * height
        
        # If more than 5% of pixels are green, likely has "Online" text
        green_ratio = green_pixels / total_pixels
        return green_ratio > 0.05
    
    def read_status_text(self, image: np.ndarray, x: int, y: int, width: int, height: int) -> str:
        """
        Read the status text from a region using OCR
        
        Args:
            image: Full screenshot (BGR format)
            x, y: Top-left corner of region
            width, height: Size of region
            
        Returns:
            Extracted text (lowercase, cleaned)
        """
        # Extract region
        roi = image[y:y+height, x:x+width]
        
        if roi.size == 0:
            return ""
        
        # Convert to grayscale
        gray = cv2.cvtColor(roi, cv2.COLOR_BGR2GRAY)
        
        # Apply thresholding to make text clearer
        _, thresh = cv2.threshold(gray, 0, 255, cv2.THRESH_BINARY + cv2.THRESH_OTSU)
        
       # Convert to PIL Image for Tesseract
        pil_image = Image.fromarray(thresh)
        
        # Perform OCR
        try:
            text = pytesseract.image_to_string(
                pil_image,
                config='--psm 7 --oem 3'  # Single line mode
            )
            
            # Clean text
            text = text.strip().lower()
            return text
            
        except Exception as e:
            return ""
    
    def detect_all_rows(self, image: np.ndarray) -> List[bool]:
        """
        Detect online status for all visible rows (2 columns per row)
        
        Args:
            image: Full screenshot (BGR format)
            
        Returns:
            List of booleans for each player (left column first, then right)
        """
        results = []
        
        for row_idx in range(MonitorConfig.MAX_VISIBLE_ROWS):
            # Check LEFT column player
            x, y, width, height = MonitorConfig.get_green_text_coords_left(row_idx)
            
            # Check if region is within image bounds
            if y + height <= image.shape[0]:
                # Check for green text first (faster)
                is_online_left = self.has_green_text(image, x, y, width, height)
                
                # Optionally verify with OCR for accuracy
                if is_online_left:
                    text = self.read_status_text(image, x, y, width, height)
                    # Double-check if "online" is in the text
                    is_online_left = "online" in text
                
                results.append(is_online_left)
            
            # Check RIGHT column player
            x, y, width, height = MonitorConfig.get_green_text_coords_right(row_idx)
            
            # Check if region is within image bounds
            if y + height <= image.shape[0]:
                # Check for green text
                is_online_right = self.has_green_text(image, x, y, width, height)
                
                # Verify with OCR
                if is_online_right:
                    text = self.read_status_text(image, x, y, width, height)
                    is_online_right = "online" in text
                
                results.append(is_online_right)
        
        return results
    
    def visualize_detection(self, image: np.ndarray, save_path: Optional[str] = None) -> np.ndarray:
        """
        Create a visualization of detection regions
        """
        vis_image = image.copy()
        
        for row_idx in range(MonitorConfig.MAX_VISIBLE_ROWS):
            # LEFT column
            x, y, w, h = MonitorConfig.get_green_text_coords_left(row_idx)
            if y + h <= image.shape[0]:
                is_online = self.has_green_text(image, x, y, w, h)
                color = (0, 255, 0) if is_online else (0, 0, 255) # Green if online, Red if offline
                cv2.rectangle(vis_image, (x, y), (x + w, y + h), color, 2)
                cv2.putText(vis_image, "L", (x, y-5), cv2.FONT_HERSHEY_SIMPLEX, 0.5, color, 1)
            
            # RIGHT column
            x, y, w, h = MonitorConfig.get_green_text_coords_right(row_idx)
            if y + h <= image.shape[0]:
                is_online = self.has_green_text(image, x, y, w, h)
                color = (0, 255, 0) if is_online else (0, 0, 255)
                cv2.rectangle(vis_image, (x, y), (x + w, y + h), color, 2)
                cv2.putText(vis_image, "R", (x, y-5), cv2.FONT_HERSHEY_SIMPLEX, 0.5, color, 1)
        
        if save_path:
            cv2.imwrite(save_path, vis_image)
        return vis_image


# Test function
if __name__ == "__main__":
    print("Testing Online Status Detector...")
    
    import os
    if os.path.exists("test_screenshot.png"):
        img = cv2.imread("test_screenshot.png")
        
        detector = OnlineStatusDetector()
        
        # Detect all rows
        results = detector.detect_all_rows(img)
        print(f"\n✓ Detection results for {len(results)} players:")
        for i, is_online in enumerate(results):
            status = "🟢 ONLINE" if is_online else "⚪ OFFLINE"
            column = "LEFT" if i % 2 == 0 else "RIGHT"
            row = i // 2
            print(f"  Row {row}, {column} column: {status}")
        
        # Create visualization
        vis = detector.visualize_detection(img, "detection_visualization.png")
        print("\n✓ Visualization saved to detection_visualization.png")
    else:
        print("✗ No test screenshot found!")
        print("Run capture.py first to create test_screenshot.png")
