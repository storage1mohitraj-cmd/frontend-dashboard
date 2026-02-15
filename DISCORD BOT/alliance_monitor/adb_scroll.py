"""
ADB Scrolling Module

Handles scrolling automation in BlueStacks using ADB commands.
Implements human-like behavior with randomization and delays.
"""

import subprocess
import time
import random
from typing import Optional
from .monitor_config import MonitorConfig


class ADBScroller:
    """Handles ADB-based scrolling automation"""
    
    def __init__(self):
        self.device_id = None
        self.connected = False
    
    def connect(self) -> bool:
        """
        Connect to ADB device (BlueStacks)
        """
        try:
            adb = MonitorConfig.ADB_PATH
            # First, try to connect to BlueStacks
            host_port = f"{MonitorConfig.ADB_HOST}:{MonitorConfig.ADB_PORT}"
            print(f"Connecting to ADB at {host_port} using {adb}...")
            
            # Use -s to target specific host:port if needed, but connect first
            subprocess.run(f'"{adb}" connect {host_port}', shell=True, capture_output=True, timeout=15)
            
            # Get list of devices
            devices_result = subprocess.run(f'"{adb}" devices', shell=True, capture_output=True, text=True, timeout=10)
            
            if host_port not in devices_result.stdout:
                print(f"Device {host_port} not found in 'adb devices'. Attempting server restart...")
                subprocess.run(f'"{adb}" kill-server', shell=True, capture_output=True)
                subprocess.run(f'"{adb}" start-server', shell=True, capture_output=True)
                time.sleep(2)
                subprocess.run(f'"{adb}" connect {host_port}', shell=True, capture_output=True, timeout=15)
                devices_result = subprocess.run(f'"{adb}" devices', shell=True, capture_output=True, text=True, timeout=10)

            # Parse devices list
            lines = devices_result.stdout.strip().split('\n')
            devices = []
            for line in lines[1:]:
                if '\tdevice' in line:
                    device_id = line.split('\t')[0]
                    devices.append(device_id)
            
            if not devices:
                print("No ADB devices found after restart!")
                return False
            
            # Use the first device (or the one matching our port)
            for device in devices:
                if str(MonitorConfig.ADB_PORT) in device:
                    self.device_id = device
                    break
            
            if self.device_id is None:
                self.device_id = devices[0]
            
            print(f"Connected to device: {self.device_id}")
            self.connected = True
            return True
            
        except subprocess.TimeoutExpired:
            print("ADB connection timed out")
            return False
        except Exception as e:
            print(f"Error connecting to ADB: {e}")
            return False
    
    def disconnect(self):
        """Disconnect from ADB device"""
        if self.connected and self.device_id:
            try:
                adb = MonitorConfig.ADB_PATH
                subprocess.run(
                    f'"{adb}" disconnect {self.device_id}',
                    shell=True,
                    capture_output=True,
                    timeout=5
                )
                print("Disconnected from ADB")
            except Exception as e:
                print(f"Error disconnecting: {e}")
        
        self.connected = False
        self.device_id = None
    
    def execute_swipe(self, x1: int, y1: int, x2: int, y2: int, duration_ms: int = 300) -> bool:
        """
        Execute a swipe gesture via ADB
        
        Args:
            x1, y1: Starting coordinates
            x2, y2: Ending coordinates
            duration_ms: Duration of swipe in milliseconds
            
        Returns:
            True if successful, False otherwise
        """
        if not self.connected:
            print("Not connected to ADB!")
            return False
        
        try:
            adb = MonitorConfig.ADB_PATH
            # ADB swipe command: adb shell input swipe x1 y1 x2 y2 duration
            cmd = f'"{adb}" -s {self.device_id} shell input swipe {x1} {y1} {x2} {y2} {duration_ms}'
            
            result = subprocess.run(
                cmd,
                shell=True,
                capture_output=True,
                text=True,
                timeout=5
            )
            
            if result.returncode != 0:
                print(f"Swipe command failed: {result.stderr}")
                return False
            
            return True
            
        except Exception as e:
            print(f"Error executing swipe: {e}")
            return False
    
    def scroll_down(self) -> bool:
        """
        Perform one scroll down action with human-like randomization
        
        Returns:
            True if successful, False otherwise
        """
        # Add randomization to coordinates
        x1 = MonitorConfig.SCROLL_START_X + random.randint(
            -MonitorConfig.SCROLL_RANDOMIZATION,
            MonitorConfig.SCROLL_RANDOMIZATION
        )
        y1 = MonitorConfig.SCROLL_START_Y + random.randint(
            -MonitorConfig.SCROLL_RANDOMIZATION,
            MonitorConfig.SCROLL_RANDOMIZATION
        )
        x2 = MonitorConfig.SCROLL_END_X + random.randint(
            -MonitorConfig.SCROLL_RANDOMIZATION,
            MonitorConfig.SCROLL_RANDOMIZATION
        )
        y2 = MonitorConfig.SCROLL_END_Y + random.randint(
            -MonitorConfig.SCROLL_RANDOMIZATION,
            MonitorConfig.SCROLL_RANDOMIZATION
        )
        
        # Randomize duration slightly
        duration = MonitorConfig.SCROLL_DURATION_MS + random.randint(-50, 50)
        
        print(f"Scrolling: ({x1}, {y1}) -> ({x2}, {y2}), duration: {duration}ms")
        
        return self.execute_swipe(x1, y1, x2, y2, duration)
    
    def scroll_to_top(self) -> bool:
        """
        Scroll to the top of the list (do a few upward swipes)
        
        Returns:
            True if successful, False otherwise
        """
        print("Scrolling to top...")
        
        # Do 5 quick upward swipes to ensure we're at the top
        for i in range(5):
            # Reverse the coordinates for upward scroll
            x1 = MonitorConfig.SCROLL_END_X
            y1 = MonitorConfig.SCROLL_END_Y
            x2 = MonitorConfig.SCROLL_START_X
            y2 = MonitorConfig.SCROLL_START_Y
            
            if not self.execute_swipe(x1, y1, x2, y2, 200):
                return False
            
            time.sleep(0.3)  # Short delay between swipes
        
        print("Reached top")
        return True
    
    def random_delay(self):
        """Sleep for a random duration between actions"""
        delay = random.uniform(
            MonitorConfig.SCROLL_DELAY_MIN,
            MonitorConfig.SCROLL_DELAY_MAX
        )
        print(f"Waiting {delay:.2f} seconds...")
        time.sleep(delay)
    
    def tap(self, x: int, y: int) -> bool:
        """
        Perform a tap at specified coordinates
        """
        if not self.connected:
            if not self.connect():
                return False
        
        try:
            adb = MonitorConfig.ADB_PATH
            cmd = f'"{adb}" -s {self.device_id} shell input tap {x} {y}'
            result = subprocess.run(cmd, shell=True, capture_output=True, text=True, timeout=5)
            return result.returncode == 0
        except Exception as e:
            print(f"Error executing tap: {e}")
            return False

    def click_rank(self, rank_name: str) -> bool:
        """
        Click on a specific Rank header (R3, R2, R1 etc)
        """
        if rank_name not in MonitorConfig.RANK_HEADERS:
            print(f"Unknown rank: {rank_name}")
            return False
            
        x, y = MonitorConfig.RANK_HEADERS[rank_name]
        print(f"Clicking {rank_name} header at ({x}, {y})...")
        return self.tap(x, y)
    
    def __del__(self):
        """Cleanup on deletion"""
        self.disconnect()


# Test function
if __name__ == "__main__":
    print("Testing ADB Scroller Module...")
    
    scroller = ADBScroller()
    
    # Test connection
    if scroller.connect():
        print("✓ Connected to ADB")
        
        # Test scroll to top
        if scroller.scroll_to_top():
            print("✓ Scrolled to top")
        
        # Test a single scroll down
        print("\nTesting scroll down in 3 seconds...")
        time.sleep(3)
        
        if scroller.scroll_down():
            print("✓ Scroll down successful")
        else:
            print("✗ Scroll down failed")
        
        scroller.disconnect()
    else:
        print("✗ Failed to connect to ADB")
        print("\nTroubleshooting:")
        print("1. Make sure BlueStacks is running")
        print("2. Enable ADB in BlueStacks Settings > Advanced")
        print("3. Check ADB port (usually 5555 or 5565)")
        print("4. Try: adb connect localhost:5555")
