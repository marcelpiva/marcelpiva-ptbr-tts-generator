"""
Generic pt-BR TTS Pipeline: 4-layer text-to-speech generation.

Layers:
  1. Accent Correction  — fix missing pt-BR accents (fix_accents.py)
  2. Value Normalization — emoji, punctuation, numbers→words, abbreviations
  3. Prosody/Pronunciation — phonetic respelling for TTS engines
  4. Audio Generation   — F5-TTS → WAV → MP3

Input format (JSON array):
  [
    {
      "id": "unique_item_id",
      "type": "description|reveal|preview|...",
      "text": "Text to synthesize",
      "source": "origin_file_or_api",
      "series_id": "optional_series",
      "season_id": "optional_season",
      "stage_id": "optional_stage",
      "puzzle_id": "optional_puzzle"
    }
  ]

Output:
  - MP3 files: <output_dir>/<item_id>.mp3
  - Progress JSON: tracks what's been generated (for resume)
  - Manifest JSON: full list of generated items with metadata
"""

import json
import re
import subprocess
import sys
import time
from pathlib import Path

from fix_accents import apply_word_replacements, apply_phrase_replacements

# --- Constants ---

_EMOJI_RE = re.compile(
    "["
    "\U0001F300-\U0001FAFF"
    "\U00002702-\U000027B0"
    "\U0000FE00-\U0000FE0F"
    "\U0000200D"
    "]+",
    flags=re.UNICODE,
)

_ROMAN_NUMERALS = {
    "II", "III", "IV", "V", "VI", "VII", "VIII", "IX", "X", "XI", "XII",
}

_KEEP_UPPER = _ROMAN_NUMERALS | {
    "MD5", "ROT13", "ASCII", "SHA256", "CEO", "XOR", "PIB", "DNA", "FBI",
    "CIA", "GPS", "USB", "PDF", "HTML", "CSS", "URL", "API", "RAM", "ROM",
    "LED", "PIN", "SOS", "VIP", "FAQ", "ID",
    "DNS", "TXT", "RSA", "RTLO", "DDOS", "TTS", "UTC", "MIT", "SSH", "IP",
    "QG", "CORP", "CNUT",
    "CBC", "BMP", "EKG", "ECG", "ICD", "ICU", "UTI", "SpO2", "BPM", "WHO",
    "OMS", "PCR", "CPR", "RCP", "CPK", "LDH", "ALT", "AST", "HDL", "LDL",
    "IM", "IV", "VO", "SC",
}

_ALL_CAPS_WORD = re.compile(r"\b([A-ZÁÀÂÃÉÊÍÓÔÕÚÇ]{2,}\d*)\b")
_DOC_NUMBER = re.compile(r"#(\d+)")
_MULTI_SPACES = re.compile(r" {2,}")

_PROTECT_HEX_PAIRS = re.compile(r"(?:[0-9a-fA-F]{2} ){2,}[0-9a-fA-F]{2}")
_PROTECT_BINARY = re.compile(r"\b[01]{8,}\b")
_PROTECT_HEX_PREFIX = re.compile(r"0x[0-9a-fA-F]+")
_PROTECT_COORD = re.compile(r"\d+\.\d+[NSEW]")
_PROTECT_ASCII_SEQ = re.compile(r"\d{2,3}(?:,\s*\d{2,3}){2,}")
_PROTECT_ALPHANUM_ID = re.compile(r"\b[A-Za-z]+\d+[A-Za-z]*\b|\b\w+-\d+\b")

_ORDINALS_M = {
    "1o": "primeiro", "2o": "segundo", "3o": "terceiro", "4o": "quarto",
    "5o": "quinto", "6o": "sexto", "7o": "sétimo", "8o": "oitavo",
    "9o": "nono", "10o": "décimo",
}
_ORDINALS_F = {
    "1a": "primeira", "2a": "segunda", "3a": "terceira", "4a": "quarta",
    "5a": "quinta", "6a": "sexta", "7a": "sétima", "8a": "oitava",
    "9a": "nona", "10a": "décima",
}

