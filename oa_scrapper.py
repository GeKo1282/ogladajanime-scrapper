import requests
import json
import threading
import sys
import random
import asyncio
import os
from datetime import datetime
from urllib.parse import unquote
from bs4 import BeautifulSoup
from typing import List, Union, Tuple, Optional

OA_PLAYER_FETCH_BASE_URL = "https://ogladajanime.pl:8443/Player/"

def check_for_arguments(arguments: Union[str, List[str]]) -> bool:
    if type(arguments) != list:
        arguments = [arguments]
    
    for argument in arguments:
        if argument in sys.argv:
            return True
        
def get_argument_value(arguments: Union[str, List[str]]) -> str:
    for argument in arguments:
        try:
            return sys.argv[sys.argv.index(argument) + 1]
        except:
            pass

    return None

def get_nominus_argument(index: int, args_with_values=None):
    if args_with_values is None:
        args_with_values = []

    for arg in sys.argv[1:]:
        if not arg.startswith('-') and (sys.argv.index(arg) == 0 or sys.argv[sys.argv.index(arg) - 1] not in args_with_values):
            if index == 0:
                return arg
            index -= 1

    return None


def is_correct_url(url: str) -> bool:
    return url.startswith("https://ogladajanime.pl/")

def convert_size(bytes: int, precision: int = 2, no_prefix: bool = False) -> str:
    suffixes = ['B', 'KB', 'MB', 'GB', 'TB']
    suffix_index = 0
    while bytes > 1024 and suffix_index < 4:
        bytes /= 1024
        suffix_index += 1
    return f"{round(bytes, precision):.2f}" + (f"{suffixes[suffix_index]}" if not no_prefix else "")

class Proxies:
    def __init__(self, proxyfile: str):
        self.proxyfile = proxyfile
        self.proxies = []
        self.working_proxies = []

    def load_proxies(self):
        with open(self.proxyfile, "r") as f:
            self.proxies = f.read().split("\n")
    
    def test_proxies(self, threads: int = 500):
        t = []
        for _ in range(threads):
            t.append(threading.Thread(target=self.test_proxy))

        for thread in t:
            thread.start()

        for thread in t:
            thread.join()

    def test_proxy(self):
        url = "https://www.example.com"
        while len(self.proxies) > 0:            
            proxy = self.proxies.pop(0)
            proxy = {"http": f"http://{proxy}"}
            try:
                r = requests.get(url, proxies=proxy, timeout=10)
                if r.status_code == 200:
                    self.working_proxies.append(proxy)
            except:
                pass

