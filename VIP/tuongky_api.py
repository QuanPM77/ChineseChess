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
        self._lock = threading.Lock()

    def create_match(self, red_name="VIP Robot", black_name="Human Player"):
        """Creates a match in a separate thread, but realistically we need room_id soon."""
        def _task():
            payload = {
                "redPlayerName": red_name,
                "blackPlayerName": black_name,
                "redPlayerAvatar": "https://robot-open-day.test/robot.png",
                "blackPlayerAvatar": "https://robot-open-day.test/human.png"
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
        # Optionally wait briefly if we desperately need the room ID to be ready right away
        # time.sleep(1)

    def send_fen(self, fen):
        """Sends FEN asynchronously."""
        with self._lock:
            room = self.room_id
        if not room:
            print("[API] ⚠️ No Room ID yet, cannot send FEN!")
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
        """Ends the match asynchronously."""
        with self._lock:
            room = self.room_id
        if not room:
            return

        def _task():
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

        threading.Thread(target=_task, daemon=True).start()
