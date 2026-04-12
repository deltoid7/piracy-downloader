import re
import os
import sys
from urllib.parse import quote, unquote, urlparse
from curl_cffi import requests
from utils.m3u8_downloader import M3U8Downloader
from utils.core import print_credit, decrypt_key

os.system('cls' if os.name == 'nt' else 'clear')
print_credit()
print('다운로드할 영상의 url을 입력해주세요.')
input_url = input()

_p = urlparse(unquote(input_url.strip()))
_parts = [s for s in _p.path.split("/") if s]
base_url = f"{_p.scheme}://{_p.netloc}"
vid, eid = _parts[1], "/".join(_parts[2:])

os.system('cls' if os.name == 'nt' else 'clear')
print_credit()
print('딜레이를 설정해주세요. (추천 값: 5)')
_delay_in = input().strip()
try:
    delay = float(_delay_in) if _delay_in else 5.0
except ValueError:
    delay = 5.0

os.system('cls' if os.name == 'nt' else 'clear')
print_credit()
print(f"{vid} : {eid} 다운로드를 시작합니다.")

def extract(pattern, html):
    m = re.search(pattern, html, re.I | re.DOTALL)
    return m.group(1)

url = quote(f"{base_url}/video/{vid}/{eid}", safe=":/")
session = requests.Session(impersonate="chrome142")

res = session.get(url)
if res.status_code != 200:
    print(f"Error: {res.status_code}")
    exit()

html = res.text
iframe_url = extract(r'<iframe[^>]*\bid=["\']view_iframe["\'][^>]*\bsrc=["\']([^"\']+)', html)

html = session.get(iframe_url, headers={"Referer": base_url}).text
m3u8_url = extract(r'data-m3u8=["\']([^"\']+)', html)

m3u8_headers = {
    "Origin": "https://player-v2.bcbc.red",
    "Referer": "https://player-v2.bcbc.red/",
}
res = session.get(m3u8_url, headers=m3u8_headers)
m3u8_data = res.text

enc_info = None
for line in m3u8_data.strip().split('\n'):
    line = line.strip()
    if line.startswith('#EXT-X-KEY:'):
        method_m = re.search(r'METHOD=([^,\s]+)', line)
        uri_m = re.search(r'URI="([^"]+)"', line)
        iv_m = re.search(r'IV=(0x[0-9a-fA-F]+)', line, re.I)
        if method_m and method_m.group(1) == 'AES-128' and uri_m:
            enc_info = {
                'uri': uri_m.group(1),
                'iv': iv_m.group(1) if iv_m else None,
            }
        break

aes_key, aes_iv = None, None
if enc_info:
    key_res = session.get(enc_info['uri'], headers=m3u8_headers)
    aes_key = decrypt_key(key_res.text)
    raw_iv = enc_info['iv']
    aes_iv = bytes.fromhex(raw_iv.removeprefix('0x').removeprefix('0X')) if raw_iv else b'\x00' * 16

downloader = M3U8Downloader(headers=m3u8_headers)
downloader.session = session

downloader.download_m3u8_to_mp4(
    m3u8_data=m3u8_data,
    output_dir="output",
    output_name=f"{vid}_{eid}",
    max_workers=8,
    aes_key=aes_key,
    aes_iv=aes_iv,
    delay=delay,
)