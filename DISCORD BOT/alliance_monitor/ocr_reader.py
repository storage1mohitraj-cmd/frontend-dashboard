"""
OCR Module for Player Name Extraction

Uses Tesseract OCR to extract player names from screenshots.
Includes text cleaning and preprocessing for better accuracy.
"""

import cv2
import numpy as np
import pytesseract
from typing import List, Optional, Tuple
import re
from PIL import Image
from .monitor_config import MonitorConfig


class OCRReader:
    """Handles OCR for player name extraction"""
    
    def __init__(self):
        # Set Tesseract path if configured
        if MonitorConfig.TESSERACT_PATH:
            pytesseract.pytesseract.tesseract_cmd = MonitorConfig.TESSERACT_PATH
    
    def preprocess_for_ocr(self, image: np.ndarray) -> np.ndarray:
        """
        Preprocess card region optimized for WHITE text on BLUE background using HSV Masking.
        Pipeline: Upscale -> HSV Mask -> Invert -> Pad
        """
        # 1. Upscale by 3x (Tesseract loves large text)
        height, width = image.shape[:2]
        scaled = cv2.resize(image, (width * 3, height * 3), interpolation=cv2.INTER_CUBIC)
        
        # 2. Convert to HSV
        hsv = cv2.cvtColor(scaled, cv2.COLOR_BGR2HSV)
        
        # 3. Create Mask for White Text
        lower_white = np.array(MonitorConfig.WHITE_HSV_LOWER)
        upper_white = np.array(MonitorConfig.WHITE_HSV_UPPER)
        mask = cv2.inRange(hsv, lower_white, upper_white)
        
        # 4. Optional: Morphological operations to remove noise
        kernel = np.ones((2,2), np.uint8)
        mask = cv2.morphologyEx(mask, cv2.MORPH_CLOSE, kernel)
        
        # 5. Create final Black Text on White Background image
        # The mask makes white pixels 255 (white) and background 0 (black).
        # We want Black Text (0) on White Background (255).
        # So we just INVERT the mask.
        final_image = cv2.bitwise_not(mask)
        
        # 6. Add White Border (Padding)
        # Tesseract struggles with text touching the edge
        final_image = cv2.copyMakeBorder(
            final_image, 
            10, 10, 10, 10, 
            cv2.BORDER_CONSTANT, 
            value=255 # White
        )
            
        return final_image
    
    def clean_ocr_text(self, text: str) -> str:
        """
        Clean OCR output text
        
        Args:
            text: Raw OCR text
            
        Returns:
            Cleaned text
        """
        # Strip whitespace
        text = text.strip()
        
        # Remove junk characters
        for char in MonitorConfig.OCR_JUNK_CHARS:
            text = text.replace(char, '')
        
        # Remove extra whitespace
        text = ' '.join(text.split())
        
        # Remove non-alphanumeric characters except spaces and common game characters
        # Keep: letters, numbers, spaces, and some special chars like - _ .
        text = re.sub(r'[^\w\s\-\.]', '', text)
        
        return text
    
    def extract_name_from_region(self, image: np.ndarray, x: int, y: int, width: int, height: int) -> str:
        """
        Extract player name from a specific region
        
        Args:
            image: Full screenshot (BGR format)
            x, y: Top-left corner of region
            width, height: Size of region
            
        Returns:
            Extracted player name (cleaned)
        """
        # Extract region of interest
        roi = image[y:y+height, x:x+width]
        
        if roi.size == 0:
            return ""
        
        # Preprocess for OCR
        processed = self.preprocess_for_ocr(roi)
        
        # DEBUG: Save processed image to check what Tesseract sees
        # cv2.imwrite(f"debug_name_ocr_{x}_{y}.png", processed)
        
        # Convert to PIL Image for Tesseract
        pil_image = Image.fromarray(processed)
        
        # Perform OCR
        try:
            text = pytesseract.image_to_string(
                pil_image,
                config=MonitorConfig.TESSERACT_CONFIG
            )
            
            # Clean the text
            cleaned = self.clean_ocr_text(text)
            
            return cleaned
            
        except Exception as e:
            print(f"OCR error: {e}")
            return ""
    
    def find_rank_header_y(self, image: np.ndarray, rank_text: str) -> Optional[int]:
        """
        Scan for a Rank Header (e.g. "R4", "R3") on the left side and return its Y position.
        """
        # Crop to the left side where headers are (e.g. x=0 to x=100)
        h, w = image.shape[:2]
        left_strip = image[0:h, 0:100]
        
        # Preprocess for better text detection (simple threshold)
        gray = cv2.cvtColor(left_strip, cv2.COLOR_BGR2GRAY)
        _, thresh = cv2.threshold(gray, 200, 255, cv2.THRESH_BINARY)
        
        data = pytesseract.image_to_data(thresh, config="--psm 6", output_type="dict")
        
        for i, text in enumerate(data['text']):
            if rank_text.upper() in text.upper():
                return data['top'][i]
                
        return None

    def extract_name_from_card(self, image: np.ndarray, card_rect: Tuple[int, int, int, int]) -> str:
        """
        Extract name from a detected card using Relative Offsets.
        """
        cx, cy, cw, ch = card_rect
        off = MonitorConfig.NAME_OCR_OFFSET
        
        # Calculate absolute region
        # Use min/max to ensure we don't go out of bounds
        img_h, img_w = image.shape[:2]
        x = max(0, min(img_w - 1, cx + off['x']))
        y = max(0, min(img_h - 1, cy + off['y']))
        
        # Ensure width/height don't go off screen
        w = min(off['width'], img_w - x)
        h = min(off['height'], img_h - y)
        
        if w <= 0 or h <= 0:
            return ""
        
        return self.extract_name_from_region(image, x, y, w, h)

    def extract_all_names(self, image: np.ndarray) -> List[str]:
        """
        Extract player names from all visible rows (2 columns per row)
        
        Args:
            image: Full screenshot (BGR format)
            
        Returns:
            List of player names (left column first, then right, for each row)
        """
        names = []
        
        for row_idx in range(MonitorConfig.MAX_VISIBLE_ROWS):
            # LEFT column player
            x, y, width, height = MonitorConfig.get_name_ocr_coords_left(row_idx)
            
            # Check if region is within image bounds
            if y + height <= image.shape[0]:
                name = self.extract_name_from_region(image, x, y, width, height)
                
                # Only add non-empty names
                if name:
                    names.append(name)
            
            # RIGHT column player
            x, y, width, height = MonitorConfig.get_name_ocr_coords_right(row_idx)
            
            # Check if region is within image bounds
            if y + height <= image.shape[0]:
                name = self.extract_name_from_region(image, x, y, width, height)
                
                # Only add non-empty names
                if name:
                    names.append(name)
        
        return names
    
    def visualize_ocr_regions(self, image: np.ndarray, save_path: Optional[str] = None) -> np.ndarray:
        """
        Create a visualization of OCR regions with extracted text (for debugging)
        
        Args:
            image: Full screenshot (BGR format)
            save_path: Optional path to save the visualization
            
        Returns:
            Annotated image
        """
        # Create a copy to draw on
        vis_image = image.copy()
        
        for row_idx in range(MonitorConfig.MAX_VISIBLE_ROWS):
            # LEFT column
            x, y, width, height = MonitorConfig.get_name_ocr_coords_left(row_idx)
            
            # Check if region is within image bounds
            if y + height <= image.shape[0]:
                # Extract name
                name = self.extract_name_from_region(image, x, y, width, height)
                
                # Draw rectangle around OCR region
                cv2.rectangle(vis_image, (x, y), (x + width, y + height), (255, 0, 0), 2)
                
                # Add extracted text
                if name:
                    cv2.putText(
                        vis_image,
                        name,
                        (x, y - 10),
                        cv2.FONT_HERSHEY_SIMPLEX,
                        0.4,
                        (255, 0, 0),
                        1
                    )
            
            # RIGHT column
            x, y, width, height = MonitorConfig.get_name_ocr_coords_right(row_idx)
            
            # Check if region is within image bounds
            if y + height <= image.shape[0]:
                # Extract name
                name = self.extract_name_from_region(image, x, y, width, height)
                
                # Draw rectangle around OCR region
                cv2.rectangle(vis_image, (x, y), (x + width, y + height), (255, 0, 0), 2)
                
                # Add extracted text
                if name:
                    cv2.putText(
                        vis_image,
                        name,
                        (x, y - 10),
                        cv2.FONT_HERSHEY_SIMPLEX,
                        0.4,
                        (255, 0, 0),
                        1
                    )
        
        if save_path:
            cv2.imwrite(save_path, vis_image)
            print(f"OCR visualization saved to {save_path}")
        
        return vis_image
    
    def test_tesseract(self) -> bool:
        """
        Test if Tesseract is properly installed and accessible
        
        Returns:
            True if Tesseract is working, False otherwise
        """
        try:
            version = pytesseract.get_tesseract_version()
            print(f"Tesseract version: {version}")
            return True
        except Exception as e:
            print(f"Tesseract error: {e}")
            print(f"Please install Tesseract and update TESSERACT_PATH in monitor_config.py")
            return False


# Test function
if __name__ == "__main__":
    print("Testing OCR Reader Module...")
    
    ocr = OCRReader()
    
    # Test Tesseract installation
    if ocr.test_tesseract():
        print("✓ Tesseract is working")
        
        # Try to load a test screenshot
        import os
        if os.path.exists("test_screenshot.png"):
            img = cv2.imread("test_screenshot.png")
            
            # Extract all names
            names = ocr.extract_all_names(img)
            print(f"\n✓ Extracted {len(names)} names:")
            for i, name in enumerate(names):
                print(f"  Row {i}: '{name}'")
            
            # Create visualization
            vis = ocr.visualize_ocr_regions(img, "ocr_visualization.png")
            print("\n✓ OCR visualization saved to ocr_visualization.png")
            
        else:
            print("\n✗ No test screenshot found!")
            print("Run capture.py first to create test_screenshot.png")
    else:
        print("✗ Tesseract not working properly")
