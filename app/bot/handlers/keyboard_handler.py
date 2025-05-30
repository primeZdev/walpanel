from aiogram import Router, types, F
from aiogram.fsm.context import FSMContext


from app.bot.keyboards.main_admin_keyboards import (
    main_admin_menu,
    settings_menu,
    language_menu,
    cancel_keyboard,
    card_method_settings_keyboard,
)
from app.bot.keyboards.keyboards import (
    sign_up_menu,
    cancel_keyboard as dealer_cancel_keyboard,
    admin_panel,
    start_menu,
)
from app.bot.services.query import (
    admins_query,
    panels_query,
    settings_query,
    help_message_query,
    registering_message_query,
    plans_query,
    card_query,
)
from app.admin_services.api import panels_api
from app.bot.messages.messages import BOT_MESSAGE
from app.bot.middlewares.middleware import set_new_language
from app.bot.oprations.backup import get_backup_from_bot
from app.bot.oprations.notif_settings import show_notif_settings
from app.bot.oprations.plan_setting import show_plans
from app.bot.states.states import (
    HelpTextStates,
    RegistrationTextStates,
    AddPlanStates,
    EditPlanStates,
    DeletePlanStates,
    LoginUserStates,
)
from app.bot.oprations.auth import check_loged_in, logout_admin
from datetime import date
import os
from aiogram.types import InlineKeyboardMarkup, InlineKeyboardButton


router = Router()


@router.message(F.text == "👤 Admins")
async def handle_admins_button(
    message: types.Message, bot_language: str, user_role: str
):
    if user_role == "main_admin":
        admins = await admins_query.get_all_admins()
        if not admins:
            await message.answer("No admins found!")
            return

        message_text = "📊 Dealers/Admins Status\n\n"
        try:
            for admin in admins:
                admin_status = "active" if admin["is_active"] else "disabled"
                message_text += BOT_MESSAGE.DEALERS_STATUS[bot_language].format(
                    username=admin["username"],
                    days_remaining=admin["days_remaining"],
                    traffic=admin["traffic"],
                    panel=admin["panel"],
                    status=admin_status,
                )
            await message.answer(
                message_text, parse_mode="HTML", reply_markup=main_admin_menu()
            )
        except Exception as e:
            await message.answer(BOT_MESSAGE.ERROR[bot_language].format(e=e))


@router.message(F.text == "🌐 Panels")
async def handle_panels_button(
    message: types.Message, bot_language: str, user_role: str
):
    if user_role == "main_admin":
        panels = await panels_query.get_all_panels()
        if not panels:
            await message.answer("No panels found!")
            return

        message_text = "📊 Panel Status Report\n\n"
        try:
            for panel in panels:
                panel_status = await panels_api.server_status(
                    panel["url"], panel["username"], panel["password"]
                )
                if not panel_status:
                    await message.answer(
                        "Your panels are not running. Please check them on walpanel (web)."
                    )
                    return

                status_data = panel_status.get("obj", {})
                xray_status = status_data.get("xray", "unknown")
                used_mem = status_data.get("mem", {}).get("current", 0)
                total_mem = status_data.get("mem", {}).get("total", 1)
                mem_percent = (used_mem / total_mem) * 100
                uptime = status_data.get("uptime", 0) // 3600

                message_text += BOT_MESSAGE.PANELS_STATUS[bot_language].format(
                    name=panel["name"],
                    cpu_usage=int(status_data.get("cpu", 0)),
                    ram_usage=int(mem_percent),
                    xray_status=xray_status.get("state", "unknown"),
                    xray_version=xray_status.get("version", "N/A"),
                    uptime=uptime,
                )

            await message.answer(
                message_text, parse_mode="HTML", reply_markup=main_admin_menu()
            )
        except Exception as e:
            await message.answer(BOT_MESSAGE.ERROR[bot_language].format(e=e))


@router.message(F.text == "🌎 Language")
async def handle_lang_button(message: types.Message, user_role: str):
    if user_role == "main_admin":
        await message.answer("🤖 Bot Language", reply_markup=language_menu())


@router.message(F.text == "🇺🇸 English")
async def handle_en_button(message: types.Message, user_role: str):
    if user_role == "main_admin":
        new_language = "en"
        await settings_query.change_language(new_language)
        await message.answer(
            BOT_MESSAGE.START_MAIN_ADMIN[new_language], reply_markup=main_admin_menu()
        )
        await set_new_language()


