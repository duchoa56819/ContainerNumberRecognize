"""
ISO 6346 Shipping Container Code Parser, Validator, and Intelligent Auto-Corrector.
"""
import re
from typing import Dict, List, Optional, Tuple

# Mapping of characters to numerical values according to ISO 6346
# Multiples of 11 (11, 22, 33) are intentionally omitted.
ISO_CHAR_MAP: Dict[str, int] = {
    'A': 10, 'B': 12, 'C': 13, 'D': 14, 'E': 15, 'F': 16, 'G': 17, 'H': 18, 'I': 19, 'J': 20,
    'K': 21, 'L': 23, 'M': 24, 'N': 25, 'O': 26, 'P': 27, 'Q': 28, 'R': 29, 'S': 30, 'T': 31,
    'U': 32, 'V': 34, 'W': 35, 'X': 36, 'Y': 37, 'Z': 38,
    '0': 0, '1': 1, '2': 2, '3': 3, '4': 4, '5': 5, '6': 6, '7': 7, '8': 8, '9': 9
}

# Equipment Category Identifiers per ISO 6346 standard
# Only U, J, Z are standardized category letters
CATEGORY_MAP: Dict[str, str] = {
    'U': 'Freight Container (All standard shipping containers)',
    'J': 'Detachable freight container-related equipment',
    'Z': 'Trailers and Chassis',
    'R': 'Reefer / Thermal Container'
}

VALID_CATEGORIES = {'U', 'J', 'Z', 'R'}

# Common weight and specification prefixes that must NOT be confused with owner codes
BLACKLIST_PREFIXES = {'TAR', 'GRO', 'NET', 'MAX', 'PAY', 'LBS', 'KGS', 'CUC', 'CAP', 'VOL'}

# Known Major Container Owners / Shipping Lines (BIC codes)
OWNER_CODES: Dict[str, str] = {
    'MSK': 'Maersk Line',
    'MAE': 'Maersk Line',
    'APM': 'Maersk / APM Terminals',
    'MSC': 'Mediterranean Shipping Company (MSC)',
    'MED': 'Mediterranean Shipping Company (MSC)',
    'CMA': 'CMA CGM Group',
    'CGM': 'CMA CGM Group',
    'ANL': 'ANL Container Line (CMA CGM)',
    'CNC': 'CNC Line (CMA CGM)',
    'COS': 'COSCO Shipping Lines',
    'CSN': 'COSCO Shipping Lines',
    'CCL': 'COSCO Shipping Lines',
    'CSL': 'China Shipping / CSL Group',
    'HLC': 'Hapag-Lloyd',
    'HLX': 'Hapag-Lloyd',
    'ONE': 'Ocean Network Express (ONE)',
    'NYK': 'NYK Line (ONE)',
    'MOL': 'Mitsui O.S.K. Lines (ONE)',
    'KLI': 'K Line (ONE)',
    'EGL': 'Evergreen Marine Corp',
    'EIS': 'Evergreen Line',
    'EMC': 'Evergreen Marine Corp',
    'YML': 'Yang Ming Marine Transport',
    'ZIM': 'ZIM Integrated Shipping',
    'HMM': 'HMM (Hyundai Merchant Marine)',
    'HDM': 'HMM (Hyundai Merchant Marine)',
    'PIL': 'Pacific International Lines (PIL)',
    'WHL': 'Wan Hai Lines',
    'SMC': 'SM Line Corporation',
    'OOC': 'Orient Overseas Container Line (OOCL)',
    'OOL': 'Orient Overseas Container Line (OOCL)',
    'TCL': 'Triton International',
    'TRH': 'Textainer Group',
    'TEX': 'Textainer Group',
    'TEM': 'Textainer Equipment Management',
    'TGH': 'Textainer Group',
    'TCN': 'Trans-Container Transport',
    'SEG': 'Seaco Global',
    'SCA': 'Seaco Global',
    'CAI': 'CAI International',
    'FCI': 'Florens Container Services',
    'FLR': 'Florens Container Services',
    'BMO': 'Beacon Intermodal Leasing',
    'GES': 'GE SeaCo',
    'DFS': 'Dong Fang International Container',
    'CRX': 'Cronos Containers',
    'CBH': 'China Shipping Container Lines',
    'CXZ': 'China Railway Express / SinoTrans',
    'SUD': 'Hamburg Süd',
    'HAS': 'Hamburg Süd',
    'ARK': 'Arkas Line',
    'UAC': 'United Arab Shipping Company (UASC)',
    'SML': 'Sealand / Maersk',
    'MAT': 'Matson Navigation',
    'KMT': 'KMTC (Korea Marine Transport)'
}

