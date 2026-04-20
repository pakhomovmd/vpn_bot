"""
Обработчик для проверки подписки на канал.
"""

from aiogram import Router, F
from aiogram.types import CallbackQuery
from config import CHANNEL_ID

router = Router()


@router.callback_query(F.data == "check_subscription")
async def check_subscription_handler(callback: CallbackQuery):
    """Проверяет подписку пользователя на канал."""
    if not CHANNEL_ID:
        await callback.answer("Канал не настроен", show_alert=True)
        return
    
    try:
        member = await callback.bot.get_chat_member(chat_id=CHANNEL_ID, user_id=callback.from_user.id)
        
        if member.status in ["creator", "administrator", "member"]:
            # Подписан - показываем главное меню
            from keyboards.inline import main_menu
            await callback.message.edit_text(
                "✅ Отлично! Теперь ты можешь пользоваться ботом.\n\n"
                "Выбери действие:",
                reply_markup=main_menu()
            )
            await callback.answer("Подписка подтверждена!", show_alert=False)
        else:
            await callback.answer("Ты еще не подписался на канал", show_alert=True)
    except Exception as e:
        print(f"[CheckSubscription] Ошибка проверки: {e}")
        await callback.answer("Ошибка проверки подписки", show_alert=True)
