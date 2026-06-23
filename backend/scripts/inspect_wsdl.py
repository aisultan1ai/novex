"""Inspect CSE WSDL to extract real namespace and method signatures."""
import warnings

warnings.filterwarnings("ignore")

import re

import httpx

resp = httpx.get("http://web.cse.ru/1c/ws/Web1C.1cws?wsdl", timeout=20)
wsdl = resp.text

print("=== NAMESPACE ===")
ns_matches = re.findall(r'xmlns(?::\w+)?="([^"]+)"', wsdl[:500])
for ns in ns_matches:
    print(" ", ns)

print("\n=== TARGET NAMESPACE ===")
tns = re.findall(r'targetNamespace="([^"]+)"', wsdl[:500])
print(" ", tns)

print("\n=== OPERATIONS ===")
ops = re.findall(r'<operation name="(\w+)"', wsdl)
print(" ", ops)

print("\n=== SOAP BINDINGS (SOAPAction) ===")
bindings = re.findall(r'<(?:soapbind|soap12bind):operation[^/]*/>', wsdl)
for b in bindings[:15]:
    print(" ", b)

print("\n=== MESSAGE PARTS (first GetReferenceData) ===")
# Find GetReferenceData message
idx = wsdl.find("GetReferenceData")
if idx > 0:
    chunk = wsdl[max(0, idx-200):idx+2000]
    print(chunk[:2000])

print("\n=== FULL WSDL PART (portType operations) ===")
pt_idx = wsdl.find("<portType")
if pt_idx > 0:
    print(wsdl[pt_idx:pt_idx+3000])
