import socket
import json
import time
import threading
import random
import uuid
import argparse
import logging
import re
from queue import PriorityQueue, Empty
from collections import defaultdict, deque

# =========================================================
# SPACETIME NETWORKING DELUXE MOCKUP
# =========================================================

HOST_GROUND = "127.0.0.1"
PORT_GROUND = 5000

HOST_RELAY_UDP = "127.0.0.1"
PORT_RELAY_UDP = 5011

RELAY_ID = "SAT-LEO-01"

# -------------------------
# Logging Configuration
# -------------------------
logging.basicConfig(
    filename="network_log.txt",
    level=logging.INFO,
    format="%(asctime)s - %(message)s"
)

# -------------------------
# ANSI colors
# -------------------------
RESET = "\033[0m"
BOLD = "\033[1m"
DIM = "\033[2m"

RED = "\033[91m"
GREEN = "\033[92m"
YELLOW = "\033[93m"
BLUE = "\033[94m"
MAGENTA = "\033[95m"
CYAN = "\033[96m"
WHITE = "\033[97m"

BG_RED = "\033[41m"
BG_GREEN = "\033[42m"
BG_YELLOW = "\033[43m"
BG_BLUE = "\033[44m"
BG_MAGENTA = "\033[45m"
BG_CYAN = "\033[46m"

LOCK = threading.Lock()

def now_ts():
    return time.time()

def iso_now():
    return time.strftime("%H:%M:%S")

def get_tick_icon(tick: int) -> str:
    if not tick: return "⚪"
    icons = ["🔴", "🟠", "🟡", "🟢", "🔵", "🟣"]
    return icons[tick % len(icons)]

def color_for_state(state: str) -> str:
    return {
        "nominal": GREEN,
        "warning": YELLOW,
        "emergency": RED,
        "science": CYAN,
        "media": MAGENTA,
    }.get(state, WHITE)

def pri_label(priority: int) -> str:
    if priority >= 100:
        return "P0"
    if priority >= 60:
        return "P1"
    if priority >= 30:
        return "P2"
    return "P3"

def banner(title: str, color=BG_BLUE):
    line = f"{color}{WHITE}{BOLD}  {title}  {RESET}"
    print("\n" + line)

def log(prefix: str, message: str, color=WHITE):
    with LOCK:
        # พิมพ์ลง Terminal
        print(f"{DIM}[{iso_now()}]{RESET} {color}{BOLD}{prefix}{RESET} {message}")
        
        # ลบ ANSI Color Codes ออกก่อนเขียนลงไฟล์ text เพื่อให้อ่านง่าย
        clean_msg = re.sub(r'\x1b\[[0-9;]*m', '', message) if '\x1b' in message else message
        logging.info(f"[{prefix}] {clean_msg}")

def safe_json_send(sock: socket.socket, obj: dict):
    data = (json.dumps(obj) + "\n").encode("utf-8")
    sock.sendall(data)

# =========================================================
# Mission QoS
# =========================================================

class MissionQoSEngine:
    def classify(self, telemetry: dict) -> tuple[int, str]:
        state = telemetry["state"]
        msg_type = telemetry.get("msg_type", "telemetry")

        if state == "emergency":
            return 100, "P0_EMERGENCY_ALERT"
        if state == "warning":
            return 60, "P1_WARNING_TELEMETRY"
        if msg_type == "science":
            return 30, "P2_SCIENCE_DATA"
        if msg_type == "media":
            return 10, "P3_MEDIA_DATA"
        return 20, "P2_NOMINAL_TELEMETRY"

    def to_bundle(self, telemetry: dict) -> dict:
        priority, command = self.classify(telemetry)

        bundle_id = f"{telemetry['spacecraft_id']}-{telemetry['tick']}-{uuid.uuid4().hex[:6]}"
        created_at = now_ts()

        return {
            "bundle_id": bundle_id,
            "command": command,
            "priority": priority,
            "raw": telemetry,
            "timeline": [
                {
                    "stage": "CREATED",
                    "ts": created_at,
                    "node": telemetry["spacecraft_id"],
                }
            ],
            "retry_count": 0,
        }

# =========================================================
# Ground Station
# =========================================================

