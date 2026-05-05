import requests
import hashlib
import time
import os
import sys

# Add current dir to path
sys.path.append(os.getcwd())

try:
    from cogs.gift_captchasolver import GiftCaptchaSolver
except ImportError:
    # If running on Oracle, might need different path
    sys.path.append("/home/ubuntu/bot")
    from cogs.gift_captchasolver import GiftCaptchaSolver

def get_sign(params, api_key):
    sorted_keys = sorted(params.keys())
    sorted_str = "&".join([f"{k}={params[k]}" for k in sorted_keys])
    return hashlib.md5((sorted_str + api_key).encode()).hexdigest()

async def test_case_sensitivity(fid, code_list):
    api_key = "tB87#kPtkxqOS2"
    headers = {
        'Accept': 'application/json, text/plain, */*',
        'Content-Type': 'application/x-www-form-urlencoded',
        'Origin': 'https://wos-giftcode.centurygame.com',
        'Referer': 'https://wos-giftcode.centurygame.com/',
        'User-Agent': 'Mozilla/5.0 (Windows NT 10.0; Win64; x64) AppleWebKit/537.36 (KHTML, like Gecko) Chrome/124.0.0.0 Safari/537.36',
    }
    
    solver = GiftCaptchaSolver()
    session = requests.Session()
    
    for code in code_list:
        print(f"\n--- Testing code: {code} ---")
        # 1. Login
        timestamp = str(int(time.time() * 1000))
        login_params = {"fid": str(fid), "time": timestamp}
        login_params["sign"] = get_sign(login_params, api_key)
        login_url = "https://wos-giftcode-api.centurygame.com/api/player"
        resp = session.post(login_url, headers=headers, data=login_params)
        print(f"Login: {resp.json().get('msg')}")
        
        # 2. Get Captcha JSON
        timestamp = str(int(time.time() * 1000))
        captcha_params = {"fid": str(fid), "time": timestamp}
        captcha_params["sign"] = get_sign(captcha_params, api_key)
        captcha_url = "https://wos-giftcode-api.centurygame.com/api/get_captcha"
        resp = session.post(captcha_url, headers=headers, data=captcha_params)
        
        # 3. Get Image and Solve
        image_url = f"{captcha_url}?fid={fid}&time={timestamp}&sign={captcha_params['sign']}"
        img_resp = session.get(image_url, headers=headers)
        captcha_result = await solver.solve_captcha(img_resp.content)
        captcha_text, success, model, conf, solve_time = captcha_result
        print(f"OCR solved: {captcha_text} (Success: {success})")
        
        if not success or not captcha_text:
            print("OCR failed, skipping redemption")
            continue
            
        # 4. Redeem
        redeem_params = {
            "fid": str(fid),
            "cdk": code,
            "captcha_code": captcha_text,
            "time": timestamp
        }
        redeem_params["sign"] = get_sign(redeem_params, api_key)
        redeem_url = "https://wos-giftcode-api.centurygame.com/api/gift_code"
        resp = session.post(redeem_url, headers=headers, data=redeem_params)
        print(f"Response: {resp.json()}")
        time.sleep(2)

if __name__ == "__main__":
    import asyncio
    fid = "519056344"
    codes = ["ChildrensDay505", "CHILDRENSDAY505", "OFFICIALSTORE"]
    asyncio.run(test_case_sensitivity(fid, codes))