_NUM_UNITS = [
    "zero", "um", "dois", "três", "quatro", "cinco", "seis", "sete",
    "oito", "nove", "dez", "onze", "doze", "treze", "quatorze",
    "quinze", "dezesseis", "dezessete", "dezoito", "dezenove",
]
_NUM_TENS = [
    "", "", "vinte", "trinta", "quarenta", "cinquenta",
    "sessenta", "setenta", "oitenta", "noventa",
]
_NUM_HUNDREDS = [
    "", "cento", "duzentos", "trezentos", "quatrocentos", "quinhentos",
    "seiscentos", "setecentos", "oitocentos", "novecentos",
]


# =========================================================================
# Number conversion
# =========================================================================

def number_to_words_pt(n: int) -> str:
    """Convert integer 0-999999 to Brazilian Portuguese words."""
    if n < 0 or n > 999_999:
        return str(n)
    if n == 0:
        return "zero"
    if n == 100:
        return "cem"

    if n >= 1000:
        thousands, remainder = divmod(n, 1000)
        if thousands == 1:
            parts = ["mil"]
        else:
            parts = [number_to_words_pt(thousands) + " mil"]
        if remainder > 0:
            if remainder < 100:
                parts.append("e")
            parts.append(number_to_words_pt(remainder))
        return " ".join(parts)

    if n >= 100:
        h, remainder = divmod(n, 100)
        if remainder == 0:
            return _NUM_HUNDREDS[h] if h > 1 else "cem"
        return f"{_NUM_HUNDREDS[h]} e {number_to_words_pt(remainder)}"

    if n >= 20:
        t, u = divmod(n, 10)
        if u == 0:
            return _NUM_TENS[t]
        return f"{_NUM_TENS[t]} e {_NUM_UNITS[u]}"

    return _NUM_UNITS[n]


# =========================================================================
# Layer 1: Accent Correction
# =========================================================================

def layer_1_accent_correction(text: str) -> str:
    """Camada 1: Correção de acentuação pt-BR."""
    text = apply_word_replacements(text)
    text = apply_phrase_replacements(text)
    return text


# =========================================================================
# Layer 2: Value Normalization
# =========================================================================

