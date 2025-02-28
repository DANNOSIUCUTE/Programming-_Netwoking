import tkinter as tk
from tkinter import ttk, messagebox
import socket
import threading
import struct
import os
import hashlib
import time

# Cấu hình Server và các hằng số
SERVER_IP = "192.168.1.8"  # Địa chỉ IP của server
SERVER_PORT = 12345
TOTAL_CHUNKS = 4         # Số kết nối/chunk theo yêu cầu đồ án
CHUNK_TIMEOUT = 15
MAX_RETRIES = 3

class DownloadClient:
    def __init__(self, root):
        self.root = root
        self.root.title("UDP File Downloader")
        self.root.geometry("600x500")

        ttk.Label(root, text="Available Files:", font=("Arial", 12)).pack(pady=5)
        self.file_listbox = tk.Listbox(root, height=10, selectmode=tk.SINGLE)
        self.file_listbox.pack(fill=tk.BOTH, padx=10, pady=5, expand=True)

        # Nút cập nhật file list
        self.refresh_button = ttk.Button(root, text="Refresh List", command=self.get_file_list)
        self.refresh_button.pack(pady=5)

        # Nút download file được chọn
        self.download_button = ttk.Button(root, text="Download Selected", command=self.start_download)
        self.download_button.pack(pady=5)

        self.periodic_file_list_update()
        self.root.bind("<Control-c>", self.handle_ctrl_c)

        self.get_file_list()

    def periodic_file_list_update(self):
        self.get_file_list()
        self.root.after(5000, self.periodic_file_list_update)

    def handle_ctrl_c(self, event):
        print("Ctrl+C pressed. Exiting gracefully.")
        self.root.quit()

    def update_file_list(self, file_list):
        self.file_listbox.delete(0, tk.END)
        for file in file_list:
            if file.strip():
                self.file_listbox.insert(tk.END, file)

    def get_file_list(self):
        def worker():
            try:
                sock = socket.socket(socket.AF_INET, socket.SOCK_DGRAM)
                sock.settimeout(5)
                sock.sendto(b"LIST", (SERVER_IP, SERVER_PORT))
                data, _ = sock.recvfrom(4096)
                file_list = data.decode().split("\n")
                self.root.after(0, lambda: self.update_file_list(file_list))
                sock.close()
            except Exception as e:
                self.root.after(0, lambda: messagebox.showerror("Error", f"Failed to get file list: {e}"))
        threading.Thread(target=worker, daemon=True).start()

    def compute_checksum(self, data):
        return hashlib.md5(data).hexdigest()

    def start_download(self):
        selected_file = self.file_listbox.get(tk.ACTIVE)
        if not selected_file:
            messagebox.showwarning("Warning", "Please select a file to download!")
            return
        threading.Thread(target=self.download_file, args=(selected_file,), daemon=True).start()

    def download_file(self, filename):
        # Mở cửa sổ mới để hiển thị tiến độ cho từng chunk của file download này
        progress_window = tk.Toplevel(self.root)
        progress_window.title(f"Downloading {filename}")
        chunk_labels = []
        for i in range(TOTAL_CHUNKS):
            lbl = ttk.Label(progress_window, text=f"Part {i+1}: 0%")
            lbl.pack(pady=2)
            chunk_labels.append(lbl)

        # Yêu cầu DOWNLOAD để nhận kích thước file
        sock = socket.socket(socket.AF_INET, socket.SOCK_DGRAM)
        sock.settimeout(5)
        sock.sendto(f"DOWNLOAD {filename}".encode(), (SERVER_IP, SERVER_PORT))
        try:
            data, _ = sock.recvfrom(1024)
        except socket.timeout:
            messagebox.showerror("Error", "Timeout while requesting file size!")
            sock.close()
            return
        sock.close()

        response = data.decode()
        if response.startswith("ERROR:"):
            messagebox.showerror("Error", response)
            return

        try:
            file_size = int(response)
        except ValueError:
            messagebox.showerror("Error", f"Invalid file size received: {response}")
            return

        # Tính toán offset và kích thước cho mỗi chunk
        part_size = file_size // TOTAL_CHUNKS
        sizes = [part_size] * TOTAL_CHUNKS
        remainder = file_size - part_size * TOTAL_CHUNKS
        sizes[-1] += remainder
        offsets = [i * part_size for i in range(TOTAL_CHUNKS)]
        downloaded_parts = [False] * TOTAL_CHUNKS

        def download_part(part_id, offset, size, progress_label):
            attempts = 0
            while attempts < MAX_RETRIES:
                sock_part = socket.socket(socket.AF_INET, socket.SOCK_DGRAM)
                sock_part.settimeout(CHUNK_TIMEOUT)
                request = f"CHUNK {filename} {offset} {size} {part_id}"
                sock_part.sendto(request.encode(), (SERVER_IP, SERVER_PORT))
                try:
                    received_packet, _ = sock_part.recvfrom(65535)
                    if received_packet.startswith(b"ERROR:"):
                        print(f"Server error for part {part_id}: {received_packet.decode()}")
                        attempts += 1
                        continue
                    if len(received_packet) < 36:
                        print(f"Error: Packet too small for part {part_id}")
                        attempts += 1
                        continue
                    recv_part_id = struct.unpack("!I", received_packet[:4])[0]
                    checksum = received_packet[4:36].decode()
                    data = received_packet[36:]
                    if recv_part_id != part_id:
                        print(f"Error: Expected part {part_id}, but got {recv_part_id}")
                        attempts += 1
                        continue
                    if self.compute_checksum(data) != checksum:
                        print(f"Checksum mismatch for part {part_id}")
                        attempts += 1
                        continue

                    # Cập nhật tiến độ từng chunk (giả lập 10 bước)
                    for step in range(10):
                        time.sleep(0.05)
                        progress = int((step + 1) * 10)
                        self.root.after(0, lambda p=progress, lbl=progress_label: lbl.config(text=f"Part {part_id+1}: {p}%"))
                    # Lưu dữ liệu vào file tạm
                    with open(f"{filename}.part{part_id}", "wb") as f:
                        f.write(data)
                    downloaded_parts[part_id] = True

                    # Gửi ACK về server
                    sock_part.sendto(struct.pack("!I", part_id), (SERVER_IP, SERVER_PORT))
                    print(f"Received and ACK sent for part {part_id}")
                    sock_part.close()
                    break
                except socket.timeout:
                    attempts += 1
                    print(f"Timeout while downloading part {part_id}, retrying... (Attempt {attempts}/{MAX_RETRIES})")
                finally:
                    sock_part.close()
            if attempts == MAX_RETRIES:
                print(f"Failed to download part {part_id} after {MAX_RETRIES} attempts.")
                self.root.after(0, lambda lbl=progress_label: lbl.config(text=f"Part {part_id+1}: Failed"))

        threads = []
        for i in range(TOTAL_CHUNKS):
            t = threading.Thread(target=download_part, args=(i, offsets[i], sizes[i], chunk_labels[i]))
            threads.append(t)
            t.start()
        for t in threads:
            t.join()

        if not all(downloaded_parts):
            missing = [i for i, done in enumerate(downloaded_parts) if not done]
            messagebox.showerror("Error", f"Download failed! Missing parts: {missing}")
            return

        self.merge_parts(filename)
        messagebox.showinfo("Download Complete", f"File {filename} downloaded successfully!")

    def merge_parts(self, filename):
        """Ghép các phần đã tải thành file hoàn chỉnh và xóa file tạm"""
        with open(filename, "wb") as outfile:
            for i in range(TOTAL_CHUNKS):
                part_filename = f"{filename}.part{i}"
                with open(part_filename, "rb") as infile:
                    outfile.write(infile.read())
                os.remove(part_filename)

if __name__ == "__main__":
    root = tk.Tk()
    app = DownloadClient(root)
    root.mainloop()