class SeriesFetcher:
    def __init__(self, url: str, episodes: List[Union[Tuple[int, int], int]] = None, working_proxy_list: List[dict] = None) -> None:
        self.url: str = url
        self.episodes: List[str] = episodes
        self.headers = {
            'User-Agent': 'Mozilla/5.0 (Windows NT 10.0; Win64; x64) AppleWebKit/537.36 (KHTML, like Gecko) Chrome/92.0.4515.131 Safari/537.36',
            'Origin': 'https://ogladajanime.pl',
        }
        self.proxies: List[str] = working_proxy_list

    @staticmethod
    async def scrap_cda_video(url, proxies: Optional[List[dict]] = None, allow_redirects=True):
        headers = {
            'User-Agent': 'Mozilla/5.0 (Windows NT 10.0; Win64; x64) AppleWebKit/537.36 (KHTML, like Gecko) Chrome/92.0.4515.131 Safari/537.36',
        }

        def check_if_cda(url):
            return 'cda.pl' in url

        def compat_ord(c):
            if type(c) == int:
                return c
            else:
                return ord(c)

        def decrypt_file(a):
            for p in ('_XDDD', '_CDA', '_ADC', '_CXD', '_QWE', '_Q5', '_IKSDE'):
                a = a.replace(p, '')
            a = unquote(a)
            b = []
            for c in a:
                f = compat_ord(c)
                b.append(chr(33 + (f + 14) % 94) if 33 <= f and 126 >= f else chr(f))
            a = ''.join(b)
            a = a.replace('.cda.mp4', '')
            for p in ('.2cda.pl', '.3cda.pl'):
                a = a.replace(p, '.cda.pl')
            if '/upstream' in a:
                a = a.replace('/upstream', '.mp4/upstream')
                return 'https://' + a
            return 'https://' + a + '.mp4'

        def find_qualities(base_url, qualitites):
            quality_arr = list(qualitites.keys())
            url_dict = {}
            threads = []

            def find_quality(quality):
                async def inner():
                    slep = 1
                    while True:
                        try:
                            proxy = random.choice(proxies) if proxies else None
                            response = requests.get(base_url + f"?wersja={quality}", headers=headers, allow_redirects=allow_redirects, proxies=proxy, timeout=10)
                            if response.status_code in [200, 206]:
                                break

                            if response.status_code == 429:
                                print(f"Sir, we are being rate limited! Sleeping for {slep} seconds... Proxy:", proxy, end="\r")
                                await asyncio.sleep(slep)
                                slep += 1
                            else:
                                print(f"Error: {response.status_code}! Sleeping for a second... Proxy:", proxy, end="\r")
                                await asyncio.sleep(1)
                        except:
                            pass

                    soup = BeautifulSoup(response.content, "html.parser")
                    file = decrypt_file(json.loads(soup.find('div', attrs={'player_data': True}).get_attribute_list('player_data')[0])['video']['file'])
                    url_dict[quality] = file
                
                asyncio.run(inner())

            for quality in quality_arr:
                threads.append(threading.Thread(target=find_quality, args=(quality,)))

            for thread in threads:
                thread.start()

            for thread in threads:
                thread.join()

            return url_dict
        
        if not check_if_cda(url):
            raise InvalidUrl(f"Error: {url} is not a valid cda.pl url!")        

        slep = 1
        while True:
            try:
                proxy = random.choice(proxies)
                response = requests.get(url, headers=headers, allow_redirects=True, proxies=proxy, timeout=10)
                if response.status_code in [200, 206]:
                    break

                if response.status_code == 429:
                    print(f"Sir, we are being rate limited! Sleeping for {slep} second... Proxy:", proxy, end="\r")
                    await asyncio.sleep(slep)
                    slep += 1
                else:
                    print(f"Error: {response.status_code}! Sleeping for a second... Proxy:", proxy, end="\r")
                    await asyncio.sleep(1)

            except:
                continue

        soup = BeautifulSoup(response.content, "html.parser")
        try:
            qualitites = json.loads(soup.find('div', attrs={'player_data': True}).get_attribute_list('player_data')[0])['video']['qualities']
        except:
            raise NoQualitiesFound(f"Error: Couldn't find video qualities for following url: {url}!")

        quality_urls = find_qualities(url, qualitites)

        return quality_urls

    def fetch_episodes(self):
        page = requests.get(self.url)
        soup = BeautifulSoup(page.content, "html.parser")

        episodes_list = soup.find(id="ep_list")
        episodes = {index: (episode.attrs.get("title"), episode.attrs.get("ep_id")) for index, episode in enumerate(episodes_list.findChildren(recursive=False))}
        if self.episodes is None:
            return episodes
        
        no_episodes = len(episodes)
        episodes_to_keep = [False] * no_episodes
        
        for entry in self.episodes:
            if type(entry) == int:
                episodes_to_keep[entry] = True
            elif type(entry) == tuple:
                for i in range(entry[0] if entry[0] > -1 else no_episodes + entry[0], entry[1] + 1 if entry[1] > -1 else no_episodes + entry[1] + 1):
                    episodes_to_keep[i] = True
        
        episodes = {index: episode for index, episode in episodes.items() if episodes_to_keep[index]}
        return episodes

    async def fetch_episode_qualities(self, episode_id: str):
        episode_json = json.loads(requests.get(OA_PLAYER_FETCH_BASE_URL + episode_id, headers=self.headers).content.decode())        
        try:
            main_url = episode_json[0]["mainUrl"]
        except:
            return None

        if self.proxies:
            tp = [self.proxies.pop(0), self.proxies.pop(0), self.proxies.pop(0), self.proxies.pop(0)]
            qualities = await SeriesFetcher.scrap_cda_video(main_url, tp)
            self.proxies.extend(tp)
        else:
            qualities = await SeriesFetcher.scrap_cda_video(main_url)

        return qualities

    def get_episodes_with_qualitites(self):
        episodes = {}
        threads = []
        def inner(index, name, url):
            async def async_inner():
                qualitites = await self.fetch_episode_qualities(url)
                if not qualitites:
                    print(f"Couldn't find players for episode \"{name}\" ({index})")
                    return
                episodes[index] = (name, qualitites)

            loop = asyncio.new_event_loop()
            asyncio.set_event_loop(loop)
            loop.run_until_complete(async_inner())

        for index, episode in self.fetch_episodes().items():
            threads.append(threading.Thread(target=inner, args=(index, episode[0], episode[1])))

        for thread in threads:
            thread.start()

        for thread in threads:
            thread.join()

        return episodes