def layer_2_value_normalization(text: str, locale: str = "pt_BR") -> str:
    """Camada 2: Limpeza, expansão e normalização de valores."""
    text = _EMOJI_RE.sub("", text)
    text = re.sub(r"\n- ", "\n", text)
    text = text.replace("\n\n", ". ")
    text = text.replace("\n", " ")
    text = re.sub(r"\s*--\s*Departamento\b.*", "", text)
    text = text.replace(" -- ", ", ")
    text = text.replace(" — ", ", ")
    text = text.replace("—", ", ")
    text = text.replace(" // ", ", ")
    text = text.replace(" → ", ", ")
    text = text.replace("→", ", ")
    text = text.replace("...", ", ")

    if locale.startswith("pt"):
        text = _DOC_NUMBER.sub(lambda m: f"número {int(m.group(1))}", text)
    else:
        text = _DOC_NUMBER.sub(lambda m: f"number {int(m.group(1))}", text)

    if locale.startswith("pt"):
        text = text.replace("P.P.S.:", "pós-pós-escrito:")
        text = text.replace("P.P.S.", "pós-pós-escrito")
        text = text.replace("P.S.:", "pós-escrito:")
        text = text.replace("P.S.", "pós-escrito")
        text = text.replace("a.C.", "antes de Cristo")
        text = text.replace("24/7", "24 horas por dia")
        text = re.sub(r"R\$\s*", "reais ", text)
    else:
        text = text.replace("24/7", "24 hours a day")

    text = re.sub(r"\$(\d)", r"\1", text)
    text = re.sub(r"\$([A-Z])", r"\1", text)

    if locale.startswith("pt"):
        text = re.sub(
            r"\b(\d+)o\b",
            lambda m: _ORDINALS_M.get(m.group(0), m.group(0)),
            text,
        )
        text = re.sub(
            r"\b(\d+)a\b",
            lambda m: _ORDINALS_F.get(m.group(0), m.group(0)),
            text,
        )

        def _pct_decimal(m: re.Match) -> str:
            integer = int(m.group(1))
            decimals = m.group(2)
            dec_words = " ".join(number_to_words_pt(int(d)) for d in decimals)
            return f"{number_to_words_pt(integer)} vírgula {dec_words} por cento"
        text = re.sub(r"\b(\d+)[.,](\d+)%", _pct_decimal, text)
        text = re.sub(
            r"\b(\d+)%",
            lambda m: f"{number_to_words_pt(int(m.group(1)))} por cento",
            text,
        )

        _protected = {}
        _prot_counter = [0]

        def _protect(m: re.Match) -> str:
            key = chr(0xE000 + _prot_counter[0])
            _protected[key] = m.group(0)
            _prot_counter[0] += 1
            return key

        for pat in (_PROTECT_HEX_PAIRS, _PROTECT_BINARY, _PROTECT_HEX_PREFIX,
                     _PROTECT_COORD, _PROTECT_ASCII_SEQ, _PROTECT_ALPHANUM_ID):
            text = pat.sub(_protect, text)

        text = re.sub(
            r"\b\d{1,3}(?:\.\d{3})+\b",
            lambda m: number_to_words_pt(int(m.group(0).replace(".", ""))),
            text,
        )

        def _decimal_comma(m: re.Match) -> str:
            integer = int(m.group(1))
            decimals = m.group(2)
            dec_words = " ".join(number_to_words_pt(int(d)) for d in decimals)
            return f"{number_to_words_pt(integer)} vírgula {dec_words}"
        text = re.sub(r"\b(\d+),(\d+)\b", _decimal_comma, text)

        text = re.sub(
            r"\b(\d+)\b",
            lambda m: number_to_words_pt(int(m.group(1)))
                      if int(m.group(1)) <= 999_999 else m.group(0),
            text,
        )

        for key, val in _protected.items():
            text = text.replace(key, val)

    def _lower_caps(m: re.Match) -> str:
        word = m.group(1)
        if word in _KEEP_UPPER:
            return word
        return word.title()

    text = _ALL_CAPS_WORD.sub(_lower_caps, text)
    text = _MULTI_SPACES.sub(" ", text)
    text = text.strip()

    return text


# =========================================================================
# Layer 3: Prosody & Pronunciation
# =========================================================================

