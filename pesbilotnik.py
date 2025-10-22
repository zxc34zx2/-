import asyncio
import logging
from datetime import datetime
import sqlite3
from telegram import Update
from telegram.ext import Application, CommandHandler, ContextTypes
import random

# Настройка логирования
logging.basicConfig(
    format='%(asctime)s - %(name)s - %(levelname)s - %(message)s',
    level=logging.INFO
)
logger = logging.getLogger(__name__)

class DroneAlertBot:
    def __init__(self, token: str):
        self.token = token
        self.db_path = "drone_alerts.db"
        self.init_database()
        
        # Локации для мониторинга в Татарстане
        self.monitoring_locations = [
            "Казань", "Набережные Челны", "Альметьевск", "Нижнекамск", 
            "Зеленодольск", "Бугульма", "Елабуга", "Лениногорск", "Чистополь"
        ]
        
    def init_database(self):
        """Инициализация базы данных для хранения подписчиков"""
        conn = sqlite3.connect(self.db_path)
        cursor = conn.cursor()
        cursor.execute('''
            CREATE TABLE IF NOT EXISTS subscribers (
                user_id INTEGER PRIMARY KEY,
                chat_id INTEGER,
                username TEXT,
                first_name TEXT,
                last_name TEXT,
                subscribed_at TIMESTAMP DEFAULT CURRENT_TIMESTAMP,
                is_active BOOLEAN DEFAULT TRUE
            )
        ''')
        cursor.execute('''
            CREATE TABLE IF NOT EXISTS alert_history (
                id INTEGER PRIMARY KEY AUTOINCREMENT,
                alert_type TEXT,
                location TEXT,
                description TEXT,
                severity TEXT,
                created_at TIMESTAMP DEFAULT CURRENT_TIMESTAMP
            )
        ''')
        conn.commit()
        conn.close()

    async def add_subscriber(self, user_id: int, chat_id: int, username: str, 
                           first_name: str, last_name: str):
        """Добавление подписчика в базу данных"""
        conn = sqlite3.connect(self.db_path)
        cursor = conn.cursor()
        cursor.execute('''
            INSERT OR REPLACE INTO subscribers 
            (user_id, chat_id, username, first_name, last_name, is_active)
            VALUES (?, ?, ?, ?, ?, TRUE)
        ''', (user_id, chat_id, username, first_name, last_name))
        conn.commit()
        conn.close()

    async def remove_subscriber(self, user_id: int):
        """Удаление подписчика"""
        conn = sqlite3.connect(self.db_path)
        cursor = conn.cursor()
        cursor.execute('UPDATE subscribers SET is_active = FALSE WHERE user_id = ?', (user_id,))
        conn.commit()
        conn.close()

    async def get_active_subscribers(self):
        """Получение списка активных подписчиков"""
        conn = sqlite3.connect(self.db_path)
        cursor = conn.cursor()
        cursor.execute('SELECT chat_id FROM subscribers WHERE is_active = TRUE')
        subscribers = [row[0] for row in cursor.fetchall()]
        conn.close()
        return subscribers

    async def save_alert(self, alert_type: str, location: str, description: str, severity: str):
        """Сохранение уведомления в историю"""
        conn = sqlite3.connect(self.db_path)
        cursor = conn.cursor()
        cursor.execute('''
            INSERT INTO alert_history (alert_type, location, description, severity)
            VALUES (?, ?, ?, ?)
        ''', (alert_type, location, description, severity))
        conn.commit()
        conn.close()

    def get_severity_emoji(self, severity: str) -> str:
        """Получение emoji для уровня опасности"""
        emoji_map = {
            "critical": "🚨",
            "high": "⚠️", 
            "medium": "🔶",
            "low": "💡"
        }
        return emoji_map.get(severity.lower(), "📢")

    async def start_command(self, update: Update, context: ContextTypes.DEFAULT_TYPE):
        """Обработчик команды /start"""
        user = update.effective_user
        await self.add_subscriber(
            user.id, 
            update.effective_chat.id,
            user.username or "", 
            user.first_name or "",
            user.last_name or ""
        )
        
        welcome_text = """
🚨 *Система оповещения о беспилотной опасности в Республике Татарстан*

Вы успешно подписались на уведомления о беспилотных летательных аппаратах.

*Доступные команды:*
/start - Подписаться на уведомления
/stop - Отписаться от уведомлений
/status - Статус системы
/alerts - Последние уведомления
/help - Помощь

*Типы уведомлений:*
• 🚨 Критическая опасность
• ⚠️ Высокая опасность  
• 🔶 Средняя опасность
• 💡 Информационное сообщение

Будьте бдительны и соблюдайте меры безопасности!
CEO: @Lekroqq
        """
        await update.message.reply_text(welcome_text, parse_mode='Markdown')

    async def stop_command(self, update: Update, context: ContextTypes.DEFAULT_TYPE):
        """Обработчик команды /stop"""
        user = update.effective_user
        await self.remove_subscriber(user.id)
        
        stop_text = """
✅ Вы отписались от уведомлений о беспилотной опасности.

Чтобы снова подписаться, используйте команду /start

Берегите себя!
        """
        await update.message.reply_text(stop_text, parse_mode='Markdown')

    async def status_command(self, update: Update, context: ContextTypes.DEFAULT_TYPE):
        """Обработчик команды /status"""
        subscribers = await self.get_active_subscribers()
        
        status_text = f"""
📊 *Статус системы оповещения*

• 🤖 Бот активен
• 👥 Подписчиков: {len(subscribers)}
• 🟢 Система работает в штатном режиме
• 📍 Республика Татарстан

*Последняя проверка:* {datetime.now().strftime('%d.%m.%Y %H:%M')}
        """
        await update.message.reply_text(status_text, parse_mode='Markdown')

    async def alerts_command(self, update: Update, context: ContextTypes.DEFAULT_TYPE):
        """Обработчик команды /alerts - последние уведомления"""
        conn = sqlite3.connect(self.db_path)
        cursor = conn.cursor()
        cursor.execute('''
            SELECT alert_type, location, description, severity, created_at 
            FROM alert_history 
            ORDER BY created_at DESC 
            LIMIT 5
        ''')
        alerts = cursor.fetchall()
        conn.close()
        
        if not alerts:
            await update.message.reply_text("📭 Нет последних уведомлений")
            return
        
        alerts_text = "📋 *Последние уведомления:*\n\n"
        for alert in alerts:
            alert_type, location, description, severity, created_at = alert
            emoji = self.get_severity_emoji(severity)
            alerts_text += f"{emoji} *{alert_type}* ({severity})\n"
            alerts_text += f"📍 *Место:* {location}\n"
            alerts_text += f"📝 *Описание:* {description}\n"
            alerts_text += f"🕒 *Время:* {created_at}\n\n"
        
        await update.message.reply_text(alerts_text, parse_mode='Markdown')

    async def help_command(self, update: Update, context: ContextTypes.DEFAULT_TYPE):
        """Обработчик команды /help"""
        help_text = """
🆘 *Помощь по системе оповещения*

*Команды бота:*
/start - Подписаться на уведомления
/stop - Отписаться от уведомлений  
/status - Статус системы
/alerts - Последние уведомления
/help - Эта справка

*Что делать при получении уведомления:*
1. Немедленно проследуйте в укрытие
2. Сообщите окружающим об опасности
3. Следуйте инструкциям местных властей
4. Не приближайтесь к месту происшествия

*Контакты экстренных служб:*
112 - Единый номер экстренных служб
117 - Для сообщение минобороны нахождения БПЛА

*Зоны повышенного риска в РТ:*
• Ключевые инфраструктурные объекты
• Городские центры
• Промышленные зоны
        """
        await update.message.reply_text(help_text, parse_mode='Markdown')

    async def send_alert(self, alert_type: str, location: str, description: str, 
                        severity: str = "medium", context: ContextTypes.DEFAULT_TYPE = None):
        """Отправка уведомления всем подписчикам"""
        subscribers = await self.get_active_subscribers()
        
        if not subscribers:
            logger.warning("Нет активных подписчиков для отправки уведомления")
            return
        
        emoji = self.get_severity_emoji(severity)
        
        alert_message = f"""
{emoji} *УВЕДОМЛЕНИЕ О БЕСПИЛОТНОЙ ОПАСНОСТИ* {emoji}

*Тип:* {alert_type}
*Уровень опасности:* {severity.upper()}
*Место:* {location}
*Описание:* {description}

*Рекомендации:*
• Немедленно проследуйте в укрытие
• Сообщите окружающим об опасности
• Следуйте инструкциям местных властей

*Время оповещения:* {datetime.now().strftime('%d.%m.%Y %H:%M')}
📍 Республика Татарстан
        """
        
        # Сохраняем уведомление в историю
        await self.save_alert(alert_type, location, description, severity)
        
        # Отправляем всем подписчикам
        successful_sends = 0
        
        for chat_id in subscribers:
            try:
                await context.bot.send_message(
                    chat_id=chat_id,
                    text=alert_message,
                    parse_mode='Markdown'
                )
                successful_sends += 1
                await asyncio.sleep(0.1)  # Задержка чтобы не превысить лимиты Telegram
            except Exception as e:
                logger.error(f"Ошибка отправки уведомления для {chat_id}: {e}")
        
        logger.info(f"Уведомление отправлено {successful_sends} из {len(subscribers)} подписчиков")

    async def test_alert_command(self, update: Update, context: ContextTypes.DEFAULT_TYPE):
        """Симуляция тестового уведомления"""
        location = random.choice(self.monitoring_locations)
        alert_types = [
            "Обнаружение беспилотного аппарата",
            "Нарушение воздушного пространства", 
            "Потенциальная угроза БПЛА"
        ]
        
        await self.send_alert(
            alert_type="ТЕСТ: " + random.choice(alert_types),
            location=location,
            description="Проверка системы оповещения. Это тестовое сообщение.",
            severity="low",
            context=context
        )
        await update.message.reply_text("✅ Тестовое уведомление отправлено всем подписчикам")

    async def simulate_random_alert(self, context: ContextTypes.DEFAULT_TYPE):
        """Симуляция случайного уведомления для демонстрации"""
        subscribers = await self.get_active_subscribers()
        
        if not subscribers:
            return
            
        # 10% шанс сгенерировать уведомление при проверке
        if random.random() < 0.1:
            location = random.choice(self.monitoring_locations)
            alert_types = [
                "Обнаружение беспилотного аппарата",
                "Нарушение воздушного пространства", 
                "Потенциальная угроза БПЛА",
                "Активность беспилотных систем"
            ]
            severity_levels = ["medium", "high"]
            
            await self.send_alert(
                alert_type=random.choice(alert_types),
                location=location,
                description=f"Зафиксирована активность беспилотных летательных аппаратов в районе {location}. Рекомендуется соблюдать осторожность.",
                severity=random.choice(severity_levels),
                context=context
            )

    async def periodic_check(self, context: ContextTypes.DEFAULT_TYPE):
        """Периодическая проверка для симуляции уведомлений"""
        await self.simulate_random_alert(context)