# ISO 6346 Size and Type Codes
SIZE_TYPE_CODES: Dict[str, str] = {
    '20G0': "20ft General Purpose Container (8ft 6in)",
    '20G1': "20ft General Purpose Container with passive vents (8ft 6in)",
    '22G0': "20ft General Purpose Container (8ft 6in)",
    '22G1': "20ft General Purpose Container with passive vents (8ft 6in)",
    '22P1': "20ft Flat Rack Container",
    '22R1': "20ft Reefer Container (Refrigerated)",
    '22T1': "20ft Tank Container",
    '22U1': "20ft Open Top Container",
    '25G1': "20ft High Cube General Purpose Container (9ft 6in)",
    '40G0': "40ft General Purpose Container (8ft 6in)",
    '40G1': "40ft General Purpose Container with passive vents (8ft 6in)",
    '42G0': "40ft General Purpose Container (8ft 6in)",
    '42G1': "40ft General Purpose Container (8ft 6in)",
    '42P1': "40ft Flat Rack Container",
    '42R1': "40ft Reefer Container",
    '42U1': "40ft Open Top Container",
    '45G0': "40ft High Cube General Purpose Container (9ft 6in)",
    '45G1': "40ft High Cube General Purpose Container (9ft 6in)",
    '45R1': "40ft High Cube Reefer Container (9ft 6in)",
    '45U1': "40ft High Cube Open Top Container (9ft 6in)",
    'L5G1': "45ft High Cube General Purpose Container (9ft 6in)",
    'L5R1': "45ft High Cube Reefer Container (9ft 6in)"
}

# OCR Letter to Digit mapping
LETTER_TO_DIGIT: Dict[str, str] = {
    'O': '0', 'D': '0', 'Q': '0', 'C': '0',
    'I': '1', 'L': '1', 'l': '1', '|': '1', '!': '1', 'T': '1',
    'Z': '2',
    'E': '3',
    'A': '4',
    'S': '5', 's': '5',
    'G': '6', 'b': '6',
    'B': '8',
    'g': '9', 'q': '9'
}

# OCR Digit to Letter substitutions
DIGIT_TO_LETTER: Dict[str, List[str]] = {
    '0': ['O', 'C', 'D', 'U', 'Q'],
    '1': ['I', 'L', 'T'],
    '2': ['Z'],
    '3': ['E', 'B'],
    '4': ['A'],
    '5': ['S'],
    '6': ['G'],
    '7': ['T', 'Z'],
    '8': ['B'],
    '9': ['G']
}


def calculate_check_digit(code_10: str) -> Optional[int]:
    """
    Calculates the ISO 6346 check digit for the first 10 characters
    (3 owner letters + 1 category letter + 6 serial digits).
    Returns integer 0-9, or None if invalid characters.
    """
    code_10 = code_10.upper().replace(' ', '').replace('-', '')
    if len(code_10) != 10:
        return None

    total = 0
    for i, char in enumerate(code_10):
        if char not in ISO_CHAR_MAP:
            return None
        weight = 2 ** i
        total += ISO_CHAR_MAP[char] * weight

    remainder = total % 11
    return 0 if remainder == 10 else remainder


def get_step_by_step_calculation(code_10: str) -> Optional[Dict]:
    """
    Returns step-by-step mathematical breakdown of the ISO 6346 calculation for educational/debugging UI.
    """
    code_10 = code_10.upper().replace(' ', '').replace('-', '')
    if len(code_10) != 10:
        return None

    steps = []
    total = 0
    for i, char in enumerate(code_10):
        if char not in ISO_CHAR_MAP:
            return None
        val = ISO_CHAR_MAP[char]
        weight = 2 ** i
        product = val * weight
        total += product
        steps.append({
            "position": i + 1,
            "char": char,
            "value": val,
            "weight": f"2^{i} = {weight}",
            "product": product
        })

    remainder = total % 11
    check_digit = 0 if remainder == 10 else remainder
    return {
        "steps": steps,
        "total_sum": total,
        "modulo_11": remainder,
        "check_digit": check_digit
    }


