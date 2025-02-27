import tkinter as tk
from tkinter import ttk, messagebox
import socket
import threading
import struct
import os
import hashlib
import math

# Cấu hình Server
SERVER_IP = "192.168.1.8"
SERVER_PORT = 12345
TOTAL_CHUNKS = 4  # Số phần chia file
# Phải khớp với server: MAX_UDP_PAYLOAD và HEADER_SIZE
MAX_UDP_PAYLOAD = 60000
SEGMENT_HEADER_SIZE = 44  # 4+4+4+32

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

        self.periodic_file_list_update()
        self.root.bind("<Control-c>", self.handle_ctrl_c)

        self.get_file_list()

    def periodic_file_list_update(self):
        self.get_file_list()
        self.root.after(5000, self.periodic_file_list_update)

    def handle_ctrl_c(self, event):
        print("Ctrl+C pressed. Exiting gracefully.")
        self.root.quit()

    def get_file_list(self):
        try:
            sock = socket.socket(socket.AF_INET, socket.SOCK_DGRAM)
            sock.sendto(b"LIST", (SERVER_IP, SERVER_PORT))
            data, _ = sock.recvfrom(4096)
            file_list = data.decode().split("\n")
            self.file_listbox.delete(0, tk.END)
            for file in file_list:
                if file.strip():
                    self.file_listbox.insert(tk.END, file)
            sock.close()
        except Exception as e:
            messagebox.showerror("Error", f"Failed to get file list: {e}")

    def start_download(self):
        selected_file = self.file_listbox.get(tk.ACTIVE)
        if not selected_file:
            messagebox.showwarning("Warning", "Please select a file to download!")
            return
        threading.Thread(target=self.download_file, args=(selected_file,), daemon=True).start()

    def compute_checksum(self, data):
        return hashlib.md5(data).hexdigest()

    def download_file(self, filename):
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

        # Chia file thành TOTAL_CHUNKS phần
        part_size = file_size // TOTAL_CHUNKS
        sizes = [part_size] * TOTAL_CHUNKS
        remainder = file_size - part_size * TOTAL_CHUNKS
        sizes[-1] += remainder
        offsets = [i * part_size for i in range(TOTAL_CHUNKS)]
        downloaded_parts = [False] * TOTAL_CHUNKS

        def download_part(part_id, offset, size):
            sock_part = socket.socket(socket.AF_INET, socket.SOCK_DGRAM)
            sock_part.settimeout(15)
            request = f"CHUNK {filename} {offset} {size} {part_id}"
            sock_part.sendto(request.encode(), (SERVER_IP, SERVER_PORT))
            
            segments = {}  # Lưu các segment theo segment_no
            total_segments = None

            while True:
                try:
                    packet, _ = sock_part.recvfrom(65535)
                except socket.timeout:
                    break
                if len(packet) < SEGMENT_HEADER_SIZE:
                    print(f"Error: Packet too small for part {part_id}")
                    continue
                # Giải mã header: 4 byte part_id, 4 byte segment_no, 4 byte total_segments, 32 byte checksum
                recv_part_id = struct.unpack("!I", packet[:4])[0]
                segment_no = struct.unpack("!I", packet[4:8])[0]
                total_seg = struct.unpack("!I", packet[8:12])[0]
                try:
                    checksum = packet[12:44].decode()
                except UnicodeDecodeError as e:
                    print(f"UnicodeDecodeError in part {part_id} segment {segment_no}: {e}")
                    continue
                seg_data = packet[44:]
                
                if recv_part_id != part_id:
                    print(f"Error: Expected part {part_id}, but got {recv_part_id}")
                    continue
                if self.compute_checksum(seg_data) != checksum:
                    print(f"Checksum mismatch for part {part_id} segment {segment_no}")
                    continue
                segments[segment_no] = seg_data
                # Gửi ACK cho segment (8 byte: part_id, segment_no)
                ack_packet = struct.pack("!II", part_id, segment_no)
                sock_part.sendto(ack_packet, (SERVER_IP, SERVER_PORT))
                print(f"Received segment {segment_no} for part {part_id}, ACK sent.")
                if total_segments is None:
                    total_segments = total_seg
                    print(f"Part {part_id} expects {total_segments} segments.")
                if total_segments is not None and len(segments) >= total_segments:
                    break
            sock_part.close()

            if total_segments is None or len(segments) < total_segments:
                missing = set(range(total_segments)) - set(segments.keys()) if total_segments is not None else "unknown"
                print(f"Timeout while downloading part {part_id}. Missing segments: {missing}")
                return
            try:
                part_data = b''.join(segments[i] for i in range(total_segments))
            except KeyError as e:
                print(f"Missing segment {e} for part {part_id}")
                return
            with open(f"{filename}.part{part_id}", "wb") as f:
                f.write(part_data)
            downloaded_parts[part_id] = True
            self.root.after(0, lambda: self.progress.step(100 / TOTAL_CHUNKS))
            print(f"Successfully downloaded part {part_id}")

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
