"""
Patch script: replaces the corrupted fetch_captcha + attempt_gift_code_with_api
block in manage_giftcode.py with correct, robust versions.
"""
import shutil, datetime

SRC = 'cogs/manage_giftcode.py'
BAK = f'cogs/manage_giftcode.py.bak_{datetime.datetime.now().strftime("%Y%m%d_%H%M%S")}'

START_MARKER = '    async def fetch_captcha(self, player_id, session):'
END_MARKER   = '    async def get_stove_info_wos(self, player_id, session=None):'

NEW_BLOCK = '''\
    async def fetch_captcha(self, player_id, session):
        """Fetch CAPTCHA image from WOS API"""
        try:
            import time

            data_to_encode = {
                "fid": str(player_id),
                "time": str(int(time.time() * 1000))
            }
            data = self.encode_data(data_to_encode)

            try:
                headers = {
                    'Content-Type': 'application/x-www-form-urlencoded',
                    'Origin': 'https://wos-giftcode.centurygame.com',
                    'Referer': 'https://wos-giftcode.centurygame.com/',
                    'User-Agent': 'Mozilla/5.0 (Windows NT 10.0; Win64; x64) AppleWebKit/537.36 (KHTML, like Gecko) Chrome/122.0.0.0 Safari/537.36'
                }
                timeout = aiohttp.ClientTimeout(total=12)

                async with session.post(self.wos_captcha_url, headers=headers, data=data, timeout=timeout) as response:
                    if response.status == 403:
                        self.logger.error(f"\\u274c 403 Forbidden in fetch_captcha for FID {player_id}.")
                        return None, "FORBIDDEN"
                    if response.status == 429:
                        self.logger.warning(f"Rate limited (429) in fetch_captcha for FID {player_id}")
                        return None, "RATE_LIMITED"

                    if response.status == 200:
                        try:
                            response_json = await response.json(content_type=None)
                            api_msg = str(response_json.get("msg", "")).lower()
                            if api_msg == "success":
                                captcha_data = response_json.get("data")
                                if captcha_data:
                                    return captcha_data, None
                                else:
                                    self.logger.warning(f"CAPTCHA API success but no data for FID {player_id}: {response_json}")
                                    return None, "CAPTCHA_FETCH_ERROR"
                            elif "too frequent" in api_msg or "captcha get too frequent" in api_msg:
                                return None, "CAPTCHA_TOO_FREQUENT"
                            else:
                                self.logger.warning(f"CAPTCHA API unexpected msg for FID {player_id}: \\'{response_json.get(\\'msg\\', \\'Unknown\\')}\\'")
                                return None, f"API Error: {response_json.get(\\'msg\\', \\'Unknown\\')}"
                        except Exception as json_error:
                            try:
                                text = await response.text()
                            except Exception:
                                text = ""
                            if text.strip().startswith("<!DOCTYPE") or text.strip().startswith("<html"):
                                self.logger.warning(f"HTML rate-limit page in fetch_captcha for FID {player_id}")
                                return None, "RATE_LIMITED"
                            self.logger.error(f"JSON decode error in fetch_captcha for FID {player_id}: {json_error}")
                            return None, f"JSON Error: {json_error}"
                    else:
                        self.logger.warning(f"HTTP {response.status} in fetch_captcha for FID {player_id}")
                        return None, f"HTTP Error: {response.status}"

            except asyncio.TimeoutError:
                self.logger.warning(f"Timeout in fetch_captcha for FID {player_id}")
                return None, "TIMEOUT"
            except Exception as e:
                self.logger.error(f"Request error in fetch_captcha for FID {player_id}: {e}")
                return None, f"Request Error: {e}"

        except Exception as e:
            self.logger.exception(f"Unexpected error in fetch_captcha for FID {player_id}: {e}")
            return None, str(e)

    async def attempt_gift_code_with_api(self, player_id, giftcode, session):
        """Attempt to redeem a gift code with CAPTCHA solving.

        Robust design: transient captcha-fetch errors are retried with
        exponential backoff *within* this function so the caller sees a
        definitive verdict rather than a transient intermediate error.
        """
        import time
        import base64
        import random

        if not self.captcha_solver or not self.captcha_solver.is_initialized:
            self.logger.error(f"\\u274c CAPTCHA solver not available for FID {player_id}")
            return "CAPTCHA_SOLVER_NOT_AVAILABLE", None, None, None

        max_ocr_attempts = 8  # increased from 4 for robustness

        for attempt in range(max_ocr_attempts):
            self.logger.info(f"Attempt {attempt + 1}/{max_ocr_attempts} to redeem for FID {player_id}")

            # ── Inner captcha-fetch retry loop ────────────────────────────────
            # Transient API errors (rate-limit, timeout, JSON glitches) are
            # retried here so they do NOT surface as CAPTCHA_FETCH_ERROR to the
            # outer redemption loop unless every fetch try is exhausted.
            captcha_image_base64 = None
            FETCH_RETRIES = 4
            last_fetch_error = None
            for fetch_try in range(FETCH_RETRIES):
                captcha_image_base64, last_fetch_error = await self.fetch_captcha(player_id, session)
                if captcha_image_base64 and not last_fetch_error:
                    break  # got a valid image — proceed to solve

                # Permanent: don\'t retry
                if last_fetch_error == "FORBIDDEN":
                    return "FORBIDDEN", None, None, None

                # Rate-limit / too-frequent: back off then retry the fetch
                if last_fetch_error in ("RATE_LIMITED", "CAPTCHA_TOO_FREQUENT"):
                    wait = min(6.0 * (fetch_try + 1), 30.0)
                    self.logger.warning(
                        f"\\u23f3 CAPTCHA fetch rate-limited for FID {player_id} "
                        f"(fetch_try {fetch_try+1}/{FETCH_RETRIES}), waiting {wait:.1f}s"
                    )
                    await asyncio.sleep(wait)
                    continue

                # Timeout / request error: short backoff then retry
                if last_fetch_error in ("TIMEOUT", "REQUEST_ERROR") or (
                    last_fetch_error and str(last_fetch_error).startswith("Request Error")
                ):
                    wait = min(3.0 * (fetch_try + 1), 15.0)
                    self.logger.warning(
                        f"\\u23f3 CAPTCHA fetch timeout/error for FID {player_id}: {last_fetch_error} "
                        f"(fetch_try {fetch_try+1}/{FETCH_RETRIES}), retrying in {wait:.1f}s"
                    )
                    await asyncio.sleep(wait)
                    continue

                # Other transient error (API msg, JSON, HTTP non-200): brief retry
                wait = min(2.0 * (fetch_try + 1), 10.0)
                self.logger.warning(
                    f"\\u26a0\\ufe0f CAPTCHA fetch error for FID {player_id}: {last_fetch_error} "
                    f"(fetch_try {fetch_try+1}/{FETCH_RETRIES}), retrying in {wait:.1f}s"
                )
                await asyncio.sleep(wait)

            # If still no image after all fetch retries
            if not captcha_image_base64:
                if last_fetch_error in ("RATE_LIMITED", "CAPTCHA_TOO_FREQUENT"):
                    return "RATE_LIMITED", None, None, None
                if attempt == max_ocr_attempts - 1:
                    return "CAPTCHA_FETCH_ERROR", None, None, None
                # Wait briefly then retry the outer OCR attempt
                await asyncio.sleep(random.uniform(1.5, 3.0))
                continue

            # ── Decode captcha image ──────────────────────────────────────────
            try:
                img_b64_data = None
                if isinstance(captcha_image_base64, dict):
                    img_b64_data = captcha_image_base64.get(\'img\', \'\') or captcha_image_base64.get(\'data\', \'\')
                    if img_b64_data and img_b64_data.startswith("data:image"):
                        img_b64_data = img_b64_data.split(",", 1)[1]
                elif isinstance(captcha_image_base64, str):
                    if captcha_image_base64.startswith("data:image"):
                        img_b64_data = captcha_image_base64.split(",", 1)[1]
                    else:
                        img_b64_data = captcha_image_base64
                else:
                    self.logger.error(f"Unexpected CAPTCHA data type: {type(captcha_image_base64)}")
                    if attempt == max_ocr_attempts - 1:
                        return "CAPTCHA_FETCH_ERROR", None, None, None
                    await asyncio.sleep(random.uniform(1.0, 2.0))
                    continue

                if not img_b64_data:
                    self.logger.error(f"CAPTCHA image data is empty for FID {player_id}")
                    if attempt == max_ocr_attempts - 1:
                        return "CAPTCHA_FETCH_ERROR", None, None, None
                    await asyncio.sleep(random.uniform(1.0, 2.0))
                    continue

                image_bytes = base64.b64decode(img_b64_data)
            except Exception as e:
                self.logger.error(f"Failed to decode base64 captcha image for FID {player_id}: {e}")
                if attempt == max_ocr_attempts - 1:
                    return "CAPTCHA_FETCH_ERROR", None, None, None
                await asyncio.sleep(random.uniform(1.0, 2.0))
                continue

            # ── Solve captcha ─────────────────────────────────────────────────
            captcha_code, success, method, confidence, _ = await self.captcha_solver.solve_captcha(
                image_bytes, fid=player_id, attempt=attempt)

            if not success:
                if attempt == max_ocr_attempts - 1:
                    return "MAX_CAPTCHA_ATTEMPTS_REACHED", None, None, None
                continue

            self.logger.info(f"OCR solved: {captcha_code} (method:{method}, conf:{confidence:.2f})")

            # ── Submit gift code with solved captcha ──────────────────────────
            data_to_encode = {
                "fid": str(player_id),
                "cdk": giftcode,
                "captcha_code": captcha_code,
                "time": str(int(time.time() * 1000))
            }
            data = self.encode_data(data_to_encode)

            try:
                headers = {
                    \'Accept\': \'application/json, text/plain, */*\',
                    \'Accept-Language\': \'en-US,en;q=0.9\',
                    \'Content-Type\': \'application/x-www-form-urlencoded\',
                    \'Origin\': \'https://wos-giftcode.centurygame.com\',
                    \'Referer\': \'https://wos-giftcode.centurygame.com/\',
                    \'User-Agent\': \'Mozilla/5.0 (Windows NT 10.0; Win64; x64) AppleWebKit/537.36 (KHTML, like Gecko) Chrome/124.0.0.0 Safari/537.36\',
                    \'sec-ch-ua\': \'\"Chromium\";v=\"124\", \"Google Chrome\";v=\"124\", \"Not-A.Brand\";v=\"99\"\',
                    \'sec-ch-ua-mobile\': \'?0\',
                    \'sec-ch-ua-platform\': \'\"Windows\"\',
                }
                timeout = aiohttp.ClientTimeout(total=20)

                async with session.post(self.wos_giftcode_url, headers=headers, data=data, timeout=timeout) as response:
                    if response.status == 403:
                        self.logger.error(f"\\u274c 403 Forbidden in gift code redemption for FID {player_id}.")
                        return "FORBIDDEN", None, giftcode, method

                    if response.status == 429:
                        self.logger.warning(f"Rate limited (429) in gift code redemption for FID {player_id}")
                        return "RATE_LIMITED", None, giftcode, method

                    if response.status != 200:
                        self.logger.warning(f"HTTP {response.status} in gift code redemption for FID {player_id}")
                        if attempt < max_ocr_attempts - 1:
                            await asyncio.sleep(random.uniform(1.5, 3.0))
                            continue
                        return f"HTTP_{response.status}", None, giftcode, method

                    try:
                        response_json = await response.json()
                        self.logger.info(f"\\U0001f50d [API RESPONSE] Status: {response.status} | Result: {response_json}")
                        msg = response_json.get("msg", "Unknown Error").strip(\'.\')
                        err_code = response_json.get("err_code")
                    except Exception as json_error:
                        response_text = await response.text()
                        if response_text.strip().startswith(\'<!DOCTYPE\') or response_text.strip().startswith(\'<html\'):
                            return "RATE_LIMITED", None, giftcode, method
                        self.logger.error(f"Error parsing gift code response for FID {player_id}: {json_error}")
                        return "RESPONSE_PARSE_ERROR", None, giftcode, method

            except asyncio.TimeoutError:
                self.logger.warning(f"Timeout in gift code redemption for FID {player_id} (attempt {attempt+1})")
                if attempt < max_ocr_attempts - 1:
                    await asyncio.sleep(random.uniform(2.0, 5.0))
                    continue
                return "TIMEOUT", None, giftcode, method
            except Exception as e:
                self.logger.error(f"Request error in redemption for FID {player_id}: {e}")
                if attempt < max_ocr_attempts - 1:
                    await asyncio.sleep(random.uniform(1.5, 3.0))
                    continue
                return "REQUEST_ERROR", None, giftcode, method

            # ── Check API response ────────────────────────────────────────────
            captcha_errors = {
                ("CAPTCHA CHECK ERROR", 40103),
                ("CAPTCHA GET TOO FREQUENT", 40100),
                ("CAPTCHA CHECK TOO FREQUENT", 40101),
                ("CAPTCHA EXPIRED", 40102)
            }

            is_captcha_error = (msg, err_code) in captcha_errors

            if is_captcha_error:
                if attempt == max_ocr_attempts - 1:
                    return "CAPTCHA_INVALID", image_bytes, captcha_code, method
                await asyncio.sleep(random.uniform(0.3, 0.7))
                continue

            msg = str(msg).upper()

            if msg == "SUCCESS":
                return "SUCCESS", image_bytes, captcha_code, method
            elif msg == "RECEIVED" and err_code == 40008:
                return "ALREADY_RECEIVED", image_bytes, captcha_code, method
            elif msg == "SAME TYPE EXCHANGE" and err_code == 40011:
                return "SAME TYPE EXCHANGE", image_bytes, captcha_code, method
            elif msg == "TIME ERROR" and err_code == 40007:
                return "TIME_ERROR", image_bytes, captcha_code, method
            elif msg == "CDK NOT FOUND":
                self.logger.warning(f"\\u274c CDK NOT FOUND for FID {player_id}")
                return "CDK_NOT_FOUND", image_bytes, captcha_code, method
            elif msg == "USAGE LIMIT" and err_code == 40009:
                return "USAGE_LIMIT", image_bytes, captcha_code, method
            else:
                self.logger.warning(f"\\u26a0\\ufe0f Unhandled API status: \\'{msg}\\' (code: {err_code}) for FID {player_id}")
                return f"UNKNOWN_STATUS_{msg}", image_bytes, captcha_code, method

        return "MAX_ATTEMPTS_REACHED", None, None, None

'''

