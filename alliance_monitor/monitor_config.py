"""
Configuration for Alliance Online Status Monitor

All coordinates and parameters that may need calibration are centralized here.
Adjust these values based on your specific BlueStacks setup and screen layout.
"""

import os
from typing import Tuple


class MonitorConfig:
    """Configuration for alliance member monitoring"""
    
    # ========== BLUESTACKS SETTINGS ==========
    # Window title pattern to find BlueStacks
    WINDOW_TITLE_PATTERN = "BlueStacks App Player"
    
    
    # Expected resolution (BlueStacks should be set to 1280x720)
    # Current BlueStacks resolution detected: 446x766
    # Recommended to change BlueStacks to 1280x720 for best results
    EXPECTED_WIDTH = 558  
    EXPECTED_HEIGHT = 958  
    
    # ========== ADB SETTINGS ==========
    # ADB connection settings
    ADB_PATH = r"C:\adb\platform-tools\adb.exe"  # Full path to adb.exe
    ADB_HOST = "localhost"
    ADB_PORT = 5555  # Confirmed port 5555 is listening
    
    # Scroll coordinates (adjust based on your layout)
    # Scaled for the current window size (approx 558x958)
    SCROLL_START_X = 279  # Center of 558
    SCROLL_START_Y = 800  
    SCROLL_END_X = 279    
    SCROLL_END_Y = 300    
    
    # Randomization range for scroll coordinates (in pixels)
    SCROLL_RANDOMIZATION = 15
    
    # Scroll duration in milliseconds (higher = slower, more human-like)
    SCROLL_DURATION_MS = 350
    
    # ========== TIMING SETTINGS ==========
    # Delay between scroll actions (seconds)
    SCROLL_DELAY_MIN = 1.5
    SCROLL_DELAY_MAX = 3.0
    
    # Cooldown between full scans (seconds)
    SCAN_COOLDOWN_MIN = 600   # 10 minutes
    SCAN_COOLDOWN_MAX = 1200  # 20 minutes
    
    # ========== PLAYER LIST LAYOUT ==========
    # Recalibrated to fix vertical offset (Moving boxes UP by 35px)
    
    # Starting Y position of the first grid row (e.g. Boogie/Gina)
    FIRST_ROW_Y = 412  
    
    # Height of each player card row
    ROW_HEIGHT = 110  
    
    # Number of player card rows visible at once
    MAX_VISIBLE_ROWS = 4  
    
    # Number of columns in the grid
    COLUMNS = 2  
    
    # ========== STATUS DETECTION ==========
    # Regions for "Online" or "X min ago" text
    
    # Left card status
    GREEN_TEXT_REGION_LEFT = {
        'x': 25,      
        'y': 75,      # Status text Y offset
        'width': 85,  
        'height': 22  
    }
    
    # Right card status
    GREEN_TEXT_REGION_RIGHT = {
        'x': 260,     
        'y': 75,      
        'width': 85,  
        'height': 22  
    }
    
    # HSV color range for green text
    GREEN_HSV_LOWER = (40, 100, 100)
    GREEN_HSV_UPPER = (80, 255, 255)
    
    # HSV color range for WHITE text (Player Names)
    # Extremely relaxed for white/gray
    WHITE_HSV_LOWER = (0, 0, 100) 
    WHITE_HSV_UPPER = (180, 100, 255)

    # HSV color range for BLUE CARD background
    # Extremely relaxed for any blue-ish tone
    BLUE_CARD_HSV_LOWER = (80, 20, 20)
    BLUE_CARD_HSV_UPPER = (160, 255, 255)
    
    # Minimum area (in pixels) for a green blob
    MIN_GREEN_BLOB_AREA = 20
    
    # Name text relative offset (from card top-left)
    NAME_OCR_OFFSET = {
        'x': 80,      # Relative X start (Corrected from 50)
        'y': 8,       # Relative Y start
        'width': 170, # Width of name box
        'height': 35  # Height of name box
    }

    # Status text relative offset
    STATUS_OCR_OFFSET = {
        'x': 50,      
        'y': 75,      
        'width': 85,  
        'height': 22  
    }

    # Left card name (Legacy support / Fallback)
    NAME_OCR_REGION_LEFT = {
        'x': 105,     
        'y': 8,       # Name text top
        'width': 150, # Increased for longer names
        'height': 35  
    }
    
    # Right card name
    NAME_OCR_REGION_RIGHT = {
        'x': 340,     
        'y': 8,       
        'width': 170, # Increased for 'Baby Rangarokk'
        'height': 35  
    }
    
    # ========== RANK HEADERS (CLICKABLE) ==========
    # Approximate center coordinates for Rank Headers to expand/collapse
    RANK_HEADERS = {
        'R5': (279, 150),   # Row at the very top (Hydra)
        'R4': (279, 390),   # Angels Header bar
        'R3': (279, 895),   # Gods Header bar at the bottom
        'R2': (279, 930),   # Legends Header bar
        'R1': (279, 965)    # Soldiers Header bar
    }
    
    # Tesseract executable path (update this if tesseract is not in PATH)
    TESSERACT_PATH = r"C:\Program Files\Tesseract-OCR\tesseract.exe"
    
    # Tesseract configuration for better name recognition
    # Optimization: whitelist common name characters
    TESSERACT_CONFIG = '--psm 7 --oem 3 -c tessedit_char_whitelist=abcdefghijklmnopqrstuvwxyzABCDEFGHIJKLMNOPQRSTUVWXYZ0123456789.-'
    
    # Characters to remove from OCR output
    OCR_JUNK_CHARS = "[]{}()<>|/\\@#$%^&*_+=`~"
    
    # ========== SCROLL DETECTION ==========
    # How many consecutive duplicate names indicate we've reached the bottom
    DUPLICATE_THRESHOLD = 3
    
    # Maximum number of scrolls before forcing stop (safety limit)
    MAX_SCROLL_COUNT = 50
    
    # ========== DISCORD OUTPUT ==========
    # Emoji for online status
    ONLINE_EMOJI = "🟢"
    
    # Emoji for offline status
    OFFLINE_EMOJI = "⚪"
    
    # Maximum players to show in one message (Discord has 2000 char limit)
    MAX_PLAYERS_PER_MESSAGE = 50
    
    
    @classmethod
    def get_row_bounds(cls, row_index: int) -> Tuple[int, int, int, int]:
        """
        Get the bounding box for a specific row
        
        Args:
            row_index: Row number (0-based)
            
        Returns:
            Tuple of (x, y, width, height)
        """
        y = cls.FIRST_ROW_Y + (row_index * cls.ROW_HEIGHT)
        return (0, y, cls.EXPECTED_WIDTH, cls.ROW_HEIGHT)
    
    @classmethod
    def get_green_text_coords_left(cls, row_index: int) -> Tuple[int, int, int, int]:
        """
        Get the green "Online" text detection region for LEFT column player
        
        Args:
            row_index: Row number (0-based)
            
        Returns:
            Tuple of (x, y, width, height)
        """
        row_y = cls.FIRST_ROW_Y + (row_index * cls.ROW_HEIGHT)
        return (
            cls.GREEN_TEXT_REGION_LEFT['x'],
            row_y + cls.GREEN_TEXT_REGION_LEFT['y'],
            cls.GREEN_TEXT_REGION_LEFT['width'],
            cls.GREEN_TEXT_REGION_LEFT['height']
        )
    
    @classmethod
    def get_green_text_coords_right(cls, row_index: int) -> Tuple[int, int, int, int]:
        """
        Get the green "Online" text detection region for RIGHT column player
        
        Args:
            row_index: Row number (0-based)
            
        Returns:
            Tuple of (x, y, width, height)
        """
        row_y = cls.FIRST_ROW_Y + (row_index * cls.ROW_HEIGHT)
        return (
            cls.GREEN_TEXT_REGION_RIGHT['x'],
            row_y + cls.GREEN_TEXT_REGION_RIGHT['y'],
            cls.GREEN_TEXT_REGION_RIGHT['width'],
            cls.GREEN_TEXT_REGION_RIGHT['height']
        )
    
    @classmethod
    def get_name_ocr_coords_left(cls, row_index: int) -> Tuple[int, int, int, int]:
        """
        Get the name OCR region for LEFT column player
        
        Args:
            row_index: Row number (0-based)
            
        Returns:
            Tuple of (x, y, width, height)
        """
        row_y = cls.FIRST_ROW_Y + (row_index * cls.ROW_HEIGHT)
        return (
            cls.NAME_OCR_REGION_LEFT['x'],
            row_y + cls.NAME_OCR_REGION_LEFT['y'],
            cls.NAME_OCR_REGION_LEFT['width'],
            cls.NAME_OCR_REGION_LEFT['height']
        )
    
    @classmethod
    def get_name_ocr_coords_right(cls, row_index: int) -> Tuple[int, int, int, int]:
        """
        Get the name OCR region for RIGHT column player
        
        Args:
            row_index: Row number (0-based)
            
        Returns:
            Tuple of (x, y, width, height)
        """
        row_y = cls.FIRST_ROW_Y + (row_index * cls.ROW_HEIGHT)
        return (
            cls.NAME_OCR_REGION_RIGHT['x'],
            row_y + cls.NAME_OCR_REGION_RIGHT['y'],
            cls.NAME_OCR_REGION_RIGHT['width'],
            cls.NAME_OCR_REGION_RIGHT['height']
        )
    
    @classmethod
    def validate_config(cls) -> bool:
        """
        Validate configuration settings
        
        Returns:
            True if config is valid, False otherwise
        """
        # Check if Tesseract path exists
        if not os.path.exists(cls.TESSERACT_PATH):
            print(f"Warning: Tesseract not found at {cls.TESSERACT_PATH}")
            print("Please update TESSERACT_PATH in monitor_config.py")
            return False
        
        return True