class SeriesDownloader:
    def __init__(self, episodes: dict, title_scheme: str, quality: str, output_dir: str, proxies: Proxies):
        self.episodes = episodes
        self.title_scheme = title_scheme
        self.quality = quality
        self.output_dir = output_dir
        self.queue = []
        self.proxies = proxies
        self.custom_text = ""
        self.debug = {
            "inmemory_chunks": 0,
            "last_saved_chunk": 0,
            "chunks_to_save": 0
        }

    def downloader(self):
        async def inner():
            for index in range(len(self.queue)):
                self.get_video_size(index)
                threads = []
                _, _, episode_url, output_file, download_info, _ = self.queue[index]
                while download_info[1] == 0:
                    await asyncio.sleep(.2)
                    _, _, episode_url, output_file, download_info, _ = self.queue[index]

                if os.path.exists(output_file):
                    os.remove(output_file)

                chunk_size = 1024 * 1024
                split_in_chunks = [i for i in enumerate(range(0, download_info[1], chunk_size))]
                retry_chunks = []
                chunks_to_save = len(split_in_chunks)
                file_chunks = {}

                def chunk_downloader():
                    while len(split_in_chunks) > 0 or len(retry_chunks) > 0:
                        if len(retry_chunks) > 0:
                            chunk_index, chunk = retry_chunks.pop(0)
                        else:
                            chunk_index, chunk = split_in_chunks.pop(0)

                        try:
                            r = requests.get(episode_url, headers={"Range": f"bytes={chunk}-{chunk+chunk_size-1}"}, proxies=random.choice(self.proxies.working_proxies), timeout=10)
                            while r.status_code not in [200, 206]:
                                r = requests.get(episode_url, headers={"Range": f"bytes={chunk}-{chunk+chunk_size-1}"}, proxies=random.choice(self.proxies.working_proxies), timeout=10)
                            file_chunks[chunk_index] = r.content
                            self.queue[index][4][0] += len(r.content)
                        except:
                            retry_chunks.append((chunk_index, chunk))

                def saver(chunks_to_save):
                    async def inner(chunks_to_save):
                        last_saved_chunk = -1
                        while chunks_to_save > 0 or len(file_chunks) > 0:
                            for chunk_index in sorted(file_chunks.keys()):
                                if chunk_index == last_saved_chunk + 1:
                                    with open(output_file, "ab") as f:
                                        f.write(file_chunks[chunk_index])
                                    del file_chunks[chunk_index]
                                    last_saved_chunk += 1
                                    self.debug['last_saved_chunk'] = last_saved_chunk
                                    chunks_to_save -= 1
                                    self.debug['chunks_to_save'] = chunks_to_save
                                else:
                                    self.debug['inmemory_chunks'] = len(file_chunks)
                                    break
                            
                            await asyncio.sleep(.2)

                    asyncio.run(inner(chunks_to_save))

                for _ in range(20):
                    threads.append(threading.Thread(target=chunk_downloader))

                threads.append(threading.Thread(target=saver, args=(chunks_to_save,)))

                for thread in threads:
                    thread.start()

                for thread in threads:
                    thread.join()
        
        asyncio.run(inner())


    def get_video_size(self, index: int):
        def get_file_size(episode_url) -> int:
            r = requests.head(episode_url, proxies=random.choice(self.proxies.working_proxies))
            return int(r.headers["Content-Length"])

        episode = self.queue[index]
        _, _, episode_url, _, _, _ = episode
        
        episode_size = get_file_size(episode_url)
        self.queue[index][4][1] = episode_size
        

    def update_console(self, run):
        async def inner():
            while run():
                def const_title_length(title: str, length: int):
                    if len(title) > length:
                        return title[:length-3] + "..."
                    else:
                        return title + " " * (length - len(title))

                def make_progressbar(value, max_value, length=30):
                    progress = round(value / (max_value or 1) * (length - 2))
                    return f"[{'=' * progress}{' ' * ((length - 2) - progress)}]"

                output = self.custom_text + "\n"
                total_size = 0
                no_episodes = 0
                for index, episode in enumerate(self.queue):
                    ep_index, title, _, _output_file, download_info, quality = episode
                    no_episodes += 1
                    total_size += download_info[1]
                    output += f"{index + 1}.\t[{('0' + str(ep_index))[-2:]}] {const_title_length(title, 35)} {make_progressbar(download_info[0], download_info[1])} {(download_info[0] / (download_info[1] or 1) * 100):.2f}% {convert_size(download_info[0])}/{convert_size(download_info[1])} [{quality}]\n"
                
                output += f"Total size of those {no_episodes} episodes is " + convert_size(total_size) + "\n"
                output += "In memory chunks: " + str(self.debug['inmemory_chunks']) + "\n"
                output += "Last saved chunk: " + str(self.debug['last_saved_chunk']) + "\n"
                output += "Chunks to save: " + str(self.debug['chunks_to_save']) + "\n"

                os.system("cls")
                print(output)
                await asyncio.sleep(1)

        asyncio.run(inner())

    def download(self, custon_text=""):
        self.custom_text = custon_text

        def get_top_quality(episode_urls):
            return f"{max([int(quality[:-1]) for quality in list(episode_urls.keys())])}p"
        
        for index, episode in self.episodes.items():
            title, urls = episode
            episode_quality = self.quality if self.quality != "best" else get_top_quality(urls)
            episode_url = urls.get(episode_quality, None)

            if episode_url is None:
                print(f"Error: Couldn't find quality {episode_quality} for episode {index}!")
                print(f"Available qualities: {', '.join(list(urls.keys()))}")
                quality = input("Input quality: ")
                while quality not in urls:
                    quality = input("Input quality: ")
                episode_url = urls[quality]

            full_output = os.path.join(self.output_dir, self.title_scheme
                .replace("%dt", datetime.now().strftime("%Y-%m-%d %H-%M-%S"))
                .replace("%ne", f"0{str(index)}"[-2:])
                .replace("%e", str(index))
                .replace("%q", episode_quality)
                .replace("%t", title)
            )

            jindex = 1
            if os.path.exists(full_output):
                rename = ""
                if check_for_arguments(["--rename-all", "-ra"]):
                    rename = "r"
                
                if check_for_arguments(["--overwrite-all", "-oa"]):
                    rename = "o"

                if check_for_arguments(["--skip-all", "-sa"]):
                    rename = "s"
                
                if rename == "":
                    rename = input(f"File {full_output} already exists, input r to rename, s to skip, o to overwrite: ")

                if rename == "s":
                    continue

                if rename == "r":
                    full_output = full_output[:-4] + "(1).mp4"
                    while os.path.exists(full_output):
                        jindex += 1
                        full_output = full_output[:-len(f"({jindex-1}).mp4")] + f"({jindex}).mp4"
            
            self.queue.append([index, title, episode_url, full_output, [0, 0], episode_quality])

        run = True
        threading.Thread(target=self.update_console, args=(lambda: run,)).start()

        for index in range(len(self.queue)):
            threading.Thread(target=self.get_video_size, args=(index,)).start()

        self.downloader()

        run = False
            

