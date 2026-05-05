import requests
import hashlib
import time
import os
import sys
import asyncio

# Add the bot directory to sys.path to import modules
sys.path.append(os.path.abspath(os.path.join(os.path.dirname(__file__), '..')))

from cogs.gift_captchasolver import GiftCaptchaSolver

async def test_real_redemption(fid, code):
    api_key = "tB87#kPtkxqOS2"
    headers = {
        'Accept': 'application/json, text/plain, */*',
        'Content-Type': 'application/x-www-form-urlencoded',
        'Origin': 'https://wos-giftcode.centurygame.com',
        'Referer': 'https://wos-giftcode.centurygame.com/',
        'User-Agent': 'Mozilla/5.0 (Windows NT 10.0; Win64; x64) AppleWebKit/537.36 (KHTML, like Gecko) Chrome/124.0.0.0 Safari/537.36',
    }
    
    solver = GiftCaptchaSolver(None) # None for bot instance
    
    session = requests.Session()
    
    # 1. Login
    timestamp = str(int(time.time() * 1000))
    login_params = {"fid": str(fid), "time": timestamp}
    sorted_keys = sorted(login_params.keys())
    sorted_str = "&".join([f"{k}={login_params[k]}" for k in sorted_keys])
    login_params["sign"] = hashlib.md5((sorted_str + api_key).encode()).hexdigest()
    
    login_url = "https://wos-giftcode-api.centurygame.com/api/player"
    resp = session.post(login_url, headers=headers, data=login_params)
    print(f"Login: {resp.json().get('msg')}")
    
    # 2. Get Captcha
    timestamp = str(int(time.time() * 1000))
    captcha_params = {"fid": str(fid), "time": timestamp}
    sorted_keys = sorted(captcha_params.keys())
    sorted_str = "&".join([f"{k}={captcha_params[k]}" for k in sorted_keys])
    captcha_params["sign"] = hashlib.md5((sorted_str + api_key).encode()).hexdigest()
    
    captcha_url = "https://wos-giftcode-api.centurygame.com/api/get_captcha"
    resp = session.post(captcha_url, headers=headers, data=captcha_params)
    captcha_json = resp.json()
    
    if captcha_json.get("msg") != "SUCCESS":
        print(f"Failed to get captcha: {captcha_json}")
        return

    # Solve Captcha
    image_url = "https://wos-giftcode-api.centurygame.com/api/get_captcha?fid=" + str(fid) + "&time=" + timestamp + "&sign=" + captcha_params["sign"]
    img_resp = session.get(image_url, headers=headers)
    captcha_code, success, _, _, _ = await solver.solve_captcha(img_resp.content, fid=fid)
    
    if not success:
        print("Failed to solve captcha")
        return
    print(f"Solved Captcha: {captcha_code}")
    
    # 3. Redeem
    timestamp = str(int(time.time() * 1000))
    redeem_params = {
        "fid": str(fid),
        "cdk": code,
        "captcha_code": captcha_code,
        "time": timestamp
    }
    sorted_keys = sorted(redeem_params.keys())
    sorted_str = "&".join([f"{k}={redeem_params[k]}" for k in sorted_keys])
    redeem_params["sign"] = hashlib.md5((sorted_str + api_key).encode()).hexdigest()
    
    redeem_url = "https://wos-giftcode-api.centurygame.com/api/gift_code"
    resp = session.post(redeem_url, headers=headers, data=redeem_params)
    print(f"Redeeming {code}: {resp.json()}")

if __name__ == "__main__":
    fid = "519056344"
    asyncio.run(test_real_redemption(fid, "CHILDRENSDAY505"))
    asyncio.run(test_real_redemption(fid, "ChildrensDay505"))
