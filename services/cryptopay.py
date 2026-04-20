"""
Сервис для работы с Crypto Pay API (CryptoBot).
Документация: https://help.crypt.bot/crypto-pay-api
"""

import aiohttp
from typing import Optional
from config import CRYPTOBOT_TOKEN


class CryptoPayService:
    def __init__(self):
        self.base_url = "https://pay.crypt.bot/api"
        self.token = CRYPTOBOT_TOKEN
    
    async def create_invoice(
        self,
        amount: float,
        currency: str = "USDT",
        description: str = "",
        payload: str = ""
    ) -> Optional[dict]:
        """
        Создает счет для оплаты.
        
        Args:
            amount: Сумма платежа в USD
            currency: Валюта для оплаты (TON, USDT, BTC, USDC, TRX)
            description: Описание платежа
            payload: Дополнительные данные (например, user_id:plan_key)
        
        Returns:
            {"invoice_id": "...", "pay_url": "...", "amount": ...}
        """
        url = f"{self.base_url}/createInvoice"
        
        params = {
            "currency_type": "fiat",
            "fiat": "USD",
            "amount": amount,
            "accepted_assets": currency,  # Валюта которой можно оплатить
            "description": description,
            "payload": payload,
            "paid_btn_name": "callback",
            "paid_btn_url": "https://t.me/SakuraVPNorProxy_bot",
        }
        
        headers = {
            "Crypto-Pay-API-Token": self.token
        }
        
        print(f"[CryptoPay] Создаем счет: amount={amount}, currency={currency}, payload={payload}")
        print(f"[CryptoPay] URL: {url}")
        print(f"[CryptoPay] Params: {params}")
        
        try:
            async with aiohttp.ClientSession() as session:
                async with session.get(url, params=params, headers=headers) as resp:
                    print(f"[CryptoPay] HTTP Status: {resp.status}")
                    text = await resp.text()
                    print(f"[CryptoPay] Response: {text}")
                    
                    data = await resp.json()
                    
                    if not data.get("ok"):
                        print(f"[CryptoPay] Ошибка создания счета: {data}")
                        return None
                    
                    result = data.get("result", {})
                    return {
                        "invoice_id": result.get("invoice_id"),
                        "pay_url": result.get("pay_url"),
                        "amount": result.get("amount"),
                        "currency": result.get("asset"),
                    }
        except Exception as e:
            print(f"[CryptoPay] Исключение при создании счета: {e}")
            import traceback
            traceback.print_exc()
            return None
    
    async def get_invoice(self, invoice_id: int) -> Optional[dict]:
        """
        Получает информацию о счете.
        
        Returns:
            {"status": "paid"|"active"|"expired", "amount": ..., ...}
        """
        url = f"{self.base_url}/getInvoices"
        
        params = {
            "invoice_ids": invoice_id
        }
        
        headers = {
            "Crypto-Pay-API-Token": self.token
        }
        
        try:
            async with aiohttp.ClientSession() as session:
                async with session.get(url, params=params, headers=headers) as resp:
                    data = await resp.json()
                    
                    if not data.get("ok"):
                        print(f"[CryptoPay] Ошибка получения счета: {data}")
                        return None
                    
                    items = data.get("result", {}).get("items", [])
                    if not items:
                        return None
                    
                    invoice = items[0]
                    return {
                        "status": invoice.get("status"),
                        "amount": invoice.get("amount"),
                        "currency": invoice.get("asset"),
                        "payload": invoice.get("payload"),
                    }
        except Exception as e:
            print(f"[CryptoPay] Исключение при получении счета: {e}")
            return None


cryptopay = CryptoPayService()
