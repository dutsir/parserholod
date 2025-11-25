"""
Утилита для парсинга адресов и извлечения района.
"""

import re
from typing import Tuple, Optional

def extract_district(address: str) -> Tuple[str, Optional[str]]:
    """
    Извлекает район из адреса и возвращает очищенный адрес и район.

    Примеры:
        "Тигровая ул., 16А р-н Фрунзенский" -> ("Тигровая ул., 16А", "Фрунзенский")
        "ул. Ленина, 10, район Центральный" -> ("ул. Ленина, 10", "Центральный")
        "Москва, ул. Пушкина, 5" -> ("Москва, ул. Пушкина, 5", None)

    Args:
        address: Полный адрес

    Returns:
        Tuple[str, Optional[str]]: (очищенный адрес, название района или None)
    """
    if not address:
        return "", None

    district_patterns = [
        r"р-н\s+([А-Яа-яЁё\s-]+)",
        r"район\s+([А-Яа-яЁё\s-]+)",
        r"р\.\s*н\.\s*([А-Яа-яЁё\s-]+)",
        r"район\s*:\s*([А-Яа-яЁё\s-]+)",
    ]

    district = None
    cleaned_address = address

    for pattern in district_patterns:
        match = re.search(pattern, address, re.IGNORECASE)
        if match:
            district = match.group(1).strip()

            cleaned_address = re.sub(pattern, "", address, flags=re.IGNORECASE).strip()

            cleaned_address = re.sub(r"\s*,\s*,", ",", cleaned_address)
            cleaned_address = re.sub(r",\s*$", "", cleaned_address)
            cleaned_address = " ".join(cleaned_address.split())
            break

    if not district:

        end_pattern = r",\s*(?:р-н\s+)?([А-Яа-яЁё][А-Яа-яЁё\s-]+?)(?:\s*$|\s*,\s*[А-Яа-яЁё])"
        match = re.search(end_pattern, address)
        if match:
            potential_district = match.group(1).strip()

            if len(potential_district) >= 3 and not re.match(r"^\d+", potential_district):
                district = potential_district
                cleaned_address = re.sub(rf",\s*{re.escape(district)}", "", address).strip()

    return cleaned_address, district

def normalize_address(address: str) -> str:
    """
    Нормализует адрес: убирает лишние пробелы, приводит к единому формату.

    Args:
        address: Адрес для нормализации

    Returns:
        str: Нормализованный адрес
    """
    if not address:
        return ""

    address = " ".join(address.split())

    address = re.sub(r",\s*,+", ",", address)

    address = address.strip(", ")

    return address
