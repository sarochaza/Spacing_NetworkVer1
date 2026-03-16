import asyncio
import threading
import json
import socket
import re
import time
from collections import deque
from fastapi import FastAPI, WebSocket, WebSocketDisconnect
from fastapi.responses import HTMLResponse
import uvicorn

import spacetime_deluxe
from spacetime_deluxe import GroundStation, SatelliteRelayNode, SpacecraftSensor, handle_ground_client
from spacetime_deluxe import HOST_GROUND, PORT_GROUND, HOST_RELAY_UDP, PORT_RELAY_UDP

app = FastAPI()

gs = GroundStation()
relay = SatelliteRelayNode("SAT-LEO-01")
sensor = SpacecraftSensor("SC-ALPHA")

web_logs = deque(maxlen=40)
original_log = spacetime_deluxe.log

# -- ระบบดักจับ Log ส่งขึ้นเว็บ --
def hooked_log(prefix, message, color=spacetime_deluxe.WHITE):
    original_log(prefix, message, color)
    clean_msg = re.sub(r'\x1B(?:[@-Z\\-_]|\[[0-?]*[ -/]*[@-~])', '', message)
    web_logs.append({"prefix": prefix, "msg": clean_msg})

spacetime_deluxe.log = hooked_log

# -- ระบบ Hack ปรับความเร็ว Sensor --
sensor_speed_multiplier = 1.0 
original_uniform = spacetime_deluxe.random.uniform

def hooked_uniform(a, b):
    return max(0.1, original_uniform(a, b) / sensor_speed_multiplier) 

spacetime_deluxe.random.uniform = hooked_uniform

def start_ground_server():
    server = socket.socket(socket.AF_INET, socket.SOCK_STREAM)
    server.bind((HOST_GROUND, PORT_GROUND))
    server.listen(5)
    while True:
        conn, addr = server.accept()
        threading.Thread(target=handle_ground_client, args=(conn, addr, gs), daemon=True).start()

@app.on_event("startup")
def startup_event():
    threading.Thread(target=gs.process_queue, daemon=True).start()
    threading.Thread(target=start_ground_server, daemon=True).start()
    time.sleep(1)
    relay.connect_to_ground()
    threading.Thread(target=relay.run, daemon=True).start()
    threading.Thread(target=sensor.run, daemon=True).start()

@app.get("/")
def get_dashboard():
    with open("index.html", "r", encoding="utf-8") as f:
        return HTMLResponse(f.read())

@app.websocket("/ws")
async def websocket_endpoint(websocket: WebSocket):
    global sensor_speed_multiplier
    await websocket.accept()
    
    async def receive_commands():
        global sensor_speed_multiplier
        try:
            while True:
                data = await websocket.receive_text()
                cmd = json.loads(data)
                
                if cmd.get("action") == "set_loss_rate":
                    relay.loss_rate = float(cmd["value"])
                elif cmd.get("action") == "set_speed":
                    sensor_speed_multiplier = float(cmd["value"])
                elif cmd.get("action") == "toggle_window":
                    relay.window_open = not relay.window_open
                    relay.phase_start = time.time()
                    web_logs.append({"prefix": "COMMAND", "msg": f"Override: Relay Window forced to {'OPEN' if relay.window_open else 'CLOSED'}"})
                elif cmd.get("action") == "force_emergency":
                    telemetry = {
                        "spacecraft_id": "SC-MANUAL",
                        "tick": sensor.tick,
                        "state": "emergency",
                        "msg_type": "telemetry",
                        "payload_size": 250,
                        "temperature_c": 99.9,
                        "bus_voltage_v": 12.0,
                        "timestamp": time.time(),
                    }
                    sensor.sock.sendto(json.dumps(telemetry).encode("utf-8"), (HOST_RELAY_UDP, PORT_RELAY_UDP))
                    web_logs.append({"prefix": "COMMAND", "msg": "Injected P0 EMERGENCY packet! Preemption Triggered."})
        except WebSocketDisconnect:
            pass

    asyncio.create_task(receive_commands())

    try:
        while True:
            current_logs = list(web_logs)
            web_logs.clear()

            # --- ดึงข้อมูล Priority Breakdown ใน Queue สดๆ ---
            q_items = list(relay.forward_queue.queue)
            qos_counts = {"P0": 0, "P1": 0, "P2": 0, "P3": 0}
            for item in q_items:
                pri = -item[0]
                if pri >= 100: qos_counts["P0"] += 1
                elif pri >= 60: qos_counts["P1"] += 1
                elif pri >= 20: qos_counts["P2"] += 1
                else: qos_counts["P3"] += 1

            # --- ดึง Timeline ของแพ็กเก็ตล่าสุดที่ Ground Station ได้รับ ---
            latest_trace = {"id": None, "stages": []}
            if gs.timeline_store:
                # ดึง key ล่าสุดใน dictionary
                last_id = list(gs.timeline_store.keys())[-1]
                latest_trace = {"id": last_id, "stages": gs.timeline_store[last_id]}

            payload = {
                "ground": {
                    "avg_latency": gs.metrics["avg_latency"],
                    "latest_trace": latest_trace
                },
                "relay": {
                    "queue_size": relay.forward_queue.qsize(),
                    "window_open": relay.window_open,
                    "qos": qos_counts
                },
                "new_logs": current_logs
            }
            await websocket.send_json(payload)
            await asyncio.sleep(0.2) 
    except WebSocketDisconnect:
        pass

if __name__ == "__main__":
    uvicorn.run(app, host="127.0.0.1", port=8000)