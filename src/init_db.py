"""Create the SQLite metadata database and register the source documents."""
import sqlite3
from pathlib import Path

ROOT = Path(__file__).resolve().parent.parent
DB_PATH = ROOT / "db" / "metadata.db"
SCHEMA_PATH = ROOT / "db" / "schema.sql"
RAW_DIR = ROOT / "data" / "raw"

NIST = "https://nvlpubs.nist.gov/nistpubs"
CSWP = f"{NIST}/CSWP/NIST.CSWP"

# (filename, title, publisher, series_number, pub_year, status, technology, source_url)
DOCUMENTS = [
    ("sp800-153_wlan.pdf", "Guidelines for Securing Wireless Local Area Networks (WLANs)",
     "NIST", "SP 800-153", 2012, "final", "Wi-Fi",
     f"{NIST}/legacy/sp/nistspecialpublication800-153.pdf"),
    ("sp800-97_80211i.pdf", "Establishing Wireless Robust Security Networks: A Guide to IEEE 802.11i",
     "NIST", "SP 800-97", 2007, "withdrawn", "Wi-Fi",
     f"{NIST}/legacy/sp/nistspecialpublication800-97.pdf"),
    ("sp800-121r2_bluetooth.pdf", "Guide to Bluetooth Security",
     "NIST", "SP 800-121 Rev. 2", 2022, "final", "Bluetooth",
     "https://doi.org/10.6028/NIST.SP.800-121r2-upd1"),
    ("sp800-187_lte.pdf", "Guide to LTE Security",
     "NIST", "SP 800-187", 2017, "final", "LTE",
     f"{NIST}/SpecialPublications/NIST.SP.800-187.pdf"),
    ("cswp-36_5g.pdf", "Applying 5G Cybersecurity and Privacy Capabilities: Introduction to the White Paper Series",
     "NIST", "CSWP 36", 2026, "final", "5G", f"{CSWP}.36.pdf"),
    ("cswp-36A_5g.pdf", "Protecting Subscriber Identifiers with Subscription Concealed Identifier (SUCI)",
     "NIST", "CSWP 36A", 2026, "final", "5G", f"{CSWP}.36A.pdf"),
    ("cswp-36B_5g.pdf", "Using Hardware-Enabled Security to Ensure 5G System Platform Integrity",
     "NIST", "CSWP 36B", 2026, "final", "5G", f"{CSWP}.36B.pdf"),
    ("cswp-36C_5g.pdf", "Reallocation of Temporary Identities",
     "NIST", "CSWP 36C", 2026, "final", "5G", f"{CSWP}.36C.pdf"),
    ("cswp-36D_5g.pdf", "No SUPI-Based Paging",
     "NIST", "CSWP 36D", 2026, "final", "5G", f"{CSWP}.36D.pdf"),
    ("cswp-36E_5g.pdf", "5G Network Security Design Principles",
     "NIST", "CSWP 36E", 2026, "final", "5G", f"{CSWP}.36E.pdf"),
    ("nsa_wireless_public.pdf", "Securing Wireless Devices in Public Settings",
     "NSA", "CSI U/OO/166417-21", 2021, "final", "Wi-Fi/Bluetooth/NFC",
     "https://media.defense.gov/2021/Jul/29/2002815141/-1/-1/0/CSI_SECURING_WIRELESS_DEVICES_IN_PUBLIC.PDF"),
]


def main():
    missing = [d[0] for d in DOCUMENTS if not (RAW_DIR / d[0]).exists()]
    if missing:
        print("WARNING - files not found in data/raw:", missing)

    conn = sqlite3.connect(DB_PATH)
    conn.execute("PRAGMA foreign_keys = ON")
    conn.executescript(SCHEMA_PATH.read_text())
    conn.executemany(
        """INSERT OR IGNORE INTO documents
           (filename, title, publisher, series_number, pub_year, status, technology, source_url)
           VALUES (?, ?, ?, ?, ?, ?, ?, ?)""",
        DOCUMENTS,
    )
    conn.commit()

    print(f"{'ID':<4}{'Series':<22}{'Year':<6}{'Status':<11}Technology")
    for row in conn.execute(
        "SELECT doc_id, series_number, pub_year, status, technology FROM documents ORDER BY doc_id"
    ):
        print(f"{row[0]:<4}{row[1]:<22}{row[2]:<6}{row[3]:<11}{row[4]}")
    conn.close()


if __name__ == "__main__":
    main()
