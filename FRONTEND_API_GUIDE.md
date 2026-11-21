# ACCS Platform - Comprehensive Frontend Developer API Reference Manual

> **Base URL:** `http://127.0.0.1:8000` (Local Development)  
> **Interactive Swagger UI:** `http://127.0.0.1:8000/api/docs/` or `http://127.0.0.1:8000/docs/`  
> **Redoc Documentation:** `http://127.0.0.1:8000/api/redoc/`  
> **OpenAPI Schema (JSON/YAML):** `http://127.0.0.1:8000/api/schema/`

---

## 🔐 Authentication & Global Headers

### Headers Format
For all protected endpoints (Buyer, Vendor, Admin), send the JWT access token in the standard Authorization header:
```http
Authorization: Bearer <access_token>
Content-Type: application/json
```
*(Note: For file/image uploads, use `multipart/form-data` and omit the manual `Content-Type` header so the browser sets the boundary automatically).*

### User Roles & Permissions
| Role | Description |
| :--- | :--- |
| **PUBLIC / GUEST** | Accessible without login. Guest carts use a browser cookie `guest_id` automatically set by the server. |
| **BUYER** | Regular customer (`ROLE: BUYER`). Can browse, manage shipping address, place orders, track parcels. |
| **VENDOR** | Merchant (`ROLE: VENDOR`). Can manage Shop Profile, Products, Inventory, View Assigned Sub-Orders, and View Wallet. |
| **ADMIN / STAFF** | Superuser or Staff (`is_staff: true`). Full access to approve KYC, approve products, approve orders, override delivery/pickup, and manage finances. |

---

