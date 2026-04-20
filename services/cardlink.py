"""
Сервис для работы с Card Link API.
Документация: https://cardlink.link/reference/api
"""

import aiohttp
import hashlib
from typing import Optional
from config import CARDLINK_API_TOKEN, CARDLINK_SHOP_ID


class CardLinkService:
    def __init__(self):
        self.base_url = "https://cardlink.link/api/v1"
        self.api_token = CARDLINK_API_TOKEN
        self.shop_id = CARDLINK_SHOP_ID
    
    def _generate_signature(self, out_sum: str, inv_id: str) -> str:
        """
        Генерирует подпись для проверки postback.
        Формат: strtoupper(md5($OutSum . ":" . $InvId . ":" . $apiToken))
        """
        sign_string = f"{out_sum}:{inv_id}:{self.api_token}"
        signature = hashlib.md5(sign_string.encode()).hexdigest().upper()
        return signature
    
    async def create_bill(
        self,
        amount: float,
        order_id: str,
        description: str = "VPN подписка",
        custom: str = ""
    ) -> Optional[dict]:
        """
        Создает счет для оплаты.
        
        Args:
            amount: Сумма платежа в рублях
            order_id: ID заказа в вашей системе
            description: Описание платежа
            custom: Дополнительные данные (например, user_id:plan_key)
        
        Returns:
            {"bill_id": "...", "link_page_url": "...", "link_url": "..."}
        """
        print(f"[CardLink] Начало создания счета")
        print(f"[CardLink] API Token: {'установлен' if self.api_token else 'НЕ УСТАНОВЛЕН'}")
        print(f"[CardLink] Shop ID: {self.shop_id if self.shop_id else 'НЕ УСТАНОВЛЕН'}")
        
        if not self.api_token or not self.shop_id:
            print(f"[CardLink] ОШИБКА: API Token или Shop ID не установлены!")
            return None
        
        url = f"{self.base_url}/bill/create"
        
        data = {
            "amount": str(amount),
            "order_id": order_id,
            "description": description,
            "type": "normal",  # Одноразовый счет
            "shop_id": self.shop_id,
            "currency_in": "RUB",
            "payer_pays_commission": 1,  # Комиссию платит плательщик
            "name": "VPN подписка"
        }
        
        if custom:
            data["custom"] = custom
        
        headers = {
            "Authorization": f"Bearer {self.api_token}",
            "Content-Type": "application/x-www-form-urlencoded"
        }
        
        print(f"[CardLink] Создаем счет: amount={amount}, order_id={order_id}")
        print(f"[CardLink] URL: {url}")
        
        try:
            async with aiohttp.ClientSession() as session:
                async with session.post(url, data=data, headers=headers) as resp:
                    print(f"[CardLink] HTTP Status: {resp.status}")
                    text = await resp.text()
                    print(f"[CardLink] Response: {text}")
                    
                    response = await resp.json()
                    
                    if not response.get("success"):
                        print(f"[CardLink] Ошибка создания счета: {response}")
                        return None
                    
                    return {
                        "bill_id": response.get("bill_id"),
                        "link_page_url": response.get("link_page_url"),
                        "link_url": response.get("link_url"),
                    }
        except Exception as e:
            print(f"[CardLink] Исключение при создании счета: {e}")
            import traceback
            traceback.print_exc()
            return None
    
    async def get_bill_status(self, bill_id: str) -> Optional[dict]:
        """
        Получает статус счета.
        
        Returns:
            {"status": "NEW"|"PROCESS"|"SUCCESS"|"FAIL", ...}
        """
        url = f"{self.base_url}/bill/status"
        
        params = {
            "id": bill_id
        }
        
        headers = {
            "Authorization": f"Bearer {self.api_token}"
        }
        
        try:
            async with aiohttp.ClientSession() as session:
                async with session.get(url, params=params, headers=headers) as resp:
                    response = await resp.json()
                    
                    if not response.get("success"):
                        print(f"[CardLink] Ошибка получения статуса: {response}")
                        return None
                    
                    return {
                        "status": response.get("status"),
                        "amount": response.get("amount"),
                        "order_id": response.get("order_id"),
                        "currency_in": response.get("currency_in"),
                    }
        except Exception as e:
            print(f"[CardLink] Исключение при получении статуса: {e}")
            return None
    
    def verify_signature(self, out_sum: str, inv_id: str, signature: str) -> bool:
        """
        Проверяет подпись postback запроса.
        """
        expected_signature = self._generate_signature(out_sum, inv_id)
        return expected_signature == signature.upper()


cardlink = CardLinkService()
