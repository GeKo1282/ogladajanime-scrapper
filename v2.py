import os, sys, json, random, threading, asyncio, pathlib
import requests
from bs4 import BeautifulSoup
from datetime import datetime, timedelta
from urllib.parse import unquote
from typing import List, Union, Tuple

class Color:
    BLACK = 0
    RED = 1
    GREEN = 2
    YELLOW = 3
    BLUE = 4
    MAGENTA = 5
    CYAN = 6
    WHITE = 7
    RESET = "\033[0m"

    FORE_GEN = lambda fore: "\033[" + "3" + str(fore) + "m"
    BACK_GEN = lambda back: "\033[" + "4" + str(back) + "m"
    FORE_RGB = lambda r, g, b: "\033[38;2;" + str(r) + ";" + str(g) + ";" + str(b) + "m"
    DECORATION = lambda dec: "\033[" + str(dec) + "m"


class Fore:
    BLACK = Color.FORE_GEN(Color.BLACK)
    RED = Color.FORE_GEN(Color.RED)
    GREEN = Color.FORE_GEN(Color.GREEN)
    YELLOW = Color.FORE_GEN(Color.YELLOW)
    BLUE = Color.FORE_GEN(Color.BLUE)
    MAGENTA = Color.FORE_GEN(Color.MAGENTA)
    CYAN = Color.FORE_GEN(Color.CYAN)
    WHITE = Color.FORE_RGB(170, 170, 170)
    GRAY = Color.FORE_RGB(70, 70, 70)
    LIGHT_GRAY = Color.FORE_RGB(120, 120, 120)

    ORANGE = Color.FORE_RGB(255, 120, 0)
    PINK = Color.FORE_RGB(219, 79, 123)
    MINT = Color.FORE_RGB(42, 189, 110)

    UNDERLINE = Color.DECORATION(4)


class Back:
    BLACK = Color.BACK_GEN(Color.BLACK)
    RED = Color.BACK_GEN(Color.RED)
    GREEN = Color.BACK_GEN(Color.GREEN)
    YELLOW = Color.BACK_GEN(Color.YELLOW)
    BLUE = Color.BACK_GEN(Color.BLUE)
    MAGENTA = Color.BACK_GEN(Color.MAGENTA)
    CYAN = Color.BACK_GEN(Color.CYAN)
    WHITE = Color.BACK_GEN(Color.WHITE)

arglist = {
    "value_arguments": {
        "proxies": [["--proxies", "-p"], "Specifies path to file containing one proxy per line to use."],
        "config": [["--config", "-c"], "Specifies path to config file."],
        "proxy_threads": [["--proxy-threads", "-pt"], "Specifies amount of threads to use when checking proxies."],
        "download_threads": [["--download-threads", "-dt"], "Specifies amount of threads to use when downloading files."],
        "timeout": [["--timeout", "-t"], "Specifies timeout for requests."],
    },
    "flag_arguments": {
        "help": [["--help", "-h"], "Shows this help message."],
        "skip_all_existing": [["--skip-all-existing", "-sae"], "Skips all existing files without warning."],
        "replace_all_existing": [["--replace-all-existing", "-rae"], "Replaces all existing files without warning."],
        "rename_all_existing": [["--rename-all-existing", "-rnae"], "Automatically renames all existing files without waring."],
        "ignore_directory_warning": [["--ignore-directory-warning", "-idw"], "Ignores warning about directory existing and not being empty."],
    }
}

timer = 0
SPEED_TIMER_ROUND = 10
last_downloaded_amount = 0
last_round_speed = 0
speed_already_calculated = False

def convert_size(bytes: int, precision: int = 2, no_suffix: bool = False) -> str:
    suffixes = ['B', 'KB', 'MB', 'GB', 'TB']
    suffix_index = 0
    while bytes > 1024 and suffix_index < 4:
        bytes /= 1024
        suffix_index += 1
    return f"{round(bytes, precision):.2f}" + (f"{suffixes[suffix_index]}" if not no_suffix else "")

