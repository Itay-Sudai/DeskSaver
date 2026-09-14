import os
import json
import socket
import threading
import customtkinter as ctk
from tkinter import filedialog, messagebox
import ssl




BASE_DIR = os.path.dirname(os.path.abspath(__file__))
SERVER_CERT = os.path.join(BASE_DIR, "server.crt")


# ------------------------------
# Socket helpers (one JSON per line)
# ------------------------------
def send_request(host, port, req: dict) -> dict:
    """Sends request to server"""
    payload = (json.dumps(req, ensure_ascii=False) + "\n").encode("utf-8")
    print("[TLS] SERVER_CERT =", SERVER_CERT)
    print("[TLS] exists =", os.path.exists(SERVER_CERT))

    #context = ssl.create_default_context(ssl.Purpose.SERVER_AUTH)
    #context.load_verify_locations(cafile=SERVER_CERT)
    context = ssl.create_default_context()
    context.check_hostname = False
    context.verify_mode = ssl.CERT_NONE

    print("[DEBUG] payload sending")
    with socket.create_connection((host, port), timeout=10) as s:
        with context.wrap_socket(s, server_hostname=host) as ssock:
            ssock.sendall(payload)
            buf = bytearray()
            while True:
                chunk = ssock.recv(4096)
                if not chunk:
                    break
                buf.extend(chunk)
                if b"\n" in chunk:
                    break
            line = buf.split(b"\n", 1)[0].decode("utf-8", errors="replace")
            return json.loads(line)


def read_local_preset(snapshot_dir: str, name: str):
    """Reads """
    print("[DEBUG] reading local preset")
    path = os.path.join(snapshot_dir, f"{name}.json")
    with open(path, "r", encoding="utf-8") as f:
        data = json.load(f)
    if not isinstance(data, list):
        raise ValueError("Local preset JSON must be a LIST (offline format).")
    return data


def write_local_preset(snapshot_dir: str, name: str, programs):
    """Writes a local preset into the servers snapshot file"""
    print("[DEBUG] writing in, a local preset")
    os.makedirs(snapshot_dir, exist_ok=True)
    path = os.path.join(snapshot_dir, f"{name}.json")
    with open(path, "w", encoding="utf-8") as f:
        json.dump(programs, f, indent=4, ensure_ascii=False)
    return path


