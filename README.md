# 🚀 ACCS Multi-Vendor E-Commerce & Logistics Platform

> **A Next-Generation, Enterprise-Grade Marketplace Engine** powered by **Django 6**, **Django REST Framework**, **Pathao Courier Aladdin API**, and **Automas SMS Gateway**.

---

## 🌟 Executive Overview

**ACCS** is a multi-vendor e-commerce, fulfillment, and financial management platform designed for scale. It unifies buyers, retail and wholesale merchants, logistics couriers, and platform administrators into one cohesive ecosystem.

### ⚡ Core Capabilities at a Glance
- **Zero-Friction Buyer Onboarding:** 2-step OTP registration with auto-login and SMS password dispatch.
- **Enterprise Vendor Verification:** Automated KYC document verification (NID, Trade License) with administrative audit workflows.
- **Revolutionary Hybrid Fulfillment:** Smart auto-routing for direct vendor parcel pickups or central warehouse consolidation.
- **Deep Logistics Integration:** Native Pathao Courier Aladdin API integration with live pricing, tracking, and HMAC-verified webhooks.
- **Automated Financial Ledger & Overdraft Guard:** Real-time commission debits, double-entry wallet accounting, and auto-suspension of delinquent merchant accounts.
- **Zero-Loss Inventory & Commission Restock:** 1-click order cancellation and return handling with automatic inventory replenishment and wallet refunds.
- **Executive BI Dashboard:** Live analytics for sales trends, parcel pipelines, inventory health, and commission revenue.

---

## 🛠️ Technology Stack

| Layer | Technology | Purpose |
| :--- | :--- | :--- |
| **Backend Framework** | **Django 6.0** & **DRF** | High-performance RESTful API architecture |
| **Asynchronous & Realtime**| **Daphne** & **Channels** | ASGI server and WebSocket infrastructure |
| **Database** | **PostgreSQL** / SQLite | Robust relational storage with `dj_database_url` |
| **Logistics Provider** | **Pathao Courier Aladdin API** | Real-time rates, city/zone mapping, consignment dispatch |
| **SMS Gateway** | **Automas SMS BD** | Instant OTP verification and account credentials dispatch |
| **Documentation** | **DRF Spectacular (OpenAPI 3.0)** | Interactive Swagger UI & Redoc API manual |
| **Authentication** | **Custom JWT + Rotating Sessions**| Dual-token authentication with HTTP-only security cookies |

---

## 💡 Step-by-Step Impactful Features

```mermaid
graph LR
    subgraph Onboarding ["1. Smart Onboarding"]
        OTP[Buyer 2-Step OTP]
        KYC[Vendor KYC Verification]
    end

    subgraph Marketplace ["2. Dynamic Catalog"]
        CatTree[Category Tree]
        Inventory[Low-Stock Alert]
        Cart[Unified Guest & Buyer Cart]
    end

    subgraph FulfillmentEngine ["3. Hybrid Logistics"]
        Direct[Single Shop -> Direct Pickup]
        Hub[Multi Shop -> Central Warehouse]
        Pathao[Pathao Aladdin API Dispatch]
    end

    subgraph FinancialGuard ["4. Financial Ledger"]
        Comm[Automated Commission]
        Wallet[Double-Entry Ledger]
        Overdraft[Auto-Block Overdraft Guard]
    end

    Onboarding --> Marketplace
    Marketplace --> FulfillmentEngine
    FulfillmentEngine --> FinancialGuard
```

---

### 1. 🔐 Frictionless Authentication & Smart Onboarding

#### **A. Buyer Quick Register (2-Step Zero-Password Experience)**
Traditional e-commerce registration forms cause drop-offs. ACCS uses a high-conversion 2-step phone verification:
1. **Step 1 (`POST /api/auth/buyer/register/`):** Buyer enters their phone number and name. An instant 6-digit OTP is sent via SMS.
2. **Step 2 (`POST /api/auth/buyer/register-verify/`):** Upon OTP verification:
   - Account is created automatically with `BUYER` role.
   - A secure 6-digit password (derived from the phone number) is generated and sent via SMS for future logins.
   - The user is logged in immediately, receiving JWT tokens in both the response and secure HTTP-only cookies.

#### **B. Merchant & Vendor KYC Verification**
- Merchants register via `POST /api/auth/register/` with business documents (NID Front, NID Back, Trade License).
- Accounts default to `is_approved=False` until an Administrator audits the KYC profile and approves it via `POST /api/admin/users/{id}/approve-kyc`.

