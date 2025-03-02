# import tkinter as tk
# from tkinter import ttk, messagebox
# import socket
# import threading
# import struct
# import os
# import hashlib
# import time

# # Cấu hình chung
# SERVER_IP = "127.0.0.1"  # Cập nhật theo IP của server
# SERVER_PORT = 12345
# TOTAL_CHUNKS = 1         # Số kết nối/chunk theo yêu cầu đồ án
# CHUNK_TIMEOUT = 20       # Timeout cho việc nhận các segment của 1 chunk (điều chỉnh nếu cần)
# MAX_RETRIES = 10

# class DownloadClient:
#     def __init__(self, root):
#         self.root = root
#         self.root.title("UDP File Downloader")
#         self.root.geometry("600x500")

#         ttk.Label(root, text="Available Files:", font=("Arial", 12)).pack(pady=5)
#         self.file_listbox = tk.Listbox(root, height=10, selectmode=tk.SINGLE)
#         self.file_listbox.pack(fill=tk.BOTH, padx=10, pady=5, expand=True)

#         # Nút cập nhật file list
#         self.refresh_button = ttk.Button(root, text="Refresh List", command=self.get_file_list)
#         self.refresh_button.pack(pady=5)

#         # Nút download file được chọn
#         self.download_button = ttk.Button(root, text="Download Selected", command=self.start_download)
#         self.download_button.pack(pady=5)

#         self.periodic_file_list_update()
#         self.root.bind("<Control-c>", self.handle_ctrl_c)
#         self.get_file_list()

#     def periodic_file_list_update(self):
#         self.get_file_list()
#         self.root.after(5000, self.periodic_file_list_update)

#     def handle_ctrl_c(self, event):
#         self.root.quit()

#     def update_file_list(self, file_list):
#         self.file_listbox.delete(0, tk.END)
#         for f in file_list:
#             if f.strip():
#                 self.file_listbox.insert(tk.END, f.strip())

#     def get_file_list(self):
#         def worker():
#             try:
#                 sock = socket.socket(socket.AF_INET, socket.SOCK_DGRAM)
#                 sock.settimeout(5)
#                 sock.sendto(b"LIST", (SERVER_IP, SERVER_PORT))
#                 data, _ = sock.recvfrom(4096)
#                 file_list = data.decode().split("\n")
#                 self.root.after(0, lambda: self.update_file_list(file_list))
#                 sock.close()
#             except Exception as e:
#                 err = str(e)
#                 self.root.after(0, lambda: messagebox.showerror("Error", f"Failed to get file list: {err}"))
#         threading.Thread(target=worker, daemon=True).start()

#     def compute_checksum(self, data):
#         return hashlib.md5(data).hexdigest()

#     def start_download(self):
#         selected_file = self.file_listbox.get(tk.ACTIVE)
#         if not selected_file:
#             messagebox.showwarning("Warning", "Please select a file to download!")
#             return
#         threading.Thread(target=self.download_file, args=(selected_file,), daemon=True).start()

#     def download_file(self, filename):
#         # Yêu cầu kích thước file
#         sock = socket.socket(socket.AF_INET, socket.SOCK_DGRAM)
#         sock.settimeout(5)
#         sock.sendto(f"DOWNLOAD {filename}".encode(), (SERVER_IP, SERVER_PORT))
#         try:
#             data, _ = sock.recvfrom(1024)
#         except socket.timeout:
#             messagebox.showerror("Error", "Timeout while requesting file size!")
#             sock.close()
#             return
#         sock.close()

#         response = data.decode()
#         if response.startswith("ERROR:"):
#             messagebox.showerror("Error", response)
#             return

#         try:
#             file_size = int(response)
#         except ValueError:
#             messagebox.showerror("Error", f"Invalid file size received: {response}")
#             return

#         # Tính toán offset và kích thước cho từng chunk
#         part_size = file_size // TOTAL_CHUNKS
#         sizes = [part_size] * TOTAL_CHUNKS
#         remainder = file_size - part_size * TOTAL_CHUNKS
#         sizes[-1] += remainder
#         offsets = [i * part_size for i in range(TOTAL_CHUNKS)]

#         # Mở cửa sổ để hiển thị tiến độ tải cho từng chunk
#         progress_window = tk.Toplevel(self.root)
#         progress_window.title(f"Downloading {filename}")
#         chunk_labels = []
#         for i in range(TOTAL_CHUNKS):
#             lbl = ttk.Label(progress_window, text=f"Part {i+1}: 0%")
#             lbl.pack(pady=2)
#             chunk_labels.append(lbl)

