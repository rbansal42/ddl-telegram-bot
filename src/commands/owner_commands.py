import os
from telebot import TeleBot, types
from src.database.mongo_db import MongoDB
from src.database.roles import Role, Permissions
from src.middleware.auth import check_owner
from src.utils.notifications import notify_user, NotificationType
from src.utils.user_actions import log_action, ActionType
from src.utils.markup_helpers import create_promotion_markup, create_admin_list_markup

def register_owner_handlers(bot: TeleBot):
    db = MongoDB()
    
    @bot.message_handler(commands=['addadmin'])
    @check_owner(bot, db)
    def add_admin(message):
        """Add a new admin user"""
        try:
            args = message.text.split()
            if len(args) == 1:  # No user_id provided
                # Get members query
                members_query = {
                    'registration_status': 'approved',
                    'role': Role.MEMBER.name.lower()
                }
                
                # Execute query
                members = db.users.find(members_query)
                member_list = list(members)
                
                if not member_list:
                    bot.reply_to(message, "📝 No registered members found to promote.")
                    return

                # Create markup
                markup = types.InlineKeyboardMarkup()
                for member in member_list:
                    # Format member info in one line
                    full_name = f"{member.get('first_name', '')} {member.get('last_name', '')}".strip() or 'N/A'
                    email = member.get('email', 'N/A')
                    user_id = member.get('user_id')
                    
                    # Single button with all info
                    markup.add(
                        types.InlineKeyboardButton(
                            f"👤 {full_name} | 📧 {email}",
                            callback_data=f"promote_{user_id}"
                        )
                    )
                
                bot.reply_to(message, 
                    "👥 *Select a member to promote to admin:*",
                    reply_markup=markup,
                    parse_mode="Markdown")
                
            else:
                new_admin_id = int(args[1])
                promote_to_admin(bot, db, message.from_user.id, new_admin_id)
                
        except Exception as e:
            print(f"❌ Error in add_admin: {e}")
            log_action(
                ActionType.COMMAND_FAILED,
                message.from_user.id,
                error_message=str(e),
                metadata={'command': 'addadmin'}
            )
            bot.reply_to(message, f"❌ Error adding admin: {e}")

    @bot.message_handler(commands=['removeadmin'])
    @check_owner(bot, db)
    def remove_admin(message):
        """Remove an admin user"""
        try:
            args = message.text.split()
            if len(args) == 1:  # No user_id provided
                admins = db.users.find(
                    {'role': Role.ADMIN.name.lower()},
                    {
                        'user_id': 1,
                        'username': 1,
                        'first_name': 1,
                        'last_name': 1,
                        'email': 1,
                        'role': 1
                    }
                )
                admin_list = list(admins)
                
                if not admin_list:
                    bot.reply_to(message, "📝 No admins found to demote.")
                    return

                # Create markup
                markup = types.InlineKeyboardMarkup()
                for admin in admin_list:
                    # Format admin info in one line
                    full_name = f"{admin.get('first_name', '')} {admin.get('last_name', '')}".strip() or 'N/A'
                    email = admin.get('email', 'N/A')
                    user_id = admin.get('user_id')
                    
                    # Single button with all info
                    markup.add(
                        types.InlineKeyboardButton(
                            f"👤 {full_name} | 📧 {email}",
                            callback_data=f"demote_{user_id}"
                        )
                    )
                
                bot.reply_to(message, 
                    "👥 *Select an admin to demote:*",
                    reply_markup=markup,
                    parse_mode="Markdown")
            else:
                admin_id = int(args[1])
                demote_to_member(bot, db, message.from_user.id, admin_id)
                
        except Exception as e:
            bot.reply_to(message, f"❌ Error removing admin: {e}")
            
    @bot.callback_query_handler(func=lambda call: call.data.startswith('demote_'))
    def handle_admin_demotion(call):
        try:
            user_id = call.from_user.id
            user = db.users.find_one({'user_id': user_id})
            
            if not user or user.get('role') != Role.OWNER.name.lower():
                bot.answer_callback_query(call.id, "⛔️ This action is only available to the bot owner.")
                return
            
            _, admin_id = call.data.split('_')
            admin_id = int(admin_id)
            
            demote_to_member(bot, db, call.message.chat.id, admin_id)
            
            bot.edit_message_text(
                f"✅ Admin demotion completed.",
                call.message.chat.id,
                call.message.message_id,
                parse_mode="Markdown"
            )
            bot.answer_callback_query(call.id)
            
        except Exception as e:
            bot.answer_callback_query(call.id, f"❌ Error: {str(e)}")

    def demote_to_member(bot, db, chat_id, admin_id):
        """Helper function to demote an admin to member"""
        user = db.users.find_one({'user_id': admin_id})
        
        if not user:
            raise Exception("User not found.")
            
        if user.get('role') != Role.ADMIN.name.lower():
            raise Exception("User is not an admin.")
            
        db.users.update_one(
            {'user_id': admin_id},
            {'$set': {'role': Role.MEMBER.name.lower()}}
        )
        
        bot.send_message(chat_id, f"✅ User {admin_id} has been demoted to member.")
        
        try:
            notify_user(
                bot,
                NotificationType.DEMOTION_TO_MEMBER,
                admin_id,
                issuer_id=chat_id
            )
        except Exception as e:
            print(f"Failed to notify former admin: {e}")

    def promote_to_admin(bot, db, chat_id, member_id):
        """Helper function to promote a member to admin"""
        user = db.users.find_one({'user_id': member_id})
        
        if not user:
            raise Exception("User not found.")
            
        if user.get('role') != Role.MEMBER.name.lower():
            raise Exception("User is not a member.")
            
        db.users.update_one(
            {'user_id': member_id},
            {'$set': {'role': Role.ADMIN.name.lower()}}
        )
        
        bot.send_message(chat_id, f"✅ User {member_id} has been promoted to admin.")
        
        try:
            notify_user(
                bot,
                NotificationType.PROMOTION_TO_ADMIN,
                member_id,
                issuer_id=chat_id
            )
        except Exception as e:
            print(f"Failed to notify new admin: {e}")

    @bot.message_handler(commands=['listadmins'])
    @check_owner(bot, db)
    def list_admins(message):
        """List all admin users"""
        try:
            admins = db.users.find({'role': Role.ADMIN.name.lower()})
            admin_list = list(admins)
            
            if not admin_list:
                bot.reply_to(message, "📝 No admins found.")
                return
                
            response = "👥 *Admin List:*\n\n"
            for admin in admin_list:
                response += (f"• ID: `{admin['user_id']}`\n"
                           f"  Username: @{admin.get('username', 'N/A')}\n"
                           f"  Name: {admin.get('first_name', '')} {admin.get('last_name', '')}\n\n")
                           
            bot.reply_to(message, response, parse_mode="Markdown")
            
        except Exception as e:
            bot.reply_to(message, f"❌ Error listing admins: {e}")
            
    @bot.message_handler(commands=['ownerhelp'])
    @check_owner(bot, db)
    def owner_help(message):
        """Show all owner-level commands"""
        help_text = "👑 *Owner Commands:*\n\n"
        
        # Add owner-specific commands
        owner_commands = {
            "addadmin": "Add a new admin user",
            "removeadmin": "Remove an admin user",
            "listadmins": "List all admin users",
            "pending": "List all pending registrations",
            "ownerhelp": "Show this help message"
        }
        
        for cmd, desc in owner_commands.items():
            help_text += f"/{cmd} - {desc}\n"
            
        help_text += "\n*Usage Examples:*\n"
        help_text += "• `/addadmin 123456789` - Make user with ID 123456789 an admin\n"
        help_text += "• `/removeadmin 123456789` - Remove admin privileges from user\n"
        help_text += "• `/listadmins` - Show all current admins\n"
        
        bot.reply_to(message, help_text, parse_mode="Markdown") 