class ConsoleLogger:
    def __init__(self):
        self.messages = {}
        self.loading_sign = ["|", "/", "-", "\\"]
        self.run = False
        self.stop_on_print = False

    def clear(self):
        self.messages = {}

    def stop(self, wait_for_print: bool = False):
        if not wait_for_print:
            self.run = False
        else:
            self.stop_on_print = True

    def set_message(self, weight: int, message: str, loading_sign: bool = False):
        self.messages[weight] = [message, self.loading_sign[0] if loading_sign else False]

    def remove_message(self, weight: int):
        if weight in self.messages:
            del self.messages[weight]
            return True
        return False

    def print(self):
        if len(self.messages) == 0:
            return
        
        for weight in sorted(self.messages.keys()):
            if callable(self.messages[weight][0]):
                print(self.messages[weight][0](), end="")
            else:
                print(self.messages[weight][0], end="")

            if self.messages[weight][1]:
                self.messages[weight][1] = self.loading_sign[(self.loading_sign.index(self.messages[weight][1]) + 1) % len(self.loading_sign)]
                print(f" {self.messages[weight][1]}", end="")
            print()

    def ask(self, question: str) -> str:
        rerun = False
        if self.run:
            self.stop()
            rerun = True
        
        os.system("cls")
        response = input(question)

        if rerun:
            self.start()
        
        return response

    def start(self, wait_for: int = 1) -> threading.Thread:
        self.run = True

        async def inner():
            while self.run:
                os.system("cls")
                self.print()
                if self.stop_on_print:
                    self.stop()
                    break
                await asyncio.sleep(wait_for)
    
        thread = threading.Thread(target=asyncio.run, args=(inner(),))
        thread.start()
        return thread

def extract_from_argv() -> List[Tuple[List[str], Union[str, bool]]]:
    def find_argument(argument: str):
        for arglist_entry in arglist["value_arguments"]:
            if argument in arglist["value_arguments"][arglist_entry][0]:
                return ["value", arglist_entry]
            
        for arglist_entry in arglist["flag_arguments"]:
            if argument in arglist["flag_arguments"][arglist_entry][0]:
                return ["flag", arglist_entry]

    arguments = []
    lone_arguments = []
    argv_copy = [*sys.argv[1:]]
    while len(argv_copy) > 0:
        argument = argv_copy[0]
        found = find_argument(argument)
        if not found:
            lone_arguments.append(argument)
            argv_copy.remove(argument)
            continue

        if found[0] == "value" and argv_copy.index(argument) + 1 < len(argv_copy):
            arguments.append([found[1], argv_copy[argv_copy.index(argument) + 1]])
            argv_copy.remove(argv_copy[argv_copy.index(argument) + 1])

        elif found[0] == "flag":
            arguments.append([found[1], True])
            

        argv_copy.remove(argument)
    
    return [arguments, lone_arguments]

def check_internet_connection() -> bool:
    try:
        requests.get("https://example.com")
        return True
    except:
        return False

def check_proxies(proxies: List[str], threads: int = 500) -> List[str]:
    thread_list = []
    working_proxies = []

    def tester() -> bool:
        while len(proxies) > 0:
            proxy = proxies.pop(0)
            try:
                requests.get("https://example.com", proxies={"http": proxy}, timeout=10)
                working_proxies.append(proxy)
            except:
                pass

    for _ in range(threads):
        thread_list.append(threading.Thread(target=tester))
        thread_list[-1].start()

    for thread in thread_list:
        thread.join()

    return working_proxies

