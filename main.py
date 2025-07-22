import os
import time
import hashlib
import requests
import asyncio
import random
from datetime import datetime, timedelta
from telegram import Update
from telegram.ext import Application, CommandHandler, MessageHandler, filters, ContextTypes

# Cấu hình bot
TOKEN = "7944488163:AAERF2f3qYI9LO3-f0dBdHdZmEQuEv3JBGM"

# Biến toàn cục
core_admins = [6763308189]  # ID của admin chính
vip_users = set()  # Danh sách người dùng VIP
running_tasks = {}  # Theo dõi các tác vụ đang chạy
waiting_users = {}  # Theo dõi người dùng đang trong thời gian chờ

# Thống kê buff
stats = {
    "total_buff": 0,
    "successful_buff": 0,
    "failed_buff": 0,
    "last_updated": time.time()
}

# Cấu hình lưu trữ key
KEY_STORAGE_DIR = "freefire_keys"  # Thư mục lưu trữ file xác thực key
os.makedirs(KEY_STORAGE_DIR, exist_ok=True)

# Tạo file key.txt để lưu trữ
KEY_FILE = "ffkey.txt"
if not os.path.exists(KEY_FILE):
    with open(KEY_FILE, 'w') as f:
        f.write('')

# Hàm trợ giúp
def TimeStamp():
    """Lấy ngày hiện tại dưới dạng chuỗi (DD-MM-YYYY) theo múi giờ Việt Nam (GMT+7)"""
    vietnam_time = datetime.now() + timedelta(hours=7)
    return vietnam_time.strftime('%d-%m-%Y')

def auto_delete_message(chat_id, message_id, delay=15):
    """Tự động xóa tin nhắn sau một khoảng thời gian"""
    def delete_message():
        time.sleep(delay)
        try:
            bot.delete_message(chat_id, message_id)
        except Exception as e:
            print(f"Không thể xóa tin nhắn: {e}")
    
    # Tạo một luồng mới để xóa tin nhắn sau delay giây
    threading.Thread(target=delete_message, daemon=True).start()

def admin_auto_delete(func):
    """Decorator tự động xóa tin nhắn phản hồi cho admin sau 15 giây"""
    @wraps(func)
    def wrapper(message, *args, **kwargs):
        # Gọi hàm gốc
        response = func(message, *args, **kwargs)
        
        # Nếu tin nhắn từ admin, tự động xóa phản hồi sau 15 giây
        if is_admin(message.from_user.id) and hasattr(response, 'message_id'):
            auto_delete_message(message.chat.id, response.message_id)
        
        return response
    return wrapper

def is_key_valid(user_id):
    """Kiểm tra xem người dùng có key hợp lệ cho ngày hôm nay không"""
    today = TimeStamp()
    user_folder = f"{KEY_STORAGE_DIR}/{today}"
    return os.path.exists(f"{user_folder}/{user_id}.txt")

def is_admin(user_id):
    """Kiểm tra xem người dùng có phải là admin không"""
    return user_id in core_admins
    
def is_vip(user_id):
    """Kiểm tra xem người dùng có phải là VIP không"""
    return user_id in vip_users

def add_vip(user_id):
    """Thêm người dùng vào danh sách VIP"""
    vip_users.add(user_id)
    
    # Lưu file VIP
    with open("ff_vip_users.txt", "a") as f:
        f.write(f"{user_id}\n")
        
def load_vip_users():
    """Load danh sách người dùng VIP từ file"""
    if os.path.exists("ff_vip_users.txt"):
        with open("ff_vip_users.txt", "r") as f:
            for line in f:
                try:
                    user_id = int(line.strip())
                    vip_users.add(user_id)
                except:
                    pass

