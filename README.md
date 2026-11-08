## Academic Portal (CN331)
[![CI](https://github.com/Vtopic-for-CN331/CN331/blob/main/.github/workflows/main.yml)](...)

## Live Production : https://debate-portal.onrender.com/

## System Overview
* **ชื่อระบบ:** VoteTopics (ระบบแพลตฟอร์มดีเบตและโหวตประเด็นสังคม)
* **วัตถุประสงค์:** เพื่อแลกเปลี่ยนความคิดและช่วยหาข้อสรุปทางสังคม
* **สมาชิกผู้จัดทำ:**
  * 6810420015 กัณฑ์อเนก จิตรามัยกุล
  * 6810610045 ชญานนท์ เถื่อนวงษ์
  * 6810610250 สิรภพ คูหาแดนสวรรค์
  * 6810610284 อัฑฒ์ คำฟอง

## System Architecture (C4 Model)
![C4 Level 1](./docs/architecture/C4Level1.drawio.png)
![C4 Level 2](./docs/architecture/C4Level2.drawio.png)

## Local Setup
คำสั่งสำหรับการติดตั้งและรัน migrations บนเครื่อง Local:

```bash
$ git clone [https://github.com/Vtopic-for-CN331/CN331.git](https://github.com/Vtopic-for-CN331/CN331.git) && cd portal
$python -m venv .venv && source .venv/bin/activate$ pip install -r requirements.txt
$ python manage.py migrate && python manage.py runserver