#### **C. Rotating Token Vault & Session Security**
- Access tokens expire in 24 hours.
- Refresh tokens are cryptographically random (64-byte strings), stored as SHA-256 hashes in the database.
- Every refresh request rotates the token, preventing replay attacks.

---

### 2. 🛡️ Role-Based Access Control (RBAC) & Admin Governance

ACCS implements an **Admin Bypass Permission Architecture** ([`AdminBypassPermission`](file:///d:/Shain/Accs/users/permissions.py)):
- **Granular Roles:** `BUYER`, `VENDOR`, `RETAILER`, `WHOLESALER`, `SERVICE_PROVIDER`, `STAFF`, and `ADMIN`.
- **Dedicated Admin Login (`POST /api/admin/login/`):** Strictly enforces `is_staff: true`. Normal users are blocked at the perimeter.
- **Dynamic Permission Grants:** Returns the admin's group memberships and granular Django permissions (`can_post_product`, `can_auto_approve_product`) so client UIs can dynamically render authorized menus.
- **Account Moderation:** Administrators can instantly `suspend` or `unsuspend` accounts.

---

### 3. 🏪 Merchant Shop Management & 4-Factor Reviews

#### **A. Shop Profile Architecture**
- Each merchant manages a unique [ShopProfile](file:///d:/Shain/Accs/vendors/models.py) with shop type (`RETAILER` or `WHOLESALER`), logo, banner, physical address, operating hours, trade license, and **Pathao Pickup Store ID**.
- Access own shop details via `GET /api/vendors/shops/me`.

#### **B. 4-Factor Customer Review System**
Buyers evaluate vendors across 4 transparent parameters:
1. **Product Quality Rating** (1–5)
2. **Pricing Rating** (1–5)
3. **On-Time Delivery Rating** (1–5)
4. **Behavior & Communication Rating** (1–5)
- The overall rating and review counts are recalculated automatically on every review submission.
- Vendors cannot review their own shops.
- Admins have an adjustment lever (`admin_rating_adjustment`) to moderate ratings when necessary.

---

### 4. 📦 Product Catalog, Dynamic Pricing & Smart Inventory

#### **A. Recursive Category Navigation**
- Supports unlimited nested category tiers (`GET /api/products/categories/tree`).
- Searchable and paginated for fast catalog exploration.

#### **B. Automated Discount Engine**
- Supports **FLAT** (fixed BDT) and **PERCENTAGE** discounts.
- Time-gated: discounts only apply if current time is within `discount_start_date` and `discount_end_date`.
- Calculates `after_discount_price` on-the-fly.

#### **C. Minimum Order Quantity (MOQ) & Stock Reservation**
- Enforces wholesale and retail MOQ limits.
- Tracks `stock_quantity` vs. `low_stock_threshold`.
- Dedicated alert endpoint (`GET /api/products/products/low-stock/`) alerts vendors and admins when inventory needs replenishment.

#### **D. Product Approval Workflow**
- Standard vendors submit products in `PENDING` status.
- Trusted vendors with `can_auto_approve_product` permission get instant auto-publishing.
- Admins audit and publish products via `/approve` or reject with reason via `/reject`.

---

### 5. 🛒 Unified Cart System (Guest & Authenticated)

- **Guest Shopping:** Visitors can add items to cart immediately without logging in. Session state is tracked via UUID stored in cookies or `x-guest-id` header.
- **Smart Cart Merging:** When a guest logs in or completes registration, their guest cart items are automatically merged into their user cart without duplicates.

---

### 6. 🚚 Revolutionary Hybrid Fulfillment Engine

ACCS solves the fundamental challenge of multi-vendor marketplaces: **Where does the courier pick up the order?**

```
                  ┌──────────────────────────────┐
                  │      Buyer Cart Checkout     │
                  └──────────────┬───────────────┘
                                 │
                 How many vendor shops in cart?
                                 │
                ┌────────────────┴────────────────┐
                ▼                                 ▼
      [ Exactly 1 Vendor ]              [ 2+ Different Vendors ]
                │                                 │
      Fulfillment Type:                 Fulfillment Type:
       "DIRECT_VENDOR"                   "CENTRAL_HUB"
                │                                 │
  Courier collects directly from       Vendors send items to Central Hub;
    Vendor's Shop & Store ID          Courier picks up consolidated parcel
```

#### **How It Works:**
1. **Single-Vendor Order (`DIRECT_VENDOR`):**
   - Courier collects parcel directly from that vendor's registered shop address and `pathao_store_id`.
2. **Multi-Vendor Order (`CENTRAL_HUB`):**
   - Items originate from different parts of the country.
   - The order fulfillment routes through the **Central Hub Warehouse** (`pathao_hub_store_id`).
3. **Sub-Order Splitting:**
   - When an order is approved, it automatically splits into dedicated [VendorOrder](file:///d:/Shain/Accs/orders/models.py) sub-orders for each shop.
   - Delivery fees are proportionally apportioned across each sub-order.

---

### 7. 🚛 Deep Pathao Courier Logistics Integration

Full native integration with Pathao Courier's Aladdin Merchant API:
- **Location Lookup:** Real-time lookup for deliverable Cities, Zones, and Areas.
- **Live Rate Estimation:** Dynamic shipping fee calculation (`/api/orders/pathao/calculate-price/`) based on parcel weight and destination city/zone.
- **1-Click Consignment Dispatch:** Generates consignment ID and tracking code with automatic Cash on Delivery (COD) amount calculation (`/api/orders/admin/orders/{id}/dispatch-pathao/`).
- **Live Parcel Tracking:** Returns real-time delivery checkpoints and timeline history (`/track-pathao`).
- **Secure Webhook Listener:** Listens for Pathao courier updates (`Pickup_Pending`, `In_Transit`, `Delivered`, `Returned`) secured with **HMAC-SHA256** signature verification.
- **Sandbox Delivery Simulator:** Built-in 1-click test simulator (`/simulate-delivery`) to test completed delivery workflows in development.

---

### 8. 💳 Financial Ledger, Platform Commissions & Overdraft Guard

#### **A. Automated Platform Commission**
- Each product carries a platform commission percentage (`woner_commission`).
- When an administrator approves an order, the system calculates the exact commission and records an [OrderCommission](file:///d:/Shain/Accs/orders/models.py).
- The commission amount is debited from the vendor's wallet balance with a corresponding `OUT` transaction.

#### **B. Automated Delinquency Guard (Overdraft Safety)**
- Every merchant has a [Wallet](file:///d:/Shain/Accs/wallets/models.py) with a defined `credit_limit` (default: **2000.00 BDT**).
- **The Safety Trigger:** If commission deductions drive a vendor's balance below `-credit_limit`:
  ```python
  if wallet.balance < -wallet.credit_limit:
      shop.is_blocked = True  # Automatically locks merchant store
  ```
- **Instant Marketplace Isolation:** Once blocked, all products from this shop are automatically hidden from the public marketplace.
- As soon as the merchant clears their dues or an admin grants a credit, the shop automatically unblocks.

#### **C. Admin Financial Controls**
- Admins can inspect delinquent accounts via `/api/blocked-profiles/`.
- Admins can customize credit limits (`update-credit-limit`) or inject promotional credits (`add-discount`).

---

### 9. 🔄 Zero-Loss Return & Inventory Restock Engine

When orders are cancelled or returned by the courier:
1. **Inventory Restoration:** Calling `/restock` immediately restores the deducted quantities back to the product's `stock_quantity`.
2. **Commission Reversal:** The platform commission previously debited from the vendor's wallet is **refunded in full** (creates an `IN` transaction in the ledger).
3. **Double-Restock Prevention:** Protected by `is_restocked` state flags to ensure inventory and money cannot be credited twice.

---

### 10. 📊 Executive Analytics & Broadcast Communications

#### **A. Real-Time Admin Analytics (`GET /api/admin/dashboard/analytics/`)**
A single call gives administrators an executive summary:
- **Users & Merchants:** Total active buyers and registered vendor shops.
- **Sales Volume:** Monthly sales curves for delivered orders.
- **Top Merchants:** Leaderboard of highest-rated vendors by review volume.
- **Revenue Tracker:** Platform commission earnings broken down by **Today**, **This Month**, and **All-Time**.
- **Inventory Health:** Total items, low stock warnings, and out-of-stock items.
- **Logistics Pipeline:** Active parcels in transit, delivered, returned, and awaiting restock.

#### **B. Broadcast Announcement System**
Targeted communications platform (`BroadcastAnnouncement`) allowing administrators to broadcast updates to:
- `ALL` Users
- `BUYERS` Only
- `VENDORS` Only
- `STAFF` Only
- Specific individual users

---

## 📡 API Quick Reference

Explore full interactive docs at:
- **Swagger UI:** `http://127.0.0.1:8000/docs/`
- **Redoc UI:** `http://127.0.0.1:8000/redoc/`
- **OpenAPI Schema:** `http://127.0.0.1:8000/api/schema/`

| Category | Endpoint | Method | Access | Description |
| :--- | :--- | :---: | :---: | :--- |
| **Auth** | `/api/auth/buyer/register/` | POST | Public | Send OTP for Buyer registration |
| | `/api/auth/buyer/register-verify/`| POST | Public | Verify OTP & auto-login Buyer |
| | `/api/auth/register/` | POST | Public | Vendor onboarding with KYC upload |
| | `/api/auth/login/` | POST | Public | General login (Buyer & Vendor) |
| | `/api/auth/shipping-address/` | GET/POST/PATCH | Buyer | Mapped Pathao shipping address |
| **Admin** | `/api/admin/login/` | POST | Staff | Dedicated staff portal login |
| | `/api/admin/users/` | GET/PATCH | Admin | User management & KYC review |
| | `/api/admin/dashboard/analytics/` | GET | Admin | Platform executive statistics |
| | `/api/blocked-profiles/` | GET | Admin | Merchants exceeding overdraft limit |
| **Catalog**| `/api/products/categories/tree` | GET | Public | Hierarchical category navigation |
| | `/api/products/products/` | GET/POST | Public/Vendor| Browse or submit new products |
| | `/api/products/products/low-stock/`| GET | Vendor/Admin| Smart inventory restock alerts |
| | `/api/products/products/{id}/approve`| POST | Admin | Review and publish vendor product |
| **Cart** | `/api/orders/cart/` | GET | Public/Buyer | Fetch user or guest cart |
| | `/api/orders/cart/add/` | POST | Public/Buyer | Add item to cart |
| **Orders** | `/api/orders/buyer/orders/` | POST | Buyer | Checkout cart & place order |
| | `/api/orders/admin/orders/{id}/approve/`| POST | Admin | Approve order, reserve stock, split sub-orders |
| | `/api/orders/admin/orders/{id}/dispatch-pathao/`| POST | Admin | Dispatch parcel to Pathao Courier |
| | `/api/orders/admin/orders/{id}/restock/`| POST | Admin | Restock returned order & refund commission |
| **Logistics**| `/api/orders/pathao/calculate-price/`| POST | Public | Calculate live shipping fee |
| | `/api/orders/webhooks/pathao/` | POST | Pathao | Webhook receiver for parcel updates |
| **Wallets** | `/api/wallets/my-wallet/` | GET | Vendor | Live balance & credit limit |
| | `/api/wallets/my-transactions/` | GET | Vendor | Full financial transaction history |

---

## 🚀 Quick Setup & Installation

### 1. Clone & Activate Virtual Environment
```bash
# Windows
python -m venv pro_env
pro_env\Scripts\activate

# Linux / macOS
python3 -m venv pro_env
source pro_env/bin/activate
```

### 2. Install Dependencies
```bash
pip install -r requirements.txt
```

### 3. Configure Environment Variables (`.env`)
Create a `.env` file in the project root:
```env
DEBUG=True
SECRET_KEY=your-secure-secret-key
DATABASE_URL=postgres://postgres:password@localhost:5432/accs

# Automas SMS Gateway
AUTOMAS_SMS_API_KEY=your_automas_api_key
AUTOMAS_SMS_SENDER_ID=your_active_sender_id
AUTOMAS_SMS_URL=https://api.automas.com.bd/smsapiv3

# Pathao Courier API
PATHAO_BASE_URL=https://courier-api-sandbox.pathao.com
PATHAO_CLIENT_ID=your_client_id
PATHAO_CLIENT_SECRET=your_client_secret
PATHAO_USERNAME=your_username
PATHAO_PASSWORD=your_password
PATHAO_GRANT_TYPE=password
PATHAO_WEBHOOK_SECRET=your_webhook_secret
```

### 4. Apply Database Migrations
```bash
python manage.py migrate
```

### 5. Run the Test Suite
Verify that all core business logic and fulfillment rules pass:
```bash
python manage.py test orders
```

### 6. Start the Local Server
```bash
python manage.py runserver
```
Visit `http://127.0.0.1:8000/docs/` to explore and test the interactive API documentation.

---

## 📄 License & Ownership
Copyright © 2026 **ACCS Platform**. All rights reserved.
Built for high-performance commerce and reliable logistics.