class GroundStation:
    def __init__(self):
        self.queue = PriorityQueue()
        self.metrics = {
            "received": 0,
            "delivered": 0,
            "acked": 0,
            "warnings": 0,
            "emergencies": 0,
            "avg_latency": 0.0,
            "latencies": deque(maxlen=200),
        }
        self.timeline_store = {}
        self.running = True
        self.received_count = 0        # -- ตัวนับจำนวน packet ที่ “รับเข้ามา”
        self.start_time = time.time()  # -- เก็บ เวลาที่เริ่มต้นระบบ

    def get_throughput(self):
        # คำนวณความเร็วในการส่ง/ประมวลผล packet ต่อวินาที
        elapsed = time.time() - self.start_time
        if elapsed == 0:
            return 0
        return self.metrics["delivered"] / elapsed

    def process_queue(self):
        banner("GROUND STATION PROCESSOR", BG_GREEN)
        while self.running:
            try:
                neg_priority, _, packet = self.queue.get(timeout=0.5)
            except Empty:
                continue

            priority = -neg_priority
            bundle = packet["bundle"]
            timeline = bundle.get("timeline", [])
            bundle_id = bundle["bundle_id"]
            raw = bundle["raw"]
            state = raw["state"]
            sc_id = raw["spacecraft_id"]
            relay_id = packet.get("relay_id", "UNKNOWN")

            # simulate processing time
            time.sleep(0.03)

            delivered_ts = now_ts()
            timeline.append({"stage": "DELIVERED", "ts": delivered_ts, "node": "GROUND"})
            timeline.append({"stage": "ACKED", "ts": delivered_ts, "node": "GROUND"})
            self.timeline_store[bundle_id] = timeline

            self.metrics["delivered"] += 1
            self.metrics["acked"] += 1
            if state == "warning":
                self.metrics["warnings"] += 1
            if state == "emergency":
                self.metrics["emergencies"] += 1
                # -- Alert ตอน Emergency
                log("ALERT", f"🚨 EMERGENCY DETECTED from {sc_id}", RED)

            start_time = raw.get("timestamp")
            latency_txt = "N/A"
            if start_time:
                latency = delivered_ts - start_time
                self.metrics["latencies"].append(latency)
                self.metrics["avg_latency"] = sum(self.metrics["latencies"]) / len(self.metrics["latencies"])
                status = f"{GREEN}PASS{RESET}" if latency < 0.5 else f"{YELLOW}WARN{RESET}"
                latency_txt = f"{latency:.4f}s ({status})"

            tick_val = raw.get("tick")
            log(
                "GROUND",
                f"✔ DELIVERED {get_tick_icon(tick_val)} {bundle_id} | from={sc_id} via={relay_id} "
                f"| state={state.upper():<9} | qos={pri_label(priority)} | latency={latency_txt}",
                color_for_state(state),
            )

            # print compact timeline
            stages = " -> ".join([t["stage"] for t in timeline])
            log("TIMELINE", f"{bundle_id}: {stages}", CYAN)

    def dashboard_loop(self):
        while self.running:
            time.sleep(5)
            banner("GROUND DASHBOARD", BG_CYAN)
            avg = self.metrics["avg_latency"]
            print(f"{BOLD}Delivered:{RESET} {self.metrics['delivered']}")
            print(f"{BOLD}ACKed:{RESET}     {self.metrics['acked']}")
            print(f"{BOLD}Warnings:{RESET}  {self.metrics['warnings']}")
            print(f"{BOLD}Emergencies:{RESET} {self.metrics['emergencies']}")
            print(f"{BOLD}Avg Latency:{RESET} {avg:.4f}s")
            
            # -- วัดอัตราการประมวลผลของระบบ
            tp = self.get_throughput()
            print(f"{BOLD}Throughput:{RESET}  {tp:.2f} pkt/s")
            print("-" * 48)

