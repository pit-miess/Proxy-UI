import sys
import threading
import tkinter as tk
from tkinter import ttk, messagebox
from proxy import *
import json
from cryptography.fernet import Fernet, InvalidToken
import cryptography
import hashlib
import base64
import os
import requests

VERSION = "2.0.2"

class ScrollableFrame(ttk.Frame):
    def __init__(self, parent, *args, **kwargs):
        super().__init__(parent, *args, **kwargs)
        self.canvas = tk.Canvas(self, highlightthickness=0)
        self.scrollbar = ttk.Scrollbar(self, orient="vertical", command=self.canvas.yview)
        self.scrollable_frame = ttk.Frame(self.canvas, style="TFrame")

        self.scoll_window = self.canvas.create_window((0, 0), window=self.scrollable_frame, anchor="nw")
        self.canvas.configure(yscrollcommand=self.scrollbar.set)

        self.scrollable_frame.bind("<Configure>", lambda e: self.canvas.configure(scrollregion=self.canvas.bbox("all")))
        self.canvas.bind("<Configure>", lambda e: self.canvas.itemconfig(self.scoll_window, width=e.width))

        self.canvas.bind("<Enter>", self._bind_mousewheel)
        self.canvas.bind("<Leave>", self._unbind_mousewheel)

        self.canvas.pack(side="left", fill="both", expand=True, padx=0, pady=0)
        self.scrollbar.pack(side="right", fill="y")
    def _bind_mousewheel(self, event):
        self.canvas.bind_all("<MouseWheel>", self._on_mousewheel)
        self.canvas.bind_all("<Button-4>", self._on_mousewheel)
        self.canvas.bind_all("<Button-5>", self._on_mousewheel)
    def _unbind_mousewheel(self, event):
        self.canvas.unbind_all("<MouseWheel>")
        self.canvas.unbind_all("<Button-4>")
        self.canvas.unbind_all("<Button-5>")
    def _on_mousewheel(self, event):
        widget = event.widget
        if isinstance(widget, tk.Text):
            # get scrollposition of the text widget
            text_scroll_position = widget.yview()
            # scrolling up and widget at not the top of the text widget
            if event.delta > 0 and text_scroll_position[0] > 0:
                return
            # scrolling down and widget at not the bottom of the text widget
            if event.delta < 0 and text_scroll_position[1] < 1:
                return


        if event.delta: #macos windows
            modifier = -1 if sys.platform == "darwin" else -1
            self.canvas.yview_scroll(int(modifier * (event.delta / 120)), "units")
        elif event.num == 4: #linux scroll up
            self.canvas.yview_scroll(-1, "units")
        elif event.num == 5: #linux scroll down
            self.canvas.yview_scroll(1, "units")

current_dir = os.path.dirname(os.path.abspath(__file__))
data_path = os.path.join(current_dir, "proxies.dat")