def update_stats():
    """Cập nhật và gửi thống kê sau mỗi 5 phút"""
    while True:
        time.sleep(300)  # Chờ 5 phút
        vietnam_time = datetime.now() + timedelta(hours=7)
        current_time = vietnam_time.strftime("%H:%M:%S %d/%m/%Y")
        
        # Gửi thống kê cho tất cả admin
        stats_message = f"""```
╭─────────────⭓
│ 📊 THỐNG KÊ BUFF LIKE FREE FIRE
│ ⏰ Cập nhật lúc: {current_time}
│
│ 🚀 Tổng số lệnh buff: {stats['total_buff']}
│ ✅ Buff thành công: {stats['successful_buff']}
│ ❌ Buff thất bại: {stats['failed_buff']}
│ 🔄 Tỷ lệ thành công: {(stats['successful_buff'] / stats['total_buff'] * 100) if stats['total_buff'] > 0 else 0:.2f}%
╰─────────────⭓
```"""
        
        for admin_id in core_admins:
            try:
                bot.send_message(admin_id, stats_message, parse_mode="Markdown")
            except Exception as e:
                print(f"Không thể gửi thống kê cho admin {admin_id}: {e}")

def get_ff_info(uid):
    """Lấy thông tin tài khoản Free Fire từ API"""
    try:
        keyy = "proAmine"
        api_url = f"https://ff-virusteam.vercel.app/likes2?key={keyy}&uid={uid}"
        response = requests.get(api_url, timeout=10)
        
        if response.status_code == 200:
            data = response.json()
            if isinstance(data.get("message"), dict):
                user_data = data.get("message", {})
                return {
                    'success': True,
                    'name': user_data.get('Name', ''),
                    'uid': user_data.get('UID', ''),
                    'level': user_data.get('Level', ''),
                    'region': user_data.get('Region', ''),
                    'likes_before': user_data.get('Likes Before', 0),
                    'likes_after': user_data.get('Likes After', 0),
                    'likes_added': user_data.get('Likes Added', 0),
                    'time_sent': user_data.get('Time Sent', ''),
                }
            else:
                return {
                    'success': False,
                    'error': f"UID {uid} đã đạt giới hạn like hàng ngày hoặc không tìm thấy."
                }
        else:
            return {
                'success': False,
                'error': f"Lỗi máy chủ: {response.status_code}"
            }
    except Exception as e:
        print(f"Lỗi khi lấy thông tin Free Fire: {e}")
        return {
            'success': False,
            'error': str(e)
        }

def buff_like(uid, chat_id):
    """Thực hiện tăng like cho UID Free Fire"""
    # Cập nhật thống kê
    stats["total_buff"] += 1
    
    try:
        # Gửi thông báo đang xử lý
        bot.send_message(chat_id, f"""```
╭─────────────⭓
│ 🔄 Đang xử lý buff like cho UID: {uid}
│ ⏳ Vui lòng chờ trong giây lát...
╰─────────────⭓
```""", parse_mode="Markdown")
        
        # Sử dụng API để buff like
        info = get_ff_info(uid)
        
        if info.get('success'):
            # Buff thành công
            bot.send_message(chat_id, f"""```
╭─────────────⭓
│ ✅ BUFF LIKE FREE FIRE THÀNH CÔNG!
│
│ 📋 Thông tin tài khoản:
│ 👤 Tên: {info.get('name')}
│ 🆔 UID: {info.get('uid')}
│ 🎯 Level: {info.get('level')}
│ 🌍 Khu vực: {info.get('region')}
│
│ ❤️ Like trước: {info.get('likes_before')}
│ 👍 Like sau: {info.get('likes_after')}
│ ➕ Đã thêm: {info.get('likes_added')} like
│ ⚡ Tốc độ: {info.get('time_sent')}
╰─────────────⭓
```""", parse_mode="Markdown")
            
            stats["successful_buff"] += 1
        else:
            # Buff thất bại
            error_msg = info.get('error', 'Lỗi không xác định')
            bot.send_message(chat_id, f"""```
╭─────────────⭓
│ ❌ Buff like thất bại:
│ {error_msg}
╰─────────────⭓
```""", parse_mode="Markdown")
            
            stats["failed_buff"] += 1
            
    except Exception as e:
        print(f"Lỗi trong buff_like: {e}")
        bot.send_message(chat_id, f"""```
╭─────────────⭓
│ ❌ Đã xảy ra lỗi khi buff like cho UID {uid}. 
│ Vui lòng thử lại sau.
╰─────────────⭓
```""", parse_mode="Markdown")
        stats["failed_buff"] += 1
    finally:
        # Dọn dẹp tác vụ đang chạy
        if (chat_id, uid) in running_tasks:
            del running_tasks[(chat_id, uid)]

