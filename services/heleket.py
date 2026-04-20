"""
Сервис для работы с Heleket API.
Документация: https://doc.heleket.com
"""

import aiohttp
import hashlib
import base64
import json
from typing import Optional
from config import HELEKET_MERCHANT_ID, HELEKET_API_KEY


class HeleketService:
    def __init__(self):
        self.base_url = "https://api.heleket.com/v1"
        self.merchant_id = HELEKET_MERCHANT_ID
        self.api_key = HELEKET_API_KEY
    
    def _generate_sign(self, data: dict | None = None) -> str:
        """
        Генерирует подпись для запроса.
        Согласно документации Heleket: sign = md5(base64_encode(json_body) + api_key)
        """
        if data:
            json_data = json.dumps(data)
        else:
            json_data = ""
        
        base64_data = base64.b64encode(json_data.encode()).decode()
        sign_string = base64_data + self.api_key
        sign = hashlib.md5(sign_string.encode()).hexdigest()
        
        print(f"[Heleket] JSON data: {json_data[:100]}...")
        print(f"[Heleket] Base64 data: {base64_data[:50]}...")
        print(f"[Heleket] Generated sign: {sign}")
        return sign
    
    async def create_invoice(
        self,
        amount: float,
        currency: str = "USD",
        order_id: str = "",
        url_callback: str = ""
    ) -> Optional[dict]:
        """
        Создает инвойс для оплаты.
        
        Args:
            amount: Сумма платежа в USD
            currency: Валюта (USD, RUB и т.д.)
            order_id: ID заказа в вашей системе
            url_callback: URL для webhook уведомлений
        
        Returns:
            {"uuid": "...", "url": "...", "address": "...", ...}
        """
        print(f"[Heleket] Начало создания инвойса")
        print(f"[Heleket] Merchant ID: {self.merchant_id[:8]}... (длина: {len(self.merchant_id) if self.merchant_id else 0})")
        print(f"[Heleket] API Key: {'установлен' if self.api_key else 'НЕ УСТАНОВЛЕН'} (длина: {len(self.api_key) if self.api_key else 0})")
        
        if not self.merchant_id or not self.api_key:
            print(f"[Heleket] ОШИБКА: Merchant ID или API Key не установлены!")
            return None
        
        url = f"{self.base_url}/payment"
        
        data = {
            "amount": str(amount),
            "currency": currency,
            "order_id": order_id,
            "lifetime": 3600,  # 1 час
        }
        
        if url_callback:
            data["url_callback"] = url_callback
        
        headers = {
            "merchant": self.merchant_id,
            "sign": self._generate_sign(data),
            "Content-Type": "application/json"
        }
        
        print(f"[Heleket] Создаем инвойс: amount={amount}, currency={currency}, order_id={order_id}")
        print(f"[Heleket] URL: {url}")
        
        try:
            async with aiohttp.ClientSession() as session:
                async with session.post(url, json=data, headers=headers) as resp:
                    print(f"[Heleket] HTTP Status: {resp.status}")
                    text = await resp.text()
                    print(f"[Heleket] Response: {text}")
                    
                    response = await resp.json()
                    
                    if response.get("state") != 0:
                        print(f"[Heleket] Ошибка создания инвойса: {response}")
                        return None
                    
                    result = response.get("result", {})
                    return {
                        "uuid": result.get("uuid"),
                        "url": result.get("url"),
                        "address": result.get("address"),
                        "amount": result.get("payer_amount"),
                        "currency": result.get("payer_currency"),
                        "network": result.get("network"),
                        "qr_code": result.get("address_qr_code"),
                    }
        except Exception as e:
            print(f"[Heleket] Исключение при создании инвойса: {e}")
            import traceback
            traceback.print_exc()
            return None
    
    async def get_invoice(self, uuid: str) -> Optional[dict]:
        """
        Получает информацию об инвойсе.
        
        Returns:
            {"payment_status": "paid"|"check"|"expired", ...}
        """
        url = f"{self.base_url}/payment/{uuid}"
        
        headers = {
            "merchant": self.merchant_id,
            "sign": self._generate_sign(),
        }
        
        try:
            async with aiohttp.ClientSession() as session:
                async with session.get(url, headers=headers) as resp:
                    response = await resp.json()
                    
                    if response.get("state") != 0:
                        print(f"[Heleket] Ошибка получения инвойса: {response}")
                        return None
                    
                    result = response.get("result", {})
                    return {
                        "payment_status": result.get("payment_status"),
                        "payment_amount": result.get("payment_amount"),
                        "txid": result.get("txid"),
                    }
        except Exception as e:
            print(f"[Heleket] Исключение при получении инвойса: {e}")
            return None


heleket = HeleketService()