def validate_container_number(full_code: str) -> Tuple[bool, Optional[int]]:
    """
    Validates a full 11-character container number (4 letters + 6 digits + 1 check digit).
    Returns (is_valid, expected_check_digit).
    """
    clean = re.sub(r'[^A-Za-z0-9]', '', full_code.upper())
    if len(clean) != 11:
        return False, None

    prefix = clean[:10]
    provided_check = clean[10]

    if prefix[:3] in BLACKLIST_PREFIXES:
        return False, None

    # Check that first 4 are letters and category is valid
    if not prefix[:4].isalpha():
        return False, None

    if not provided_check.isdigit():
        return False, None

    expected = calculate_check_digit(prefix)
    if expected is None:
        return False, None

    is_valid = (expected == int(provided_check))
    return is_valid, expected


def auto_correct_container_code(candidate: str) -> Optional[Dict]:
    """
    Attempts to auto-correct common OCR errors in an 11-character candidate
    by applying ISO 6346 structural rules and testing substitutions against
    the check digit algorithm.
    """
    clean = re.sub(r'[^A-Za-z0-9]', '', candidate.upper())
    if len(clean) < 10 or len(clean) > 12:
        return None

    # Handle 11 or 12 character candidates
    if len(clean) >= 11:
        clean = clean[:11]
        chars = list(clean)

        raw_prefix_3 = "".join(chars[:3])
        if raw_prefix_3 in BLACKLIST_PREFIXES:
            return None

        # 0. Check if raw candidate is ALREADY 100% valid as-is
        if clean[:4].isalpha() and clean[4:].isdigit():
            val, exp = validate_container_number(clean)
            if val:
                return {
                    "code": clean,
                    "repaired": False,
                    "confidence": 1.0,
                    "known_owner": raw_prefix_3 in OWNER_CODES
                }

        # 1. Clean serial number (indices 4..9) to digits
        for i in range(4, 10):
            if chars[i] in LETTER_TO_DIGIT:
                chars[i] = LETTER_TO_DIGIT[chars[i]]

        # 2. Clean check digit (index 10) to digit
        if chars[10] in LETTER_TO_DIGIT:
            chars[10] = LETTER_TO_DIGIT[chars[10]]

        # 3. Clean owner code (indices 0..2) to letters
        for i in range(3):
            if chars[i].isdigit() and chars[i] in DIGIT_TO_LETTER:
                chars[i] = DIGIT_TO_LETTER[chars[i]][0]

        # Check again after standard digit/letter mapping
        mapped_clean = "".join(chars)
        mapped_prefix_3 = mapped_clean[:3]
        if mapped_prefix_3 in BLACKLIST_PREFIXES:
            return None

        if mapped_clean[:4].isalpha() and mapped_clean[4:].isdigit():
            val, exp = validate_container_number(mapped_clean)
            if val:
                return {
                    "code": mapped_clean,
                    "repaired": (mapped_clean != clean),
                    "confidence": 0.98,
                    "known_owner": mapped_prefix_3 in OWNER_CODES
                }

        # 4. Check known owner match with category 'U'
        if raw_prefix_3 in OWNER_CODES:
            test_prefix = raw_prefix_3 + 'U' + "".join(chars[4:10])
            calc_chk = calculate_check_digit(test_prefix)
            if calc_chk is not None:
                if chars[10].isdigit() and int(chars[10]) == calc_chk:
                    repaired_code = f"{test_prefix}{calc_chk}"
                    return {
                        "code": repaired_code,
                        "repaired": (repaired_code != clean),
                        "confidence": 0.95,
                        "known_owner": True
                    }

        # 5. Check 1-char typo against known owner codes
        for known_owner in OWNER_CODES.keys():
            diffs = sum(1 for a, b in zip(raw_prefix_3, known_owner) if a != b)
            if diffs == 1:
                test_prefix = known_owner + 'U' + "".join(chars[4:10])
                calc_chk = calculate_check_digit(test_prefix)
                if calc_chk is not None and chars[10].isdigit() and int(chars[10]) == calc_chk:
                    repaired_code = f"{test_prefix}{calc_chk}"
                    return {
                        "code": repaired_code,
                        "repaired": True,
                        "confidence": 0.90,
                        "known_owner": True
                    }

        # 6. Try category candidates with current prefix
        cat_candidates = ['U', chars[3]] if chars[3] in VALID_CATEGORIES else ['U', 'J', 'Z']
        for cat in cat_candidates:
            test_prefix = "".join(chars[:3]) + cat + "".join(chars[4:10])
            calc_chk = calculate_check_digit(test_prefix)
            if calc_chk is not None:
                if chars[10].isdigit() and int(chars[10]) == calc_chk:
                    repaired_code = f"{test_prefix}{calc_chk}"
                    return {
                        "code": repaired_code,
                        "repaired": (repaired_code != clean),
                        "confidence": 0.88,
                        "known_owner": raw_prefix_3 in OWNER_CODES
                    }

        # 7. Fallback: calculate check digit using category 'U'
        best_prefix = "".join(chars[:3]) + 'U' + "".join(chars[4:10])
        calc_chk = calculate_check_digit(best_prefix)
        if calc_chk is not None:
            return {
                "code": f"{best_prefix}{calc_chk}",
                "repaired": True,
                "confidence": 0.82,
                "known_owner": raw_prefix_3 in OWNER_CODES
            }

    # Handle 10-character candidate (missing check digit)
    if len(clean) == 10:
        chars = list(clean)
        if "".join(chars[:3]) in BLACKLIST_PREFIXES:
            return None

        for i in range(3):
            if chars[i].isdigit() and chars[i] in DIGIT_TO_LETTER:
                chars[i] = DIGIT_TO_LETTER[chars[i]][0]
        if chars[3] not in VALID_CATEGORIES:
            chars[3] = 'U'
        for i in range(4, 10):
            if chars[i] in LETTER_TO_DIGIT:
                chars[i] = LETTER_TO_DIGIT[chars[i]]
        repaired_10 = "".join(chars)
        calc = calculate_check_digit(repaired_10)
        if calc is not None:
            return {
                "code": f"{repaired_10}{calc}",
                "repaired": True,
                "confidence": 0.85,
                "known_owner": "".join(chars[:3]) in OWNER_CODES
            }

    return None


