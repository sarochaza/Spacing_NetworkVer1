#Project: Spacetime Networking — Spacecraft-to-Satellite Communication Network (TS-Com)
โดเมน: Computer Networks / Space Networking
 ธีม: สื่อสารในอวกาศ (หน่วงสูง + สัญญาณขาดช่วง + bandwidth จำกัด)
----

 สมาชิกกลุ่ม
กัญญาวี ศรีเหรา 673380026-6


รสริน เมืองหงษ์ 673380289-4


สโรชา เสาทอง 673380296-7


ปวิศร์ แพงมา 673380047-8


ธนกร ทองศรี 673380040-2

## 🏗️ Network Topology: Hybrid Mesh-Tree

สถาปัตยกรรมเครือข่ายของระบบถูกออกแบบในลักษณะ **Hybrid Mesh-Tree Topology** เพื่อรับมือกับข้อจำกัดด้านการสื่อสารในอวกาศ (Spacetime Latency & Intermittent Visibility) โดยแบ่งการทำงานออกเป็น 2 ส่วนหลัก:

### 🛰️ แผนผังเครือข่าย (Architecture Diagram)

```text
      [ Ground Station / Internet Gateway ]
                       ║ (High-Speed Link)
          ╔════════════╩════════════╗
    [Summit Alpha] ═══ [Summit Beta] ═══ [Summit Gamma]  <-- Core Layer (Mesh)
          ║  ╲             ║             ╱  ║
          ║    ╲           ║           ╱    ║
    [Relay North] ════ [Relay Center] ════ [Relay East]  <-- Relay Layer (Mesh)
          │                ║                │
    [Village A/B]    [Village B/C]    [Village C/D]      <-- Access Layer (Tree)
          │                ║                │
   [Sensor Cluster]  [Sensor Cluster]  [Sensor Cluster]  <-- End Devices (Tree)
    
```
🎯 ทำไมต้องเป็น Hybrid Mesh-Tree?
Core & Relay Layer (โครงสร้างแบบ Mesh): * การเชื่อมต่อ: ระหว่าง Summit และ Relay (ดาวเทียม) จะเชื่อมต่อกันแบบตาข่าย (Mesh)
เหตุผล: เพื่อสร้าง Redundancy (ความทนทาน) หากดาวเทียมดวงใดดวงหนึ่งลับขอบฟ้า หรือลิงก์ขาดหาย (Window Closed) ข้อมูลจะสามารถหาเส้นทางอื่น (Routing) ส่งกลับมาที่สถานีฐานได้อย่างปลอดภัยโดยไม่มี Single Point of Failure
Access Layer (โครงสร้างแบบ Tree):

การเชื่อมต่อ: จาก Relay ลงไปหา Village และ Sensor (ยานอวกาศ/อุปกรณ์ IoT) จะเชื่อมต่อแบบต้นไม้ (Tree)

เหตุผล: เพื่อความง่ายในการจัดการ IP (Network Segmentation) และการจัดการพลังงาน (Energy-Aware) เนื่องจากเซ็นเซอร์มีพลังงานจำกัด จึงไม่ควรต้องประมวลผลการหาเส้นทางที่ซับซ้อนแบบ Mesh ส่งผลให้ประหยัดพลังงานได้มากขึ้น