def handle_ground_client(conn: socket.socket, addr, gs: GroundStation):
    log("GROUND", f"Relay connected from {addr}", GREEN)
    buffer = ""

    try:
        conn.sendall("GROUND READY\n".encode("utf-8"))

        while True:
            data = conn.recv(4096)
            if not data:
                break

            buffer += data.decode("utf-8", errors="ignore")

            while "\n" in buffer:
                line, buffer = buffer.split("\n", 1)
                line = line.strip()
                if not line:
                    continue

                try:
                    msg = json.loads(line)
                except json.JSONDecodeError:
                    log("GROUND", f"Malformed JSON ignored: {line[:100]}", RED)
                    continue

                action = msg.get("action")

                if action == "hello":
                    relay_id = msg.get("relay_id", "UNKNOWN")
                    log("GROUND", f"Handshake from relay {relay_id}", CYAN)

                elif action == "forward":
                    bundle = msg["bundle"]
                    priority = bundle["priority"]
                    bundle["timeline"].append({
                        "stage": "RELAYED",
                        "ts": now_ts(),
                        "node": msg.get("relay_id", "UNKNOWN"),
                    })
                    gs.queue.put((-priority, now_ts(), msg))
                    gs.metrics["received"] += 1

                else:
                    log("GROUND", f"Unknown action: {action}", YELLOW)

    except ConnectionResetError:
        log("GROUND", f"Connection reset by peer: {addr}", RED)
    except Exception as e:
        log("GROUND", f"Unexpected error: {e}", RED)
    finally:
        conn.close()
        log("GROUND", f"Relay disconnected: {addr}", YELLOW)

def run_ground():
    gs = GroundStation()

    threading.Thread(target=gs.process_queue, daemon=True).start()
    threading.Thread(target=gs.dashboard_loop, daemon=True).start()

    server = socket.socket(socket.AF_INET, socket.SOCK_STREAM)
    server.bind((HOST_GROUND, PORT_GROUND))
    server.listen(5)

    banner(f"GROUND STATION LISTENING TCP {HOST_GROUND}:{PORT_GROUND}", BG_GREEN)

    try:
        while True:
            conn, addr = server.accept()
            threading.Thread(target=handle_ground_client, args=(conn, addr, gs), daemon=True).start()
    except KeyboardInterrupt:
        log("GROUND", "Shutting down...", YELLOW)
    finally:
        gs.running = False
        server.close()

# =========================================================
# Satellite Relay
# =========================================================

