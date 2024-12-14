import os
from telebot import TeleBot, types
from src.database.mongo_db import MongoDB
from src.database.roles import Role, Permissions
from src.middleware.auth import check_owner
from src.utils.notifications import notify_user, NotificationType
from src.utils.user_actions import log_action, ActionType

def create_member_markup(members):
    markup = types.InlineKeyboardMarkup()
    for member in members:
        button = types.InlineKeyboardButton(
            text=f"@{member.get('username', member['user_id'])}",
            callback_data=f"promote_{member['user_id']}"
        )
        markup.add(button)
    return markup

def register_owner_handlers(bot: TeleBot):
    db = MongoDB()
    
    @bot.message_handler(commands=['addadmin'])
    @check_owner(bot, db)
    def add_admin(message):
        """Add a new admin user"""
        try:
            args = message.text.split()
            if len(args) == 1:  # No user_id provided
                members = db.users.find({
                    'registration_status': 'approved',
                    'role': Role.MEMBER.name.lower()
                })
                member_list = list(members)
                
                if not member_list:
                    log_action(
                        ActionType.COMMAND_FAILED,
                        message.from_user.id,
                        error_message="No members found",
                        metadata={'command': 'addadmin'}
                    )
                    bot.reply_to(message, "📝 No registered members found to promote.")
                    return
                
                # Create inline keyboard with member buttons
                markup = create_member_markup(member_list)
                
                log_action(
                    ActionType.ADMIN_COMMAND,
                    message.from_user.id,
                    metadata={
                        'command': 'addadmin',
                        'action': 'list_displayed'
                    }
                )
                
                bot.reply_to(message, 
                    "👥 *Select a member to promote to admin:*",
                    reply_markup=markup,
                    parse_mode="Markdown")
                
            else:
                new_admin_id = int(args[1])
                promote_to_admin(bot, db, message.from_user.id, new_admin_id)
                
        except Exception as e:
            log_action(
                ActionType.COMMAND_FAILED,
                message.from_user.id,
                error_message=str(e),
                metadata={'command': 'addadmin'}
            )
            bot.reply_to(message, f"❌ Error adding admin: {e}")

    # Add new callback handler for promotion buttons
    @bot.callback_query_handler(func=lambda call: call.data.startswith('promote_'))
    def handle_admin_promotion(call):
        """Handle admin promotion from inline keyboard"""
        try:
            # Check if user is owner
            user_id = call.from_user.id
            user = db.users.find_one({'user_id': user_id})
            
            if not user or user.get('role') != Role.OWNER.name.lower():
                bot.answer_callback_query(call.id, "⛔️ This action is only available to the bot owner.")
                return
            
            _, user_id = call.data.split('_')
            user_id = int(user_id)
            
            promote_to_admin(bot, db, call.message.chat.id, user_id)
            
            # Update the original message to remove the inline keyboard
            bot.edit_message_text(
                f"✅ Admin promotion completed.",
                call.message.chat.id,
                call.message.message_id,
                parse_mode="Markdown"
            )
            bot.answer_callback_query(call.id)
            
        except Exception as e:
            bot.answer_callback_query(call.id, f"❌ Error: {str(e)}")

    def promote_to_admin(bot, db, chat_id, user_id):
        """Helper function to promote a user to admin"""
        try:
            # Update user role to admin
            db.users.update_one(
                {'user_id': user_id},
                {'$set': {'role': Role.ADMIN.name.lower()}}
            )
            
            bot.send_message(chat_id, f"✅ User {user_id} has been promoted to admin.")
            
            # Notify the new admin
            try:
                notify_user(
                    bot,
                    NotificationType.PROMOTION_TO_ADMIN,
                    user_id,
                    issuer_id=chat_id
                )
            except Exception as e:
                print(f"Failed to notify new admin: {e}")
                
        except Exception as e:
            raise Exception(f"Failed to promote user to admin: {e}")
        
    @bot.message_handler(commands=['removeadmin'])
    @check_owner(bot, db)
    def remove_admin(message):
        """Remove an admin user"""
        args = message.text.split()
        if len(args) != 2:
            bot.reply_to(message, "⚠️ Usage: /removeadmin <user_id>")
            return
            
        try:
            admin_id = int(args[1])
            user = db.users.find_one({'user_id': admin_id})
            
            if not user:
                bot.reply_to(message, "❌ User not found.")
                return
                
            if user.get('role') != Role.ADMIN.name.lower():
                bot.reply_to(message, "⚠️ User is not an admin.")
                return
                
            # Update user role to member
            db.users.update_one(
                {'user_id': admin_id},
                {'$set': {'role': Role.MEMBER.name.lower()}}
            )
            
            bot.reply_to(message, f"✅ Admin privileges removed from user {admin_id}.")
            
            # Notify the user
            try:
                notify_user(
                    bot,
                    NotificationType.DEMOTION_TO_MEMBER,
                    admin_id,
                    issuer_id=message.from_user.id
                )
            except Exception as e:
                print(f"Failed to notify former admin: {e}")
                
        except ValueError:
            bot.reply_to(message, "❌ Invalid user ID format.")
        except Exception as e:
            bot.reply_to(message, f"❌ Error removing admin: {e}")
            
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