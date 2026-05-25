"""IAM (Maroc Telecom) multi-page invoice parser - VERSION CORRIGÉE."""

from __future__ import annotations

import io
import re
from dataclasses import dataclass, field, asdict
from pathlib import Path
from typing import Any, BinaryIO, Optional, Tuple, List

import pdfplumber


_AMOUNT = r"-?\d{1,3}(?:[ \u00a0]\d{3})*(?:[.,]\d+)?"
_DATE = r"\d{2}/\d{2}/\d{4}"

# Patterns plus flexibles
RE_INVOICE_NUMBER = re.compile(
    r"N°\s*Facture\s*:?\s*([A-Z0-9\s]+?)(?:\n|\s{2,}|$)",
    re.IGNORECASE
)
RE_CLIENT_NUMBER = re.compile(
    r"N°\s*Client\s*:?\s*(\S+)",
    re.IGNORECASE
)
RE_INVOICE_DATE = re.compile(
    r"Date\s*Facture\s*:?\s*(\d{2}[/\-]\d{2}[/\-]\d{4})",
    re.IGNORECASE
)
RE_PHONE = re.compile(
    r"N°\s*d['\u2019]Appel\s*:?\s*(0[567]\d[\s\-]?\d{2}[\s\-]?\d{2}[\s\-]?\d{2}[\s\-]?\d{2})",
    re.IGNORECASE
)
RE_PAGE_NUM = re.compile(r"Page\s+(\d+)/(\d+)", re.IGNORECASE)
RE_TOTAL_CONTRAT = re.compile(
    r"TOTAL\s+CONTRAT\s*:?\s*([\d\s\.,]+)",
    re.IGNORECASE
)
# Ajoutez ces patterns (vers ligne 55)
RE_CLIENT_NUMBER = re.compile(
    r"(?:N°\s*Client|N°\s*d['\u2019]Abonnement|N°\s*Abonnement)\s*:?\s*(\S+)",
    re.IGNORECASE
)
RE_PERIOD = re.compile(
    r"P[ée]riode\s+factur[ée]e\s*:?\s*(\d{2}[/\-]\d{2}[/\-]\d{4})\s*[-à]\s*(\d{2}[/\-]\d{2}[/\-]\d{4})",
    re.IGNORECASE
)

# Pour capturer les lignes du tableau
RE_TABLE_ROW = re.compile(
    r"^(?P<desc>.+?)\s+(?P<start>" + _DATE + r")\s+(?P<end>" + _DATE + r")\s+(?P<amount>" + _AMOUNT + r")\s*$"
)

RE_PONCTUAL_ROW = re.compile(r"^(?P<desc>.+?)\s+(?P<amount>" + _AMOUNT + r")\s*$")


def _to_float(value: str) -> float:
    """Convertit un montant formaté français en float."""
    if not value:
        return 0.0
    cleaned = value.replace("\u00a0", "").replace(" ", "").replace(",", ".")
    # Extraire seulement les chiffres et le point
    match = re.search(r"(\d+(?:\.\d+)?)", cleaned)
    if match:
        return float(match.group(1))
    return 0.0


@dataclass
class LineItem:
    description: str
    amount: float
    date_start: Optional[str] = None
    date_end: Optional[str] = None


@dataclass
class Contract:
    page_number: int
    document_page: Optional[str] = None
    contract_type: str = ""
    phone_number: Optional[str] = None
    period_start: Optional[str] = None
    period_end: Optional[str] = None
    articles_mensuels: int = 0
    articles_ponctuels: int = 0
    frais_mensuels: List[LineItem] = field(default_factory=list)
    frais_ponctuels: List[LineItem] = field(default_factory=list)
    total_contrat: float = 0.0


@dataclass
class GlobalSummary:
    page_number: int = 1
    document_page: Optional[str] = None
    frais_abonnement_services: float = 0.0
    frais_ponctuels: float = 0.0
    montant_ht: float = 0.0
    montant_tva: float = 0.0
    montant_ttc: float = 0.0
    montant_du: float = 0.0


@dataclass
class InvoiceData:
    source_file: str
    client_number: Optional[str] = None
    invoice_number: Optional[str] = None
    invoice_date: Optional[str] = None
    period_start: Optional[str] = None
    period_end: Optional[str] = None
    global_summary: GlobalSummary = field(default_factory=GlobalSummary)
    contracts: List[Contract] = field(default_factory=list)
    total: float = 0.0

    def to_dict(self) -> dict[str, Any]:
        return asdict(self)