class InvalidUrl(Exception):
    pass

class NoQualitiesFound(Exception):
    pass

if __name__ == "__main__":
    os.system("cls")

    if check_for_arguments(["--help", "-h"]):
        print("--help, -h: Shows this message")
        print("--best-quality, -bq: Best quality")
        print("--quality, -q: Quality selection (1080p, 720p, etc...), for example \"-q 1080p\"")
        print("--title, -t: Template for file name, for example \"-t \"%t.mp4\"\"")
        print("Variables for template:")
        print("\t%dt: Time at moment of saving")
        print("\t%n: Series name")
        print("\t%s: Season number (Not available yet!)")
        print("\t%ns: Normalized season number (Not available yet!)")
        print("\t%e: Episode number")
        print("\t%ne: Normalised episode number, for example \"01\" instead of \"1\"")
        print("\t%q: Quality")
        print("\t%t: Title of episode")
        print("--output, -o: Output directory, for example \"-o \"C:\\Users\\User\\Downloads\"\"")
        print("--proxies, -p: Proxy list file name, for example \"-p proxies.txt\". Proxy file must contain one proxy per line!")
        print("--rename-all, -ra: Rename all files that already exist")
        print("--overwrite-all, -oa: Overwrite all files that already exist")
        print("--skip-all, -sa: Skip all files that already exist")
        print("--ignore-directory-exists: Ignore if output directory already exists")
        print("[url_or_file]: Url of series to download or path to file containing multiple urls ([url, output, title, quality or \"best\"])")
        print("Usage: py main.py [url_or_file] -bq -t \"%t.mp4\" -o \"output\" -p proxies.txt")
        exit(0)
    
    best_quality = check_for_arguments(["--best-quality", "-bq"])
    quality = get_argument_value(["--quality", "-q"])
    title_scheme = get_argument_value(["--title", "-t"])
    output = get_argument_value(["--output", "-o"])
    proxies = get_argument_value(["--proxies", "-p"])
    url_or_file = get_nominus_argument(0, ["--title", "-t", "--quality", "-q", "--output", "-o", "--proxies", "-p"])

    if url_or_file and is_correct_url(url_or_file) and not any([not (best_quality or quality), not title_scheme, not output, not proxies]):
        url_list = [[url_or_file, output, title_scheme, quality]]
    elif url_or_file and os.path.exists(url_or_file) and proxies:
        url_list = json.load(open(url_or_file, "r"))
    else:
        print("Error: Missing arguments!")
        exit(1)

    for _, output, _, _ in url_list:
        try:
            os.makedirs(output)
        except OSError:
            if len(os.listdir(output)) > 0 and not check_for_arguments(["--ignore-directory-exists", "-ide"]):
                print(f"Error: Output directory \"{output}\" exists and is not empty!")
                continue_anyway = input("Continue anyway? (y/n): ")
                if continue_anyway.lower() != "y":
                    exit(1)

    proxies = Proxies(proxies)
    proxies.load_proxies()
    proxies.test_proxies()

    print(f"Found {len(proxies.working_proxies)} working proxies.")

    for index in range(len(url_list)):
        url, output, title_scheme, quality = url_list[index]
        url_list[index].append(SeriesFetcher(url, [(1, -1)], working_proxy_list=proxies.working_proxies))

    for index, url in enumerate(url_list):
        episode_url, output, title_scheme, quality, sf = url
        episodes = sf.get_episodes_with_qualitites()
        episodes = {k:episodes[k] for k in sorted(episodes.keys())}

        downloader = SeriesDownloader(episodes, title_scheme, quality or "best", output, proxies=proxies)
        downloader.download(f"Downloading series {index + 1} out of {len(url_list)}...")

    print("Done!")