with open(SRC, 'r', encoding='utf-8') as f:
    content = f.read()

start_idx = content.find(START_MARKER)
end_idx   = content.find(END_MARKER)

if start_idx == -1 or end_idx == -1:
    print("ERROR: Could not find markers!")
    exit(1)

print(f"Found markers: start={start_idx}, end={end_idx}")
print(f"Replacing {end_idx - start_idx} bytes...")

# Back up first
shutil.copy2(SRC, BAK)
print(f"Backed up to {BAK}")

new_content = content[:start_idx] + NEW_BLOCK + content[end_idx:]

with open(SRC, 'w', encoding='utf-8') as f:
    f.write(new_content)

print(f"Done! New file size: {len(new_content)} bytes")

# Quick verification
with open(SRC, 'r', encoding='utf-8') as f:
    verify = f.read()

if 'async def fetch_captcha' in verify and 'async def attempt_gift_code_with_api' in verify and 'async def get_stove_info_wos' in verify:
    print("✅ All three functions found in patched file")
else:
    print("❌ Verification failed!")

# Check for the key new logic
if 'FETCH_RETRIES = 4' in verify:
    print("✅ New inner fetch-retry loop is present")
else:
    print("❌ New retry logic NOT found!")

if 'max_ocr_attempts = 8' in verify:
    print("✅ max_ocr_attempts=8 confirmed")
