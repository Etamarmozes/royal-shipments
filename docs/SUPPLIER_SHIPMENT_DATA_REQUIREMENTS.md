# Royal Linen — Shipment Update Email Standard

**For our suppliers, freight forwarders, and customs brokers.**

To make sure shipment updates land in our system **automatically** and reach the right people without delay, please follow this format whenever you send us an update.

The system reads emails directly. The cleaner the structure, the more accurate the auto-detection — and the less back-and-forth we'll need.

---

## 📧 Subject line format

```
Shipment Update | <Supplier> | PO <po> | <Booking> | <Container>
```

Example:
```
Shipment Update | Nandan Terry | PO 4567 | BK998877 | MSNU5649034
```

Any of these identifiers helps the system match the email to the right shipment automatically: **SHP-ID**, **container number**, **booking number**, **BL/BOL**, **invoice**, or **PO**.

---

## 📋 Body — recommended structure

Plain text, one field per line, label followed by colon. Both English and Hebrew labels are supported.

```
Supplier: <name>
PO: <po number>
Invoice: <invoice number>
Booking: <booking number>
BOL: <bill of lading>
Container: <container no, e.g. MSNU5649034>
Container Type: <40HC / 40HQ / 20'>
Goods: <short description>
Cartons: <quantity>
Carton Size CM: <length × width × height>
Gross Weight KG: <weight>
CBM: <cbm>
ETD: <DD/MM/YYYY>
ETA Israel: <DD/MM/YYYY>
ETA Port: <DD/MM/YYYY>
ETA Warehouse: <DD/MM/YYYY>
Notes: <free text>
```

### Example

```
Supplier: Nandan Terry / A&M Global
PO: 4567
Invoice: INV-2026-0012
Booking: BK998877
BOL: MAEU4061194
Container: MSNU5649034
Container Type: 40HC
Goods: 100% Cotton towels
Cartons: 939
Carton Size CM: 40 × 30 × 25
Gross Weight KG: 7,512
CBM: 60.85
ETD: 22/04/2026
ETA Israel: 12/05/2026
ETA Port: 14/05/2026
ETA Warehouse: 18/05/2026
Notes: Booking confirmed, vessel sailed on schedule.
```

---

## 📎 Attachments

Please attach as PDF when relevant:

| Document            | When                                |
|---------------------|-------------------------------------|
| Commercial Invoice  | Always (when issued)                |
| Packing List        | Always (when issued)                |
| Bill of Lading / BL | Once vessel sailed                  |
| Booking Confirmation| When booking is created             |
| Vessel/sailing notice| Reschedules or delays               |

Filename hint: include the SHP-ID, container, or booking in the filename, e.g. `SHP-006_PackingList.pdf`. This lets the system link the file to the right shipment automatically.

---

## 🌐 English-only quick reference (share with overseas suppliers)

| Field               | Required? | Example                      |
|---------------------|-----------|------------------------------|
| Supplier            | Yes       | Nandan Terry                 |
| PO                  | Yes       | 4567                         |
| Invoice             | Yes       | INV-2026-0012                |
| Booking             | Yes       | BK998877                     |
| BOL                 | If known  | MAEU4061194                  |
| Container           | If known  | MSNU5649034                  |
| Container Type      | If known  | 40HC                         |
| Goods               | Yes       | 100% Cotton towels           |
| Cartons             | Yes       | 939                          |
| Carton Size CM      | Yes       | 40 × 30 × 25                 |
| Gross Weight KG     | Yes       | 7,512                        |
| CBM                 | Yes       | 60.85                        |
| ETD                 | Yes       | DD/MM/YYYY                   |
| ETA Israel          | Yes       | DD/MM/YYYY                   |
| ETA Port            | If known  | DD/MM/YYYY                   |
| ETA Warehouse       | If known  | DD/MM/YYYY                   |
| Notes               | Optional  | Free text                    |

---

## ⚙️ How the system handles your email

When your email arrives:

1. **Parse** — fields above are auto-extracted from the subject + body + (later) PDF attachments.
2. **Match** — the system looks for an existing shipment by **SHP-ID** → **container** → **booking** → **BOL** → **invoice** → **PO**, in that order.
3. **Auto-apply (safe writes)**:
   - Filling an empty field (ETA, booking, BOL, supplier, etc.)
   - Adding a new container number
   - Adding documents and notes
4. **Hold for review (risky writes)**:
   - **ETA changes by more than 3 days** → flagged
   - Replacing an already-set booking / BOL with a different value → flagged
   - Cartons / CBM / weight changes by more than 10% → flagged
   - **Any delay mention** → always flagged with high-priority alert
5. **New shipment** — if no match is found, a draft is created and queued for the operations manager to approve.

---

## ❓ FAQ for suppliers

**Can I send the email in any language?**
The structured fields above (in English) are easiest. Hebrew labels are also recognized for buyers in Israel.

**What if my company already uses a different format?**
Send what you have — the system tries to extract data from free text too. Following this format just gives the highest match rate (95%+ vs ~50–70% for unstructured emails).

**Where do I send the email?**
The Royal Linen logistics inbox. Your account manager will share the address.

**What happens if I send the same update twice?**
Safe — the system deduplicates by Gmail message ID and won't double-process.

---

*Maintained by Royal Linen Operations. Last updated 2026-05-03.*
