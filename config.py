# =============================================================================
# === FILE: config.py (CẤU HÌNH TOÀN HỆ THỐNG) ===
# =============================================================================

# --- THÔNG SỐ ROBOT & BÀN CỜ ---
# (Các tọa độ này sẽ được ghi đè bởi quy trình Hiệu chỉnh tự động, nhưng cứ để làm gốc)
BOARD_ORIGIN_X = 0.0
BOARD_ORIGIN_Y = 0.0
CELL_SIZE = 60.0

# Tọa độ bãi chứa quân bị ăn (X, Y, Z)
CAPTURE_BIN_X = -226.123
CAPTURE_BIN_Y = 225.024
CAPTURE_BIN_Z = 291.68  # [QUAN TRỌNG] Độ cao khi thả quân vào thùng

# Độ cao an toàn (mm)
SAFE_Z  = 217.227  # Bay trên cao
PICK_Z  = 180.0   # Hạ xuống gắp (Đã nâng lên để tránh đập bàn, hạ từ từ)
PLACE_Z = 190.0   # Hạ xuống đặt

# Cấu hình Kẹp (Gripper) - Tùy chỉnh theo loại van của bạn
GRIPPER_CLOSE = 1
GRIPPER_OPEN = 0
MOVE_SPEED = 50

# Góc xoay của đầu Robot (Rx, Ry, Rz)
ROTATION = [89.658,-0.394, 174.148] 

# Kết nối Robot
ROBOT_IP = "192.168.58.2"
DRY_RUN = False # Đổi thành True nếu muốn test code mà không cần bật Robot

# Camera index (0 = built-in webcam, 1 = USB cam, etc.)
# main.py will auto-try 0, 1, 2 if this index fails.
VIDEO_SOURCE = 1

# --- THÔNG SỐ AI ---
AI_THINK_TIME = 10  # Time per move in seconds — AI gets 10s after subtracting TIME_BUFFER (0.5)
AI_DEPTH = 30          # Độ sâu mặc định (sẽ bị ghi đè bởi logic tự động)

# --- PIKAFISH ENGINE ---
# Tải từ: https://github.com/official-pikafish/Pikafish/releases
# Tải .nnue từ: https://pikafish.org
# Đặt cả 2 file vào thư mục: <project_root>/pikafish/
import os as _os
_PIKAFISH_DIR = _os.path.join(_os.path.dirname(_os.path.abspath(__file__)), 'pikafish')
PIKAFISH_EXE  = _os.path.join(_PIKAFISH_DIR, 'pikafish-avx2.exe')
PIKAFISH_NNUE = _os.path.join(_PIKAFISH_DIR, 'pikafish.nnue')
PIKAFISH_THINK_MS = 3000  # Thời gian suy nghĩ mỗi nước (milliseconds)
MOONFISH_MAX_DEPTH = 3    # Giới hạn độ sâu số nước đi Moonfish suy nghĩ (nếu chơi quá khó, có thể giảm xuống 3-5)

# Tọa độ về nhà (Home) để né Camera
IDLE_X = -72.027
IDLE_Y = 200.248
IDLE_Z = 278.586  