class DeskSaverOnlineGUI(ctk.CTk):
    def __init__(self):
        super().__init__()
        ctk.set_appearance_mode("light")
        self.title("DeskSaver Online (Users + Sharing)")
        self.geometry("920x620+420+100")

        # Connection
        self.server_host = ctk.StringVar(value="192.168.0.108")
        self.server_port = ctk.IntVar(value=5050)

        # Auth
        self.username = ctk.StringVar(value="")
        self.password = ctk.StringVar(value="")
        self.token = None
        self.role = None

        # Offline snapshots folder
        self.snapshots_dir = ctk.StringVar(value=r"D:\dev\offline_DeskSaver_working\snapshots")

        # ---------- UI ----------
        header = ctk.CTkLabel(self, text="DeskSaver Online", font=("Arial", 24, "bold"))
        header.pack(pady=10)

        top = ctk.CTkFrame(self)
        top.pack(fill="x", padx=12, pady=6)

        ctk.CTkLabel(top, text="Server IP").grid(row=0, column=0, padx=6, pady=6, sticky="w")
        ctk.CTkEntry(top, textvariable=self.server_host, width=160).grid(row=0, column=1, padx=6, pady=6)

        ctk.CTkLabel(top, text="Port").grid(row=0, column=2, padx=6, pady=6, sticky="w")
        ctk.CTkEntry(top, textvariable=self.server_port, width=90).grid(row=0, column=3, padx=6, pady=6)

        ctk.CTkLabel(top, text="Username").grid(row=0, column=4, padx=6, pady=6, sticky="w")
        ctk.CTkEntry(top, textvariable=self.username, width=140).grid(row=0, column=5, padx=6, pady=6)

        ctk.CTkLabel(top, text="Password").grid(row=0, column=6, padx=6, pady=6, sticky="w")
        ctk.CTkEntry(top, textvariable=self.password, width=160, show="*").grid(row=0, column=7, padx=6, pady=6)

        ctk.CTkButton(top, text="Register", command=self.register_user).grid(row=0, column=8, padx=6, pady=6)
        ctk.CTkButton(top, text="Login", command=self.login).grid(row=0, column=9, padx=6, pady=6)
        ctk.CTkButton(top, text="Refresh", command=self.refresh_presets).grid(row=0, column=10, padx=6, pady=6)

        self.status_lbl = ctk.CTkLabel(self, text="Not logged in")
        self.status_lbl.pack(pady=(0, 6))

        snap = ctk.CTkFrame(self)
        snap.pack(fill="x", padx=12, pady=6)
        ctk.CTkLabel(snap, text="Offline snapshots folder:").pack(side="left", padx=8)
        ctk.CTkEntry(snap, textvariable=self.snapshots_dir).pack(side="left", expand=True, fill="x", padx=8)
        ctk.CTkButton(snap, text="Browse", command=self.browse_snapshots).pack(side="left", padx=8)
        ctk.CTkButton(snap, text="Open", command=self.open_snapshots_folder).pack(side="left", padx=8)

        # Main split: presets + actions + admin
        main = ctk.CTkFrame(self)
        main.pack(fill="both", expand=True, padx=12, pady=10)

        # Presets list
        left = ctk.CTkFrame(main)
        left.pack(side="left", fill="both", expand=True, padx=8, pady=8)

        ctk.CTkLabel(left, text="Visible presets (yours + shared to you)", font=("Arial", 16, "bold")).pack(pady=(8, 4))

        self.presets_box = ctk.CTkTextbox(left)
        self.presets_box.pack(fill="both", expand=True, padx=8, pady=8)
        self._set_presets_text("Login then press Refresh.\n")

        # Right actions
        right = ctk.CTkFrame(main, width=360)
        right.pack(side="right", fill="y", padx=8, pady=8)

        ctk.CTkLabel(right, text="Actions", font=("Arial", 16, "bold")).pack(pady=(8, 4))

        self.preset_entry = ctk.CTkEntry(right, placeholder_text="Preset name (e.g. Coding)")
        self.preset_entry.pack(fill="x", padx=10, pady=6)

        ctk.CTkButton(right, text="Upload (save to server)", command=self.upload_preset).pack(fill="x", padx=10, pady=5)
        ctk.CTkButton(right, text="Download (to offline snapshots)", command=self.download_preset).pack(fill="x", padx=10, pady=5)
        ctk.CTkButton(right, text="Delete (server)", command=self.delete_preset).pack(fill="x", padx=10, pady=5)

        # Sharing block
        ctk.CTkLabel(right, text="Sharing (owner/admin)", font=("Arial", 14, "bold")).pack(pady=(16, 4))

        self.share_target = ctk.CTkEntry(right, placeholder_text="Target username (e.g. Itay)")
        self.share_target.pack(fill="x", padx=10, pady=5)

        self.share_perm = ctk.StringVar(value="read")
        self.share_perm_menu = ctk.CTkOptionMenu(right, values=["read", "write", "none"], variable=self.share_perm)
        self.share_perm_menu.pack(fill="x", padx=10, pady=5)

        ctk.CTkButton(right, text="Share selected preset", command=self.share_preset).pack(fill="x", padx=10, pady=5)

        # Admin panel (hidden unless admin)
        self.admin_frame = ctk.CTkFrame(right)
        self.admin_frame.pack(fill="x", padx=10, pady=(18, 6))

        ctk.CTkLabel(self.admin_frame, text="Admin", font=("Arial", 14, "bold")).pack(pady=(8, 4))
        ctk.CTkButton(self.admin_frame, text="List users", command=self.admin_list_users).pack(fill="x", padx=8, pady=4)

        self.log_tail_n = ctk.IntVar(value=200)
        ctk.CTkEntry(self.admin_frame, textvariable=self.log_tail_n).pack(fill="x", padx=8, pady=4)
        ctk.CTkButton(self.admin_frame, text="Show log tail", command=self.admin_log_tail).pack(fill="x", padx=8, pady=4)

        # Start hidden
        self.admin_frame.pack_forget()

        # Log box
        self.log_box = ctk.CTkTextbox(self, height=140)
        self.log_box.pack(fill="x", padx=12, pady=(0, 12))
        self.log("Ready.")

    # ------------------------------
    # UI helpers
    # ------------------------------
    def _server(self):
        return self.server_host.get().strip(), int(self.server_port.get())


    def _preset_name(self):
        return self.preset_entry.get().strip()


    def _require_login(self):
        if not self.token:
            messagebox.showwarning("Login required", "Please login first.")
            return False
        return True


    def _set_presets_text(self, text: str):
        self.presets_box.configure(state="normal")
        self.presets_box.delete("1.0", "end")
        self.presets_box.insert("end", text)
        self.presets_box.configure(state="disabled")


    def log(self, msg: str):
        """Client side log UI"""
        self.log_box.insert("end", msg + "\n")
        self.log_box.see("end")
        self.update_idletasks()


    def _run_bg(self, fn, done=None):
        """Starts a new thread that updates the GUI in the background.\n
        fn - > points to function (e.g fn = job & job will only execute when fn() is called).\n
        Doing this wont freeze the UI"""
        def worker():
            try:
                result = fn()
                if done:
                    self.after(0, lambda: done(True, result)) # lambda puts off the calling of done
                    #after() expects a callable to run later on the GUI thread 
            except Exception as e:
                if done:
                    err = str(e)
                    self.after(0, lambda: done(False, err))
        threading.Thread(target=worker, daemon=True).start()


    def browse_snapshots(self):
        """Opens file explorer to choose the snapshot folder"""
        print("[DEBUG] snapshot browser")
        folder = filedialog.askdirectory()
        if folder:
            self.snapshots_dir.set(folder)


    def open_snapshots_folder(self):
        """Opens the current local snapshot folder in file explorer"""
        print("[DEBUG] snapshot folder open")
        path = self.snapshots_dir.get()
        if not os.path.exists(path):
            messagebox.showerror("Error", f"Folder not found:\n{path}")
            return
        os.startfile(path)

    # ------------------------------
    # Auth
    # ------------------------------
    def register_user(self):
        """Registering user.\n
        Sends: host, port, username, passsword -> to server.\n
        Updates: message box, client side log"""
        host, port = self._server()
        username = self.username.get().strip()
        password = self.password.get().strip()
        if not username or not password:
            messagebox.showwarning("Missing", "Enter username + password")
            return

        self.log(f"[REGISTER] {username}")

        def job():
            # role=admin only works for first ever user on the server
            return send_request(host, port, {"cmd": "REGISTER", "username": username, "password": password, "role": "admin"})

        def done(ok, res):
            if not ok:
                self.log(f"[REGISTER] Failed: {res}")
                return
            self.log(f"[REGISTER] {res}")

        self._run_bg(job, done) # passing request (job) and error message (done)


    def login(self):
        """Logging in user.\n
        Sends: host, port, username, passsword -> to server.\n
        Updates: message box, client side log"""
        host, port = self._server()
        username = self.username.get().strip()
        password = self.password.get().strip()
        if not username or not password:
            messagebox.showwarning("Missing", "Enter username + password")
            return

        self.log(f"[LOGIN] {username}")

        def job():
            return send_request(host, port, {"cmd": "LOGIN", "username": username, "password": password})

        def done(ok, res):
            if not ok or not res.get("ok"):
                self.log(f"[LOGIN] Failed: {res}")
                return
            self.token = res["token"]
            self.role = res.get("role")
            self.status_lbl.configure(text=f"Logged in as {res.get('user')} ({self.role})")

            if self.role == "admin": #
                self.admin_frame.pack(fill="x", padx=10, pady=(18, 6))
            else:
                self.admin_frame.pack_forget()

            self.log(f"[LOGIN] OK role={self.role}")
            self.refresh_presets()

        self._run_bg(job, done) # passing request (job) and error message (done)

    # ------------------------------
    # Presets
    # ------------------------------
    def refresh_presets(self):
        if not self._require_login():
            return

        host, port = self._server()
        self.log("[LIST] Refreshing presets...")

        def job():
            return send_request(host, port, {"cmd": "LIST", "token": self.token})

        def done(ok, res):
            if not ok:
                self.log(f"[LIST] Failed: {res}")
                return
            if not res.get("ok"):
                self.log(f"[LIST] Server error: {res}")
                return
            presets = res.get("presets", [])
            self.log(f"[LIST] Found {len(presets)}")
            self._set_presets_text("\n".join(presets) + ("\n" if presets else ""))
        self._run_bg(job, done)

    def upload_preset(self):
        if not self._require_login():
            return

        preset = self._preset_name()
        if not preset:
            messagebox.showwarning("Missing", "Enter preset name")
            return

        snapshot_dir = self.snapshots_dir.get()
        host, port = self._server()
        self.log(f"[UPLOAD] {preset}")

        def job():
            programs = read_local_preset(snapshot_dir, preset)
            return send_request(host, port, {"cmd": "PUT", "name": preset, "programs": programs, "token": self.token})

        def done(ok, res):
            if not ok:
                self.log(f"[UPLOAD] Failed: {res}")
                return
            if not res.get("ok"):
                self.log(f"[UPLOAD] Server error: {res}")
                return
            self.log(f"[UPLOAD] OK saved={res.get('saved')} owner={res.get('owner')} count={res.get('count')}")
            self.refresh_presets()

        self._run_bg(job, done) # passing request (job) and error message (done)

    def download_preset(self):
        if not self._require_login():
            return

        preset = self._preset_name()
        if not preset:
            messagebox.showwarning("Missing", "Enter preset name")
            return

        snapshot_dir = self.snapshots_dir.get()
        host, port = self._server()
        self.log(f"[DOWNLOAD] {preset}")

        def job():
            res = send_request(host, port, {"cmd": "GET", "name": preset, "token": self.token})
            if not res.get("ok"):
                raise RuntimeError(str(res))
            preset_payload = res["preset"]
            programs = preset_payload.get("programs", [])
            path = write_local_preset(snapshot_dir, preset, programs)
            return {"saved_to": path, "count": len(programs), "owner": preset_payload.get("owner")}

        def done(ok, res):
            if not ok:
                self.log(f"[DOWNLOAD] Failed: {res}")
                return
            self.log(f"[DOWNLOAD] OK  saved_to={res['saved_to']} count={res['count']} owner={res.get('owner')}")

        self._run_bg(job, done) # passing request (job) and error message (done)

    def delete_preset(self):
        if not self._require_login():
            return

        preset = self._preset_name()
        if not preset:
            messagebox.showwarning("Missing", "Enter preset name")
            return

        if not messagebox.askyesno("Confirm delete", f"Delete '{preset}' from server?"):
            return

        host, port = self._server()
        self.log(f"[DELETE] {preset}")

        def job():
            return send_request(host, port, {"cmd": "DELETE", "name": preset, "token": self.token})

        def done(ok, res):
            if not ok:
                self.log(f"[DELETE] Failed: {res}")
                return
            self.log(f"[DELETE] {res}")
            self.refresh_presets()

        self._run_bg(job, done) # passing request (job) and error message (done)

    # ------------------------------
    # Sharing
    # ------------------------------
    def share_preset(self):
        if not self._require_login():
            return

        preset = self._preset_name()
        if not preset:
            messagebox.showwarning("Missing", "Enter preset name")
            return

        target = self.share_target.get().strip()
        perm = self.share_perm.get().strip().lower()
        if not target:
            messagebox.showwarning("Missing", "Enter target username")
            return

        host, port = self._server()
        self.log(f"[SHARE] {preset} -> {target} ({perm})")

        def job():
            return send_request(host, port, {
                "cmd": "SHARE",
                "name": preset,
                "target": target,
                "perm": perm,
                "token": self.token
            })

        def done(ok, res):
            if not ok:
                self.log(f"[SHARE] Failed: {res}")
                return
            self.log(f"[SHARE] {res}")

        self._run_bg(job, done) # passing request (job) and error message (done)

    # ------------------------------
    # Admin
    # ------------------------------
    def admin_list_users(self):
        if not self._require_login():
            return
        if self.role != "admin":
            messagebox.showwarning("Admin only", "You are not an admin.")
            return

        host, port = self._server()
        self.log("[ADMIN] LIST_USERS")

        def job():
            return send_request(host, port, {"cmd": "LIST_USERS", "token": self.token})

        def done(ok, res):
            if not ok:
                self.log(f"[ADMIN] Failed: {res}")
                return
            self.log(f"[ADMIN] Users:\n" + "\n".join(res.get("users", [])))

        self._run_bg(job, done) # passing request (job) and error message (done)

    def admin_log_tail(self):
        if not self._require_login():
            return
        if self.role != "admin":
            messagebox.showwarning("Admin only", "You are not an admin.")
            return

        host, port = self._server()
        n = int(self.log_tail_n.get())
        self.log(f"[ADMIN] LOG_TAIL n={n}")

        def job():
            return send_request(host, port, {"cmd": "LOG_TAIL", "n": n, "token": self.token})

        def done(ok, res):
            if not ok:
                self.log(f"[ADMIN] Failed: {res}")
                return
            txt = res.get("log", "")
            self.log("[ADMIN] log tail:\n" + (txt if txt else "(empty)"))

        self._run_bg(job, done) # passing request (job) and error message (done)


def main():
    app = DeskSaverOnlineGUI()
    app.mainloop()

if __name__ == "__main__":
    main()
