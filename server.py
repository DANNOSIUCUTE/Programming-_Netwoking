import socket
import os
import struct
import hashlib

# Cấu hình Server
SERVER_IP = "0.0.0.0"
SERVER_PORT = 12345
CHUNK_SIZE = 1024  # Kích thước nhỏ của gói tin khi gửi (nếu cần chia nhỏ hơn)
TIMEOUT = 10  # Timeout chờ ACK
FILE_LIST = "files.txt"

def compute_checksum(data):
    return hashlib.md5(data).hexdigest()  # 32 ký tự hex

def send_file_list(sock, client_addr):
    """Gửi danh sách file có sẵn cho client"""
    if not os.path.exists(FILE_LIST):
        sock.sendto(b"ERROR: No file list found.", client_addr)
        return
    with open(FILE_LIST, "r") as f:
        files = f.read()
    sock.sendto(files.encode(), client_addr)

def send_file_size(sock, client_addr, filename):
    """Gửi kích thước file cho client"""
    if not os.path.exists(filename):
        sock.sendto(b"ERROR: File not found.", client_addr)
        return
    filesize = os.path.getsize(filename)
    sock.sendto(f"{filesize}".encode(), client_addr)

def send_chunk_part(sock, client_addr, filename, offset, size, part_id):
    """Đọc file từ offset, lấy size byte, đóng gói cùng checksum và gửi về client"""
    try:
        with open(filename, "rb") as f:
            f.seek(offset)
            data = f.read(size)
    except Exception as e:
        sock.sendto(f"ERROR: {str(e)}".encode(), client_addr)
        return
    
    # Tính checksum và đóng gói: 4 byte part_id, 32 byte checksum (utf-8) và dữ liệu
    checksum = compute_checksum(data)
    packet = struct.pack("!I", part_id) + checksum.encode() + data

    # Gửi gói tin và chờ ACK
    sock.sendto(packet, client_addr)
    sock.settimeout(TIMEOUT)
    try:
        ack, _ = sock.recvfrom(1024)
        if len(ack) != 4:
            print(f"Malformed ACK received for part {part_id}")
            return
        ack_id = struct.unpack("!I", ack)[0]
        if ack_id == part_id:
            print(f"Received ACK for part {part_id}")
        else:
            print(f"Error: Expected ACK {part_id}, but got {ack_id}")
    except socket.timeout:
        print(f"Timeout: Resending part {part_id}")
        sock.sendto(packet, client_addr)
    sock.settimeout(None)

def main():
    sock = socket.socket(socket.AF_INET, socket.SOCK_DGRAM)
    sock.bind((SERVER_IP, SERVER_PORT))
    print(f"Server listening on {SERVER_IP}:{SERVER_PORT}")

    while True:
        try:
            data, client_addr = sock.recvfrom(4096)
            message = data.decode()
            # Xử lý yêu cầu "LIST"
            if message == "LIST":
                send_file_list(sock, client_addr)
            # Xử lý yêu cầu "DOWNLOAD <filename>"
            elif message.startswith("DOWNLOAD"):
                _, filename = message.split(maxsplit=1)
                send_file_size(sock, client_addr, filename)
            # Xử lý yêu cầu "CHUNK <filename> <offset> <size> <part_id>"
            elif message.startswith("CHUNK"):
                parts = message.split()
                if len(parts) < 5:
                    sock.sendto(b"ERROR: Invalid CHUNK request", client_addr)
                    continue
                _, filename, offset_str, size_str, part_id_str = parts
                offset = int(offset_str)
                size = int(size_str)
                part_id = int(part_id_str)
                send_chunk_part(sock, client_addr, filename, offset, size, part_id)
            # (Có thể xử lý RESEND nếu cần)
        except Exception as e:
            print(f"Error: {e}")
            continue

if __name__ == "__main__":
    main()
