"""
Scan Orchestrator Module

Coordinates the entire scanning process:
- Scrolling through the alliance member list
- Capturing screenshots at each position
- Detecting online status and extracting names
- Merging results and removing duplicates
- Rate limiting to prevent excessive scans
"""

import time
from datetime import datetime, timedelta
from typing import Dict, List, Tuple, Optional
import cv2
from .capture import ScreenCapture
from .adb_scroll import ADBScroller
from .detector import OnlineDetector
from .ocr_reader import OCRReader
from .advanced_ocr import AdvancedOCR
from .monitor_config import MonitorConfig


class ScanResult:
    """Container for scan results"""
    
    def __init__(self):
        self.online_players: List[str] = []
        self.offline_players: List[str] = []
        self.total_screenshots: int = 0
        self.scan_duration: float = 0
        self.timestamp: datetime = datetime.now()
    
    def __str__(self):
        return (
            f"Scan completed at {self.timestamp.strftime('%Y-%m-%d %H:%M:%S')}\n"
            f"Online: {len(self.online_players)} | Offline: {len(self.offline_players)}\n"
            f"Screenshots: {self.total_screenshots} | Duration: {self.scan_duration:.1f}s"
        )


class AllianceScanner:
    """Main scanner orchestrator"""
    
    def __init__(self):
        self.capture = ScreenCapture()
        self.scroller = ADBScroller()
        self.detector = OnlineDetector()
        self.ocr = OCRReader()  # Keep for fallback
        self.advanced_ocr = AdvancedOCR()  # NEW: Dynamic OCR
        
        self.last_scan_time: Optional[datetime] = None
        self.is_scanning = False
    
    def should_allow_scan(self) -> Tuple[bool, Optional[str]]:
        """
        Check if a scan is allowed based on rate limiting
        
        Returns:
            (allowed, reason) - allowed is True if scan can proceed
        """
        if self.is_scanning:
            return False, "A scan is already in progress"
        
        if self.last_scan_time is None:
            return True, None
        
        # Calculate time since last scan
        elapsed = datetime.now() - self.last_scan_time
        min_cooldown = timedelta(seconds=MonitorConfig.SCAN_COOLDOWN_MIN)
        
        if elapsed < min_cooldown:
            remaining = min_cooldown - elapsed
            minutes = int(remaining.total_seconds() / 60)
            seconds = int(remaining.total_seconds() % 60)
            return False, f"Please wait {minutes}m {seconds}s before scanning again"
        
        return True, None
    
    def detect_bottom_reached(self, current_names: List[str], previous_batches: List[List[str]]) -> bool:
        """
        Detect if we've reached the bottom of the list
        
        Args:
            current_names: Names from current screenshot
            previous_batches: List of name lists from previous screenshots
            
        Returns:
            True if bottom reached, False otherwise
        """
        if not current_names or not previous_batches:
            return False
        
        # Check last few batches for duplicates
        check_count = min(MonitorConfig.DUPLICATE_THRESHOLD, len(previous_batches))
        recent_batches = previous_batches[-check_count:]
        
        # If current names are very similar to recent batches, we're at the bottom
        for prev_names in recent_batches:
            # Count how many names match
            matches = sum(1 for name in current_names if name in prev_names)
            similarity = matches / max(len(current_names), 1)
            
            if similarity > 0.7:  # 70% similarity threshold
                return True
        
        return False
    
    def merge_results(self, all_data: List[Tuple[List[str], List[bool]]]) -> Tuple[List[str], List[str]]:
        """
        Merge results from all screenshots and remove duplicates
        
        Args:
            all_data: List of (names, online_status) tuples from each screenshot
            
        Returns:
            (online_players, offline_players) - Two lists of unique player names
        """
        # Use dictionaries to track unique players and their status
        # If a player appears multiple times, prefer "online" status
        player_status: Dict[str, bool] = {}
        
        for names, statuses in all_data:
            for name, is_online in zip(names, statuses):
                if not name:  # Skip empty names
                    continue
                
                # If player already seen and was online, keep online status
                # Otherwise, update with current status
                if name in player_status:
                    player_status[name] = player_status[name] or is_online
                else:
                    player_status[name] = is_online
        
        # Separate into online and offline lists
        online_players = [name for name, status in player_status.items() if status]
        offline_players = [name for name, status in player_status.items() if not status]
        
        # Sort alphabetically
        online_players.sort()
        offline_players.sort()
        
        return online_players, offline_players
    
    def navigate_to_alliance_list(self, log_fn=print) -> bool:
        """
        Automatically navigate from main screen to alliance members list.
        Path: Alliance (bottom bar) -> Members (bottom bar)
        """
        log_fn("📍 Checking current screen for navigation...")
        img = self.capture.capture_bluestacks()
        if img is None: return False

        # 1. Check if we're ALREADY on the members list
        # Look for rank headers like R5 or R4
        if self.advanced_ocr.find_text_pos(img, "R5") or self.advanced_ocr.find_text_pos(img, "Rank 5"):
            log_fn("  ✅ Already on Members list.")
            return True

        # 2. Check if we are on Alliance Main Menu (look for 'Members' button)
        members_pos = self.advanced_ocr.find_text_pos(img, "Members")
        if members_pos:
            log_fn(f"  👆 Found 'Members' button at {members_pos}. Clicking...")
            self.scroller.tap(members_pos[0], members_pos[1])
            time.sleep(2.5)
            return True

        # 3. Check if we are on Main Game Screen (look for 'Alliance' button)
        alliance_pos = self.advanced_ocr.find_text_pos(img, "Alliance")
        if alliance_pos:
            log_fn(f"  👆 Found 'Alliance' button at {alliance_pos}. Clicking...")
            self.scroller.tap(alliance_pos[0], alliance_pos[1])
            time.sleep(3.0)
            
            # Now we should be on Alliance Menu, look for Members
            img = self.capture.capture_bluestacks()
            members_pos = self.advanced_ocr.find_text_pos(img, "Members")
            if members_pos:
                log_fn(f"  👆 Found 'Members' button at {members_pos}. Clicking...")
                self.scroller.tap(members_pos[0], members_pos[1])
                time.sleep(2.5)
                return True
        
        log_fn("  ❌ Could not find navigation buttons. Please open the Members list manually.")
        return False

    def perform_full_scan(self, progress_callback=None) -> Optional[ScanResult]:
        """
        Perform ROBUST scan using STATIC OCR + Smart Rank Navigation.
        """
        def update_progress(msg: str):
            print(msg)
            if progress_callback:
                progress_callback(msg)
        
        allowed, reason = self.should_allow_scan()
        if not allowed:
            update_progress(f"Scan blocked: {reason}")
            return None
        
        if not self.scroller.connect():
            update_progress("Failed to connect to ADB!")
            return None

        # --- AUTO NAVIGATION ---
        if not self.navigate_to_alliance_list(update_progress):
            update_progress("⚠️ Auto-navigation failed. Attempting scan anyway...")
        
        self.is_scanning = True
        start_time = time.time()
        
        try:
            result = ScanResult()
            all_data = []
        
            ranks = ['R5', 'R4', 'R3', 'R2', 'R1']
            
            for i, rank in enumerate(ranks):
                next_rank = ranks[i+1] if i+1 < len(ranks) else None
                update_progress(f"🚀 Scanning Rank: {rank}...")
                
                # 1. Visual Rank Expansion
                # Capture current screen to find the header
                img = self.capture.capture_bluestacks()
                header_y = self.advanced_ocr.find_text_y(img, rank)
                
                # Check if already expanded (look for cards below the header)
                # If we see blue/gold cards on the screen, R5 or R4 might already be open
                cards = self.advanced_ocr.detect_blue_cards(img)
                is_already_expanded = False
                if cards:
                    # If any card is found reasonably near/below our current rank section
                    # For simplicity, if we see cards during the initial expansion phase, 
                    # we assume something is already open.
                    is_already_expanded = True
                
                if header_y:
                    if is_already_expanded:
                        update_progress(f"  ✨ {rank} seems already expanded. Skipping click.")
                    else:
                        update_progress(f"  👆 Found {rank} header at Y={header_y}. Clicking to expand...")
                        # Click center of the header bar
                        self.scroller.tap(MonitorConfig.SCREEN_WIDTH // 2, header_y)
                        time.sleep(2.0)  # Wait for expansion animation
                else:
                    # Fallback to static click if OCR fails to find it
                    if not is_already_expanded:
                        update_progress(f"  ⚠️ Could not find {rank} header visually. Using fallback click...")
                        self.scroller.click_rank(rank)
                        time.sleep(2.5)
                
                # 2. Scroll & Scan
                scan_attempts = 0
                max_scrolls = 30  # Increased limit for large ranks
                seen_names = set()  # Track duplicates to detect bottom
                
                while scan_attempts < max_scrolls:
                    img = self.capture.capture_bluestacks()
                    if img is None: 
                        break
                    
                    result.total_screenshots += 1
                    
                    # Check if NEXT rank header is visible (means we finished current rank)
                    if next_rank:
                        header_y = self.advanced_ocr.find_text_y(img, next_rank)
                        # If the NEXT rank header is high enough, we've passed all players in this rank
                        if header_y and header_y < 850: 
                            update_progress(f"  🛑 Found {next_rank} header at Y={header_y}. Finishing {rank}.")
                            break
                    
                    # Use ADVANCED OCR - Works regardless of scroll position!
                    players_on_screen = self.advanced_ocr.extract_all_players(img)
                    
                    if players_on_screen:
                        new_count = 0
                        for player_data in players_on_screen:
                            name = player_data['name']
                            is_online = player_data['online']
                            
                            # Check if this is a new player
                            if name and name not in seen_names:
                                seen_names.add(name)
                                all_data.append(([name], [is_online]))
                                new_count += 1
                        
                        if new_count > 0:
                            update_progress(f"  📋 Scanned {len(players_on_screen)} players ({new_count} new)")
                        else:
                            # If we see NO new names, it might be the bottom or a overlap
                            update_progress(f"  ⚠️ No new names found on this screen (All {len(players_on_screen)} are duplicates).")
                            # Only break if we've seen at least some players in this rank
                            if len(seen_names) > 0:
                                update_progress(f"  ✅ Reached bottom of {rank} (all names duplicated).")
                                break
                    else:
                        update_progress(f"  🔍 No player cards detected on screen (Scroll {scan_attempts+1})")
                    
                    # Scroll down
                    self.scroller.scroll_down()
                    time.sleep(1.2)
                    scan_attempts += 1
                
                update_progress(f"  ✅ Rank {rank} complete. Total unique: {len(seen_names)}")
            
            # Merge Results
            update_progress("📊 Processing results...")
            online, offline = self.merge_results(all_data)
            
            result.online_players = online
            result.offline_players = offline
            result.scan_duration = time.time() - start_time
            result.timestamp = datetime.now()
            self.last_scan_time = datetime.now()
            
            update_progress(f"✅ Scan complete! Found {len(online)} online, {len(offline)} offline")
            return result
            
        except Exception as e:
            update_progress(f"❌ Error during scan: {e}")
            import traceback
            traceback.print_exc()
            return None
            
        finally:
            self.is_scanning = False
            self.scroller.disconnect()
    
    def format_for_discord(self, result: ScanResult) -> str:
        """
        Format scan results for Discord output
        
        Args:
            result: ScanResult object
            
        Returns:
            Formatted string for Discord
        """
        lines = []
        
        # Online section
        lines.append(f"{MonitorConfig.ONLINE_EMOJI} **ONLINE ({len(result.online_players)})**")
        if result.online_players:
            for player in result.online_players[:MonitorConfig.MAX_PLAYERS_PER_MESSAGE]:
                lines.append(f"• {player}")
            
            if len(result.online_players) > MonitorConfig.MAX_PLAYERS_PER_MESSAGE:
                remaining = len(result.online_players) - MonitorConfig.MAX_PLAYERS_PER_MESSAGE
                lines.append(f"... and {remaining} more")
        else:
            lines.append("• None")
        
        lines.append("")  # Empty line
        
        # Offline section
        lines.append(f"{MonitorConfig.OFFLINE_EMOJI} **OFFLINE ({len(result.offline_players)})**")
        if result.offline_players:
            for player in result.offline_players[:MonitorConfig.MAX_PLAYERS_PER_MESSAGE]:
                lines.append(f"• {player}")
            
            if len(result.offline_players) > MonitorConfig.MAX_PLAYERS_PER_MESSAGE:
                remaining = len(result.offline_players) - MonitorConfig.MAX_PLAYERS_PER_MESSAGE
                lines.append(f"... and {remaining} more")
        else:
            lines.append("• None")
        
        lines.append("")  # Empty line
        lines.append(f"*Last scanned: {result.timestamp.strftime('%Y-%m-%d %H:%M:%S')}*")
        lines.append(f"*Duration: {result.scan_duration:.1f}s | Screenshots: {result.total_screenshots}*")
        
        return "\n".join(lines)


# Test function
if __name__ == "__main__":
    print("Testing Alliance Scanner...")
    print("=" * 60)
    
    scanner = AllianceScanner()
    
    # Check if scan is allowed
    allowed, reason = scanner.should_allow_scan()
    if not allowed:
        print(f"✗ {reason}")
    else:
        print("✓ Scan is allowed")
        print("\nIMPORTANT: Make sure you have:")
        print("1. BlueStacks running")
        print("2. Whiteout Survival open")
        print("3. Alliance member list visible")
        print("\nStarting scan in 5 seconds...")
        time.sleep(5)
        
        # Perform scan
        result = scanner.perform_full_scan()
        
        if result:
            print("\n" + "=" * 60)
            print("SCAN RESULTS")
            print("=" * 60)
            print(result)
            print("\nOnline players:")
            for player in result.online_players:
                print(f"  🟢 {player}")
            print("\nOffline players:")
            for player in result.offline_players:
                print(f"  ⚪ {player}")
            
            print("\n" + "=" * 60)
            print("DISCORD FORMAT")
            print("=" * 60)
            print(scanner.format_for_discord(result))
        else:
            print("✗ Scan failed!")
