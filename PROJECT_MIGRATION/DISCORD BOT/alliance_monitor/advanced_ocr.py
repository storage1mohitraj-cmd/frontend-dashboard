"""
Advanced OCR Module with PaddleOCR
Uses state-of-the-art deep learning OCR for maximum accuracy
"""

import cv2
import numpy as np
from paddleocr import PaddleOCR
from typing import List, Tuple, Optional, Dict


class AdvancedOCR:
    """
    Dynamic OCR using PaddleOCR (deep learning).
    Detects blue player cards and extracts text from each card.
    Works regardless of scroll position!
    """
    
    def __init__(self):
        # Using 'ch' (Chinese) handles both English and Chinese characters perfectly
        # It handles names like 'saleh' and Special Symbols/Characters well.
        try:
            # Note: Removed show_log and use_angle_cls here as they cause errors 
            # in some PaddleOCR versions. Basic init is most stable.
            self.ocr = PaddleOCR(lang='ch')
        except Exception as e:
            print(f"DEBUG: PaddleOCR Init Error: {e}")
            self.ocr = PaddleOCR(lang='en')
    
    def detect_blue_cards(self, image: np.ndarray) -> List[Tuple[int, int, int, int]]:
        """
        Dynamically detect all blue player cards in the image.
        Uses edge detection for better accuracy on varying resolutions.
        """
        gray = cv2.cvtColor(image, cv2.COLOR_BGR2GRAY)
        
        # Edge detection helps find card boundaries when background is also blue
        edges = cv2.Canny(gray, 50, 150)
        
        # Dilate edges to connect nearby lines
        kernel = np.ones((3, 3), np.uint8)
        edges_dilated = cv2.dilate(edges, kernel, iterations=2)
        
        # Find contours
        contours, _ = cv2.findContours(edges_dilated, cv2.RETR_EXTERNAL, cv2.CHAIN_APPROX_SIMPLE)
        
        # Find valid cards by size and aspect ratio
        cards = []
        for contour in contours:
            x, y, w, h = cv2.boundingRect(contour)
            
            # Filter: cards are approximately 200-240px wide, 80-130px tall
            if 150 < w < 350 and 60 < h < 180:
                aspect = w / h if h > 0 else 0
                if 1.5 < aspect < 3.5:
                    # Skip header/footer regions
                    if y > 80 and y + h < image.shape[0] - 50:
                        cards.append((x, y, w, h))
        
        # Remove overlapping boxes
        cards = self._remove_overlapping(cards)
        
        # Sort by position: top to bottom, then left to right
        cards.sort(key=lambda c: (c[1] // 50, c[0]))
        return cards

    def _remove_overlapping(self, boxes: List[Tuple[int, int, int, int]], threshold=0.5):
        if not boxes: return []
        boxes = sorted(boxes, key=lambda b: b[2] * b[3], reverse=True)
        keep = []
        for box in boxes:
            is_dup = False
            for kept in keep:
                xi1, yi1 = max(box[0], kept[0]), max(box[1], kept[1])
                xi2, yi2 = min(box[0] + box[2], kept[0] + kept[2]), min(box[1] + box[3], kept[1] + kept[3])
                if xi1 < xi2 and yi1 < yi2:
                    intersection = (xi2 - xi1) * (yi2 - yi1)
                    if intersection / (box[2] * box[3]) > threshold:
                        is_dup = True; break
            if not is_dup: keep.append(box)
        return keep

    def extract_text_from_card(self, image: np.ndarray, card_rect: Tuple[int, int, int, int]) -> Dict[str, any]:
        """
        Extract player name and online status from a card region.
        """
        x, y, w, h = card_rect
        card_img = image[y:y+h, x:x+w]
        
        # Define Regions
        # 1. Name Region: Top-right 65% of card
        ny1, ny2 = int(h * 0.05), int(h * 0.45)
        nx1, nx2 = int(w * 0.35), int(w * 0.95)
        name_img = card_img[ny1:ny2, nx1:nx2]
        
        # 2. Status Region: Below avatar, left 30%
        sy1, sy2 = int(h * 0.65), int(h * 0.95)
        sx1, sx2 = int(w * 0.05), int(w * 0.35)
        status_img = card_img[sy1:sy2, sx1:sx2]
        
        # --- PLAYER NAME OCR ---
        name = ""
        if name_img.size > 0:
            # Upscale 3x for vastly improved OCR on small names
            name_large = cv2.resize(name_img, (name_img.shape[1]*3, name_img.shape[0]*3), interpolation=cv2.INTER_CUBIC)
            try:
                # Recognition only mode is faster and more accurate here
                # result = self.ocr.ocr(name_large, det=False)
                # But some versions error on det=False in ocr() call, so we use regular and parse
                result = self.ocr.ocr(name_large)
                name = self._parse_player_name(result)
            except Exception as e:
                print(f"DEBUG: OCR Error on name: {e}")

        # --- ONLINE STATUS DETECTION ---
        # Instead of just OCR, we use Color Masking + OCR for status
        is_online = self._check_online_status(status_img)
        
        return {
            'name': name or "Unknown",
            'online': is_online,
            'position': (x, y)
        }
    
    def _parse_player_name(self, ocr_result) -> str:
        """
        Robustly extract name, handling multi-word names (e.g., 'Twins Go').
        """
        if not ocr_result: return ""
        
        def find_text(obj):
            """Recursively find all text chunks, excluding garbage."""
            texts = []
            if isinstance(obj, str):
                t = obj.strip()
                # Ignore power values, time strings, and common garbage
                if len(t) > 1 and not any(kw in t.lower() for kw in ['lv', '.', 'm', 'k', 'ago', 'hour', 'min']):
                    if not (t.isdigit() and len(t) < 8):
                        return [t]
                return []
            
            if isinstance(obj, (list, tuple)):
                for item in obj:
                    texts.extend(find_text(item))
            elif isinstance(obj, dict):
                for key in ['rec_texts', 'text', 'str_res']:
                    if key in obj: texts.extend(find_text(obj[key]))
                if not texts:
                    for v in obj.values(): texts.extend(find_text(v))
            elif hasattr(obj, 'rec_texts'):
                texts.extend(find_text(obj.rec_texts))
            return texts

        all_words = find_text(ocr_result)
        if all_words:
            # Remove duplicates, preserve order
            seen = set()
            unique_words = [x for x in all_words if not (x in seen or seen.add(x))]
            # Join with space to support multi-word names
            name = " ".join(unique_words)
            return name
        
        return ""
    
    def _check_online_status(self, status_img: np.ndarray) -> bool:
        """
        Check if player is online using color detection for the green text/light.
        """
        if status_img.size == 0: return False
        
        # Convert to HSV
        hsv = cv2.cvtColor(status_img, cv2.COLOR_BGR2HSV)
        
        # Green color for "Online"
        lower_green = np.array([35, 80, 80])
        upper_green = np.array([85, 255, 255])
        mask_green = cv2.inRange(hsv, lower_green, upper_green)
        
        # If enough green pixels exist, they are definitely online
        green_count = np.sum(mask_green > 0)
        if green_count > 15:
            return True
            
        # Fallback: Check for "Online" text if color is ambiguous
        try:
            res = self.ocr.ocr(status_img)
            def has_online(obj):
                if isinstance(obj, str) and "online" in obj.lower(): return True
                if isinstance(obj, (list, tuple)):
                    return any(has_online(i) for i in obj)
                if isinstance(obj, dict):
                    return any(has_online(v) for v in obj.values())
                return False
            return has_online(res)
        except:
            return False
    
    def extract_all_players(self, image: np.ndarray) -> List[Dict[str, any]]:
        """
        Main method: Extract all players from a screenshot.
        """
        # Detect all cards
        cards = self.detect_blue_cards(image)
        
        players = []
        for card_rect in cards:
            player_data = self.extract_text_from_card(image, card_rect)
            
            # Only add if we got a valid-looking name
            name = player_data['name']
            if name and name != "Unknown" and len(name) > 1:
                players.append(player_data)
        
        return players
    
    def visualize_detection(self, image: np.ndarray, save_path: str = "detection_debug.png"):
        """
        Create visualization showing detected cards and text.
        Useful for debugging.
        """
        vis = image.copy()
        cards = self.detect_blue_cards(image)
        
        for i, (x, y, w, h) in enumerate(cards):
            # Draw card boundary (GREEN)
            cv2.rectangle(vis, (x, y), (x+w, y+h), (0, 255, 0), 2)
            
            # Draw label
            cv2.putText(vis, f"Card {i}", (x, y-5), 
                       cv2.FONT_HERSHEY_SIMPLEX, 0.5, (0, 255, 0), 2)
            
            # Extract and display name
            player_data = self.extract_text_from_card(image, (x, y, w, h))
            if player_data['name']:
                status = "ONLINE" if player_data['online'] else "OFFLINE"
                label = f"{player_data['name']} ({status})"
                cv2.putText(vis, label, (x, y+h+15), 
                           cv2.FONT_HERSHEY_SIMPLEX, 0.4, (255, 0, 0), 1)
        
        cv2.imwrite(save_path, vis)
        return vis

    def find_text_y(self, image: np.ndarray, target_text: str) -> Optional[int]:
        """
        Find the Y-coordinate of a specific text on screen using PaddleOCR.
        """
        pos = self.find_text_pos(image, target_text)
        return pos[1] if pos else None

    def find_text_pos(self, image: np.ndarray, target_text: str) -> Optional[Tuple[int, int]]:
        """
        Find the (X, Y) center of a specific text on screen.
        Useful for clicking buttons like 'Alliance', 'Members', etc.
        """
        try:
            result = self.ocr.ocr(image)
            if not result or not result[0]:
                return None
            
            target_lower = target_text.lower()
            
            for line in result[0]:
                try:
                    if len(line) >= 2:
                        bbox = line[0]
                        text_data = line[1]
                        if isinstance(text_data, (list, tuple)):
                            text, confidence = str(text_data[0]).lower(), float(text_data[1])
                        else:
                            text, confidence = str(text_data).lower(), 1.0
                        
                        # Match if target is in the detected text or vice versa
                        if confidence > 0.4 and (target_lower in text or text in target_lower):
                            bbox_array = np.array(bbox)
                            center_x = int(np.mean(bbox_array[:, 0]))
                            center_y = int(np.mean(bbox_array[:, 1]))
                            print(f"DEBUG: Found '{target_text}' at ({center_x}, {center_y})")
                            return (center_x, center_y)
                except:
                    continue
        except Exception as e:
            print(f"DEBUG: OCR Error in find_text_pos: {e}")
        
        return None