class SatelliteRelayNode:
    def __init__(self, relay_id: str, loss_rate: float = 0.08):
        self.relay_id = relay_id
        self.qos = MissionQoSEngine()
        self.forward_queue = PriorityQueue()

        self.udp_sock = socket.socket(socket.AF_INET, socket.SOCK_DGRAM)
        self.udp_sock.bind((HOST_RELAY_UDP, PORT_RELAY_UDP))
        self.udp_sock.settimeout(0.5)

        self.tcp_sock = socket.socket(socket.AF_INET, socket.SOCK_STREAM)

        self.window_open = False
        self.phase_start = now_ts()
        self.phase_len = 10
        self.base_open = 10
        self.base_closed = 15

        self.loss_rate = loss_rate

        self.metrics = {
            "stored": 0,
            "forwarded": 0,
            "dropped_simulated": 0,
            "retried": 0,
            "window_switches": 0,
        }

        self.running = True

    def connect_to_ground(self):
        banner("SATELLITE RELAY CONNECTING", BG_MAGENTA)
        self.tcp_sock.connect((HOST_GROUND, PORT_GROUND))
        safe_json_send(self.tcp_sock, {"action": "hello", "relay_id": self.relay_id})
        resp = self.tcp_sock.recv(1024).decode("utf-8", errors="ignore").strip()
        log("RELAY", f"Ground response: {resp}", GREEN)

    def self_heal_window(self):
        qsize = self.forward_queue.qsize()

        if qsize > 12:
            self.base_open = 14
            self.base_closed = 8
        elif qsize > 5:
            self.base_open = 12
            self.base_closed = 10
        else:
            self.base_open = 10
            self.base_closed = 15

    def update_contact_window(self):
        self.self_heal_window()
        now = now_ts()

        if now - self.phase_start >= self.phase_len:
            self.window_open = not self.window_open
            self.phase_start = now
            self.phase_len = self.base_open if self.window_open else self.base_closed
            self.metrics["window_switches"] += 1

            state_txt = f"{GREEN}OPEN ✅{RESET}" if self.window_open else f"{RED}CLOSED ❌{RESET}"
            log(
                "WINDOW",
                f"{state_txt} | duration={self.phase_len}s | q={self.forward_queue.qsize()}",
                CYAN,
            )

    def enqueue_packet(self, bundle: dict):
        bundle["timeline"].append({
            "stage": "QUEUED",
            "ts": now_ts(),
            "node": self.relay_id,
        })
        self.forward_queue.put((-bundle["priority"], now_ts(), bundle))
        
        # -- Queue Warning
        if self.forward_queue.qsize() > 15:
            log("RELAY", "⚠ HIGH QUEUE CONGESTION", YELLOW)
            
        self.metrics["stored"] += 1

    def flush_queue_if_possible(self):
        if not self.window_open:
            return

        max_send_per_tick = 8
        sent = 0

        while not self.forward_queue.empty() and sent < max_send_per_tick:
            _, _, bundle = self.forward_queue.get()

            # simulate random packet loss before forwarding
            if random.random() < self.loss_rate:
                bundle["retry_count"] += 1
                self.metrics["dropped_simulated"] += 1
                self.metrics["retried"] += 1

                if bundle["retry_count"] <= 3:
                    log(
                        "RELAY",
                        f"⚠ simulated link loss {bundle['bundle_id']} -> requeue retry={bundle['retry_count']}",
                        YELLOW,
                    )
                    self.forward_queue.put((-bundle["priority"], now_ts(), bundle))
                else:
                    log(
                        "RELAY",
                        f"✖ dropped permanently {bundle['bundle_id']} after max retry",
                        RED,
                    )
                sent += 1
                continue

            bundle["timeline"].append({
                "stage": "SENT",
                "ts": now_ts(),
                "node": self.relay_id,
            })

            msg = {
                "action": "forward",
                "relay_id": self.relay_id,
                "bundle": bundle,
            }

            safe_json_send(self.tcp_sock, msg)
            self.metrics["forwarded"] += 1

            raw = bundle["raw"]
            state = raw["state"]
            log(
                "RELAY",
                f"➤ FORWARD {bundle['bundle_id']} | {bundle['command']} | qos={pri_label(bundle['priority'])} | retry={bundle['retry_count']}",
                color_for_state(state),
            )
            sent += 1

    def dashboard_loop(self):
        while self.running:
            time.sleep(5)
            banner("RELAY DASHBOARD", BG_MAGENTA)
            print(f"{BOLD}Queue Size:{RESET}        {self.forward_queue.qsize()}")
            print(f"{BOLD}Stored:{RESET}            {self.metrics['stored']}")
            print(f"{BOLD}Forwarded:{RESET}         {self.metrics['forwarded']}")
            print(f"{BOLD}Sim Dropped:{RESET}       {self.metrics['dropped_simulated']}")
            
            # -- Drop Rate แสดงผล 
            if self.metrics["forwarded"] > 0:
                # -- อัตราการสูญหายของ packet ต่อการส่งทั้งหมด (แปลงเป็น %)
                drop_rate = self.metrics["dropped_simulated"] / self.metrics["forwarded"]
                if drop_rate > 0.3:
                    color = RED
                elif drop_rate > 0.1:
                    color = YELLOW
                else:
                    color = GREEN
                print(f"{BOLD}Drop Rate:{RESET}         {color}{drop_rate*100:.2f}%{RESET}")
                
            print(f"{BOLD}Retried:{RESET}           {self.metrics['retried']}")
            print(f"{BOLD}Window Switches:{RESET}   {self.metrics['window_switches']}")
            print(f"{BOLD}Window State:{RESET}      {'OPEN' if self.window_open else 'CLOSED'}")
            print("-" * 48)

    def run(self):
        banner(f"SAT-RELAY UDP LISTENING {HOST_RELAY_UDP}:{PORT_RELAY_UDP}", BG_MAGENTA)
        log("RELAY", "Contact Window dynamic mode enabled", CYAN)

        threading.Thread(target=self.dashboard_loop, daemon=True).start()

        try:
            while True:
                self.update_contact_window()

                try:
                    data, _ = self.udp_sock.recvfrom(4096)
                    telemetry = json.loads(data.decode("utf-8"))
                    bundle = self.qos.to_bundle(telemetry)
                    
                    tick_val = telemetry.get('tick')
                    log("RELAY", f"↓ RECV {get_tick_icon(tick_val)} tick={tick_val:<4} | from={telemetry.get('spacecraft_id')} | qos={pri_label(bundle['priority'])}", CYAN)

                    self.enqueue_packet(bundle)

                    state = telemetry["state"]
                    log(
                        "RELAY",
                        f"Stored {bundle['bundle_id']} | state={state.upper()} | qos={pri_label(bundle['priority'])} | queue={self.forward_queue.qsize()}",
                        color_for_state(state),
                    )
                except socket.timeout:
                    pass

                self.flush_queue_if_possible()
                time.sleep(0.05)

        except KeyboardInterrupt:
            log("RELAY", "Stopped by user", YELLOW)
        finally:
            self.running = False
            try:
                self.tcp_sock.close()
            except Exception:
                pass
            try:
                self.udp_sock.close()
            except Exception:
                pass

