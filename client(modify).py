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
CHUNK_TIMEOUT = 1        # Timeout cho việc nhận các segment của 1 chunk
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

        # Hàm download_part: nhận dữ liệu của 1 chunk được chia thành nhiều segment nhỏ theo sliding window
        # Header của mỗi segment: part_id (4 byte), sequence_number (4 byte),
        # total_segments (4 byte), checksum (32 byte) => tổng HEADER_SIZE = 44 byte
        def download_part(part_id, offset, size, progress_label):
            attempts = 0
            chunk_data = None
            HEADER_FORMAT = "!III32s"  # Định nghĩa header
            HEADER_SIZE = struct.calcsize(HEADER_FORMAT)
            while attempts < MAX_RETRIES and chunk_data is None:
                sock_part = socket.socket(socket.AF_INET, socket.SOCK_DGRAM)
                sock_part.settimeout(CHUNK_TIMEOUT)
                request = f"CHUNK {filename} {offset} {size} {part_id}"
                sock_part.sendto(request.encode(), (SERVER_IP, SERVER_PORT))
                segments = {}
                expected_segments = None
                start_time = time.time()
                while True:
                    try:
                        packet, _ = sock_part.recvfrom(65535)
                    except socket.timeout:
                        # Hết thời gian chờ, break để retry
                        break
                    if packet.startswith(b"ERROR:"):
                        print(f"Server error for part {part_id}: {packet.decode()}")
                        continue
                    if len(packet) < HEADER_SIZE:
                        print(f"Packet too small for part {part_id}")
                        continue
                    header = packet[:HEADER_SIZE]
                    part_id_recv, seq, tot_seg, chksum_bytes = struct.unpack(HEADER_FORMAT, header)
                    if part_id_recv != part_id:
                        continue
                    if expected_segments is None:
                        expected_segments = tot_seg
                    data_segment = packet[HEADER_SIZE:]
                    computed_checksum = hashlib.md5(data_segment).hexdigest()
                    expected_checksum = chksum_bytes.decode()
                    if computed_checksum != expected_checksum:
                        print(f"Checksum mismatch for part {part_id}, segment {seq}")
                        continue
                    # Lưu segment nếu chưa nhận
                    if seq not in segments:
                        segments[seq] = data_segment
                        # Gửi ACK cho segment (ACK gồm part_id và sequence_number)
                        ack_packet = struct.pack("!II", part_id, seq)
                        sock_part.sendto(ack_packet, (SERVER_IP, SERVER_PORT))
                        # Cập nhật tiến độ (dựa trên số segment nhận được)
                        if expected_segments:
                            progress = int((len(segments) / expected_segments) * 100)
                            self.root.after(0, lambda p=progress, lbl=progress_label: lbl.config(text=f"Part {part_id+1}: {p}%"))
                    if expected_segments is not None and len(segments) == expected_segments:
                        break
                    if time.time() - start_time > CHUNK_TIMEOUT:
                        break
                sock_part.close()
                if expected_segments is not None and len(segments) == expected_segments:
                    # Ghép các segment theo thứ tự tăng dần của sequence number
                    chunk_data = b"".join(segments[i] for i in sorted(segments))
                else:
                    attempts += 1
                    print(f"Retrying part {part_id}, attempt {attempts}")
            if chunk_data is None:
                self.root.after(0, lambda lbl=progress_label: lbl.config(text=f"Part {part_id+1}: Failed"))
                return None
            else:
                self.root.after(0, lambda lbl=progress_label: lbl.config(text=f"Part {part_id+1}: 100%"))
                return chunk_data

        threads = []
        results = [None] * TOTAL_CHUNKS
        def thread_download(i):
            data_part = download_part(i, offsets[i], sizes[i], chunk_labels[i])
            results[i] = data_part

        for i in range(TOTAL_CHUNKS):
            t = threading.Thread(target=thread_download, args=(i,))
            threads.append(t)
            t.start()
        for t in threads:
            t.join()

        if any(r is None for r in results):
            missing = [i for i, r in enumerate(results) if r is None]
            messagebox.showerror("Error", f"Download failed! Missing parts: {missing}")
            return

        # Ghi dữ liệu thành file hoàn chỉnh và hiển thị thông báo
        with open(filename, "wb") as outfile:
            for i in range(TOTAL_CHUNKS):
                outfile.write(results[i])
        messagebox.showinfo("Download Complete", f"File {filename} downloaded successfully!")

if __name__ == "__main__":
    root = tk.Tk()
    app = DownloadClient(root)
    root.mainloop()
