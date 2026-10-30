"""Generator script for synthetic invoice evaluation dataset (invoice-eval-v1)."""

from __future__ import annotations

import json
from pathlib import Path

DATASET_DIR = Path(__file__).resolve().parent.parent / "evaluation" / "dataset" / "invoice-eval-v1"
DOCS_DIR = DATASET_DIR / "documents"
GROUND_TRUTH_FILE = DATASET_DIR / "ground_truth.jsonl"

DATASET_ITEMS = [
    {
        "id": "inv_001",
        "ground_truth": {
            "invoice_number": "INV-2026-001",
            "vendor": "Acme Industrial Supplies",
            "invoice_date": "2026-01-15",
            "total": 1450.75,
        },
        "content": """# INVOICE

**Acme Industrial Supplies Ltd.**  
123 Market Street, Suite 400, Chicago, IL 60601  
Tax ID: US-99281726

**BILL TO:**  
Docling Enterprise Corp  
500 Tech Boulevard, Austin, TX 78701  

---

**Invoice Number:** INV-2026-001  
**Invoice Date:** January 15, 2026  
**Due Date:** February 15, 2026  
**Payment Terms:** Net 30  

### Description of Goods & Services

| Item | Description | Qty | Unit Price | Amount |
|---|---|---|---|---|
| 1 | Heavy Duty Shelving Unit | 4 | $250.00 | $1,000.00 |
| 2 | Industrial Casters 4-Pack | 5 | $45.00 | $225.00 |
| 3 | Safety Lock Pins (Box) | 10 | $15.00 | $150.00 |

**Subtotal:** $1,375.00  
**Shipping & Handling:** $75.75  
**TOTAL AMOUNT DUE:** $1,450.75  

*Thank you for your business! Please remit payment via ACH or wire transfer.*
""",
    },
    {
        "id": "inv_002",
        "ground_truth": {
            "invoice_number": "GC-8921",
            "vendor": "Global Cloud Logistics",
            "invoice_date": "2026-02-18",
            "total": 3200.00,
        },
        "content": """# COMMERCIAL INVOICE

**Global Cloud Logistics Inc.**  
25 Wharfside Way, London, EC2R 8AH, United Kingdom  

Invoice Ref: GC-8921  
Date of Issue: 18/02/2026  
Customer Reference: PO-99021  

Services Rendered:
- Freight forward customs handling: £1,200.00
- Multi-region pallet warehousing: £1,500.00
- Expedited dispatch courier: £500.00

Sub-Total: £3,200.00  
Tax / VAT (0% Export): £0.00  
Balance Due: £3,200.00  
""",
    },
    {
        "id": "inv_003",
        "ground_truth": {
            "invoice_number": "NOS-1049",
            "vendor": "Nexus Office Solutions",
            "invoice_date": "2026-03-04",
            "total": 450.20,
        },
        "content": """# Nexus Office Solutions LLC
742 Evergreen Terrace, Springfield, OR

Tax Invoice
Invoice #: NOS-1049
Date: March 4, 2026

Items:
1. Ergonomic Mesh Office Chair (Qty 1) - $350.00
2. Desk Mat & Cable Management (Qty 2) - $65.00
3. Shipping: $35.20

Total: $450.20
Paid by Credit Card: $0.00
Amount Outstanding: $450.20
""",
    },
    {
        "id": "inv_004",
        "ground_truth": {
            "invoice_number": "VTX-4401",
            "vendor": "Vertex Data Systems",
            "invoice_date": "2026-04-12",
            "total": 12900.50,
        },
        "content": """# VERTEX DATA SYSTEMS
Enterprise Software & Infrastructure Billing
Web: https://vertexdata.io

INVOICE: VTX-4401
DATE: 2026.04.12
ACCOUNT ID: ACC-88192

Statement of Charges:
- High-Performance Compute Cluster (April Reservation): $10,000.00
- Dedicated NVMe Object Storage (50TB): $1,800.00
- Premium 24/7 SRE Support Add-on: $1,100.50

Total USD Due: $12,900.50
""",
    },
    {
        "id": "inv_005",
        "ground_truth": {
            "invoice_number": "SH-7712",
            "vendor": "Summit Hardware",
            "invoice_date": "2026-05-20",
            "total": 85.99,
        },
        "content": """# SUMMIT HARDWARE CORP.
Denver, Colorado

Bill Number: SH-7712
Date: 05-20-2026

Sold to: Quick Repair Shop
Item: Drill Bit Cobalt Set - Qty 1 @ $79.99
Sales Tax (7.5%): $6.00

Total Payable: $85.99
""",
    },
    {
        "id": "inv_006",
        "ground_truth": {
            "invoice_number": "QE-901",
            "vendor": "Quantum Energy Services",
            "invoice_date": "2026-06-01",
            "total": 5420.00,
        },
        "content": """# QUANTUM ENERGY SERVICES Ltd
Monthly Facility Utility Billing

Invoice ID: QE-901
Date of Invoice: 2026-06-01
Service Period: May 1 - May 31, 2026

Commercial Electricity (42,000 kWh): $4,200.00
Peak Demand Surcharge: $800.00
Grid Maintenance Fee: $420.00

Grand Total: $5,420.00
Payment due upon receipt.
""",
    },
    {
        "id": "inv_007",
        "ground_truth": {
            "invoice_number": "HMG-302",
            "vendor": "Horizon Media Group",
            "invoice_date": "2026-07-19",
            "total": 875.00,
        },
        "content": """# Horizon Media Group LLC
Creative & Brand Strategy

Invoice No: HMG-302
Issue Date: July 19, 2026
Client: Platform Growth Team

Description:
- Technical Documentation Illustration Pack: $500.00
- Architecture Diagram Vector Polish: $375.00

Total Balance: $875.00
""",
    },
    {
        "id": "inv_008",
        "ground_truth": {
            "invoice_number": "IC-5519",
            "vendor": "Ironclad Security Technologies",
            "invoice_date": "2026-08-22",
            "total": 2400.00,
        },
        "content": """# IRONCLAD SECURITY TECHNOLOGIES Inc.
Cybersecurity Operations & Audit

Reference: IC-5519
Billing Date: 22/08/2026

Work Summary:
Quarterly Penetration Test & Container Vulnerability Scan
Scope: Kubernetes Ingress, Redis cluster, Worker Nodes

Total Professional Fee: $2,400.00
""",
    },
    {
        "id": "inv_009",
        "ground_truth": {
            "invoice_number": "BSC-109",
            "vendor": "BlueSky Catering",
            "invoice_date": "2026-09-09",
            "total": 650.40,
        },
        "content": """# BlueSky Catering Ltd.
Catering & Corporate Hospitality

Invoice: BSC-109
Date: Sep 09, 2026

Event: Q3 Engineering Hackathon
- Lunch Buffet (30 persons): $500.00
- Beverage Service & Refreshments: $110.00
- Gratuity & Delivery: $40.40

Total: $650.40
""",
    },
    {
        "id": "inv_010",
        "ground_truth": {
            "invoice_number": "PFT-883",
            "vendor": "Pioneer Freight & Transport",
            "invoice_date": "2026-10-15",
            "total": 1850.25,
        },
        "content": """# PIONEER FREIGHT & TRANSPORT
Freight Waybill & Invoice

Bill No: PFT-883
Date: 2026-10-15

Consignment: 2 Pallets Server Rack Hardware
Route: Dallas, TX -> Ashburn, VA
Mileage charge: $1,600.00
Fuel Surcharge: $195.25
Toll charges: $55.00

Total Charges: $1,850.25
""",
    },
    {
        "id": "inv_011",
        "ground_truth": {
            "invoice_number": "SCS-2026-11",
            "vendor": "Sentinel Cyber Solutions",
            "invoice_date": "2026-11-02",
            "total": 9500.00,
        },
        "content": """# SENTINEL CYBER SOLUTIONS
200 Federal Plaza, New York, NY

INVOICE NUMBER: SCS-2026-11
DATE OF BILL: Nov 2, 2026

Annual SIEM & Security Log Ingestion License (100 Nodes)
Subtotal: $9,500.00
Tax: $0.00
TOTAL: $9,500.00
""",
    },
    {
        "id": "inv_012",
        "ground_truth": {
            "invoice_number": "APC-441",
            "vendor": "Alpha Packaging",
            "invoice_date": "2026-12-05",
            "total": 320.15,
        },
        "content": """# Alpha Packaging Co.
Industrial Boxes & Wrapping Supplies

Invoice: APC-441
Date: 12/05/2026

500x Recycled Heavy Duty Corrugated Boxes: $280.00
Biodegradable Packing Tape (12 rolls): $40.15

Grand Total Due: $320.15
""",
    },
    {
        "id": "inv_013",
        "ground_truth": {
            "invoice_number": "BEW-992",
            "vendor": "Beacon Electrical Works",
            "invoice_date": "2026-01-28",
            "total": 1120.00,
        },
        "content": """# Beacon Electrical Works Ltd
Contractor Invoice

Invoice #: BEW-992
Date: 2026-01-28
Job Site: Data Center Room B

Labor: 14 hours @ $70/hr = $980.00
Materials: Conduit, 3-phase PDU breaker = $140.00

Balance Due: $1,120.00
""",
    },
    {
        "id": "inv_014",
        "ground_truth": {
            "invoice_number": "DCP-761",
            "vendor": "Delta Consulting Partners",
            "invoice_date": "2026-02-14",
            "total": 4750.80,
        },
        "content": """# DELTA CONSULTING PARTNERS LLC
Strategy & Cloud Architecture

Invoice Reference: DCP-761
Date: 14 Feb 2026

Kubernetes Migration & KEDA Tuning Engagement
Consultant Hours: 25 hrs @ $180/hr = $4,500.00
Travel & Admin Expenses: $250.80

Net Amount Payable: $4,750.80
""",
    },
    {
        "id": "inv_015",
        "ground_truth": {
            "invoice_number": "EFM-003",
            "vendor": "Evergreen Facility Maintenance",
            "invoice_date": "2026-03-30",
            "total": 910.00,
        },
        "content": """# Evergreen Facility Maintenance Inc.
Monthly Cleaning & Environmental Controls

Invoice: EFM-003
Invoice Date: 2026-03-30

Server Room HEPA filtration service: $450.00
Facility deep sanitization: $460.00

Total: $910.00
""",
    },
    {
        "id": "inv_016",
        "ground_truth": {
            "invoice_number": "HSS-552",
            "vendor": "Helios Solar Systems",
            "invoice_date": "2026-04-18",
            "total": 15300.00,
        },
        "content": """# HELIOS SOLAR SYSTEMS INC.
Clean Power Solutions

Invoice ID: HSS-552
Date: 2026-04-18

Commercial Inverter Replacement & Battery Rack Integration:
Subtotal: $15,000.00
Permit fees: $300.00
Total Due: $15,300.00
""",
    },
    {
        "id": "inv_017",
        "ground_truth": {
            "invoice_number": "ZMS-881",
            "vendor": "Zenith Medical Supplies",
            "invoice_date": "2026-05-09",
            "total": 2840.60,
        },
        "content": """# Zenith Medical Supplies Corp.
Healthcare & Safety Equipment

Invoice #: ZMS-881
Date: 05/09/2026

First Aid Station Kits (Industrial): $1,200.00
Automated External Defibrillator (AED) Unit: $1,500.00
State Sales Tax: $140.60

Invoice Total: $2,840.60
""",
    },
    {
        "id": "inv_018",
        "ground_truth": {
            "invoice_number": "AHE-120",
            "vendor": "Atlas Heavy Equipment",
            "invoice_date": "2026-06-25",
            "total": 34500.00,
        },
        "content": """# ATLAS HEAVY EQUIPMENT LLC
Generator Rental & Power Backup

Invoice Number: AHE-120
Date: June 25, 2026

Diesel Generator 500kVA Rental (3 Months): $30,000.00
Delivery, Rigging & Commissioning: $4,500.00

Total Amount: $34,500.00
""",
    },
    {
        "id": "inv_019",
        "ground_truth": {
            "invoice_number": "VIS-990",
            "vendor": "Velocity Internet Services",
            "invoice_date": "2026-07-04",
            "total": 199.99,
        },
        "content": """# Velocity Internet Services
Dedicated Fiber Billing

Invoice ID: VIS-990
Date: 2026-07-04

Gigabit Symmetrical Fiber Circuit (July 2026): $199.99
Total Due: $199.99
""",
    },
    {
        "id": "inv_020",
        "ground_truth": {
            "invoice_number": "SPD-331",
            "vendor": "Sterling Print & Design",
            "invoice_date": "2026-08-11",
            "total": 430.50,
        },
        "content": """# Sterling Print & Design LLC
Marketing Collateral

Invoice: SPD-331
Date: 11/08/2026

Product Brochures (Glossy, 1000 copies): $380.00
Direct Shipping: $50.50

Total Due: $430.50
""",
    },
    {
        "id": "inv_021",
        "ground_truth": {
            "invoice_number": None,
            "vendor": "Northern Woodcraft",
            "invoice_date": "2026-09-14",
            "total": 560.00,
        },
        "content": """# Order Receipt
**Northern Woodcraft Shop**  
Custom conference table cable tray carpentry.  

Date: 2026-09-14  
(Note: Paid in cash on delivery, no formal invoice issued)  

Amount Paid: $560.00  
""",
    },
    {
        "id": "inv_022",
        "ground_truth": {
            "invoice_number": "ASL-404",
            "vendor": "Apex Software Labs",
            "invoice_date": "2026-10-20",
            "total": 1780.00,
        },
        "content": """# APEX SOFTWARE LABS Inc.
Invoice: ASL-404
Invoice Date: 2026-10-20

Itemized Charges:
- Enterprise Docling Orchestration Plugin: $2,000.00
- Early Adopter Promotional Discount: -$220.00

Net Payable Total: $1,780.00
""",
    },
    {
        "id": "inv_023",
        "ground_truth": {
            "invoice_number": "KRO-229",
            "vendor": "Kromer Automotive",
            "invoice_date": "2026-11-03",
            "total": 4165.00,
        },
        "content": """# KROMER AUTOMOTIVE GMBH
Munich, Germany

Rechnung / Invoice: KRO-229
Datum: 03.11.2026

Fleet Maintenance & EV Charging Station Install:
Netto / Subtotal: €3,500.00
MwSt / VAT (19%): €665.00
Gesamtbetrag / Total: €4,165.00
""",
    },
    {
        "id": "inv_024",
        "ground_truth": {
            "invoice_number": "QFP-108",
            "vendor": "QuickFix Plumbing",
            "invoice_date": None,
            "total": 275.50,
        },
        "content": """# QuickFix Plumbing Co.
Emergency Facility Repair

Invoice #: QFP-108
(Date unprinted due to thermal printer error)

Repaired broken valve in restrooms: $250.00
Parts: $25.50

Total: $275.50
""",
    },
    {
        "id": "inv_025",
        "ground_truth": {
            "invoice_number": "THI-9900",
            "vendor": "Titan Heavy Industries",
            "invoice_date": "2026-12-15",
            "total": 88450.00,
        },
        "content": """# TITAN HEAVY INDUSTRIES LTD.
Global Manufacturing Solutions

INVOICE NUMBER: THI-9900
DATE: Dec 15, 2026

Heavy Machinery Installation (Phase 1): $80,000.00
Calibration & Structural Testing: $8,450.00

Final Balance Due: $88,450.00
""",
    },
]


def generate_dataset():
    DOCS_DIR.mkdir(parents=True, exist_ok=True)
    DATASET_DIR.mkdir(parents=True, exist_ok=True)

    with open(GROUND_TRUTH_FILE, "w", encoding="utf-8") as gt_file:
        for item in DATASET_ITEMS:
            doc_id = item["id"]
            doc_path = DOCS_DIR / f"{doc_id}.md"
            with open(doc_path, "w", encoding="utf-8") as df:
                df.write(item["content"].strip() + "\n")

            gt_entry = {"doc_id": doc_id, **item["ground_truth"]}
            gt_file.write(json.dumps(gt_entry) + "\n")

    print(f"Generated {len(DATASET_ITEMS)} synthetic documents in {DOCS_DIR}")
    print(f"Written ground truth to {GROUND_TRUTH_FILE}")


if __name__ == "__main__":
    generate_dataset()