# Command handlers
@bot.message_handler(commands=['start'])
def start_command(message):
    """Xử lý lệnh /start"""
    user_id = message.from_user.id
    username = message.from_user.username or "Khách"
    
    welcome_text = f"""```
╭─────────────⭓
│ 👋 Chào mừng, {username}!
│
│ 🤖 Bot này giúp bạn tăng like Free Fire.
│
│ 🔹 LỆNH THƯỜNG (CẦN KEY):
│ 🔑 /getkey - Lấy key để kích hoạt bot
│ 🔓 /key [key] - Kích hoạt bot với key
│ 🚀 /like [UID] - Tăng like Free Fire
│
│ 🔹 LỆNH KHÁC:
│ 💎 /muavip - Xem thông tin gói VIP
│ ❓ /help - Hiển thị trợ giúp
│
│ ❗ Lưu ý: Lệnh /like cần key hợp lệ
│ 💼 Admin: @liggdzut1
╰─────────────⭓
```"""
    bot.send_message(message.chat.id, welcome_text, parse_mode="Markdown")

@bot.message_handler(commands=['help'])
def help_command(message):
    """Xử lý lệnh /help"""
    help_text = """```
╭─────────────⭓
│ 📚 LỆNH BOT FREE FIRE:
│
│ 🔹 LỆNH THƯỜNG (CẦN KEY):
│ 🔑 /getkey - Tạo key duy nhất có hiệu lực 24 giờ
│ 🔓 /key [key] - Kích hoạt bot bằng key của bạn
│ 🚀 /like [UID] - Tăng like cho UID Free Fire
│
│ 🔹 LỆNH KHÁC:
│ 💎 /muavip - Xem thông tin gói VIP
│
│ ❗️ LƯU Ý:
│ - Mỗi key có hiệu lực trong 24 giờ
│ - Lệnh /like cần key hợp lệ để sử dụng
│ - Mỗi UID chỉ có thể buff 1 lần mỗi ngày
╰─────────────⭓
```"""
    bot.send_message(message.chat.id, help_text, parse_mode="Markdown")

@bot.message_handler(commands=['getkey'])
def get_key_command(message):
    """Xử lý lệnh /getkey"""
    bot.reply_to(message, """```
╭─────────────⭓
│ ⏳ Đang tạo key, vui lòng chờ...
╰─────────────⭓
```""", parse_mode="Markdown")
    
    user_id = message.from_user.id
    username = message.from_user.username or "Khách"
    timestamp = int(time.time())
    
    # Tạo key sử dụng hash MD5
    string = f'freefire-{username}-{random.randint(1000, 9999)}'
    hash_object = hashlib.md5(string.encode())
    key = hash_object.hexdigest()[:12]
    
    # Lưu key vào file
    with open(KEY_FILE, 'a') as f:
        f.write(f'{key}\n')
    
    # Thông báo cho admin
    for admin_id in core_admins:
        try:
            bot.send_message(admin_id, f"""```
╭─────────────⭓
│ 🔑 Key Free Fire mới được tạo:
│ 👤 User: {username} ({user_id})
│ 🔐 Key: {key}
╰─────────────⭓
```""", parse_mode="Markdown")
        except Exception as e:
            print(f"Không thể thông báo cho admin {admin_id}: {e}")
    
    # Gửi key cho người dùng
    key_text = f"""```
╭─────────────⭓
│ 🔑 Key Free Fire của bạn đã được tạo!
│
│ 🔐 Key: {key}
│ ⏳ Thời hạn Key: 24 giờ
│ 🛠 Nhập Key bằng lệnh: /key {key}
│
│ ❗ Lưu ý: Mỗi key chỉ dùng được một lần!
╰─────────────⭓
```"""
    bot.reply_to(message, key_text, parse_mode="Markdown")