@router.message(F.text == "🇮🇷 Persian")
async def handle_fa_button(message: types.Message, user_role: str):
    if user_role == "main_admin":
        new_language = "fa"
        await settings_query.change_language(new_language)
        await message.answer(
            BOT_MESSAGE.START_MAIN_ADMIN[new_language], reply_markup=main_admin_menu()
        )
        await set_new_language()


@router.message(F.text == "🇺🇸 English")
async def handle_en_button(message: types.Message, user_role: str):
    if user_role == "main_admin":

        await message.answer("🇺🇸 English", reply_markup=settings_menu())


@router.message(F.text == "⚙️ Settings")
async def handle_settings_button(message: types.Message, user_role: str):
    if user_role == "main_admin":
        await message.answer("⚙️ Settings Menu", reply_markup=settings_menu())


@router.message(F.text == "🔙 Back")
async def handle_back_button(message: types.Message, user_role: str):
    if user_role == "main_admin":
        await message.answer("📱 Main menu", reply_markup=main_admin_menu())


@router.message(F.text == "🔙 Back to settings")
async def handle_back_button(message: types.Message, user_role: str):
    if user_role == "main_admin":
        await message.answer("⚙️ Settings Menu", reply_markup=settings_menu())


@router.message(F.text == "📝 Logs")
async def handle_logs_button(message: types.Message, user_role: str, bot_language: str):
    if user_role == "main_admin":
        current_dir = os.path.dirname(
            os.path.dirname(os.path.dirname(os.path.abspath(__file__)))
        )
        log_file_path = os.path.join(current_dir, "data", "app.log")

        try:
            if not os.path.exists(log_file_path):
                await message.answer(f"Log file not found at: {log_file_path}")
                return

            with open(log_file_path, "r", encoding="utf-8") as file:
                # Read all lines and get the last 10
                lines = file.readlines()
                last_10_lines = lines[-10:] if len(lines) >= 10 else lines

                log_content = "".join(last_10_lines)
                await message.answer(
                    f"{BOT_MESSAGE.LOG_MESSAGE[bot_language]}<pre>{log_content}</pre>",
                    parse_mode="HTML",
                    reply_markup=main_admin_menu(),
                )
        except Exception as e:
            await message.answer(f"Error reading log file: {str(e)}")


@router.message(F.text == "📦 Backup")
async def handle_backup_button(
    message: types.Message, user_role: str, bot_language: str
):
    if user_role == "main_admin":
        await get_backup_from_bot(message, bot_language)


@router.message(F.text == "📄 Help text")
async def handle_help_text_button(
    message: types.Message, user_role: str, bot_language: str, state: FSMContext
):
    if user_role == "main_admin":
        help_text = help_message_query.get_help_message()
        show_text = BOT_MESSAGE.HELP_TEXT[bot_language].format(help_text=help_text)
        await message.answer(
            show_text, parse_mode="HTML", reply_markup=cancel_keyboard()
        )
        await state.set_state(HelpTextStates.waiting_for_new_help_text)


@router.message(F.text == "⚪ Registration text")
async def handle_registration_text_button(
    message: types.Message, user_role: str, bot_language: str, state: FSMContext
):
    if user_role == "main_admin":
        registration_text = registering_message_query.get_registering_message()
        show_text = BOT_MESSAGE.REGISTRATION_TEXT[bot_language].format(
            registration_text=registration_text
        )
        await message.answer(
            show_text, parse_mode="HTML", reply_markup=cancel_keyboard()
        )
        await state.set_state(RegistrationTextStates.waiting_for_new_registration_text)


@router.message(F.text == "🔔 Notifications")
async def handle_notifications_button(
    message: types.Message, user_role: str, bot_language: str, state: FSMContext
):
    if user_role == "main_admin":
        await show_notif_settings(message, bot_language, user_role)


@router.message(F.text == "🛍️ Sales Plan")
async def handle_sales_plan_button(
    message: types.Message, user_role: str, bot_language: str
):
    if user_role == "main_admin":
        await show_plans(message, bot_language)


@router.message(F.text == "➕ Add a plan")
async def handle_add_plan_button(
    message: types.Message, user_role: str, bot_language: str, state: FSMContext
):
    if user_role == "main_admin":
        await message.answer(
            BOT_MESSAGE.WAITING_FOR_PLAN_TRAFFIC[bot_language],
            reply_markup=cancel_keyboard(),
        )
        await state.set_state(AddPlanStates.waiting_for_traffic)


@router.message(F.text == "⚙️ Edit a plan")
async def handle_settings_button(
    message: types.Message, user_role: str, bot_language: str, state: FSMContext
):
    if user_role == "main_admin":
        await message.answer(
            BOT_MESSAGE.WAITING_FOR_PLAN_ID[bot_language],
            reply_markup=cancel_keyboard(),
        )
        await state.set_state(EditPlanStates.waiting_for_id)


