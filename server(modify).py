import socket
import os
import struct
import hashlib

# Cấu hình Server
SERVER_IP = "0.0.0.0"
SERVER_PORT = 12345
TIMEOUT = 5  # Timeout chờ ACK cho từng gói con (đã giảm để phù hợp với sliding window)
FILE_LIST = "files.txt"

def compute_checksum(data):
    return hashlib.md5(data).hexdigest()  # Trả về chuỗi 32 ký tự hex

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

def send_chunk_part_sliding_window(sock, client_addr, filename, offset, size, part_id):
    """
    Đọc file từ offset với size byte, sau đó chia thành nhiều gói UDP nhỏ
    và gửi theo cơ chế sliding window.
    
    Header của mỗi gói được định nghĩa theo định dạng:
      - part_id: 4 byte (unsigned int)
      - sequence_number: 4 byte (unsigned int)
      - total_segments: 4 byte (unsigned int)
      - checksum: 32 byte (MD5 hex string của dữ liệu gói)
    """
    try:
        with open(filename, "rb") as f:
            f.seek(offset)
            chunk_data = f.read(size)
    except Exception as e:
        sock.sendto(f"ERROR: {str(e)}".encode(), client_addr)
        return

    # Cấu hình phân mảnh: xác định kích thước an toàn của gói UDP
    HEADER_FORMAT = "!III32s"  # part_id, sequence_number, total_segments, checksum
    HEADER_SIZE = struct.calcsize(HEADER_FORMAT)
    SAFE_UDP_SIZE = 1400     # Kích thước tối đa gói UDP an toàn
    DATA_SIZE = SAFE_UDP_SIZE - HEADER_SIZE

    total_segments = (len(chunk_data) + DATA_SIZE - 1) // DATA_SIZE

    # Tạo danh sách các gói (segment)
    segments = []
    for seq in range(total_segments):
        start = seq * DATA_SIZE
        end = start + DATA_SIZE
        segment_data = chunk_data[start:end]
        chksum = hashlib.md5(segment_data).hexdigest()  # 32 ký tự hex
        header = struct.pack(HEADER_FORMAT, part_id, seq, total_segments, chksum.encode())
        packet = header + segment_data
        segments.append(packet)

    # Cơ chế sliding window
    WINDOW_SIZE = 5
    base = 0        # Chỉ số gói đầu của cửa sổ
    next_seq = 0    # Chỉ số gói tiếp theo cần gửi
    acked = [False] * total_segments

    sock.settimeout(TIMEOUT)
    while base < total_segments:
        # Gửi tất cả các gói trong cửa sổ
        while next_seq < total_segments and next_seq < base + WINDOW_SIZE:
            sock.sendto(segments[next_seq], client_addr)
            next_seq += 1
        try:
            # Nhận ACK từ client: cấu trúc ACK gồm part_id và sequence_number (mỗi 4 byte)
            while True:
                ack_packet, _ = sock.recvfrom(1024)
                ack_part, ack_seq = struct.unpack("!II", ack_packet)
                if ack_part != part_id:
                    continue
                if ack_seq < total_segments:
                    acked[ack_seq] = True
                    # Trượt cửa sổ nếu các gói từ base đã được ACK
                    while base < total_segments and acked[base]:
                        base += 1
                    if base >= total_segments:
                        break
        except socket.timeout:
            # Nếu hết timeout, resend các gói chưa ACK trong cửa sổ
            for seq in range(base, min(base + WINDOW_SIZE, total_segments)):
                if not acked[seq]:
                    sock.sendto(segments[seq], client_addr)
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
                send_chunk_part_sliding_window(sock, client_addr, filename, offset, size, part_id)
            # Có thể mở rộng thêm các trường hợp xử lý khác (ví dụ: RESEND)
        except Exception as e:
            print(f"Error: {e}")
            continue

if __name__ == "__main__":
    main()
