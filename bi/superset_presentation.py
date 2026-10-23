"""Business-facing copy; methodology belongs in descriptions and documentation."""

PAGES = {
    'overview': {
        'title': 'Tổng quan kinh doanh',
        'context': 'Bán hàng, cơ cấu đóng góp và trải nghiệm giao hàng · Theo tháng đặt hàng',
        'footnote': 'Nguồn: Olist · BRL. Giá trị hàng đã giao chưa gồm vận chuyển; giao đúng hẹn tính trên đơn đủ ngày giao.',
    },
    'sales': {
        'title': 'Hiệu quả bán hàng',
        'context': 'Giá trị hàng đã giao, quy mô đơn hàng và tăng trưởng theo tháng',
        'footnote': 'Nguồn: Olist · BRL. AOV = giá trị hàng đã giao / số đơn đã giao. Xu hướng: 01/2017–08/2018.',
    },
    'commercial': {
        'title': 'Sản phẩm & nhà bán hàng',
        'context': 'Đóng góp theo danh mục, nhà bán hàng và khu vực người mua',
        'footnote': 'Nguồn: Olist · BRL. Giá trị hàng đã giao, chưa gồm vận chuyển. Nhà bán hàng được hiển thị bằng mã.',
    },
    'customers': {
        'title': 'Khách hàng & mua lại',
        'context': 'Toàn kỳ đến 31/08/2018 · Mua lại và quay lại theo nhóm tháng mua đầu tiên',
        'footnote': 'Nguồn: Olist. Mua lại: từ 2 đơn đã giao trong kỳ quan sát. M1–M6: tháng kể từ lần mua đầu tiên quan sát được.',
    },
    'service': {
        'title': 'Giao hàng & thanh toán',
        'context': 'Thời gian giao hàng, tỷ lệ đúng hẹn và cơ cấu thanh toán · Theo tháng đặt hàng',
        'footnote': 'Nguồn: Olist · BRL. Giao hàng dùng đơn đủ ngày hợp lệ. Thanh toán tính theo số tiền/bản ghi, không phải số đơn.',
    },
    'trust': {
        'title': 'Chất lượng dữ liệu & vận hành',
        'context': 'Bản dữ liệu phục vụ báo cáo · Chất lượng nguồn và lịch sử vận hành',
        'footnote': 'Nguồn: Olist. Cảnh báo được giữ theo chính sách chấp nhận; một bản ghi có thể thuộc nhiều quy tắc.',
    },
}

FORBIDDEN_PANELS = ('Dùng để:', 'Cách đọc & phân tích sâu', 'Giới hạn kết luận')


def copy_for(board):
    return PAGES[board]
