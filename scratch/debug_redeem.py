import requests
import hashlib
import time

def get_sign(params, api_key):
    sorted_keys = sorted(params.keys())
    sorted_str = "&".join([f"{k}={params[k]}" for k in sorted_keys])
    return hashlib.md5((sorted_str + api_key).encode()).hexdigest()

def test_redeem(fid, code):
    api_key = "tB87#kPtkxqOS2"
    headers = {
        'Accept': 'application/json, text/plain, */*',
        'Content-Type': 'application/x-www-form-urlencoded',
        'Origin': 'https://wos-giftcode.centurygame.com',
        'Referer': 'https://wos-giftcode.centurygame.com/',
        'User-Agent': 'Mozilla/5.0 (Windows NT 10.0; Win64; x64) AppleWebKit/537.36 (KHTML, like Gecko) Chrome/124.0.0.0 Safari/537.36',
    }
    
    session = requests.Session()
    
    # 1. Login
    timestamp = str(int(time.time() * 1000))
    login_params = {"fid": str(fid), "time": timestamp}
    login_params["sign"] = get_sign(login_params, api_key)
    
    login_url = "https://wos-giftcode-api.centurygame.com/api/player"
    resp = session.post(login_url, headers=headers, data=login_params)
    print(f"Login Response: {resp.json()}")
    
    # 2. Get Captcha (to be safe)
    timestamp = str(int(time.time() * 1000))
    captcha_params = {"fid": str(fid), "time": timestamp}
    captcha_params["sign"] = get_sign(captcha_params, api_key)
    captcha_url = "https://wos-giftcode-api.centurygame.com/api/get_captcha"
    resp = session.post(captcha_url, headers=headers, data=captcha_params)
    print(f"Captcha Response: {resp.json()}")
    
    # 3. Redeem
    timestamp = str(int(time.time() * 1000))
    redeem_params = {
        "fid": str(fid),
        "cdk": code,
        "captcha_code": "1234", # Dummy to trigger CDK check if possible
        "time": timestamp
    }
    redeem_params["sign"] = get_sign(redeem_params, api_key)
    redeem_url = "https://wos-giftcode-api.centurygame.com/api/gift_code"
    resp = session.post(redeem_url, headers=headers, data=redeem_params)
    print(f"Redeeming {code}: {resp.json()}")

if __name__ == "__main__":
    fid = "519056344"
    test_redeem(fid, "ChildrensDay505")
    test_redeem(fid, "CHILDRENSDAY505")
