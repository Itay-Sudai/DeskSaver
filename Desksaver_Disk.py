import os
import re
import socket
from pywinauto import Desktop as PywinautoDesktop
#from pywinauto import Application
#from pywinauto.findwindows import ElementNotFoundError
import json
import psutil
import subprocess
import time
import pyautogui
import customtkinter as ctk
#import win32process
import shutil


#TODO:
#WhiteList - default, add , remove,
#Load - block cmd, powershell (check white list not includes)


current_folder = os.path.dirname(os.path.abspath(__file__))
CURRENT_HOST = socket.gethostname()
WINDOW_SIZE = "400x400+500+100"


def adapt_path_to_host(path: str) -> str:
    """Replace a foreign hostname in a path with the current machine's hostname.

    Handles:
      - UNC paths:      \\\\OLDHOST\\share\\...  ->  \\\\CURRENTHOST\\share\\...
      - Profile paths:  C:\\Users\\OLDHOST\\...   ->  C:\\Users\\CURRENTHOST\\...
    Returns the adapted path (may be unchanged if no substitution needed).
    """
    # UNC: \\HOSTNAME\...
    unc = re.match(r'^(\\\\)([^\\]+)(\\.*)', path)
    if unc:
        old_host = unc.group(2)
        if old_host.lower() != CURRENT_HOST.lower():
            return unc.group(1) + CURRENT_HOST + unc.group(3)
        return path

    # User profile folder named after host: C:\Users\HOSTNAME\...
    prof = re.match(r'^([A-Za-z]:\\[Uu]sers\\)([^\\]+)(\\.*)', path)
    if prof:
        old_host = prof.group(2)
        if old_host.lower() != CURRENT_HOST.lower():
            candidate = prof.group(1) + CURRENT_HOST + prof.group(3)
            if os.path.exists(candidate):
                return candidate

    return path

#self.wm_attributes('-fullscreen', True)

class Desktop(object):
    """
    Handling desktop propeties.
    """
    def __init__(self, save_path="snapshots", preset_name="default"):
        """Desktop() constractor."""
        # Make sure save path exists
        self.save_path = os.path.join(current_folder, save_path)
        os.makedirs(self.save_path, exist_ok=True)
        self.preset_name = preset_name
        self.programs = [] # will hold running program info
    

    def capture(self):
        """Capture all user apps, their positions, and store in self.programs"""
        desk = PywinautoDesktop(backend="uia")
        windows = desk.windows()
        self.programs = []

        my_pid = os.getpid()
    
        for w in windows:
            try:
                pid = w.process_id()
                if pid == my_pid:
                    continue # Skip capturing this program itself
            except Exception:
                pid = None
                
            #TODO: Fix position not working

            try:
                rect = w.rectangle()
                position = {
                    "left": rect.left,
                    "top": rect.top,
                    "width": rect.width(),
                    "height": rect.height()
                }
                if position and (position["width"] <= 0 or position["height"] <= 0):
                    position = None

            except Exception:
                position = None

            # Get title
            try:
                title = w.window_text()
            except Exception:
                title = ""

            title = (title or "").strip()
            if not title:
                continue

            try:
                if pid is None:
                    continue
                p = psutil.Process(pid)
                cmd = p.cmdline()

                if not cmd:
                    exe = p.name()
                    args = []
                else:
                    exe = cmd[0]
                    args = cmd[1:] if len(cmd) > 1 else []

                # Detect UWP apps hosted by ApplicationFrameHost.exe
                if exe.lower().endswith("applicationframehost.exe"):
                    app_type = "uwp"
                    aumid = self.get_aumid(title)
                else:
                    app_type = "win32"
                    aumid = None

                # Skip obvious system processes
                if app_type == "win32" and exe.lower().startswith(r"c:\windows"):
                    continue

                self.programs.append({
                    "exe": exe,
                    "args": args,
                    "title": title,
                    "pid": pid,
                    "position": position,
                    "type": app_type,
                    "aumid": aumid
                })

            except (psutil.NoSuchProcess, psutil.AccessDenied):
                continue

        print(f"[Desktop] Captured {len(self.programs)} programs")
        for prog in self.programs:
            print(prog)


    def save(self): #TODO: stop saving PID 
        """Saves programs to JSON with preset name"""
        filename = f"{self.preset_name}.json"
        print(f"[DEBUG][SAVE] -- file name -- {filename}")

        file_path = os.path.join(self.save_path, filename)
        with open(file_path, "w") as f:
            json.dump(self.programs, f, indent=4)
        print(f"[Desktop] Saved preset '{self.preset_name}' to {file_path}")

    def load_from_file(self): # TODO: sig, whitelist
        filename = f"{self.preset_name}.json"
        file_path = os.path.join(self.save_path, filename)

        if not os.path.exists(file_path):
            print(f"[Desktop] Preset file not found: {file_path}")
            self.programs = []
            return False

        with open(file_path, "r", encoding="utf-8") as f:
            self.programs = json.load(f)

        print(f"[Desktop] Loaded preset '{self.preset_name}' from {file_path} ({len(self.programs)} items)")
        return True

    def load(self):
        """Launch all saved programs and restore their positions"""

        if not self.load_from_file():
            return

        for program in self.programs:
            exe = program["exe"]
            position = program["position"]

            # ---------- UWP ----------
            if program["type"] == "uwp":
                if program.get("aumid"):
                    try:
                        print(f"[LOAD] Launching UWP: {program['title']}")
                        subprocess.Popen(["explorer.exe", f"shell:AppsFolder\\{program['aumid']}"])
                    except Exception as e:
                        print(e)
                else:
                    print(f"[LOAD] Skipping UWP (missing aumid): {program.get('title')}")
                time.sleep(1.0)
                continue

            # ---------- WIN32 ----------
            if program["type"] == "win32":
                args = program.get("args") or []

                # Replace foreign hostname in exe path
                exe = adapt_path_to_host(exe)

                # resolve exe path (handles just 'chrome.exe')
                if not os.path.exists(exe):
                    found = shutil.which(os.path.basename(exe))
                    if found:
                        exe = found
                    else:
                        print(f"[LOAD] Failed to load \"{program['exe']}\" (not found after host substitution, skipping)")
                        continue

                try:
                    if args:
                        subprocess.Popen([exe, *args], close_fds=True)
                    else:
                        os.startfile(exe)
                except Exception as e:
                    print(f"[LOAD] Failed launching {exe}: {e}")
                    continue

                time.sleep(1.0)
            # Give the app time to launch before moving
