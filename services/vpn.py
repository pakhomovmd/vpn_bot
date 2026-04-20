"""
Сервис для работы с панелью 3X-UI через её REST API.
"""

import aiohttp
import uuid
import json as json_mod
import os
from datetime import datetime, timedelta
from config import XRAY_PANEL_URL, XRAY_USERNAME, XRAY_PASSWORD, XRAY_INBOUND_ID

PANEL_PATH = os.getenv("XRAY_PANEL_PATH", "").strip("/")


class XRayService:
    def __init__(self):
        self.base_url = XRAY_PANEL_URL.rstrip("/")

    def _url(self, path: str) -> str:
        """Формирует полный URL с учётом WebBasePath панели."""
        path = path.lstrip("/")
        if PANEL_PATH:
            return f"{self.base_url}/{PANEL_PATH}/{path}"
        return f"{self.base_url}/{path}"

    def _connector(self):
        return aiohttp.TCPConnector(ssl=False)

    async def _login(self, session: aiohttp.ClientSession) -> bool:
        """Авторизация в панели."""
        try:
            resp = await session.post(
                self._url("/login"),
                json={"username": XRAY_USERNAME, "password": XRAY_PASSWORD},
            )
            data = await resp.json()
            ok = data.get("success", False)
            if not ok:
                print(f"[XRay] Логин неудачен: {data}")
            return ok
        except Exception as e:
            print(f"[XRay] Ошибка логина: {e}")
            return False

    async def create_client(self, user_id: int, days: int) -> dict | None:
        """
        Создаёт клиента в 3X-UI.
        Возвращает {"uuid": "...", "vless_link": "..."}
        """
        client_uuid = str(uuid.uuid4())
        expire_ms = int((datetime.now() + timedelta(days=days)).timestamp() * 1000)
        email = f"user_{user_id}"

        print(f"[XRay] Создаём клиента: user_id={user_id}, uuid={client_uuid}, expire_ms={expire_ms}")

        # Сначала получаем текущие настройки inbound
        cookie_jar = aiohttp.CookieJar(unsafe=True)
        async with aiohttp.ClientSession(connector=self._connector(), cookie_jar=cookie_jar) as session:
            if not await self._login(session):
                print(f"[XRay] Не удалось авторизоваться")
                return None
            
            try:
                # Получаем список всех inbounds
                print(f"[XRay] Получаем список inbounds...")
                resp = await session.get(self._url("/panel/api/inbounds/list"))
                inbound_data = await resp.json()
                
                if not inbound_data.get("success"):
                    print(f"[XRay] Не удалось получить список inbounds: {inbound_data}")
                    return None
                
                # Находим нужный inbound по ID
                inbounds = inbound_data.get("obj", [])
                obj = None
                for inbound in inbounds:
                    if inbound.get("id") == XRAY_INBOUND_ID:
                        obj = inbound
                        break
                
                if not obj:
                    print(f"[XRay] Inbound с ID {XRAY_INBOUND_ID} не найден")
                    return None
                
                print(f"[XRay] Найден inbound: {obj.get('remark', 'unnamed')}")
                
                # Формируем payload для добавления ТОЛЬКО нового клиента
                from config import MAX_DEVICES
                new_client = {
                    "id": client_uuid,
                    "email": email,
                    "expiryTime": expire_ms,
                    "enable": True,
                    "limitIp": MAX_DEVICES,  # Ограничение на количество устройств
                    "totalGB": 0,
                    "flow": "xtls-rprx-vision",
                    "tgId": str(user_id),
                    "subId": "",
                    "reset": 0
                }
                
                # API addClient принимает только ОДНОГО нового клиента
                payload = {
                    "id": XRAY_INBOUND_ID,
                    "settings": json_mod.dumps({
                        "clients": [new_client]
                    })
                }
                
                resp = await session.post(
                    self._url("/panel/api/inbounds/addClient"),
                    json=payload,
                )
                data = await resp.json()
                print(f"[XRay] Ответ addClient: {data}")

                if data.get("success"):
                    link = await self._build_vless_link(session, client_uuid, email)
                    print(f"[XRay] Клиент успешно создан! VLESS link: {link[:50]}...")
                    return {"uuid": client_uuid, "vless_link": link}
                else:
                    print(f"[XRay] Ошибка создания клиента: {data}")
            except Exception as e:
                print(f"[XRay] Исключение при создании клиента: {e}")
                import traceback
                traceback.print_exc()

        return None

    async def _build_vless_link(self, session: aiohttp.ClientSession, client_uuid: str, email: str) -> str:
        """Собирает VLESS ссылку из параметров inbound."""
        try:
            # Используем ту же сессию что и для создания клиента (с cookie)
            resp = await session.get(self._url("/panel/api/inbounds/list"))
            data = await resp.json()
            if not data.get("success"):
                print(f"[XRay] Не удалось получить список inbounds для ссылки: {data}")
                return self._fallback_link(client_uuid)

            # Находим нужный inbound
            inbounds = data.get("obj", [])
            obj = None
            for inbound in inbounds:
                if inbound.get("id") == XRAY_INBOUND_ID:
                    obj = inbound
                    break
            
            if not obj:
                print(f"[XRay] Inbound {XRAY_INBOUND_ID} не найден при построении ссылки")
                return self._fallback_link(client_uuid)
            port = obj.get("port", 443)
            stream_raw = obj.get("streamSettings", "{}")
            stream = json_mod.loads(stream_raw) if isinstance(stream_raw, str) else stream_raw

            security = stream.get("security", "reality")
            network = stream.get("network", "tcp")
            reality = stream.get("realitySettings", {})
            server_names = reality.get("serverNames", ["yahoo.com"])
            short_ids = reality.get("shortIds", [""])
            pub_key = reality.get("settings", {}).get("publicKey", "")
            sni = server_names[0] if server_names else "yahoo.com"
            sid = short_ids[0] if short_ids else ""

            server_ip = self.base_url.split("//")[-1].split(":")[0]

            return (
                f"vless://{client_uuid}@{server_ip}:{port}"
                f"?type={network}&security={security}"
                f"&pbk={pub_key}&sni={sni}&sid={sid}"
                f"&flow=xtls-rprx-vision#{email}"
            )
        except Exception as e:
            print(f"[XRay] Ошибка сборки ссылки: {e}")
            return self._fallback_link(client_uuid)

    def _fallback_link(self, client_uuid: str) -> str:
        server_ip = self.base_url.split("//")[-1].split(":")[0]
        return f"vless://{client_uuid}@{server_ip}:443?type=tcp&security=reality&flow=xtls-rprx-vision#VPN"

    async def disable_client(self, client_uuid: str) -> bool:
        """Деактивирует клиента."""
        cookie_jar = aiohttp.CookieJar(unsafe=True)
        async with aiohttp.ClientSession(connector=self._connector(), cookie_jar=cookie_jar) as session:
            if not await self._login(session):
                return False
            try:
                resp = await session.post(
                    self._url(f"/panel/api/inbounds/{XRAY_INBOUND_ID}/updateClient/{client_uuid}"),
                    json={
                        "id": XRAY_INBOUND_ID,
                        "settings": json_mod.dumps({"clients": [{"id": client_uuid, "enable": False}]})
                    },
                )
                data = await resp.json()
                return data.get("success", False)
            except Exception as e:
                print(f"[XRay] Ошибка деактивации: {e}")
        return False

    async def extend_client(self, client_uuid: str, days: int) -> bool:
        """Продлевает подписку клиента."""
        expire_ms = int((datetime.now() + timedelta(days=days)).timestamp() * 1000)
        cookie_jar = aiohttp.CookieJar(unsafe=True)
        async with aiohttp.ClientSession(connector=self._connector(), cookie_jar=cookie_jar) as session:
            if not await self._login(session):
                return False
            try:
                resp = await session.post(
                    self._url(f"/panel/api/inbounds/{XRAY_INBOUND_ID}/updateClient/{client_uuid}"),
                    json={
                        "id": XRAY_INBOUND_ID,
                        "settings": json_mod.dumps({"clients": [{"id": client_uuid, "expiryTime": expire_ms, "enable": True}]})
                    },
                )
                data = await resp.json()
                return data.get("success", False)
            except Exception as e:
                print(f"[XRay] Ошибка продления: {e}")
        return False

    async def find_client_by_email(self, email: str) -> dict | None:
        """
        Ищет клиента в 3X-UI панели по email.
        Возвращает {"id": "uuid", "email": "...", "expiryTime": ..., "enable": True/False} или None
        """
        cookie_jar = aiohttp.CookieJar(unsafe=True)
        async with aiohttp.ClientSession(connector=self._connector(), cookie_jar=cookie_jar) as session:
            if not await self._login(session):
                print(f"[XRay] Не удалось авторизоваться для поиска по email")
                return None

            try:
                # Получаем список inbounds
                resp = await session.get(self._url("/panel/api/inbounds/list"))
                data = await resp.json()

                if not data.get("success"):
                    print(f"[XRay] Не удалось получить список inbounds: {data}")
                    return None

                # Находим нужный inbound
                inbounds = data.get("obj", [])
                target_inbound = None
                for inbound in inbounds:
                    if inbound.get("id") == XRAY_INBOUND_ID:
                        target_inbound = inbound
                        break

                if not target_inbound:
                    print(f"[XRay] Inbound {XRAY_INBOUND_ID} не найден")
                    return None

                # Парсим настройки
                settings_raw = target_inbound.get("settings", "{}")
                settings = json_mod.loads(settings_raw) if isinstance(settings_raw, str) else settings_raw
                clients = settings.get("clients", [])

                # Ищем клиента по email
                for client in clients:
                    if client.get("email") == email:
                        print(f"[XRay] Найден клиент по email {email}: uuid={client.get('id')}, expiryTime={client.get('expiryTime')}")
                        return client

                print(f"[XRay] Клиент с email {email} не найден в inbound {XRAY_INBOUND_ID}")
                return None

            except Exception as e:
                print(f"[XRay] Ошибка поиска клиента по email: {e}")
                import traceback
                traceback.print_exc()
                return None

    async def get_client_info(self, client_uuid: str) -> dict | None:
        """
        Получает информацию о клиенте из 3X-UI панели.
        Возвращает {"email": "...", "expiryTime": ..., "enable": True/False} или None
        """
        cookie_jar = aiohttp.CookieJar(unsafe=True)
        async with aiohttp.ClientSession(connector=self._connector(), cookie_jar=cookie_jar) as session:
            if not await self._login(session):
                print(f"[XRay] Не удалось авторизоваться для получения info")
                return None

            try:
                # Получаем список inbounds
                resp = await session.get(self._url("/panel/api/inbounds/list"))
                data = await resp.json()

                if not data.get("success"):
                    print(f"[XRay] Не удалось получить список inbounds: {data}")
                    return None

                # Находим нужный inbound
                inbounds = data.get("obj", [])
                target_inbound = None
                for inbound in inbounds:
                    if inbound.get("id") == XRAY_INBOUND_ID:
                        target_inbound = inbound
                        break

                if not target_inbound:
                    print(f"[XRay] Inbound {XRAY_INBOUND_ID} не найден")
                    return None

                # Парсим настройки
                settings_raw = target_inbound.get("settings", "{}")
                settings = json_mod.loads(settings_raw) if isinstance(settings_raw, str) else settings_raw
                clients = settings.get("clients", [])

                # Ищем клиента по UUID
                for client in clients:
                    if client.get("id") == client_uuid:
                        print(f"[XRay] Найден клиент {client_uuid}: expiryTime={client.get('expiryTime')}, enable={client.get('enable')}")
                        return client

                print(f"[XRay] Клиент {client_uuid} не найден в inbound {XRAY_INBOUND_ID}")
                return None

            except Exception as e:
                print(f"[XRay] Ошибка получения информации о клиенте: {e}")
                import traceback
                traceback.print_exc()
                return None


xray = XRayService()
