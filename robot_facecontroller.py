import cv2
import mediapipe as mp
import numpy as np
import time
import threading
import os
import queue
from openni import openni2
from openni import _openni2 as c_api
from gtts import gTTS
import pygame

# Import bộ điều khiển khuôn mặt HTML gắn server WebSocket
from face_controller import RobotFaceController

# ──────────────────────────────────────────────────────────────
# CẤU HÌNH THAM SỐ TỐI ƯU TỐC ĐỘ PHẢN HỒI
# ──────────────────────────────────────────────────────────────
MAX_DISTANCE_MM = 2500  
STABLE_TIME_REQ = 3.5   
FORGET_TIME_REQ = 4.0   

# Độ phân giải màn hình hiển thị UI robot_face.html
SCREEN_WIDTH = 1024
SCREEN_HEIGHT = 600

# ──────────────────────────────────────────────────────────────
# Hệ thống TTS (Text-to-Speech) Bất đồng bộ (Non-blocking FPS)
# ──────────────────────────────────────────────────────────────
class AsyncTTS:
    def __init__(self):
        self.queue = queue.Queue()
        pygame.mixer.init()
        self.thread = threading.Thread(target=self._worker, daemon=True)
        self.thread.start()

    def _worker(self):
        while True:
            text, lang = self.queue.get()
            if text is None:
                break
            try:
                tts = gTTS(text=text, lang=lang, slow=False)
                temp_file = "temp_speech.mp3"
                tts.save(temp_file)
                
                pygame.mixer.music.load(temp_file)
                pygame.mixer.music.play()
                while pygame.mixer.music.get_busy():
                    time.sleep(0.1)
                
                pygame.mixer.music.unload()
                if os.path.exists(temp_file):
                    os.remove(temp_file)
            except Exception as e:
                print(f"[TTS Error] {e}")
            finally:
                self.queue.task_done()

    def speak(self, text, lang='vi'):
        self.queue.put((text, lang))

