import os
import re
from telebot import TeleBot, types
from src.database.mongo_db import MongoDB
from src.commands import CMD_REGISTER
from src.utils.notifications import notify_user
from src.utils.notifications import NotificationType
from src.middleware.auth import check_admin_or_owner

def register_registration_handlers(bot: TeleBot):
    db = MongoDB()
    
    def is_admin(user_id):
        admin_ids_str = os.getenv("ADMIN_IDS", "")
        owner_id = os.getenv("OWNER_ID")
        admin_ids = [int(id.strip()) for id in admin_ids_str.split(",") if id.strip()]
        if owner_id:
            admin_ids.append(int(owner_id))
        return user_id in admin_ids
    
    @bot.message_handler(commands=[CMD_REGISTER])
    def handle_register(message):
        """Handle initial registration command"""
        user_id = message.from_user.id
        
        # Check if user is already registered
        if db.is_user_registered(user_id):
            bot.reply_to(message,
                "✅ You are already registered and approved!")
            return
            
        # Check for existing pending request
        existing = db.registration_requests.find_one({
            'user_id': user_id,
            'status': 'pending'
        })
        
        if existing:
            bot.reply_to(message, 
                "⚠️ You already have a pending registration request.\n"
                "Please wait for admin approval.")
            return
            
        bot.reply_to(message, 
            "📝 Registration process started!\n"
            "Please enter your full name (First Last):")
        bot.register_next_step_handler(message, process_fullname)

    def process_fullname(message):
        """Process full name input"""
        full_name = message.text.strip()
        if len(full_name.split()) < 2:
            bot.reply_to(message, 
                "⚠️ Please enter your full name (First Last):")
            bot.register_next_step_handler(message, process_fullname)
            return
            
        user_data = {
            'user_id': message.from_user.id,
            'username': message.from_user.username,
            'first_name': full_name.split()[0],
            'last_name': ' '.join(full_name.split()[1:]),
            'full_name': full_name
        }
        bot.reply_to(message, 
            "📧 Please enter your email address:")
        bot.register_next_step_handler(message, process_email, user_data)

    def process_email(message, user_data):
        """Process email input and create registration request"""
        email = message.text.strip()
        if '@' not in email:
            bot.reply_to(message, 
                "⚠️ Please enter a valid email address:")
            bot.register_next_step_handler(message, process_email, user_data)
            return
            
        # Create registration request
        success = db.create_registration_request(
            user_id=user_data['user_id'],
            username=user_data['username'],
            first_name=user_data['first_name'],
            last_name=user_data['last_name'],
            email=email
        )
        
        if success:
            bot.reply_to(message,
                "✅ Registration request submitted!\n"
                "An admin will review your request shortly.")
            
            # Notify admins
            notify_admins_about_registration(user_data['user_id'])
        else:
            bot.reply_to(message,
                "❌ Error submitting registration request.\n"
                "Please try again later or contact support.")

    @bot.message_handler(commands=['pending'])
    @check_admin_or_owner(bot, db)
    def list_pending_registrations(message):
        """List all pending registration requests"""
        try:
            # Get pending registrations
            pending = db.registration_requests.find({'status': 'pending'})
            pending_list = list(pending)
            
            if not pending_list:
                bot.reply_to(message, "📝 No pending registration requests.")
                return
            
            # Send each request as a separate message with approve/reject buttons
            for request in pending_list:
                # Format user info
                full_name = f"{request.get('first_name', '')} {request.get('last_name', '')}".strip() or 'N/A'
                email = request.get('email', 'N/A')
                request_id = str(request['_id'])
                
                # Create markup with info display and action buttons
                markup = types.InlineKeyboardMarkup(row_width=2)
                # Info button (non-clickable)
                markup.add(
                    types.InlineKeyboardButton(
                        f"👤 {full_name} | 📧 {email}",
                        callback_data=f"info_{request_id}"
                    )
                )
                # Action buttons row
                markup.row(
                    types.InlineKeyboardButton(
                        "✅ Approve",
                        callback_data=f"approve_{request_id}"
                    ),
                    types.InlineKeyboardButton(
                        "❌ Reject",
                        callback_data=f"reject_{request_id}"
                    )
                )
                
                bot.send_message(
                    message.chat.id,
                    "📝 *Registration Request:*",
                    reply_markup=markup,
                    parse_mode="Markdown"
                )
                
        except Exception as e:
            bot.reply_to(message, f"❌ Error listing pending requests: {e}")

    @bot.callback_query_handler(func=lambda call: call.data.startswith(('approve_', 'reject_')))
    def handle_registration_decision(call):
        try:
            action, request_id = call.data.split('_')
            admin_id = call.from_user.id
            
            if not is_admin(admin_id):
                bot.answer_callback_query(call.id, "⛔️ You don't have permission to do this.")
                return

            success, user_id = db.process_registration(
                request_id=request_id,
                admin_id=admin_id,
                approved=(action == 'approve'),
                response=f"{action.capitalize()}d by admin"
            )

            if success:
                status = '✅ Approved' if action == 'approve' else '❌ Rejected'
                bot.edit_message_text(
                    f"Registration {status}",
                    call.message.chat.id,
                    call.message.message_id
                )
                bot.answer_callback_query(call.id, f"Registration {action}d successfully!")
                
                # Notify user about their registration status
                if action == 'approve':
                    notify_user(
                        bot,
                        NotificationType.REGISTRATION_APPROVED,
                        user_id,
                        issuer_id=admin_id
                    )
                else:
                    notify_user(
                        bot,
                        NotificationType.REGISTRATION_REJECTED,
                        user_id,
                        issuer_id=admin_id
                    )
            else:
                print(f"❌ Failed to {action} registration")
                bot.answer_callback_query(call.id, f"Error processing registration {action}.")
            
        except Exception as e:
            print(f"❌ Error in handle_registration_decision: {e}")
            bot.answer_callback_query(call.id, "Error processing registration.")

    def notify_admins_about_registration(user_id):
        """Notify admins (except owner) about new registration request"""
        admin_ids_str = os.getenv("ADMIN_IDS", "")
        owner_id = int(os.getenv("OWNER_ID", "0"))  # Owner's ID
        admin_ids = [int(id.strip()) for id in admin_ids_str.split(",") if id.strip() and int(id.strip()) != owner_id]
        
        for admin_id in admin_ids:
            try:
                bot.send_message(admin_id, 
                    f"🔔 New registration request from user {user_id}\n"
                    f"Use /pending to review registration requests.")
            except Exception as e:
                print(f"Failed to notify admin {admin_id}: {e}")