def layer_3_prosody_pronunciation(text: str, locale: str = "pt_BR") -> str:
    """Camada 3: Respelling fonético para TTS."""
    if not locale.startswith("pt"):
        return text

    text = text.replace("receitadavovo.com.br",
                        "receita da vovó ponto com ponto bê érre")
    text = re.sub(r"\b[Bb]ase64\b", "base meia quatro", text)
    text = re.sub(r"\bpaçocas\b", "paçócas", text)
    text = re.sub(r"\bPaçocas\b", "Paçócas", text)
    text = re.sub(r"\bpaçoca\b", "paçóca", text)
    text = re.sub(r"\bPaçoca\b", "Paçóca", text)
    text = re.sub(r"\bcocadas\b", "cocádas", text)
    text = re.sub(r"\bCocadas\b", "Cocádas", text)
    text = re.sub(r"\bcocada\b", "cocáda", text)
    text = re.sub(r"\bCocada\b", "Cocáda", text)
    text = re.sub(r"\bcocos\b", "côcos", text)
    text = re.sub(r"\bCocos\b", "Côcos", text)
    text = re.sub(r"\bcoco\b", "côco", text)
    text = re.sub(r"\bCoco\b", "Côco", text)

    text = re.sub(r"(?<=\d)mg\b", " miligramas", text)
    text = re.sub(r"\bmg\b", "miligramas", text)
    text = re.sub(r"(?<=\d)ml\b", " mililitros", text)
    text = re.sub(r"\bml\b", "mililitros", text)
    text = re.sub(r"(?<=\d)kg\b", " quilogramas", text)
    text = re.sub(r"\bkg\b", "quilogramas", text)
    text = re.sub(r"\bmmHg\b", "milímetros de mercúrio", text)
    text = re.sub(r"\bmmol/L\b", "milimóis por litro", text)
    text = re.sub(r"\bmEq/L\b", "miliequivalentes por litro", text)
    text = re.sub(r"\bg/dL\b", "gramas por decilitro", text)
    text = re.sub(r"\bSpO2\b", "saturação de oxigênio", text)
    text = re.sub(r"\bBPM\b", "batimentos por minuto", text)
    text = re.sub(r"(?<!\w)b\.i\.d\.(?!\w)", "duas vezes ao dia", text)
    text = re.sub(r"(?<!\w)t\.i\.d\.(?!\w)", "três vezes ao dia", text)
    text = re.sub(r"(?<!\w)q\.i\.d\.(?!\w)", "quatro vezes ao dia", text)
    text = re.sub(r"(?<!\w)q\.d\.(?!\w)", "uma vez ao dia", text)
    text = re.sub(r"(?<!\w)p\.r\.n\.(?!\w)", "quando necessário", text)
    text = re.sub(r"\bRx\b", "receita médica", text)
    text = re.sub(r"\bDx\b", "diagnóstico", text)
    text = re.sub(r"\bHx\b", "história clínica", text)
    text = re.sub(r"\bTx\b", "tratamento", text)
    text = re.sub(r"\bSx\b", "sintomas", text)
    text = re.sub(r"\bVO\b", "via oral", text)
    text = re.sub(r"\bIM\b", "intramuscular", text)
    text = re.sub(r"\bIV\b", "intravenosa", text)
    text = re.sub(r"\bSC\b", "subcutânea", text)
    text = re.sub(r"\bUTI\b", "unidade de terapia intensiva", text)
    text = re.sub(r"\bOMS\b", "Organização Mundial da Saúde", text)
    text = re.sub(r"\bEKG\b", "eletrocardiograma", text)
    text = re.sub(r"\bECG\b", "eletrocardiograma", text)
    text = re.sub(r"\bCBC\b", "hemograma completo", text)
    text = re.sub(r"\bICD-10\b", "Cê Í Dê dez", text)

    return text


# =========================================================================
# Full pipeline
# =========================================================================

def normalize_for_tts(text: str, locale: str = "pt_BR") -> str:
    """Full pipeline (layers 1-3). Returns normalized text ready for TTS."""
    text = layer_1_accent_correction(text)
    text = layer_2_value_normalization(text, locale)
    text = layer_3_prosody_pronunciation(text, locale)
    return text


# =========================================================================
# Content filtering
# =========================================================================

def filter_content(items, series=None, season=None, stage=None, puzzle=None):
    """Filter items by hierarchy: series → season → stage → puzzle."""
    filtered = items
    if series:
        filtered = [i for i in filtered if i.get("series_id") == series]
    if season:
        filtered = [i for i in filtered if i.get("season_id") == season]
    if stage:
        filtered = [i for i in filtered if i.get("stage_id") == stage]
    if puzzle:
        filtered = [i for i in filtered if i.get("puzzle_id") == puzzle]
    return filtered


# =========================================================================
# Display
# =========================================================================

