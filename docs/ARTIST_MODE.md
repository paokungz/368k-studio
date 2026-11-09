# Artist Mode — เว็บออกแบบสำหรับนักวาด

Artist Mode ใช้งานใน browser โดยไม่ต้องมี Python, Launcher หรือ boot backup บนเครื่องนักวาด และไม่มี API เชื่อมต่อ/ติดตั้ง/คืนค่ารถ

เว็บ public: https://paokungz.github.io/368k-studio/

## เริ่มใช้งาน

1. เปิดลิงก์เว็บ เลือกหนึ่งใน 9 กลุ่ม เช่น วอลเปเปอร์ พื้นวง แผงซ้าย/ขวา หรือสีตัวเลข
2. นำ PNG/JPG/WEBP/GIF/BMP มาใส่ ปรับการครอป ความทึบ หรือสีด้วย palette/HEX/RGB
3. ใช้ค่าความเร็ว/รอบเครื่องตัวอย่างดูการอ่านข้อมูล และเทียบพื้นเดิม
4. กด **บันทึกโปรเจกต์** เพื่อเก็บ JSON พร้อมภาพต้นทางและ template ที่โหลด สามารถเปิดกลับใน Artist Mode หรือเปิดด้วย Studio เดิม
5. กด **ส่งออกชิ้นภาพ** เพื่อเก็บ ZIP: PNG พื้น 10 ไฟล์, preview, project และ palette ส่งให้นักพัฒนาหรือเจ้าของรถตรวจต่อ

ภาพในเว็บเริ่มต้นวาดด้วยโค้ดขึ้นใหม่ ไม่มี PNG/ฟอนต์ของผู้ผลิตหรือภาพส่วนตัวจากรถแนบในเว็บ รูปที่นำเข้าไม่อัปโหลดไป backend ไม่มี analytics และไม่มีการบันทึกอัตโนมัติ ปิดแท็บแล้วงานที่ยังไม่บันทึกอาจหาย browser อาจแสดงข้อความถามก่อนปิดหากมีการแก้ไข

ตัวเว็บและไฟล์โปรแกรมโหลดจากโฮสต์ตามปกติ แต่การอ่าน/แปลงภาพและโปรเจกต์ทำใน browser ไม่ส่งรูปที่เลือกไป GitHub หรือรถ

## ใช้ template จริงที่ได้รับเป็นการส่วนตัว

แตก ZIP ชุด template ที่เจ้าของงานให้ก่อน กด **โหลดโฟลเดอร์ template** แล้วเลือกโฟลเดอร์ที่มี `res_sport` และ `res/Other/dark/sport` โปรแกรมใช้ชื่อ resource และขนาด canvas เป็นตัวจับคู่

Template ที่อ่านครบและขนาดตรงจะใช้แทนภาพตัวอย่าง เฉพาะส่วนที่นำเข้า ส่วนอื่นและฟอนต์/ตำแหน่งมาตรวัดยังประมาณ จำนวน template ที่โหลดแสดงอยู่ในหน้าเว็บ ชิ้นภาพบาง variant ขนาดต่างกัน เช่น `bg0.png` 470×518 และ `bg0_1.png` 468×518 ห้าม trim canvas ตอนส่งงาน

โปรเจกต์ JSON แนบ PNG template ที่คุณเลือกด้วย เพื่อเปิดกลับแล้ว mask ไม่เปลี่ยน ดังนั้นไฟล์ที่ส่งให้คนอื่นอาจมีภาพส่วนตัว/ไฟล์อ้างอิงแนบอยู่ ส่วน repository และเว็บ public ไม่ได้รับไฟล์เหล่านี้

ปุ่ม **ดาวน์โหลด template ตัวอย่าง** ส่งออกเฉพาะ template ที่วาดขึ้นด้วยโค้ด ไม่ใช่ชิ้นภาพจาก firmware ใช้สเก็ตช์ทิศทางและขนาดก่อน แล้วโหลด template จริงเพื่อดู mask ถ้ามี

## ส่งกลับไป Studio

