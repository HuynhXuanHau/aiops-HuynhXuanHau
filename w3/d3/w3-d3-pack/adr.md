# ADR-001: Triển khai bộ bảo vệ kiểm tra lệnh cho các script bảo trì

> Format: Nygard (2011)

## Trạng thái (Status)
*Được chấp thuận (accepted)*

## Bối cảnh (Context)
Trong quá trình mô phỏng sự cố AWS S3 2017, một lỗi gõ nhầm lệnh `docker compose stop` đã đánh sập toàn bộ hệ thống hạ tầng (billing, index, placement) do thiếu tham số lọc đối tượng (thiếu cờ `--workdir` hoặc tên dịch vụ cụ thể). Chúng ta cần một cơ chế để ngăn chặn các lệnh phá hoại diện rộng bị thực thi ngoài ý muốn và gây ra sự cố hệ thống.

## Quyết định (Decision)
Chúng ta sẽ bọc tất cả các thao tác quản lý môi trường và các lệnh CLI có rủi ro cao vào một script shell tùy chỉnh (`safe-cli`). Công cụ này bắt buộc phải có bước chạy thử (dry-run), xác nhận rõ ràng, và cấm sử dụng wildcard (dấu *) hoặc các lệnh phá hủy không có mục tiêu cụ thể trên môi trường production.

## Các phương án đã bị từ bỏ (Alternatives considered)
1. **Xóa hoàn toàn quyền truy cập shell và dùng GUI (VD: Portainer)** — *Bị loại bỏ vì các kỹ sư vẫn cần các công cụ shell để chẩn đoán sự cố nhanh và tự động hóa.*
2. **Triển khai RBAC nghiêm ngặt ở cấp độ Docker daemon** — *Bị loại bỏ vì quá phức tạp khi thiết lập quyền hạn cho từng dịch vụ và từng kỹ sư trong các hệ thống cũ.*
3. **Phụ thuộc hoàn toàn vào AIOps để rollback (khôi phục) các lệnh sai** — *Bị loại bỏ vì việc phòng bệnh luôn rẻ và an toàn hơn chữa bệnh, nhất là khi một lệnh sai có thể làm sập chính hệ thống giám sát.*

## Hệ quả (Consequences)
- **Mặt lợi (Positive):** Những lỗi gõ nhầm hay quên cờ (flags) sẽ không còn gây ra sập hệ thống diện rộng.
- **Mặt hại (Negative):** Các kỹ sư sẽ thấy hơi phiền phức và chậm hơn một chút vì có thêm bước xác nhận (confirmation prompts).
- **Rủi ro tạo ra (Risks introduced):** Bản thân đoạn script bọc lệnh (`safe-cli`) có thể có bug, chặn nhầm các lệnh khẩn cấp hợp lệ.
- **Sự ràng buộc (What gets locked in):** Chúng ta sẽ bị phụ thuộc vào công cụ `safe-cli` cho các thao tác hàng ngày, đòi hỏi nó phải được cài đặt ở mọi nơi.