def main():
    """Основная функция запуска бота"""
    # ⚠️ ЗАМЕНИТЕ ЭТОТ ТОКЕН НА ВАШ РЕАЛЬНЫЙ ТОКЕН ⚠️
    BOT_TOKEN = "8200731966:AAFmXTfvQd_PIrkiXv3YA8LS1LEqsud4dlc"  # <-- ВСТАВЬТЕ ВАШ ТОКЕН ЗДЕСЬ
    
    # Проверяем, не остался ли стандартный токен
    if "YOUR_BOT_TOKEN_HERE" in BOT_TOKEN or len(BOT_TOKEN) < 10:
        print("❌ Пожалуйста, установите реальный токен бота!")
        print(f"Текущий токен: {BOT_TOKEN}")
        return
    
    try:
        # Создаем приложение
        application = Application.builder().token(BOT_TOKEN).build()
        
        # Создаем экземпляр бота
        bot = DroneAlertBot(BOT_TOKEN)
        
        # Добавляем обработчики команд
        application.add_handler(CommandHandler("start", bot.start_command))
        application.add_handler(CommandHandler("stop", bot.stop_command))
        application.add_handler(CommandHandler("status", bot.status_command))
        application.add_handler(CommandHandler("alerts", bot.alerts_command))
        application.add_handler(CommandHandler("help", bot.help_command))
        application.add_handler(CommandHandler("test_alert", bot.test_alert_command))
        
        # Настраиваем периодическую проверку для демонстрации
        job_queue = application.job_queue
        if job_queue:
            job_queue.run_repeating(bot.periodic_check, interval=300, first=10)  # Каждые 5 минут
        
        # Запускаем бота
        print("🤖 Бот запускается...")
        print("📍 Система оповещения о беспилотной опасности в Республике Татарстан")
        print("📊 Команды: /start, /stop, /status, /alerts, /help, /test_alert")
        print("🚀 Бот активен и готов к работе!")
        
        application.run_polling()
        
    except Exception as e:
        print(f"❌ Ошибка при запуске бота: {e}")
        print("Проверьте правильность токена и подключение к интернету")

if __name__ == "__main__":
    main()