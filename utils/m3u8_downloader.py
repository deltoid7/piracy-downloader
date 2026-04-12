import requests
from urllib.parse import urljoin
import re
import os
import tempfile
import subprocess
import io
from concurrent.futures import ThreadPoolExecutor, as_completed
from tqdm import tqdm
import time
import random
from Crypto.Cipher import AES


def _pkcs7_unpad(data: bytes) -> bytes:
    pad = data[-1]
    return data[:-pad] if 1 <= pad <= 16 else data


class M3U8Downloader:
    def __init__(self, headers=None):
        self.headers = headers or {}
        self.session = requests.Session()
        if headers:
            self.session.headers.update(headers)

    def parse_m3u8(self, content):
        segments, enc_info = [], None
        lines = content.strip().split('\n')
        for i, line in enumerate(lines):
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
            elif line.startswith('#EXTINF:'):
                m = re.search(r'#EXTINF:([\d.]+),', line)
                if m and i + 1 < len(lines) and not lines[i + 1].strip().startswith('#'):
                    segments.append({'duration': float(m.group(1)), 'url': lines[i + 1].strip()})
        return segments, enc_info

    def download_segment(self, segment_info, delay=0, aes_key=None, aes_iv=None):
        index, segment = segment_info
        try:
            if delay > 0:
                time.sleep(random.uniform(0, delay))
            res = self.session.get(segment['url'], headers=self.headers.copy(), timeout=(10, 30))
            res.raise_for_status()
            data = res.content
            if aes_key is not None and aes_iv is not None:
                data = _pkcs7_unpad(AES.new(aes_key, AES.MODE_CBC, aes_iv).decrypt(data))
            return index, data
        except Exception as e:
            tqdm.write(f"[오류] 세그먼트 {index+1}: {e}")
            return index, None

    def download_m3u8_to_mp4(self, m3u8_data, output_dir, output_name,
                              max_workers=5, delay=3, aes_key=None, aes_iv=None):
        segments, _ = self.parse_m3u8(m3u8_data)

        downloaded = {}
        with ThreadPoolExecutor(max_workers=max_workers) as executor:
            futures = [
                executor.submit(self.download_segment, (i, seg), delay, aes_key, aes_iv)
                for i, seg in enumerate(segments)
            ]
            for future in tqdm(as_completed(futures), total=len(segments), leave=False):
                index, content = future.result()
                if content is not None:
                    downloaded[index] = content

        ts_data = io.BytesIO()
        omission, olist = 0, []
        for i in tqdm(range(len(segments)), desc="세그먼트 합치는 중", ncols=80, leave=False):
            if i in downloaded:
                ts_data.write(downloaded[i])
            else:
                omission += 1
                olist.append(i)

        ts_data.seek(0)
        print('\r' + ' ' * 100 + '\r', end='')
        print("mp4로 변환 중...", end='', flush=True)

        os.makedirs(output_dir, exist_ok=True)
        output_filename = os.path.join(output_dir, f"{output_name}.mp4")

        try:
            with tempfile.NamedTemporaryFile(suffix='.ts', delete=False) as f:
                f.write(ts_data.getvalue())
                temp_path = f.name

            subprocess.run(
                ['ffmpeg', '-loglevel', 'quiet', '-i', temp_path, '-c', 'copy', '-y', output_filename],
                check=True
            )
            os.unlink(temp_path)
            print('\r' + ' ' * 100 + '\r', end='')
            print(f"{output_name}이(가) {os.path.abspath(output_dir)}에 저장되었습니다.")
            print(f"누락된 세그먼트: {omission}개" + (f" ({', '.join(str(i) for i in olist)})" if olist else ""))
            return output_filename

        except (subprocess.CalledProcessError, FileNotFoundError) as e:
            if isinstance(e, FileNotFoundError):
                print("ffmpeg가 설치되어 있지 않습니다.")
            else:
                print(f"ffmpeg 변환 오류: {e}")
            if 'temp_path' in locals():
                try:
                    os.unlink(temp_path)
                except Exception:
                    pass
            return None