@bot.message_handler(commands=['key'])
def key_command(message):
    """Xử lý lệnh /key"""
    if len(message.text.split()) == 1:
        bot.reply_to(message, """```
╭─────────────⭓
│ ❗ Vui lòng nhập Key!
│ Ví dụ: /key abc123def456
╰─────────────⭓
```""", parse_mode="Markdown")
        return
    
    user_id = message.from_user.id
    key_input = message.text.split()[1]
    
    # Kiểm tra key trong file
    try:
        with open(KEY_FILE, 'r') as f:
            keys = f.read().splitlines()

        if key_input in keys:
            # Key hợp lệ, xóa khỏi danh sách
            keys.remove(key_input)
            with open(KEY_FILE, 'w') as f:
                f.write('\n'.join(keys) + '\n')
            
            # Tạo file xác thực cho người dùng
            today = TimeStamp()
            user_folder = f"{KEY_STORAGE_DIR}/{today}"
            os.makedirs(user_folder, exist_ok=True)
            
            vietnam_time = datetime.now() + timedelta(hours=7)
            with open(f"{user_folder}/{user_id}.txt", 'w', encoding='utf-8') as f:
                f.write(f"Da xac thuc key vao: {vietnam_time.strftime('%Y-%m-%d %H:%M:%S')}\n")
                
            bot.reply_to(message, """```
╭─────────────⭓
│ ✅ Xác thực key thành công! Bạn có thể sử dụng bot.
╰─────────────⭓
```""", parse_mode="Markdown")
        else:
            bot.reply_to(message, """```
╭─────────────⭓
│ ❌ Key không hợp lệ hoặc đã hết hạn!
╰─────────────⭓
```""", parse_mode="Markdown")
    except Exception as e:
        print(f"Lỗi xác thực key: {e}")
        bot.reply_to(message, """```
╭─────────────⭓
│ ❌ Lỗi xác thực key! Vui lòng thử lại sau.
╰─────────────⭓
```""", parse_mode="Markdown")

@bot.message_handler(commands=['like'])
def like_command(message):
    """Xử lý lệnh /like"""
    chat_id = message.chat.id
    user_id = message.from_user.id
    args = message.text.split()
    
    # Kiểm tra xem người dùng có key hợp lệ không hoặc là admin/VIP
    if not (is_key_valid(user_id) or is_admin(user_id) or is_vip(user_id)):
        bot.send_message(chat_id, """```
╭─────────────⭓
│ 🔒 Bạn cần có key hợp lệ trước khi sử dụng tính năng này. 
│ Sử dụng /getkey để lấy key và /key [key] để kích hoạt.
╰─────────────⭓
```""", parse_mode="Markdown")
        return
    
    # Kiểm tra định dạng lệnh
    if len(args) != 2:
        bot.send_message(chat_id, """```
╭─────────────⭓
│ 📌 Vui lòng sử dụng đúng định dạng: 
│ /like [UID Free Fire]
╰─────────────⭓
```""", parse_mode="Markdown")
        return
    
    uid = args[1].strip()
    
    # Kiểm tra UID có hợp lệ không
    if not uid.isdigit():
        bot.send_message(chat_id, """```
╭─────────────⭓
│ ❌ UID Free Fire phải là số!
╰─────────────⭓
```""", parse_mode="Markdown")
        return
    
    # Kiểm tra xem đã có tác vụ đang chạy cho người dùng này chưa
    if (chat_id, uid) in running_tasks:
        bot.send_message(chat_id, f"""```
╭─────────────⭓
│ 🚀 Đang buff like cho UID {uid}, vui lòng chờ.
╰─────────────⭓
```""", parse_mode="Markdown")
        return
    
    # Bắt đầu quá trình buff
    bot.send_message(chat_id, f"""```
╭─────────────⭓
│ 🚀 Bắt đầu buff like cho UID {uid}...
╰─────────────⭓
```""", parse_mode="Markdown")
    
    # Sử dụng threading để thực hiện việc buff trong nền
    thread = threading.Thread(target=buff_like, args=(uid, chat_id))
    thread.daemon = True
    thread.start()
    running_tasks[(chat_id, uid)] = thread

