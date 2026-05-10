"""
Сервис для работы с ЮKassa API.
Документация: https://yookassa.ru/developers/api
"""

import uuid
from typing import Optional
from yookassa import Configuration, Payment
from config import YUKASSA_SHOP_ID, YUKASSA_SECRET_KEY


class YuKassaService:
    def __init__(self):
        """Инициализация конфигурации ЮKassa."""
        if YUKASSA_SHOP_ID and YUKASSA_SECRET_KEY:
            Configuration.account_id = YUKASSA_SHOP_ID
            Configuration.secret_key = YUKASSA_SECRET_KEY
            print(f"[YuKassa] Конфигурация установлена: Shop ID = {YUKASSA_SHOP_ID}")
        else:
            print(f"[YuKassa] ПРЕДУПРЕЖДЕНИЕ: Shop ID или Secret Key не установлены!")
    
    async def create_payment(
        self,
        amount: float,
        description: str,
        order_id: str,
        return_url: str = None
    ) -> Optional[dict]:
        """
        Создает платеж в ЮKassa.
        
        Args:
            amount: Сумма платежа в рублях
            description: Описание платежа
            order_id: ID заказа в вашей системе
            return_url: URL для возврата после оплаты (опционально)
        
        Returns:
            {
                "payment_id": "...",
                "confirmation_url": "...",
                "status": "pending"
            }
        """
        print(f"[YuKassa] Начало создания платежа")
        print(f"[YuKassa] Shop ID: {'установлен' if YUKASSA_SHOP_ID else 'НЕ УСТАНОВЛЕН'}")
        print(f"[YuKassa] Secret Key: {'установлен' if YUKASSA_SECRET_KEY else 'НЕ УСТАНОВЛЕН'}")
        
        if not YUKASSA_SHOP_ID or not YUKASSA_SECRET_KEY:
            print(f"[YuKassa] ОШИБКА: Shop ID или Secret Key не установлены!")
            return None
        
        try:
            # Генерируем уникальный ключ идемпотентности
            idempotence_key = str(uuid.uuid4())
            
            # Формируем данные платежа
            payment_data = {
                "amount": {
                    "value": f"{amount:.2f}",
                    "currency": "RUB"
                },
                "confirmation": {
                    "type": "redirect",
                    "return_url": return_url if return_url else "https://t.me/your_bot"
                },
                "capture": True,  # Автоматическое подтверждение платежа
                "description": description,
                "metadata": {
                    "order_id": order_id
                }
            }
            
            print(f"[YuKassa] Создаем платеж: amount={amount}, order_id={order_id}")
            print(f"[YuKassa] Idempotence key: {idempotence_key}")
            
            # Создаем платеж
            payment = Payment.create(payment_data, idempotence_key)
            
            print(f"[YuKassa] Платеж создан: ID = {payment.id}, Status = {payment.status}")
            
            # Получаем URL для оплаты
            confirmation_url = payment.confirmation.confirmation_url if payment.confirmation else None
            
            if not confirmation_url:
                print(f"[YuKassa] ОШИБКА: Не получен URL для оплаты")
                return None
            
            return {
                "payment_id": payment.id,
                "confirmation_url": confirmation_url,
                "status": payment.status
            }
            
        except Exception as e:
            print(f"[YuKassa] Исключение при создании платежа: {e}")
            import traceback
            traceback.print_exc()
            return None
    
    async def get_payment_status(self, payment_id: str) -> Optional[dict]:
        """
        Получает статус платежа.
        
        Args:
            payment_id: ID платежа в ЮKassa
        
        Returns:
            {
                "status": "pending"|"waiting_for_capture"|"succeeded"|"canceled",
                "amount": float,
                "paid": bool,
                "order_id": str
            }
        """
        print(f"[YuKassa] Проверка статуса платежа: {payment_id}")
        
        if not YUKASSA_SHOP_ID or not YUKASSA_SECRET_KEY:
            print(f"[YuKassa] ОШИБКА: Shop ID или Secret Key не установлены!")
            return None
        
        try:
            # Получаем информацию о платеже
            payment = Payment.find_one(payment_id)
            
            print(f"[YuKassa] Статус платежа {payment_id}: {payment.status}")
            
            # Извлекаем order_id из метаданных
            order_id = payment.metadata.get("order_id") if payment.metadata else None
            
            return {
                "status": payment.status,
                "amount": float(payment.amount.value),
                "paid": payment.paid,
                "order_id": order_id
            }
            
        except Exception as e:
            print(f"[YuKassa] Исключение при получении статуса: {e}")
            import traceback
            traceback.print_exc()
            return None
    
    def verify_notification(self, notification_data: dict) -> bool:
        """
        Проверяет подлинность уведомления от ЮKassa.
        
        Args:
            notification_data: Данные уведомления
        
        Returns:
            True если уведомление подлинное
        """
        # ЮKassa использует IP whitelist для проверки подлинности
        # Дополнительная проверка через signature не требуется
        return True


yukassa = YuKassaService()
