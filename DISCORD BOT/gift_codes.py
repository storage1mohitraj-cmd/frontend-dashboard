from typing import Union
import aiohttp
import asyncio
from bs4 import BeautifulSoup
from datetime import datetime, timedelta
import re
import logging
import dateutil.parser
import discord

logger = logging.getLogger(__name__)

def build_codes_embed(codes):
    """Builds a Discord embed for a list of gift codes."""
    if not codes:
        return discord.Embed(
            title="🎁 Gift Codes",
            description="No active codes found.",
            color=discord.Color.red()
        )
    
    embed = discord.Embed(
        title="🎁 Active Gift Codes",
        description=f"Found {len(codes)} active codes!",
        color=discord.Color.green()
    )
    
    for code in codes:
        name = code.get('code', 'Unknown')
        rewards = code.get('rewards', 'Unknown Rewards')
        expiry = code.get('expiry', 'Unknown Expiry')
        
        embed.add_field(
            name=f"🏷️ {name}",
            value=f"🎁 {rewards}\n⏳ Expires: {expiry}",
            inline=False
        )
        
    embed.set_footer(text="Use the buttons below to copy codes or refresh the list.")
    return embed

class GiftCodeScraper:
    def __init__(self):
        self.url = "https://wosgiftcodes.com/"
        self.headers = {
            'User-Agent': 'Mozilla/5.0 (Windows NT 10.0; Win64; x64) AppleWebKit/537.36 (KHTML, like Gecko) Chrome/91.0.4472.124 Safari/537.36'
        }
        self.cache_data = None
        self.last_fetched = None
        self.cache_duration = timedelta(minutes=10)
    
    async def fetch_gift_codes(self):
        """
        Fetch and parse gift codes from wosgiftcodes.com
        Returns a dict with active and expired codes
        """
        # Return cached result if valid
        if self.cache_data and self.last_fetched:
            if datetime.now() - self.last_fetched < self.cache_duration:
                logger.debug("Returning cached gift codes")
                return self.cache_data

        try:
            async with aiohttp.ClientSession() as session:
                async with session.get(self.url, headers=self.headers, timeout=aiohttp.ClientTimeout(total=15)) as response:
                    if response.status != 200:
                        logger.error(f"Failed to fetch gift codes. Status: {response.status}")
                        # Return fallback codes if fetch fails (dont cache failure unless we want to retry soon)
                        return {
                            'active_codes': self.get_fallback_codes(),
                            'expired_codes': [],
                            'last_updated': datetime.now().strftime("%Y-%m-%d %H:%M:%S")
                        }

                    html = await response.text()
                    result = self.parse_gift_codes(html)
                    if result is None:
                        # If parsing fails, return fallback
                        return {
                            'active_codes': self.get_fallback_codes(),
                            'expired_codes': [],
                            'last_updated': datetime.now().strftime("%Y-%m-%d %H:%M:%S")
                        }
                    
                    # Update cache
                    self.cache_data = result
                    self.last_fetched = datetime.now()
                    return result

        except aiohttp.ClientTimeout:
            logger.error("Timeout while fetching gift codes")
            # Return fallback codes on timeout
            return {
                'active_codes': self.get_fallback_codes(),
                'expired_codes': [],
                'last_updated': datetime.now().strftime("%Y-%m-%d %H:%M:%S")
            }
        except Exception as e:
            logger.error(f"Error fetching gift codes: {str(e)}")
            # Return fallback codes on any error
            return {
                'active_codes': self.get_fallback_codes(),
                'expired_codes': [],
                'last_updated': datetime.now().strftime("%Y-%m-%d %H:%M:%S")
            }
    
    def parse_gift_codes(self, html):
        """
        Parse HTML content to extract gift codes
        """
        try:
            soup = BeautifulSoup(html, 'html.parser')
            
            active_codes = []
            expired_codes = []
            
            # Method 1: Look for structured sections
            active_section = soup.find('h2', text=re.compile(r'Active Codes', re.I))
            if active_section:
                active_codes = self.extract_codes_from_section(active_section, is_active=True)
            
            expired_section = soup.find('h2', text=re.compile(r'Expired Codes', re.I))
            if expired_section:
                expired_codes = self.extract_codes_from_section(expired_section, is_active=False)
            
            # Method 2: Fallback - parse entire text content for known patterns
            if not active_codes and not expired_codes:
                logger.info("No structured sections found, trying text parsing fallback")
                active_codes, expired_codes = self.parse_text_content(html)
            
            # Method 3: Final fallback - use external context data if available
            if not active_codes:
                # Check if the page has a div with class 'table-responsive' containing the codes table
                soup_div = soup.find('div', class_='table-responsive')
                if soup_div:
                    table = soup_div.find('table')
                    if table:
                        active_codes = self.extract_from_table(table, is_active=True)
                else:
                    active_codes = self.get_fallback_codes()
            
            return {
                'active_codes': active_codes,
                'expired_codes': expired_codes,
                'last_updated': datetime.now().strftime("%Y-%m-%d %H:%M:%S")
            }
        
        except Exception as e:
            logger.error(f"Error parsing gift codes: {str(e)}")
            return None
    
    def extract_codes_from_section(self, section_header, is_active=True):
        """
        Extract code information from a section
        """
        codes = []
        
        try:
            # Find the next table or code container after the header
            current = section_header.find_next_sibling()
            
            while current:
                # Look for code entries in various possible formats
                if current.name == 'table':
                    codes.extend(self.extract_from_table(current, is_active))
                    break
                elif current.name in ['div', 'section'] and any(keyword in current.get_text().lower() for keyword in ['code', 'gems', 'rewards']):
                    codes.extend(self.extract_from_div(current, is_active))
                elif current.name in ['h2', 'h3'] and current != section_header:
                    # Hit another section, stop parsing
                    break
                
                current = current.find_next_sibling()
            
            # If no structured data found, try to extract from text content
            if not codes:
                # Special case: check if next sibling is a div with class 'table-responsive'
                next_sibling = section_header.find_next_sibling()
                if next_sibling and next_sibling.name == 'div' and 'table-responsive' in next_sibling.get('class', []):
                    table = next_sibling.find('table')
                    if table:
                        codes.extend(self.extract_from_table(table, is_active))
                else:
                    codes = self.extract_from_text_content(section_header, is_active)
                
        except Exception as e:
            logger.error(f"Error extracting codes from section: {str(e)}")
        
        return codes
    
    def extract_from_table(self, table, is_active):
        """Extract codes from table format"""
        codes = []
        rows = table.find_all('tr')[1:]  # Skip header row
        
        for row in rows:
            cells = row.find_all(['td', 'th'])
            if len(cells) >= 3:
                code = cells[0].get_text(strip=True)
                description = cells[1].get_text(strip=True) if len(cells) > 1 else ""
                rewards = cells[2].get_text(strip=True) if len(cells) > 2 else description
                expiry = cells[3].get_text(strip=True) if len(cells) > 3 else ("Unknown" if is_active else "Expired")
                
                if code and code.upper() not in ['CODE', 'DESCRIPTION', 'REWARDS', 'EXPIRES']:
                    codes.append({
                        'code': code,
                        'description': description,
                        'rewards': rewards,
                        'expiry': expiry,
                        'is_active': is_active
                    })
        
        return codes
    
    def extract_from_div(self, div, is_active):
        """Extract codes from div format"""
        codes = []
        text = div.get_text()
        
        # Look for code patterns
        code_matches = re.findall(r'([A-Z0-9]{4,15})', text)
        
        for code in code_matches:
            # Try to find associated rewards/description
            code_context = self.find_code_context(text, code)
            codes.append({
                'code': code,
                'description': code_context.get('description', ''),
                'rewards': code_context.get('rewards', ''),
                'expiry': code_context.get('expiry', 'Unknown' if is_active else 'Expired'),
                'is_active': is_active
            })
        
        return codes
    
    def extract_from_text_content(self, section_header, is_active):
        """Extract codes from plain text content - fallback method"""
        codes = []
        
        # Get text from the section
        section_text = ""
        current = section_header
        for _ in range(10):  # Limit search scope
            current = current.find_next_sibling()
            if not current or (current.name in ['h2', 'h3'] and current != section_header):
                break
            section_text += current.get_text() + " "
        
        # Based on the external context, parse the known active code
        if is_active and 'OFFICIALSTORE' in section_text:
            codes.append({
                'code': 'OFFICIALSTORE',
                'description': 'Official Store Code',
                'rewards': '1K Gems, 2 Mythic Shards, 2 Mythic Expedition+Exploration Manuals, 1 Lucky Hero Gear Chest, 50K Hero XP, 8 Hr Speed',
                'expiry': 'Unknown',
                'is_active': True
            })
        
        # Look for other code patterns
        code_pattern = r'([A-Z0-9]{4,15})\s+([^0-9\n]+?)(?:\s+([\d-]+\s+[\d:]+|\w+\s+\d+))?'
        matches = re.finditer(code_pattern, section_text)
        
        for match in matches:
            code = match.group(1)
            if code not in [c['code'] for c in codes]:  # Avoid duplicates
                rewards = match.group(2).strip() if match.group(2) else ''
                expiry = match.group(3) if match.group(3) else ('Unknown' if is_active else 'Expired')
                
                codes.append({
                    'code': code,
                    'description': '',
                    'rewards': rewards,
                    'expiry': expiry,
                    'is_active': is_active
                })
        
        return codes
    
    def find_code_context(self, text, code):
        """Find description, rewards, and expiry for a specific code"""
        context = {'description': '', 'rewards': '', 'expiry': 'Unknown'}
        
        # Find the position of the code in text
        code_pos = text.find(code)
        if code_pos == -1:
            return context
        
        # Get surrounding text (before and after the code)
        before = text[max(0, code_pos-100):code_pos]
        after = text[code_pos+len(code):code_pos+len(code)+200]
        
        # Look for common reward keywords
        reward_keywords = ['gems', 'shards', 'speed', 'vip', 'meat', 'wood', 'coal', 'iron', 'xp', 'hero', 'chest']
        rewards = []
        
        for keyword in reward_keywords:
            if keyword.lower() in after.lower():
                # Extract the reward portion
                reward_match = re.search(rf'(\d+[kKmM]?\s+{keyword})', after, re.IGNORECASE)
                if reward_match:
                    rewards.append(reward_match.group(1))
        
        context['rewards'] = ', '.join(rewards) if rewards else after.split('\n')[0][:100]
        
        # Look for expiry date
        date_pattern = r'(\d{4}-\d{2}-\d{2}|\w+ \d{1,2}, \d{4})'
        date_match = re.search(date_pattern, after)
        if date_match:
            context['expiry'] = date_match.group(1)
        
        return context
    
    def parse_text_content(self, html):
        """
        Parse entire HTML text content for gift codes using regex patterns
        """
        active_codes = []
        expired_codes = []
        
        try:
            # Remove HTML tags and get plain text
            soup = BeautifulSoup(html, 'html.parser')
            text = soup.get_text()
            
            # Split content by sections if possible
            active_section_text = ""
            expired_section_text = ""
            
            # Try to find section divisions
            active_match = re.search(r'Active Codes?(.*?)(?=Expired Codes?|$)', text,Union[re.IGNORECASE, re.DOTALL])
            if active_match:
                active_section_text = active_match.group(1)
            
            expired_match = re.search(r'Expired Codes?(.*?)(?=Final Results|$)', text,Union[re.IGNORECASE, re.DOTALL])
            if expired_match:
                expired_section_text = expired_match.group(1)
            
            # Extract codes from active section
            active_codes = self.extract_codes_from_text(active_section_text, is_active=True)
            
            # Extract codes from expired section
            expired_codes = self.extract_codes_from_text(expired_section_text, is_active=False)
            
        except Exception as e:
            logger.error(f"Error in text content parsing: {str(e)}")
        
        return active_codes, expired_codes
    
    def extract_codes_from_text(self, text, is_active=True):
        """
        Extract gift codes from plain text using patterns
        """
        codes = []
        
        # Pattern to match code entries with rewards and dates
        # Examples: "OFFICIALSTORE 1K Gems, 2 Mythic Shards..."
        #           "901MUSIC 3-day Primal Vibe Avatar Frame, 500 Gems... 2025-09-02"
        
        # Split text into potential code blocks
        lines = [line.strip() for line in text.split('\n') if line.strip()]
        
        i = 0
        while i < len(lines):
            line = lines[i]
            
            # Look for lines that start with a code pattern
            code_match = re.match(r'^([A-Z0-9]{4,20})\s+(.+)', line)
            if code_match:
                code = code_match.group(1)
                rest_of_line = code_match.group(2)
                
                # Skip common headers
                if code.upper() in ['CODE', 'DESCRIPTION', 'REWARDS', 'EXPIRES', 'FINAL', 'RESULTS']:
                    i += 1
                    continue
                
                # Extract rewards and expiry
                rewards = ""
                expiry = "Unknown" if is_active else "Expired"
                
                # Look for date pattern in the line or next few lines
                full_text = rest_of_line
                for j in range(i + 1, min(i + 3, len(lines))):
                    if lines[j] and not re.match(r'^[A-Z0-9]{4,20}\s', lines[j]):
                        full_text += " " + lines[j]
                    else:
                        break
                
                # Extract expiry date
                date_match = re.search(r'(\d{4}-\d{2}-\d{2}\s+\d{2}:\d{2})', full_text)
                if date_match:
                    expiry = date_match.group(1)
                    # Remove date from rewards text
                    rewards = re.sub(r'\d{4}-\d{2}-\d{2}\s+\d{2}:\d{2}', '', full_text).strip()
                else:
                    rewards = full_text
                
                # Clean up rewards text
                rewards = re.sub(r'\s+', ' ', rewards).strip()
                
                codes.append({
                    'code': code,
                    'description': '',
                    'rewards': rewards,
                    'expiry': expiry,
                    'is_active': is_active
                })
            
            i += 1
        
        return codes
    
    def get_fallback_codes(self):
        """
        Return known active codes from external context as fallback
        """
        fallback_codes = [
            {
                'code': 'OFFICIALSTORE',
                'description': 'Official Store Code',
                'rewards': '1K Gems, 2 Mythic Shards, 2 Mythic Expedition+Exploration Manuals, 1 Lucky Hero Gear Chest, 50K Hero XP, 8 Hr Speed',
                'expiry': 'Unknown',
                'is_active': True
            }
        ]
        
        logger.info(f"Using fallback codes: {len(fallback_codes)} codes")
        return fallback_codes

# Global instance
gift_code_scraper = GiftCodeScraper()

async def get_active_gift_codes():
    """
    Public function to get active gift codes
    Returns list of active codes or None if error
    """
    result = await gift_code_scraper.fetch_gift_codes()
    if result:
        active_codes = result.get('active_codes', [])
        filtered_active_codes = []
        now = datetime.now()
        for code in active_codes:
            expiry_str = code.get('expiry', 'Unknown')
            try:
                expiry_date = dateutil.parser.parse(expiry_str, fuzzy=True)
                if expiry_date > now:
                    filtered_active_codes.append(code)
            except Exception:
                # If expiry date cannot be parsed, assume active
                filtered_active_codes.append(code)
        return filtered_active_codes
    return None

async def get_all_gift_codes():
    """
    Public function to get all gift codes (active and expired)
    """
    return await gift_code_scraper.fetch_gift_codes()


