import requests
import hashlib
import time

def test_redeem(fid, code, captcha, timestamp):
    url = "https://wos-giftcode-api.centurygame.com/api/gift_code"
    api_key = "tB87#kPtkxqOS2"
    
    params = {
        "fid": str(fid),
        "cdk": code,
        "captcha_code": captcha,
        "time": str(timestamp)
    }
    sorted_keys = sorted(params.keys())
    sorted_str = "&".join([f"{k}={params[k]}" for k in sorted_keys])
    sign = hashlib.md5((sorted_str + api_key).encode()).hexdigest()
    params["sign"] = sign
    
    headers = {
        'Accept': 'application/json, text/plain, */*',
        'Content-Type': 'application/x-www-form-urlencoded',
        'Origin': 'https://wos-giftcode.centurygame.com',
        'Referer': 'https://wos-giftcode.centurygame.com/',
        'User-Agent': 'Mozilla/5.0 (Windows NT 10.0; Win64; x64) AppleWebKit/537.36 (KHTML, like Gecko) Chrome/124.0.0.0 Safari/537.36',
    }
    
    resp = requests.post(url, headers=headers, data=params)
    print(f"Params: {params}")
    print(f"Sign Str: {sorted_str + api_key}")
    print(f"Response: {resp.json()}")

if __name__ == "__main__":
    # From bot log: fid 492244270, code CHILDRENSDAY505, captcha SKP9
    test_redeem("492244270", "CHILDRENSDAY505", "SKP9", int(time.time() * 1000))
