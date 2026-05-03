import base64
import json
import os
import time
import random
import requests
from requests.adapters import HTTPAdapter


async def fetch_captcha(gift_ops, player_id, session=None):
    """Fetch a captcha image for a player ID using gift_ops context."""
    if session is None:
        session = requests.Session()
        session.mount("https://", HTTPAdapter(max_retries=gift_ops.retry_config))

    headers = {
        "accept": "application/json, text/plain, */*",
        "content-type": "application/x-www-form-urlencoded",
        "origin": gift_ops.wos_giftcode_redemption_url,
    }

    data_to_encode = {
        "fid": player_id,
        "time": f"{int(time.time() * 1000)}",
        "init": "0"
    }
    data = gift_ops.encode_data(data_to_encode)

    try:
        response = session.post(
            gift_ops.wos_captcha_url,
            headers=headers,
            data=data,
        )

        if response.status_code == 200:
            captcha_data = response.json()
            if captcha_data.get("code") == 1 and captcha_data.get("msg") == "CAPTCHA GET TOO FREQUENT.":
                return None, "CAPTCHA_TOO_FREQUENT"

            if "data" in captcha_data and "img" in captcha_data["data"]:
                return captcha_data["data"]["img"], None

        return None, "CAPTCHA_FETCH_ERROR"
    except Exception as e:
        gift_ops.logger.exception(f"Error fetching captcha: {e}")
        return None, f"CAPTCHA_EXCEPTION: {str(e)}"


