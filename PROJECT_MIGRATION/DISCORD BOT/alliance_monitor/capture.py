"""
Screen Capture Module

Captures screenshots of the BlueStacks window using mss.
Only captures the BlueStacks window client area, excluding title bars and borders.
"""

import mss
import mss.tools
import numpy as np
import cv2
from PIL import Image
from typing import Optional, Dict
try:
    import win32gui
    import win32ui
    import win32con
    HAS_WIN32 = True
except ImportError:
    win32gui = None
    win32ui = None
    win32con = None
    HAS_WIN32 = False
from .monitor_config import MonitorConfig


class ScreenCapture:
    """Handles screen capture of BlueStacks window"""
    
    def __init__(self):
        self.sct = mss.mss()
        self.bluestacks_hwnd = None
    
    def find_bluestacks_window(self) -> bool:
        """Find the BlueStacks window by title"""
        if not HAS_WIN32:
            print("Win32 libraries not available. Cannot find window by title.")
            return False
        def enum_windows_callback(hwnd, windows):
            if win32gui.IsWindowVisible(hwnd):

                title = win32gui.GetWindowText(hwnd)
                if MonitorConfig.WINDOW_TITLE_PATTERN in title:
                    windows.append((hwnd, title))
        
        windows = []
        win32gui.EnumWindows(enum_windows_callback, windows)
        
        if not windows:
            print(f"No window found with '{MonitorConfig.WINDOW_TITLE_PATTERN}' in title")
            self.bluestacks_hwnd = None
            return False
        
        # Use the first matching window
        self.bluestacks_hwnd = windows[0][0]
        return True

    def get_window_info(self) -> Optional[Dict]:
        """Get the client area (game area) position and size"""
        if not self.bluestacks_hwnd:
            if not self.find_bluestacks_window():
                return None
        
        hwnd = self.bluestacks_hwnd
        
        # Get client area size
        left, top, right, bottom = win32gui.GetClientRect(hwnd)
        width = right - left
        height = bottom - top
        
        # Convert client (0,0) to screen coordinates
        point = win32gui.ClientToScreen(hwnd, (0, 0))
        
        return {
            'hwnd': hwnd,
            'title': win32gui.GetWindowText(hwnd),
            'x': point[0],
            'y': point[1],
            'width': width,
            'height': height,
            'size': (width, height)
        }

    def capture_bluestacks(self) -> Optional[np.ndarray]:
        """Capture only the game client area from BlueStacks"""
        info = self.get_window_info()
        if not info:
            return None
            
        monitor = {
            "top": info['y'],
            "left": info['x'],
            "width": info['width'],
            "height": info['height']
        }
        
        try:
            with mss.mss() as sct:
                screenshot = sct.grab(monitor)
                img = np.array(screenshot)
                # Convert BGRA to BGR
                img = cv2.cvtColor(img, cv2.COLOR_BGRA2BGR)
                return img
        except Exception as e:
            print(f"Error capturing screenshot: {e}")
            return None
    
    def capture_as_pil(self) -> Optional[Image.Image]:
        """Capture as PIL Image"""
        img_array = self.capture_bluestacks()
        if img_array is None:
            return None
        
        # Convert BGR to RGB for PIL
        img_rgb = img_array[:, :, ::-1]
        return Image.fromarray(img_rgb)
    
    def save_screenshot(self, filepath: str) -> bool:
        """Capture and save screenshot to file"""
        img = self.capture_as_pil()
        if img is None:
            return False
        
        try:
            img.save(filepath)
            print(f"Screenshot saved to {filepath}")
            return True
        except Exception as e:
            print(f"Error saving screenshot: {e}")
            return False
    
    def __del__(self):
        """Cleanup on deletion"""
        if hasattr(self, 'sct'):
            self.sct.close()


# Test function
if __name__ == "__main__":
    print("Testing Screen Capture Module...")
    capture = ScreenCapture()
    img = capture.capture_bluestacks()
    if img is not None:
        print(f"✓ Screenshot captured: {img.shape}")
        capture.save_screenshot("test_screenshot.png")
    else:
        print("✗ Failed to capture screenshot")