#
            ## Restore position
            #if position:
            #    try:
            #        app = Application(backend="uia").connect(path=exe)
            #        window = app.top_window()
            #        window.move_window(
            #            x=position["left"],
            #            y=position["top"],
            #            width=position["width"],
            #            height=position["height"],
            #            repaint=True
            #        )
            #        print(f"[LOAD] Moved {exe} to {position}")
            #    except Exception as e:
            #        print(f"[LOAD] Could not move {exe}: {e}")


    # --------------------------------------------------
    # UWP AUMID
    # --------------------------------------------------

    def get_aumid(self, app_name):
        safe = (app_name or "").replace('"', '`"')

        ps = (
            f'Get-StartApps | '
            f'Where-Object {{ $_.Name -eq "{safe}" }} | '
            f'Select-Object -First 1 -ExpandProperty AppID'
        )

        # Force 64-bit powershell
        powershell_path = r"C:\Windows\Sysnative\WindowsPowerShell\v1.0\powershell.exe"

        result = subprocess.run(
            [powershell_path, "-NoProfile", "-ExecutionPolicy", "Bypass", "-Command", ps],
            capture_output=True,
            text=True,
            timeout=10
        )

        if result.stderr.strip():
            print("[get_aumid] stderr:", result.stderr.strip())

        return result.stdout.strip() or None


    def set_name(self, preset_name):
        """Setting preset name <preset_name>"""
        self.preset_name = preset_name
        print(f"[Desktop] Preset name is set to: '{self.preset_name}'")
    

    def get_name(self):
        """Returning preset_name"""
        return self.preset_name
    

    def quit(self):
        raise SystemExit

    def new_preset(self, preset_name):
        preset_name = preset_name.strip()
        if not preset_name:
            print("[Desktop] Preset name is empty")
            return False

        file_path = os.path.join(self.save_path, f"{preset_name}.json")
        if os.path.exists(file_path):
            print("[Desktop] Preset already exists")
            return False

        with open(file_path, "w", encoding="utf-8") as f:
            json.dump([], f, indent=4)

        print(f"[Desktop] Created preset '{preset_name}'")
        return True

    

    def choose_preset(self):
        """
        Choosing a preset to work on

        Returns a list of strings contaning all json files without .json at the
        """
        try:
            all_files = os.listdir(self.save_path)  # Goes to snapshots folder and gets all files from there
            json_files = []
        except Exception as e:
            print(f"[Error | choose_preset] {e}")

        for file in all_files: # Checks for each file if it is a .json file
            if file.endswith(".json"):
                json_files.append(file) # Addes all .json file to a list
                #print(f"[DEBUG CHOOSE_PRESET] {file}"")
                #        
        presets = [] 
        for file in json_files: 
            just_name, _ = os.path.splitext(file) # Removes from string .json 
            presets.append(just_name)
            #print(f"[DEBUG CHOOSE_PRESET] {file}"")
        return presets