import sys
import threading
import tkinter as tk
from tkinter import ttk, messagebox
from proxy import *
import keyring
import keyring.errors
import requests

VERSION = "1.0.0"

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

class MiddleMan(tk.Tk):
    def __init__(self):
        super().__init__()

        self.title("Proxy Chain Configuration")
        self.geometry("440x340")
        self.protocol("WM_DELETE_WINDOW", self.on_close)

        self.proxy_config = config
        self.connected = False
        self.username = None
        self.password = None
        self.server = None
        self.server_thread = None

        self.tabwidget = ttk.Notebook(self)
        self.tabwidget.pack(expand=True, fill="both")

        # Login tab
        self.login_frame = ttk.Frame(self.tabwidget, padding=12)
        self.tabwidget.add(self.login_frame, text="Login")

        self.username_label = ttk.Label(self.login_frame, text="Username:")
        self.username_label.pack(pady=5)
        self.username_entry = ttk.Entry(self.login_frame)
        self.username_entry.pack(pady=5)

        self.password_label = ttk.Label(self.login_frame, text="Password:")
        self.password_label.pack(pady=5)
        self.password_entry = ttk.Entry(self.login_frame, show="*")
        self.password_entry.pack(pady=5)

        self.error_label = ttk.Label(self.login_frame, text="", foreground="red")
        self.error_label.pack(pady=5)

        self.login_button = ttk.Button(self.login_frame, text="Login", command=self.handle_login)
        self.login_button.pack(pady=5)

        # Main tab
        self.main_frame = ttk.Frame(self.tabwidget, padding=12)
        self.tabwidget.add(self.main_frame, text="Main")

        self.proxy_status_label = ttk.Label(self.main_frame, text="Proxy status: Not connected")
        self.proxy_status_label.pack(pady=10)

        self.local_address_label = ttk.Label(self.main_frame, text=f"Local proxy: {LOCAL_HOST}:{LOCAL_PORT}")
        self.local_address_label.pack(pady=5)

        self.start_button = ttk.Button(self.main_frame, text="Start Proxy", command=self.start_proxy, state="disabled")
        self.start_button.pack(pady=5)

        self.stop_button = ttk.Button(self.main_frame, text="Stop Proxy", command=self.stop_proxy, state="disabled")
        self.stop_button.pack(pady=5)

        self.delete_credentials_button = ttk.Button(self.main_frame, text="Delete Credentials", command=self.delete_credentials)
        self.delete_credentials_button.pack(pady=10)

        # About Page
        self.about_frame = ScrollableFrame(self.tabwidget, padding=12)
        self.tabwidget.add(self.about_frame, text="About")
        self.about_title_label = ttk.Label(self.about_frame.scrollable_frame, text="About:", font=("Arial", 14, "bold"))
        self.about_title_label.pack(pady=10)
        self.used_packages_label = ttk.Label(self.about_frame.scrollable_frame, text="Used packages:", font=("Arial", 12, "bold"))
        self.used_packages_label.pack(pady=5)
        self.requests_label = ttk.Label(self.about_frame.scrollable_frame, text=f"requests: {requests.__version__}")
        self.requests_label.pack(pady=5)
        self.keysring_label = ttk.Label(self.about_frame.scrollable_frame, text=f"keyring: version info not available")
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
        self.load_credentials()

    def switch_page(self, page_name):
        for index in range(self.tabwidget.index("end")):
            if self.tabwidget.tab(index, "text") == page_name:
                self.tabwidget.select(index)
                return

    def load_credentials(self):
        if not NEEDS_AUTH:
            self.switch_page("Main")
            self.start_button.config(state="normal")
            return
        try:
            username = keyring.get_password(SERVICE, "username")
            password = keyring.get_password(SERVICE, "password")

            if username and password and self.test_connection(username, password):
                self.username = username
                self.password = password
                self.connected = True
                self.proxy_status_label.config(text="Upstream proxy: Connected")
                self.start_button.config(state="normal")
                self.switch_page("Main")
            else:
                self.switch_page("Login")

        except Exception:
            self.switch_page("Login")

    def test_connection(self, username, password):
        try:
            proxy_url = self.proxy_config.build_url(username, password)

            response = requests.get(
                "https://example.com/",
                proxies=None if BYPASS_PROXY else {"http": proxy_url, "https": proxy_url},
                timeout=10,
            )
            response.close()
            return response.status_code < 500

        except (requests.RequestException, ValueError):
            return False

    def handle_login(self):
        username = self.username_entry.get().strip()
        password = self.password_entry.get()

        if not username or not password:
            self.error_label.config(text="Enter both username and password.")
            return

        self.error_label.config(text="Checking upstream proxy...")
        self.update_idletasks()

        if not self.test_connection(username, password):
            self.error_label.config(text="Connection failed. Check credentials and proxy access.")
            return

        try:
            keyring.set_password(SERVICE, "username", username)
            keyring.set_password(SERVICE, "password", password)
        except Exception:
            self.error_label.config(text="Could not save credentials to the system keyring.")
            return

        self.username_entry.delete(0, tk.END)
        self.password_entry.delete(0, tk.END)
        self.username = username
        self.password = password
        self.connected = True

        self.proxy_status_label.config(text="Upstream proxy: Connected")
        self.start_button.config(state="normal")
        self.error_label.config(text="")
        self.switch_page("Main")

    def start_proxy(self):
        if not self.connected:

            if NEEDS_AUTH and (not self.username or not self.password):
                messagebox.showerror("Proxy", "Log in to the upstream proxy first.")
                return

        if self.server is not None:
            return

        try:
            server = LocalProxyServer((LOCAL_HOST, LOCAL_PORT), self.username, self.password)
        except OSError as exc:
            messagebox.showerror("Proxy", f"Could not start local proxy: {exc}")
            return

        self.server = server
        self.server_thread = threading.Thread(target=server.serve_forever, daemon=True)
        self.server_thread.start()

        self.proxy_status_label.config(text="Proxy status: Running")
        self.start_button.config(state="disabled")
        self.stop_button.config(state="normal")

    def stop_proxy(self):
        server = self.server
        if server is None:
            return

        self.server = None
        server.shutdown()
        server.server_close()

        self.proxy_status_label.config(text="Upstream proxy: Disconnected")
        self.start_button.config(state="normal")
        self.stop_button.config(state="disabled")

    def delete_credentials(self):
        if self.server is not None:
            self.stop_proxy()

        if not messagebox.askyesno("Delete Credentials", "Delete the saved upstream proxy credentials?"):
            return

        for account in ("username", "password"):
            try:
                keyring.delete_password(SERVICE, account)
            except keyring.errors.PasswordDeleteError:
                pass
            except Exception as exc:
                messagebox.showerror("Keyring", f"Could not delete {account}: {exc}")
                return

        self.username = None
        self.password = None
        self.connected = False

        self.username_entry.delete(0, tk.END)
        self.password_entry.delete(0, tk.END)
        if NEEDS_AUTH:
            self.proxy_status_label.config(text="Proxy status: Not connected")
            self.start_button.config(state="disabled")
            self.switch_page("Login")

    def on_close(self):
        if self.server is not None:
            self.stop_proxy()
        self.destroy()


if __name__ == "__main__":
    MiddleMan().mainloop()