1. นักวาดส่ง `368K-Artist-project.json` หรือ `project.json` จาก ZIP ให้เจ้าของรถ
2. เจ้าของรถเปิด Studio ที่เตรียมต้นฉบับผ่าน `prepare_private.py` แล้ว กด **เปิดโปรเจกต์** และเลือก JSON
3. Studio อ่านภาพและ config เดียวกันมาแปลงกับ resource จริง ตรวจ ELF/QRC, mask, alpha, red zone และพื้นที่รวม ก่อนสร้าง candidate
4. ถ้า PNG ใหญ่เกินพื้นที่ ค่อยลดจำนวนสีหรือกลับไปปรับ source ไม่มีเพดาน KB ต่อภาพแบบตายตัว
5. ตรวจ preview และไฟล์จริงก่อนใช้ workflow ติดตั้งของ Studio

Artist Mode ไม่สร้าง `Launcher.theme.bin` หรือ boot image ไม่ได้เปิดบริการ Telnet และไม่แทนการตรวจ firmware หลังเปิดงานจาก Artist Mode ใน Studio ต้องสร้างไฟล์ใหม่ก่อนติดตั้งเสมอ

## ขอบเขตและข้อจำกัด

- ใช้ contract เดียวกับโปรเจกต์ Studio: `application`, `version`, `config`, `images` และ metadata `artist` ที่ Studio เดิมข้ามได้
- สีตัวเลข/รอบเครื่องปรับได้เฉพาะสี คง alpha และส่วนสีแดงตามเกณฑ์เดียวกับ Studio ไฟเตือนใน concept คงสีเดิม
- Preview ไม่ใช่ Qt emulator รูปทรง placeholder, ฟอนต์, การจัดวาง และการ resample ใน browser อาจต่างจาก resource/ตัวแปลงจริง
- Export สี-only เป็นค่าตั้งใน project/palette ส่วน PNG ใน ZIP เป็นพื้น 10 ไฟล์ ไม่ได้มี glyph ที่ฝัง firmware ใหม่
- ภาพ GIF ใช้ภาพนิ่ง ไม่แก้ boot animation งาน boot ในโปรเจกต์ Studio เดิมอยู่นอก Artist Mode จึงไม่ส่งต่อ boot edits
- ไฟล์ภาพไม่เกิน 8 MiB/ไฟล์, 16 ล้านพิกเซล; ภาพและ template รวมไม่เกิน 16 MiB; JSON ไม่เกิน 24 MiB
- รองรับโปรเจกต์ Studio ที่แนบภาพที่ใช้ครบ หากโปรเจกต์ใช้ alias ภาพตัวอย่างที่ไม่ได้แนบมา ให้เปิดใน Studio แล้วเลือกภาพต้นทางและบันทึกใหม่ ไม่เดาภาพที่ขาด
- ไม่รับ SVG/HTML เป็นภาพ แสดงชื่อภาพด้วย textContent และเปิดโปรเจกต์ใหม่หลังอ่านข้อมูลครบ การนำเข้าที่ล้มเหลวจะคงโปรเจกต์เดิม
- Export PNG เป็นสีเต็ม การตั้งลดสีจากโปรเจกต์เดิมจะเก็บไว้ แต่พรีวิวและ budget ต้องยืนยันใน Studio

## เปิดบนคอมหรือ build EXE

ผ่าน Studio เลือก **Artist Mode ↗** ได้แม้ยังไม่มี firmware ปุ่มเปิดแท็บใหม่ที่ `/artist/` และไม่เปิดสิทธิ์ device API

หรือเปิดเว็บ standalone จาก source:

```powershell
python -m http.server 8770 --bind 127.0.0.1 --directory docs/artist
```

เปิด `http://127.0.0.1:8770/` ไม่เปิด index.html ผ่าน file:// เพราะ browser จำกัด ES module ไฟล์ Artist อยู่ใน EXE ที่สร้างด้วย build.ps1 แล้ว

## ทดสอบและเผยแพร่

```text
npm ci
npm test
npx playwright install chromium
npm run test:browser
```

Windows ใช้ Edge ที่ติดตั้งไว้กับ browser tests ส่วน Linux CI ใช้ Chromium ของ Playwright

Workflow Pages อัปโหลดเฉพาะ `docs/artist` ไม่ใช่ทั้ง repository หรือ private bundle GitHub Pages ของ repository ต้องใช้ build source แบบ GitHub Actions ดู [เอกสาร GitHub Pages](https://docs.github.com/en/pages/getting-started-with-github-pages/using-custom-workflows-with-github-pages)
