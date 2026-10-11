# Changelog

## 1.1-public

- เผยแพร่ source โดยแยก firmware/ภาพ/ฟอนต์ของรถออกจาก Git และ EXE
- เพิ่ม `prepare_private.py` สำหรับตรวจ fingerprint และเตรียมชุดส่วนตัวภายนอก repository
- เพิ่มหน้าสถานะเตรียมต้นฉบับเมื่อยังไม่พร้อม และป้องกัน API สร้างไฟล์/รถในสถานะนี้
- ใช้ภาพตัวอย่างเรขาคณิตที่สร้างใหม่ แยก data/session ของ public edition
- การติดตั้งครั้งแรกสร้างสำเนาบนรถจาก Launcher ต้นฉบับที่ตรวจ SHA ได้
- คู่มือภาษาไทย, recovery guide, public unit tests และ Windows build workflow

## 1.1 (local development)

- เพิ่ม palette 24 สี, HEX/RGB และสีความเร็ว/ตัวเลขรอบ/วงรอบเครื่อง
- รักษารูปทรง alpha และเขตรอบสูงสีแดง
- บันทึกงานแบบ atomic, ตรวจผลหลังการเชื่อมต่อขาด และปลด lock ที่เจ้าของไม่ทำงานแล้ว

## 1.0 (local development)

- UI ออกแบบ Sport, แปลงรูป, ตรวจ/สร้าง Launcher และ Wi-Fi install/restore
- แปลงและส่งออกแอนิเมชันบูต offline