class MiddleMan(tk.Tk):
    def __init__(self, bypass_proxy: bool = False):
        super().__init__()
        self.proxies = {}
        self.proxy_ui_elements = {}
        self.selected_proxy = None
        self.title("Proxy Chain Configuration")
        self.geometry("540x440")
        self.protocol("WM_DELETE_WINDOW", self.on_close)

        self.bypass_proxy = bypass_proxy
        self.proxy_config = config
        self.connected = False
        self.username = None
        self.password = None
        self.server = None
        self.server_thread = None

        self.tabwidget = ttk.Notebook(self)
        self.tabwidget.pack(expand=True, fill="both")


        # master login tab
        self.master_frame = ttk.Frame(self.tabwidget, padding=12)
        self.tabwidget.add(self.master_frame, text="Master")
        self.master_password_label = ttk.Label(self.master_frame, text="Master Password:")
        self.master_password_label.pack(pady=5)
        self.master_password_entry = ttk.Entry(self.master_frame, show="*")
        self.master_password_entry.pack(pady=5)
        self.master_password_entry.bind("<Return>", lambda event: self.handle_master_login())
        self.master_error_label = ttk.Label(self.master_frame, text="", foreground="red")
        self.master_error_label.pack(pady=5)
        self.master_login_button = ttk.Button(self.master_frame, text="Login", command=self.handle_master_login)
        self.master_login_button.pack(pady=5)


        # master registration tab
        self.register_frame = ttk.Frame(self.tabwidget, padding=12)
        self.tabwidget.add(self.register_frame, text="Register")
        self.register_password_label = ttk.Label(self.register_frame, text="Master Password:")
        self.register_password_label.pack(pady=5)
        self.register_password_entry = ttk.Entry(self.register_frame, show="*")
        self.register_password_entry.pack(pady=5)
        self.register_password_confirm_label = ttk.Label(self.register_frame, text="Confirm Password:")
        self.register_password_confirm_label.pack(pady=5)
        self.register_password_confirm_entry = ttk.Entry(self.register_frame, show="*")
        self.register_password_confirm_entry.pack(pady=5)
        self.register_password_confirm_entry.bind("<Return>", lambda event: self.handle_master_register())
        self.register_error_label = ttk.Label(self.register_frame, text="", foreground="red")
        self.register_error_label.pack(pady=5)
        self.register_button = ttk.Button(self.register_frame, text="Register", command=self.handle_master_register)
        self.register_button.pack(pady=5)

        # proxy selection tab
        self.proxy_selection_frame = ScrollableFrame(self.tabwidget, padding=12)
        self.tabwidget.add(self.proxy_selection_frame, text="Proxy Selection")
        self.new_proxy_button = ttk.Button(self.proxy_selection_frame.scrollable_frame, text="Add New Proxy", command=lambda: self.switch_page("New Proxy"))
        self.new_proxy_button.pack(pady=5)

        # new proxy tab/edit proxy tab
        self.login_frame = ttk.Frame(self.tabwidget, padding=12)
        self.tabwidget.add(self.login_frame, text="New Proxy")

        self.proxy_name_label = ttk.Label(self.login_frame, text="Proxy Name:")
        self.proxy_name_label.pack(pady=5)
        self.proxy_name_entry = ttk.Entry(self.login_frame)
        self.proxy_name_entry.pack(pady=5)
        self.proxy_frame = ttk.Frame(self.login_frame, padding=12)
        self.proxy_frame.pack(pady=10)
        self.proxy_type_dropdown = ttk.Combobox(self.proxy_frame, values=["HTTP", "HTTPS", "SOCKS5"], state="readonly")
        self.proxy_type_dropdown.set("HTTP")
        self.proxy_type_dropdown.pack(side="left", padx=5)
        self.proxy_address_entry = ttk.Entry(self.proxy_frame)
        self.proxy_address_entry.pack(side="left", padx=5)
        self.proxy_port_entry = ttk.Entry(self.proxy_frame, width=6)
        self.proxy_port_entry.pack(side="left", padx=5)
        self.needs_auth_var = tk.BooleanVar(value=True)
        self.needs_auth_checkbox = ttk.Checkbutton(self.proxy_frame, text="Needs Auth", variable=self.needs_auth_var, command=self.toggle_auth_fields)
        self.needs_auth_checkbox.pack(side="left", padx=5)
        self.auth_frame = ttk.Frame(self.login_frame, padding=12)
        self.auth_frame.pack(pady=10)
        self.username_label = ttk.Label(self.auth_frame, text="Username:")
        self.username_label.pack(pady=5)
        self.username_entry = ttk.Entry(self.auth_frame)
        self.username_entry.pack(pady=5)

        self.password_label = ttk.Label(self.auth_frame, text="Password:")
        self.password_label.pack(pady=5)
        self.password_entry = ttk.Entry(self.auth_frame, show="*")
        self.password_entry.pack(pady=5)

        self.error_label = ttk.Label(self.login_frame, text="", foreground="red")
        self.error_label.pack(pady=5)

        self.save_button = ttk.Button(self.login_frame, text="Save", command=self.save_proxy)
        self.save_button.pack(pady=5)


        # Main tab
        self.main_frame = ttk.Frame(self.tabwidget, padding=12)
        self.tabwidget.add(self.main_frame, text="Main")

        self.back_button = ttk.Button(self.main_frame, text="Back to Proxy Selection", command=self.back_to_proxy_selection)
        self.back_button.pack(pady=5, anchor="w")
        self.proxy_status_label = ttk.Label(self.main_frame, text="Proxy status: Not connected")
        self.proxy_status_label.pack(pady=10)

        self.local_address_label = ttk.Label(self.main_frame, text=f"Local proxy: N/A:N/A")
        self.local_address_label.pack(pady=5)

        self.start_button = ttk.Button(self.main_frame, text="Start Proxy", command=self.start_proxy, state="disabled")
        self.start_button.pack(pady=5)

        self.stop_button = ttk.Button(self.main_frame, text="Stop Proxy", command=self.stop_proxy, state="disabled")
        self.stop_button.pack(pady=5)

        # About Page
        self.about_frame = ScrollableFrame(self.tabwidget, padding=12)
        self.tabwidget.add(self.about_frame, text="About")
        self.about_title_label = ttk.Label(self.about_frame.scrollable_frame, text="About:", font=("Arial", 14, "bold"))
        self.about_title_label.pack(pady=10)
        self.used_packages_label = ttk.Label(self.about_frame.scrollable_frame, text="Used packages:", font=("Arial", 12, "bold"))
        self.used_packages_label.pack(pady=5)
        self.requests_label = ttk.Label(self.about_frame.scrollable_frame, text=f"requests: {requests.__version__}")
        self.requests_label.pack(pady=5)
        self.keysring_label = ttk.Label(self.about_frame.scrollable_frame, text=f"cryptography: {cryptography.__version__}")
        self.keysring_label.pack(pady=5)
        self.python_label = ttk.Label(self.about_frame.scrollable_frame, text=f"Python: {'.'.join(map(str, (sys.version_info.major, sys.version_info.minor, sys.version_info.micro)))}")
        self.python_label.pack(pady=5)
        self.author_label = ttk.Label(self.about_frame.scrollable_frame, text="Author:", font=("Arial", 12, "bold"))
        self.author_label.pack(pady=5)
        self.author_text = ttk.Label(self.about_frame.scrollable_frame, text="Pit Miess")
        self.author_text.pack(pady=5)
        self.license_label = ttk.Label(self.about_frame.scrollable_frame, text="License:", font=("Arial", 12, "bold"))
        self.license_label.pack(pady=5)
        self.license_text = tk.Text(self.about_frame.scrollable_frame, wrap="word", height=10, width=50)
        self.license_text.insert("1.0", """This software is licensed under a custom license.
Copyright (c) 2026 Pit Miess.
This is a copy of the LICENSE file.
Usage Guidelines:

Commercial use:
    - You can use this software freely for commercial purposes, including selling the software or using it in a commercial product or service if proper credit according to the credit section is given to the original author, and a link to the license is provided.

Educational, personal and non-commercial use:
    - You are free to use this software for educational purposes, personal projects, and non-commercial projects.
    - You must give appropriate credit to the original author according to the credit section, provide a link to the license, and indicate if changes were made if the software is redistributed, forked or modified.

Credit:
    - You must give appropriate credit to the original author, Pit Miess, and provide a link to the license when using or redistributing this software.
    - The credit must be visible and easily accessible, on the software itself, in the documentation, or on the website where the software is hosted.
    - The credit must be given even if the software is just running on a server or in the background, and not directly visible to the end user.
    - The License file must be included with the software when it is redistributed, forked or modified.

Contact:
    - Email: a23122160@gmail.com
    - GitHub: blockhunter0007

Disclaimer:
THE SOFTWARE IS PROVIDED "AS IS", WITHOUT WARRANTY OF ANY KIND, EXPRESS OR IMPLIED,
INCLUDING BUT NOT LIMITED TO THE WARRANTIES OF MERCHANTABILITY,
FITNESS FOR A PARTICULAR PURPOSE AND NONINFRINGEMENT.
IN NO EVENT SHALL THE AUTHORS OR COPYRIGHT HOLDERS BE LIABLE FOR ANY CLAIM, DAMAGES OR OTHER LIABILITY, 
WHETHER IN AN ACTION OF CONTRACT, TORT OR OTHERWISE, ARISING FROM, 
OUT OF OR IN CONNECTION WITH THE SOFTWARE OR THE USE OR OTHER DEALINGS IN THE SOFTWARE.""")
        self.license_text.config(state="disabled")
        self.license_text.pack(pady=5)
        self.verison_label = ttk.Label(self.about_frame.scrollable_frame, text=f"Version: {VERSION}")
        self.verison_label.pack(pady=5)
        if os.path.exists(data_path):
            self.switch_page("Master")
        else:
            self.switch_page("Register")
    def save_proxy(self):
        proxy_name = self.proxy_name_entry.get()
        if not proxy_name:
            self.error_label.config(text="Please enter a proxy name.")
            return
        self.proxies[proxy_name] = {
            "type": self.proxy_type_dropdown.get(),
            "address": self.proxy_address_entry.get(),
            "port": self.proxy_port_entry.get(),
            "needs_auth": self.needs_auth_var.get(),
            "username": self.username_entry.get(),
            "password": self.password_entry.get()
        }
        self.proxy_name_entry.delete(0, "end")
        self.proxy_address_entry.delete(0, "end")
        self.proxy_port_entry.delete(0, "end")
        self.username_entry.delete(0, "end")
        self.password_entry.delete(0, "end")
        self.needs_auth_var.set(True)
        self.error_label.config(text="")
        self.switch_page("Proxy Selection")
        self.reload_proxy_selection()
        self.save()

    def handle_master_login(self):
        with open(data_path, "rb") as f:
            data = f.read()
        password = self.master_password_entry.get()
        salt = data[:16]
        data = data[16:]
        key = hashlib.pbkdf2_hmac("sha256", password.encode(), salt, 100000)
        fernet = Fernet(base64.urlsafe_b64encode(key))
        try:
            data = fernet.decrypt(data)
        except InvalidToken:
            self.master_error_label.config(text="Invalid master password.")
            return
        data = json.loads(data.decode())
        self.password = password
        for proxy_name, proxy_data in data.items():
            self.proxies[proxy_name] = {
                "type": proxy_data["type"],
                "address": proxy_data["address"],
                "port": proxy_data["port"],
                "needs_auth": proxy_data["needs_auth"],
                "username": proxy_data.get("username"),
                "password": proxy_data.get("password")
            }
        self.reload_proxy_selection()
        self.master_password_entry.delete(0, "end")
        self.master_error_label.config(text="")
        self.switch_page("Proxy Selection")
    def reload_proxy_selection(self):
        for widget in self.proxy_selection_frame.scrollable_frame.winfo_children():
            widget.destroy()
        for proxy_name, proxy_data in self.proxies.items():
            frame = ttk.Frame(self.proxy_selection_frame.scrollable_frame, padding=12)
            frame.pack(pady=5, fill="x")
            label = ttk.Label(frame, text=f"{proxy_name}: {proxy_data['type']}://{proxy_data['address']}:{proxy_data['port']}")
            label.pack(side="left", padx=5)
            edit_button = ttk.Button(frame, text="Edit", command=lambda name=proxy_name: self.edit_proxy(name))
            edit_button.pack(side="left", padx=5)
            delete_button = ttk.Button(frame, text="Delete", command=lambda name=proxy_name: self.delete_proxy(name))
            delete_button.pack(side="left", padx=5)
            select = ttk.Button(frame, text="Select", command=lambda name=proxy_name: self.select_called(name))
            select.pack(side="left", padx=5)
        self.new_proxy_button = ttk.Button(self.proxy_selection_frame.scrollable_frame, text="Add New Proxy", command=lambda: self.switch_page("New Proxy"))
        self.new_proxy_button.pack(pady=5)
    def edit_proxy(self, proxy_name):
        proxy_data = self.proxies[proxy_name]
        self.proxy_name_entry.delete(0, "end")
        self.proxy_name_entry.insert(0, proxy_name)
        self.proxy_type_dropdown.set(proxy_data["type"])
        self.proxy_address_entry.delete(0, "end")
        self.proxy_address_entry.insert(0, proxy_data["address"])
        self.proxy_port_entry.delete(0, "end")
        self.proxy_port_entry.insert(0, proxy_data["port"])
        self.needs_auth_var.set(proxy_data["needs_auth"])
        self.username_entry.delete(0, "end")
        if proxy_data["username"]:
            self.username_entry.insert(0, proxy_data["username"])
        self.password_entry.delete(0, "end")
        if proxy_data["password"]:
            self.password_entry.insert(0, proxy_data["password"])
        self.switch_page("New Proxy")
    def delete_proxy(self, proxy_name):
        if messagebox.askyesno("Delete Proxy", f"Are you sure you want to delete the proxy '{proxy_name}'?"):
            del self.proxies[proxy_name]
            self.reload_proxy_selection()
        self.save()
    def handle_master_register(self):
        password = self.register_password_entry.get()
        confirm_password = self.register_password_confirm_entry.get()
        if password != confirm_password:
            self.register_error_label.config(text="Passwords do not match.")
            return
        salt = os.urandom(16)
        key = hashlib.pbkdf2_hmac("sha256", password.encode(), salt, 100000)
        fernet = Fernet(base64.urlsafe_b64encode(key))
        data = fernet.encrypt(json.dumps(self.proxies).encode())
        with open(data_path, "wb") as f:
            f.write(salt + data)
        self.register_password_entry.delete(0, "end")
        self.register_password_confirm_entry.delete(0, "end")
        self.register_error_label.config(text="")
        self.switch_page("Proxy Selection")
    def save(self):
        if not self.password:
            return
        salt = os.urandom(16)
        key = hashlib.pbkdf2_hmac("sha256", self.password.encode(), salt, 100000)
        fernet = Fernet(base64.urlsafe_b64encode(key))
        data = fernet.encrypt(json.dumps(self.proxies).encode())
        with open(data_path, "wb") as f:
            f.write(salt + data)
    def select_called(self, proxy_name):
        self.selected_proxy = proxy_name
        self.start_button.config(state="normal")
        self.local_address_label.config(text=f"Local proxy: {LOCAL_HOST}:{LOCAL_PORT}")
        self.switch_page("Main")
    def toggle_auth_fields(self):
        if self.needs_auth_var.get():
            self.error_label.pack_forget()
            self.save_button.pack_forget()
            for widget in (self.username_label, self.username_entry, self.password_label, self.password_entry):
                widget.pack(pady=5)
            self.error_label.pack(pady=5)
            self.save_button.pack(pady=5)
        else:
            for widget in (self.username_label, self.username_entry, self.password_label, self.password_entry):
                widget.pack_forget()
            self.save_button.pack_forget()
            self.error_label.pack_forget()
            self.error_label.pack(pady=5)
            self.save_button.pack(pady=5)
    def switch_page(self, page_name):
        for index in range(self.tabwidget.index("end")):
            if self.tabwidget.tab(index, "text") == page_name:
                self.tabwidget.select(index)
                return

    def test_connection(self, username, password, proxy_type, proxy_address, proxy_port, proxy_needs_auth):
        try:
            temp_config = ProxyConfig(
                host=proxy_address,
                port=proxy_port,
                scheme=proxy_type.lower(),
                needs_auth=proxy_needs_auth,
                bypass_proxy=self.bypass_proxy
            )
            proxy_url = temp_config.build_url(username, password)

            response = requests.get(
                "https://example.com/",
                proxies=None if self.bypass_proxy else {"http": proxy_url, "https": proxy_url},
                timeout=10,
            )
            response.close()
            success = response.status_code < 500
            if success:
                self.proxy_config = temp_config
                return True
            return False
        except (requests.RequestException, ValueError) as exc:
            print(f"Connection test error: {type(exc).__name__}: {exc}")
            return False




    def start_proxy(self, proxy_name = None):
        if proxy_name is None:
            proxy_name = self.selected_proxy
        if proxy_name is None:
            print("No proxy selected.")
            return
        proxy_data = self.proxies[proxy_name]
        p_type = proxy_data["type"]
        address = proxy_data["address"]
        port = proxy_data["port"]
        needs_auth = proxy_data["needs_auth"]
        username = proxy_data.get("username")
        password = proxy_data.get("password")
        print(f"Starting proxy with settings: {p_type}://{address}:{port}, needs_auth={needs_auth}, username={username}, password={'***' if password else None}")
        if not self.connected:
            if not p_type or not address or not port or needs_auth is None:
                messagebox.showerror("Proxy", "Enter the upstream proxy details first.")
                return
            if needs_auth and (not username or not password) and not self.bypass_proxy:
                messagebox.showerror("Proxy", "Log in to the upstream proxy first.")
                return

        if self.server is not None:
            print("Proxy server is already running.")
            return

        try:
            server = LocalProxyServer((LOCAL_HOST, LOCAL_PORT), username, password, p_type, address, port, needs_auth, bypass_proxy=self.bypass_proxy)
        except OSError as exc:
            messagebox.showerror("Proxy", f"Could not start local proxy: {exc}")
            return

        self.server = server
        self.server_thread = threading.Thread(target=server.serve_forever, daemon=True)
        self.server_thread.start()

        self.proxy_status_label.config(text="Proxy status: Running")
        self.start_button.config(state="disabled")
        self.stop_button.config(state="normal")
    def back_to_proxy_selection(self):
        if self.server is not None:
            self.stop_proxy()
        self.selected_proxy = None
        self.start_button.config(state="disabled")
        self.switch_page("Proxy Selection")
    def stop_proxy(self):
        server = self.server
        if server is None:
            return

        self.server = None
        server.shutdown()
        server.server_close()

        self.local_address_label.config(text="Local proxy: N/A:N/A")
        self.proxy_status_label.config(text="Upstream proxy: Disconnected")
        self.start_button.config(state="normal")
        self.stop_button.config(state="disabled")

    def on_close(self):
        if self.server is not None:
            self.stop_proxy()
        if self.proxies and self.password:
            self.save()
        self.destroy()
    def run(self):
        self.mainloop()


if __name__ == "__main__":
    args = sys.argv[1:]
    bypass_proxy = False
    for arg in args:
        if arg in ("-d", "--d", "-debug", "--debug"):
            bypass_proxy = True
    ui = MiddleMan(bypass_proxy=bypass_proxy)
    ui.run()
