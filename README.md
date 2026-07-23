# ADY201m_Final_Project: Stock Market Analysis

Dự án được thực hiện trong lĩnh vực Công nghệ Tài chính (Fintech) và Thị trường Chứng khoán Việt Nam (HOSE). Nhóm đã chọn cổ phiếu Ngân hàng TMCP Ngoại thương Việt Nam (Vietcombank - Mã: VCB) là cổ phiếu có vốn hóa lớn nhất và tác động mạnh nhất đến chỉ số VN-Index, làm đối tượng phân tích cốt lõi. Xây dựng một ứng dụng Web Dashboard toàn diện, ứng dụng Deep Learning để dự báo giá đóng cửa của cổ phiếu VCB và tự động hóa các tín hiệu giao dịch (Mua/Bán/Nắm giữ).


**Môn học:** ADY201m - Introduction to Data Science | **Lớp:**  | **Giảng viên hướng dẫn:** Bùi Thị Loan

## Thành viên nhóm

| STT | Họ và Tên | MSSV | Vai trò |
|:---:|:---|:---|:---|
| 1 | Lưu Đình Huy | HE200075 | Leader |
| 2 | Trần Vũ Bình | HE200038 | Member |
| 3 | Quách Thiện Nhân | HE210429 | Member |

## Cấu trúc Thư mục Dự án

```text
ADYFINAL/
├── data/               # Thư mục chứa dữ liệu
├── models/             # Chứa các file mô hình (.h5, .pkl)
├── Appv5.py            # File chạy ứng dụng chính
├── Getdata.ipynb       # Notebook thu thập dữ liệu
├── Predict.ipynb       # Notebook thực hiện dự báo
└── README.md           # Tài liệu hướng dẫn sử dụng
```
##  Hướng dẫn Cài đặt & Chạy Dự án

### 1. Tải dự án từ GitHub về
```bash
git clone https://github.com/dinhhuy410/ADY201m_Final_Project.git
cd ADY201m_Final_Project
```

### 1. Chuẩn bị môi trường
```bash
# Tạo môi trường ảo
python -m venv .venv

# Kích hoạt môi trường ảo
# Trên Windows (PowerShell):
.venv\Scripts\Activate.ps1
```
### 2. Cài đặt các thư viện cần thiết
```bash
   pip install -r requirements.txt
```
### 3. Chạy dự án
* **Thu thập dữ liệu:** Chạy file `Getdata.ipynb`.
* **Dự báo:** Chạy file `Predict.ipynb` hoặc chạy ứng dụng chính bằng lệnh:
```bash
python Appv5.py
