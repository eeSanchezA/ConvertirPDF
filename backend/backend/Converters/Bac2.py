"""Compatibilidad: delega al convertidor unificado de BAC."""

from Converters.Bac import convert_pdf_to_excel as convert_bac2_pdf_to_excel

__all__ = ["convert_bac2_pdf_to_excel"]
