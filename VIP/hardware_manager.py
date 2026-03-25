import os
import time
import sys
import numpy as np
import cv2
import threading
from pathlib import Path

from robot_VIP import FR5Robot
from ai_controller import AIController
from camera_monitor import CameraMonitor
from snapshot_detector import SnapshotDetector as YoloSnapshotDetector
from calibrate_camera import calibrate_perspective_camera

try:
    from ultralytics import YOLO
except ImportError:
    pass

class HardwareManager:
    """Manages Robot, Camera (Vision), and AI Engine connections."""
    def __init__(self, config, project_dir):
        self.config = config
        self.project_dir = project_dir
        self.dry_run = config.DRY_RUN
        
        # Hardware instances
        self.robot = FR5Robot()
        self.engine = None
        self.ai_ctrl = None
        self.cap = None
        self.model = None
        self.cam_monitor = None
        self.yolo_detector = None
        self.perspective_path = Path(project_dir) / "VIP" / "perspective.npy"
        
        self.class_id_to_name = {
            0: "b_A", 1: "b_C", 2: "b_R", 3: "b_E", 4: "b_K", 5: "b_N", 6: "b_P",
            8: "r_A", 9: "r_C", 10: "r_R", 11: "r_E", 12: "r_K", 13: "r_N", 14: "r_P",
        }

    def initialize_all(self):
        """Khởi tạo toàn bộ Robot, AI, Camera theo đúng thứ tự."""
        self._init_robot()
        self._init_ai()
        self._init_camera()
        return self

    def _init_robot(self):
        if not self.dry_run:
            try:
                self.robot.connect()
                print("[MAIN] ✅ Robot kết nối thành công.")
            except Exception as e:
                print(f"⚠️ [MAIN] Robot connection error: {e}")
                print("   → Tiếp tục chạy KHÔNG có robot (camera + calibrate vẫn hoạt động)")
                self.robot.connected = False

            if self.robot.connected:
                try:
                    self.robot.go_to_home_chess()
                except Exception as e:
                    print(f"⚠️ [MAIN] go_to_home_chess lỗi: {e} → bỏ qua, robot vẫn CONNECTED")
        else:
            print("[MAIN] DRY_RUN: Skipping physical robot connection.")
            self.robot.connected = False

        self._calibrate_robot()

    def _calibrate_robot(self):
        print("\n--- ROBOT CALIBRATION ---")
        dst_pts_logic = np.array([[0, 0], [8, 0], [8, 9], [0, 9]], dtype=np.float32)
        try:
            if self.dry_run:
                src_pts_fake = np.array([[200, -100], [520, -100], [520, 260], [200, 260]], dtype=np.float32)
                self.robot.set_perspective_matrix(cv2.getPerspectiveTransform(dst_pts_logic, src_pts_fake))
            else:
                print("Reading coordinates from robot...")
                pts_data = []
                for i in range(1, 4+1):
                    err, data = self.robot.robot.GetRobotTeachingPoint(f"R{i}")
                    if err != 0:
                        raise Exception(f"Error getting teaching point R{i} (err={err})")
                    x, y = float(data[0]), float(data[1])
                    print(f"  ✅ R{i}: X={x:.3f}, Y={y:.3f}")
                    pts_data.append([x, y])

                src_pts_robot = np.array(pts_data, dtype=np.float32)
                M_rob = cv2.getPerspectiveTransform(dst_pts_logic, src_pts_robot)
                self.robot.set_perspective_matrix(M_rob)
                print("=== ROBOT CALIBRATION OK ===")
        except Exception as e:
            print(f"\n{'='*60}")
            print(f"❌ [CRITICAL] Robot calibration THẤT BẠI: {e}")
            self.robot.connected = False
            print("   Robot đã bị vô hiệu hóa. Game tiếp tục ở chế độ KHÔNG CÓ ROBOT.")

    def _init_ai(self):
        try:
            self.ai_ctrl = AIController(engine=None, config=self.config)
            print(f"✅ Moonfish AI Controller started! (think={getattr(self.config, 'PIKAFISH_THINK_MS', 2000)}ms)")
        except Exception as e:
            print(f"⚠️ Moonfish init error: {e}")
            self.ai_ctrl = None

    def _init_camera(self):
        if self.dry_run:
            return

        model_path = str(Path(self.project_dir) / "runs" / "detect" / "chess_vision" / "yolo26_occupancy_run" / "weights" / "best.pt")
        try:
            self.model = YOLO(model_path)
            print(f"✅ Model loaded: {model_path}")
        except Exception as e:
            print(f"⚠️ Warning: Could not load YOLO model: {e}")
            
        cam_index = int(os.environ.get("VIDEO_INDEX", str(self.config.VIDEO_SOURCE)))
        for idx in [cam_index] + [i for i in [0, 1, 2] if i != cam_index]:
            cap_try = cv2.VideoCapture(idx, cv2.CAP_DSHOW)
            if cap_try.isOpened():
                self.cap = cap_try
                print(f"✅ Camera opened at index {idx}")
                break
            else:
                cap_try.release()
                
        if self.cap is None:
            print("❌ Lỗi: Không mở được Camera!")
            sys.exit()
            
        self.cap.set(cv2.CAP_PROP_FRAME_WIDTH, 1280)
        self.cap.set(cv2.CAP_PROP_FRAME_HEIGHT, 720)

        # Calibrate Vision
        print("\n" + "=" * 60)
        print("  📐  CAMERA CALIBRATION — BẮT BUỘC KHI KHỞI ĐỘNG")
        print("=" * 60)
        if os.path.exists(str(self.perspective_path)):
            print(f"⚠️  Đã có file cũ: {self.perspective_path}")
            print("   Bấm 'S' để dùng lại hoặc calibrate lại bằng cách click 4 góc.")
        calibrate_perspective_camera(self.cap, str(self.perspective_path))
        
        if not os.path.exists(str(self.perspective_path)):
            print("❌ Chưa có perspective.npy! Không thể detect nước đi.")
            sys.exit()

        # Start Monitor
        if self.model is not None:
            self.cam_monitor = CameraMonitor(self.cap, self.model, self.perspective_path)
            self.cam_monitor.start()
            self.yolo_detector = YoloSnapshotDetector(self.perspective_path, self.class_id_to_name)
            print("[INIT] ✅ YoloSnapshotDetector initialized.")

    def cleanup(self):
        print("[CLEANUP] Đang dọn dẹp hardware...")
        if self.cam_monitor:
            try: self.cam_monitor.stop()
            except: pass
        if self.engine:
            try: self.engine.stop()
            except: pass
        if self.cap and self.cap.isOpened():
            try: self.cap.release()
            except: pass
        if self.robot and self.robot.connected and not self.dry_run:
            try: self.robot.robot.RobotEnable(0)
            except: pass

    # --- WRAPPER VISION UTILS ---
    def capture_baseline_if_needed(self, force_delay=0.0):
        if self.cam_monitor and self.yolo_detector:
            if force_delay > 0:
                time.sleep(force_delay)
            frame, detections = self.cam_monitor.get_fresh_snapshot()
            success = self.yolo_detector.capture_baseline(frame, detections)
            return success
        return False

    def clear_yolo_baseline(self):
        if self.yolo_detector:
            self.yolo_detector._baseline_occ = None

    def restore_yolo_baseline(self, occ, baseline_time):
        if self.yolo_detector and occ is not None:
            self.yolo_detector._baseline_occ = [row[:] for row in occ]
            self.yolo_detector._baseline_time = baseline_time
