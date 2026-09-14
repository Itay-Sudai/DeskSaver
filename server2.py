import os
import json
import socket
import threading
import time
import secrets
import hashlib
from datetime import datetime
from typing import Optional, Dict, Any, Tuple
import ssl

HOST = "0.0.0.0"
PORT = 5050


CONNECTION_RECV_LENGTH = 4096


BASE_DIR = os.path.dirname(os.path.abspath(__file__))

DATA_DIR   = os.path.join(BASE_DIR, "preset_store")
USERS_FILE = os.path.join(BASE_DIR, "users_db.json")
LOG_FILE   = os.path.join(BASE_DIR, "server.log")

SERVER_CERT = os.path.join(BASE_DIR, "server.crt")
SERVER_PRIVATE_KEY = os.path.join(BASE_DIR, "server.key")

os.makedirs(DATA_DIR, exist_ok=True)

# ---- Auth/session ----
# token -> {"user": username, "role": "user"/"admin", "issued_at": int, "last_seen": int}
SESSIONS: Dict[str, Dict[str, Any]] = {}
SESSIONS_LOCK = threading.Lock()

SESSION_OVER_SECONDS = 60 * 60 * 24  # 24h in seconds. Usage: deleting token for session that exisits for more then 24h

# ---- Locks for presets ----
_locks: Dict[str, threading.Lock] = {}
#Visual example:
#_locks = {
#{"preset_name1",<lock>,}
#{"preset_name2",<lock>,}
#{"preset_name3",<lock>}
#}

_global_lock = threading.Lock()
#prevents race conditions while creating/retriving preset locks.
#ensures only shared lock per preset name...

def lock_for(name: str) -> threading.Lock:
    """Creates or retreives lock for preset name"""
    with _global_lock:
        if name not in _locks:
            _locks[name] = threading.Lock()
        return _locks[name]


# -----------------------
# Utilities
# -----------------------
def ensure_server_storage():
    """Makes sure that all storage files exist.\n
    If not, creates them."""
    #create preset directory
    os.makedirs(DATA_DIR, exist_ok=True)

    # create users db file if missing
    if not os.path.exists(USERS_FILE):
        with open(USERS_FILE, "w", encoding="utf-8") as f:
            json.dump({"users": {}}, f, indent=2)

    # create log file if missing
    if not os.path.exists(LOG_FILE):
        with open(LOG_FILE, "w", encoding="utf-8") as f:
            pass   # empty log file

def now_iso():
    """Returns current time. Usage - Log documentation"""
    return datetime.utcnow().strftime("%Y-%m-%d - %H:%M:%S")


def log_event(addr, user: str, cmd: str, name: str, ok: bool, detail: str = ""):
    """Logs event into the log file"""
    line = f"{now_iso()} ip={addr[0]} user={user} cmd={cmd} preset={name} ok={ok} detail={detail}\n"
    #line is - time, ip, username, command, presetname, validity, detail
    #detail is different for each command and validation
    with open(LOG_FILE, "a", encoding="utf-8") as f: #appends line in log file..
        f.write(line)


def safe_name(name: str) -> str:
    """Verifies preset name contains only alphanumeric characters.\n
    Exeption for: - _ and spaces."""
    
    chars = []
    for ch in name:
        if ch.isalnum() or ch in ("-", "_", " "): #Only appends legeal characters
            chars.append(ch)

    s = "".join(chars)
    s = s.strip()
    if not s:
        raise ValueError("Invalid preset name")
    return s


def preset_path(name: str) -> str:
    """Returns server side preset path (../../preset_store/presetname.json)"""
    return os.path.join(DATA_DIR, f"{safe_name(name)}.json")


def send_line(connstream: socket.socket, obj: dict):
    """Sends json message and marks it's end with \\n"""
    data = (json.dumps(obj, ensure_ascii=False) + "\n").encode("utf-8")
    connstream.sendall(data)


