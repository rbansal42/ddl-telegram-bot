import os
import re
from telebot import TeleBot, types
from database.db import BotDB
from commands import CMD_REGISTER

def register_registration_handlers(bot: TeleBot):
    db = BotDB()
    
    def is_admin(user_id):
        admin_ids_str = os.getenv("ADMIN_IDS", "")
        admin_ids = [int(id.strip()) for id in admin_ids_str.split(",") if id.strip()]
        return user_id in admin_ids
    
    @bot.message_handler(commands=[CMD_REGISTER])
    def start_registration(message: types.Message):
        """Handler for the initial /register command"""
        try:
            # Get user info
            user_id = message.from_user.id
            username = message.from_user.username
            first_name = message.from_user.first_name
            last_name = message.from_user.last_name
            
            print(f"\n=== Starting Registration Process ===")
            print(f"User ID: {user_id}")
            print(f"Username: {username}")
            print(f"First Name: {first_name}")
            print(f"Last Name: {last_name}")
            
            # Check if user is already registered
            if db.is_user_registered(user_id):
                print(f"❌ User {user_id} is already registered")
                bot.reply_to(message, "You are already registered! 🎉")
                return
            
            # Add basic user info to database
            success = db.add_user(
                user_id=user_id,
                username=username,
                first_name=first_name,
                last_name=last_name
            )
            
            if success:
                print(f"✅ Successfully added user {user_id} to database")
            else:
                print(f"❌ Failed to add user {user_id} to database")
            
            # Send welcome message and register next step
            msg = bot.reply_to(
                message,
                "🎉 Registration process started!\n\nPlease enter your full name:"
            )
            
            # Register the next step handler
            bot.register_next_step_handler(msg, process_name)
            
        except Exception as e:
            print(f"❌ Error in start_registration: {e}")
            bot.reply_to(message, "❌ Sorry, an error occurred. Please try again later.")

    def process_name(message: types.Message):
        """Handler for processing the name input"""
        print(f"\n=== Processing Name ===")
        print(f"User ID: {message.from_user.id}")
        print(f"Received name: {message.text}")
        
        try:
            name = message.text.strip()
            if len(name) < 2:
                print("❌ Name too short, asking again")
                msg = bot.reply_to(message, "Please enter a valid name (at least 2 characters).")
                bot.register_next_step_handler(msg, process_name)
                return

            print(f"✅ Valid name received: {name}")
            # Ask for email
            msg = bot.reply_to(
                message, 
                f"Thanks {name}! Now please enter your email address:"
            )
            # Pass the name to the next handler
            bot.register_next_step_handler(msg, process_email, name=name)
            
        except Exception as e:
            print(f"❌ Error in process_name: {e}")
            bot.reply_to(message, "❌ Sorry, an error occurred. Please try again.")

    def process_email(message: types.Message, name: str):
        """Handler for processing the email input"""
        print(f"\n=== Processing Email ===")
        print(f"User ID: {message.from_user.id}")
        print(f"Name: {name}")
        print(f"Received email: {message.text}")
        
        try:
            email = message.text.strip()
            
            # Basic email validation
            email_pattern = r'^[a-zA-Z0-9._%+-]+@[a-zA-Z0-9.-]+\.[a-zA-Z]{2,}$'
            if not re.match(email_pattern, email):
                print("❌ Invalid email format, asking again")
                msg = bot.reply_to(message, "Please enter a valid email address.")
                bot.register_next_step_handler(msg, process_email, name=name)
                return

            print(f"✅ Valid email received: {email}")
            print("Creating registration request...")
            
            # Create registration request in database
            success = db.create_registration_request(message.from_user.id, email, name)
            
            if success:
                print("✅ Registration request created successfully")
                bot.reply_to(
                    message,
                    f"✅ Registration submitted successfully!\n\n"
                    f"Name: {name}\n"
                    f"Email: {email}\n\n"
                    f"Your registration will be reviewed by an admin."
                )
            else:
                print("❌ Failed to create registration request")
                bot.reply_to(message, "❌ Sorry, there was an error submitting your registration.")
            
        except Exception as e:
            print(f"❌ Error in process_email: {e}")
            bot.reply_to(message, "❌ Sorry, an error occurred. Please try again.")

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
                
            for user_id, username, first_name, last_name, email, _, _, request_id in pending:
                markup = types.InlineKeyboardMarkup()
                markup.row(
                    types.InlineKeyboardButton("✅ Approve", callback_data=f"approve_{request_id}"),
                    types.InlineKeyboardButton("❌ Reject", callback_data=f"reject_{request_id}")
                )
                
                text = (
                    f"📝 Registration Request #{request_id}\n"
                    f"User ID: {user_id}\n"
                    f"Username: @{username}\n"
                    f"Name: {first_name} {last_name}\n"
                    f"Email: {email}"
                )
                
                bot.send_message(message.chat.id, text, reply_markup=markup)
                
        except Exception as e:
            print(f"❌ Error in list_pending_registrations: {e}")
            bot.reply_to(message, "❌ Error fetching pending registrations.")

    @bot.callback_query_handler(func=lambda call: call.data.startswith(('approve_', 'reject_')))
    def handle_registration_decision(call: types.CallbackQuery):
        """Handler for registration approval/rejection callbacks"""
        try:
            if not is_admin(call.from_user.id):
                bot.answer_callback_query(call.id, "❌ You are not authorized to do this.")
                return
                
            action, request_id = call.data.split('_')
            request_id = int(request_id)
            
            print(f"\n=== Processing Registration Decision ===")
            print(f"Action: {action}")
            print(f"Request ID: {request_id}")
            
            success = db.process_registration(
                request_id=request_id,
                admin_id=call.from_user.id,
                approved=(action == 'approve'),
                response=f"Registration {action}d by admin"
            )
            
            if success:
                print(f"✅ Successfully {action}d registration")
                bot.edit_message_reply_markup(
                    call.message.chat.id,
                    call.message.message_id,
                    reply_markup=None
                )
                bot.edit_message_text(
                    f"{call.message.text}\n\n{'✅ Approved' if action == 'approve' else '❌ Rejected'} by admin.",
                    call.message.chat.id,
                    call.message.message_id
                )
            else:
                print(f"❌ Failed to {action} registration")
                bot.answer_callback_query(call.id, f"Error processing registration {action}.")
                
        except Exception as e:
            print(f"❌ Error in handle_registration_decision: {e}")
            bot.answer_callback_query(call.id, "❌ Error processing your decision.")