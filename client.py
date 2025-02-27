import tkinter as tk
from tkinter import ttk, messagebox
import socket
import threading
import struct
import os
import hashlib

# Cấu hình Server
SERVER_IP = "192.168.1.8"
SERVER_PORT = 12345
TOTAL_CHUNKS = 4  # Số phần chia ra

class DownloadClient:
    def __init__(self, root):
        self.root = root
        self.root.title("UDP File Downloader")
        self.root.geometry("500x400")

        ttk.Label(root, text="Available Files:", font=("Arial", 12)).pack(pady=5)
        self.file_listbox = tk.Listbox(root, height=10, selectmode=tk.SINGLE)
        self.file_listbox.pack(fill=tk.BOTH, padx=10, pady=5, expand=True)
        self.refresh_button = ttk.Button(root, text="Refresh List", command=self.get_file_list)
        self.refresh_button.pack(pady=5)
        self.download_button = ttk.Button(root, text="Download", command=self.start_download)
        self.download_button.pack(pady=5)
        self.progress = ttk.Progressbar(root, length=400, mode="determinate")
        self.progress.pack(pady=5)

        self.get_file_list()

    def get_file_list(self):
        """Gửi yêu cầu danh sách file từ Server và hiển thị lên giao diện"""
        try:
            sock = socket.socket(socket.AF_INET, socket.SOCK_DGRAM)
            sock.sendto(b"LIST", (SERVER_IP, SERVER_PORT))
            data, _ = sock.recvfrom(4096)
            file_list = data.decode().split("\n")
            self.file_listbox.delete(0, tk.END)
            for file in file_list:
                if file.strip():
                    self.file_listbox.insert(tk.END, file)
        except Exception as e:
            messagebox.showerror("Error", f"Failed to get file list: {e}")

    def start_download(self):
        """Bắt đầu tải file (trên luồng riêng)"""
        selected_file = self.file_listbox.get(tk.ACTIVE)
        if not selected_file:
            messagebox.showwarning("Warning", "Please select a file to download!")
            return
        threading.Thread(target=self.download_file, args=(selected_file,), daemon=True).start()

    def compute_checksum(self, data):
        """Tính checksum của chunk (dạng hex 32 ký tự)"""
        return hashlib.md5(data).hexdigest()

    def download_file(self, filename):
        """Tải file theo cách chia thành 4 phần song song"""
        self.progress["value"] = 0
        # Gửi yêu cầu DOWNLOAD để nhận file size
        sock = socket.socket(socket.AF_INET, socket.SOCK_DGRAM)
        sock.sendto(f"DOWNLOAD {filename}".encode(), (SERVER_IP, SERVER_PORT))
        data, _ = sock.recvfrom(1024)
        try:
            file_size = int(data.decode())
        except ValueError:
            messagebox.showerror("Error", "Invalid file size received!")
            return

        # Tính toán offset và size cho mỗi phần
        part_size = file_size // TOTAL_CHUNKS
        sizes = [part_size] * TOTAL_CHUNKS
        remainder = file_size - part_size * TOTAL_CHUNKS
        sizes[-1] += remainder  # Phần cuối nhận phần dư
        offsets = [i * part_size for i in range(TOTAL_CHUNKS)]

        downloaded_parts = [False] * TOTAL_CHUNKS

        def download_part(part_id, offset, size):
            sock_part = socket.socket(socket.AF_INET, socket.SOCK_DGRAM)
            sock_part.settimeout(5)
            # Gửi yêu cầu: "CHUNK filename offset size part_id"
            request = f"CHUNK {filename} {offset} {size} {part_id}"
            sock_part.sendto(request.encode(), (SERVER_IP, SERVER_PORT))
            try:
                packet, _ = sock_part.recvfrom(65535)  # Kích thước buffer lớn
                if len(packet) < 36:
                    print(f"Error: Packet too small for part {part_id}")
                    return
                recv_part_id = struct.unpack("!I", packet[:4])[0]
                checksum = packet[4:36].decode()
                data = packet[36:]
                if recv_part_id != part_id:
                    print(f"Error: Expected part {part_id}, but got {recv_part_id}")
                    return
                if self.compute_checksum(data) != checksum:
                    print(f"Checksum mismatch for part {part_id}")
                    return
                # Lưu phần dữ liệu vào file tạm
                with open(f"{filename}.part{part_id}", "wb") as f:
                    f.write(data)
                downloaded_parts[part_id] = True
                self.root.after(0, lambda: self.progress.step(100 / TOTAL_CHUNKS))
                # Gửi ACK cho server
                sock_part.sendto(struct.pack("!I", part_id), (SERVER_IP, SERVER_PORT))
                print(f"Received and ACK sent for part {part_id}")
            except socket.timeout:
                print(f"Timeout while downloading part {part_id}")
            finally:
                sock_part.close()

        threads = []
        for i in range(TOTAL_CHUNKS):
            t = threading.Thread(target=download_part, args=(i, offsets[i], sizes[i]))
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
