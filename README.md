# 🚀 Project: Spacetime Networking (TS-Com)
**Spacecraft-to-Satellite Communication Network**

**โดเมน:** Computer Networks / Space Networking  
**ธีม:** การสื่อสารในอวกาศ (หน่วงสูง + สัญญาณขาดช่วง + Bandwidth จำกัด)

---

## 👥 สมาชิกผู้จัดทำ
| ลำดับ | ชื่อ-นามสกุล | รหัสนักศึกษา |
| :---: | :--- | :--- |
| 1 | กัญญาวี ศรีเหรา | 673380026-6 |
| 2 | รสริน เมืองหงษ์ | 673380289-4 |
| 3 | สโรชา เสาทอง | 673380296-7 |
| 4 | ปวิศร์ แพงมา | 673380047-8 |
| 5 | ธนกร ทองศรี | 673380040-2 |

---

## 🌌 ภาพรวมสถาปัตยกรรม (System Architecture)

ระบบจำลองนี้ถูกออกแบบมาเพื่อแก้ปัญหาคอขวดของการสื่อสารในอวกาศ (Spacetime Latency & Intermittent Visibility) โดยอิงตามแนวคิด **Space DTN (Delay/Disruption-Tolerant Networking)** ประกอบด้วย 3 โหนดหลัก:

```text
  [ SC-ALPHA ] (Spacecraft Sensor)
       │  (สร้าง Telemetry: Nominal, Science, Emergency)
       │
       ▼  UDP (127.0.0.1:5011)
  [ SAT-LEO-01 ] (Satellite Relay Node)  <-- ทำหน้าที่ Store-and-Forward (DTN)
       │  (Contact Window & Energy System)
       │
       ▼  TCP (127.0.0.1:5000)
  [ Ground Station ] (Earth)             <-- รับข้อมูล วัด Latency
       │
       ▼  HTTP / WebSockets (Port 8000)
  [ Web Dashboard ] (Presentation UI)
```
### 🧠 กลไกการทำงานหลัก (Core Innovations)
1. Delay/Disruption Tolerance (Store-and-Forward)
ดาวเทียม (Relay) จะไม่ส่งข้อมูลแบบ stream ต่อเนื่อง แต่จะใช้กลไก Custody Transfer คือการรับก้อนข้อมูล (Bundle) เข้ามาเก็บไว้ใน Persistent Queue ก่อน และจะส่งต่อก็ต่อเมื่อ "หน้าต่างการติดต่อ (Contact Window)" เปิดขึ้นเท่านั้น หากส่งพลาด (Packet Loss) จะมีระบบ Auto-Retry อัตโนมัติ  
2. Mission QoS (Quality of Service ตามความสำคัญ)
ข้อมูลไม่ได้ถูกปฏิบัติอย่างเท่าเทียมกัน ในคิวของดาวเทียมจะมีการจัดลำดับความสำคัญ (Priority Queue) ตามชนิดของข้อมูล:  
🔴 P0 (Emergency): ระดับ 100 - คำสั่งฉุกเฉิน (เช่น อุณหภูมิพุ่งสูง) (ได้สิทธิ์ส่งก่อนเสมอ)  
🟠 P1 (Warning): ระดับ 60 - แจ้งเตือนสถานะยาน  
🔵 P2 (Science/Nominal): ระดับ 30/20 - ข้อมูลวิทยาศาสตร์ทั่วไป  
🟣 P3 (Media): ระดับ 10 - รูปภาพ/วิดีโอ (ส่งเมื่อว่างเท่านั้น)
3. Contact-Aware & Window Simulation
อวกาศไม่ใช่ topology ที่เชื่อมต่อกันตลอดเวลา ดาวเทียมจะมีการจำลองสถานะ Window OPEN ✅ และ CLOSED ❌ สลับกันไปตามรอบ หากหน้าต่างปิด ข้อมูลทั้งหมดจะถูกค้างไว้ใน Queue 

4. Energy Degradation System (ระบบจำลองพลังงาน)
ดาวเทียมมีพลังงานเริ่มต้น 100% พลังงานจะลดลงเรื่อยๆ ตามจำนวน Packet ที่ค้างใน Queue (ยิ่งเก็บเยอะยิ่งสูบพลังงาน)
Low Power Mode: หากพลังงานลดลงต่ำกว่า 20% ระบบจะเข้าสู่โหมดประหยัดพลังงานขั้นวิกฤต โดยจะทำการ REJECT ทราฟฟิกอื่นทั้งหมด และรับเฉพาะ P0 (Emergency) เท่านั้น จนกว่าระบบจะฟื้นฟู

---
```text
ts-com-network/
├── server.py              ← ตัวรันเซิร์ฟเวอร์หลัก (FastAPI) และระบบ Dashboard
├── spacetime_deluxe.py    ← Core Logic ทั้งหมด (Ground, Relay, Sensor)
├── index.html             ← UI ของ Web Dashboard
└── network_log.txt        ← ไฟล์บันทึก Network Log อัตโนมัติ
```
## วิธีการติดตั้งและรันระบบ (Quick Start)
Requirements:   
   - Python 3.9+  
   - FastAPI (pip install fastapi)  
   - Uvicorn (pip install uvicorn)  

---
###การรันระบบแบบรวมศูนย์ (All-in-One + Dashboard):
รันเซิร์ฟเวอร์ผ่านไฟล์ server.py
```text
   python server.py
```