async def attempt_gift_code_with_api(gift_ops, player_id, giftcode, session):
    """Attempt to redeem a gift code using captcha solving logic. Returns same tuple as original method."""
    max_ocr_attempts = 4

    for attempt in range(max_ocr_attempts):
        gift_ops.logger.info(f"GiftOps: Attempt {attempt + 1}/{max_ocr_attempts} to fetch/solve captcha for FID {player_id}")

        # Fetch captcha
        captcha_image_base64, error = await fetch_captcha(gift_ops, player_id, session)

        if error:
            if error == "CAPTCHA_TOO_FREQUENT":
                gift_ops.logger.info(f"GiftOps: API returned CAPTCHA_TOO_FREQUENT for FID {player_id}")
                return "CAPTCHA_TOO_FREQUENT", None, None, None
            else:
                gift_ops.logger.error(f"GiftOps: Captcha fetch error for FID {player_id}: {error}")
                return "CAPTCHA_FETCH_ERROR", None, None, None

        if not captcha_image_base64:
            gift_ops.logger.warning(f"GiftOps: No captcha image returned for FID {player_id}")
            return "CAPTCHA_FETCH_ERROR", None, None, None

        # Decode captcha image
        try:
            if captcha_image_base64.startswith("data:image"):
                img_b64_data = captcha_image_base64.split(",", 1)[1]
            else:
                img_b64_data = captcha_image_base64
            image_bytes = base64.b64decode(img_b64_data)
        except Exception as decode_err:
            gift_ops.logger.error(f"Failed to decode base64 image for FID {player_id}: {decode_err}")
            return "CAPTCHA_FETCH_ERROR", None, None, None

        # Solve captcha
        gift_ops.processing_stats["ocr_solver_calls"] += 1
        captcha_code, success, method, confidence, _ = await gift_ops.captcha_solver.solve_captcha(
            image_bytes, fid=player_id, attempt=attempt)

        if not success:
            gift_ops.logger.info(f"GiftOps: OCR failed for FID {player_id} on attempt {attempt + 1}")
            if attempt == max_ocr_attempts - 1:
                return "MAX_CAPTCHA_ATTEMPTS_REACHED", None, None, None
            continue

        gift_ops.processing_stats["ocr_valid_format"] += 1
        gift_ops.logger.info(f"GiftOps: OCR solved for {player_id}: {captcha_code} (method:{method}, conf:{confidence:.2f}, attempt:{attempt+1})")

        # Submit gift code with solved captcha
        data_to_encode = {
            "fid": f"{player_id}",
            "cdk": giftcode,
            "captcha_code": captcha_code,
            "time": f"{int(time.time() * 1000)}"
        }
        data = gift_ops.encode_data(data_to_encode)
        gift_ops.processing_stats["captcha_submissions"] += 1

        # Submit to gift code API
        response_giftcode = session.post(gift_ops.wos_giftcode_url, data=data)

        # Log the redemption attempt
        log_entry_redeem = f"\n{time.time()} API REQ - Gift Code Redeem\nFID:{player_id}, Code:{giftcode}, Captcha:{captcha_code}\n"
        try:
            response_json_redeem = response_giftcode.json()
            log_entry_redeem += f"Resp Code: {response_giftcode.status_code}\nResponse JSON:\n{json.dumps(response_json_redeem, indent=2)}\n"
        except json.JSONDecodeError:
            response_json_redeem = {}
            log_entry_redeem += f"Resp Code: {response_giftcode.status_code}\nResponse Text (Not JSON): {response_giftcode.text[:500]}...\n"
        log_entry_redeem += "-" * 50 + "\n"
        try:
            gift_ops.giftlog.info(log_entry_redeem.strip())
        except Exception:
            pass

        # Parse response
        msg = response_json_redeem.get("msg", "Unknown Error").strip('.')
        err_code = response_json_redeem.get("err_code")

        captcha_errors = {
            ("CAPTCHA CHECK ERROR", 40103),
            ("CAPTCHA GET TOO FREQUENT", 40100),
            ("CAPTCHA CHECK TOO FREQUENT", 40101),
            ("CAPTCHA EXPIRED", 40102)
        }

        is_captcha_error = (msg, err_code) in captcha_errors

        if is_captcha_error:
            gift_ops.processing_stats["server_validation_failure"] += 1
            if attempt == max_ocr_attempts - 1:
                return "CAPTCHA_INVALID", image_bytes, captcha_code, method
            else:
                gift_ops.logger.info(f"GiftOps: CAPTCHA_INVALID for FID {player_id} on attempt {attempt + 1} (msg: {msg}). Retrying...")
                await asyncio_sleep(random.uniform(1.5, 2.5))
                continue
        else:
            gift_ops.processing_stats["server_validation_success"] += 1

        # Determine final status
        if msg == "SUCCESS":
            status = "SUCCESS"
        elif msg == "RECEIVED" and err_code == 40008:
            status = "RECEIVED"
        elif msg == "SAME TYPE EXCHANGE" and err_code == 40011:
            status = "SAME TYPE EXCHANGE"
        elif msg == "TIME ERROR" and err_code == 40007:
            status = "TIME_ERROR"
        elif msg == "CDK NOT FOUND" and err_code == 40014:
            status = "CDK_NOT_FOUND"
        elif msg == "USED" and err_code == 40005:
            status = "USAGE_LIMIT"
        elif msg == "TIMEOUT RETRY" and err_code == 40004:
            status = "TIMEOUT_RETRY"
        elif msg == "NOT LOGIN":
            status = "LOGIN_EXPIRED_MID_PROCESS"
        elif "sign error" in msg.lower():
            status = "SIGN_ERROR"
            gift_ops.logger.error(f"[SIGN ERROR] Sign error detected for FID {player_id}, code {giftcode}")
            gift_ops.logger.error(f"[SIGN ERROR] Response: {response_json_redeem}")
        elif msg == "STOVE_LV ERROR" and err_code == 40006:
            status = "TOO_SMALL_SPEND_MORE"
            gift_ops.logger.error(f"[FURNACE LVL ERROR] Furnace level is too low for FID {player_id}, code {giftcode}")
            gift_ops.logger.error(f"[FURNACE LVL ERROR] Response: {response_json_redeem}")
        elif msg == "RECHARGE_MONEY ERROR" and err_code == 40017:
            status = "TOO_POOR_SPEND_MORE"
            gift_ops.logger.error(f"[VIP LEVEL ERROR] VIP level is too low for FID {player_id}, code {giftcode}")
            gift_ops.logger.error(f"[VIP LEVEL ERROR] Response: {response_json_redeem}")
        else:
            status = "UNKNOWN_API_RESPONSE"
            gift_ops.logger.info(f"Unknown API response for {player_id}: msg='{msg}', err_code={err_code}")

        return status, image_bytes, captcha_code, method

    return "MAX_CAPTCHA_ATTEMPTS_REACHED", None, None, None


async def asyncio_sleep(delay):
    """Small wrapper to allow asyncio.sleep inside this module without importing asyncio at top-level in some test contexts."""
    import asyncio
    await asyncio.sleep(delay)