def run_relay():
    relay = SatelliteRelayNode(RELAY_ID)
    relay.connect_to_ground()
    relay.run()

# =========================================================
# Spacecraft Sensor
# =========================================================

class SpacecraftSensor:
    def __init__(self, spacecraft_id: str):
        self.spacecraft_id = spacecraft_id
        self.sock = socket.socket(socket.AF_INET, socket.SOCK_DGRAM)
        self.tick = 1
        self.running = True
        self.metrics = defaultdict(int)

    def make_telemetry(self) -> dict:
        states = ["nominal", "warning", "emergency", "science", "media"]
        weights = [0.45, 0.22, 0.10, 0.15, 0.08]
        chosen = random.choices(states, weights=weights)[0]

        if chosen == "science":
            msg_type = "science"
            payload_size = random.randint(800, 2000)
        elif chosen == "media":
            msg_type = "media"
            payload_size = random.randint(2500, 5000)
        else:
            msg_type = "telemetry"
            payload_size = random.randint(80, 220)

        temp = round(random.uniform(18, 95), 2)
        voltage = round(random.uniform(10.8, 14.5), 2)

        telemetry = {
            "spacecraft_id": self.spacecraft_id,
            "tick": self.tick,
            "state": chosen if chosen in ["nominal", "warning", "emergency"] else "nominal",
            "msg_type": msg_type,
            "payload_size": payload_size,
            "temperature_c": temp,
            "bus_voltage_v": voltage,
            "timestamp": now_ts(),
        }

        if temp > 80:
            telemetry["state"] = "emergency"
        elif temp > 65:
            telemetry["state"] = "warning"

        return telemetry

    def dashboard_loop(self):
        while self.running:
            time.sleep(5)
            banner(f"SENSOR DASHBOARD {self.spacecraft_id}", BG_YELLOW)
            total = sum(self.metrics.values())
            print(f"{BOLD}Total Sent:{RESET} {total}")
            for k in ["nominal", "warning", "emergency", "science", "media"]:
                print(f"{BOLD}{k.capitalize()}:{RESET} {self.metrics[k]}")
            print("-" * 48)

    def run(self):
        banner(f"SPACECRAFT SENSOR {self.spacecraft_id}", BG_YELLOW)
        threading.Thread(target=self.dashboard_loop, daemon=True).start()

        try:
            while True:
                telemetry = self.make_telemetry()

                original_state = telemetry["msg_type"]
                if original_state == "science":
                    self.metrics["science"] += 1
                elif original_state == "media":
                    self.metrics["media"] += 1
                else:
                    self.metrics[telemetry["state"]] += 1

                self.sock.sendto(json.dumps(telemetry).encode("utf-8"), (HOST_RELAY_UDP, PORT_RELAY_UDP))

                state = telemetry["state"]
                msg_type = telemetry["msg_type"]
                
                log(
                    "SENSOR",
                    f"↑ SEND {get_tick_icon(self.tick)} tick={self.tick:<4} | type={msg_type.upper():<9} | state={state.upper():<9} "
                    f"| temp={telemetry['temperature_c']}C | volt={telemetry['bus_voltage_v']}V "
                    f"| size={telemetry['payload_size']}B",
                    color_for_state(state),
                )

                self.tick += 1

                time.sleep(random.uniform(0.8, 2.2))

        except KeyboardInterrupt:
            log("SENSOR", "Stopped by user", YELLOW)
        finally:
            self.running = False
            self.sock.close()

def run_sensor(spacecraft_id: str):
    sensor = SpacecraftSensor(spacecraft_id)
    sensor.run()

# =========================================================
# Main
# =========================================================

def main():
    parser = argparse.ArgumentParser(description="Spacetime Networking Deluxe Mockup")
    parser.add_argument("mode", choices=["ground", "relay", "sensor"], help="Run mode")
    parser.add_argument("--spacecraft", default="SC-ALPHA", help="Spacecraft ID for sensor mode")
    args = parser.parse_args()

    if args.mode == "ground":
        run_ground()
    elif args.mode == "relay":
        run_relay()
    elif args.mode == "sensor":
        run_sensor(args.spacecraft)

if __name__ == "__main__":
    main()