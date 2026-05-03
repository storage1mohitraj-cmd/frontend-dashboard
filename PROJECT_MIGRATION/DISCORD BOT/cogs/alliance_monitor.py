"""
Alliance Monitor Discord Cog

Provides Discord commands for alliance member online status monitoring.
"""

import discord
from discord.ext import commands
from discord import app_commands
import asyncio
from typing import Optional
import os

# Import our alliance monitoring modules
from alliance_monitor.scanner import AllianceScanner, ScanResult
from alliance_monitor.monitor_config import MonitorConfig
from alliance_monitor.capture import ScreenCapture
from alliance_monitor.status_detector import OnlineStatusDetector
from alliance_monitor.detector import OnlineDetector
from alliance_monitor.ocr_reader import OCRReader
import cv2


class AllianceMonitorCog(commands.Cog, name="AllianceMonitor"):
    """Alliance member online status monitoring"""
    
    def __init__(self, bot):
        self.bot = bot
        self.scanner = AllianceScanner()
    
    @commands.command(name="online", help="Check which alliance members are currently online")
    async def check_online(self, ctx):
        """
        Main command to check alliance member online status
        
        Usage: !online
        """
        # Check if scan is allowed
        allowed, reason = self.scanner.should_allow_scan()
        if not allowed:
            await ctx.send(f"⚠️ {reason}")
            return
        
        # Send initial message
        status_msg = await ctx.send("🔍 Starting alliance scan...\nThis may take 1-2 minutes.")
        
        # Progress callback to update Discord message
        last_update_time = asyncio.get_event_loop().time()
        
        async def progress_callback(message: str):
            nonlocal last_update_time
            current_time = asyncio.get_event_loop().time()
            
            # Update message every 3 seconds to avoid rate limits
            if current_time - last_update_time >= 3:
                try:
                    await status_msg.edit(content=f"🔍 {message}")
                    last_update_time = current_time
                except:
                    pass  # Ignore edit errors
        
        # Perform scan in executor to avoid blocking
        loop = asyncio.get_event_loop()
        result = await loop.run_in_executor(
            None,
            lambda: self.scanner.perform_full_scan(lambda msg: asyncio.run_coroutine_threadsafe(progress_callback(msg), loop))
        )
        
        # Update with results
        if result:
            # Create a nice summary embed or formatted message
            online_count = len(result.online_players)
            total_scanned = online_count + len(result.offline_players)
            
            summary = f"📊 **{MonitorConfig.WINDOW_TITLE_PATTERN} Status**\n"
            summary += f"🔥 **Total Online:** `{online_count}` players found\n"
            summary += f"🕒 *Scan took {result.scan_duration:.1f}s*\n\n"
            
            # Send online list
            if result.online_players:
                online_msg = f"{MonitorConfig.ONLINE_EMOJI} **ONLINE ({online_count})**\n"
                online_p_list = sorted(list(set(result.online_players)))
                online_msg += "```\n" + "\n".join([f"• {p}" for p in online_p_list]) + "\n```"
                
                if len(online_msg) > 2000:
                    online_msg = online_msg[:1990] + "...\n```"
                
                await status_msg.edit(content=summary + online_msg)
            else:
                await status_msg.edit(content=summary + "❌ No online players detected.")
                
            # Send offline list in a separate message to avoid char limits
            if result.offline_players:
                offline_msg = f"{MonitorConfig.OFFLINE_EMOJI} **OFFLINE ({len(result.offline_players)})**\n"
                offline_msg += "```\n" + "\n".join([f"• {p}" for p in result.offline_players[:50]]) # Cap display
                if len(result.offline_players) > 50:
                    offline_msg += f"\n... and {len(result.offline_players)-50} more"
                offline_msg += "\n```"
                await ctx.send(offline_msg)
            
            # Send timestamp
            await ctx.send(f"*Last updated: {result.timestamp.strftime('%H:%M:%S')}*")
        else:
            await status_msg.edit(content="❌ Scan failed! Check the logs for details.")
    
    @commands.command(name="online_test", help="Test screenshot capture (Admin only)")
    @commands.has_permissions(administrator=True)
    async def test_capture(self, ctx):
        """
        Test command to verify screenshot capture
        
        Usage: !online_test
        """
        await ctx.send("📸 Testing screenshot capture...")
        
        capture = ScreenCapture()
        
        # Find window
        if not capture.find_bluestacks_window():
            await ctx.send("❌ BlueStacks window not found!")
            return
        
        # Get window info
        info = capture.get_window_info()
        await ctx.send(f"✅ Found window: {info['title']}\nSize: {info['size']}")
        
        # Capture and save
        test_path = "test_capture.png"
        if capture.save_screenshot(test_path):
            await ctx.send(f"✅ Screenshot saved to {test_path}", file=discord.File(test_path))
            
            # Clean up
            try:
                os.remove(test_path)
            except:
                pass
        else:
            await ctx.send("❌ Failed to capture screenshot!")
    
    @commands.command(name="online_config", help="Show current monitor configuration (Admin only)")
    @commands.has_permissions(administrator=True)
    async def show_config(self, ctx):
        """
        Show current configuration settings
        
        Usage: !online_config
        """
        config_info = f"""
**Alliance Monitor Configuration**

**BlueStacks Settings:**
• Window: `{MonitorConfig.WINDOW_TITLE_PATTERN}`
• Resolution: {MonitorConfig.EXPECTED_WIDTH}x{MonitorConfig.EXPECTED_HEIGHT}

**ADB Settings:**
• Host: {MonitorConfig.ADB_HOST}:{MonitorConfig.ADB_PORT}

**Scan Settings:**
• Cooldown: {MonitorConfig.SCAN_COOLDOWN_MIN//60}-{MonitorConfig.SCAN_COOLDOWN_MAX//60} minutes
• Max scrolls: {MonitorConfig.MAX_SCROLL_COUNT}
• Scroll delay: {MonitorConfig.SCROLL_DELAY_MIN}-{MonitorConfig.SCROLL_DELAY_MAX}s

**Detection Settings:**
• Rows per screen: {MonitorConfig.MAX_VISIBLE_ROWS}
• Row height: {MonitorConfig.ROW_HEIGHT}px
• First row Y: {MonitorConfig.FIRST_ROW_Y}px

**Calibration:**
To adjust coordinates, edit `alliance_monitor/monitor_config.py`
        """
        
        await ctx.send(config_info)
    
    @commands.command(name="online_visualize", help="Create visualization of detection regions (Admin only)")
    @commands.has_permissions(administrator=True)
    async def visualize_detection(self, ctx):
        """
        Create visualizations of green dot detection and OCR regions
        
        Usage: !online_visualize
        """
        await ctx.send("📸 Capturing screenshot for visualization...")
        
        capture = ScreenCapture()
        img = capture.capture_bluestacks()
        
        if img is None:
            await ctx.send("❌ Failed to capture screenshot!")
            return
        
        # Create detector visualization
        detector = OnlineStatusDetector()
        detector.visualize_detection(img, "detection_viz.png")
        
        # Create OCR visualization
        ocr = OCRReader()
        ocr.visualize_ocr_regions(img, "ocr_viz.png")
        
        # Send both visualizations
        await ctx.send(
            "🎯 **Detection Regions Visualization**\nGreen boxes = online detected, Red boxes = offline",
            file=discord.File("detection_viz.png")
        )
        
        await ctx.send(
            "📝 **OCR Regions Visualization**\nBlue boxes show name extraction regions",
            file=discord.File("ocr_viz.png")
        )
        
        # Clean up
        try:
            os.remove("detection_viz.png")
            os.remove("ocr_viz.png")
        except:
            pass
    
    @commands.command(name="online_debug", help="Debug OCR for a single screen (Admin only)")
    @commands.has_permissions(administrator=True)
    async def debug_ocr(self, ctx):
        """
        Debug OCR extraction using DYNAMIC CARD DETECTION.
        Draws boxes around detected cards and extracted names.
        """
        await ctx.send("🔍 Running Dynamic CV Debug Scan...")
        
        capture = ScreenCapture()
        img = capture.capture_bluestacks()
        
        if img is None:
            await ctx.send("❌ Failed to capture screenshot!")
            return
            
        # Initialize Dynamic Modules
        detector = OnlineDetector()
        ocr = OCRReader()
        
        # 1. Detect Cards
        cards = detector.detect_player_cards(img)
        
        # Save Debug Mask to verify HSV range
        mask = detector.get_blue_card_mask(img)
        mask_path = "debug_hsv_mask.png"
        cv2.imwrite(mask_path, mask)
        
        if not cards:
            await ctx.send("❌ No player cards detected! Sending HSV Mask...", file=discord.File(mask_path))
            try: os.remove(mask_path)
            except: pass
            return
        
        # Send mask anyway for verification
        await ctx.send(file=discord.File(mask_path))
        try: os.remove(mask_path)
        except: pass

        debug_msg = f"**Found {len(cards)} Player Cards:**\n"
        vis_image = img.copy()
        
        for i, card_rect in enumerate(cards):
            x, y, w, h = card_rect
            
            # 2. Extract Name using Relative Offset
            name = ocr.extract_name_from_card(img, card_rect)
            
            # 3. Detect Online Status using Relative Offset
            is_online = detector.detect_status_in_card(img, card_rect)
            status_icon = "🟢" if is_online else "⚪"
            
            debug_msg += f"Card {i+1}: {status_icon} `{name}` (y={y})\n"
            
            # 4. Draw Visualization
            # Green Box = Card
            cv2.rectangle(vis_image, (x, y), (x + w, y + h), (0, 255, 0), 2)
            
            # Blue Box = Name Region
            nx = x + MonitorConfig.NAME_OCR_OFFSET['x']
            ny = y + MonitorConfig.NAME_OCR_OFFSET['y']
            nw = MonitorConfig.NAME_OCR_OFFSET['width']
            nh = MonitorConfig.NAME_OCR_OFFSET['height']
            cv2.rectangle(vis_image, (nx, ny), (nx + nw, ny + nh), (255, 0, 0), 1)
            
        await ctx.send(debug_msg)
        
        # Save visualization
        viz_path = "dynamic_debug_viz.png"
        cv2.imwrite(viz_path, vis_image)
        await ctx.send(file=discord.File(viz_path))
        try:
            os.remove(viz_path)
        except: 
            pass
    
    @commands.command(name="calibrate", help="Visual calibration tool (Admin only)")
    @commands.has_permissions(administrator=True)
    async def calibrate_coordinates(self, ctx):
        """
        Visual coordinate calibration tool.
        Shows colored boxes on screenshot indicating where bot looks for data.
        """
        await ctx.send("🎯 Running Calibration Scan...")
        
        capture = ScreenCapture()
        img = capture.capture_bluestacks()
        
        if img is None:
            await ctx.send("❌ Failed to capture screenshot!")
            return
        
        ocr = OCRReader()
        vis_image = img.copy()
        
        report = "**📊 Calibration Report:**\n\n"
        
        # Draw detection regions for all visible rows
        for row_idx in range(MonitorConfig.MAX_VISIBLE_ROWS):
            # LEFT COLUMN
            # Name region (RED)
            nx, ny, nw, nh = MonitorConfig.get_name_ocr_coords_left(row_idx)
            cv2.rectangle(vis_image, (nx, ny), (nx + nw, ny + nh), (0, 0, 255), 2)
            cv2.putText(vis_image, f"L{row_idx}", (nx, ny - 5), 
                       cv2.FONT_HERSHEY_SIMPLEX, 0.5, (0, 0, 255), 2)
            
            # Status region (BLUE)
            sx, sy, sw, sh = MonitorConfig.get_green_text_coords_left(row_idx)
            cv2.rectangle(vis_image, (sx, sy), (sx + sw, sy + sh), (255, 0, 0), 2)
            
            # Extract name
            name = ocr.extract_name_from_region(img, nx, ny, nw, nh)
            if name:
                report += f"**L{row_idx}:** `{name}`\n"
            
            # RIGHT COLUMN
            # Name region (RED)
            nx, ny, nw, nh = MonitorConfig.get_name_ocr_coords_right(row_idx)
            cv2.rectangle(vis_image, (nx, ny), (nx + nw, ny + nh), (0, 0, 255), 2)
            cv2.putText(vis_image, f"R{row_idx}", (nx, ny - 5), 
                       cv2.FONT_HERSHEY_SIMPLEX, 0.5, (0, 0, 255), 2)
            
            # Status region (BLUE)
            sx, sy, sw, sh = MonitorConfig.get_green_text_coords_right(row_idx)
            cv2.rectangle(vis_image, (sx, sy), (sx + sw, sy + sh), (255, 0, 0), 2)
            
            # Extract name
            name = ocr.extract_name_from_region(img, nx, ny, nw, nh)
            if name:
                report += f"**R{row_idx}:** `{name}`\n"
        
        # Add legend
        legend_y = 20
        cv2.putText(vis_image, "RED = Name OCR", (10, legend_y), 
                   cv2.FONT_HERSHEY_SIMPLEX, 0.6, (0, 0, 255), 2)
        cv2.putText(vis_image, "BLUE = Status Check", (10, legend_y + 25), 
                   cv2.FONT_HERSHEY_SIMPLEX, 0.6, (255, 0, 0), 2)
        
        # Save and send
        viz_path = "calibration_overlay.png"
        cv2.imwrite(viz_path, vis_image)
        
        await ctx.send(report[:1900])  # Discord char limit
        await ctx.send(file=discord.File(viz_path))
        
        try:
            os.remove(viz_path)
        except:
            pass
    
    @commands.command(name="test_advanced", help="Test Advanced OCR (Admin only)")
    @commands.has_permissions(administrator=True)
    async def test_advanced_ocr(self, ctx):
        """
        Test the new AdvancedOCR with dynamic card detection.
        """
        await ctx.send("🚀 Testing Advanced OCR...")
        
        from alliance_monitor.capture import ScreenCapture
        from alliance_monitor.advanced_ocr import AdvancedOCR
        
        capture = ScreenCapture()
        img = capture.capture_bluestacks()
        
        if img is None:
            await ctx.send("❌ Failed to capture screenshot!")
            return
        
        ocr = AdvancedOCR()
        
        # Extract players
        players = ocr.extract_all_players(img)
        
        # Create visualization
        viz_path = "advanced_ocr_test.png"
        ocr.visualize_detection(img, viz_path)
        
        # Build report
        report = f"**🎯 Advanced OCR Results: {len(players)} players detected**\n\n"
        
        for i, player in enumerate(players, 1):
            status = "🟢 ONLINE" if player['online'] else "⚪ OFFLINE"
            report += f"{i}. {status} `{player['name']}`\n"
        
        await ctx.send(report[:1900])
        await ctx.send(file=discord.File(viz_path))
        
        try:
            os.remove(viz_path)
        except:
            pass

    @test_capture.error
    @show_config.error
    @visualize_detection.error
    @debug_ocr.error
    async def admin_command_error(self, ctx, error):
        """Error handler for admin commands"""
        if isinstance(error, commands.MissingPermissions):
            await ctx.send("❌ This command requires administrator permissions!")
        else:
            await ctx.send(f"❌ An error occurred: {error}")


async def setup(bot):
    """Setup function for the cog"""
    await bot.add_cog(AllianceMonitorCog(bot))