def _identify_page_kind(text: str) -> Tuple[str, Optional[str]]:
    """Identifie le type de page."""
    if re.search(r"Forfait\s+Optimis", text, re.IGNORECASE):
        return "contract", "Forfait Optimis"
    if re.search(r"Illimit[ée]\s+Mobile\s+Plafonn[ée]", text, re.IGNORECASE):
        return "contract", "Illimité Mobile Plafonné"
    if re.search(r"Illimit[ée]\s+Mobile", text, re.IGNORECASE):
        return "contract", "Illimité Mobile"
    if RE_TOTAL_CONTRAT.search(text):
        return "contract", "Contrat"
    if re.search(r"Page\s+globale|R[ée]capitulatif", text, re.IGNORECASE):
        return "global", None
    return "unknown", None


def _document_page(text: str) -> Optional[str]:
    """Extrait le numéro de page document."""
    m = RE_PAGE_NUM.search(text)
    if m:
        return f"{m.group(1)}/{m.group(2)}"
    return None


def _parse_global_page(text: str) -> GlobalSummary:
    """Parse la page globale/récapitulative."""
    g = GlobalSummary()
    g.document_page = _document_page(text)
    
    patterns = {
        'frais_abonnement_services': [
            r"Frais\s+d['\u2019]abonnement\s+et\s+services\s*:?\s*(" + _AMOUNT + ")",
            r"Abonnement\s+et\s+services\s*:?\s*(" + _AMOUNT + ")",
        ],
        'frais_ponctuels': [
            r"Frais\s+ponctuels\s+li[ée]s\s+au\s+contrat\s*:?\s*(" + _AMOUNT + ")",
            r"Frais\s+ponctuels\s*:?\s*(" + _AMOUNT + ")",
        ],
        'montant_ht': [
            r"Montant\s+HT\s*:?\s*(" + _AMOUNT + ")",
            r"Total\s+HT\s*:?\s*(" + _AMOUNT + ")",
        ],
        'montant_tva': [
            r"Montant\s+TVA[^:\n]*:?\s*(" + _AMOUNT + ")",
            r"TVA\s*:?\s*(" + _AMOUNT + ")",
        ],
        'montant_ttc': [
            r"Montant\s+TTC\s*:?\s*(" + _AMOUNT + ")",
            r"Total\s+TTC\s*:?\s*(" + _AMOUNT + ")",
        ],
        'montant_du': [
            r"Montant\s+d[uû]\s*:?\s*(" + _AMOUNT + ")",
            r"Net\s+[àa]\s+payer\s*:?\s*(" + _AMOUNT + ")",
        ],
    }
    
    for attr, pattern_list in patterns.items():
        for pattern in pattern_list:
            m = re.search(pattern, text, re.IGNORECASE)
            if m:
                setattr(g, attr, _to_float(m.group(1)))
                break
    
    return g


def _parse_contract_page(text: str, page_no: int, contract_type: str) -> Contract:
    """Parse une page de contrat."""
    contract = Contract(
        page_number=page_no,
        document_page=_document_page(text),
        contract_type=contract_type,
    )
    
    # Numéro de téléphone
    m_phone = RE_PHONE.search(text)
    if m_phone:
        phone_raw = m_phone.group(1)
        contract.phone_number = re.sub(r"\s", "", phone_raw)
    else:
        # Fallback: chercher un numéro à 10 chiffres
        phone_match = re.search(r'(0[5678]\d{8})', text.replace(" ", ""))
        if phone_match:
            contract.phone_number = phone_match.group(1)
    
    # Période
    m_period = RE_PERIOD.search(text)
    if m_period:
        contract.period_start = m_period.group(1)
        contract.period_end = m_period.group(2)
    else:
        # Fallback: chercher deux dates
        dates = re.findall(r'(\d{2}/\d{2}/\d{4})', text)
        if len(dates) >= 2:
            contract.period_start = dates[0]
            contract.period_end = dates[1]
    
    # Total contrat
    m_total = RE_TOTAL_CONTRAT.search(text)
    if m_total:
        contract.total_contrat = _to_float(m_total.group(1))
    
    # Extraction des frais
    section = None
    
    for line in text.split('\n'):
        line = line.strip()
        if not line:
            continue
        
        line_upper = line.upper()
        
        if 'FRAIS MENSUELS' in line_upper:
            section = "mensuel"
            continue
        if 'FRAIS PONCTUELS' in line_upper:
            section = "ponctuel"
            continue
        if 'TOTAL CONTRAT' in line_upper:
            section = None
            continue
        
        if section == "mensuel":
            m = RE_TABLE_ROW.match(line)
            if m:
                contract.frais_mensuels.append(
                    LineItem(
                        description=m.group("desc").strip(),
                        date_start=m.group("start"),
                        date_end=m.group("end"),
                        amount=_to_float(m.group("amount")),
                    )
                )
                contract.articles_mensuels += 1
        elif section == "ponctuel":
            m = RE_PONCTUAL_ROW.match(line)
            if m:
                desc = m.group("desc").strip()
                if not desc.upper().startswith(('FRAIS', 'DESCRIPTION', 'DATE', 'MONTANT', 'N°', 'TOTAL')):
                    contract.frais_ponctuels.append(
                        LineItem(
                            description=desc,
                            amount=_to_float(m.group("amount")),
                        )
                    )
                    contract.articles_ponctuels += 1
    
    return contract


