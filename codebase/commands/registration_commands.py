from telebot import TeleBot
from telebot.handler_backends import State, StatesGroup
from database.db import BotDB

class RegistrationState(StatesGroup):
    waiting_for_email = State()
    waiting_for_organization = State()
    waiting_for_reason = State()

def register_registration_handlers(bot: TeleBot):
    db = BotDB()

    @bot.message_handler(commands=['register'])
    def start_registration(message):
        user_id = message.from_user.id
        msg = bot.reply_to(message, "Please enter your email address:")
        bot.set_state(user_id, RegistrationState.waiting_for_email, message.chat.id)

    @bot.message_handler(state=RegistrationState.waiting_for_email)
    def process_email(message):
        email = message.text.strip()
        if '@' not in email:
            bot.reply_to(message, "Please enter a valid email address.")
            return
        
        bot.set_state(message.from_user.id, RegistrationState.waiting_for_organization, message.chat.id)
        with bot.retrieve_data(message.from_user.id, message.chat.id) as data:
            data['email'] = email
        
        bot.reply_to(message, "Please enter your organization name:")

    @bot.message_handler(state=RegistrationState.waiting_for_organization)
    def process_organization(message):
        with bot.retrieve_data(message.from_user.id, message.chat.id) as data:
            data['organization'] = message.text.strip()
        
        bot.set_state(message.from_user.id, RegistrationState.waiting_for_reason, message.chat.id)
        bot.reply_to(message, "Please explain why you need access to this bot:")

    @bot.message_handler(state=RegistrationState.waiting_for_reason)
    def process_reason(message):
        with bot.retrieve_data(message.from_user.id, message.chat.id) as data:
            db.create_registration_request(
                message.from_user.id,
                data['email'],
                data['organization'],
                message.text.strip()
            )
        
        bot.delete_state(message.from_user.id, message.chat.id)
        bot.reply_to(message, "Thank you for your registration request. An administrator will review it soon.")
        notify_admins_about_registration(message.from_user.id)

    def notify_admins_about_registration(user_id):
        admin_ids = [int(id) for id in os.getenv("ADMIN_IDS", "").split(",") if id]
        user_info = bot.get_chat_member(user_id, user_id).user
        
        notification = (
            f"New registration request from:\n"
            f"User: {user_info.first_name} {user_info.last_name or ''}\n"
            f"Username: @{user_info.username or 'N/A'}\n"
            f"ID: {user_id}\n\n"
            f"Use /approve {user_id} or /reject {user_id} to process this request."
        )
        
        for admin_id in admin_ids:
            try:
                bot.send_message(admin_id, notification)
            except Exception as e:
                print(f"Failed to notify admin {admin_id}: {e}")

    @bot.message_handler(commands=['approve', 'reject'])
    def handle_registration_response(message):
        if not is_admin(message.from_user.id):
            bot.reply_to(message, "This command is only available to administrators.")
            return

        parts = message.text.split(maxsplit=2)
        if len(parts) < 2:
            bot.reply_to(message, "Please provide a request ID. Usage: /approve <id> [reason] or /reject <id> [reason]")
            return

        request_id = parts[1]
        reason = parts[2] if len(parts) > 2 else "No reason provided."
        approved = message.text.startswith('/approve')
        
        if db.process_registration(request_id, message.from_user.id, approved, reason):
            status = "approved" if approved else "rejected"
            bot.reply_to(message, f"Registration request {request_id} has been {status}.")
        else:
            bot.reply_to(message, "Failed to process registration request.") 