def extract_iso_candidates(texts: List[str]) -> List[Dict]:
    """
    Extracts potential ISO 6346 container numbers from a list of OCR strings.
    Handles single-line, spaced, hyphenated, multi-token, and vertical arrangements.
    """
    results = []
    seen = set()

    # Pattern for container number: 4 chars + 6 digits + optional 1 check digit
    pattern = re.compile(r'([A-Za-z0-9]{4})[\s\-_]*([A-Za-z0-9]{6})[\s\-_]*([A-Za-z0-9]{1})?')

    # Check each individual string
    for text in texts:
        clean_text = text.strip()
        for match in pattern.finditer(clean_text):
            owner_cat, serial, check = match.groups()
            candidate_raw = f"{owner_cat}{serial}{check if check else ''}"
            fixed = auto_correct_container_code(candidate_raw)
            if fixed and fixed["code"] not in seen:
                seen.add(fixed["code"])
                results.append(fixed)

    # Check space-joined and concatenated string
    combined_spaced = " ".join(texts)
    for match in pattern.finditer(combined_spaced):
        owner_cat, serial, check = match.groups()
        candidate_raw = f"{owner_cat}{serial}{check if check else ''}"
        fixed = auto_correct_container_code(candidate_raw)
        if fixed and fixed["code"] not in seen:
            seen.add(fixed["code"])
            results.append(fixed)

    # Multi-token matching (e.g. ['CSLU', '1442268'] or ['CSLU', '144226', '8'])
    clean_tokens = [re.sub(r'[^A-Za-z0-9]', '', t) for t in texts if t.strip()]
    for i in range(len(clean_tokens) - 1):
        t1 = clean_tokens[i]
        t2 = clean_tokens[i+1]

        # 4 letters + 6 or 7 digits
        if len(t1) == 4 and len(t2) in (6, 7):
            candidate_raw = t1 + t2
            fixed = auto_correct_container_code(candidate_raw)
            if fixed and fixed["code"] not in seen:
                seen.add(fixed["code"])
                results.append(fixed)

        # 4 letters + 6 digits + 1 check digit in 3 tokens
        if i + 2 < len(clean_tokens):
            t3 = clean_tokens[i+2]
            if len(t1) == 4 and len(t2) == 6 and len(t3) == 1:
                candidate_raw = t1 + t2 + t3
                fixed = auto_correct_container_code(candidate_raw)
                if fixed and fixed["code"] not in seen:
                    seen.add(fixed["code"])
                    results.append(fixed)

    # Check vertical letters/digits sequence
    single_chars = [t.strip() for t in texts if len(t.strip()) == 1]
    if len(single_chars) >= 10:
        candidate_raw = "".join(single_chars[:11])
        fixed = auto_correct_container_code(candidate_raw)
        if fixed and fixed["code"] not in seen:
            seen.add(fixed["code"])
            results.append(fixed)

    # Sort results:
    # 1. Unmodified valid match (repaired == False and is_valid == True): 100 points
    # 2. Known owner bonus: 10 points
    # 3. Repaired valid match: 50 points
    # 4. Confidence
    def sort_score(c):
        is_val, _ = validate_container_number(c["code"])
        repaired = c.get("repaired", False)
        known = 1 if c.get("known_owner") or c["code"][:3] in OWNER_CODES else 0
        
        score = 0
        if is_val and not repaired:
            score += 1000
        elif is_val and repaired:
            score += 500
        
        score += known * 100
        score += c.get("confidence", 0) * 10
        return score

    results.sort(key=sort_score, reverse=True)
    return results


