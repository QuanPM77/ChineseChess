# ==================================
# === FILE: VIP/ai_controller.py ===
# === AI Controller — Moonfish Engine Wrapper ===
# ==================================
import sys
import os
import time
import traceback

_THIS_DIR = os.path.dirname(os.path.abspath(__file__))
_PROJECT_DIR = os.path.dirname(_THIS_DIR)
_MOONFISH_DIR = os.path.join(_PROJECT_DIR, 'moonfish', 'moonfish')

if _MOONFISH_DIR not in sys.path:
    sys.path.insert(0, _MOONFISH_DIR)

# Guard import: nếu moonfish engine chưa được clone đầy đủ thì module
# vẫn load được — AIController sẽ báo lỗi rõ ràng khi khởi tạo.
_MOONFISH_AVAILABLE = False
try:
    from moonfish import *
    import tools
    _MOONFISH_AVAILABLE = True
except ImportError as _e:
    print(f"[AI] ⚠️ Không thể import moonfish engine: {_e}")
    print(f"[AI]    Kiểm tra thư mục: {_MOONFISH_DIR}")
    print("[AI]    Gợi ý: chạy  git submodule update --init --recursive  rồi thử lại.")
from fen_utils import board_array_to_fen

class AIController:
    """Wrapper cho Moonfish engine (Pure Python), chạy trong thread riêng (non-blocking).
    
    Tương thích hoàn toàn (drop-in) với logic Pikafish cũ: nhận board, trả toạ độ.
    """

    def __init__(self, engine=None, config=None):
        """
        Args:
            engine: Tham số giữ lại để tương thích với signature khởi tạo cũ (có thể bỏ qua = None).
            config: module config (dùng PIKAFISH_THINK_MS).
        """
        if not _MOONFISH_AVAILABLE:
            raise RuntimeError(
                "Moonfish engine không có sẵn. "
                f"Hãy chạy:  git submodule update --init --recursive  "
                f"để populate thư mục {_MOONFISH_DIR}"
            )
        self.config = config
        self.searcher = Searcher()

    def pick_move(self, board_snapshot, color="b"):
        """Gọi Moonfish để lấy nước đi tốt nhất.

        Args:
            board_snapshot: bản sao board 10x9 tại thời điểm AI bắt đầu nghĩ
            color:          màu AI đang đánh ('b' = đen)

        Returns:
            (src, dst) tuple nếu tìm được nước đi form ((sc, sr), (dc, dr))
            None nếu thất bại.
        """
        try:
            think_ms = getattr(self.config, 'PIKAFISH_THINK_MS', 2000)
            
            # 1. Sinh FEN
            fen = board_array_to_fen(board_snapshot, color, 1)
            print(f"[AI] Moonfish bắt đầu suy nghĩ với FEN: {fen}")
            
            # 2. Parse Position
            pos = tools.parseFEN(fen)
            
            # 3. Chạy search trong giới hạn thời gian (chặn theo thời gian)
            start = time.time()
            movetime = think_ms / 1000.0
            
            # Đọc giới hạn số nước đi đệ quy (mặc định 12)
            max_depth = getattr(self.config, 'MOONFISH_MAX_DEPTH', 12)
            self.searcher.max_depth = max_depth

            for s_score in self.searcher._search(pos):
                if (s_score >= MATE_UPPER) or (s_score <= -MATE_UPPER): 
                    break
                if (time.time() - start) > movetime:
                    break
            
            # In ra độ sâu (số nước đi ahead) mà Moonfish đạt được trong khoảng thời gian vừa qua
            achieved_depth = self.searcher.depth
            print(f"[AI] Moonfish đã suy nghĩ trước {achieved_depth} nước cờ trong {time.time()-start:.2f}s.")
                    
            entry = self.searcher.tp_score.get((pos, self.searcher.depth, True))
            if entry and entry.lower == -MATE_UPPER:
                print("[AI] Moonfish dự đoán sẽ thua cờ (Bị chiếu bí), nhưng LUẬT cấm đầu hàng, AI sẽ đi tiếp nước tốt nhất có thể sinh tồn!")
                # return None # Bỏ dòng này để AI KHÔNG được đầu hàng
            
            m = self.searcher.tp_move.get(pos)
            if not m:
                print("[AI] ⚠️ Moonfish không tìm được nước đi hợp lệ!")
                return None
            
            # 4. Chuyển đổi tọa độ interval "i" của Moonfish thành (col, row) của VIP board
            # A0 ở Moonfish là 145 (cột a, hàng dưới cùng). VIP (0, 9) là góc trái dưới.
            def moonfish_to_vip(i):
                rank_internal, col = divmod(i - 145, 13)
                row = 9 + rank_internal
                return (col, row)
                
            src = moonfish_to_vip(m[0])
            dst = moonfish_to_vip(m[1])
            
            # Moonfish xoay bàn cờ 180° khi đánh Đen (parseFEN rotate)
            # → Tọa độ trả về ở hệ xoay, cần un-rotate về hệ tuyệt đối
            if color == "b":
                src = (8 - src[0], 9 - src[1])
                dst = (8 - dst[0], 9 - dst[1])
            
            result = (src, dst)
            print(f"[AI] Moonfish chỉ định: {result}")
            return result
            
        except Exception as e:
            print(f"[AI] ❌ Moonfish error: {e}")
            traceback.print_exc()
            return None