def parse_invoice(
    pdf_source: str | Path | BinaryIO,
    ocr_engine=None,
    progress_callback=None,
) -> InvoiceData:
    """Parse une facture IAM PDF."""
    source_label = str(pdf_source) if isinstance(pdf_source, (str, Path)) else "<uploaded>"
    invoice = InvoiceData(source_file=source_label)
    
    # Lire le PDF
    if isinstance(pdf_source, (str, Path)):
        pdf_bytes = Path(pdf_source).read_bytes()
    else:
        pdf_bytes = pdf_source.read()
        if hasattr(pdf_source, 'seek'):
            pdf_source.seek(0)
    
    with pdfplumber.open(io.BytesIO(pdf_bytes)) as pdf:
        total_pages = len(pdf.pages)
        
        for idx, page in enumerate(pdf.pages, start=1):
            if progress_callback:
                progress_callback(idx, total_pages, f"Traitement page {idx}/{total_pages}...")
            
            text = page.extract_text() or ""
            
            if not text.strip() and ocr_engine:
                try:
                    import fitz
                    fitz_doc = fitz.open(stream=pdf_bytes, filetype="pdf")
                    fitz_page = fitz_doc[idx - 1]
                    text = ocr_engine.ocr_page(fitz_page)
                    fitz_doc.close()
                except Exception:
                    pass
            
            if not text.strip():
                continue
            
            # Extraire les infos globales
            if invoice.invoice_number is None:
                m = RE_INVOICE_NUMBER.search(text)
                if m:
                    invoice.invoice_number = m.group(1).strip()
            
            if invoice.client_number is None:
                m = RE_CLIENT_NUMBER.search(text)
                if m:
                    invoice.client_number = m.group(1).strip()
            
            if invoice.invoice_date is None:
                m = RE_INVOICE_DATE.search(text)
                if m:
                    invoice.invoice_date = m.group(1)
            
            if invoice.period_start is None:
                m = RE_PERIOD.search(text)
                if m:
                    invoice.period_start = m.group(1)
                    invoice.period_end = m.group(2)
            
            # Identifier le type de page
            kind, contract_type = _identify_page_kind(text)
            
            if kind == "global":
                invoice.global_summary = _parse_global_page(text)
                invoice.global_summary.page_number = idx
            elif kind == "contract":
                contract = _parse_contract_page(text, idx, contract_type)
                if contract.total_contrat > 0 or contract.phone_number:
                    invoice.contracts.append(contract)
    
    # Calculer le total
    invoice.total = round(sum(c.total_contrat for c in invoice.contracts), 2)
    
    # Si aucun contrat trouvé, essayer d'extraire depuis la page globale
    if len(invoice.contracts) == 0 and invoice.global_summary.montant_ttc > 0:
        # Créer un contrat par défaut
        default_contract = Contract(
            page_number=1,
            contract_type="Standard",
            total_contrat=invoice.global_summary.montant_ttc
        )
        invoice.contracts.append(default_contract)
        invoice.total = invoice.global_summary.montant_ttc
    
    if progress_callback:
        progress_callback(total_pages, total_pages, "✅ Terminé !")
    
    return invoice