#         results = [None] * TOTAL_CHUNKS

#         # def download_part(part_id, offset, size, progress_label):
#         #     attempts = 0
#         #     segments = {}  # Tích lũy các segment đã nhận được
#         #     expected_segments = None
#         #     HEADER_FORMAT = "!III32s"  # part_id, sequence_number, total_segments, checksum
#         #     HEADER_SIZE = struct.calcsize(HEADER_FORMAT)
#         #     while attempts < MAX_RETRIES:
#         #         sock_part = socket.socket(socket.AF_INET, socket.SOCK_DGRAM)
#         #         sock_part.settimeout(CHUNK_TIMEOUT)
#         #         # Gửi yêu cầu CHUNK đến server (vẫn gửi qua SERVER_PORT)
#         #         sock_part.sendto(f"CHUNK {filename} {offset} {size} {part_id}".encode(), (SERVER_IP, SERVER_PORT))
#         #         start_time = time.time()
#         #         while True:
#         #             try:
#         #                 packet, sender_addr = sock_part.recvfrom(65535)
#         #             except socket.timeout:
#         #                 break
#         #             if packet.startswith(b"ERROR:"):
#         #                 continue
#         #             if len(packet) < HEADER_SIZE:
#         #                 continue
#         #             try:
#         #                 header = packet[:HEADER_SIZE]
#         #                 part_id_recv, seq, tot_seg, chksum_bytes = struct.unpack(HEADER_FORMAT, header)
#         #             except struct.error:
#         #                 continue
#         #             if part_id_recv != part_id:
#         #                 continue
#         #             if expected_segments is None:
#         #                 expected_segments = tot_seg
#         #             data_segment = packet[HEADER_SIZE:]
#         #             computed_checksum = hashlib.md5(data_segment).hexdigest()
#         #             expected_checksum = chksum_bytes.decode()
#         #             if computed_checksum != expected_checksum:
#         #                 continue
#         #             if seq not in segments:
#         #                 segments[seq] = data_segment
#         #                 # Gửi ACK về sender_addr (địa chỉ của socket phụ server)
#         #                 ack_packet = struct.pack("!II", part_id, seq)
#         #                 sock_part.sendto(ack_packet, sender_addr)
#         #                 if expected_segments:
#         #                     progress = int((len(segments) / expected_segments) * 100)
#         #                     self.root.after(0, lambda p=progress, lbl=progress_label: lbl.config(text=f"Part {part_id+1}: {p}%"))
#         #             if expected_segments is not None and len(segments) == expected_segments:
#         #                 break
#         #             if time.time() - start_time > CHUNK_TIMEOUT:
#         #                 break
#         #         sock_part.close()
#         #         if expected_segments is not None and len(segments) == expected_segments:
#         #             break
#         #         attempts += 1
#         #         print(f"Retrying part {part_id}, attempt {attempts}")
#         #     if expected_segments is not None and len(segments) == expected_segments:
#         #         self.root.after(0, lambda lbl=progress_label: lbl.config(text=f"Part {part_id+1}: 100%"))
#         #         chunk_data = b"".join(segments[i] for i in sorted(segments))
#         #         return chunk_data
#         #     else:
#         #         self.root.after(0, lambda lbl=progress_label: lbl.config(text=f"Part {part_id+1}: Failed"))
#         #         return None
#         def download_part(part_id, offset, size, progress_label):
#             attempts = 0
#             segments = {}          # Tích lũy các segment đã nhận được
#             expected_segments = None
#             HEADER_FORMAT = "!III32s"  # part_id, sequence_number, total_segments, checksum
#             HEADER_SIZE = struct.calcsize(HEADER_FORMAT)

