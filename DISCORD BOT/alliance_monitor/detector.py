"""
Green Dot Detection Module

Uses OpenCV to detect green "online" dots in the screenshot.
Performs HSV color-based detection for each player row.
"""

import cv2
import numpy as np
from typing import List, Tuple, Optional
from .monitor_config import MonitorConfig


class OnlineDetector:
    """Detects online status using green dot detection"""
    
    def __init__(self):
        # HSV color range for green detection
        self.lower_green = np.array(MonitorConfig.GREEN_HSV_LOWER)
        self.upper_green = np.array(MonitorConfig.GREEN_HSV_UPPER)
        
        # HSV color range for BLUE CARD detection
        self.lower_blue = np.array(MonitorConfig.BLUE_CARD_HSV_LOWER)
        self.upper_blue = np.array(MonitorConfig.BLUE_CARD_HSV_UPPER)

    def get_blue_card_mask(self, image: np.ndarray) -> np.ndarray:
        """
        Get the binary mask for blue cards (Debug helper).
        """
        hsv = cv2.cvtColor(image, cv2.COLOR_BGR2HSV)
        mask = cv2.inRange(hsv, self.lower_blue, self.upper_blue)
        return mask

    def detect_player_cards(self, image: np.ndarray) -> List[Tuple[int, int, int, int]]:
        """
        Dynamically detect player cards in the image using Contour Detection.
        Returns a list of (x, y, w, h) sorted Top->Bottom, Left->Right.
        """
        # 1. Convert to HSV
        hsv = cv2.cvtColor(image, cv2.COLOR_BGR2HSV)
        
        # 2. Mask for Blue Cards
        mask = cv2.inRange(hsv, self.lower_blue, self.upper_blue)
        
        
        # 3. Clean up mask (Skipping morphology to maximize detection)
        # kernel = np.ones((3,3), np.uint8)
        # mask = cv2.morphologyEx(mask, cv2.MORPH_CLOSE, kernel)
        # mask = cv2.morphologyEx(mask, cv2.MORPH_OPEN, kernel) 
        
        # 4. Find Contours
        contours, _ = cv2.findContours(mask, cv2.RETR_EXTERNAL, cv2.CHAIN_APPROX_SIMPLE)
        
        valid_cards = []
        for cnt in contours:
            x, y, w, h = cv2.boundingRect(cnt)
            
            # Filter by size
            # Relaxed constraints to ensure we catch cards even if imperfectly masked
            if w > 100 and h > 60:
                valid_cards.append((x, y, w, h))
        
        # 5. Sort: Top to Bottom, then Left to Right
        # We allow a small 'y' tolerance to group items in the same row
        valid_cards.sort(key=lambda b: (b[1] // 20, b[0])) 
        
        return valid_cards

    def detect_status_in_card(self, image: np.ndarray, card_rect: Tuple[int, int, int, int]) -> bool:
        """
        Check if a player is online using Relative Coordinates within the card.
        """
        cx, cy, cw, ch = card_rect
        
        # Get relative offset
        off = MonitorConfig.STATUS_OCR_OFFSET
        
        # Calculate absolute position
        abs_x = cx + off['x']
        abs_y = cy + off['y']
        
        return self.detect_green_in_region(image, abs_x, abs_y, off['width'], off['height'])

    def detect_green_in_region(self, image: np.ndarray, x: int, y: int, width: int, height: int) -> bool:
        """
        Detect if there's a green blob in the specified region
        
        Args:
            image: Full screenshot (BGR format)
            x, y: Top-left corner of region
            width, height: Size of region
            
        Returns:
            True if green dot detected, False otherwise
        """
        # Extract region of interest
        roi = image[y:y+height, x:x+width]
        
        if roi.size == 0:
            return False
        
        # Convert to HSV color space
        hsv = cv2.cvtColor(roi, cv2.COLOR_BGR2HSV)
        
        # Create mask for green color
        mask = cv2.inRange(hsv, self.lower_green, self.upper_green)
        
        # Find contours in the mask
        contours, _ = cv2.findContours(mask, cv2.RETR_EXTERNAL, cv2.CHAIN_APPROX_SIMPLE)
        
        # Check if any contour is large enough
        for contour in contours:
            area = cv2.contourArea(contour)
            if area >= MonitorConfig.MIN_GREEN_BLOB_AREA:
                return True
        
        return False
    
    def detect_all_rows(self, image: np.ndarray) -> List[bool]:
        """
        Detect online status for all visible rows (both left and right columns)
        
        Args:
            image: Full screenshot (BGR format)
            
        Returns:
            List of booleans (True = online, False = offline) for each player slot
        """
        results = []
        
        for row_idx in range(MonitorConfig.MAX_VISIBLE_ROWS):
            # LEFT column player
            x, y, width, height = MonitorConfig.get_green_text_coords_left(row_idx)
            
            # Check if region is within image bounds
            if y + height <= image.shape[0]:
                is_online = self.detect_green_in_region(image, x, y, width, height)
                results.append(is_online)
            
            # RIGHT column player
            x, y, width, height = MonitorConfig.get_green_text_coords_right(row_idx)
            
            # Check if region is within image bounds
            if y + height <= image.shape[0]:
                is_online = self.detect_green_in_region(image, x, y, width, height)
                results.append(is_online)
        
        return results
    
    def visualize_detection(self, image: np.ndarray, save_path: Optional[str] = None) -> np.ndarray:
        """
        Create a visualization of detection regions (for debugging/calibration)
        
        Args:
            image: Full screenshot (BGR format)
            save_path: Optional path to save the visualization
            
        Returns:
            Annotated image
        """
        # Create a copy to draw on
        vis_image = image.copy()
        
        for row_idx in range(MonitorConfig.MAX_VISIBLE_ROWS):
            x, y, width, height = MonitorConfig.get_green_dot_coords(row_idx)
            
            # Check if region is within image bounds
            if y + height > image.shape[0]:
                break
            
            # Detect green in this region
            is_online = self.detect_green_in_region(image, x, y, width, height)
            
            # Draw rectangle around detection region
            color = (0, 255, 0) if is_online else (0, 0, 255)  # Green if online, red if offline
            cv2.rectangle(vis_image, (x, y), (x + width, y + height), color, 2)
            
            # Add label
            label = "ONLINE" if is_online else "OFFLINE"
            cv2.putText(vis_image, label, (x, y - 5), cv2.FONT_HERSHEY_SIMPLEX, 0.5, color, 2)
        
        if save_path:
            cv2.imwrite(save_path, vis_image)
            print(f"Visualization saved to {save_path}")
        
        return vis_image
    
    def get_green_mask(self, image: np.ndarray) -> np.ndarray:
        """
        Get the green color mask for the entire image (for debugging)
        
        Args:
            image: Full screenshot (BGR format)
            
        Returns:
            Binary mask showing detected green regions
        """
        hsv = cv2.cvtColor(image, cv2.COLOR_BGR2HSV)
        mask = cv2.inRange(hsv, self.lower_green, self.upper_green)
        return mask
    
    def adjust_hsv_range(self, lower: Tuple[int, int, int], upper: Tuple[int, int, int]):
        """
        Adjust HSV range for green detection (for calibration)
        
        Args:
            lower: Lower HSV bound (H, S, V)
            upper: Upper HSV bound (H, S, V)
        """
        self.lower_green = np.array(lower)
        self.upper_green = np.array(upper)
        print(f"Updated HSV range: {lower} - {upper}")


# Test function
if __name__ == "__main__":
    print("Testing Green Dot Detector Module...")
    
    # Try to load a test screenshot
    import os
    if os.path.exists("test_screenshot.png"):
        img = cv2.imread("test_screenshot.png")
        
        detector = OnlineDetector()
        
        # Detect all rows
        results = detector.detect_all_rows(img)
        print(f"\n✓ Detection results for {len(results)} rows:")
        for i, is_online in enumerate(results):
            status = "🟢 ONLINE" if is_online else "⚪ OFFLINE"
            print(f"  Row {i}: {status}")
        
        # Create visualization
        vis = detector.visualize_detection(img, "detection_visualization.png")
        print("\n✓ Visualization saved to detection_visualization.png")
        
        # Show green mask
        mask = detector.get_green_mask(img)
        cv2.imwrite("green_mask.png", mask)
        print("✓ Green mask saved to green_mask.png")
        
    else:
        print("✗ No test screenshot found!")
        print("Run capture.py first to create test_screenshot.png")
