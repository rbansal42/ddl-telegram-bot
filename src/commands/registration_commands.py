import os
import re
from telebot import TeleBot, types
from src.database.mongo_db import MongoDB
from src.commands import CMD_REGISTER
from src.utils.notifications import notify_user
from src.utils.notifications import NotificationType

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
    def list_pending_registrations(message: types.Message):
        """Handler for listing pending registrations (admin only)"""
        try:
            if not is_admin(message.from_user.id):
                bot.reply_to(message, "❌ This command is only available to admins.")
                return
                
            print("\n=== Listing Pending Registrations ===")
            pending = db.get_pending_registrations()
            
            if not pending:
                bot.reply_to(message, "No pending registrations.")
                return
            
            # Send header message
            bot.reply_to(message, "📝 *Pending Registration Requests:*\n", parse_mode="Markdown")
            
            # Create separate message for each registration with inline keyboard
            for user_id, username, first_name, last_name, email, status, request_id in pending:
                markup = types.InlineKeyboardMarkup()
                
                # Create user info button (non-functional, just for display)
                full_name = f"{first_name} {last_name}".strip()
                info_button = types.InlineKeyboardButton(
                    text=f"👤 {full_name} (@{username})",
                    callback_data=f"info_{request_id}"  # This won't do anything
                )
                
                # Create email button (non-functional, just for display)
                email_button = types.InlineKeyboardButton(
                    text=f"📧 {email}",
                    callback_data=f"email_{request_id}"  # This won't do anything
                )
                
                # Create action buttons
                approve_button = types.InlineKeyboardButton(
                    "✅ Approve",
                    callback_data=f"approve_{request_id}"
                )
                reject_button = types.InlineKeyboardButton(
                    "❌ Reject",
                    callback_data=f"reject_{request_id}"
                )
                
                # Add buttons to markup
                markup.add(info_button)  # First row
                markup.add(email_button)  # Second row
                markup.row(approve_button, reject_button)  # Third row
                
                text = (
                    f"*Registration Request #{request_id}*\n"
                    f"User ID: `{user_id}`"
                )
                
                bot.send_message(
                    message.chat.id,
                    text,
                    reply_markup=markup,
                    parse_mode="Markdown"
                )
                
        except Exception as e:
            print(f"❌ Error in list_pending_registrations: {e}")
            bot.reply_to(message, "❌ Error fetching pending registrations.")

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