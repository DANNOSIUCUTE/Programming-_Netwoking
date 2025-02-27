import socket
import os
import struct
import hashlib
import math

# Cấu hình Server
SERVER_IP = "0.0.0.0"
SERVER_PORT = 12345
MAX_UDP_PAYLOAD = 60000  # Giới hạn payload cho mỗi gói tin
SEGMENT_HEADER_SIZE = 44  # 4 byte part_id, 4 byte segment_no, 4 byte total_segments, 32 byte checksum
TIMEOUT = 15  # Timeout chờ ACK
FILE_LIST = "files.txt"

def compute_checksum(data):
    return hashlib.md5(data).hexdigest()  # 32 ký tự hex

def send_file_list(sock, client_addr):
    if not os.path.exists(FILE_LIST):
        sock.sendto(b"ERROR: No file list found.", client_addr)
        return
    with open(FILE_LIST, "r") as f:
        files = f.read()
    sock.sendto(files.encode(), client_addr)

def send_file_size(sock, client_addr, filename):
    if not os.path.exists(filename):
        sock.sendto(b"ERROR: File not found.", client_addr)
        return
    filesize = os.path.getsize(filename)
    sock.sendto(f"{filesize}".encode(), client_addr)

def send_chunk_part(sock, client_addr, filename, offset, size, part_id):
    """
    Gửi phần (part) của file từ offset, với kích thước size.
    Nếu dữ liệu vượt quá giới hạn UDP cho phép, chia nhỏ thành các segment.
    Mỗi segment có header gồm:
      - 4 byte: part_id
      - 4 byte: segment_no
      - 4 byte: total_segments
      - 32 byte: checksum (MD5 hex) của dữ liệu segment
    Sau đó, gửi dữ liệu segment.
    Chờ ACK cho mỗi segment (ACK gồm 8 byte: part_id, segment_no).
    """
    try:
        with open(filename, "rb") as f:
            f.seek(offset)
            data = f.read(size)
    except Exception as e:
        sock.sendto(f"ERROR: {str(e)}".encode(), client_addr)
        return

    # Tạo socket riêng cho quá trình gửi phần này
    s = socket.socket(socket.AF_INET, socket.SOCK_DGRAM)
    s.settimeout(TIMEOUT)

    # Kiểm tra kích thước dữ liệu
    if len(data) <= MAX_UDP_PAYLOAD - SEGMENT_HEADER_SIZE:
        # Dữ liệu nhỏ, gửi 1 gói tin
        checksum = compute_checksum(data)
        header = struct.pack("!III", part_id, 0, 1)  # segment_no=0, total_segments=1
        packet = header + checksum.encode() + data
        s.sendto(packet, client_addr)
        try:
            ack, _ = s.recvfrom(1024)
            if len(ack) != 4:
                print(f"Malformed ACK received for part {part_id}")
            else:
                ack_id = struct.unpack("!I", ack)[0]
                if ack_id == part_id:
                    print(f"Received ACK for part {part_id}")
                else:
                    print(f"Error: Expected ACK {part_id}, but got {ack_id}")
        except socket.timeout:
            print(f"Timeout: Resending part {part_id}")
            s.sendto(packet, client_addr)
    else:
        # Dữ liệu lớn, chia thành các segment nhỏ
        max_data_per_segment = MAX_UDP_PAYLOAD - SEGMENT_HEADER_SIZE
        total_segments = math.ceil(len(data) / max_data_per_segment)
        print(f"Part {part_id}: Data length = {len(data)} bytes, will be sent in {total_segments} segments")
        for seg_no in range(total_segments):
            seg_offset = seg_no * max_data_per_segment
            seg_data = data[seg_offset: seg_offset + max_data_per_segment]
            seg_checksum = compute_checksum(seg_data)
            header = struct.pack("!III", part_id, seg_no, total_segments)
            packet = header + seg_checksum.encode() + seg_data
            # Gửi segment
            s.sendto(packet, client_addr)
            try:
                # Chờ ACK cho segment, ACK gồm 8 byte: part_id, seg_no
                ack, _ = s.recvfrom(1024)
                if len(ack) != 8:
                    print(f"Malformed segmented ACK received for part {part_id}, segment {seg_no}")
                    continue
                ack_part, ack_seg = struct.unpack("!II", ack)
                if ack_part == part_id and ack_seg == seg_no:
                    print(f"Received ACK for part {part_id}, segment {seg_no}")
                else:
                    print(f"Error: Expected ACK for part {part_id}, segment {seg_no} but got part {ack_part}, segment {ack_seg}")
                    continue
            except socket.timeout:
                print(f"Timeout: Resending part {part_id}, segment {seg_no}")
                s.sendto(packet, client_addr)
    s.close()

def main():
    sock = socket.socket(socket.AF_INET, socket.SOCK_DGRAM)
    sock.bind((SERVER_IP, SERVER_PORT))
    print(f"Server listening on {SERVER_IP}:{SERVER_PORT}")
    while True:
        try:
            data, client_addr = sock.recvfrom(4096)
            message = data.decode()
            if message == "LIST":
                send_file_list(sock, client_addr)
            elif message.startswith("DOWNLOAD"):
                _, filename = message.split(maxsplit=1)
                send_file_size(sock, client_addr, filename)
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
        except Exception as e:
            print(f"Error: {e}")
            continue

if __name__ == "__main__":
    main()