#             while attempts < MAX_RETRIES:
#                 sock_part = socket.socket(socket.AF_INET, socket.SOCK_DGRAM)
#                 sock_part.settimeout(CHUNK_TIMEOUT)
#                 sock_part.sendto(f"CHUNK {filename} {offset} {size} {part_id}".encode(), (SERVER_IP, SERVER_PORT))
#                 start_time = time.time()
#                 while True:
#                     try:
#                         packet, sender_addr = sock_part.recvfrom(65535)
#                     except socket.timeout:
#                         break  # Thoát vòng lặp inner nếu timeout
#                     if packet.startswith(b"ERROR:"):
#                         continue
#                     if len(packet) < HEADER_SIZE:
#                         continue
#                     try:
#                         header = packet[:HEADER_SIZE]
#                         part_id_recv, seq, tot_seg, chksum_bytes = struct.unpack(HEADER_FORMAT, header)
#                     except struct.error:
#                         continue
#                     if part_id_recv != part_id:
#                         continue
#                     if expected_segments is None:
#                         expected_segments = tot_seg
#                     data_segment = packet[HEADER_SIZE:]
#                     computed_checksum = hashlib.md5(data_segment).hexdigest()
#                     expected_checksum = chksum_bytes.decode()
#                     if computed_checksum != expected_checksum:
#                         continue
#                     if seq not in segments:
#                         segments[seq] = data_segment
#                         progress = int((len(segments) / expected_segments) * 100)
#                         self.root.after(0, lambda p=progress, lbl=progress_label: lbl.config(text=f"Part {part_id+1}: {p}%"))
#                         print(f"Part {part_id}: received seq {seq}. Total: {len(segments)}/{expected_segments}")
#                     if expected_segments is not None and len(segments) == expected_segments:
#                         break
#                     if time.time() - start_time > CHUNK_TIMEOUT:
#                         break
#                 sock_part.close()
#                 if expected_segments is not None and len(segments) == expected_segments:
#                     break
#                 attempts += 1
#                 print(f"Retrying part {part_id}, attempt {attempts}")
#             if expected_segments is not None and len(segments) == expected_segments:
#                 self.root.after(0, lambda lbl=progress_label: lbl.config(text=f"Part {part_id+1}: 100%"))
#                 chunk_data = b"".join(segments[i] for i in sorted(segments))
#                 return chunk_data
#             else:
#                 self.root.after(0, lambda lbl=progress_label: lbl.config(text=f"Part {part_id+1}: Failed"))
#                 return None


#         def thread_download(i):
#             data_part = download_part(i, offsets[i], sizes[i], chunk_labels[i])
#             results[i] = data_part

#         threads = []
#         for i in range(TOTAL_CHUNKS):
#             t = threading.Thread(target=thread_download, args=(i,))
#             threads.append(t)
#             t.start()
#         for t in threads:
#             t.join()

#         if any(r is None for r in results):
#             missing = [i for i, r in enumerate(results) if r is None]
#             messagebox.showerror("Error", f"Download failed! Missing parts: {missing}")
#             return

#         with open(filename, "wb") as outfile:
#             for i in range(TOTAL_CHUNKS):
#                 outfile.write(results[i])
#         messagebox.showinfo("Download Complete", f"File {filename} downloaded successfully!")

#     def compute_checksum(self, data):
#         return hashlib.md5(data).hexdigest()

# if __name__ == "__main__":
#     root = tk.Tk()
#     app = DownloadClient(root)
#     root.mainloop()
import tkinter as tk
from tkinter import ttk, messagebox
import socket
import threading
import struct
import os
import hashlib
import time