## Table of Contents
1. [Authentication & Buyer/Vendor Onboarding](#1-authentication--account-apis)
2. [Shipping Address (Pathao Location Mapping)](#2-shipping-address-apis)
3. [Vendors & Shop Profiles](#3-vendors--shops-apis)
4. [Categories & Products Catalog](#4-categories--products-apis)
5. [Shopping Cart (Guest & Authenticated)](#5-shopping-cart-apis)
6. [Orders, Checkout & Fulfillment](#6-orders--checkout-apis)
7. [Admin Order Review & Overrides](#7-admin-order-management-apis)
8. [Vendor Sub-Orders Management](#8-vendor-orders-apis)
9. [Pathao Courier Integration & Live Tracking](#9-pathao-courier-apis)
10. [Wallets, Commissions & Balance](#10-wallets--commissions-apis)
11. [Lookup & Core Platform APIs](#11-lookup--core-platform-apis)

---

## 1. Authentication & Account APIs

### 1.1 Buyer Quick Register (Step 1 - Send OTP)
* **Endpoint:** `POST /api/auth/buyer/register/`
* **Access:** Public
* **Purpose:** Initiates buyer registration by validating phone number and sending an OTP via SMS.
* **Request Body (JSON):**
  * `phone_number` (*Required, String*): e.g., `"01711111111"`
  * `full_name` (*Required, String*): e.g., `"Rahim Ahmed"`
```json
{
  "phone_number": "01711111111",
  "full_name": "Rahim Ahmed"
}
```
* **Success Response (200 OK):**
```json
{
  "status": "success",
  "message": "OTP sent to phone number."
}
```

---

### 1.2 Buyer Quick Register (Step 2 - Verify OTP & Auto-Login)
* **Endpoint:** `POST /api/auth/buyer/register-verify/`
* **Access:** Public
* **Purpose:** Verifies OTP. Automatically creates the Buyer account, generates a 6-digit default password sent via SMS, logs the user in, and returns JWT tokens.
* **Request Body (JSON):**
  * `phone_number` (*Required, String*): e.g., `"01711111111"`
  * `otp_code` (*Required, String, 6 digits*): e.g., `"123456"`
```json
{
  "phone_number": "01711111111",
  "otp_code": "123456"
}
```
* **Success Response (201 Created):**
```json
{
  "message": "Registration verified and logged in successfully.",
  "data": {
    "access_token": "eyJhbGciOi...",
    "user": {
      "user": {
        "id": 12,
        "phone_number": "01711111111",
        "full_name": "Rahim Ahmed",
        "role": { "id": 1, "name": "ROLE", "value": "BUYER" }
      }
    }
  }
}
```

---

### 1.3 General / Vendor Registration (With KYC)
* **Endpoint:** `POST /api/auth/register/`
* **Access:** Public
* **Content-Type:** `multipart/form-data`
* **Purpose:** Used for Vendor registration. Defaults role to `VENDOR` and uploads mandatory KYC documents (NID / Trade License).
* **Request Form-Data:**
  * `phone_number` (*Required, String*): `"01811111111"`
  * `password` (*Required, String*): `"Secret123!"`
  * `confirm_password` (*Required, String*): `"Secret123!"`
  * `full_name` (*Optional, String*): `"Karim Trading"`
  * `nid_number` (*Optional/Vendor Required, String*): `"19921234567890"`
  * `nid_front_image` (*File*): NID Front photo
  * `nid_back_image` (*File*): NID Back photo
* **Success Response (201 Created):**
```json
{
  "status": "success",
  "message": "Registration successful. OTP sent to phone number."
}
```

---

### 1.4 User & Vendor Login
* **Endpoint:** `POST /api/auth/login/`
* **Access:** Public
* **Request Body (JSON):**
  * `phone_number` (*Required, String*): `"01711111111"`
  * `password` (*Required, String*): `"Secret123!"`
```json
{
  "phone_number": "01711111111",
  "password": "password123"
}
```
* **Success Response (200 OK):**
```json
{
  "status": "success",
  "message": "Login successful.",
  "data": {
    "access_token": "eyJhbGci...",
    "user": {
      "user": {
        "id": 5,
        "phone_number": "01711111111",
        "full_name": "Rahim Ahmed",
        "role": { "value": "BUYER" },
        "is_approved": true,
        "is_phone_verified": true
      }
    }
  }
}
```

---

### 1.5 Admin & Staff Login
* **Endpoint:** `POST /api/admin/login/`
* **Access:** Public (Only users with `is_staff: true` are permitted)
* **Request Body (JSON):**
  * `phone_number` (*Required, String*)
  * `password` (*Required, String*)
```json
{
  "phone_number": "01844444444",
  "password": "AdminPassword123"
}
```
* **Success Response (200 OK):** Returns admin access token and permission groups.

---

### 1.6 Refresh Access Token & Logout
* **Refresh Token:** `POST /api/auth/getRefreshToken/` (Public - Reads `refresh_token` httpOnly cookie).
* **Logout:** `POST /api/auth/logout/` (Public - Revokes refresh token and clears auth cookies).

---

## 2. Shipping Address APIs

Saved shipping address for the logged-in Buyer. Fully integrated with **Pathao Courier** city and zone IDs.

### 2.1 Get Current Saved Address
* **Endpoint:** `GET /api/auth/shipping-address/`
* **Access:** Authenticated (Buyer)
* **Success Response (200 OK):**
```json
{
  "id": 1,
  "full_name": "Rahim Ahmed",
  "phone_number": "01711111111",
  "address": "House 12, Road 4, Sector 3, Uttara",
  "pathao_city_id": 1,
  "pathao_zone_id": 102,
  "pathao_area_id": 502,
  "city_name": "Dhaka",
  "zone_name": "Uttara",
  "area_name": "Sector 3"
}
```

---

### 2.2 Create Shipping Address
* **Endpoint:** `POST /api/auth/shipping-address/`
* **Access:** Authenticated (Buyer)
* **Request Body (JSON):**
  * `full_name` (*Required, String*): Name of the recipient
  * `phone_number` (*Required, String*): Recipient contact phone
  * `address` (*Required, String*): Detailed street address
  * `pathao_city_id` (*Required for delivery, Integer*): e.g. `1` for Dhaka (from Pathao Cities API)
  * `pathao_zone_id` (*Required for delivery, Integer*): e.g. `102` for Uttara (from Pathao Zones API)
  * `pathao_area_id` (*Optional, Integer*): Pathao Area ID
  * *(Note: `city_name`, `zone_name`, and `area_name` are automatically resolved by the backend from Pathao; they do NOT need to be passed in the request body!)*
```json
{
  "full_name": "Rahim Ahmed",
  "phone_number": "01711111111",
  "address": "House 12, Road 4, Sector 3",
  "pathao_city_id": 1,
  "pathao_zone_id": 102,
  "pathao_area_id": 502
}
```

---

### 2.3 Update Shipping Address
* **Endpoint:** `PATCH /api/auth/shipping-address/`
* **Access:** Authenticated (Buyer)
* **Request Body (JSON):** Pass any of the fields to update.

---

## 3. Vendors & Shops APIs

### 3.1 List All Shops (Marketplace Directory)
* **Endpoint:** `GET /api/vendors/shops/`
* **Access:** Public
* **Query Filters:**
  * `?shop_type=RETAILER` or `?shop_type=WHOLESALER`
  * `?search=Alpha` (searches shop name & address)
  * `?page=1`

### 3.2 Get Single Shop Details
* **Endpoint:** `GET /api/vendors/shops/{id}/`
* **Access:** Public

### 3.3 Create Shop Profile (Vendor Onboarding)
* **Endpoint:** `POST /api/vendors/shops/`
* **Access:** Authenticated Vendor (`ROLE: VENDOR`)
* **Content-Type:** `multipart/form-data`
* **Request Form-Data:**
  * `shop_name` (*Required, String*): e.g., `"Gadget World"`
  * `shop_type` (*Required, Choice*): `"RETAILER"` or `"WHOLESALER"`
  * `shop_address` (*Required, String*): `"Shop 4B, Multiplan Center, Dhaka"`
  * `contact_email` (*Optional, Email*): `"vendor@example.com"`
  * `city` (*Optional, Integer*): City ID
  * `logo` (*Optional, File*): Image
  * `banner` (*Optional, File*): Image
  * `trade_license_number` (*Optional, String*)
  * `trade_license_document` (*Optional, File*)
  * `pathao_store_id` (*Optional, String*): Pathao pickup store ID

### 3.4 Get Logged-in Vendor's Own Shop
* **Endpoint:** `GET /api/vendors/shops/me/`
* **Access:** Authenticated Vendor

### 3.5 Shop Reviews
* **List Reviews:** `GET /api/vendors/reviews/?shop_id={shop_id}` (Public)
* **Submit Review:** `POST /api/vendors/reviews/` (Authenticated Buyer)
  * `shop` (*Required, Integer*): Shop ID
  * `product_rating` (*Required, Integer, 1-5*)
  * `delivery_rating` (*Required, Integer, 1-5*)
  * `comment` (*Optional, String*)

---

## 4. Categories & Products Catalog

### 4.1 Hierarchical Category Tree (For Navbar & Menus)
* **Endpoint:** `GET /api/products/categories/tree/`
* **Access:** Public
* **Success Response (200 OK):**
```json
[
  {
    "id": 1,
    "name": "Electronics",
    "slug": "electronics",
    "image": "/media/categories/electronics.png",
    "subcategories": [
      {
        "id": 5,
        "name": "Mobile Phones",
        "slug": "mobile-phones",
        "subcategories": []
      }
    ]
  }
]
```

---

### 4.2 Product List (Marketplace)
* **Endpoint:** `GET /api/products/products/`
* **Access:** Public (Returns only approved, active products from unblocked vendors)
* **Query Filters:**
  * `?category={id}`: Filter by category ID
  * `?shop={id}`: Filter by vendor shop ID
  * `?search=mouse`: Search by product title or description
  * `?page=1`: Page number

---

### 4.3 Product Detail
* **Endpoint:** `GET /api/products/products/{id}/`
* **Access:** Public
* **Response:** Product details including price, wholesale tier pricing, MOQ, images, and shop details.

---

### 4.4 Create Product (Vendor or Admin)
* **Endpoint:** `POST /api/products/products/`
* **Access:** Authenticated Vendor or Admin (staff need the `add_product` permission)
* **Content-Type:** `multipart/form-data`
* **Vendor:** the product goes to the vendor's own shop as `PENDING` (or `APPROVED` with auto-approve permission).
* **Admin:** send `shop` (shop ID) to choose the selling shop; required unless the admin owns a shop. Admin products are `APPROVED` straight away.
* **Request Form-Data:**
  * `shop` (*Admin only, Integer*): Shop that sells the product
  * `preview_pdf` (*Optional, File*): A few sample pages as one PDF (max 15 MB, must be a real PDF). Returned as a
    public URL that shoppers read on the product page. On `PATCH`, a new file replaces the old one and an empty value
    (`preview_pdf=`) removes it.
  * `category` (*Required, Integer*): Category ID
  * `title` (*Required, String*): `"Wireless Mouse M185"`
  * `description` (*Optional, String*): `"High precision ergonomic mouse"`
  * `price` (*Required, Decimal*): Regular retail price, e.g. `1200.00`
  * `discount_price` (*Optional, Decimal*): Sale price, e.g. `999.00`
  * `stock_quantity` (*Required, Integer*): Available stock, e.g. `50`
  * `moq` (*Optional, Integer, Default 1*): Minimum Order Quantity
  * `woner_commission` (*Optional, Decimal*): Platform commission percentage, e.g. `10.00` (10%)
  * `image` (*Optional, File*): Primary product cover image
  * `wholesale_tier1_min_qty`, `wholesale_tier1_price`: Tier 1 wholesale pricing
  * `wholesale_tier2_min_qty`, `wholesale_tier2_price`: Tier 2 wholesale pricing

---

### 4.5 Vendor's Own Products
* **Endpoint:** `GET /api/products/products/my-products/`
* **Access:** Authenticated Vendor
* **Query Filters:** `?approval_status=APPROVED` / `PENDING` / `REJECTED`

---

### 4.6 Smart Inventory: Low Stock Alerts
* **Endpoint:** `GET /api/products/products/low-stock`
* **Access:** Authenticated (Admin or Vendor)
* **Purpose:** Returns all products where current `stock_quantity <= low_stock_threshold` (default threshold is `5`).
  * **Admin:** Returns all low-stock products across all platform vendors.
  * **Vendor:** Returns only low-stock products belonging to the logged-in vendor's shop.
* **Product Model Attributes for Inventory:**
  * `stock_quantity` (*Integer*): Current available inventory.
  * `low_stock_threshold` (*Integer, Default 5*): Minimum warning threshold.
  * `is_low_stock` (*Boolean, Read-only*): `true` whenever `stock_quantity <= low_stock_threshold`. (Included on all product list/detail endpoints).
* **Response (200 OK):**
```json
{
  "status": "success",
  "message": "Data fetched successfully",
  "data": [
    {
      "id": 14,
      "title": "Bluetooth Earbuds",
      "stock_quantity": 2,
      "low_stock_threshold": 5,
      "is_low_stock": true,
      "price": "1200.00",
      "shop_name": "Gadget Hub"
    }
  ]
}
```

## 5. Shopping Cart APIs

Supports **both unauthenticated guests and logged-in buyers**. The backend automatically manages and persists a `guest_id` cookie. When a guest logs in, their cart is automatically merged into their buyer account!

### 5.1 View Cart
* **Endpoint:** `GET /api/orders/cart/`
* **Access:** Public / Guest / Buyer
* **Response (200 OK):**
```json
{
  "id": 10,
  "items": [
    {
      "id": 25,
      "product": {
        "id": 3,
        "title": "Mechanical Keyboard",
        "price": "1500.00",
        "shop": { "id": 1, "shop_name": "Shop Alpha" }
      },
      "quantity": 2,
      "unit_price": "1500.00",
      "subtotal_price": "3000.00"
    }
  ],
  "total_items": 2,
  "total_amount": "3000.00"
}
```

---

### 5.2 Add Product to Cart
* **Endpoint:** `POST /api/orders/cart/add/`
* **Access:** Public / Guest / Buyer
* **Request Body (JSON):**
  * `product_id` (*Required, Integer*): ID of the product
  * `quantity` (*Required, Integer, Minimum 1*): Number of units to add
```json
{
  "product_id": 3,
  "quantity": 2
}
```

---

### 5.3 Update Cart Item Quantity
* **Endpoint:** `POST /api/orders/cart/update_quantity/`
* **Access:** Public / Guest / Buyer
* **Request Body (JSON):**
  * `product_id` (*Required, Integer*)
  * `quantity` (*Required, Integer*): New quantity (setting `0` removes the item)
```json
{
  "product_id": 3,
  "quantity": 5
}
```

---

### 5.4 Remove Item & Clear Cart
* **Remove Item:** `POST /api/orders/cart/remove/` with `{"product_id": 3}`
* **Clear Entire Cart:** `POST /api/orders/cart/clear/`

---

## 6. Orders & Checkout APIs

### 6.1 Place Order (Checkout Active Cart)
* **Endpoint:** `POST /api/orders/buyer/orders/`
* **Access:** Authenticated (Buyer)
* **Purpose:** Converts the items in the user's cart into an active Order.
  * Checks whether items come from 1 shop (`DIRECT_VENDOR`) or multiple shops (`CENTRAL_HUB`).
  * Calls **Pathao live price calculation** to compute the exact delivery charge.
  * Empties the cart.
* **Request Body (JSON):**
  * `shipping_address` (*Optional, String*): Delivery address (falls back to saved profile address)
  * `contact_phone` (*Optional, String*): Recipient phone (falls back to saved profile or account phone)
  * `pathao_recipient_city_id` (*Optional, Integer*): Pathao City ID (e.g. `1` for Dhaka)
  * `pathao_recipient_zone_id` (*Optional, Integer*): Pathao Zone ID (e.g. `101` for Dhanmondi)
  * `pathao_recipient_area_id` (*Optional, Integer*): Pathao Area ID
  * `payment_method` (*Optional, Choice, Default 'COD'*): `"COD"` or `"ONLINE"`
```json
{
  "shipping_address": "House 12, Road 4, Dhanmondi, Dhaka",
  "contact_phone": "01711111111",
  "pathao_recipient_city_id": 1,
  "pathao_recipient_zone_id": 101,
  "payment_method": "COD"
}
```
* **Success Response (201 Created):**
```json
{
  "id": 105,
  "order_number": "ORD-000105",
  "status": "PENDING_ADMIN_APPROVAL",
  "fulfillment_type": "DIRECT_VENDOR",
  "total_amount": "3000.00",
  "total_delivery_charge": "60.00",
  "grand_total": "3060.00",
  "delivery_charge_breakdown": [
    {
      "source": "Pathao Courier Dynamic Fee",
      "delivery_charge": "60.00"
    }
  ],
  "items": [...]
}
```

---

### 6.2 Buyer Orders History
* **List Orders:** `GET /api/orders/buyer/orders/`
* **Order Detail:** `GET /api/orders/buyer/orders/{id}/`

---

## 7. Admin Order Management APIs

### 7.1 Approve Order (With Optional Pickup/Delivery Overrides)
* **Endpoint:** `POST /api/orders/admin/orders/{id}/approve/`
* **Access:** Admin
* **Purpose:**
  1. Approves the order (`status: APPROVED`).
  2. Allows Admin to override either **Pickup Details** or **Recipient Delivery Details**.
  3. If destination or store is updated, automatically recalculates Pathao delivery fee!
  4. Automatically splits into sub-orders (`VendorOrder`) for each vendor.
  5. Deducts inventory stock from product stock.
  6. Calculates owner commission and debits it from each vendor's wallet balance.
* **Request Body (JSON - All Fields Optional):**
  * **Pickup Overrides:**
    * `pickup_address` (*String*): Custom pickup warehouse/store
    * `pickup_phone` (*String*): Custom pickup phone number
    * `pathao_store_id` (*String*): Pathao pickup store ID override
  * **Delivery / Recipient Overrides:**
    * `shipping_address` (*String*): Customer delivery address override
    * `contact_phone` (*String*): Customer contact phone override
    * `pathao_recipient_city_id` (*Integer*): New Pathao destination city ID
    * `pathao_recipient_zone_id` (*Integer*): New Pathao destination zone ID
    * `recalculate_delivery_charge` (*Boolean, Default true*): Recalculates Pathao delivery fee if destination changed
```json
{
  "pickup_address": "Central Warehouse Tejgaon, Dhaka",
  "pathao_store_id": "HUB-STORE-001",
  "shipping_address": "GEC Circle, Chattogram",
  "contact_phone": "01822222222",
  "pathao_recipient_city_id": 2,
  "pathao_recipient_zone_id": 201,
  "recalculate_delivery_charge": true
}
```

---

### 7.2 Reject Order
* **Endpoint:** `POST /api/orders/admin/orders/{id}/reject/`
* **Access:** Admin
* **Request Body (JSON):**
  * `rejection_reason` (*Required, String*): e.g., `"Out of stock or invalid recipient contact."`

---

### 7.3 Dispatch Consignment to Pathao Courier
* **Endpoint:** `POST /api/orders/admin/orders/{id}/dispatch-pathao/`
* **Access:** Admin
* **Purpose:** Registers the parcel in Pathao Aladdin Courier API. Assigns `pathao_consignment_id` and `pathao_tracking_code`.
* **Request Body (JSON):**
  * `item_weight` (*Required, Decimal*): Weight in KG, e.g. `1.0`
  * `item_quantity` (*Required, Integer*): Total parcel quantity, e.g. `2`
  * `special_instruction` (*Optional, String*): e.g. `"Fragile, handle with care"`
```json
{
  "item_weight": 1.0,
  "item_quantity": 2,
  "special_instruction": "Handle with care. Call recipient before delivery."
}
```
* **Success Response (200 OK):**
```json
{
  "message": "Order dispatched to Pathao successfully",
  "pathao_data": {
    "consignment_id": "PTH-CS-789012",
    "tracking_code": "TRK987654321",
    "order_status": "Pickup_Pending",
    "delivery_fee": 60.0
  }
}
```

---

### 7.4 Restock Returned or Cancelled Order (Inventory & Commission Refund)
* **Endpoint:** `POST /api/orders/admin/orders/{id}/restock/`
* **Access:** Admin
* **Purpose:**
  1. Validates that the order is `CANCELLED`, `RETURNED`, `REJECTED`, or marked `Returned`/`Cancelled` by courier.
  2. Automatically restores product stock for all items back into shop inventory (`stock_quantity += item.quantity`).
  3. Automatically refunds debited platform commissions back into participating vendors' wallets (`WalletTransaction(transaction_type='IN')`).
  4. Marks `is_restocked: true` and sets `restocked_at` and `restocked_by`.
  5. Prevents double restock (returns 400 if already restocked).
* **Response (200 OK):**
```json
{
  "message": "Order ORD-000105 successfully restocked and commissions refunded to vendor wallets.",
  "order": {
    "id": 105,
    "order_number": "ORD-000105",
    "status": "RETURNED",
    "is_restocked": true,
    "restocked_at": "2026-09-11T17:30:00.000Z"
  }
}
```

---

### 7.5 Courier & Restock Inventory Overview
* **Endpoint:** `GET /api/orders/admin/orders/courier-summary/`
* **Access:** Admin
* **Purpose:** Real-time visibility of parcels held with courier vs returned/cancelled and pending restock.
* **Response (200 OK):**
```json
{
  "in_transit_parcels": 8,
  "delivered_parcels": 45,
  "returned_parcels": 3,
  "cancelled_parcels": 2,
  "pending_restock_parcels": 1,
  "restocked_parcels": 4
}
```

---

## 8. Vendor Orders APIs

When an order is approved, it splits into sub-orders for each participating shop.

### 8.1 Vendor Sub-Orders List
* **Endpoint:** `GET /api/orders/vendor/orders/`
* **Access:** Authenticated Vendor
* **Query Filters:** `?status=PROCESSING` / `PACKED` / `SHIPPED` / `DELIVERED` / `CANCELLED` / `RETURNED`

### 8.2 Update Sub-Order Fulfillment Status
* **Endpoint:** `PATCH /api/orders/vendor/orders/{id}/update-status/`
* **Access:** Authenticated Vendor
* **Request Body (JSON):**
  * `status` (*Required, Choice*): `"PROCESSING"`, `"PACKED"`, `"SHIPPED"`, `"DELIVERED"`, or `"CANCELLED"`
```json
{
  "status": "PACKED"
}
```

---

### 8.3 Vendor Restock Returned Sub-Order
* **Endpoint:** `POST /api/orders/vendor/orders/{id}/restock/`
* **Access:** Authenticated Vendor (or Admin)
* **Purpose:** When a returned parcel is received back at the vendor shop, the vendor can 1-click restock items into their shop inventory and receive immediate wallet commission refund.
* **Response (200 OK):**
```json
{
  "message": "Vendor Order VORD-000105 successfully restocked.",
  "vendor_order": {
    "id": 12,
    "vendor_order_number": "VORD-000105",
    "status": "RETURNED",
    "is_restocked": true,
    "restocked_at": "2026-09-11T17:30:00.000Z"
  }
}
```

---

## 9. Pathao Courier APIs

Public endpoints for live location lookups and delivery fee estimation.

### 9.1 Get Pathao Deliverable Cities
* **Endpoint:** `GET /api/orders/pathao/cities/`
* **Access:** Public
* **Response (200 OK):** Returns list of all deliverable cities with their `city_id` and `city_name` (e.g., `city_id: 1` = Dhaka, `city_id: 2` = Chattogram).

---

### 9.2 Get Pathao Zones (Thanas) in a City
* **Endpoint:** `GET /api/orders/pathao/zones/?city_id=1`
* **Access:** Public
* **Query Param:** `city_id` (*Required, Integer*): e.g. `1` for Dhaka
* **Response (200 OK):** Returns all zones (e.g. Dhanmondi, Gulshan, Mirpur, Uttara) with `zone_id` and `zone_name`.

---

### 9.3 Get Pathao Areas in a Zone
* **Endpoint:** `GET /api/orders/pathao/areas/?zone_id=101`
* **Access:** Public
* **Query Param:** `zone_id` (*Required, Integer*): e.g. `101` for Dhanmondi

---

### 9.4 Calculate Live Pathao Delivery Price
* **Endpoint:** `POST /api/orders/pathao/calculate-price/`
* **Access:** Public / Buyer
* **Request Body (JSON):**
  * `recipient_city` (*Required, Integer*): e.g. `1`
  * `recipient_zone` (*Required, Integer*): e.g. `101`
  * `weight` (*Optional, Decimal, Default 0.5*): Weight in KG
  * `item_type` (*Optional, Integer, Default 1*): `1` (Document), `2` (Parcel), `3` (Fragile)
  * `delivery_type` (*Optional, Integer, Default 48*): `48` (Normal 48h), `12` (On Demand)
```json
{
  "recipient_city": 1,
  "recipient_zone": 101,
  "weight": 1.5,
  "item_type": 2,
  "delivery_type": 48
}
```
* **Success Response (200 OK):**
```json
{
  "type": "success",
  "data": {
    "price": 70.0,
    "plan_id": 1
  }
}
```

---

### 9.5 Track Parcel in Realtime
* **Endpoint:** `GET /api/orders/admin/orders/{id}/track-pathao/`
* **Access:** Buyer / Admin
* **Response (200 OK):** Returns Pathao consignment timeline, current rider status, and event timestamps.

---

## 10. Wallets & Commissions APIs

Every vendor has an automated virtual wallet.
* **Credit Limit:** Maximum allowable negative balance (e.g. `500.00` BDT).
* **Automatic Debit:** Whenever an order is approved, the platform's commission is debited (`OUT`).
* **Auto-Blocking:** If a vendor's negative balance exceeds their credit limit, their shop and products are automatically blocked from the public marketplace until payment/discount is applied!

### 10.1 Vendor My Wallet
* **Endpoint:** `GET /api/wallets/my-wallet/`
* **Access:** Authenticated Vendor
* **Response (200 OK):**
```json
{
  "id": 4,
  "balance": "-250.00",
  "credit_limit": "500.00",
  "user_info": { "full_name": "Karim Vendor", "phone_number": "01822222222" },
  "shop_profile": { "shop_name": "Shop Alpha" }
}
```

---

### 10.2 Vendor Wallet Transactions
* **Endpoint:** `GET /api/wallets/transactions/`
* **Access:** Authenticated Vendor
* **Query Filters:** `?transaction_type=IN` / `OUT` / `DISCOUNT`

---

### 10.3 Admin Wallet Management
* **List All Wallets:** `GET /api/wallets/admin/all/` (Admin)
* **Update Vendor Credit Limit:** `PATCH /api/wallets/admin/all/{id}/update-credit-limit/` (Admin)
  * `credit_limit` (*Required, Decimal*): e.g. `1000.00`
* **Add Discount / Credit Balance:** `POST /api/wallets/admin/all/{id}/add-discount/` (Admin)
  * `amount` (*Required, Decimal*): e.g. `500.00`
  * `description` (*Optional, String*): e.g. `"Promotional subsidy"`
* **List Blocked Vendor Profiles:** `GET /api/blocked-profiles/` (Admin)

---

## 11. Lookup & Core Platform APIs

### 11.1 Lookup Items (Roles, Categories)
* **Endpoint:** `GET /api/lookup/items/?name=ROLE`
* **Access:** Public / Authenticated

### 11.2 Platform Policies & About Us
* **List Policies:** `GET /api/core/policies/` (Public)
* **About Us:** `GET /api/core/about-us/` (Public)

### 11.3 Admin Analytics Dashboard
* **Endpoint:** `GET /api/admin/dashboard/analytics/`
* **Access:** Admin
* **Purpose:** Comprehensive platform KPIs including user/vendor statistics, product sales trends, top performing vendors, wallet commissions, real-time inventory overview, and courier parcel pipeline.
* **Success Response (200 OK):**
```json
{
  "users": {
    "total": 120,
    "vendors": 15
  },
  "orders": {
    "total_product_orders": 85
  },
  "sales_trend": {
    "products": [
      {
        "month": "2026-09-01T00:00:00Z",
        "sales_volume": "145000.00"
      }
    ]
  },
  "top_vendors": [
    {
      "id": 1,
      "shop_name": "Shop Alpha",
      "rating": 4.8
    }
  ],
  "commissions": {
    "daily_commission": 1500.00,
    "monthly_commission": 34000.00,
    "total_commission": 95000.00
  },
  "inventory_summary": {
    "total_products": 340,
    "low_stock_products": 12,
    "out_of_stock_products": 3
  },
  "courier_summary": {
    "in_transit_parcels": 8,
    "delivered_parcels": 65,
    "returned_parcels": 4,
    "cancelled_parcels": 2,
    "pending_restock_parcels": 1,
    "restocked_parcels": 5
  }
}
```

---

## 12. Additions & Changes for the Next.js Frontend

### New endpoints

| Method | Endpoint | Auth | Purpose |
| :--- | :--- | :--- | :--- |
| `GET` / `PATCH` | `/api/auth/me/` | Any user | Current user + KYC profile (works for every role). PATCH `full_name`, `date_of_birth`, `profile_img` (multipart). |
| `POST` | `/api/auth/change-password/` | Any user | `{current_password, new_password, confirm_new_password}` |
| `POST` | `/api/auth/forgot-password/` | Public | `{phone_number}` — sends a reset OTP |
| `POST` | `/api/auth/reset-password/` | Public | `{phone_number, otp_code, new_password, confirm_new_password}` |
| `POST` | `/api/orders/buyer/orders/{id}/cancel/` | Buyer | Cancel own order while `PENDING_ADMIN_APPROVAL`. Optional `{reason}` |
| `GET` | `/api/orders/buyer/orders/{id}/track/` | Buyer | Pathao tracking timeline for own order |
| `GET` | `/api/orders/admin/orders/commissions/` | Admin | Paginated commission ledger (`?search=`) |
| `GET` / `PATCH` | `/api/orders/admin/delivery-settings/` | Admin | Central hub + fallback delivery charges |
| `GET` | `/api/vendors/shops/me/dashboard` | Vendor | Product / order / revenue / wallet stats for the seller dashboard |
| `GET` | `/api/core/announcements/` | Any user | Broadcast announcements targeted at the current user |

### Behaviour changes

- Login, OTP-verify, buyer register-verify and admin login responses now include `data.refresh_token`, so SPA clients
  can refresh with `POST /api/auth/getRefreshToken/ {refresh_token}` without relying on cross-site cookies.
  Admin login returns the same `{user, kyc_profile}` shape as the regular login.
- `GET /api/products/products` supports `?category=` (a category also matches everything below it — sub- and
  sub-sub-categories), `?min_price=`, `?max_price=`, `?in_stock=1` and `?ordering=price|-price|-created_at|title`;
  search also matches shop and category names.
- Categories can be nested **three levels** deep (e.g. `Stationery → Pens & Pencils → Ball Pens`). Creating or moving a
  category deeper than that, or inside its own branch, returns 400. `facets` counts roll up to every ancestor, and a
  product's `category_details.ancestors` lists `[{id, name}]` from the top-level category down to the direct parent.
- Vendors can open / edit / delete **their own** products in any approval state; editing someone else's product returns
  403. Editing a `REJECTED` product sends it back to `PENDING`. `woner_commission` is admin-only.
- Product images: only the owning vendor (or admin) can add / update / delete; setting `is_primary` unsets the others.
- Categories, cities, policies, about-us and lookups are read-only for non-admins (previously any logged-in user could write).
- Shop reviews are saved with the correct `reviewer`; a buyer can review each shop once and edit/delete only their own review.
- Shop profile endpoints accept JSON as well as multipart.

### Demo data

```bash
python manage.py seed_demo
```

Creates roles, cities, a category tree, two vendor shops with products, policies and these accounts
(password `12345678`): admin `01700000001`, buyer `01711111111`, vendors `01722222222` / `01733333333`.

---

## 13. Book shop, marketing & engagement (2026-11)

| Method | Endpoint | Auth | Purpose |
| :--- | :--- | :--- | :--- |
| `GET` | `/api/products/products/home-sections?limit=5` | Public | Every top-level category (Class 1–12) with its latest books |
| `GET` | `/api/products/products/facets` | Public | Filter counts: `categories`, `publishers`, `authors` for the current search/filters |
| `GET` | `/api/products/products?category=1,2&publisher=A,B&author=X&discounted=1` | Public | Multi-value filters (comma separated) |
| `GET/POST/DELETE` | `/api/products/wishlist` (`DELETE ?product_id=`) | User | Saved books |
| `GET/POST/DELETE` | `/api/products/reviews` (`?product=`), `/reviews/eligibility?product=` | Public read / buyers write | Book reviews; only buyers with an approved/delivered order can review |
| `GET` | `/api/marketing/banners/` (`?all=1` for admins) | Public | Home page slider |
| `POST/PATCH/DELETE` | `/api/marketing/banners/` | Admin | Manage banners (multipart: `image`, `mobile_image`, `title`, `subtitle`, `button_text`, `link_url`, `position`, `is_active`, `starts_at`, `ends_at`) |
| `CRUD` | `/api/marketing/landing-pages/` | Admin | Landing pages; write `product_ids` / `preselected_ids` (list or comma string) |
| `GET` | `/api/marketing/landing/<slug>/` | Public | Published landing page with its books |
| `POST` | `/api/marketing/landing/<slug>/order/` | Public | Guest order: `{items:[{product_id,quantity}], full_name, phone_number, address, pathao_city_id, pathao_zone_id, pathao_area_id, coupon_code?, note?}` |
| `CRUD` | `/api/marketing/coupons/` | Admin | Discount codes |
| `POST` | `/api/marketing/coupons/validate/` | Public | `{code, subtotal}` → `{discount}` |
| `GET` | `/api/marketing/site-settings/` | Public | Store contact details: `whatsapp_number`, `whatsapp_message`, `whatsapp_enabled`, `whatsapp_url` (ready-made wa.me link, `null` when off), `hotline`, `support_email`, `address`, `facebook_url` |
| `PATCH` | `/api/marketing/site-settings/` | Admin (`change_sitesettings`) | Update contact details; a local number like `01712345678` is saved as `8801712345678` |

- Checkout (`POST /api/orders/buyer/orders/`) accepts `coupon_code` and `note`.
- Orders now include `discount_amount`, `coupon_code`, `source` (`WEBSITE` / `LANDING`), `landing_page`, `customer_note`; `grand_total` subtracts the discount and so does the Pathao cash-to-collect amount.
- Books: `Product.author`, `Product.publisher`, `rating_avg`, `rating_count`; `Category.position` orders Class 1 → 12.
- Demo data: `python manage.py seed_books --reset` (classes, subjects, books with covers, banners, `WELCOME10` coupon, `/offer/ssc-science-pack` landing page).