def show_count(items: list[dict], group_by_series: bool = False):
    """Show content counts by type."""
    from collections import Counter, defaultdict

    if group_by_series:
        by_series = defaultdict(list)
        for item in items:
            by_series[item.get("series_id", "unknown")].append(item)

        for sid in sorted(by_series):
            sitems = by_series[sid]
            by_type = Counter(i["type"] for i in sitems)
            print(f"\n--- {sid} ---")
            print(f"{'Type':<20} {'Count':>6}")
            print("-" * 30)
            for t in sorted(by_type):
                print(f"{t:<20} {by_type[t]:>6}")
            print("-" * 30)
            print(f"{'TOTAL':<20} {len(sitems):>6}")
    else:
        by_type = Counter(item["type"] for item in items)
        print(f"\n{'Type':<20} {'Count':>6}")
        print("-" * 30)
        for t in sorted(by_type):
            print(f"{t:<20} {by_type[t]:>6}")
        print("-" * 30)
        print(f"{'TOTAL':<20} {len(items):>6}")


def show_dry_run(items: list[dict], locale: str = "pt_BR"):
    """List all content with per-layer transformation diff."""
    for item in items:
        original = item["text"]
        after_l1 = layer_1_accent_correction(original)
        after_l2 = layer_2_value_normalization(after_l1, locale)
        after_l3 = layer_3_prosody_pronunciation(after_l2, locale)

        meta_parts = []
        if item.get("series_id"):
            meta_parts.append(f"series={item['series_id']}")
        if item.get("season_id"):
            meta_parts.append(f"season={item['season_id']}")
        if item.get("stage_id"):
            meta_parts.append(f"stage={item['stage_id']}")
        meta = " ".join(meta_parts)

        print(f"[{item['type']:<15}] {item['id']}")
        if meta:
            print(f"  {meta}")
        print(f"  original:  {original[:100].replace(chr(10), ' ')}")

        any_change = False
        if after_l1 != original:
            print(f"  L1 accent: {after_l1[:100].replace(chr(10), ' ')}")
            any_change = True
        if after_l2 != after_l1:
            print(f"  L2 values: {after_l2[:100]}")
            any_change = True
        if after_l3 != after_l2:
            print(f"  L3 prosod: {after_l3[:100]}")
            any_change = True
        if not any_change:
            print(f"  (no changes)")
        print()

    print(f"Total: {len(items)} items")


# =========================================================================
# Layer 4: Audio Generation
# =========================================================================

def wav_to_mp3(wav_path: Path, mp3_path: Path):
    subprocess.run(
        ["ffmpeg", "-y", "-loglevel", "error", "-i", str(wav_path),
         "-b:a", "64k", "-ar", "24000", str(mp3_path)],
        capture_output=True,
    )


def load_progress(progress_file: Path) -> dict:
    if progress_file.exists():
        with open(progress_file) as f:
            return json.load(f)
    return {"generated": {}}


def save_progress(progress: dict, progress_file: Path):
    progress_file.parent.mkdir(parents=True, exist_ok=True)
    with open(progress_file, "w") as f:
        json.dump(progress, f, indent=2)


