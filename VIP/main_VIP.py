# ===================================================================================
# === FILE: main_VIP.py (VIP VERSION: CLEAN ARCHITECTURE) ===
# ===================================================================================
import sys
import os
import time
import random
import threading
import atexit
import subprocess
import traceback
import pygame

_THIS_DIR = os.path.dirname(os.path.abspath(__file__))
_PROJECT_DIR = os.path.dirname(_THIS_DIR)
sys.path.insert(0, _THIS_DIR)
sys.path.insert(0, _PROJECT_DIR)

import config
import xiangqi

from game_state import GameState
from hardware_manager import HardwareManager
from input_handler import InputHandler
from tuongky_api import TuongKyAPI

# ==========================================
# 0. CHẾ ĐỘ & DỌN DẸP TIẾN TRÌNH CŨ
# ==========================================
_mode_label = '🛠️ DRY RUN (MOUSE & LOG)' if config.DRY_RUN else '🤖 REAL RUN (CAMERA & ROBOT)'
print(f"\n=== MODE: {_mode_label} ===")

def _kill_zombie_processes():
    pass

_kill_zombie_processes()

# ==========================================
# 1. KHỞI TẠO HỆ THỐNG CỐT LÕI
# ==========================================
pygame.init()
pygame.font.init()

from board_renderer import BoardRenderer, SCREEN_WIDTH, SCREEN_HEIGHT
screen = pygame.display.set_mode((SCREEN_WIDTH, SCREEN_HEIGHT))
pygame.display.set_caption(f"Xiangqi Robot VIP - { _mode_label }")
renderer = BoardRenderer(screen)

# Khởi tạo các module quản lý SRP
hw = HardwareManager(config, _PROJECT_DIR).initialize_all()

# Khởi tạo TuongKy API (chỉ khi có internet)
API_TOKEN = "eyJhbGciOiJIUzI1NiJ9.eyJzdWIiOiJzaW11bGF0aW9uMDAxIiwicm9sZSI6IlNJTVVMQVRJT04iLCJ0b2tlbklkIjoiMTlkYjRjMDEtNjk4My00MTU5LTllNzYtODk0NDU5YjJhMjM5IiwiaWF0IjoxNzczMTI3MTE5LCJleHAiOjE4MDQ2NjMxMTl9.cHQEzHS-SqrZqUZ9FRcJgUE_BzyxZ60iiy7xYzZPQOo"
api_client = TuongKyAPI(API_TOKEN)
if api_client.check_internet():
    api_client.create_match(red_name="Human Player", black_name="VIP Robot AI")
else:
    api_client = None  # Không có internet → dùng Moonfish local, không gọi API

state = GameState(allow_mouse_move=config.DRY_RUN, api_client=api_client)
input_mgr = InputHandler(state, hw)

def _cleanup_all():
    print("\n[CLEANUP] Đang dọn dẹp hệ thống...")
    # Gọi POST /end đồng bộ (synchronous) để đảm bảo request hoàn tất trước khi thoát
    if state.api_client and state.api_client.room_id and not state.game_over:
        room = state.api_client.room_id
        try:
            import requests as _req
            url = f"{state.api_client.base_url}/{room}/end"
            _req.post(url, json={"winner": "DRAW", "reason": "OTHER"},
                      headers=state.api_client.headers, timeout=5)
            print(f"[CLEANUP] ✅ Đã POST /end cho phòng {room}")
        except Exception as _e:
            print(f"[CLEANUP] ⚠️ Không gửi được POST /end: {_e}")
    hw.cleanup()
    try: pygame.quit()
    except: pass
    print("[CLEANUP] ✅ Xong!")

atexit.register(_cleanup_all)

# ==========================================
# 2. VÒNG LẶP CHÍNH
# ==========================================
running = True
clock = pygame.time.Clock()

print(f"\n[GAME] === GAME STARTED ===")
print(f"[FEN] {state.current_fen}")

hw.capture_baseline_if_needed(force_delay=1.0)

