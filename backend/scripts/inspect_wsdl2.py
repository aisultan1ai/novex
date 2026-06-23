"""Inspect CSE WSDL — get all method signatures."""
import warnings
warnings.filterwarnings("ignore")
import httpx, re

resp = httpx.get("http://web.cse.ru/1c/ws/Web1C.1cws?wsdl", timeout=20)
wsdl = resp.text

# Find all xs:element definitions for request types
methods = ["Calc", "GetReferenceData", "Tracking", "GetDocuments",
           "DeleteDocuments", "GetFormsForDocuments", "SaveWaybillOffice", "Ping"]

for method in methods:
    pattern = rf'<xs:element name="{method}">(.*?)</xs:element>'
    m = re.search(pattern, wsdl, re.DOTALL)
    if m:
        print(f"\n=== {method} REQUEST ===")
        print(m.group(0)[:800])
    else:
        print(f"\n=== {method} === NOT FOUND in xs:element")
