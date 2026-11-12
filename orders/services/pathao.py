import os
import time
import hmac
import hashlib
import requests
from django.conf import settings
from decimal import Decimal

class PathaoService:
    """
    Service wrapper for the Pathao Courier Merchant Aladdin API.
    Handles token management, location lookups, pricing calculations,
    consignment dispatch, tracking, and webhooks.
    """
    _cached_token = None
    _token_expires_at = 0

    def __init__(self):
        self.base_url = getattr(settings, 'PATHAO_BASE_URL', 'https://courier-api-sandbox.pathao.com').rstrip('/')
        self.client_id = getattr(settings, 'PATHAO_CLIENT_ID', '')
        self.client_secret = getattr(settings, 'PATHAO_CLIENT_SECRET', '')
        self.username = getattr(settings, 'PATHAO_USERNAME', '')
        self.password = getattr(settings, 'PATHAO_PASSWORD', '')
        self.grant_type = getattr(settings, 'PATHAO_GRANT_TYPE', 'password')
        self.webhook_secret = getattr(settings, 'PATHAO_WEBHOOK_SECRET', '')

    def is_configured(self):
        """Check if all required credentials are provided."""
        return bool(self.client_id and self.client_secret and self.username and self.password)

    def get_token(self):
        """Fetch or return cached OAuth2 Bearer Token."""
        if PathaoService._cached_token and time.time() < PathaoService._token_expires_at - 60:
            return PathaoService._cached_token

        if not self.is_configured():
            return None

        url = f"{self.base_url}/aladdin/api/v1/issue-token"
        payload = {
            "client_id": self.client_id,
            "client_secret": self.client_secret,
            "username": self.username,
            "password": self.password,
            "grant_type": self.grant_type
        }
        headers = {
            "Content-Type": "application/json",
            "Accept": "application/json"
        }

        try:
            response = requests.post(url, json=payload, headers=headers, timeout=15)
            response.raise_for_status()
            data = response.json()
            token = data.get('access_token')
            expires_in = data.get('expires_in', 3600)

            PathaoService._cached_token = token
            PathaoService._token_expires_at = time.time() + expires_in
            return token
        except Exception as e:
            print(f"[PathaoService] Token generation failed: {e}")
            return None

    def _get_headers(self):
        token = self.get_token()
        headers = {
            "Content-Type": "application/json",
            "Accept": "application/json"
        }
        if token:
            headers["Authorization"] = f"Bearer {token}"
        return headers

    def get_cities(self):
        """Fetch list of all cities/districts."""
        if not self.is_configured():
            return {
                "type": "success",
                "data": {
                    "data": [
                        {"city_id": 1, "city_name": "Dhaka"},
                        {"city_id": 2, "city_name": "Chattogram"},
                        {"city_id": 3, "city_name": "Sylhet"},
                        {"city_id": 4, "city_name": "Rajshahi"},
                        {"city_id": 5, "city_name": "Khulna"},
                        {"city_id": 6, "city_name": "Barishal"},
                        {"city_id": 7, "city_name": "Rangpur"},
                        {"city_id": 8, "city_name": "Mymensingh"}
                    ]
                }
            }

        url = f"{self.base_url}/aladdin/api/v1/countries/1/city-list"
        try:
            resp = requests.get(url, headers=self._get_headers(), timeout=15)
            resp.raise_for_status()
            return resp.json()
        except Exception as e:
            print(f"[PathaoService] Failed to get cities: {e}")
            return {"error": str(e)}

    def get_zones(self, city_id):
        """Fetch list of zones/thanas for a city."""
        if not self.is_configured():
            return {
                "type": "success",
                "data": {
                    "data": [
                        {"zone_id": 101, "zone_name": "Dhanmondi"},
                        {"zone_id": 102, "zone_name": "Gulshan"},
                        {"zone_id": 103, "zone_name": "Uttara"},
                        {"zone_id": 104, "zone_name": "Mirpur"},
                        {"zone_id": 105, "zone_name": "Motijheel"},
                        {"zone_id": 106, "zone_name": "Mohammadpur"}
                    ]
                }
            }

        url = f"{self.base_url}/aladdin/api/v1/cities/{city_id}/zone-list"
        try:
            resp = requests.get(url, headers=self._get_headers(), timeout=15)
            resp.raise_for_status()
            return resp.json()
        except Exception as e:
            print(f"[PathaoService] Failed to get zones for city {city_id}: {e}")
            return {"error": str(e)}

    def get_areas(self, zone_id):
        """Fetch list of areas within a zone."""
        if not self.is_configured():
            return {
                "type": "success",
                "data": {
                    "data": [
                        {"area_id": 1001, "area_name": "Road 1 to 15"},
                        {"area_id": 1002, "area_name": "Road 16 to 32"},
                        {"area_id": 1003, "area_name": "Sector 1 to 7"},
                        {"area_id": 1004, "area_name": "Sector 8 to 14"}
                    ]
                }
            }

        url = f"{self.base_url}/aladdin/api/v1/zones/{zone_id}/area-list"
        try:
            resp = requests.get(url, headers=self._get_headers(), timeout=15)
            resp.raise_for_status()
            return resp.json()
        except Exception as e:
            print(f"[PathaoService] Failed to get areas for zone {zone_id}: {e}")
            return {"error": str(e)}

    def get_stores(self):
        """Fetch merchant pickup stores."""
        if not self.is_configured():
            return {
                "type": "success",
                "data": {
                    "data": [
                        {
                            "store_id": 5001,
                            "store_name": "Central Hub",
                            "store_address": "Dhaka Central Warehouse",
                            "is_active": 1
                        }
                    ]
                }
            }

        url = f"{self.base_url}/aladdin/api/v1/merchant/stores"
        try:
            resp = requests.get(url, headers=self._get_headers(), timeout=15)
            resp.raise_for_status()
            return resp.json()
        except Exception as e:
            print(f"[PathaoService] Failed to get stores: {e}")
            return {"error": str(e)}

    def calculate_price(self, store_id=None, recipient_city=1, recipient_zone=101, weight=0.5, item_type=1, delivery_type=48):
        """
        Calculate Pathao live delivery price.
        delivery_type: 48 (Normal) / 12 (On demand / express)
        item_type: 1 (Document) / 2 (Parcel) / 3 (Fragile)
        """
        if not self.is_configured():
            # Fallback estimation based on city
            base_fee = Decimal('60.00') if str(recipient_city) == '1' else Decimal('120.00')
            if float(weight) > 1.0:
                base_fee += Decimal(str((float(weight) - 1.0) * 20))
            return {
                "type": "success",
                "data": {
                    "price": float(base_fee),
                    "plan_id": 1
                }
            }

        url = f"{self.base_url}/aladdin/api/v1/merchant/price-plan"
        payload = {
            "store_id": int(store_id) if store_id else None,
            "item_type": int(item_type),
            "delivery_type": int(delivery_type),
            "item_weight": float(weight),
            "recipient_city": int(recipient_city),
            "recipient_zone": int(recipient_zone)
        }
        try:
            resp = requests.post(url, json=payload, headers=self._get_headers(), timeout=15)
            resp.raise_for_status()
            return resp.json()
        except Exception as e:
            print(f"[PathaoService] Price calculation failed: {e}")
            return {"error": str(e)}

    def create_consignment(self, order, store_id=None, item_quantity=1, item_weight=0.5, item_description=None, special_instruction=None):
        """
        Dispatches consignment order to Pathao Aladdin API.
        """
        # Determine pickup store ID
        pickup_store = store_id or order.pathao_store_id
        if not pickup_store and order.pickup_city:
            # Fallback to delivery charge hub store
            from orders.models import DeliveryCharge
            hub_rates = DeliveryCharge.objects.first()
            if hub_rates and hub_rates.pathao_hub_store_id:
                pickup_store = hub_rates.pathao_hub_store_id

        # Determine amount to collect (0 for online paid, full total for COD)
        amount_to_collect = 0.00
        if order.payment_method == 'COD' and order.payment_status != 'PAID':
            amount_to_collect = float(order.total_amount + order.total_delivery_charge - (order.discount_amount or 0))

        # Fallback simulation if not configured
        if not self.is_configured():
            fake_consignment_id = f"PTH-CS-{order.id:06d}"
            fake_tracking_code = f"TRK{order.id:06d}{int(time.time()) % 10000}"
            return {
                "type": "success",
                "message": "Order created successfully (Simulated Pathao Sandbox)",
                "data": {
                    "consignment_id": fake_consignment_id,
                    "tracking_code": fake_tracking_code,
                    "order_status": "Pickup_Pending",
                    "delivery_fee": 80.00
                }
            }

        url = f"{self.base_url}/aladdin/api/v1/orders"
        payload = {
            "store_id": int(pickup_store) if pickup_store else None,
            "merchant_order_id": order.order_number,
            "recipient_name": order.buyer.full_name or "Valued Customer",
            "recipient_phone": order.contact_phone or order.buyer.phone_number,
            "recipient_address": order.shipping_address,
            "recipient_city": order.pathao_recipient_city_id or 1,
            "recipient_zone": order.pathao_recipient_zone_id or 101,
            "recipient_area": order.pathao_recipient_area_id or 1001,
            "delivery_type": 48,
            "item_type": 2, # Parcel
            "special_instruction": special_instruction or f"Fulfillment: {order.fulfillment_type}. Pickup at: {order.pickup_address or 'Hub'}",
            "item_quantity": int(item_quantity),
            "item_weight": float(item_weight),
            "amount_to_collect": amount_to_collect,
            "item_description": item_description or f"Order {order.order_number} with {order.items.count()} items"
        }

        try:
            resp = requests.post(url, json=payload, headers=self._get_headers(), timeout=15)
            resp.raise_for_status()
            return resp.json()
        except Exception as e:
            print(f"[PathaoService] Consignment creation failed: {e}")
            if hasattr(e, 'response') and e.response is not None:
                try:
                    return {"error": e.response.json()}
                except Exception:
                    return {"error": e.response.text}
            return {"error": str(e)}

    def track_consignment(self, consignment_id):
        """Fetch live status timeline for a consignment."""
        if not self.is_configured() or consignment_id.startswith('PTH-CS-'):
            return {
                "type": "success",
                "data": {
                    "consignment_id": consignment_id,
                    "order_status": "In_Transit",
                    "history": [
                        {"status": "Order_Created", "time": "2026-08-28 10:00:00"},
                        {"status": "Pickup_Assigned", "time": "2026-08-28 12:30:00"},
                        {"status": "In_Transit", "time": "2026-08-28 14:00:00"}
                    ]
                }
            }

        url = f"{self.base_url}/aladdin/api/v1/orders/{consignment_id}/info"
        try:
            resp = requests.get(url, headers=self._get_headers(), timeout=15)
            resp.raise_for_status()
            return resp.json()
        except Exception as e:
            print(f"[PathaoService] Tracking failed for {consignment_id}: {e}")
            return {"error": str(e)}

    def verify_webhook_signature(self, request_body, signature_header):
        """Verify HMAC SHA256 webhook signature from Pathao."""
        if not self.webhook_secret:
            return True
        if not signature_header:
            return False

        computed_sig = hmac.new(
            self.webhook_secret.encode('utf-8'),
            request_body,
            hashlib.sha256
        ).hexdigest()

        return hmac.compare_digest(computed_sig, signature_header)