def find_size_type_code(texts: List[str]) -> Optional[Tuple[str, str]]:
    """
    Finds ISO size/type codes (e.g. 22G1, 45G1, 42G1) in OCR text lines.
    """
    for text in texts:
        clean = re.sub(r'[^A-Za-z0-9]', '', text.upper())
        for code, desc in SIZE_TYPE_CODES.items():
            if code in clean:
                return code, desc
        # Match standard 4-char regex for size/type: [24L][025][A-Z][0-9]
        m = re.search(r'\b([24L][025][A-Z][0-9])\b', text.upper())
        if m:
            code = m.group(1)
            desc = SIZE_TYPE_CODES.get(code, "Standard ISO Freight Container")
            return code, desc

    return None


def parse_container_info(raw_code: str, all_texts: Optional[List[str]] = None) -> Dict:
    """
    Builds full structured container metadata from recognized container number
    and associated OCR lines.
    """
    clean = re.sub(r'[^A-Za-z0-9]', '', raw_code.upper())

    if len(clean) >= 11:
        owner_code = clean[:3]
        category_char = clean[3]
        serial_number = clean[4:10]
        check_digit = clean[10]
    elif len(clean) == 10:
        owner_code = clean[:3]
        category_char = clean[3]
        serial_number = clean[4:10]
        check_digit = str(calculate_check_digit(clean[:10]) or "")
    else:
        owner_code = clean[:3] if len(clean) >= 3 else clean
        category_char = clean[3] if len(clean) >= 4 else ""
        serial_number = clean[4:] if len(clean) > 4 else ""
        check_digit = ""

    # Validation
    is_valid, expected_check = validate_container_number(clean)
    owner_name = OWNER_CODES.get(owner_code, "Other / Private Operator")
    category_desc = CATEGORY_MAP.get(category_char, "Standard Container")

    # Size / Type code
    size_type = find_size_type_code(all_texts or [])

    return {
        "container_number": f"{clean[:11]}" if len(clean) >= 11 else clean,
        "formatted_number": f"{owner_code}{category_char} {serial_number} [{check_digit}]" if len(clean) >= 11 else clean,
        "owner_code": owner_code,
        "owner_name": owner_name,
        "category_char": category_char,
        "category_description": category_desc,
        "serial_number": serial_number,
        "check_digit": check_digit,
        "expected_check_digit": str(expected_check) if expected_check is not None else "",
        "is_valid": is_valid,
        "size_type_code": size_type[0] if size_type else None,
        "size_type_desc": size_type[1] if size_type else None
    }