def generate_audio(
    items: list[dict],
    output_dir: Path,
    progress_file: Path,
    voice_file: str,
    voice_text: str,
    model_file: str,
    vocab_file: str,
    locale: str = "pt_BR",
    force: bool = False,
    device: str = "mps",
):
    """Layer 4: Generate TTS audio for all items.

    Args:
        items: List of content items (id, type, text, ...)
        output_dir: Directory for MP3 output files
        progress_file: Path to progress JSON (for resume)
        voice_file: Reference WAV file for voice cloning
        voice_text: Transcript of the reference WAV
        model_file: Path to F5-TTS model checkpoint
        vocab_file: Path to F5-TTS vocab file
        locale: Locale for text normalization
        force: If True, regenerate all items
        device: PyTorch device (mps, cuda, cpu)
    """
    output_dir.mkdir(parents=True, exist_ok=True)
    progress = load_progress(progress_file)

    if force:
        for item in items:
            progress["generated"].pop(item["id"], None)
        save_progress(progress, progress_file)

    to_generate = [item for item in items if item["id"] not in progress["generated"]]

    if not to_generate:
        print("All audio already generated!")
        return

    done = len(items) - len(to_generate)
    total = len(to_generate)
    print(f"\nGenerating {total} audio files ({done} already done)...")

    print("Loading F5-TTS model...", flush=True)
    from f5_tts.api import F5TTS
    tts = F5TTS(model="F5TTS_v1_Base", ckpt_file=model_file, vocab_file=vocab_file, device=device)
    print("Model loaded!\n", flush=True)

    import soundfile as sf

    start_time = time.time()
    tmp_dir = output_dir / "_tmp"
    tmp_dir.mkdir(parents=True, exist_ok=True)

    for i, item in enumerate(to_generate, 1):
        wav_path = tmp_dir / f"{item['id']}.wav"
        mp3_path = output_dir / f"{item['id']}.mp3"

        elapsed = time.time() - start_time
        rate = i / max(elapsed, 1)
        eta = (total - i) / max(rate, 0.001)
        eta_h, eta_m = int(eta // 3600), int((eta % 3600) // 60)

        print(f"[{i}/{total}] {item['id']} (ETA {eta_h}h{eta_m:02d}m) ", end="", flush=True)

        try:
            t0 = time.time()
            wav, sr, _ = tts.infer(
                ref_file=voice_file,
                ref_text=voice_text,
                gen_text=normalize_for_tts(item["text"], locale),
                seed=42,
                show_info=lambda *a, **kw: None,
            )
            gen_time = time.time() - t0

            sf.write(str(wav_path), wav, sr)
            wav_to_mp3(wav_path, mp3_path)
            wav_path.unlink(missing_ok=True)

            dur = len(wav) / sr
            progress["generated"][item["id"]] = {
                "duration_s": round(dur, 1),
                "gen_time_s": round(gen_time, 1),
                "type": item["type"],
            }
            save_progress(progress, progress_file)

            print(f"OK {gen_time:.0f}s gen, {dur:.1f}s audio", flush=True)

        except Exception as e:
            print(f"ERROR: {e}", flush=True)

    # Cleanup tmp
    import shutil
    shutil.rmtree(tmp_dir, ignore_errors=True)

    # Write manifest
    manifest_path = output_dir / "manifest.json"
    manifest = {
        "locale": locale,
        "total_items": len(items),
        "generated": len(progress["generated"]),
        "items": [
            {
                "id": item["id"],
                "type": item["type"],
                "file": f"{item['id']}.mp3",
                **({k: item[k] for k in ("series_id", "season_id", "stage_id", "puzzle_id")
                    if item.get(k)}),
                **(progress["generated"].get(item["id"], {})),
            }
            for item in items
            if item["id"] in progress["generated"]
        ],
    }
    with open(manifest_path, "w") as f:
        json.dump(manifest, f, indent=2)

    print(f"\nGeneration complete! {len(progress['generated'])}/{len(items)}")
    print(f"Manifest: {manifest_path}")


# =========================================================================
# Standalone CLI
# =========================================================================

def main():
    """Process a JSON input file through the TTS pipeline.

    Usage:
      python tts_pipeline.py input.json --output-dir ./output [options]

    Options:
      --output-dir DIR    Output directory for MP3 files (required for generation)
      --voice-file WAV    Reference voice WAV file
      --voice-text TEXT   Transcript of the reference voice
      --model-file PATH   F5-TTS model checkpoint
      --vocab-file PATH   F5-TTS vocab file
      --locale LOCALE     Locale (default: pt_BR)
      --device DEVICE     PyTorch device (default: mps)
      --series ID         Filter by series
      --season ID         Filter by season
      --stage ID          Filter by stage
      --puzzle ID         Filter by puzzle
      --type TYPE         Filter by item type
      --ids ID1,ID2       Filter by specific IDs
      --count             Show content counts
      --dry-run           Show per-layer normalization preview
      --force             Regenerate all audio
    """
    args = sys.argv[1:]
    if not args or args[0] in ("-h", "--help"):
        print(main.__doc__)
        sys.exit(0)

    # Parse input file (first positional arg)
    input_file = None
    locale = "pt_BR"
    output_dir = None
    voice_file = None
    voice_text = None
    model_file = None
    vocab_file = None
    device = "mps"
    type_filter = None
    ids_filter = None
    series_filter = None
    season_filter = None
    stage_filter = None
    puzzle_filter = None
    force = False

    i = 0
    while i < len(args):
        if args[i] == "--output-dir" and i + 1 < len(args):
            output_dir = Path(args[i + 1])
            i += 2
        elif args[i] == "--voice-file" and i + 1 < len(args):
            voice_file = args[i + 1]
            i += 2
        elif args[i] == "--voice-text" and i + 1 < len(args):
            voice_text = args[i + 1]
            i += 2
        elif args[i] == "--model-file" and i + 1 < len(args):
            model_file = args[i + 1]
            i += 2
        elif args[i] == "--vocab-file" and i + 1 < len(args):
            vocab_file = args[i + 1]
            i += 2
        elif args[i] == "--locale" and i + 1 < len(args):
            locale = args[i + 1]
            i += 2
        elif args[i] == "--device" and i + 1 < len(args):
            device = args[i + 1]
            i += 2
        elif args[i] == "--type" and i + 1 < len(args):
            type_filter = args[i + 1]
            i += 2
        elif args[i] == "--ids" and i + 1 < len(args):
            ids_filter = set(args[i + 1].split(","))
            i += 2
        elif args[i] == "--series" and i + 1 < len(args):
            series_filter = args[i + 1]
            i += 2
        elif args[i] == "--season" and i + 1 < len(args):
            season_filter = args[i + 1]
            i += 2
        elif args[i] == "--stage" and i + 1 < len(args):
            stage_filter = args[i + 1]
            i += 2
        elif args[i] == "--puzzle" and i + 1 < len(args):
            puzzle_filter = args[i + 1]
            i += 2
        elif args[i] == "--force":
            force = True
            i += 1
        elif not args[i].startswith("--") and input_file is None:
            input_file = Path(args[i])
            i += 1
        else:
            i += 1

    if input_file is None:
        print("Error: input JSON file required")
        sys.exit(1)

    # Load items
    with open(input_file, encoding="utf-8") as f:
        items = json.load(f)

    print(f"Loaded {len(items)} items from {input_file}")

    # Apply filters
    if series_filter or season_filter or stage_filter or puzzle_filter:
        items = filter_content(items, series_filter, season_filter, stage_filter, puzzle_filter)
        parts = []
        if series_filter: parts.append(f"series={series_filter}")
        if season_filter: parts.append(f"season={season_filter}")
        if stage_filter: parts.append(f"stage={stage_filter}")
        if puzzle_filter: parts.append(f"puzzle={puzzle_filter}")
        print(f"Hierarchy filter: {len(items)} items ({', '.join(parts)})")

    if ids_filter:
        items = [item for item in items if item["id"] in ids_filter]
        print(f"Filtered to IDs: {len(items)} items")

    if type_filter:
        items = [item for item in items if item["type"] == type_filter]
        print(f"Filtered to type '{type_filter}': {len(items)} items")

    if "--count" in sys.argv:
        show_count(items, group_by_series=bool(series_filter))
        return

    if "--dry-run" in sys.argv:
        show_dry_run(items, locale)
        return

    # Audio generation requires all paths
    if not all([output_dir, voice_file, voice_text, model_file, vocab_file]):
        print("Error: --output-dir, --voice-file, --voice-text, --model-file, --vocab-file required for generation")
        sys.exit(1)

    progress_file = output_dir / "progress.json"

    generate_audio(
        items=items,
        output_dir=output_dir,
        progress_file=progress_file,
        voice_file=voice_file,
        voice_text=voice_text,
        model_file=model_file,
        vocab_file=vocab_file,
        locale=locale,
        force=force,
        device=device,
    )

    print(f"\nDONE! Output: {output_dir}")


if __name__ == "__main__":
    main()