# ──────────────────────────────────────────────────────────────
# LUỒNG XỬ LÝ CHÍNH
# ──────────────────────────────────────────────────────────────
def main():
    face = RobotFaceController(auto_start=True, open_browser=True)
    tts = AsyncTTS()
    
    # Khởi tạo OpenNI cho Orbbec Astra+
    has_depth = False
    openni_paths = ["/usr/lib", "/usr/lib/x86_64-linux-gnu/OpenNI2/Drivers", "."]
    
    for path in openni_paths:
        try:
            openni2.initialize(path)
            dev = openni2.Device.open_any()
            depth_stream = dev.create_depth_stream()
            depth_stream.start()
            depth_stream.set_video_mode(c_api.OniVideoMode(
                pixelFormat=c_api.OniPixelFormat.ONI_PIXEL_FORMAT_DEPTH_1_MM, 
                resolutionX=640, resolutionY=480, fps=30
            ))
            has_depth = True
            print(f"[Vision] Kết nối thành công Orbbec Depth từ Driver: {path}")
            break
        except Exception:
            continue

    if not has_depth:
        print("[Vision Warning] Không load được OpenNI. Chuyển sang chế độ Giả lập Depth!")

    # Khởi tạo luồng RGB (Hạ cấu hình resolution tính toán một chút nếu cần để tăng max FPS)
    cap = cv2.VideoCapture(2)
    cap.set(cv2.CAP_PROP_FRAME_WIDTH, 640)
    cap.set(cv2.CAP_PROP_FRAME_HEIGHT, 480)

    # Khởi tạo MediaPipe Face Detection cực nhẹ (model_selection=0 tối ưu cho việc tracking liên tục)
    mp_face_detection = mp.solutions.face_detection
    face_detection = mp_face_detection.FaceDetection(min_detection_confidence=0.45, model_selection=0)

    # Quản lý trạng thái logic tương tác
    interaction_state = "IDLE"  
    target_start_time = 0
    last_seen_time = time.time()
    
    # Biến phục vụ thuật toán khóa mục tiêu cố định 1 người
    locked_target_center = None

    print("\n[System] Hệ thống AI Tracking đã cập nhật tăng tốc độ phản hồi mắt! Bấm 'q' để tắt.\n")

    while cap.isOpened():
        ret, frame = cap.read()
        if not ret:
            break

        # LẬT GƯƠNG HÌNH ẢNH để đồng bộ hướng liếc mắt với robot
        frame = cv2.flip(frame, 1)
        h, w, _ = frame.shape

        # Lấy dữ liệu bản đồ độ sâu (Depth Map) từ Orbbec
        depth_frame_data = None
        if has_depth:
            try:
                d_frame = depth_stream.read_frame()
                depth_frame_data = np.frombuffer(d_frame.get_buffer_as_uint16(), dtype=np.uint16).reshape(480, 640)
                depth_frame_data = cv2.flip(depth_frame_data, 1)
            except Exception:
                pass

        # Xử lý Face Detection bằng MediaPipe
        rgb_frame = cv2.cvtColor(frame, cv2.COLOR_BGR2RGB)
        results = face_detection.process(rgb_frame)

        detected_faces = []

        if results.detections:
            for idx, detection in enumerate(results.detections):
                bboxC = detection.location_data.relative_bounding_box
                xmin = int(bboxC.xmin * w)
                ymin = int(bboxC.ymin * h)
                box_w = int(bboxC.width * w)
                box_h = int(bboxC.height * h)
                
                cx, cy = xmin + box_w // 2, ymin + box_h // 2
                cx = max(0, min(cx, w - 1))
                cy = max(0, min(cy, h - 1))

                # Đo khoảng cách
                if has_depth and depth_frame_data is not None:
                    vung_depth = depth_frame_data[max(0, cy-5):min(h, cy+5), max(0, cx-5):min(w, cx+5)]
                    vung_depth = vung_depth[vung_depth > 0]
                    actual_depth = np.median(vung_depth) if len(vung_depth) > 0 else 0
                else:
                    actual_depth = 220000 / box_w  

                if 0 < actual_depth < MAX_DISTANCE_MM:
                    detected_faces.append({
                        'bbox': (xmin, ymin, box_w, box_h),
                        'center': (cx, cy),
                        'depth': actual_depth
                    })

        # ──────────────────────────────────────────────────────────────
        # THUẬT TOÁN KHÓA CỨNG MỤC TIÊU VÀ TẬP TRUNG NHÌN THEO
        # ──────────────────────────────────────────────────────────────
        current_time = time.time()
        active_face = None

        if detected_faces:
            if interaction_state in ["TALKING", "ANNOYED"] and locked_target_center is not None:
                best_match = None
                min_distance = 99999
                
                for face_info in detected_faces:
                    dist = np.linalg.norm(np.array(face_info['center']) - np.array(locked_target_center))
                    if dist < min_distance and dist < 160:  # Nới rộng ngưỡng di chuyển một chút để bám đuổi nhanh hơn
                        min_distance = dist
                        best_match = face_info
                
                if best_match is not None:
                    active_face = best_match
                else:
                    detected_faces.sort(key=lambda f: f['depth'])
                    active_face = detected_faces[0]
            else:
                detected_faces.sort(key=lambda f: f['depth'])
                active_face = detected_faces[0]

        # ──────────────────────────────────────────────────────────────
        # ĐẨY TỌA ĐỘ MẮT REAL-TIME SANG WEB VỚI ĐỘ TRỄ THẤP NHẤT
        # ──────────────────────────────────────────────────────────────
        if active_face is not None:
            xmin, ymin, box_w, box_h = active_face['bbox']
            cx, cy = active_face['center']
            current_depth = active_face['depth']
            
            last_seen_time = current_time
            locked_target_center = (cx, cy)

            # Vẽ khung debug camera màu xanh lá
            cv2.rectangle(frame, (xmin, ymin), (xmin + box_w, ymin + box_h), (0, 255, 0), 2)
            cv2.putText(frame, f"LOCKING EYE: {int(current_depth)}mm", (xmin, ymin - 10),
                        cv2.FONT_HERSHEY_SIMPLEX, 0.55, (0, 255, 0), 2)

            # Quy đổi hệ tọa độ camera -> Màn hình HTML UI
            eye_screen_x = int((cx / w) * SCREEN_WIDTH)
            eye_screen_y = int((cy / h) * SCREEN_HEIGHT)

            # Gửi gói tin điều khiển liếc mắt (Đồng bộ tức thời với luồng WebSocket)
            if face._server:
                face._server.send({
                    "action": "camera_track",
                    "clientX": eye_screen_x,
                    "clientY": eye_screen_y
                })

            # Logic đổi biểu cảm dựa theo khoảng cách tương tác
            if current_depth < 480:  
                if interaction_state != "ANNOYED":
                    interaction_state = "ANNOYED"
                    face.annoyed()
                    print("[Logic] Chuyển biểu cảm: Annoyed.")
                    tts.speak("Bạn đang đứng hơi sát tôi rồi đấy, làm ơn lùi lại một chút.")
            else:
                if interaction_state in ["IDLE", "BORED", "SAD_WAIT"]:
                    interaction_state = "LOCKING"
                    target_start_time = current_time
                    face.neutral()
                    print(f"[Logic] Đang bám theo mục tiêu...")

                elif interaction_state == "LOCKING":
                    elapsed = current_time - target_start_time
                    cv2.putText(frame, f"Verifying Target... {elapsed:.1f}s", (20, 40), 
                                cv2.FONT_HERSHEY_SIMPLEX, 0.7, (0, 215, 255), 2)
                    
                    if elapsed >= STABLE_TIME_REQ:  
                        interaction_state = "TALKING"
                        face.happy()  
                        print("[Logic Fixed] Đã khóa cứng người đối diện!")
                        tts.speak("Xin chào bạn! Chúng ta cùng trò chuyện nhé.")

                elif interaction_state == "ANNOYED":
                    interaction_state = "TALKING"
                    face.happy()
        else:
            # Xử lý mất dấu mục tiêu
            time_since_lost = current_time - last_seen_time

            if interaction_state == "TALKING":
                interaction_state = "SAD_WAIT"
                target_start_time = current_time 
                face.sad()
                print("[Logic] Đối tượng rời đi đột ngột -> Sad.")
                tts.speak("Ơ kìa, bạn đi đâu mất rồi?")

            elif interaction_state == "SAD_WAIT":
                countdown = FORGET_TIME_REQ - (current_time - target_start_time)
                cv2.putText(frame, f"Robot is sad... {max(0.0, countdown):.1f}s", (20, 40), 
                            cv2.FONT_HERSHEY_SIMPLEX, 0.7, (255, 0, 0), 2)
                
                if countdown <= 0:
                    interaction_state = "IDLE"
                    face.neutral()
                    print("[Logic] Quay về Neutral.")
                    locked_target_center = None

            elif interaction_state in ["IDLE", "LOCKING", "ANNOYED"]:
                if time_since_lost > 15.0: 
                    if interaction_state != "BORED":
                        interaction_state = "BORED"
                        face.bored()
                        print("[Logic] Robot đi ngủ (Bored)...")
                else:
                    cv2.putText(frame, f"Searching... {time_since_lost:.1f}s", (20, 40), 
                                cv2.FONT_HERSHEY_SIMPLEX, 0.7, (255, 255, 255), 2)

        # Show camera monitor
        cv2.putText(frame, f"STATE: {interaction_state}", (20, 450), cv2.FONT_HERSHEY_SIMPLEX, 0.8, (255, 255, 0), 2)
        cv2.imshow("Orbbec Robot Vision (Tracking Active)", frame)
        
        if cv2.waitKey(1) & 0xFF == ord('q'):
            break

    cap.release()
    if has_depth:
        depth_stream.stop()
        openni2.unload()
    cv2.destroyAllWindows()

if __name__ == "__main__":
    main()