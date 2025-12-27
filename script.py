import os
import sys
import json
import shutil
import zipfile
import tarfile
import gzip
from pathlib import Path
import requests

# Configuration URLs
FFMPEG_URL = "https://github.com/eugeneware/ffmpeg-static/releases/download/b6.1.1"
BENTO4_URL = "https://www.bok.net/Bento4/binaries"
MEGATOOLS_URL = "https://megatools.megous.com/builds/builds"

BENTO4_VERSION = "1-6-0-641"
MEGATOOLS_VERSION = "1.11.3.20250401"


class BinaryDownloader:
    def __init__(self, base_path: str = "./binaries"):
        self.base_path = Path(base_path)
        self.paths_json = {}
        self.session = requests.Session()
        self.session.headers.update({
            'User-Agent': 'Mozilla/5.0 (Windows NT 10.0; Win64; x64) AppleWebKit/537.36'
        })
        
        self.platforms = {
            'windows': ['x64'],
            'darwin': ['x64', 'arm64'],
            'linux': ['x64', 'arm64']
        }
        
        self._create_directories()

    def _create_directories(self):
        for platform_name, arches in self.platforms.items():
            for arch in arches:
                (self.base_path / platform_name / arch / "ffmpeg").mkdir(parents=True, exist_ok=True)
                (self.base_path / platform_name / arch / "bento4").mkdir(parents=True, exist_ok=True)
                (self.base_path / platform_name / arch / "megatools").mkdir(parents=True, exist_ok=True)

    def _download(self, url: str, dest: Path) -> bool:
        try:
            response = self.session.get(url, stream=True, timeout=60)
            response.raise_for_status()
            
            with open(dest, 'wb') as f:
                for chunk in response.iter_content(chunk_size=8192):
                    f.write(chunk)
            
            return True
        except Exception as e:
            print(f"  X {url.split('/')[-1]}: {str(e)[:50]}")
            return False

    def _add_path(self, platform: str, arch: str, tool: str, binary: str):
        key = f"{platform}_{arch}_{tool}"
        if key not in self.paths_json:
            self.paths_json[key] = []
        
        rel_path = f"{platform}/{arch}/{tool}/{binary}"
        if rel_path not in self.paths_json[key]:
            self.paths_json[key].append(rel_path)

    def download_ffmpeg(self):
        print("\n=== FFmpeg ===")
        
        # FFmpeg mapping
        ffmpeg_map = {
            'windows': {'x64': 'win32-x64'},
            'darwin': {'x64': 'darwin-x64', 'arm64': 'darwin-arm64'},
            'linux': {'x64': 'linux-x64', 'arm64': 'linux-arm64'}
        }
        
        for platform_name, arches in self.platforms.items():
            for arch in arches:
                print(f"{platform_name}-{arch}: ", end="", flush=True)
                
                platform_str = ffmpeg_map[platform_name].get(arch)
                if not platform_str:
                    print("skip")
                    continue
                
                target_dir = self.base_path / platform_name / arch / "ffmpeg"
                success = 0
                
                for executable in ['ffmpeg', 'ffprobe']:
                    filename = f"{executable}-{platform_str}"
                    url = f"{FFMPEG_URL}/{filename}.gz"
                    gz_path = target_dir / f"{filename}.gz"
                    
                    ext = ".exe" if platform_name == "windows" else ""
                    final_path = target_dir / f"{executable}{ext}"
                    
                    if self._download(url, gz_path):
                        try:
                            with gzip.open(gz_path, 'rb') as f_in:
                                with open(final_path, 'wb') as f_out:
                                    shutil.copyfileobj(f_in, f_out)
                            
                            gz_path.unlink()
                            
                            if platform_name != "windows":
                                os.chmod(final_path, 0o755)
                            
                            self._add_path(platform_name, arch, "ffmpeg", f"{executable}{ext}")
                            success += 1
                        except Exception as e:
                            print(f"  X extract {executable}")
                
                print(f"{success}/2")

    def download_bento4(self):
        print("\n=== Bento4 ===")
        
        platform_config = {
            'windows': {'x64': 'x86_64-microsoft-win32'},
            'darwin': {'x64': 'universal-apple-macosx', 'arm64': 'universal-apple-macosx'},
            'linux': {'x64': 'x86_64-unknown-linux', 'arm64': 'x86_64-unknown-linux'}
        }
        
        executables = {
            'windows': ['mp4decrypt.exe', 'mp4encrypt.exe', 'mp4info.exe', 'mp4dump.exe'],
            'darwin': ['mp4decrypt', 'mp4encrypt', 'mp4info', 'mp4dump'],
            'linux': ['mp4decrypt', 'mp4encrypt', 'mp4info', 'mp4dump']
        }
        
        for platform_name, arches in self.platforms.items():
            for arch in arches:
                print(f"{platform_name}-{arch}: ", end="", flush=True)
                
                platform_str = platform_config[platform_name].get(arch)
                if not platform_str:
                    print("skip")
                    continue
                
                url = f"{BENTO4_URL}/Bento4-SDK-{BENTO4_VERSION}.{platform_str}.zip"
                
                target_dir = self.base_path / platform_name / arch / "bento4"
                zip_path = target_dir / "bento4.zip"
                
                if not self._download(url, zip_path):
                    print("0/4")
                    continue
                
                success = 0
                try:
                    with zipfile.ZipFile(zip_path, 'r') as zip_ref:
                        for zip_info in zip_ref.filelist:
                            for executable in executables[platform_name]:
                                if zip_info.filename.endswith(executable):
                                    temp_path = target_dir / "temp"
                                    temp_path.mkdir(exist_ok=True)
                                    
                                    zip_ref.extract(zip_info, temp_path)
                                    src = temp_path / zip_info.filename
                                    dst = target_dir / executable
                                    
                                    shutil.move(str(src), str(dst))
                                    
                                    if platform_name != "windows":
                                        os.chmod(dst, 0o755)
                                    
                                    self._add_path(platform_name, arch, "bento4", executable)
                                    success += 1
                                    
                                    if temp_path.exists():
                                        shutil.rmtree(temp_path)
                    
                    zip_path.unlink()
                except Exception as e:
                    print(f"  X extract: {str(e)[:40]}")
                
                print(f"{success}/4")

    def download_megatools(self):
        print("\n=== Megatools ===")
        
        config = {
            'windows': {'x64': ('win64', '.zip', 'megatools.exe')},
            'darwin': {'x64': ('linux-x86_64', '.tar.gz', 'megatools'), 'arm64': ('linux-aarch64', '.tar.gz', 'megatools')},
            'linux': {'x64': ('linux-x86_64', '.tar.gz', 'megatools'), 'arm64': ('linux-aarch64', '.tar.gz', 'megatools')}
        }
        
        for platform_name, arches in self.platforms.items():
            for arch in arches:
                print(f"{platform_name}-{arch}: ", end="", flush=True)
                
                if arch not in config[platform_name]:
                    print("skip")
                    continue
                
                platform_str, extension, executable = config[platform_name][arch]
                url = f"{MEGATOOLS_URL}/megatools-{MEGATOOLS_VERSION}-{platform_str}{extension}"
                
                target_dir = self.base_path / platform_name / arch / "megatools"
                archive_path = target_dir / f"megatools{extension}"
                
                if not self._download(url, archive_path):
                    print("0/1")
                    continue
                
                success = 0
                try:
                    temp_dir = target_dir / "temp"
                    temp_dir.mkdir(exist_ok=True)
                    
                    if extension == '.zip':
                        with zipfile.ZipFile(archive_path, 'r') as archive:
                            archive.extractall(temp_dir)
                    else:
                        with tarfile.open(archive_path, 'r:gz') as archive:
                            archive.extractall(temp_dir)
                    
                    for root, dirs, files in os.walk(temp_dir):
                        if executable in files:
                            src = Path(root) / executable
                            dst = target_dir / executable
                            shutil.move(str(src), str(dst))
                            
                            if platform_name != "windows":
                                os.chmod(dst, 0o755)
                            
                            self._add_path(platform_name, arch, "megatools", executable)
                            success = 1
                            break
                    
                    shutil.rmtree(temp_dir)
                    archive_path.unlink()
                except Exception as e:
                    print(f"  X extract: {str(e)[:40]}")
                
                print(f"{success}/1")

    def save_paths_json(self):
        json_path = Path("./binary_paths.json")
        with open(json_path, 'w') as f:
            json.dump(self.paths_json, f, indent=2)
        print(f"\nPaths: {json_path.absolute()}")

    def run(self):
        print("Binary Downloader")
        print(f"Base: {self.base_path.absolute()}")
        
        self.download_ffmpeg()
        self.download_bento4()
        self.download_megatools()
        self.save_paths_json()
        
        print("\nDone!")


if __name__ == "__main__":
    downloader = BinaryDownloader()
    downloader.run()