def recv_line(connstream: socket.socket, max_bytes=1_000_000) -> str:
    """Recives json message until it reads \\n"""
    buf = bytearray()
    while True:
        chunk = connstream.recv(CONNECTION_RECV_LENGTH)
        if not chunk:
            break #basicly if the connection closed for some reson it stops reading
        buf.extend(chunk)

        if len(buf) > max_bytes: #size safety check
            raise ValueError("Request too large")
        
        if b"\n" in chunk: #message is over, stops reading
            break

    line = buf.split(b"\n", 1)[0] #ignore \n and everything after if exsists 
    return line.decode("utf-8", errors="replace") #if client sends a bad utf-8,
                                                  #replace errors instead of crashing


# -----------------------
# Users DB
# -----------------------
def load_users() -> dict:
    """Returns users dictionary"""
    if not os.path.exists(USERS_FILE):
        return {"users": {}}
    try:
        with open(USERS_FILE, "r", encoding="utf-8") as f:
            return json.load(f)
    except Exception:
        return {"users": {}}


def save_users(db: dict):
    """Takes a dictionary and saves it into the users file"""
    #writing into a tmp file so if it fails and ect' the user file wont be affected
    #ofc when finishing it replaces back to the original users file.
    tmp = USERS_FILE + ".tmp"
    with open(tmp, "w", encoding="utf-8") as f:
        json.dump(db, f, indent=2, ensure_ascii=False)
    os.replace(tmp, USERS_FILE)


def pbkdf2_hash_password(password: str, salt: bytes) -> str:
    """Returns hexed password.\n
    Hash and salt"""
    dk = hashlib.pbkdf2_hmac("sha256", password.encode("utf-8"), salt, 200_000)
    return dk.hex()


def create_user(username: str, password: str, role: str = "user") -> Tuple[bool, str]:
    """Creating new user"""
    username = username.strip()

    if not username or len(username) < 3:
        return False, "Username too short (min 3)"

    if not username or any(ch in username for ch in "\\/:*?\"<>|"):
        return False, "Invalid characters in username"

    if not password or len(password) < 6:
        return False, "Password too short (min 6)"

    db = load_users()
    users = db.setdefault("users", {}) #if user exists -> returns it. else -> create it as {} and return it
                                     
    if username in users:
        return False, "User already exists"

    salt = secrets.token_bytes(16) #creates salt, len = 16 bytes
    #creates new user
    users[username] = {
        "role": role,
        "salt": salt.hex(),
        "pw": pbkdf2_hash_password(password, salt),
        "created_at": now_iso()
    }
    save_users(db) #saves new user into db
    return True, "User created"

def verify_user(username: str, password: str) -> Optional[dict]:
    """Verifies user.\n
    Returns dict\\none."""
    db = load_users()
    user = db.get("users", {}).get(username) #gets db[users] value if exisits. else -> {}
    if not user:
        return None
    salt = bytes.fromhex(user["salt"])
    candidate = pbkdf2_hash_password(password, salt)
    if secrets.compare_digest(candidate, user["pw"]):
        return {"user": username, "role": user.get("role", "user")}
    return None

def issue_token(username: str, role: str) -> str:
    """Issues unique token for user."""
    token = secrets.token_urlsafe(32)
    now = int(time.time())
    with SESSIONS_LOCK:
        SESSIONS[token] = {"user": username, "role": role, "issued_at": now, "last_seen": now}
    return token

def get_session(token: str) -> Optional[dict]:
    """Updates session last_seen time.\n
    Deletes session token if 24h passed."""
    if not token:
        return None
    now = int(time.time())
    with SESSIONS_LOCK:
        sesh = SESSIONS.get(token)
        if not sesh:
            return None
        if now - sesh["last_seen"] > SESSION_OVER_SECONDS:
            del SESSIONS[token] #deleting object.
            return None
        sesh["last_seen"] = now
        return sesh.copy()

# -----------------------
# Preset permissions
# -----------------------
# Preset file format on server:
# {
#   "schema": 1,
#   "preset_name": "X",
#   "owner": "alice",
#   "acl": {"bob": "read", "charlie": "write"},   # optional
#   "created_at": "...",
#   "updated_at": "...",
#   "programs": [ ... ]   # your list
# }