def print_help(console_logger: ConsoleLogger):
    console_logger.set_message(0, "Help:\n")
    console_logger.set_message(1, "Value arguments (arguments that require value right after them):")

    valarg_str = ""
    for value_argument in arglist["value_arguments"]:
        valarg_str += f"{', '.join(arglist['value_arguments'][value_argument][0])} - {arglist['value_arguments'][value_argument][1]}\n"
    
    console_logger.set_message(2, valarg_str)

    console_logger.set_message(3, "Flag arguments (arguments that DO NOT require any value other than self):")

    flagarg_str = ""
    for flag_argument in arglist["flag_arguments"]:
        flagarg_str += f"{', '.join(arglist['flag_arguments'][flag_argument][0])} - {arglist['flag_arguments'][flag_argument][1]}\n"

    console_logger.set_message(4, flagarg_str)

    console_logger.set_message(5, "Config file should be json file containing list of as many entries like following as user wants under \"series\" key:\n"
    "\t[url, output_directory, title_scheme, quality]\n"
    "\turl - url of the series to scrap and download\n"
    "\toutput_directory - directory where to save downloaded files\n"
    "\ttitle_scheme - scheme of the title of the downloaded files, it may contain following varaibles:\n"
    "\t\t%t - title of the series\n"
    "\t\t%s - season number\n"
    "\t\t%ns - normalized season number, eg. \"01\" instead of \"1\"\n"
    "\t\t%e - episode number\n"
    "\t\t%ne - normalized episode number, eg. \"01\" instead of \"1\"\n"
    "\t\t%et - episode title\n"
    "\t\t%q - episode quality\n"
    "\t\t%dt - datetime in following format: %Y-%m-%d %H-%M-%S. This can be changed in config file.\n"
    "\tquality - quality of the downloaded files [1080p, 720p, etc.] or\"best\" for best available\n")

    console_logger.set_message(6, "Config file can contain following keys:\n"
    "\t\"series\" - list of series to download\n"
    "\t\"datetime_format\" - format of the datetime in title_scheme\n")

    console_logger.set_message(7, "Example config file:\n"
    "\t{\n"
    "\t\t\"datetime_format\": \"%Y-%m-%d %H-%M-%S\",\n"
    "\t\t\"series\": [\n"
    "\t\t\t[\"https://www.example.com/series/1\", \"C:\\\\Users\\\\User\\\\Downloads\", \"%t S%nsE%ne %et [%q].mp4\", \"1080p\"],\n"
    "\t\t\t[\"https://www.example.com/series/2\", \"C:\\\\Users\\\\User\\\\Downloads\", \"%t S%nsE%ne %et [%q].mp4\", \"1080p\"],\n"
    "\t\t\t[\"https://www.example.com/series/3\", \"C:\\\\Users\\\\User\\\\Downloads\", \"%t S%nsE%ne %et [%q].mp4\", \"1080p\"],\n"
    "\t\t]\n"
    "\t}\n")

    console_logger.stop(wait_for_print=True)

class Episode:
    def __init__(self, series: "Series", title: str, id: str, qualities: dict, real_index: int) -> None:
        self.series: Series = series
        self.title: str = title
        self.id: str = id
        self.qualities: dict[str, str] = qualities

        self.quality: str = None
        self.size: int = 0

        self.output: str = None
        self.ignore: bool = False
        self.real_index: int = real_index

        self.downloaded: int = 0

        self.chunks: list[(int, (int, int))] = []
        self.retry_chunks: list[(int, (int, int))] = []

        self.to_save: dict[int, bytes] = {}
        self.last_saved: int = -1

    def set_quality(self, quality: str) -> bool:
        if quality in self.qualities:
            self.quality = quality
            return True
        return False
    
    def get_size(self, proxy: str) -> threading.Thread:
        async def inner():
            if self.quality is None:
                return False
            
            slep = 1
            while self.size == 0:
                try:
                    response = requests.head(self.qualities[self.quality], proxies={"http": proxy})
                    if response.status_code == 429:
                        self.series.console_logger.set_message(0, f"Proxy {proxy} has been rate limited, sleeping for {slep} seconds!")
                        slep += 1
                        continue

                    if response.status_code != 200:
                        raise Exception("Response status code is not 200")
                    
                    new_size = int(response.headers["Content-Length"])
                    if self.downloaded == 0:
                        self.chunks = []
                        for index, chunk_start in enumerate(range(0, new_size, 1024*1024)):
                            self.chunks.append((index, (chunk_start, chunk_start + 1024*1024)))
                        self.series.total_size = self.series.total_size - self.size + new_size
                        self.size = new_size

                    return new_size
                except:
                    await asyncio.sleep(1)
            
            return True
        
        thread = threading.Thread(target=asyncio.run, args=(inner(),))
        thread.start()
        return thread
    
    def set_output(self, directory: str, title_scheme: str) -> None:
        title = title_scheme.replace("%t", self.series.series_title).replace("%e", str(self.real_index)).replace("%ne", f"{(self.real_index):02d}").replace("%et", self.title).replace("%q", self.quality).replace("%dt", datetime.now().strftime(self.series.datetime_format))        
        self.output = os.path.join(directory, title)
        
        if os.path.exists(self.output):
            action = ""
            if not self.series.ignore_all_existing and not self.series.rename_all_existing and not self.series.replace_all_existing:
                while action.lower() not in ["o", "r", "s", "overwrite", "rename", "skip"]:
                    action = self.series.console_logger.ask(f"File {self.output} already exists, overwrite, rename or skip? [o/r/s]: ")

            if self.series.ignore_all_existing or action in ["s", "skip"]:
                self.output = None
                self.ignore = True
            
            elif self.series.rename_all_existing or action in ["r", "rename"]:
                self.output = self.output.removesuffix(".mp4") + f"(1).mp4"
                index = 1
                while os.path.exists(self.output):
                    self.output = self.output.removesuffix(f"({index}).mp4") + f"({index+1}).mp4"
                    index += 1

            elif self.series.replace_all_existing or action in ["o", "overwrite"]:
                os.remove(self.output)

    
    def get_raw_url(self, quality: str = None):
        if not quality:
            quality = self.quality

        return self.qualities.get(quality, None)
        