@bot.message_handler(commands=['stats'])
@admin_auto_delete
def stats_command(message):
    """Xử lý lệnh /stats - chỉ dành cho admin"""
    user_id = message.from_user.id
    
    if not is_admin(user_id):
        return bot.reply_to(message, """```
╭─────────────⭓
│ ⛔ Bạn không có quyền sử dụng lệnh này.
╰─────────────⭓
```""", parse_mode="Markdown")
    
    vietnam_time = datetime.now() + timedelta(hours=7)
    current_time = vietnam_time.strftime("%H:%M:%S %d/%m/%Y")
    stats_message = f"""```
╭─────────────⭓
│ 📊 THỐNG KÊ BUFF LIKE FREE FIRE
│ ⏰ Cập nhật lúc: {current_time}
│
│ 🚀 Tổng số lệnh buff: {stats['total_buff']}
│ ✅ Buff thành công: {stats['successful_buff']}
│ ❌ Buff thất bại: {stats['failed_buff']}
│ 🔄 Tỷ lệ thành công: {(stats['successful_buff'] / stats['total_buff'] * 100) if stats['total_buff'] > 0 else 0:.2f}%
╰─────────────⭓
```"""
    
    return bot.reply_to(message, stats_message, parse_mode="Markdown")

@bot.message_handler(commands=['muavip', 'vip'])
def muavip_command(message):
    """Xử lý lệnh /muavip và /vip - Hiển thị thông tin về gói VIP"""
    vip_info = """```
╭─────────────⭓
│ 💎 THÔNG TIN GÓI VIP FREE FIRE 💎
│
│ ⭐ ĐẶC QUYỀN THÀNH VIÊN VIP:
│ ✅ Không cần key để sử dụng bot
│ ✅ Không giới hạn số lần buff mỗi ngày
│ ✅ Ưu tiên máy chủ buff like nhanh hơn
│ ✅ Hỗ trợ kỹ thuật 24/7
│ ✅ Thêm tính năng VIP mới liên tục
│
│ 💰 CHI PHÍ:
│ • 1 tuần: 50.000 VNĐ
│ • 1 tháng: 100.000 VNĐ
│ • 3 tháng: 200.000 VNĐ
│ • 6 tháng: 350.000 VNĐ
│ • 1 năm: 500.000 VNĐ
│
│ 📱 LIÊN HỆ ĐỂ MUA VIP:
│ 👉 Telegram: @liggdzut1
╰─────────────⭓
```"""
    bot.reply_to(message, vip_info, parse_mode="Markdown")

# Xử lý tin nhắn không phải lệnh
@bot.message_handler(func=lambda message: True)
def default_handler(message):
    """Xử lý bất kỳ tin nhắn nào khác"""
    bot.reply_to(message, """```
╭─────────────⭓
│ ❓ Vui lòng sử dụng lệnh /help để xem hướng dẫn.
╰─────────────⭓
```""", parse_mode="Markdown")

# Hàm chính
if __name__ == "__main__":
    print("Starting Free Fire Like Bot...")
    try:
        # Đảm bảo thư mục lưu trữ key tồn tại
        os.makedirs(KEY_STORAGE_DIR, exist_ok=True)
        
        # Load danh sách VIP
        load_vip_users()
        
        # Bắt đầu luồng cập nhật thống kê
        stats_thread = threading.Thread(target=update_stats, daemon=True)
        stats_thread.start()
        
        # Bắt đầu bot
        bot.infinity_polling(timeout=60, long_polling_timeout=1)
    except Exception as e:
        print(f"Bot error: {e}")