def can_read(preset: dict, session: dict) -> bool:
    """Returns if a user can read a preset.\n
    Will return True if user_role = admin, or permmision for reading was granted."""
    if session["role"] == "admin":
        return True
    user = session["user"]
    if preset.get("owner") == user:
        return True
    perm = (preset.get("acl") or {}).get(user)
    return perm in ("read", "write")


def can_write(preset: dict, session: dict) -> bool:
    """Returns if a user can write a preset.\n
    Will return True if user_role = admin, or permmision for reading was granted."""
    if session["role"] == "admin":
        return True
    user = session["user"]
    if preset.get("owner") == user:
        return True
    perm = (preset.get("acl") or {}).get(user)
    return perm == "write"


def can_delete(preset: dict, session: dict) -> bool:
    """Returns if a user can delete a preset\n
    Will return True if user_role = admin, or permmision for deleting was granted."""
    # same as write for now
    return can_write(preset, session)


def load_preset_file(name: str) -> Optional[dict]:
    """Loads preset file (by name)"""
    path = preset_path(name)
    if not os.path.exists(path):
        return None
    with open(path, "r", encoding="utf-8") as f:
        return json.load(f)


def save_preset_file(name: str, data: dict):
    """Save a preset file from local to server"""
    path = preset_path(name)
    tmp = path + ".tmp" #writing into a tmp file so if it fails and ect' the user file wont be affected
    #ofc when finishing it replaces back to the original users file.
    with open(tmp, "w", encoding="utf-8") as f:
        json.dump(data, f, indent=2, ensure_ascii=False)
    os.replace(tmp, path)

   
def list_usernames() -> list:
    """Lists all usernames"""
    db = load_users()
    return sorted(list(db.get("users", {}).keys()))


def read_log_tail(n: int) -> str:
    """Return the last n lines of the server log file"""
    if not os.path.exists(LOG_FILE):
        return ""
    n = max(1, min(int(n), 5000)) # so its always x > 1 & x < 5000

    with open(LOG_FILE, "r", encoding="utf-8", errors="replace") as f:
        lines = f.readlines()
    return "".join(lines[-n:])