class Series:    
    def __init__(self, console_logger: ConsoleLogger, datetime_format: str, url: str, output_directory: str, title_scheme: str, quality: str, series_index: int,
            proxies: List[str], download_threads: int = 30, ignore_all_existing: bool = False, rename_all_existing: bool = False, replace_all_existing: bool = False) -> bool:
        
        self.url: str = url
        self.output_directory: str = output_directory.replace("/", "\\")
        self.title_scheme: str = title_scheme
        self.quality: str = quality

        self.series_title: str = None
        self.no_episodes: int = 0

        self.episodes: dict[int, Episode] = {}
        
        self.total_size: int = 0
        self.total_nonignored_size: int = 0
        self.total_downloaded: int = 0
        self.timer_start_download: int = 0

        self.datetime_format: str = datetime_format
        self.series_index: int = series_index
        self.proxies: List[str] = proxies
        self.download_threads: int = download_threads
        
        self.console_logger: ConsoleLogger = console_logger

        self.ignore_all_existing: bool = ignore_all_existing
        self.rename_all_existing: bool = rename_all_existing
        self.replace_all_existing: bool = replace_all_existing

        self.full_stop: bool = False

    def verify_url(self) -> bool:
        if not self.url.startswith("https://www.ogladajanime.pl/") and not self.url.startswith("https://ogladajanime.pl/"):
            return False
        return True

    def make_output_directory(self) -> bool:
        if os.path.exists(self.output_directory):
            if os.listdir(self.output_directory) == []:
                return True
            return False
        
        os.makedirs(self.output_directory)
        return True
    
    def verify_input(self, *, ignore_directory_warning: bool = False):
        if not self.verify_url():
            return "url"
        
        try:
            if not self.make_output_directory() and not ignore_directory_warning:
                response = self.console_logger.ask(f"Directory \"{self.output_directory}\" already exists and is not empty. Do you want to continue? [y/n]: ")
                if response.lower() != "y":
                    return "directory"
        except Exception as e:
            self.full_stop = True
            self.console_logger.clear()
            self.console_logger.set_message(0, f"Directory \"{self.output_directory}\" could not be created! Please check if you have permissions to create directories in this location. Exception: {str(e)}")
            return "directory"
            
        return True
    
    def start_fetcher(self) -> threading.Thread:
        self.console_logger.set_message(9, "Series data is still being fetched...", True)
        def inner():
            headers = {
                'User-Agent': 'Mozilla/5.0 (Windows NT 10.0; Win64; x64) AppleWebKit/537.36 (KHTML, like Gecko) Chrome/92.0.4515.131 Safari/537.36',
                'Origin': 'https://ogladajanime.pl',
                'Cookie': 'user_id=64918; user_key=ZMWA6qGdsQ5k28zKr4KIP2wpLWpTrN',
            }

            OA_PLAYER_BASE_URL = "https://ogladajanime.pl:8443/Player/"

            page = requests.get(self.url, proxies={"http": random.choice(self.proxies)}, headers=headers)
            soup = BeautifulSoup(page.content, "html.parser")

            episodes_list = soup.find(id="ep_list")
            self.series_title = soup.find(id="anime_name_id").text
            episodes: dict[int, Episode] = {index: [(episode.attrs.get("title") or "No title!"), episode.attrs.get("ep_id"), int(episode.attrs.get("value"))] for index, episode in enumerate(episodes_list.findChildren(recursive=False))}

            self.no_episodes = len(episodes)

            size_getters = []
            for episode in episodes:
                if episodes[episode][2] == 0:
                    self.no_episodes -= 1
                    continue
                
                try:
                    json_data = json.loads(requests.get(OA_PLAYER_BASE_URL + episodes[episode][1], proxies={"http": random.choice(self.proxies)}, headers=headers).content.decode("utf-8"))
                    qualities = {f"{quality['res']}p": quality["src"] for quality in json_data}
                    self.episodes[episode] = Episode(self, episodes[episode][0], episodes[episode][1], qualities, episodes[episode][2])

                    quality = self.quality
                    if self.quality == "best":
                        quality = f"{max([int(key.replace('p', '')) for key in self.episodes[episode].qualities.keys()])}p"

                    while not self.episodes[episode].set_quality(quality):
                        quality = self.console_logger.ask(f"Episode {episode} of series {self.series_title} does not have quality {quality}. Please pick a new quality: [{','.join([episodes[episode].qualities.keys()])}]: ")

                    size_getters.append(self.episodes[episode].get_size(random.choice(self.proxies)))
                    self.episodes[episode].set_output(self.output_directory, self.title_scheme)
                    self.episodes[episode].set_quality(quality)
                except:
                    self.no_episodes -= 1

            for getter in size_getters:
                getter.join()

            self.console_logger.remove_message(9)             

        thread = threading.Thread(target=inner)
        thread.start()
        return thread


    def start_downloader(self) -> List[threading.Thread]:
        global timer
        self.timer_start_download = timer       
        async def downloader():
            def get_first_nonignored_episode() -> int:
                for episode in self.episodes:
                    if not self.episodes[episode].ignore:
                        return episode
                    
                return None
            
            while (len(self.episodes) != self.no_episodes or self.no_episodes == 0 or get_first_nonignored_episode() == None or self.episodes[get_first_nonignored_episode()].output == None) or \
             self.episodes[get_first_nonignored_episode()].size == 0:
                if self.full_stop or (self.no_episodes != 0 and len(self.episodes) == self.no_episodes and all([self.episodes[episode].ignore for episode in [*list(self.episodes.keys())]])):
                    self.full_stop = True
                    return
                
                await asyncio.sleep(0.1)

            while len(self.episodes) != self.no_episodes or self.no_episodes == 0 or not all([(self.episodes[episode].downloaded == self.episodes[episode].size and self.episodes[episode].size > 0) or self.episodes[episode].ignore for episode in [*list(self.episodes.keys())]]):
                if self.full_stop:
                    return
                
                await asyncio.sleep(0.1)
                for key in [*list(self.episodes.keys())]:
                    if self.episodes[key].size == 0 or self.episodes[key].ignore or self.episodes[key].output == None:
                        continue
                    
                    self.episodes[key].get_size(random.choice(self.proxies)).join()
                    while len(self.episodes[key].chunks) > 0 or len(self.episodes[key].retry_chunks) > 0:
                        if self.full_stop:
                            return
                        
                        if len(self.episodes[key].retry_chunks) > 0:
                            chunk_index, chunk_range = self.episodes[key].retry_chunks.pop(0)
                        else:
                            chunk_index, chunk_range = self.episodes[key].chunks.pop(0)

                        data = None
                        while data is None:
                            try:
                                data = requests.get(self.episodes[key].get_raw_url(), headers={"Range": f"bytes={chunk_range[0]}-{chunk_range[1] - 1}"}, proxies={"http": random.choice(self.proxies)}, timeout=10).content
                            except:
                                await asyncio.sleep(1)

                        self.episodes[key].downloaded += len(data)
                        self.total_downloaded += len(data)
                        self.episodes[key].to_save[chunk_index] = data

        async def saver():
            while len(self.episodes) != self.no_episodes or self.no_episodes == 0 or not all([(self.episodes[episode].downloaded == self.episodes[episode].size and self.episodes[episode].size > 0 and len(self.episodes[episode].to_save) == 0) or self.episodes[episode].ignore for episode in [*list(self.episodes.keys())]]) or len(self.episodes) == 0:
                if self.full_stop:
                    return
                
                for key in [*list(self.episodes.keys())]:
                    if self.episodes[key].ignore:
                        continue

                    for chunk_index in sorted(list(self.episodes[key].to_save.keys())):
                        if chunk_index == self.episodes[key].last_saved + 1:
                            self.episodes[key].last_saved += 1
                            try:
                                with open(self.episodes[key].output, "ab") as file:
                                    file.write(self.episodes[key].to_save.pop(chunk_index))
                            except IOError:
                                self.full_stop = True
                                self.console_logger.clear()
                                self.console_logger.set_message(0, f"Could not write to file \"{self.episodes[key].output}\", stopping! Check if file is not open in another program, if there is enough space on the drive and if you have write permissions to the file and try again!")
                                return
                        else:
                            break
                
                await asyncio.sleep(.2)

        def format_console() -> str:
            def const_title_length(title: str, length: int):
                if len(title) > length:
                    return title[:length-3] + "..."
                else:
                    return title + " " * (length - len(title))

            def make_progressbar(value, max_value, *, length=30, filled_color=Fore.GREEN, empty_color=Fore.GRAY, character="━"):
                progress_percentage = value / (max_value or 1)

                full_characters = character * int(progress_percentage * length)
                empty_characters = (character * length)[len(full_characters):]

                return f"{filled_color}{full_characters}{empty_color}{empty_characters}{Color.RESET}"
            
            def get_size_of_nonignored_episodes() -> int:                
                return sum([episode.size for episode in self.episodes.values() if not episode.ignore])
            
            def calculate_eta():
                global timer
                download_progress = self.total_downloaded / (self.total_size or 1)
                seconds_to_finish = int((1 - download_progress) / (download_progress or 1) * (timer - self.timer_start_download))
                return str(timedelta(seconds=seconds_to_finish))
            
            nonignored_size = get_size_of_nonignored_episodes()
            
            message = "Series stats:"
            message += f"\n\tSeries title is {Fore.LIGHT_GRAY}\"{Fore.MINT}{self.series_title}{Fore.LIGHT_GRAY}\"{Color.RESET}."
            message += f"\n\tSeries URL is {Fore.LIGHT_GRAY}\"{Fore.MINT}{self.url}{Color.RESET}{Fore.LIGHT_GRAY}\"{Color.RESET}.\n"
            message += f"\n\tDetected {Fore.PINK}{self.no_episodes}{Color.RESET} episodes."
            message += f"\n\tDesired quality is {Fore.LIGHT_GRAY}\"{Fore.BLUE}{self.quality}{Fore.LIGHT_GRAY}\"{Color.RESET}.\n"
            message += f"\n\tTotal size of all {Fore.PINK}{len(self.episodes)}{Color.RESET} episodes is: {Fore.GREEN}{convert_size(self.total_size)}{Color.RESET}."
            message += f"\n\tTotal size of {Fore.PINK}{sum([0 if episode.ignore else 1 for episode in self.episodes.values()])}{Color.RESET} downloaded episodes is: {Fore.GREEN}{convert_size(nonignored_size)}{Color.RESET}."
            message += f"\n\tDownloading to {Fore.LIGHT_GRAY}\"{Fore.ORANGE}" + str(pathlib.Path(self.output_directory).resolve()).replace("\\", Fore.RED + f" >> " + Fore.ORANGE) + f"{Fore.LIGHT_GRAY}\"{Color.RESET} directory.\n"
            message += f"\n\t{Fore.ORANGE}Download progress: {Color.RESET}[" + make_progressbar(self.total_downloaded, nonignored_size, length=100) + f"{Color.RESET}] {Fore.GREEN}{self.total_downloaded / (nonignored_size or 1) * 100:.2f}{Color.RESET}% {Fore.GREEN}{convert_size(self.total_downloaded)}{Color.RESET}/{Fore.BLUE}{convert_size(nonignored_size)}{Color.RESET}"
            message += f"\n\t{Fore.ORANGE}ETA: {Color.RESET} [{Fore.MAGENTA}{calculate_eta()}{Color.RESET}]\n"
            message += "\n\nFollowing episodes are being downloaded:"

            item_index = 1
            for episode in self.episodes.values():
                if episode.ignore:
                    continue
                message += f"\n{f'0{item_index}'[-2:]}. Ep. {f'0{episode.real_index}'[-2:]}: {Fore.MAGENTA}{const_title_length(episode.title, 44)} {Color.RESET}[{make_progressbar(episode.downloaded, episode.size, length=70, empty_color=(Fore.GRAY if episode.downloaded == 0 else Fore.RED))}{Color.RESET}] {Fore.BLUE if episode.downloaded > 0 and episode.downloaded < episode.size else Fore.RED if episode.downloaded == 0 else Fore.GREEN} {(episode.downloaded / (episode.size or 1) * 100):.2f}{Color.RESET}% {Fore.GREEN}{convert_size(episode.downloaded)}{Color.RESET}/{Fore.BLUE}{convert_size(episode.size)} {Color.RESET}[{episode.quality}]"
                item_index += 1

            return message
        
        self.console_logger.set_message(10, lambda: format_console())

        threads = []
        for _ in range(self.download_threads):
            threads.append(threading.Thread(target=asyncio.run, args=(downloader(),)))
            threads[-1].start()

        threads.append(threading.Thread(target=asyncio.run, args=(saver(),)))
        threads[-1].start()
        
        return threads