# Cấu hình chung
SERVER_IP = "127.0.0.1"  # Dùng localhost khi test
SERVER_PORT = 12345
TOTAL_CHUNKS = 100         # Số kết nối/chunk theo yêu cầu đồ án
CHUNK_TIMEOUT = 2       # Timeout cho việc nhận các segment của 1 chunk
MAX_RETRIES = 2000

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
        self.root.quit()

    def update_file_list(self, file_list):
        self.file_listbox.delete(0, tk.END)
        for f in file_list:
            if f.strip():
                self.file_listbox.insert(tk.END, f.strip())

    def get_file_list(self):
        def worker():
            try:
                sock = socket.socket(socket.AF_INET, socket.SOCK_DGRAM)
                sock.settimeout(5)
                sock.sendto(b"LIST", (SERVER_IP, SERVER_PORT))
                data, _ = sock.recvfrom(4096)
                file_list = data.decode().split("\n")
                self.root.after(0, lambda: self.update_file_list(file_list))
                print(f"[CLIENT] Received file list: {file_list}")
                sock.close()
            except Exception as e:
                err = str(e)
                self.root.after(0, lambda: messagebox.showerror("Error", f"Failed to get file list: {err}"))
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
        # Yêu cầu kích thước file
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

        print(f"[CLIENT] File '{filename}' size: {file_size}")
        # Tính toán offset và kích thước cho từng chunk
        part_size = file_size // TOTAL_CHUNKS
        sizes = [part_size] * TOTAL_CHUNKS
        remainder = file_size - part_size * TOTAL_CHUNKS
        sizes[-1] += remainder
        offsets = [i * part_size for i in range(TOTAL_CHUNKS)]

        # Mở cửa sổ để hiển thị tiến độ tải cho từng chunk
        progress_window = tk.Toplevel(self.root)
        progress_window.title(f"Downloading {filename}")
        chunk_labels = []
        for i in range(TOTAL_CHUNKS):
            lbl = ttk.Label(progress_window, text=f"Part {i+1}: 0%")
            lbl.pack(pady=2)
            chunk_labels.append(lbl)

        results = [None] * TOTAL_CHUNKS

        # def download_part(part_id, offset, size, progress_label):
        #     attempts = 0
        #     segments = {}          # Tích lũy các segment đã nhận được
        #     expected_segments = None
        #     HEADER_FORMAT = "!III32s"  # part_id, sequence_number, total_segments, checksum
        #     HEADER_SIZE = struct.calcsize(HEADER_FORMAT)

        #     while attempts < MAX_RETRIES:
        #         print(f"[CLIENT] Part {part_id}: Attempt {attempts+1}")
        #         sock_part = socket.socket(socket.AF_INET, socket.SOCK_DGRAM)
        #         sock_part.settimeout(CHUNK_TIMEOUT)
        #         sock_part.sendto(f"CHUNK {filename} {offset} {size} {part_id}".encode(), (SERVER_IP, SERVER_PORT))
        #         start_time = time.time()
        #         while True:
        #             try:
        #                 packet, sender_addr = sock_part.recvfrom(65535)
        #             except socket.timeout:
        #                 print(f"[CLIENT] Part {part_id}: Timeout waiting for packet")
        #                 break  # Thoát vòng lặp inner nếu timeout
        #             if packet.startswith(b"ERROR:"):
        #                 print(f"[CLIENT] Part {part_id}: Received error packet")
        #                 continue
        #             if len(packet) < HEADER_SIZE:
        #                 print(f"[CLIENT] Part {part_id}: Received packet too small")
        #                 continue
        #             try:
        #                 header = packet[:HEADER_SIZE]
        #                 part_id_recv, seq, tot_seg, chksum_bytes = struct.unpack(HEADER_FORMAT, header)
        #             except struct.error:
        #                 print(f"[CLIENT] Part {part_id}: Struct unpack error")
        #                 continue
        #             if part_id_recv != part_id:
        #                 print(f"[CLIENT] Part {part_id}: Received packet for different part {part_id_recv}")
        #                 continue
        #             if expected_segments is None:
        #                 expected_segments = tot_seg
        #                 print(f"[CLIENT] Part {part_id}: Expected segments = {expected_segments}")
        #             data_segment = packet[HEADER_SIZE:]
        #             computed_checksum = hashlib.md5(data_segment).hexdigest()
        #             expected_checksum = chksum_bytes.decode()
        #             if computed_checksum != expected_checksum:
        #                 print(f"[CLIENT] Part {part_id}: Checksum mismatch for seq {seq}")
        #                 continue
        #             if seq not in segments:
        #                 segments[seq] = data_segment
        #                 print(f"[CLIENT] Part {part_id}: Received seq {seq} (total {len(segments)}/{expected_segments})")
        #                 # Gửi ACK về sender_addr (địa chỉ của socket phụ server)
        #                 ack_packet = struct.pack("!II", part_id, seq)
        #                 sock_part.sendto(ack_packet, sender_addr)
        #                 print(f"[CLIENT] Part {part_id}: Sent ACK for seq {seq} to {sender_addr}")
        #                 progress = int((len(segments) / expected_segments) * 100)
        #                 self.root.after(0, lambda p=progress, lbl=progress_label: lbl.config(text=f"Part {part_id+1}: {p}%"))
        #             if expected_segments is not None and len(segments) == expected_segments:
        #                 break
        #             if time.time() - start_time > CHUNK_TIMEOUT:
        #                 print(f"[CLIENT] Part {part_id}: CHUNK_TIMEOUT reached after {time.time()-start_time:.2f}s")
        #                 break
        #         sock_part.close()
        #         if expected_segments is not None and len(segments) == expected_segments:
        #             break
        #         attempts += 1
        #         print(f"[CLIENT] Part {part_id}: Retrying, attempt {attempts}")
        #     if expected_segments is not None and len(segments) == expected_segments:
        #         self.root.after(0, lambda lbl=progress_label: lbl.config(text=f"Part {part_id+1}: 100%"))
        #         chunk_data = b"".join(segments[i] for i in sorted(segments))
        #         print(f"[CLIENT] Part {part_id}: Completed with {len(segments)}/{expected_segments} segments")
        #         return chunk_data
        #     else:
        #         self.root.after(0, lambda lbl=progress_label: lbl.config(text=f"Part {part_id+1}: Failed"))
        #         print(f"[CLIENT] Part {part_id}: Failed after {attempts} attempts")
        #         return None
        def download_part(part_id, offset, size, progress_label):
            attempts = 0
            segments = {}          # Tích lũy các segment đã nhận được
            expected_segments = None
            HEADER_FORMAT = "!III32s"  # part_id, sequence_number, total_segments, checksum
            HEADER_SIZE = struct.calcsize(HEADER_FORMAT)

            while attempts < MAX_RETRIES:
                print(f"[CLIENT] Part {part_id}: Attempt {attempts+1}")
                sock_part = socket.socket(socket.AF_INET, socket.SOCK_DGRAM)
                sock_part.settimeout(CHUNK_TIMEOUT)
                sock_part.sendto(f"CHUNK {filename} {offset} {size} {part_id}".encode(), (SERVER_IP, SERVER_PORT))
                start_time = time.time()
                while True:
                    try:
                        packet, sender_addr = sock_part.recvfrom(65535)
                    except socket.timeout:
                        print(f"[CLIENT] Part {part_id}: Timeout waiting for packet")
                        break  # Thoát vòng lặp inner nếu timeout
                    if packet.startswith(b"ERROR:"):
                        print(f"[CLIENT] Part {part_id}: Received error packet")
                        continue
                    if len(packet) < HEADER_SIZE:
                        print(f"[CLIENT] Part {part_id}: Received packet too small")
                        continue
                    try:
                        header = packet[:HEADER_SIZE]
                        part_id_recv, seq, tot_seg, chksum_bytes = struct.unpack(HEADER_FORMAT, header)
                    except struct.error:
                        print(f"[CLIENT] Part {part_id}: Struct unpack error")
                        continue
                    if part_id_recv != part_id:
                        print(f"[CLIENT] Part {part_id}: Received packet for different part {part_id_recv}")
                        continue
                    if expected_segments is None:
                        expected_segments = tot_seg
                        print(f"[CLIENT] Part {part_id}: Expected segments = {expected_segments}")
                    data_segment = packet[HEADER_SIZE:]
                    computed_checksum = hashlib.md5(data_segment).hexdigest()
                    expected_checksum = chksum_bytes.decode()
                    if computed_checksum != expected_checksum:
                        print(f"[CLIENT] Part {part_id}: Checksum mismatch for seq {seq}")
                        continue
                    if seq not in segments:
                        segments[seq] = data_segment
                        print(f"[CLIENT] Part {part_id}: Received seq {seq} (total {len(segments)}/{expected_segments})")
                        # Gửi ACK về sender_addr (địa chỉ của socket phụ server)
                        ack_packet = struct.pack("!II", part_id, seq)
                        sock_part.sendto(ack_packet, sender_addr)
                        print(f"[CLIENT] Part {part_id}: Sent ACK for seq {seq} to {sender_addr}")
                        progress = int((len(segments) / expected_segments) * 100)
                        self.root.after(0, lambda p=progress, lbl=progress_label: lbl.config(text=f"Part {part_id+1}: {p}%"))
                    if expected_segments is not None and len(segments) == expected_segments:
                        break
                    if time.time() - start_time > CHUNK_TIMEOUT:
                        print(f"[CLIENT] Part {part_id}: CHUNK_TIMEOUT reached after {time.time()-start_time:.2f}s")
                        break
                sock_part.close()
                if expected_segments is not None and len(segments) == expected_segments:
                    break
                attempts += 1
                print(f"[CLIENT] Part {part_id}: Retrying, attempt {attempts}")
                time.sleep(0.5)  # Thêm delay giữa các lần retry
            if expected_segments is not None and len(segments) == expected_segments:
                self.root.after(0, lambda lbl=progress_label: lbl.config(text=f"Part {part_id+1}: 100%"))
                chunk_data = b"".join(segments[i] for i in sorted(segments))
                print(f"[CLIENT] Part {part_id}: Completed with {len(segments)}/{expected_segments} segments")
                return chunk_data
            else:
                self.root.after(0, lambda lbl=progress_label: lbl.config(text=f"Part {part_id+1}: Failed"))
                print(f"[CLIENT] Part {part_id}: Failed after {attempts} attempts")
                return None
        def thread_download(i):
            data_part = download_part(i, offsets[i], sizes[i], chunk_labels[i])
            results[i] = data_part

        threads = []
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

        with open(filename, "wb") as outfile:
            for i in range(TOTAL_CHUNKS):
                outfile.write(results[i])
        messagebox.showinfo("Download Complete", f"File {filename} downloaded successfully!")

    def compute_checksum(self, data):
        return hashlib.md5(data).hexdigest()

if __name__ == "__main__":
    root = tk.Tk()
    app = DownloadClient(root)
    root.mainloop()