# -----------------------
#  handling
# -----------------------
def handle_client(connstream: socket.socket, addr):
    """Client request handler"""
    user_for_log = "-"
    cmd_for_log = "-"
    preset_for_log = "-"

    try:
        raw = recv_line(connstream)
        if not raw:
            return

        try:
            req = json.loads(raw)
        except json.JSONDecodeError:
            send_line(connstream, {"ok": False, "error": "Bad JSON"})
            return

        cmd = (req.get("cmd") or "").upper()
        cmd_for_log = cmd

        # ---- Register (no token required) ----
        if cmd == "REGISTER":
            username = req.get("username")
            password = req.get("password")
            role = req.get("role", "user")
            # security: only allow creating admin if no users exist, else force user
            db = load_users()
            if not db.get("users"):
                role = "admin"
            else:
                role = "user"
            print(f"[DEBUG] {role}")
            ok, msg = create_user(username, password, role=role)
            user_for_log = username or "-"
            log_event(addr, user_for_log, cmd, "-", ok, msg)
            send_line(connstream, {"ok": ok, "message": msg})
            return

        # ---- Login (no token required) ----
        if cmd == "LOGIN":
            username = req.get("username")
            password = req.get("password")
            auth = verify_user(username, password)
            if not auth:
                user_for_log = username or "-"
                log_event(addr, user_for_log, cmd, "-", False, "Invalid credentials")
                send_line(connstream, {"ok": False, "error": "Invalid credentials"})
                return
            token = issue_token(auth["user"], auth["role"])
            user_for_log = auth["user"]
            log_event(addr, user_for_log, cmd, "-", True, "Login ok") #dict[loginS] 
            send_line(connstream, {"ok": True, "token": token, "role": auth["role"], "user": auth["user"]})
            return

        # ---- All other commands require token ----
        token = req.get("token")
        session = get_session(token)
        if not session:
            log_event(addr, "-", cmd, "-", False, "Invalid/expired token")
            send_line(connstream, {"ok": False, "error": "Unauthorized (invalid/expired token)"})
            return

        user_for_log = session["user"]
        # ----- Admin: LIST_USERS -----
        if cmd == "LIST_USERS":
            if session["role"] != "admin":
                log_event(addr, user_for_log, cmd, "-", False, "Forbidden")
                send_line(connstream, {"ok": False, "error": "Forbidden"})
                return
            users = list_usernames()
            log_event(addr, user_for_log, cmd, "-", True, f"count={len(users)}")
            send_line(connstream, {"ok": True, "users": users})
            return

        # ----- Admin: LOG_TAIL -----
        if cmd == "LOG_TAIL":
            if session["role"] != "admin":
                log_event(addr, user_for_log, cmd, "-", False, "Forbidden")
                send_line(connstream, {"ok": False, "error": "Forbidden"})
                return
            n = req.get("n", 200)
            txt = read_log_tail(n)
            log_event(addr, user_for_log, cmd, "-", True, f"n={n}")
            send_line(connstream, {"ok": True, "log": txt})
            return

        # LIST: return presets visible to user
        if cmd == "LIST":
            names = []
            for f in os.listdir(DATA_DIR):
                if not f.endswith(".json"):
                    continue
                name = os.path.splitext(f)[0]
                lock = lock_for(name)
                with lock:
                    preset = load_preset_file(name)
                if not preset:
                    continue
                if can_read(preset, session):
                    names.append(name)
            log_event(addr, user_for_log, cmd, "-", True, f"count={len(names)}")
            send_line(connstream, {"ok": True, "presets": sorted(names)})
            return

        # Commands with preset name
        name = req.get("name")
        if not isinstance(name, str) or not name.strip():
            log_event(addr, user_for_log, cmd, "-", False, "Missing preset name")
            send_line(connstream, {"ok": False, "error": "Missing preset name"})
            return

        name = safe_name(name)
        preset_for_log = name

        # GET
        if cmd == "GET":
            lock = lock_for(name)
            with lock:
                preset = load_preset_file(name)
            if not preset:
                log_event(addr, user_for_log, cmd, name, False, "Not found")
                send_line(connstream, {"ok": False, "error": "Not found"})
                return
            if not can_read(preset, session):
                log_event(addr, user_for_log, cmd, name, False, "Forbidden")
                send_line(connstream, {"ok": False, "error": "Forbidden"})
                return
            log_event(addr, user_for_log, cmd, name, True, "OK")
            send_line(connstream, {"ok": True, "preset": preset})
            return

        # PUT (create/update)
        if cmd == "PUT":
            programs = req.get("programs")
            if not isinstance(programs, list):
                log_event(addr, user_for_log, cmd, name, False, "programs not list")
                send_line(connstream, {"ok": False, "error": "programs must be a list"})
                return

            lock = lock_for(name)
            with lock:
                preset = load_preset_file(name)
                if preset:
                    if not can_write(preset, session):
                        log_event(addr, user_for_log, cmd, name, False, "Forbidden")
                        send_line(connstream, {"ok": False, "error": "Forbidden"})
                        return
                    created_at = preset.get("created_at") or now_iso()
                    owner = preset.get("owner")
                    acl = preset.get("acl") or {}
                else:
                    # new preset: owner = creator
                    created_at = now_iso()
                    owner = session["user"]
                    acl = {}

                new_data = {
                    "schema": 1,
                    "preset_name": name,
                    "owner": owner,
                    "acl": acl,
                    "created_at": created_at,
                    "updated_at": now_iso(),
                    "programs": programs,
                }
                save_preset_file(name, new_data)

            log_event(addr, user_for_log, cmd, name, True, f"count={len(programs)}")
            send_line(connstream, {"ok": True, "saved": name, "count": len(programs), "owner": owner})
            return

        # DELETE
        if cmd == "DELETE":
            lock = lock_for(name)
            with lock:
                preset = load_preset_file(name)
                if not preset:
                    log_event(addr, user_for_log, cmd, name, False, "Not found")
                    send_line(connstream, {"ok": False, "error": "Not found"})
                    return
                if not can_delete(preset, session):
                    log_event(addr, user_for_log, cmd, name, False, "Forbidden")
                    send_line(connstream, {"ok": False, "error": "Forbidden"})
                    return
                path = preset_path(name)
                if os.path.exists(path):
                    os.remove(path)

            log_event(addr, user_for_log, cmd, name, True, "Deleted")
            send_line(connstream, {"ok": True, "deleted": name})
            return

        # SHARE: owner/admin grants permission to another user
        # req: {"cmd":"SHARE","token":...,"name":"Preset","target":"Zehavit","perm":"read|write|none"}
        if cmd == "SHARE":
            target = (req.get("target") or "").strip()
            perm = (req.get("perm") or "").strip().lower()
            if perm not in ("read", "write", "none"):
                log_event(addr, user_for_log, cmd, name, False, "Bad perm")
                send_line(connstream, {"ok": False, "error": "perm must be read/write/none"})
                return
            if not target:
                log_event(addr, user_for_log, cmd, name, False, "Missing target")
                send_line(connstream, {"ok": False, "error": "Missing target"})
                return

            lock = lock_for(name)
            with lock:
                preset = load_preset_file(name)
                if not preset:
                    log_event(addr, user_for_log, cmd, name, False, "Not found")
                    send_line(connstream, {"ok": False, "error": "Not found"})
                    return
                # only owner/admin can share
                if session["role"] != "admin" and preset.get("owner") != session["user"]:
                    log_event(addr, user_for_log, cmd, name, False, "Forbidden")
                    send_line(connstream, {"ok": False, "error": "Forbidden"})
                    return

                acl = preset.get("acl") or {}
                if perm == "none": #remove given perms 
                    acl.pop(target, None) 
                else:
                    acl[target] = perm #"acl": {"bleh": "read"}
                preset["acl"] = acl
                preset["updated_at"] = now_iso()
                save_preset_file(name, preset)

            log_event(addr, user_for_log, cmd, name, True, f"{target}={perm}")
            send_line(connstream, {"ok": True, "shared": name, "target": target, "perm": perm})
            return

        log_event(addr, user_for_log, cmd, preset_for_log, False, "Unknown cmd")
        send_line(connstream, {"ok": False, "error": "Unknown cmd"})

    except Exception as e:
        log_event(addr, user_for_log, cmd_for_log, preset_for_log, False, str(e))
        try:
            send_line(connstream, {"ok": False, "error": str(e)})
        except Exception:
            pass
    finally:
        try:
            connstream.close()
        except Exception:
            pass

def main():
    # if users db empty, first user registers as admin (server enforces it)
    context = ssl.SSLContext(ssl.PROTOCOL_TLS_SERVER)
    context.load_cert_chain(certfile=SERVER_CERT, keyfile=SERVER_PRIVATE_KEY)

    ensure_server_storage()
    print(f"[SERVER] users_db={USERS_FILE} data_dir={DATA_DIR} log={LOG_FILE}")
    with socket.socket(socket.AF_INET, socket.SOCK_STREAM) as s:
        s.setsockopt(socket.SOL_SOCKET, socket.SO_REUSEADDR, 1)
        s.bind((HOST, PORT))
        s.listen(50)
        print(f"[SERVER] Listening on {HOST}:{PORT}")

        while True:
            conn, addr = s.accept()
            try:
                connstream = context.wrap_socket(conn, server_side=True)
            except ssl.SSLError as e:
                print(f"[SERVER] TLS handshake failed from {addr}: {e}")
                conn.close()
                continue
            except Exception as e:
                print(f"[SERVER] Unexpected accept/wrap error from {addr}: {e}")
                conn.close()
                continue
            t = threading.Thread(target=handle_client, args=(connstream, addr), daemon=True)
            t.start()

if __name__ == "__main__":
    main()