def start_timer_tick():
    async def tick():
        global timer
        while True:
            timer += 1
            await asyncio.sleep(1)

    threading.Thread(target=asyncio.run, args=(tick(),)).start()

async def main():
    start_timer_tick()
    args = extract_from_argv()
    console_logger = ConsoleLogger()
    console_logger.start(wait_for=.1)

    if ["help", True] in args[0]:
        print_help(console_logger)
        return
    
    proxies = None
    config = None
    proxy_threads = 500
    download_threads = 30
    timeout = 10
    skip_all_existing = False
    rename_all_existing = False
    overwrite_all_existing = False
    ignore_directory_warning = False
    info_str = ""
    
    for argument in args[0]:
        if argument[0] == "proxies":
            proxies = open(argument[1], "r").read().split("\n")

        if argument[0] == "config":
            config = json.load(open(argument[1], "r"))

        if argument == ["skip_all_existing", True]:
            skip_all_existing = True
            info_str += "Skipping all existing files.\n"

        if argument == ["rename_all_existing", True]:
            rename_all_existing = True
            info_str += "Renaming all existing files.\n"
        
        if argument == ["overwrite_all_existing", True]:
            overwrite_all_existing = True
            info_str += "Overwriting all existing files.\n"

        if argument == ["ignore_directory_warning", True]:
            ignore_directory_warning = True
            info_str += "Ignoring directory warning.\n"

        if argument[0] == "proxy_threads" and argument[1].isnumeric():
            proxy_threads = int(argument[1])

        if argument[0] == "download_threads" and argument[1].isnumeric():
            download_threads = int(argument[1])
        
        if argument[0] == "timeout" and argument[1].isnumeric():
            timeout = int(argument[1])

    unknown_arguments = False
    for index, argument in enumerate(args[1]):
        if argument.startswith("-"):
            console_logger.set_message(index, f"Unknown argument \"{argument}\"!")
            unknown_arguments = True
        
    if unknown_arguments:
        console_logger.stop(wait_for_print=True)
        return

    if not proxies:
        console_logger.set_message(0, "No proxies file specified!")
        console_logger.stop(wait_for_print=True)
        return
    
    if len(proxies) < 1:
        console_logger.set_message(0, "No proxies in proxies file!")
        console_logger.stop(wait_for_print=True)
        return
    
    if not config:
        console_logger.set_message(0, "No config file specified!")
        console_logger.stop(wait_for_print=True)
        return
    
    if not "series" in config:
        console_logger.set_message(0, "No series specified in config file!")
        console_logger.stop(wait_for_print=True)
        return
    
    if sum(1 for value in [skip_all_existing, rename_all_existing, overwrite_all_existing] if value) > 1:
        console_logger.set_message(0, "Only one of skip_all_existing, rename_all_existing and overwrite_all_existing flags can be set to True!")
        console_logger.stop(wait_for_print=True)
        return
    
    console_logger.set_message(0, "Checking internet connection...", True)

    for index in range(10):
        if check_internet_connection():
            console_logger.remove_message(1)
            console_logger.set_message(0, "Checking internet connection... [OK]")
            break
        
        console_logger.set_message(1, f"Try {index + 1}/10 failed...")
        await asyncio.sleep(1)

    console_logger.set_message(0, f"Checking {len(proxies)} proxies...", True)
    working_proxies = check_proxies([*proxies], proxy_threads)
    console_logger.set_message(5, f"Using {len(working_proxies)} working proxies.\n"
                                f"Using {download_threads} download threads.\n")
    console_logger.remove_message(0)
    if info_str:
        console_logger.set_message(1, info_str.removesuffix("\n"))

    def get_total_download_progress_and_speed():
        def make_progressbar(value, max_value, *, length=30, filled_color=Fore.GREEN, empty_color=Fore.GRAY, character="━"):
            progress_percentage = value / (max_value or 1)

            full_characters = character * int(progress_percentage * length)
            empty_characters = (character * length)[len(full_characters):]

            return f"{filled_color}{full_characters}{empty_color}{empty_characters}{Color.RESET}"

        def get_size_and_downloaded_of_nonignored_episodes(episodes: List[Episode]) -> int:
            fsum = 0
            dsum = 0
            for episode in episodes:
                if type(episode) != Episode:
                    continue

                if episode.ignore:
                    continue

                fsum += episode.size
                dsum += episode.downloaded
            return fsum, dsum
        
        def calculate_eta(download_progress: float):
            global timer
            seconds_to_finish = int((1 - download_progress) / (download_progress or 1) * timer)
            return str(timedelta(seconds=seconds_to_finish))

        
        total_size = 0
        downloaded_size = 0
        for series in series_objects:
            tsize, dsize = get_size_and_downloaded_of_nonignored_episodes(list(series.episodes.values()))
            total_size += tsize
            downloaded_size += dsize
        
        global timer, last_downloaded_amount, last_round_speed, speed_already_calculated
        if timer % SPEED_TIMER_ROUND == 0 and not speed_already_calculated:
            speed_already_calculated = True
            last_round_speed = (downloaded_size - last_downloaded_amount) / SPEED_TIMER_ROUND
            last_downloaded_amount = downloaded_size
        elif timer % SPEED_TIMER_ROUND != 0:
            speed_already_calculated = False

        return f"{Fore.ORANGE}Running for{Color.RESET}: {Fore.MAGENTA}{str(timedelta(seconds=timer))}\n" + \
        f"{Fore.ORANGE}Total progress{Color.RESET}: {Color.RESET}[{make_progressbar(downloaded_size, total_size, length=130)}{Color.RESET}] {Fore.GREEN}{downloaded_size / (total_size or 1) * 100:.2f}{Color.RESET}% {Fore.GREEN}{convert_size(downloaded_size)}{Color.RESET}/{Fore.BLUE}{convert_size(total_size)}{Color.RESET}\n" + \
        f"{Fore.ORANGE}ETA{Color.RESET}: {Color.RESET}[{Fore.MAGENTA}{calculate_eta(downloaded_size / (total_size or 1))}{Color.RESET}]\n" + \
        f"Average download speed: {Fore.GREEN}{convert_size(downloaded_size / (timer or 1))}/s{Color.RESET} | Average download speed in last {SPEED_TIMER_ROUND}s: {Fore.GREEN}{convert_size(last_round_speed)}/s{Color.RESET}"

    console_logger.set_message(6, lambda: get_total_download_progress_and_speed())

    series_objects: List[Series] = []
    for index, series in enumerate(config["series"]):
        series_object = Series(console_logger, config.get("datetime_format", "%Y-%d-%m %H-%M-%S"), series[0], series[1], series[2], series[3], index, [*proxies], download_threads,
            skip_all_existing, rename_all_existing, overwrite_all_existing)
        verified = series_object.verify_input(ignore_directory_warning=ignore_directory_warning)
        if verified == "directory":
            console_logger.stop(wait_for_print=True)
            return
        elif verified == "url":
            console_logger.set_message(0, f"URL \"{series[0]}\" is not valid!")
            console_logger.stop(wait_for_print=True)
            return
        
        series_objects.append(series_object)

    for series in series_objects:
        series.start_fetcher()

    for series in series_objects:
        console_logger.set_message(7, lambda: f"\nDownloading series {series_objects.index(series) + 1} out of {len(series_objects)} ({Fore.LIGHT_GRAY}\"{Fore.MINT}{series.series_title}{Fore.LIGHT_GRAY}\"{Color.RESET})...")
        for thread in series.start_downloader():
            thread.join()

    console_logger.set_message(1000, "\n\nAll done!\n\n\n")
        
    console_logger.stop(wait_for_print=True)
    return  

if __name__ == "__main__":
    asyncio.run(main())


# TODO: Check if enough space is available before downloading
# TODO: Login using creds instead of hand-copying cookies
# TODO: Create ETA for entire content that will be downloaded (all series)