try:
    while running:
        # 2a. Vẽ khung hình
        renderer.draw_ui(state.get_render_state())
        renderer.draw_pieces(state.board)
        renderer.draw_highlight(state.last_move, state.selected_pos, state.invalid_flash_pos, state.invalid_flash_expiry)
        if state.game_over:
            renderer.draw_game_over(state.winner)

        # 2b. Xử lý Input
        for event in pygame.event.get():
            if event.type == pygame.QUIT:
                running = False
            elif event.type == pygame.KEYDOWN:
                input_mgr.handle_keyboard(event.key)
            elif event.type == pygame.MOUSEBUTTONDOWN:
                input_mgr.handle_mouse_down(event.pos[0], event.pos[1])

        # 2c. Camera Feed update
        if hw.cam_monitor is not None:
            key = hw.cam_monitor.update_display()
            if key == ord("q"): running = False
            elif key == ord(" "):  # SPACE bấm ở cửa sổ Camera
                input_mgr.handle_keyboard(pygame.K_SPACE)
            elif key == ord("z"):  # Z bấm ở cửa sổ Camera
                input_mgr.handle_keyboard(pygame.K_z)

        # 2d. Xử lý AI Turn (Non-blocking)
        if state.turn == "b" and not state.game_over:
            
            # --- Khởi động Thread suy nghĩ ---
            if not state.ai_thinking and state.ai_thread is None:
                board_snapshot = [row[:] for row in state.board]
                state.ai_thinking = True
                state.ai_think_start = time.time()
                
                def _ai_worker():
                    state.ai_result = hw.ai_ctrl.pick_move(board_snapshot, color="b")
                    
                state.ai_thread = threading.Thread(target=_ai_worker, daemon=True)
                state.ai_thread.start()
                print("[AI] 🧵 Thinking thread started...")

            # --- Chờ Thread xong ---
            elif state.ai_thinking and state.ai_thread is not None:
                if not state.ai_thread.is_alive():
                    state.ai_thinking = False
                    state.ai_thread = None
                    best = state.ai_result
                    state.ai_result = None
                    
                    # Chống Loop
                    if best:
                        try: s, d = best
                        except: s, d = best[0], best[1]
                        if len(state.move_history) > 8:
                            last_srcs = [m['src'] for m in state.move_history[-6:]]
                            if last_srcs.count(s) >= 3:
                                print(f"⚠️ AI LOOP DETECTED ({s}->{d}) -> PANIC MODE!")
                                valid_moves = xiangqi.find_all_valid_moves("b", state.board)
                                if valid_moves:
                                    best = random.choice(valid_moves)
                                    s, d = best

                    if best:
                        try: s, d = best
                        except: s, d = best[0], best[1]
                        state.move_history.append({"turn": "b", "src": s, "dst": d})
                        
                        cap_p = state.board[d[1]][d[0]]
                        is_cap = cap_p != "."
                        if is_cap: state.r_captured.append(cap_p)

                        robot_success = True
                        if not config.DRY_RUN:
                            if hw.robot.connected:
                                print(f"[AI] Robot executing move: {s}->{d}")
                                try:
                                    hw.robot.move_piece(s[0], s[1], d[0], d[1], is_cap)
                                except Exception as e:
                                    error_str = str(e)
                                    print(f"⚠️ Robot error: {error_str}")
                                    if "112" in error_str or "MoveCart" in error_str:
                                        print("✅ Light error — counting as successful.")
                                    else:
                                        print("❌ [CRITICAL] Robot critical error, stopping game.")
                                        robot_success = False
                                        time.sleep(2)
                            else:
                                print(f"\n{'='*50}")
                                print(f"🤖 AI đi: {state.board[s[1]][s[0]]} ({s[0]},{s[1]}) → ({d[0]},{d[1]}) {'ĂN' if is_cap else ''}")
                                print(f"👉 Hãy di quân này trên bàn thật, rồi bấm SPACE!")
                                print(f"{'='*50}\n")

                        if robot_success:
                            state.board, _ = xiangqi.make_temp_move(state.board, best)
                            state.last_move = best
                            state.turn = 'r'
                            state.update_fen_from_board()
                            print(f"[FEN] {state.current_fen}")
                            
                            if xiangqi.get_king_pos('r', state.board) is None:
                                state.handle_game_over('b')
                            else:
                                if hw.robot.connected:
                                    hw.capture_baseline_if_needed(force_delay=1.0)
                                    state.set_status("Your turn!", color=(0, 100, 180), duration=5.0)
                                else:
                                    # KHÔNG CLEAR BASELINE Ở ĐÂY để người dùng đỡ phải bấm SPACE 2 lần (1 cho AI, 1 cho mình)
                                    state.set_status(f"🤖 AI: ({s[0]},{s[1]})→({d[0]},{d[1]}) | Di quân rồi SPACE", color=(0, 80, 160), duration=30.0)
                                print("[GAME] Your turn...")
                    else:
                        print("[AI] No moves available -> AI Lost")
                        state.handle_game_over("r")

        pygame.display.flip()
        clock.tick(30)

except (KeyboardInterrupt, SystemExit):
    print("\n[MAIN] ⛔ Interrupted.")
except Exception as e:
    print(f"\n[MAIN] ❌ Unexpected error: {e}")
    traceback.print_exc()
