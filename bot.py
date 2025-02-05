import logging
from telegram import Update, InlineKeyboardButton, InlineKeyboardMarkup, ChatMember
from telegram.ext import Application, CommandHandler, MessageHandler, filters, CallbackQueryHandler, ContextTypes
import re
import json
import random

# --- تنظیمات اولیه ---
logging.basicConfig(format='%(asctime)s - %(name)s - %(levelname)s - %(message)s', level=logging.INFO)
logger = logging.getLogger(__name__)

# --- خواندن دیتابیس از فایل JSON ---
def load_recipes():
    try:
        with open('recipes.json', 'r', encoding='utf-8') as file:
            return json.load(file)
    except FileNotFoundError:
        logger.error("فایل recipes.json یافت نشد!")
        return {}
    except json.JSONDecodeError:
        logger.error("فایل recipes.json معتبر نیست!")
        return {}

RECIPES = load_recipes()

# --- کانال شما ---
CHANNEL_ID = "@python_with_ali_alamshah"  # آیدی کانال خود را اینجا قرار دهید

# --- بررسی عضویت کاربر در کانال ---
async def is_user_member(update: Update, context: ContextTypes.DEFAULT_TYPE, channel_id: str) -> bool:
    try:
        member = await context.bot.get_chat_member(chat_id=channel_id, user_id=update.effective_user.id)
        return member.status in [ChatMember.MEMBER, ChatMember.ADMINISTRATOR, ChatMember.OWNER]
    except Exception as e:
        logger.error(f"خطا در بررسی عضویت: {e}")
        return False

# --- دستورات اصلی ---
async def start(update: Update, context: ContextTypes.DEFAULT_TYPE) -> None:
    if not await is_user_member(update, context, CHANNEL_ID):
        await update.message.reply_text(
            "⚠️ برای استفاده از ربات، لطفاً در کانال ما عضو شوید:\n"
            f"👉 {CHANNEL_ID}\n"
            "بعد از عضویت، /start را دوباره بزنید."
        )
        return
    
    user = update.message.from_user.first_name
    await update.message.reply_text(
        f"سلام {user}! 👩🍳\n"
        "مواد غذایی که داری رو بهم بگو تا غذا پیشنهاد بدم!\n"
        "مثال: تخم مرغ، گوجه، نمک"
    )

async def process_ingredients(update: Update, context: ContextTypes.DEFAULT_TYPE) -> None:
    if not await is_user_member(update, context, CHANNEL_ID):
        await update.message.reply_text(
            "⚠️ برای استفاده از ربات، لطفاً در کانال ما عضو شوید:\n"
            f"👉 {CHANNEL_ID}\n"
            "بعد از عضویت، دوباره امتحان کنید."
        )
        return
    
    user_input = update.message.text
    ingredients = [x.strip().lower() for x in re.split(r'،|,| و ', user_input)]
    context.user_data['ingredients'] = ingredients
    await send_suggestions(update.message, context)

async def send_suggestions(message, context: ContextTypes.DEFAULT_TYPE) -> None:
    ingredients = context.user_data.get('ingredients', [])
    
    matches = []
    for name, details in RECIPES.items():
        common = set(ingredients) & set([x.lower() for x in details['ingredients']])
        if len(common) >= 1:
            matches.append((name, len(common), details))
    
    if matches:
        matches.sort(key=lambda x: (-x[1], random.random()))  # مرتب‌سازی با امکان تصادفی‌سازی
        keyboard = []
        for recipe in matches[:3]:
            keyboard.append([InlineKeyboardButton(
                f"{recipe[0]} ({recipe[1]} ماده مشترک)", 
                callback_data=recipe[0]
            )])
        
        # اضافه کردن دکمه‌های جدید
        keyboard.append([
            InlineKeyboardButton("🔄 پیشنهاد دیگر", callback_data="another_suggestion"),
            InlineKeyboardButton("🔄 شروع مجدد", callback_data="restart")
        ])
        
        reply_markup = InlineKeyboardMarkup(keyboard)
        await message.reply_text(
            "🍽 با مواد شما این غذاها رو پیدا کردم:",
            reply_markup=reply_markup
        )
    else:
        keyboard = [
            [
                InlineKeyboardButton("🎲 پیشنهاد تصادفی", callback_data="random"),
                InlineKeyboardButton("➕ اضافه کردن مواد", callback_data="add_more")
            ],
            [
                InlineKeyboardButton("🔄 شروع مجدد", callback_data="restart")
            ]
        ]
        reply_markup = InlineKeyboardMarkup(keyboard)
        await message.reply_text(
            "😞 متاسفانه با این مواد غذایی پیشنهادی ندارم!",
            reply_markup=reply_markup
        )

async def show_recipe(update: Update, context: ContextTypes.DEFAULT_TYPE) -> None:
    query = update.callback_query
    await query.answer()
    callback_data = query.data

    if callback_data == "another_suggestion":
        await send_suggestions(query.message, context)
        return
    
    if callback_data == "restart":
        context.user_data.clear()
        await query.message.reply_text(
            "🔄 ربات ریست شد!\n"
            "مواد غذایی جدید خود را وارد کنید:\n"
            "مثال: تخم مرغ، گوجه، نمک"
        )
        return
    
    if callback_data == "random":
        recipe_name = random.choice(list(RECIPES.keys()))
    elif callback_data == "add_more":
        await query.edit_message_text(text="مواد بیشتری که داری رو بگو:")
        return
    else:
        recipe_name = callback_data

    recipe = RECIPES.get(recipe_name)
    if recipe:
        response = (
            f"🍴 {recipe_name}\n"
            f"📝 مواد لازم:\n- " + "\n- ".join(recipe['ingredients']) + "\n\n"
            f"🔪 دستور پخت:\n{recipe['instructions']}"
        )
        # اضافه کردن دکمه‌ها به صفحه جزئیات
        keyboard = [
            [
                InlineKeyboardButton("🔄 پیشنهاد دیگر", callback_data="another_suggestion"),
                InlineKeyboardButton("🔄 شروع مجدد", callback_data="restart")
            ]
        ]
        reply_markup = InlineKeyboardMarkup(keyboard)
        await query.edit_message_text(text=response, reply_markup=reply_markup)
    else:
        await query.edit_message_text(text="متاسفانه مشکلی پیش اومده!")

# --- تنظیمات اجرایی ---
def main() -> None:
    application = Application.builder().token("7750648989:AAEHjSvpFxUdNDuyqWBloZmrrr7CheRubPo").build()
    application.add_handler(CommandHandler('start', start))
    application.add_handler(MessageHandler(filters.TEXT & ~filters.COMMAND, process_ingredients))
    application.add_handler(CallbackQueryHandler(show_recipe))
    application.run_polling()

if __name__ == '__main__':
    main()