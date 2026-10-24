"""
i18n.py — Chuỗi giao diện bot theo ngôn ngữ người dùng (VI / EN / RU / ZH).

Phạm vi: vỏ hội thoại (chào mừng, menu, nút bấm, trợ giúp, xác nhận đổi
ngôn ngữ). Nội dung chuyên môn (chi tiết tín hiệu, engine, rủi ro, tin tức)
giữ nguyên ngôn ngữ gốc của nguồn dữ liệu; FAQ đã có sẵn theo từng ngôn ngữ.
"""

STRINGS = {
    "VI": {
        "welcome": (
            "Xin chào! 👋\n"
            "Tôi là bot tín hiệu của **NexusPilot Pro** — hệ thống cockpit & "
            "signal engine giao dịch MT5.\n\n"
            "📡 Tôi tự động gửi tín hiệu đạt chuẩn (điểm từ 80/100) ngay khi "
            "hệ thống phát hiện.\n"
            "Gõ /tin_hieu để xem tín hiệu gần nhất, hoặc chọn mục bên dưới:"
        ),
        "btn_signal": "📡 Tín hiệu mới nhất >",
        "btn_engines": "🧠 3 Engine tín hiệu >",
        "btn_risk": "🛡 Quản trị rủi ro >",
        "btn_products": "📈 Các cặp đang theo dõi >",
        "btn_faq_lang": "🌐 FAQ đa ngôn ngữ (VI/EN/RU/ZH) >",
        "btn_support": "👤 Gặp tư vấn viên >",
        "btn_faq": "📋 FAQ NexusPilot",
        "btn_support_short": "👤 Hỗ trợ",
        "btn_fanpage": "📘 Fanpage MrBit Onchain",
        "btn_cockpit": "🖥 Mở Cockpit NexusPilot",
        "delete_private_only": "Tính năng xóa nhật ký chỉ dùng trong chat riêng với bot.",
        "delete_done_none": "Không xóa được tin nào (các tin còn lại đều quá cũ, Telegram không cho bot xóa). Bạn có thể xóa tay trong app Telegram.",
        "delete_done_partial": "✅ Đã xóa {n} tin nhắn. {m} tin cũ Telegram không cho bot xóa — bạn có thể xóa tay trong app Telegram.",
        "delete_done": "✅ Đã xóa {n} tin nhắn của bot trong đoạn chat này.\nDữ liệu vận hành trên máy chủ vẫn được giữ.",
        "delete_kept": "Đã giữ lại nhật ký, không xóa gì cả.",
        "delete_no": "❌ Giữ lại",
        "delete_yes": "✅ Xác nhận xóa",
        "delete_confirm": "Bạn muốn xóa các tin nhắn của bot trong đoạn chat này?\nDữ liệu vận hành trên máy chủ vẫn được giữ để quản trị bot.",
        "btn_delete": "🗑 Xóa nhật ký",
        "btn_news": "📰 Tin kinh tế",
        "btn_latest": "📰 Tin mới nhất (24h)",
        "btn_upcoming": "⏩ Sắp ra — 7 ngày tới",
        "btn_released": "⏪ Đã ra — 7 ngày qua",
        "btn_menu": "⬅️ Menu chính",
        "btn_back": "⬅️ Quay lại",
        "lang_title": "🌐 **CHỌN NGÔN NGỮ HỖ TRỢ (SELECT LANGUAGE):**",
        "lang_set": "✅ Đã đổi ngôn ngữ bot sang **Tiếng Việt**. Từ nay bot sẽ trả lời bằng tiếng Việt.",
        "help": (
            "📖 **CÁC LỆNH CỦA BOT:**\n"
            "/start — Menu chính\n"
            "/tin_hieu — Tín hiệu đạt chuẩn gần nhất\n"
            "/engines — Giới thiệu 3 engine tín hiệu\n"
            "/risk — Quy tắc quản trị rủi ro\n"
            "/cockpit — Mở web cockpit\n"
            "/tin_moi — Tin kinh tế mới nhất (24h)\n"
            "/tin_sap_ra — Lịch kinh tế 7 ngày tới\n"
            "/tin_da_ra — Tin kinh tế đã ra 7 ngày qua\n"
            "/faq — Câu hỏi thường gặp\n"
            "/support — Gặp tư vấn viên"
        ),
        "default_reply": "Xin chào! Tôi có thể giúp gì cho bạn? Hãy chọn một mục bên dưới nhé:",
        "menu_prompt": "Bạn muốn tìm hiểu sản phẩm nào?",
        "btn_lang_short": "🌐 Ngôn ngữ",
        "greet": "👋 Chào {name}, đây là bot tín hiệu **NexusPilot Pro**.",
        "support_title": "👤 **KẾT NỐI TƯ VẤN VIÊN TRỰC TIẾP**",
        "support_advisor": "Tư vấn viên hỗ trợ",
        "support_site": "Website chính thức",
        "support_fanpage": "Fanpage",
        "support_note": "Bạn hãy để lại Số điện thoại hoặc nội dung cần hỗ trợ, tư vấn viên sẽ phản hồi trong ít phút!",
        "support_short": "👤 Liên hệ tư vấn viên trực tiếp",
        "support_or": "Hoặc truy cập",
        "cockpit_label": "🖥 **Cockpit NexusPilot Pro:**",
    },
    "EN": {
        "welcome": (
            "Hello! 👋\n"
            "I am the signal bot of **NexusPilot Pro** — an MT5 trading cockpit & "
            "signal engine.\n\n"
            "📡 I automatically send qualified signals (score 80/100 or above) as soon "
            "as the system detects them.\n"
            "Type /tin_hieu to see the latest qualified signal, or pick a section below:"
        ),
        "btn_signal": "📡 Latest signal >",
        "btn_engines": "🧠 3 Signal engines >",
        "btn_risk": "🛡 Risk management >",
        "btn_products": "📈 Pairs we follow >",
        "btn_faq_lang": "🌐 Multilingual FAQ (VI/EN/RU/ZH) >",
        "btn_support": "👤 Talk to an advisor >",
        "btn_faq": "📋 NexusPilot FAQ",
        "btn_support_short": "👤 Support",
        "btn_fanpage": "📘 MrBit Onchain Fanpage",
        "btn_cockpit": "🖥 Open NexusPilot Cockpit",
        "delete_private_only": "Clear history only works in a private chat with the bot.",
        "delete_done_none": "No messages could be deleted (the rest are too old for the bot to delete). You can delete them manually in Telegram.",
        "delete_done_partial": "✅ Deleted {n} messages. {m} old messages can't be deleted by the bot — you can delete them manually in Telegram.",
        "delete_done": "✅ Deleted {n} bot messages in this chat.\nServer records are kept.",
        "delete_kept": "History kept, nothing deleted.",
        "delete_no": "❌ Keep them",
        "delete_yes": "✅ Confirm delete",
        "delete_confirm": "Delete the bot's messages in this chat?\nServer records are kept for bot administration.",
        "btn_delete": "🗑 Clear history",
        "btn_news": "📰 Economic news",
        "btn_latest": "📰 Latest news (24h)",
        "btn_upcoming": "⏩ Upcoming — next 7 days",
        "btn_released": "⏪ Released — past 7 days",
        "btn_menu": "⬅️ Main menu",
        "btn_back": "⬅️ Back",
        "lang_title": "🌐 **CHOOSE SUPPORT LANGUAGE:**",
        "lang_set": "✅ Bot language set to **English**. From now on, the bot will reply in English.",
        "help": (
            "📖 **BOT COMMANDS:**\n"
            "/start — Main menu\n"
            "/tin_hieu — Latest qualified signal\n"
            "/engines — About the 3 signal engines\n"
            "/risk — Risk management rules\n"
            "/cockpit — Open the web cockpit\n"
            "/tin_moi — Latest economic news (24h)\n"
            "/tin_sap_ra — Economic calendar, next 7 days\n"
            "/tin_da_ra — Economic news released, past 7 days\n"
            "/faq — Frequently asked questions\n"
            "/support — Talk to an advisor"
        ),
        "default_reply": "Hi! How can I help you? Please choose a section below:",
        "menu_prompt": "Which section would you like to explore?",
        "btn_lang_short": "🌐 Language",
        "greet": "👋 Hi {name}, this is the **NexusPilot Pro** signal bot.",
        "support_title": "👤 **CONNECT WITH A LIVE ADVISOR**",
        "support_advisor": "Advisor",
        "support_site": "Official website",
        "support_fanpage": "Fanpage",
        "support_note": "Please leave your phone number or describe what you need — an advisor will reply within a few minutes!",
        "support_short": "👤 Contact a live advisor",
        "support_or": "Or visit",
        "cockpit_label": "🖥 **NexusPilot Pro Cockpit:**",
    },
    "RU": {
        "welcome": (
            "Здравствуйте! 👋\n"
            "Я — сигнальный бот **NexusPilot Pro**: торговая панель и сигнальный "
            "движок для MT5.\n\n"
            "📡 Я автоматически отправляю квалифицированные сигналы (оценка от 80/100), "
            "как только система их обнаруживает.\n"
            "Введите /tin_hieu, чтобы увидеть последний сигнал, или выберите раздел ниже:"
        ),
        "btn_signal": "📡 Последний сигнал >",
        "btn_engines": "🧠 3 сигнальных движка >",
        "btn_risk": "🛡 Управление рисками >",
        "btn_products": "📈 Отслеживаемые пары >",
        "btn_faq_lang": "🌐 FAQ на нескольких языках (VI/EN/RU/ZH) >",
        "btn_support": "👤 Связаться с консультантом >",
        "btn_faq": "📋 FAQ NexusPilot",
        "btn_support_short": "👤 Поддержка",
        "btn_fanpage": "📘 Фан-страница MrBit Onchain",
        "btn_cockpit": "🖥 Открыть панель NexusPilot",
        "delete_private_only": "Очистка истории работает только в личном чате с ботом.",
        "delete_done_none": "Не удалось удалить сообщения (остальные слишком старые). Удалите их вручную в Telegram.",
        "delete_done_partial": "✅ Удалено: {n}. {m} старых сообщений бот удалить не может — удалите их вручную в Telegram.",
        "delete_done": "✅ Удалено сообщений бота: {n}.\nЗаписи на сервере сохраняются.",
        "delete_kept": "История сохранена, ничего не удалено.",
        "delete_no": "❌ Оставить",
        "delete_yes": "✅ Подтвердить удаление",
        "delete_confirm": "Удалить сообщения бота в этом чате?\nЗаписи на сервере сохраняются для администрирования бота.",
        "btn_delete": "🗑 Очистить историю",
        "btn_news": "📰 Экономические новости",
        "btn_latest": "📰 Последние новости (24 ч)",
        "btn_upcoming": "⏩ Ожидаются — 7 дней",
        "btn_released": "⏪ Вышли — 7 дней",
        "btn_menu": "⬅️ Главное меню",
        "btn_back": "⬅️ Назад",
        "lang_title": "🌐 **ВЫБЕРИТЕ ЯЗЫК ПОДДЕРЖКИ:**",
        "lang_set": "✅ Язык бота изменён на **русский**. Теперь бот будет отвечать на русском языке.",
        "help": (
            "📖 **КОМАНДЫ БОТА:**\n"
            "/start — Главное меню\n"
            "/tin_hieu — Последний квалифицированный сигнал\n"
            "/engines — О 3 сигнальных движках\n"
            "/risk — Правила управления рисками\n"
            "/cockpit — Открыть веб-панель\n"
            "/tin_moi — Последние экономические новости (24 ч)\n"
            "/tin_sap_ra — Экономический календарь на 7 дней\n"
            "/tin_da_ra — Вышедшие экономические новости за 7 дней\n"
            "/faq — Часто задаваемые вопросы\n"
            "/support — Связаться с консультантом"
        ),
        "default_reply": "Здравствуйте! Чем я могу вам помочь? Выберите нужный раздел ниже:",
        "menu_prompt": "Какой раздел вас интересует?",
        "btn_lang_short": "🌐 Язык",
        "greet": "👋 Здравствуйте, {name}! Это сигнальный бот **NexusPilot Pro**.",
        "support_title": "👤 **СВЯЗЬ С КОНСУЛЬТАНТОМ**",
        "support_advisor": "Консультант",
        "support_site": "Официальный сайт",
        "support_fanpage": "Фан-страница",
        "support_note": "Оставьте номер телефона или опишите ваш вопрос — консультант ответит в течение нескольких минут!",
        "support_short": "👤 Связаться с консультантом",
        "support_or": "Или посетите",
        "cockpit_label": "🖥 **Панель NexusPilot Pro:**",
    },
    "ZH": {
        "welcome": (
            "您好！👋\n"
            "我是 **NexusPilot Pro** 的信号机器人：MT5 交易驾驶舱与信号引擎。\n\n"
            "📡 系统一旦检测到达标信号（评分 80/100 及以上），我会自动发送。\n"
            "输入 /tin_hieu 查看最近一次达标信号，或在下方选择："
        ),
        "btn_signal": "📡 最新信号 >",
        "btn_engines": "🧠 3 大信号引擎 >",
        "btn_risk": "🛡 风险管理 >",
        "btn_products": "📈 关注的交易对 >",
        "btn_faq_lang": "🌐 多语言常见问题 (VI/EN/RU/ZH) >",
        "btn_support": "👤 联系顾问 >",
        "btn_faq": "📋 NexusPilot 常见问题",
        "btn_support_short": "👤 客服支持",
        "btn_fanpage": "📘 MrBit Onchain 主页",
        "btn_cockpit": "🖥 打开 NexusPilot 驾驶舱",
        "delete_private_only": "清除记录仅适用于与机器人的私聊。",
        "delete_done_none": "无法删除任何消息（其余消息太旧，机器人无法删除）。请在 Telegram 中手动删除。",
        "delete_done_partial": "✅ 已删除 {n} 条。{m} 条旧消息机器人无法删除，请在 Telegram 中手动删除。",
        "delete_done": "✅ 已删除 {n} 条机器人消息。\n服务器记录仍会保留。",
        "delete_kept": "已保留记录，未删除任何内容。",
        "delete_no": "❌ 保留",
        "delete_yes": "✅ 确认删除",
        "delete_confirm": "删除本聊天中机器人的消息？\n服务器记录仍会保留，用于机器人管理。",
        "btn_delete": "🗑 清除记录",
        "btn_news": "📰 财经新闻",
        "btn_latest": "📰 最新消息（24小时）",
        "btn_upcoming": "⏩ 未来 7 天",
        "btn_released": "⏪ 过去 7 天已发布",
        "btn_menu": "⬅️ 主菜单",
        "btn_back": "⬅️ 返回",
        "lang_title": "🌐 **请选择支持语言：**",
        "lang_set": "✅ 机器人语言已设置为**中文**。今后机器人将用中文回复。",
        "help": (
            "📖 **机器人命令：**\n"
            "/start — 主菜单\n"
            "/tin_hieu — 最近一次达标信号\n"
            "/engines — 3 大信号引擎介绍\n"
            "/risk — 风险管理规则\n"
            "/cockpit — 打开网页驾驶舱\n"
            "/tin_moi — 最新财经新闻（24小时）\n"
            "/tin_sap_ra — 未来 7 天财经日历\n"
            "/tin_da_ra — 过去 7 天已发布财经新闻\n"
            "/faq — 常见问题\n"
            "/support — 联系顾问"
        ),
        "default_reply": "您好！需要什么帮助？请在下方选择一个选项：",
        "menu_prompt": "您想了解哪个部分？",
        "btn_lang_short": "🌐 语言",
        "greet": "👋 您好，{name}！我是 **NexusPilot Pro** 信号机器人。",
        "support_title": "👤 **联系在线顾问**",
        "support_advisor": "顾问",
        "support_site": "官方网站",
        "support_fanpage": "主页",
        "support_note": "请留下电话号码或说明您的需求，顾问将在几分钟内回复！",
        "support_short": "👤 联系在线顾问",
        "support_or": "或访问",
        "cockpit_label": "🖥 **NexusPilot Pro 驾驶舱：**",
    },
}

SUPPORTED = ("VI", "EN", "RU", "ZH")


def t(lang: str, key: str) -> str:
    """Lấy chuỗi theo ngôn ngữ, fallback về VI khi thiếu."""
    table = STRINGS.get(lang) or STRINGS["VI"]
    return table.get(key) or STRINGS["VI"][key]


def normalize(lang: str) -> str:
    lang = (lang or "").strip().upper()
    return lang if lang in SUPPORTED else "VI"