@router.message(F.text == "❌ Delete a plan")
async def handle_delete_plan_button(
    message: types.Message, user_role: str, bot_language: str, state: FSMContext
):
    if user_role == "main_admin":
        await message.answer(
            BOT_MESSAGE.WAITING_FOR_PLAN_ID[bot_language],
            reply_markup=cancel_keyboard(),
        )
        await state.set_state(DeletePlanStates.waiting_for_id)


@router.message(F.text == "💳 Card method setting")
async def handle_card_method_button(
    message: types.Message, user_role: str, bot_language: str
):
    if user_role == "main_admin":
        status = await settings_query.get_card_method()
        card_num = card_query.get_card()
        status_text = "✅" if status else "❌"

        await message.answer(
            BOT_MESSAGE.CARD_METHOD_SETTINGS[bot_language].format(
                status=status_text, card_num=card_num
            ),
            parse_mode="HTML",
            reply_markup=card_method_settings_keyboard(bot_language),
        )


# users and admins buttons


@router.message(F.text == "💎 sign up")
async def handle_sign_up_button(message: types.Message, bot_language: str):
    try:
        rules = registering_message_query.get_registering_message()
        await message.answer(
            rules,
            reply_markup=sign_up_menu(
                message.chat.id,
                message.chat.full_name,
                message.chat.username,
                bot_language,
            ),
        )
    except Exception as e:
        await message.answer(
            BOT_MESSAGE.ERROR[bot_language].format(e=e),
        )


@router.message(F.text == "🛡️ Login")
async def handle_login_button(
    message: types.Message, bot_language: str, state: FSMContext
):
    try:
        await message.answer(
            BOT_MESSAGE.LOGIN_STEP1[bot_language], reply_markup=dealer_cancel_keyboard()
        )
        await state.set_state(LoginUserStates.enter_username)

    except Exception as e:
        await message.answer(
            BOT_MESSAGE.ERROR[bot_language].format(e=e),
        )


@router.message(F.text == "💎 My account")
async def handle_myaccount_button(message: types.Message, bot_language: str):
    try:
        if await check_loged_in(message.chat.id):
            data = admins_query.get_admin_by_chat_id(message.chat.id)
            expiry_time = max((data["expiry_time"] - date.today()).days, 0)
            message_text = BOT_MESSAGE.MY_ACCOUNT[bot_language].format(
                username=data["username"],
                password=data["password"],
                traffic=data["traffic"],
                expiry_time=expiry_time,
            )
            await message.reply(message_text, reply_markup=admin_panel())
    except Exception as e:
        await message.answer(BOT_MESSAGE.ERROR[bot_language].format(e=e))


@router.message(F.text == "🛍️ Store")
async def handle_store_button(message: types.Message, bot_language: str):
    try:
        if await check_loged_in(message.chat.id):
            plans = plans_query.get_plans()
            if not plans:
                await message.answer(BOT_MESSAGE.PLAN_NOT_EXIST[bot_language])
                return

            # Create keyboard with plans
            keyboard = InlineKeyboardMarkup(
                inline_keyboard=[
                    [
                        InlineKeyboardButton(
                            text=f"{plan['traffic']}GB - {plan['price']}$ - {plan['deadline']} Days",
                            callback_data=f"buy_plan:{plan['id']}:{message.chat.id}:{bot_language}",
                        )
                    ]
                    for plan in plans
                ]
            )

            await message.answer(
                BOT_MESSAGE.SHOW_PLANS_FOR_DEALER[bot_language], reply_markup=keyboard
            )
    except Exception as e:
        await message.answer(BOT_MESSAGE.ERROR[bot_language].format(e=e))


@router.message(F.text == "ℹ️ Help")
async def handle_help_button(message: types.Message, bot_language: str):
    try:
        help_text = help_message_query.get_help_message()
        await message.answer(text=help_text)
    except Exception as e:
        await message.answer(BOT_MESSAGE.ERROR[bot_language].format(e=e))


@router.message(F.text == "❌ Logout")
async def handle_Logout_button(message: types.Message, bot_language: str):
    try:
        if await check_loged_in(message.chat.id):
            await logout_admin(message.chat.id)
            await message.answer(
                BOT_MESSAGE.LOGOUT[bot_language], reply_markup=start_menu()
            )
    except Exception as e:
        await message.answer(BOT_MESSAGE.ERROR[bot_language].format(e=e))
