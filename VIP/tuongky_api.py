import requests
import threading
import time

class TuongKyAPI:
    def __init__(self, token):
        self.token = token
        self.base_url = "https://tuongkydaisu.com/api/simulation/matches"
        self.headers = {
            "Authorization": f"Bearer {self.token}",
            "Content-Type": "application/json"
        }
        self.room_id = None
        self.online = False  # Trạng thái kết nối internet
        self._lock = threading.Lock()

    def check_internet(self):
        """Kiểm tra internet bằng cách ping tới tuongkydaisu.com.
        
        Returns:
            True nếu có internet, False nếu không.
        """
        try:
            res = requests.get("https://tuongkydaisu.com", timeout=3)
            self.online = True
            print("[API] ✅ Có kết nối internet — sẽ dùng TuongKyDaiSu API.")
            return True
        except Exception:
            self.online = False
            print("[API] ⚠️ Không có internet — sẽ dùng Moonfish engine local.")
            return False

    def create_match(self, red_name="Human Player", black_name="VIP Robot AI"):
        """Tạo match trên server. Nếu không có internet thì bỏ qua."""
        if not self.online:
            return

        def _task():
            payload = {
                "redPlayerName": red_name,
                "blackPlayerName": black_name,
                "redPlayerAvatar": "https://robot-open-day.test/human.png",
                "blackPlayerAvatar": "https://robot-open-day.test/robot.png"
            }
            try:
                res = requests.post(self.base_url, json=payload, headers=self.headers, timeout=5)
                res.raise_for_status()
                data = res.json()
                if data.get("success"):
                    with self._lock:
                        self.room_id = data["data"]["roomId"]
                    print(f"[API] ✅ Created Match, Room ID: {self.room_id}")
                else:
                    print(f"[API] ⚠️ Failed to create match: {data}")
            except Exception as e:
                print(f"[API] ❌ Error creating match: {e}")

        t = threading.Thread(target=_task, daemon=True)
        t.start()

    def send_fen(self, fen):
        """Gửi FEN lên server (async). Bỏ qua nếu không có internet."""
        if not self.online:
            return
            
        with self._lock:
            room = self.room_id
        if not room:
            return

        def _task():
            url = f"{self.base_url}/{room}/fen"
            try:
                res = requests.post(url, json={"fen": fen}, headers=self.headers, timeout=5)
                res.raise_for_status()
                print(f"[API] ✅ Sent FEN: {fen.split(' ')[0]}...")
            except Exception as e:
                print(f"[API] ❌ Error sending FEN: {e}")

        threading.Thread(target=_task, daemon=True).start()

    def end_match(self, winner="RED", reason="CHECKMATE"):
        """Kết thúc match trên server rồi xóa phòng (async). Bỏ qua nếu không có internet."""
        if not self.online:
            return
            
        with self._lock:
            room = self.room_id
        if not room:
            return

        def _task():
            # 1. Kết thúc trận đấu
            url = f"{self.base_url}/{room}/end"
            try:
                payload = {
                    "winner": winner,
                    "reason": reason
                }
                res = requests.post(url, json=payload, headers=self.headers, timeout=5)
                res.raise_for_status()
                print(f"[API] ✅ End Match: Winner={winner}, Reason={reason}")
            except Exception as e:
                print(f"[API] ❌ Error ending match: {e}")

            # 2. Xóa phòng sau khi kết thúc
            time.sleep(1)
            self._do_delete(room)

        threading.Thread(target=_task, daemon=True).start()

    def delete_match(self):
        """Xóa phòng trên server (async). Dùng khi cleanup hoặc thoát game."""
        if not self.online:
            return
            
        with self._lock:
            room = self.room_id
        if not room:
            return

        def _task():
            self._do_delete(room)

        threading.Thread(target=_task, daemon=True).start()

    def _do_delete(self, room_id):
        """Gọi DELETE API để xóa phòng."""
        url = f"{self.base_url}/{room_id}"
        try:
            res = requests.delete(url, headers=self.headers, timeout=5)
            res.raise_for_status()
            print(f"[API] ✅ Deleted Room: {room_id}")
            with self._lock:
                if self.room_id == room_id:
                    self.room_id = None
        except Exception as e:
            print(f"[API] ❌ Error deleting room: {e}")

